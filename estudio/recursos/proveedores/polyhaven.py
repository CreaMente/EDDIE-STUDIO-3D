"""Poly Haven (CC0): todos los HDRI, texturas y modelos, en las MISMAS carpetas que ya usa el estudio
(estudio/polyhaven.py), así lo descargado se usa directamente en las tomas sin volver a bajarlo:
  biblioteca/hdri/<id>_<res>.hdr · biblioteca/texturas/<id>_<res>/<mapa>.jpg · biblioteca/modelos/<id>_<res>/
"""

from __future__ import annotations

from pathlib import Path

from ... import config
from ...polyhaven import API, MAPAS_TEXTURA
from ..descargas import bajar
from . import leer_json

FUENTE = "polyhaven"
TIPOS = {0: "hdri", 1: "textura", 2: "modelo"}
# Resoluciones que usan las tomas: borrador (escala < 100) y final.
PERFILES = {"produccion": {"hdri": ["2k", "4k"], "textura": ["1k", "2k"], "modelo": ["1k"]},
            "ligero": {"hdri": ["2k"], "textura": ["1k"], "modelo": ["1k"]},
            "alta": {"hdri": ["2k", "4k", "8k"], "textura": ["1k", "2k", "4k"], "modelo": ["1k", "2k"]}}
_archivos: dict[str, dict] = {}


def descubrir(registro=print) -> list[dict]:
    datos = leer_json(f"{API}/assets?t=all")
    salida = []
    for clave, v in datos.items():
        tipo = TIPOS.get(v.get("type"))
        if not tipo:
            continue
        salida.append({"id": f"{FUENTE}:{tipo}:{clave}", "fuente": FUENTE, "tipo": tipo, "clave": clave,
                       "nombre": v.get("name", clave), "categorias": v.get("categories", []),
                       "etiquetas": v.get("tags", []), "licencia": "CC0-1.0",
                       "credito": "Poly Haven (polyhaven.com) — " + ", ".join(sorted(v.get("authors", {}))),
                       "url_pagina": f"https://polyhaven.com/a/{clave}",
                       "extra": {"descargas": v.get("download_count", 0),
                                 "dimensiones_mm": v.get("dimensions"), "polycount": v.get("polycount")}})
    registro(f"Poly Haven: {len(salida)} recursos")
    return salida


def archivos(clave: str) -> dict:
    if clave not in _archivos:
        _archivos[clave] = leer_json(f"{API}/files/{clave}")
    return _archivos[clave]


def _lista(entrada: dict, perfil: str) -> list[tuple[str, Path, int, str]]:
    """(url, destino, tamaño, md5) de todo lo que hay que bajar para esta entrada."""
    clave, tipo = entrada["clave"], entrada["tipo"]
    a = archivos(clave)
    salida = []
    for res in PERFILES[perfil][tipo]:
        if tipo == "hdri":
            d = a.get("hdri", {}).get(res, {}).get("hdr")
            if d:
                salida.append((d["url"], config.ruta_drive("biblioteca", "hdri", f"{clave}_{res}.hdr"),
                               d.get("size"), d.get("md5")))
        elif tipo == "textura":
            carpeta = config.ruta_drive("biblioteca", "texturas", f"{clave}_{res}")
            for nombre, mapa in MAPAS_TEXTURA.items():
                d = a.get(mapa, {}).get(res, {}).get("jpg")
                if d:
                    salida.append((d["url"], carpeta / f"{nombre}.jpg", d.get("size"), d.get("md5")))
        else:
            g = a.get("gltf", {}).get(res, {}).get("gltf")
            if g:
                carpeta = config.ruta_drive("biblioteca", "modelos", f"{clave}_{res}")
                salida.append((g["url"], carpeta / Path(g["url"]).name, g.get("size"), g.get("md5")))
                for rel, d in g.get("include", {}).items():
                    salida.append((d["url"], carpeta / rel, d.get("size"), d.get("md5")))
    return salida


def estimar(entrada: dict, perfil: str = "produccion") -> int:
    return sum(t or 0 for _, _, t, _ in _lista(entrada, perfil))


def descargar(entrada: dict, perfil: str = "produccion", registro=print) -> dict:
    total = 0
    lista = _lista(entrada, perfil)
    if not lista:
        raise IOError("la fuente no publica archivos en las resoluciones del perfil")
    for url, destino, tam, md5 in lista:
        total += bajar(url, destino, tam=tam, md5=md5, registro=registro)
    if entrada["tipo"] == "modelo":  # la carpeta del modelo (no su subcarpeta textures/)
        rutas = sorted({str(config.ruta_drive("biblioteca", "modelos", f"{entrada['clave']}_{res}"))
                        for res in PERFILES[perfil]["modelo"]
                        if archivos(entrada["clave"]).get("gltf", {}).get(res)})
    else:
        rutas = sorted({str(d if entrada["tipo"] == "hdri" else d.parent) for _, d, _, _ in lista})
    if entrada["tipo"] == "modelo":  # misma marca que estudio/polyhaven.modelo()
        for res in PERFILES[perfil]["modelo"]:
            g = archivos(entrada["clave"]).get("gltf", {}).get(res, {}).get("gltf")
            if g:
                carpeta = config.ruta_drive("biblioteca", "modelos", f"{entrada['clave']}_{res}")
                marca = carpeta / ".completo"
                if not marca.exists():
                    marca.write_text(Path(g["url"]).name, encoding="utf-8")
    return {"ruta": rutas[-1], "bytes": total, "extra": {"rutas": rutas, "perfil": perfil}}
