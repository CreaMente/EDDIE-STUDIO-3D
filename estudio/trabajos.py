"""Trabajos en segundo plano.

Todo lo que pueda tardar más de un minuto (render, descargas, instalación de
modelos) corre como trabajo. El túnel temporal de Cloudflare corta respuestas de
más de ~100 s, así que el servidor nunca espera: inicia el trabajo y devuelve su id.

Cada trabajo vive en <LOCAL>/trabajos/<id>/:
  comando.sh   lo que se ejecuta
  log.txt      salida combinada (stdout + stderr)
  meta.json    nombre, inicio, pid
  salida.txt   código de salida (aparece al terminar)
Se puede consultar aunque el servidor se reinicie.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from . import config


def _dir_trabajos() -> Path:
    d = config.ruta_local("trabajos")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pid_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Un proceso zombi sigue "vivo" para kill(0); revisamos /proc.
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().split()[2]
        return estado != "Z"
    except OSError:
        return True


def iniciar(comando: str, nombre: str = "", directorio: str | None = None,
            entorno: dict[str, str] | None = None) -> dict:
    tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = _dir_trabajos() / tid
    d.mkdir(parents=True)
    script = d / "comando.sh"
    salida = d / "salida.txt"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -o pipefail\n"
        f"{comando}\n",
        encoding="utf-8",
    )
    # El envoltorio guarda el código de salida aunque el servidor muera.
    envoltorio = f'bash "{script}"; echo $? > "{salida}"'
    log = open(d / "log.txt", "ab", buffering=0)
    env = os.environ.copy()
    if entorno:
        env.update(entorno)
    proc = subprocess.Popen(
        ["bash", "-c", envoltorio],
        cwd=directorio or str(config.LOCAL),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    meta = {
        "id": tid,
        "nombre": nombre or comando.splitlines()[0][:80],
        "comando": comando,
        "directorio": directorio or str(config.LOCAL),
        "inicio": time.time(),
        "pid": proc.pid,
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": tid, "nombre": meta["nombre"], "pid": proc.pid, "estado": "corriendo"}


def _cola(ruta: Path, lineas: int) -> str:
    if not ruta.exists() or lineas <= 0:
        return ""
    with open(ruta, "rb") as f:
        f.seek(0, os.SEEK_END)
        tam = f.tell()
        bloque = min(tam, max(4096, lineas * 300))
        f.seek(tam - bloque)
        texto = f.read().decode("utf-8", errors="replace")
    # Las barras de progreso usan \r; nos quedamos con el último estado de cada línea.
    filas = [ln.split("\r")[-1] for ln in texto.splitlines()]
    return "\n".join(filas[-lineas:])


def estado(tid: str, lineas_log: int = 40) -> dict:
    d = _dir_trabajos() / tid
    if not (d / "meta.json").exists():
        return {"id": tid, "error": "No existe ese trabajo"}
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    salida = d / "salida.txt"
    if salida.exists():
        txt = salida.read_text().strip()
        codigo = int(txt) if txt.lstrip("-").isdigit() else None
        est = "terminado" if codigo == 0 else "fallido"
        fin = salida.stat().st_mtime
    elif _pid_vivo(meta["pid"]):
        est, codigo, fin = "corriendo", None, None
    else:
        est, codigo, fin = "interrumpido", None, None
    if (d / "cancelado").exists() and est != "terminado":
        est = "cancelado"
    dur = (fin or time.time()) - meta["inicio"]
    return {
        "id": tid,
        "nombre": meta["nombre"],
        "estado": est,
        "codigo_salida": codigo,
        "duracion_s": round(dur, 1),
        "log": _cola(d / "log.txt", lineas_log),
        "carpeta": str(d),
    }


def listar(limite: int = 30) -> list[dict]:
    ids = sorted((p.name for p in _dir_trabajos().iterdir() if p.is_dir()), reverse=True)[:limite]
    return [{k: v for k, v in estado(i, 0).items() if k != "log"} for i in ids]


def cancelar(tid: str) -> dict:
    d = _dir_trabajos() / tid
    if not (d / "meta.json").exists():
        return {"id": tid, "error": "No existe ese trabajo"}
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    (d / "cancelado").touch()
    try:
        os.killpg(meta["pid"], signal.SIGTERM)
        time.sleep(2)
        if _pid_vivo(meta["pid"]):
            os.killpg(meta["pid"], signal.SIGKILL)
    except ProcessLookupError:
        pass
    return estado(tid, 10)


def esperar(tid: str, max_s: float) -> dict:
    """Espera hasta max_s segundos (útil para trabajos cortos)."""
    limite = time.time() + max_s
    while time.time() < limite:
        e = estado(tid, 0)
        if e.get("estado") != "corriendo":
            break
        time.sleep(0.5)
    return estado(tid)
