"""ambientCG (CC0): materiales PBR, HDRI, calcomanías y atlas, por su API pública v2.

Cada recurso se descarga como zip al disco local y se extrae en Drive:
  biblioteca/ambientcg/<tipo>/<id>_<atributo>/  (+ mapas.json con color/normal/rugosidad/ao/…)
Solo recursos ya publicados (los de «acceso anticipado» son para mecenas y no se tocan).
"""

from __future__ import annotations

import json
import re
import time
import zipfile
from pathlib import Path

from ... import config
from ..descargas import bajar
from . import leer_json

FUENTE = "ambientcg"
API = "https://ambientcg.com/api/v2/full_json"
TIPOS = {"Material": "material", "HDRI": "hdri", "Decal": "decal", "Atlas": "atlas"}
PERFILES = {"produccion": {"material": ["2K-JPG"], "hdri": ["4K"], "decal": ["2K-JPG"], "atlas": ["2K-JPG"]},
            "ligero": {"material": ["1K-JPG"], "hdri": ["2K"], "decal": ["1K-JPG"], "atlas": ["1K-JPG"]},
            "alta": {"material": ["2K-JPG", "4K-JPG"], "hdri": ["4K", "8K"], "decal": ["4K-JPG"], "atlas": ["4K-JPG"]}}
# sufijo del archivo → clave que usa set_escena.material_pbr
MAPAS = {"color": ["_Color."], "normal": ["_NormalGL."], "rugosidad": ["_Roughness."],
         "ao": ["_AmbientOcclusion."], "metal": ["_Metalness."], "alfa": ["_Opacity."],
         "desplazamiento": ["_Displacement."]}


def carpeta(tipo: str, clave: str, atributo: str) -> Path:
    return config.ruta_drive("biblioteca", "ambientcg", tipo, f"{clave}_{atributo}")


def _zips(a: dict) -> list[dict]:
    d = a.get("downloadFolders")
    for clave in ("default", "downloadFiletypeCategories", "zip"):
        d = d.get(clave) if isinstance(d, dict) else None
    lista = d.get("downloads") if isinstance(d, dict) else None
    return [z for z in (lista or []) if isinstance(z, dict) and z.get("attribute") and z.get("downloadLink")]


def descubrir(registro=print) -> list[dict]:
    salida = []
    ahora = time.strftime("%Y-%m-%d %H:%M:%S")
    for tipo_api, tipo in TIPOS.items():
        offset, total = 0, None
        while total is None or offset < total:
            d = leer_json(f"{API}?type={tipo_api}&include=downloadData,tagData,displayData&limit=250&offset={offset}"
                          "&sort=Alphabet")
            total = int(d.get("numberOfResults", 0))
            lote = d.get("foundAssets", [])
            if not lote:
                break
            for a in lote:
                if (a.get("releaseDate") or "9999") > ahora:
                    continue  # acceso anticipado (solo mecenas)
                zips = _zips(a)
                salida.append({
                    "id": f"{FUENTE}:{tipo}:{a['assetId']}", "fuente": FUENTE, "tipo": tipo, "clave": a["assetId"],
                    "nombre": a.get("displayName") or a["assetId"],
                    "categorias": [a.get("displayCategory") or ""], "etiquetas": a.get("tags", []),
                    "licencia": "CC0-1.0", "credito": "ambientCG (ambientcg.com), CC0",
                    "url_pagina": a.get("shortLink") or f"https://ambientcg.com/a/{a['assetId']}",
                    "extra": {"zips": {z["attribute"]: {"url": z["downloadLink"], "tam": z.get("size"),
                                                        "archivo": z.get("fileName")} for z in zips},
                              "dimensiones_cm": [a.get("dimensionX"), a.get("dimensionY"), a.get("dimensionZ")],
                              "popularidad": a.get("popularityScore")}})
            offset += len(lote)
        registro(f"ambientCG {tipo}: {sum(1 for x in salida if x['tipo'] == tipo)}")
    return salida


