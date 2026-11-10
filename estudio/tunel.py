"""Túnel HTTPS temporal hacia el servidor MCP.

Principal: Cloudflare Quick Tunnel (sin cuenta; la dirección cambia en cada sesión).
Opcional: ngrok, si existe NGROK_AUTHTOKEN (dirección fija del plan gratuito).

Limitaciones de Cloudflare Quick Tunnel (documentación oficial):
- No admite Server-Sent Events → el servidor responde en JSON sin streaming.
- Máximo 200 peticiones simultáneas; respuestas de más de ~100 s se cortan →
  todo lo largo corre como trabajo en segundo plano.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import time
import urllib.request
from pathlib import Path

from . import config

CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
PATRON_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _cloudflared() -> Path:
    w = shutil.which("cloudflared")
    if w:
        return Path(w)
    p = config.ruta_local("bin", "cloudflared")
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".parcial")
        with urllib.request.urlopen(CLOUDFLARED_URL, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(p)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def _guardar(info: dict) -> dict:
    config.ruta_local("tunel.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def iniciar_cloudflare(puerto: int, espera_s: float = 60) -> dict:
    exe = _cloudflared()
    log = config.ruta_local("logs", "tunel.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    f = open(log, "wb", buffering=0)
    proc = subprocess.Popen(
        [str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{puerto}"],
        stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    limite = time.time() + espera_s
    while time.time() < limite:
        texto = log.read_text(errors="replace") if log.exists() else ""
        m = PATRON_URL.search(texto)
        if m:
            return _guardar({"tipo": "cloudflare", "url": m.group(0), "pid": proc.pid, "inicio": time.time()})
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("Cloudflare no entregó una dirección. Últimas líneas:\n" +
                       "\n".join(log.read_text(errors="replace").splitlines()[-15:]))


def iniciar_ngrok(puerto: int, token: str) -> dict:
    subprocess.run(["pip", "install", "-q", "ngrok"], check=True)
    import ngrok  # type: ignore

    listener = ngrok.forward(puerto, authtoken=token)
    return _guardar({"tipo": "ngrok", "url": listener.url(), "pid": os.getpid(), "inicio": time.time()})


def iniciar(puerto: int | None = None, preferir_ngrok: bool = False) -> dict:
    puerto = puerto or config.PUERTO_SERVIDOR
    token = os.environ.get("NGROK_AUTHTOKEN")
    if preferir_ngrok and token:
        try:
            return iniciar_ngrok(puerto, token)
        except Exception as e:  # cae a Cloudflare
            print(f"ngrok falló ({e}); uso Cloudflare.")
    return iniciar_cloudflare(puerto)


def detener() -> None:
    p = config.ruta_local("tunel.json")
    if not p.exists():
        return
    info = json.loads(p.read_text())
    if info.get("tipo") == "cloudflare":
        try:
            os.killpg(info["pid"], 15)
        except (ProcessLookupError, PermissionError):
            pass
    p.unlink(missing_ok=True)


def vivo() -> bool:
    p = config.ruta_local("tunel.json")
    if not p.exists():
        return False
    info = json.loads(p.read_text())
    if info.get("tipo") != "cloudflare":
        return True
    try:
        os.kill(info["pid"], 0)
        return True
    except ProcessLookupError:
        return False
