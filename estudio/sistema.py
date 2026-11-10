"""Diagnóstico del entorno: GPU, disco, RAM, programas."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import config


def _cmd(args: list[str], timeout: float = 20) -> str | None:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def gpu() -> list[dict]:
    out = _cmd([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,driver_version,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return []
    filas = []
    for ln in out.splitlines():
        p = [x.strip() for x in ln.split(",")]
        if len(p) >= 6:
            filas.append({
                "nombre": p[0],
                "vram_total_mb": int(float(p[1])),
                "vram_usada_mb": int(float(p[2])),
                "driver": p[3],
                "uso_pct": p[4],
                "temp_c": p[5],
            })
    return filas


def memoria() -> dict:
    datos = {}
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            k, v = ln.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                datos[k] = round(int(v.split()[0]) / 1024 / 1024, 1)
    except OSError:
        pass
    return {"ram_total_gb": datos.get("MemTotal"), "ram_libre_gb": datos.get("MemAvailable")}


def disco(ruta: Path) -> dict | None:
    try:
        u = shutil.disk_usage(ruta)
    except OSError:
        return None
    return {"ruta": str(ruta), "total_gb": round(u.total / 1e9, 1), "libre_gb": round(u.free / 1e9, 1)}


def blender_bin() -> Path | None:
    """Ruta del ejecutable de Blender instalado por el sistema (o en el PATH)."""
    p = config.ruta_local("blender", f"blender-{config.BLENDER_VERSION}-linux-x64", "blender")
    if p.exists():
        return p
    w = shutil.which("blender")
    return Path(w) if w else None


def version_blender() -> str | None:
    b = blender_bin()
    if not b:
        return None
    out = _cmd([str(b), "--version"], timeout=60)
    return out.splitlines()[0] if out else None


def diagnostico(claves_presentes: list[str] | None = None) -> dict:
    tunel = config.ruta_local("tunel.json")
    return {
        "gpu": gpu(),
        "memoria": memoria(),
        "disco_local": disco(config.LOCAL if config.LOCAL.exists() else Path("/")),
        "disco_drive": disco(config.DRIVE) if config.DRIVE.exists() else None,
        "drive_montado": config.DRIVE.exists(),
        "blender": version_blender(),
        "ffmpeg": (_cmd(["ffmpeg", "-version"]) or "").split("\n")[0] or None,
        "claves_presentes": claves_presentes,
        "tunel": json.loads(tunel.read_text()) if tunel.exists() else None,
        "repo": str(config.REPO),
    }
