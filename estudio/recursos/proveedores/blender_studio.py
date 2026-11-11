"""Blender Studio (CC-BY): todos los personajes con rig de producción que se pueden bajar SIN suscripción.

Se recorre la página oficial de personajes; para cada uno se lee su página (debe decir CC-BY: se guarda
la evidencia) y se baja su archivo a biblioteca/elenco/<nombre>/ (la misma carpeta que usa el elenco),
con LICENCIA.txt y la marca .completo. Los que ya están (rain, snow) no se vuelven a bajar.
Para actuar en las tomas cada personaje necesita además su ficha (estudio/fichas/<nombre>.json): huesos
y cara calibrados. Mientras no la tenga queda «descargado» (no «aprobado»).
"""

from __future__ import annotations

import html
import json
import re
import time
import zipfile
from pathlib import Path

from ... import config, elenco
from ..descargas import bajar
from ..licencias import verificar_pagina_recurso
from . import leer_texto

FUENTE = "blender_studio"
SITIO = "https://studio.blender.org"


def _nombre(ruta: str, titulo: str) -> str:
    base = ruta.strip("/").split("/")[1]
    if re.fullmatch(r"[0-9a-f]{24}", base):
        base = titulo
    return re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")


def descubrir(registro=print) -> list[dict]:
    indice = leer_texto(f"{SITIO}/characters/")
    paginas = sorted(set(re.findall(r'href="(/characters/[^"/]+/v\d+/)"', indice)))
    # solo la versión más nueva de cada personaje
    ultimas: dict[str, str] = {}
    for p in paginas:
        base = p.split("/")[2]
        if base not in ultimas or int(p.split("/v")[-1].strip("/")) > int(ultimas[base].split("/v")[-1].strip("/")):
            ultimas[base] = p
    salida = []
    for p in sorted(ultimas.values()):
        try:
            pagina = leer_texto(SITIO + p)
        except IOError as e:
            registro(f"   (no se pudo leer {p}: {e})")
            continue
        t = re.search(r"<title>([^<]+)</title>", pagina)
        titulo = html.unescape(t.group(1)).split(" - ")[0].strip() if t else p
        descarga = re.search(r'(/download-source/[^"]+)"', pagina)
        desc = re.search(r'<meta name="description" content="([^"]*)"', pagina)
        imagen = re.search(r'og:image" content="([^"]+)"', pagina)
        licencia = verificar_pagina_recurso(FUENTE, SITIO + p, pagina)
        nombre = _nombre(p, titulo)
        salida.append({"id": f"{FUENTE}:personaje:{nombre}", "fuente": FUENTE, "tipo": "personaje", "clave": nombre,
                       "nombre": titulo, "categorias": ["personaje", "rig"],
                       "etiquetas": (html.unescape(desc.group(1)).lower().split()[:20] if desc else []),
                       "licencia": "CC-BY-4.0", "credito": f"{titulo} Rig (CC-BY) Blender Foundation | studio.blender.org",
                       "url_pagina": SITIO + p,
                       "estado": "descubierto" if descarga and licencia["ok"] else "rechazado",
                       "extra": {"descarga": descarga.group(1) if descarga else None,
                                 "gratis": bool(descarga), "licencia_pagina": licencia,
                                 "miniatura": imagen.group(1) if imagen else None,
                                 "motivo": "" if descarga and licencia["ok"] else
                                 ("solo para suscriptores" if not descarga else "la página no dice CC-BY")}})
    registro(f"Blender Studio: {len(salida)} personajes ({sum(1 for x in salida if x['extra']['gratis'])} gratuitos)")
    return salida


def estimar(entrada: dict, perfil: str = "produccion") -> int | None:
    return None


def descargar(entrada: dict, perfil: str = "produccion", registro=print) -> dict:
    if not entrada["extra"].get("descarga"):
        raise IOError(entrada["extra"].get("motivo") or "sin descarga gratuita")
    if not entrada["extra"].get("licencia_pagina", {}).get("ok"):
        raise IOError("la página del personaje no confirma la licencia CC-BY")
    destino = elenco.carpeta(entrada["clave"])
    marca = destino / ".completo"
    if marca.exists():
        return {"ruta": str(destino), "bytes": sum(f.stat().st_size for f in destino.rglob("*") if f.is_file()),
                "extra": {"ya_estaba": True}}
    url = SITIO + entrada["extra"]["descarga"]
    es_zip = url.lower().endswith(".zip")
    temporal = config.ruta_local("tmp", "blender_studio", f"{entrada['clave']}{'.zip' if es_zip else '.blend'}")
    registro(f"   {entrada['nombre']}: bajando…")
    bajar(url, temporal, registro=registro)
    destino.mkdir(parents=True, exist_ok=True)
    if es_zip:
        with zipfile.ZipFile(temporal) as zf:
            for info in zf.infolist():
                if info.is_dir() or "__MACOSX" in info.filename:
                    continue
                salida = destino / info.filename
                if salida.exists():
                    continue
                salida.parent.mkdir(parents=True, exist_ok=True)
                tmp = salida.with_name(salida.name + ".parcial")
                with zf.open(info) as src, open(tmp, "wb") as dst:
                    while bloque := src.read(8 << 20):
                        dst.write(bloque)
                tmp.replace(salida)
        temporal.unlink()
    else:
        final = destino / f"{entrada['clave']}.blend"
        if not final.exists():
            import shutil
            shutil.copyfile(temporal, final)
        temporal.unlink()
    blends = sorted(str(p.relative_to(destino)) for p in destino.rglob("*.blend"))
    (destino / "LICENCIA.txt").write_text(f"{entrada['credito']}\nLicencia CC-BY 4.0: "
                                          "https://creativecommons.org/licenses/by/4.0/\n"
                                          f"Origen: {entrada['url_pagina']}\n", encoding="utf-8")
    (destino / "info.json").write_text(json.dumps({"nombre": entrada["nombre"], "blends": blends,
                                                   "origen": entrada["url_pagina"], "descarga": url,
                                                   "fecha": time.strftime("%Y-%m-%d %H:%M")},
                                                  indent=1, ensure_ascii=False), encoding="utf-8")
    marca.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    total = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file())
    return {"ruta": str(destino), "bytes": total, "extra": {"blends": blends}}
