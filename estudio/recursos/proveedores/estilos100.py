"""100STYLE (Ian Mason, CC BY 4.0): 100 estilos de caminar/correr/estar actuados por un actor real
(viejo, zombi, borracho, deprimido, orgulloso, cojeando, con miedo en la oscuridad…).

Descarga: el zip oficial de Zenodo (1.5 GB, md5 publicado) al disco local; se extraen los BVH a
  biblioteca/animaciones/100style/bvh/<Estilo>/<Estilo>_<TIPO>.bvh   (3.4 GB)
Después, convertir.py los adapta al esqueleto Mixamo (remy) como acciones con nombre
(«estilo_viejo_caminar»…) en biblioteca/animaciones/estilos100/, listas para {"anim": …}.
Crédito obligatorio: «The 100STYLE Dataset - Ian Mason» (se escribe solo en CREDITOS.txt).
"""

from __future__ import annotations

import csv
import json
import time
import zipfile
from pathlib import Path

from ... import config
from ..descargas import bajar
from . import leer_json

FUENTE = "estilos100"
ZENODO = "8127870"
DATOS = Path(__file__).resolve().parent.parent / "datos"
# Tipo de locomoción del dataset → nombre en la biblioteca y segundos que se guardan
TIPOS = {"ID": ("quieto", 8.0), "FW": ("caminar", 8.0), "FR": ("correr", 6.0), "BW": ("caminar_atras", 6.0),
         "BR": ("correr_atras", 5.0), "SW": ("caminar_lado", 6.0), "SR": ("correr_lado", 5.0)}
ES = {
    "Aeroplane": "avion", "Akimbo": "manos_cintura", "Angry": "enojado", "ArmsAboveHead": "brazos_arriba",
    "ArmsBehindBack": "manos_atras", "ArmsBySide": "brazos_pegados", "ArmsFolded": "brazos_cruzados",
    "Balance": "equilibrio", "BeatChest": "golpear_pecho", "BentForward": "inclinado", "BentKnees": "rodillas_dobladas",
    "BigSteps": "pasos_largos", "BouncyLeft": "rebote_izq", "BouncyRight": "rebote_der", "Cat": "gato",
    "Chicken": "gallina", "CrossOver": "pasos_cruzados", "Crouched": "agachado", "CrowdAvoidance": "esquivar_gente",
    "Depressed": "deprimido", "Dinosaur": "dinosaurio", "DragLeftLeg": "arrastra_pierna_izq",
    "DragRightLeg": "arrastra_pierna_der", "Drunk": "borracho", "DuckFoot": "pies_adentro", "Elated": "euforico",
    "FairySteps": "pasos_hada", "Flapping": "aletear", "FlickLegs": "patadas_lado", "Followed": "perseguido",
    "GracefulArms": "elegante", "HandsBetweenLegs": "manos_entre_piernas", "HandsInPockets": "manos_bolsillos",
    "Heavyset": "musculoso", "HighKnees": "rodillas_altas", "InTheDark": "a_oscuras", "KarateChop": "karate",
    "Kick": "patear", "LawnMower": "podadora", "LeanBack": "echado_atras", "LeanLeft": "ladeado_izq",
    "LeanRight": "ladeado_der", "LeftHop": "saltar_pie_izq", "LegsApart": "piernas_abiertas",
    "LimpLeft": "cojear_izq", "LimpRight": "cojear_der", "LookUp": "mirar_arriba", "Lunge": "zancadas",
    "March": "marchar", "Monk": "monje", "Morris": "danza_folk", "Neutral": "normal", "Old": "viejo",
    "OnHeels": "talones", "OnPhoneLeft": "celular_izq", "OnPhoneRight": "celular_der",
    "OnToesBentForward": "puntillas_inclinado", "OnToesCrouched": "puntillas_agachado",
    "PendulumHands": "manos_pendulo", "Penguin": "pinguino", "PigeonToed": "pies_paloma", "Proud": "orgulloso",
    "Punch": "punetazos", "Quail": "pasitos_rapidos", "RaisedLeftArm": "brazo_izq_alzado",
    "RaisedRightArm": "brazo_der_alzado", "RightHop": "saltar_pie_der", "Roadrunner": "correcaminos",
    "Robot": "robot", "Rocket": "cohete", "Rushed": "apurado", "ShieldedLeft": "escudo_izq",
    "ShieldedRight": "escudo_der", "Skip": "saltitos", "SlideFeet": "arrastrar_pies", "SpinAntiClock": "girar_izq",
    "SpinClock": "girar_der", "Star": "estrella", "StartStop": "parar_seguir", "Stiff": "rigido",
    "Strutting": "pavonearse", "Superman": "superman", "Swat": "swat", "Sweep": "barrer", "Swimming": "nadar",
    "SwingArmsRound": "molinete_brazos", "SwingShoulders": "hombros", "Teapot": "tetera", "Tiptoe": "puntillas",
    "TogetherStep": "pasos_juntos", "TwoFootJump": "saltar_juntos", "WalkingStickLeft": "baston_izq",
    "WalkingStickRight": "baston_der", "Waving": "saludar", "WhirlArms": "aspas", "WideLegs": "piernas_anchas",
    "WiggleHips": "menear_cadera", "WildArms": "brazos_locos", "WildLegs": "piernas_locas", "Zombie": "zombi",
}


