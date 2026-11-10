"""Rutas y constantes del sistema.

En Colab:
- Memoria permanente: /content/drive/MyDrive/EDDIE_STUDIO  (Drive Pro)
- Trabajo rápido:     /content/eddie                        (disco local de la sesión)

Ambas se pueden cambiar con variables de entorno (EDDIE_DRIVE, EDDIE_LOCAL)
para probar fuera de Colab.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DRIVE = Path(os.environ.get("EDDIE_DRIVE", "/content/drive/MyDrive/EDDIE_STUDIO"))
LOCAL = Path(os.environ.get("EDDIE_LOCAL", "/content/eddie"))

# Versión fija de Blender (LTS). Cambiarla aquí cambia todo el sistema.
BLENDER_VERSION = os.environ.get("EDDIE_BLENDER_VERSION", "5.2.4")
BLENDER_SERIE = ".".join(BLENDER_VERSION.split(".")[:2])
BLENDER_ARCHIVO = f"blender-{BLENDER_VERSION}-linux-x64.tar.xz"
BLENDER_URL = f"https://download.blender.org/release/Blender{BLENDER_SERIE}/{BLENDER_ARCHIVO}"

PUERTO_SERVIDOR = int(os.environ.get("EDDIE_PUERTO", "8765"))

# Estructura permanente en Drive (ver docs/01_ARQUITECTURA.md §6).
CARPETAS_DRIVE = [
    "privado",
    "sistema",
    "modelos_ia",
    "voces",
    "biblioteca/_entrada",
    "biblioteca/personajes",
    "biblioteca/escenarios",
    "biblioteca/objetos",
    "biblioteca/anatomia",
    "biblioteca/animaciones",
    "biblioteca/hdri",
    "biblioteca/texturas",
    "biblioteca/sonidos",
    "biblioteca/musica",
    "biblioteca/licencias",
    "proyectos/_registro",
    "entregas",
]

# Estructura temporal en el disco local de la sesión.
CARPETAS_LOCAL = ["bin", "blender", "trabajos", "tmp", "cache", "logs"]


def ruta_drive(*partes: str) -> Path:
    return DRIVE.joinpath(*partes)


def ruta_local(*partes: str) -> Path:
    return LOCAL.joinpath(*partes)


def crear_estructura() -> dict:
    """Crea las carpetas de Drive y locales. Es idempotente."""
    creadas = []
    for base, lista in ((DRIVE, CARPETAS_DRIVE), (LOCAL, CARPETAS_LOCAL)):
        for c in lista:
            p = base / c
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                creadas.append(str(p))
    return {"drive": str(DRIVE), "local": str(LOCAL), "creadas": creadas}
