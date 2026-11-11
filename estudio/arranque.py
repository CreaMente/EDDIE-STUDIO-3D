"""Arranque completo del estudio (se llama desde la libreta de Colab).

1. Estructura de carpetas en Drive y en disco local.
2. Claves (Drive privado + Colab Secrets) → variables de entorno.
3. Blender (copia de Drive o descarga oficial).
4. Servidor MCP bajo un supervisor que lo reinicia si se cae.
5. Túnel temporal (Cloudflare) y verificación de punta a punta.
6. Muestra la dirección, la clave y la configuración para Antigravity.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from . import blender, claves, config, presentacion, sistema, tunel


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _salud(url: str, timeout: float = 10) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/salud", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _supervisor_pid_file():
    return config.ruta_local("servidor.pid")


def iniciar_servidor(clave: str) -> None:
    """Lanza el servidor bajo un bucle supervisor (bash) que lo relanza si termina."""
    detener_servidor()
    log = config.ruta_local("logs", "servidor.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["EDDIE_CLAVE_ESTUDIO"] = clave
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(config.REPO) + os.pathsep + env.get("PYTHONPATH", "")
    supervisor = (
        f'while true; do "{sys.executable}" -m servidor.mcp_server >> "{log}" 2>&1; '
        f'echo "[supervisor] servidor terminó ($?); reinicio en 1 s" >> "{log}"; sleep 1; done'
    )
    proc = subprocess.Popen(["bash", "-c", supervisor], cwd=str(config.REPO), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    _supervisor_pid_file().write_text(str(proc.pid))


def detener_servidor() -> None:
    p = _supervisor_pid_file()
    if p.exists():
        try:
            os.killpg(int(p.read_text().strip()), 15)
        except (ProcessLookupError, ValueError, PermissionError):
            pass
        p.unlink(missing_ok=True)


def detener_todo() -> None:
    tunel.detener()
    detener_servidor()


def config_antigravity(url: str, clave: str) -> dict:
    return {
        "mcpServers": {
            "eddie-studio": {
                "serverUrl": f"{url}/mcp",
                "headers": {"Authorization": f"Bearer {clave}"},
            }
        }
    }


def iniciar(instalar_blender: bool = True, preferir_ngrok: bool = False, panel: bool = False) -> dict:
    t0 = time.time()
    _log("Creando carpetas…")
    config.crear_estructura()

    _log("Cargando claves…")
    todas = claves.cargar_todas()
    claves.exportar_a_entorno(todas)
    faltan = [n for n in claves.OBLIGATORIAS if n not in todas]
    _log(f"Claves presentes: {', '.join(sorted(todas)) or 'ninguna'}")
    if faltan:
        _log(f"⚠️  Faltan claves obligatorias: {', '.join(faltan)} (algunas funciones no podrán descargar modelos)")

    if instalar_blender:
        _log("Preparando Blender…")
        blender.dependencias_sistema(_log)
        exe = blender.instalar(_log)
        _log(f"Blender listo: {exe}")

    clave = claves.clave_estudio(renovar=True)
    _log("Iniciando servidor del estudio (clave nueva para esta sesión)…")
    iniciar_servidor(clave)
    local = f"http://127.0.0.1:{config.PUERTO_SERVIDOR}"
    for _ in range(60):
        if _salud(local, 2):
            break
        time.sleep(1)
    else:
        log = config.ruta_local("logs", "servidor.log")
        raise RuntimeError("El servidor no respondió. Registro:\n" + log.read_text(errors="replace")[-3000:])

    _log("Abriendo túnel…")
    info = tunel.iniciar(preferir_ngrok=preferir_ngrok)
    url = info["url"]
    publico = False
    for _ in range(45):  # el DNS del túnel nuevo tarda unos segundos
        if _salud(url, 8):
            publico = True
            break
        time.sleep(2)
    if not publico:
        _log("⚠️  El túnel aún no responde desde internet; suele tardar menos de un minuto más.")

    cfg = config_antigravity(url, clave)
    config.ruta_privada("conexion_actual.json").write_text(
        json.dumps({"url": url, **cfg}, indent=2), encoding="utf-8")

    diag = sistema.diagnostico(sorted(todas))
    resultado = {"url": url, "clave": clave, "antigravity": cfg, "diagnostico": diag,
                 "drive": str(config.DRIVE), "tipo_tunel": info.get("tipo"), "segundos": time.time() - t0}
    if panel:
        _log("Listo.")
        presentacion.mostrar(resultado)
        return resultado
    gpu = diag["gpu"][0]["nombre"] if diag["gpu"] else "SIN GPU"
    barra = "═" * 72
    print(f"\n{barra}\n  EDDIE STUDIO 3D — LISTO en {time.time() - t0:.0f} s   (GPU: {gpu})\n{barra}")
    print(f"\n  Dirección:  {url}/mcp")
    print(f"  Clave:      {clave}")
    print("\n  En Antigravity: panel del agente → ⋯ → MCP Servers → Manage MCP Servers →")
    print("  View raw config, pega esto (reemplaza el bloque eddie-studio si ya existe) y pulsa Refresh:\n")
    print(json.dumps(cfg, indent=2))
    print(f"\n  (También quedó guardado en Drive: EDDIE_PRIVADO/conexion_actual.json)\n{barra}\n")
    return resultado


def vigilar(intervalo: float = 5.0) -> None:
    """Mantiene viva la celda: muestra el registro y relanza el túnel si se cae."""
    log = config.ruta_local("logs", "servidor.log")
    pos = log.stat().st_size if log.exists() else 0
    _log("Vigilando (detén la celda para apagar el estudio).")
    try:
        while True:
            if log.exists() and log.stat().st_size > pos:
                with open(log, "r", errors="replace") as f:
                    f.seek(pos)
                    nuevo = f.read()
                    pos = f.tell()
                for ln in nuevo.splitlines()[-30:]:
                    if "/salud" not in ln:
                        print(ln, flush=True)
            if not tunel.vivo():
                _log("El túnel se cayó; abriendo uno nuevo…")
                info = tunel.iniciar()
                clave = claves.clave_estudio()
                _log("NUEVA dirección (actualízala en Antigravity):")
                print(json.dumps(config_antigravity(info["url"], clave), indent=2), flush=True)
            time.sleep(intervalo)
    except KeyboardInterrupt:
        _log("Celda detenida. El servidor y el túnel siguen activos mientras la sesión viva; "
             "usa estudio.arranque.detener_todo() para apagarlos.")
