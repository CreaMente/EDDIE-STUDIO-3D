"""Elenco del canal: personajes de Blender Studio (CC-BY) con rig de producción y cara completa.

  python -m estudio.elenco preparar [--nombre rain]   descarga a <DRIVE>/biblioteca/elenco/<nombre>/
  python -m estudio.elenco listar

Cada personaje tiene una ficha en estudio/fichas/<nombre>.json: de dónde se descarga, qué control del
rig corresponde a cada hueso de Mixamo (para pasarle las animaciones) y cómo se mueve su cara
(calibrado mirando renders). Los archivos se abren SIN ejecutar los scripts que traen (solo datos).
Licencia: CC-BY 4.0. El crédito de cada personaje se escribe solo en CREDITOS.txt del proyecto.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

from . import config

FICHAS = Path(__file__).resolve().parent / "fichas"
SITIO = "https://studio.blender.org"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fichas() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(FICHAS.glob("*.json"))}


def ficha(nombre: str) -> dict | None:
    return fichas().get(nombre.lower())


def carpeta(nombre: str) -> Path:
    return config.ruta_drive("biblioteca", "elenco", nombre.lower())


def ruta_blend(nombre: str) -> Path:
    f = ficha(nombre)
    if not f:
        raise KeyError(nombre)
    return carpeta(nombre) / f["blend"]


def preparar(nombre: str, registro=log) -> Path:
    f = ficha(nombre)
    if not f:
        raise SystemExit(f"No hay ficha para «{nombre}». Disponibles: {sorted(fichas())}")
    destino = carpeta(nombre)
    blend = destino / f["blend"]
    if (destino / ".completo").exists() and blend.exists():
        return blend
    destino.mkdir(parents=True, exist_ok=True)
    url = SITIO + f["descarga"]
    archivo = destino / ("descarga.zip" if url.endswith(".zip") else Path(f["blend"]).name)
    registro(f"Descargando {f['titulo']} ({url})…")
    with urllib.request.urlopen(url, timeout=600) as r, open(archivo, "wb") as out:
        shutil.copyfileobj(r, out, length=1 << 20)
    if archivo.suffix == ".zip":
        with zipfile.ZipFile(archivo) as z:
            z.extractall(destino)
        archivo.unlink()
    if not blend.exists():
        raise SystemExit(f"Descargado, pero no encuentro {blend}. Revisa «blend» en la ficha.")
    (destino / "LICENCIA.txt").write_text(f"{f['credito']}\nLicencia CC-BY 4.0: "
                                          "https://creativecommons.org/licenses/by/4.0/\n"
                                          f"Origen: {f['origen']}\n", encoding="utf-8")
    (destino / ".completo").write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    registro(f"✔ {f['titulo']} listo en {destino}")
    return blend


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.elenco")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preparar")
    pp.add_argument("--nombre", default="")
    sub.add_parser("listar")
    a = p.parse_args()
    if a.cmd == "listar":
        filas = [{"nombre": n, "titulo": f["titulo"], "descargado": (carpeta(n) / ".completo").exists(),
                  "cara": "cara" in f, "credito": f["credito"]} for n, f in fichas().items()]
        print("RESULTADO_JSON: " + json.dumps({"elenco": filas}, ensure_ascii=False), flush=True)
        return
    nombres = [a.nombre] if a.nombre else list(fichas())
    hechos = {n: str(preparar(n)) for n in nombres}
    print("RESULTADO_JSON: " + json.dumps({"ok": True, "preparados": hechos}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