def carpeta() -> Path:
    return config.ruta_drive("biblioteca", "animaciones", "100style")


def ruta_bvh(estilo: str, tipo: str) -> Path:
    return carpeta() / "bvh" / estilo / f"{estilo}_{tipo}.bvh"


def estilos() -> dict[str, str]:
    with open(DATOS / "100style_estilos.csv", encoding="utf-8") as f:
        return {r["Style Name"].strip(): r["Description"].strip() for r in csv.DictReader(f)}


def cortes() -> dict[str, dict[str, tuple[int, int]]]:
    """Cuadros útiles (inicio, fin) por estilo y tipo, según el archivo oficial Frame_Cuts.csv."""
    salida: dict = {}
    with open(DATOS / "100style_cortes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            e = r["STYLE_NAME"].strip()
            for t in list(TIPOS) + ["TR1", "TR2", "TR3"]:
                a, b = r.get(f"{t}_START", "N/A"), r.get(f"{t}_STOP", "N/A")
                if a not in ("N/A", "", None) and b not in ("N/A", "", None):
                    salida.setdefault(e, {})[t] = (int(a), int(b))
    return salida


def clave(estilo: str, tipo: str) -> str:
    return f"estilo_{ES.get(estilo, estilo.lower())}_{TIPOS[tipo][0]}"


def descubrir(registro=print) -> list[dict]:
    desc, cut = estilos(), cortes()
    salida = []
    for estilo, texto in desc.items():
        for tipo, (nombre_tipo, _) in TIPOS.items():
            if tipo not in cut.get(estilo, {}):
                continue
            k = clave(estilo, tipo)
            salida.append({"id": f"{FUENTE}:animacion:{k}", "fuente": FUENTE, "tipo": "animacion", "clave": k,
                           "nombre": f"{estilo} {tipo}", "categorias": ["estilo", nombre_tipo],
                           "etiquetas": [estilo.lower(), ES.get(estilo, ""), nombre_tipo] + texto.lower().split()[:12],
                           "licencia": "CC-BY-4.0", "credito": "The 100STYLE Dataset - Ian Mason (CC BY 4.0)",
                           "url_pagina": "https://ianxmason.github.io/100style/",
                           "extra": {"estilo": estilo, "tipo_locomocion": tipo, "descripcion": texto,
                                     "corte": cut[estilo][tipo], "bvh": str(ruta_bvh(estilo, tipo))}})
    registro(f"100STYLE: {len(salida)} animaciones ({len(desc)} estilos)")
    return salida


def _zip_oficial() -> dict:
    datos = leer_json(f"https://zenodo.org/api/records/{ZENODO}")
    f = next(x for x in datos["files"] if x["key"] == "100STYLE.zip")
    return {"url": f["links"]["self"], "tam": f["size"], "md5": f["checksum"].split(":")[-1]}


def preparar(registro=print) -> Path:
    """Baja el zip oficial (una vez) y extrae todos los BVH a Drive."""
    marca = carpeta() / ".completo"
    if marca.exists():
        return carpeta()
    z = _zip_oficial()
    local = config.ruta_local("tmp", "100STYLE.zip")
    registro(f"100STYLE: bajando el zip oficial ({z['tam'] / 1e9:.2f} GB)…")
    bajar(z["url"], local, tam=z["tam"], md5=z["md5"], registro=registro)
    n = 0
    with zipfile.ZipFile(local) as zf:
        for info in zf.infolist():
            partes = Path(info.filename).parts
            if info.is_dir() or "__MACOSX" in partes or not info.filename.lower().endswith((".bvh", ".csv")):
                continue
            destino = carpeta() / ("bvh" if info.filename.lower().endswith(".bvh") else "") / Path(*partes[1:])
            if destino.exists() and destino.stat().st_size == info.file_size:
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_name(destino.name + ".parcial")
            with zf.open(info) as src, open(tmp, "wb") as dst:
                while bloque := src.read(8 << 20):
                    dst.write(bloque)
            tmp.replace(destino)
            n += 1
    (carpeta() / "LICENCIA.txt").write_text(
        "The 100STYLE Dataset - Ian Mason. Creative Commons Attribution 4.0 International (CC BY 4.0).\n"
        "https://ianxmason.github.io/100style/ · https://zenodo.org/records/8127870\n", encoding="utf-8")
    marca.write_text(json.dumps({"archivos": n, "fecha": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")
    local.unlink()
    registro(f"100STYLE: {n} archivos extraídos en {carpeta()}")
    return carpeta()


def estimar(entrada: dict, perfil: str = "produccion") -> int:
    return int(3.37e9 / 800)  # 3.37 GB extraídos / ~800 BVH


def descargar(entrada: dict, perfil: str = "produccion", registro=print) -> dict:
    preparar(registro)
    bvh = Path(entrada["extra"]["bvh"])
    if not bvh.exists():
        raise IOError(f"no está en el zip oficial: {bvh.name}")
    return {"ruta": str(bvh), "bytes": bvh.stat().st_size, "extra": {}}
