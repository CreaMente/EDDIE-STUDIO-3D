"""Proveedores de recursos. Cada uno sabe descubrir lo que ofrece su fuente y descargarlo.

Interfaz (módulo):
  FUENTE: str                                 clave en fuentes.json
  descubrir(registro) -> list[dict]            entradas para el catálogo (id «fuente:tipo:clave»)
  descargar(entrada, perfil, registro) -> dict {"ruta": str, "bytes": int, "extra": {...}}
  estimar(entrada, perfil) -> int | None       bytes que ocupará (si se puede saber sin bajar)
"""

from __future__ import annotations

import json
import time
import urllib.request

from ..descargas import CABECERAS

AUTOMATICOS = ["polyhaven", "ambientcg", "estilos100", "blender_studio"]


def modulo(nombre: str):
    import importlib
    return importlib.import_module(f"{__name__}.{nombre}")


def leer_json(url: str, reintentos: int = 4, timeout: int = 60):
    error = None
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS), timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            error = e
            time.sleep(2 ** i)
    raise IOError(f"No se pudo leer {url}: {error}")


def leer_texto(url: str, reintentos: int = 3, timeout: int = 60) -> str:
    error = None
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS), timeout=timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            error = e
            time.sleep(2 ** i)
    raise IOError(f"No se pudo leer {url}: {error}")
