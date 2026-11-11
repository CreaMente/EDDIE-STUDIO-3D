"""Lo que usan las tomas: resuelve texturas, HDRI y modelos de cualquier fuente aprobada.

- Texturas/materiales: id de Poly Haven («beige_wall_001») o de ambientCG («Bricks076», o con prefijo
  «acg:Bricks076»). Devuelve los mapas {color, normal, rugosidad, ao} que entiende set_escena.
- HDRI: id de Poly Haven o de ambientCG («acg:DaySkyHDRI072B»).
Si el recurso aún no está en Drive se baja en ese momento (y queda para siempre).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config, polyhaven

USADOS: set[str] = set()  # fuentes usadas en esta toma (para los créditos)
CREDITOS = {"polyhaven": "Iluminación HDRI, texturas y modelos 3D: Poly Haven (polyhaven.com), CC0.",
            "ambientcg": "Materiales y texturas: ambientCG (ambientcg.com), CC0."}
_ACG = re.compile(r"^[A-Z][A-Za-z]+\d{3}[A-Z]?$")
MAPAS_TOMA = ("color", "normal", "rugosidad", "ao")


def es_ambientcg(identificador: str) -> bool:
    return identificador.startswith("acg:") or bool(_ACG.match(identificador))


def _acg(identificador: str) -> str:
    return identificador.split(":", 1)[1] if identificador.startswith("acg:") else identificador


def _mapas(carpeta: Path) -> dict:
    d = json.loads((carpeta / "mapas.json").read_text(encoding="utf-8"))
    return {k: str(carpeta / v) for k, v in d.items()}


def textura(identificador: str, resolucion: str = "2k") -> dict[str, str]:
    if identificador.startswith("ph:"):
        identificador = identificador[3:]
    elif es_ambientcg(identificador):
        from .proveedores import ambientcg
        atributo = "1K-JPG" if resolucion == "1k" else "2K-JPG"
        base = config.ruta_drive("biblioteca", "ambientcg", "material")
        listo = base / f"{_acg(identificador)}_2K-JPG"  # el de producción sirve también para borradores
        carpeta = listo if (listo / ".completo").exists() else ambientcg.asegurar(_acg(identificador), "material", atributo)
        USADOS.add("ambientcg")
        return {k: v for k, v in _mapas(carpeta).items() if k in MAPAS_TOMA}
    USADOS.add("polyhaven")
    return polyhaven.textura(identificador, resolucion)


def hdri(identificador: str, resolucion: str = "4k") -> Path:
    if es_ambientcg(identificador):
        from .proveedores import ambientcg
        atributo = "4K" if resolucion in ("4k", "8k") else "2K"
        carpeta = ambientcg.asegurar(_acg(identificador), "hdri", atributo)
        USADOS.add("ambientcg")
        return Path(_mapas(carpeta)["hdri"])
    USADOS.add("polyhaven")
    return polyhaven.hdri(identificador.removeprefix("ph:"), resolucion)


def modelo(identificador: str, resolucion: str = "1k") -> str:
    USADOS.add("polyhaven")
    return polyhaven.modelo(identificador.removeprefix("ph:"), resolucion)


def es_modelo_polyhaven(identificador: str) -> bool:
    """¿Es un id de modelo de Poly Haven ya descargado (o en el catálogo)?"""
    ident = identificador.removeprefix("ph:")
    if any(config.ruta_drive("biblioteca", "modelos").glob(f"{ident}_*/.completo")):
        return True
    try:
        from . import catalogo
        return catalogo.obtener(f"polyhaven:modelo:{ident}") is not None
    except Exception:  # noqa: BLE001
        return False


def creditos() -> list[str]:
    return [CREDITOS[f] for f in sorted(USADOS) if f in CREDITOS]
