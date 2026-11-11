"""Recursos de Poly Haven (CC0): HDRI y texturas, con caché en Drive.

API pública y gratuita, también para uso comercial (pide que se indique que los recursos son de
Poly Haven: se anota en los créditos del proyecto).
Caché: <DRIVE>/biblioteca/hdri/<id>_<res>.hdr y <DRIVE>/biblioteca/texturas/<id>_<res>/<mapa>.jpg
"""

from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

from . import config

API = "https://api.polyhaven.com"
CABECERAS = {"User-Agent": "EDDIE-STUDIO-3D/1.0 (estudio de video personal)"}
MAPAS_TEXTURA = {"color": "Diffuse", "normal": "nor_gl", "rugosidad": "Rough", "ao": "AO"}


def _json(url: str):
    req = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _bajar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    req = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=4 * 1024 * 1024)
    tmp.replace(destino)


def buscar(tipo: str = "hdris", categoria: str = "", limite: int = 30) -> list[dict]:
    """Lista recursos por popularidad. tipo: hdris | textures | models."""
    url = f"{API}/assets?type={tipo}" + (f"&categories={categoria}" if categoria else "")
    datos = _json(url)
    orden = sorted(datos.items(), key=lambda kv: -kv[1].get("download_count", 0))[:limite]
    return [{"id": k, "nombre": v.get("name"), "categorias": v.get("categories"), "tags": v.get("tags")}
            for k, v in orden]


def hdri(identificador: str, resolucion: str = "4k") -> Path:
    destino = config.ruta_drive("biblioteca", "hdri", f"{identificador}_{resolucion}.hdr")
    if not destino.exists():
        archivos = _json(f"{API}/files/{identificador}")
        _bajar(archivos["hdri"][resolucion]["hdr"]["url"], destino)
    return destino


def textura(identificador: str, resolucion: str = "2k") -> dict[str, str]:
    carpeta = config.ruta_drive("biblioteca", "texturas", f"{identificador}_{resolucion}")
    rutas = {}
    archivos = None
    for nombre, clave in MAPAS_TEXTURA.items():
        destino = carpeta / f"{nombre}.jpg"
        if not destino.exists():
            archivos = archivos or _json(f"{API}/files/{identificador}")
            if clave not in archivos:
                continue
            _bajar(archivos[clave][resolucion]["jpg"]["url"], destino)
        rutas[nombre] = str(destino)
    return rutas


def modelo(identificador: str, resolucion: str = "1k") -> str:
    """Modelo 3D (glTF con sus texturas) de Poly Haven, guardado en <DRIVE>/biblioteca/modelos/<id>/."""
    carpeta = config.ruta_drive("biblioteca", "modelos", f"{identificador}_{resolucion}")
    marca = carpeta / ".completo"
    if not marca.exists():
        archivos = _json(f"{API}/files/{identificador}")
        g = archivos["gltf"][resolucion]["gltf"]
        destino = carpeta / Path(g["url"]).name
        _bajar(g["url"], destino)
        for relativa, datos in g.get("include", {}).items():
            _bajar(datos["url"], carpeta / relativa)
        marca.write_text(destino.name, encoding="utf-8")
    return str(carpeta / marca.read_text(encoding="utf-8").strip())