def _atributos(entrada: dict, perfil: str) -> list[str]:
    zips = entrada["extra"].get("zips", {})
    pedidos = [x for x in PERFILES[perfil][entrada["tipo"]] if x in zips]
    if not pedidos and zips:  # la resolución pedida no existe: la más cercana por debajo
        pedidos = [sorted(zips, key=lambda k: int(re.match(r"\d+", k).group()) if re.match(r"\d+", k) else 0)[0]]
    return pedidos


def estimar(entrada: dict, perfil: str = "produccion") -> int:
    # Extraído ocupa ~lo mismo que el zip (JPG/EXR ya están comprimidos).
    return sum(entrada["extra"]["zips"][a].get("tam") or 0 for a in _atributos(entrada, perfil))


def mapas_de(carpeta_: Path) -> dict[str, str]:
    salida = {}
    for clave, sufijos in MAPAS.items():
        for f in sorted(carpeta_.iterdir()):
            if any(s in f.name for s in sufijos) and f.suffix.lower() in (".jpg", ".png", ".exr"):
                salida[clave] = f.name  # relativo a la carpeta (Drive puede montarse en otra ruta)
                break
    return salida


def asegurar(clave: str, tipo: str = "material", atributo: str = "2K-JPG", registro=print) -> Path:
    """Un recurso puntual (lo que pide una toma): lo baja si falta y devuelve su carpeta."""
    for c in sorted(config.ruta_drive("biblioteca", "ambientcg", tipo).glob(f"{clave}_*/.completo")):
        if c.parent.name == f"{clave}_{atributo}":
            return c.parent
    d = leer_json(f"{API}?id={clave}&include=downloadData,displayData")
    a = next((x for x in d.get("foundAssets", []) if x["assetId"] == clave), None)
    if not a:
        raise SystemExit(f"ambientCG no tiene «{clave}».")
    entrada = {"clave": clave, "tipo": tipo, "extra": {"zips": {z["attribute"]: {
        "url": z["downloadLink"], "tam": z.get("size"), "archivo": z.get("fileName")} for z in _zips(a)}}}
    perfil = next((k for k, v in PERFILES.items() if atributo in v[tipo]), "produccion")
    return Path(descargar(entrada, perfil, registro)["ruta"])


def descargar(entrada: dict, perfil: str = "produccion", registro=print) -> dict:
    total, rutas = 0, []
    for atributo in _atributos(entrada, perfil):
        destino = carpeta(entrada["tipo"], entrada["clave"], atributo)
        marca = destino / ".completo"
        if marca.exists():
            total += int(json.loads(marca.read_text(encoding="utf-8")).get("bytes", 0))
            rutas.append(str(destino))
            continue
        z = entrada["extra"]["zips"][atributo]
        local = config.ruta_local("tmp", "ambientcg", z.get("archivo") or f"{entrada['clave']}_{atributo}.zip")
        bajar(z["url"], local, tam=z.get("tam"), registro=registro)
        destino.mkdir(parents=True, exist_ok=True)
        bytes_ = 0
        with zipfile.ZipFile(local) as zf:
            for info in zf.infolist():
                nombre = Path(info.filename).name
                if info.is_dir() or not nombre or nombre.startswith("."):
                    continue
                salida = destino / nombre
                if not salida.exists():
                    tmp = salida.with_name(salida.name + ".parcial")
                    with zf.open(info) as src, open(tmp, "wb") as dst:
                        dst.write(src.read())
                    tmp.replace(salida)
                bytes_ += info.file_size
        local.unlink()  # el zip temporal del disco local (lo extraído queda en Drive)
        mapas = mapas_de(destino) if entrada["tipo"] in ("material", "decal", "atlas") else {}
        if entrada["tipo"] == "hdri":
            hdr = sorted([f for f in destino.iterdir() if f.suffix.lower() in (".exr", ".hdr")], key=lambda f: f.name)
            mapas = {"hdri": hdr[0].name} if hdr else {}
        (destino / "mapas.json").write_text(json.dumps(mapas, indent=1, ensure_ascii=False), encoding="utf-8")
        marca.write_text(json.dumps({"bytes": bytes_, "fecha": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")
        total += bytes_
        rutas.append(str(destino))
    if not rutas:
        raise IOError("sin archivos para el perfil")
    return {"ruta": rutas[-1], "bytes": total, "extra": {"rutas": rutas, "perfil": perfil}}
