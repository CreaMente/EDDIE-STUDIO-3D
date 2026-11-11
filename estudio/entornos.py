"""Entornos de Python aislados para los modelos de IA (uno por familia).

Cada modelo trae dependencias pesadas (torch, transformers, gradio…) que podrían romper los paquetes
de Colab o del servidor. Por eso cada familia vive en su propio entorno, creado con `uv` (rápido) en el
disco local de la sesión: <LOCAL>/entornos/<nombre>/.

Un archivo `.listo` guarda la huella de los paquetes: si no cambió, no se reinstala.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config

ENTORNOS: dict[str, dict] = {
    # Fase 2: voz (VoxCPM2) + verificación y tiempos por palabra (Whisper vía stable-ts).
    "voz": {
        "python": "3.12",
        "paquetes": ["voxcpm[timestamps]==2.0.3", "stable-ts==2.19.1", "soundfile", "numpy"],
    },
}


def ruta(nombre: str) -> Path:
    return config.ruta_local("entornos", nombre)


def python(nombre: str) -> Path:
    return ruta(nombre) / "bin" / "python"


def _huella(defin: dict, extra_indices: list[str]) -> str:
    return hashlib.sha256(repr((defin, extra_indices)).encode()).hexdigest()[:16]


def _uv() -> str:
    w = shutil.which("uv")
    if w:
        return w
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
    return shutil.which("uv") or str(Path(sys.executable).parent / "uv")


def asegurar(nombre: str, registro=print, indice_torch: str | None = None) -> Path:
    """Crea o actualiza el entorno y devuelve su Python.

    indice_torch: índice alternativo para torch (p. ej. el de CPU en pruebas sin GPU)."""
    defin = ENTORNOS[nombre]
    extra = [indice_torch] if indice_torch else []
    huella = _huella(defin, extra)
    marca = ruta(nombre) / ".listo"
    if marca.exists() and marca.read_text().strip() == huella and python(nombre).exists():
        return python(nombre)
    uv = _uv()
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(config.ruta_local("cache", "uv"))
    env.setdefault("UV_HTTP_TIMEOUT", "300")
    registro(f"Entorno «{nombre}»: creando…")
    subprocess.run([uv, "venv", "--python", defin["python"], "--seed", str(ruta(nombre))],
                   check=True, env=env, capture_output=True)
    cmd = [uv, "pip", "install", "--python", str(python(nombre)), *defin["paquetes"]]
    if indice_torch:
        cmd += ["--extra-index-url", indice_torch, "--index-strategy", "unsafe-best-match"]
    registro(f"Entorno «{nombre}»: instalando {len(defin['paquetes'])} paquetes (unos minutos la primera vez)…")
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Falló la instalación del entorno «{nombre}»:\n{r.stderr[-3000:]}")
    marca.write_text(huella)
    registro(f"Entorno «{nombre}»: listo.")
    return python(nombre)


def comando(nombre: str, modulo: str, *args: str) -> list[str]:
    """Línea de comando para correr `python -m <modulo>` dentro del entorno."""
    return [str(python(nombre)), "-m", modulo, *args]
