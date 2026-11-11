"""Ingestor: lo que baja el navegador (de Antigravity o tuyo) entra solo a la biblioteca.

Carpeta de entrada: biblioteca/_entrada/navegador/<fuente>/  (p. ej. …/navegador/quaternius/archivo.zip)
Si el archivo está suelto en navegador/, se intenta reconocer la fuente por su nombre.

Por cada archivo (zip, fbx, glb, gltf, blend, bvh, obj):
  1. espera a que termine de sincronizar (sin cambios en el último minuto; ignora .crdownload/.part);
  2. SHA-256 → si ya se ingresó, no se repite;
  3. compuerta de licencias: la fuente debe estar verificada (si no → _entrada/_revision/ con el motivo);
  4. se copia/extrae a biblioteca/paquetes/<fuente>/<nombre>/ con LICENCIA.txt y se cataloga
     (estado «descargado»: queda listo para adaptar; no entra solo a las tomas);
  5. el original se MUEVE a _entrada/_procesados/<fecha>/ (nunca se borra).
Los FBX de Mixamo siguen su propio camino (_entrada/mixamo/ + mixamo_importar).
"""

from __future__ import annotations

import json
import re
import shutil
import time
import zipfile
from pathlib import Path

from .. import config
from . import catalogo, licencias
from .descargas import sha256_de

EXTENSIONES = (".zip", ".fbx", ".glb", ".gltf", ".blend", ".bvh", ".obj")
TEMPORALES = (".crdownload", ".part", ".parcial", ".tmp", ".download")
PATRONES = {"quaternius": r"quaternius|universal animation library|ultimate .*pack|\[standard\]",
            "kenney": r"^kenney[_ ]",
            "estilos100": r"100style",
            "polyhaven": r"_\d+k\.(hdr|exr|gltf|blend)$",
            "ambientcg": r"^[A-Z][A-Za-z]+\d{3}[A-Z]?_\d+K"}


def entrada() -> Path:
    return config.ruta_drive("biblioteca", "_entrada", "navegador")


def _fuente_de(archivo: Path) -> str | None:
    padre = archivo.parent.name.lower()
    if archivo.parent != entrada() and padre in licencias.fuentes():
        return padre
    for fuente, patron in PATRONES.items():
        if re.search(patron, archivo.name, flags=re.I):
            return fuente
    return None


def _mover(archivo: Path, carpeta: Path, motivo: str = "") -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / archivo.name
    k = 1
    while destino.exists():
        destino = carpeta / f"{archivo.stem}_{k}{archivo.suffix}"
        k += 1
    shutil.move(str(archivo), str(destino))
    if motivo:
        destino.with_name(destino.name + ".motivo.txt").write_text(motivo + "\n", encoding="utf-8")
    return destino


def _nombre(archivo: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "_", archivo.stem.lower()).strip("_")[:60] or "paquete"


def revisar(registro=print) -> dict:
    base = entrada()
    for f in licencias.fuentes():
        (base / f).mkdir(parents=True, exist_ok=True)
    hechos, revision, repetidos, esperando = [], [], [], []
    ahora = time.time()
    archivos = sorted(p for p in base.rglob("*") if p.is_file() and not p.name.endswith(".motivo.txt"))
    for archivo in archivos:
        if archivo.suffix.lower() in TEMPORALES or archivo.name.startswith("."):
            continue
        if archivo.suffix.lower() not in EXTENSIONES:
            continue
        if ahora - archivo.stat().st_mtime < 60:
            esperando.append(archivo.name)  # todavía se está bajando o sincronizando
            continue
        fuente = _fuente_de(archivo)
        if fuente == "mixamo":
            continue
        if not fuente:
            _mover(archivo, config.ruta_drive("biblioteca", "_entrada", "_revision"),
                   "No se reconoce la fuente: ponlo en _entrada/navegador/<fuente>/ (una de fuentes.json).")
            revision.append({"archivo": archivo.name, "motivo": "fuente desconocida"})
            continue
        ev = licencias.verificar(fuente)
        if not ev.get("ok"):
            _mover(archivo, config.ruta_drive("biblioteca", "_entrada", "_revision"),
                   f"Licencia de {fuente} no verificada: {ev.get('motivo')}")
            revision.append({"archivo": archivo.name, "motivo": ev.get("motivo")})
            continue
        sha = sha256_de(archivo)
        id_ = f"{fuente}:paquete:{sha[:16]}"
        if catalogo.obtener(id_):
            _mover(archivo, config.ruta_drive("biblioteca", "_entrada", "_procesados", time.strftime("%Y%m%d")),
                   f"Repetido: ya está como {id_}")
            repetidos.append(archivo.name)
            continue
        destino = config.ruta_drive("biblioteca", "paquetes", fuente, _nombre(archivo))
        k = 1
        while destino.exists():
            destino = destino.with_name(f"{_nombre(archivo)}_{k}")
            k += 1
        destino.mkdir(parents=True)
        if archivo.suffix.lower() == ".zip":
            with zipfile.ZipFile(archivo) as zf:
                for info in zf.infolist():
                    rel = Path(info.filename)
                    if info.is_dir() or "__MACOSX" in rel.parts or rel.is_absolute() or ".." in rel.parts:
                        continue
                    salida = destino / rel
                    salida.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(salida, "wb") as dst:
                        shutil.copyfileobj(src, dst, 8 << 20)
        else:
            shutil.copy2(archivo, destino / archivo.name)
        f = licencias.fuentes()[fuente]
        (destino / "LICENCIA.txt").write_text(f"{f.get('credito')}\nLicencia: {f.get('licencia')}\n"
                                              f"Evidencia oficial: {ev.get('url_licencia')} ({ev.get('fecha')})\n"
                                              f"Archivo original: {archivo.name} · sha256 {sha}\n", encoding="utf-8")
        contenido = sorted(str(p.relative_to(destino)) for p in destino.rglob("*")
                           if p.suffix.lower() in EXTENSIONES[1:])
        total = sum(p.stat().st_size for p in destino.rglob("*") if p.is_file())
        catalogo.registrar({"id": id_, "fuente": fuente, "tipo": "paquete", "clave": destino.name,
                            "nombre": archivo.stem, "categorias": ["navegador"], "etiquetas": archivo.stem.lower().split(),
                            "licencia": f.get("licencia"), "credito": f.get("credito"), "url_pagina": "",
                            "estado": "descargado", "ruta": str(destino), "bytes": total,
                            "extra": {"sha256": sha, "archivos_3d": contenido[:500], "n_archivos_3d": len(contenido)}})
        _mover(archivo, config.ruta_drive("biblioteca", "_entrada", "_procesados", time.strftime("%Y%m%d")))
        hechos.append({"fuente": fuente, "paquete": str(destino), "archivos_3d": len(contenido)})
        registro(f"✔ {archivo.name} → {destino} ({len(contenido)} archivos 3D)")
    catalogo.abrir().commit()
    if hechos:
        catalogo.guardar()
    return {"ok": True, "ingresados": hechos, "a_revision": revision, "repetidos": repetidos,
            "esperando_sincronizar": esperando, "carpeta_entrada": str(base)}
