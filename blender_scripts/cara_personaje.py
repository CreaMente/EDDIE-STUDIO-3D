"""Anima la cara de un personaje con rig facial: labios sincronizados con la voz, expresión y parpadeo.

  blender -b --factory-startup -P cara_personaje.py -- --animado animado_rain.blend --ficha rain.json \
      --salida animado_rain.blend [--palabras voz/palabras.json --desde_s 3.2 --hasta_s 7.3 --habla 1]
      [--expresion dolor --intensidad 0.8] [--semilla 3]

Labios: el español se escribe casi como se pronuncia, así que cada palabra (con sus tiempos de Whisper)
se convierte en una secuencia de visemas (A, E, I, O, U, M/B/P, F, consonante) repartidos en su
duración; cada visema mueve la mandíbula y las comisuras (ancho/redondo). Las pausas cierran la boca.
El cuadro 1 de la toma corresponde al segundo --desde_s de la voz (como en el montaje).

Expresión: base para toda la toma (cejas, comisuras, párpados, mandíbula) sobre la que se suman los
labios. Parpadeo natural cada 2–5 s. Los valores físicos de cada control vienen de la ficha («cara»),
calibrada mirando renders de cada personaje.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import unicodedata

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402

FPS = 30

# Visema → (apertura de mandíbula 0–1, ancho de boca −1 redonda … +1 estirada, labios cerrados)
VISEMAS = {
    "A": (1.00, 0.25, False), "E": (0.60, 0.60, False), "I": (0.35, 0.85, False),
    "O": (0.70, -0.65, False), "U": (0.35, -1.00, False),
    "MBP": (0.00, 0.00, True), "F": (0.12, 0.20, False), "C": (0.28, 0.15, False), "REPOSO": (0.0, 0.0, False),
}

# Expresiones: sonrisa (−1 triste … +1 alegre), cejas (−1 fruncidas … +1 arriba), párpados (0 abiertos …
# 1 cerrados), ancho de boca y apertura de mandíbula de base.
EXPRESIONES = {
    "neutral": {},
    "alegria": {"sonrisa": 0.8, "cejas": 0.25, "parpados": 0.15, "ancho": 0.3},
    "dolor": {"sonrisa": -0.5, "cejas": -0.6, "parpados": 0.25, "ancho": 0.45, "mandibula": 0.08},
    "sorpresa": {"cejas": 1.0, "mandibula": 0.3, "parpados": -0.1, "ancho": -0.2},
    "miedo": {"cejas": 0.8, "sonrisa": -0.35, "ancho": 0.5, "mandibula": 0.15},
    "tristeza": {"sonrisa": -0.7, "cejas": 0.2, "parpados": 0.35},
    "enojo": {"cejas": -0.9, "sonrisa": -0.3, "parpados": 0.25, "ancho": 0.2},
    "asco": {"sonrisa": -0.45, "cejas": -0.45, "ancho": 0.35, "parpados": 0.2},
    "pensativo": {"cejas": -0.2, "sonrisa": -0.1, "parpados": 0.2, "ancho": -0.2},
}


def sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def visemas_de_palabra(palabra: str) -> list[tuple[str, float]]:
    """Palabra en español → [(visema, peso)] (las vocales duran el doble que las consonantes)."""
    t = sin_tildes(palabra)
    t = "".join(c for c in t if c.isalpha() or c == "ñ")
    t = t.replace("ch", "c").replace("ll", "y").replace("rr", "r").replace("qu", "k").replace("gu", "g")
    salida = []
    for i, c in enumerate(t):
        if c == "h":
            continue
        if c in "aeiou":
            salida.append(("AEIOU"["aeiou".index(c)], 2.0))
        elif c == "y" and (i == len(t) - 1 or len(t) == 1):
            salida.append(("I", 1.5))
        elif c in "mbpv":
            salida.append(("MBP", 1.0))
        elif c == "f":
            salida.append(("F", 1.0))
        else:
            salida.append(("C", 1.0))
    return salida or [("C", 1.0)]


def claves_labios(palabras: list, desde: float, hasta: float) -> list[tuple[float, str]]:
    """[(segundo relativo a la toma, visema)] con reposo en las pausas."""
    claves = [(0.0, "REPOSO")]
    previo_fin = None
    for w in palabras:
        ini, fin = float(w["inicio"]), float(w["fin"])
        if fin < desde or ini > hasta:
            continue
        if fin - ini < 0.05:
            fin = ini + 0.08
        if previo_fin is not None and ini - previo_fin > 0.18:
            claves.append((previo_fin + 0.06 - desde, "REPOSO"))
            claves.append((ini - 0.04 - desde, "REPOSO"))
        vis = visemas_de_palabra(w["palabra"])
        total = sum(p for _, p in vis)
        t = ini
        for v, peso in vis:
            d = (fin - ini) * peso / total
            claves.append((t + d / 2 - desde, v))
            t += d
        previo_fin = fin
    if previo_fin is not None:
        claves.append((previo_fin + 0.08 - desde, "REPOSO"))
    return [(max(0.0, t), v) for t, v in claves]


class Cara:
    """Aplica valores normalizados a los controles de la cara según la ficha del personaje."""

    def __init__(self, rig, ficha: dict):
        self.rig, self.f = rig, ficha["cara"]
        self.huesos = set()

    def _pb(self, nombre):
        self.huesos.add(nombre)
        return self.rig.pose.bones[nombre]

    def aplicar(self, mandibula=0.0, ancho=0.0, sonrisa=0.0, cejas=0.0, parpados=0.0, cerrar_labios=False):
        f = self.f
        m = f["mandibula"]
        pb = self._pb(m["hueso"])
        pb.rotation_mode = "XYZ"
        r = [0.0, 0.0, 0.0]
        r[m["eje"]] = math.radians(m["grados"] * max(0.0, min(1.2, mandibula)))
        pb.rotation_euler = r
        c = f["comisuras"]
        for lado in ("L", "R"):
            vec = Vector(c["arriba"]) * sonrisa
            ancho_v = Vector(c[f"ancho_{lado}"])
            vec += ancho_v * (ancho if ancho >= 0 else ancho * c.get("factor_redondo", 0.7))
            self._pb(c[lado]).location = vec
        p = f["parpados"]
        for lado in ("L", "R"):
            self._pb(p[lado]).location = Vector(p["cerrar"]) * max(-0.3, min(1.0, parpados))
        e = f["cejas"]
        for lado in ("L", "R"):
            self._pb(e[lado]).location = Vector(e["subir"]) * max(-1.0, min(1.0, cejas))

    def clave(self, cuadro: int):
        parpados = {self.f["parpados"]["L"], self.f["parpados"]["R"]}
        for n in self.huesos - parpados:  # los párpados los animan la expresión y el parpadeo
            pb = self.rig.pose.bones[n]
            pb.keyframe_insert("location", frame=cuadro)
            pb.keyframe_insert("rotation_euler", frame=cuadro)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--animado", required=True)
    p.add_argument("--ficha", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--palabras", default="")
    p.add_argument("--desde_s", type=float, default=0.0)
    p.add_argument("--hasta_s", type=float, default=1e9)
    p.add_argument("--habla", type=int, default=0)
    p.add_argument("--expresion", default="neutral")
    p.add_argument("--intensidad", type=float, default=1.0)
    p.add_argument("--semilla", type=int, default=3)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()
    ficha = json.loads(open(a.ficha, encoding="utf-8").read())
    if "cara" not in ficha:
        raise SystemExit(f"La ficha de «{ficha['nombre']}» no tiene datos de cara.")
    if a.expresion not in EXPRESIONES:
        raise SystemExit(f"Expresión desconocida «{a.expresion}». Opciones: {sorted(EXPRESIONES)}")

    bpy.ops.wm.open_mainfile(filepath=a.animado, load_ui=False, use_scripts=False)
    esc = bpy.context.scene
    rig = max((o for o in esc.objects if o.type == "ARMATURE"), key=lambda o: len(o.data.bones))
    cara = Cara(rig, ficha)
    base = {k: v * a.intensidad for k, v in EXPRESIONES[a.expresion].items()}
    f0, f1 = esc.frame_start, esc.frame_end

    # Labios: visemas por cuadro clave (más la expresión de base).
    claves = [(0.0, "REPOSO")]
    if a.habla and a.palabras:
        palabras = json.loads(open(a.palabras, encoding="utf-8").read())
        claves = claves_labios(palabras, a.desde_s, a.hasta_s)
    usados = set()
    for t, v in claves:
        cuadro = f0 + int(round(t * FPS))
        if cuadro > f1 or cuadro in usados:
            continue
        usados.add(cuadro)
        mand, ancho, cerrado = VISEMAS[v]
        cara.aplicar(mandibula=base.get("mandibula", 0) + (0 if cerrado else mand * 0.85),
                     ancho=base.get("ancho", 0) * 0.5 + ancho * 0.8, sonrisa=base.get("sonrisa", 0),
                     cejas=base.get("cejas", 0), parpados=base.get("parpados", 0), cerrar_labios=cerrado)
        cara.clave(cuadro)
    if not a.habla:
        cara.aplicar(mandibula=base.get("mandibula", 0), ancho=base.get("ancho", 0), sonrisa=base.get("sonrisa", 0),
                     cejas=base.get("cejas", 0), parpados=base.get("parpados", 0))
        cara.clave(f0)
        cara.clave(f1)

    # Parpadeo: cierra en 2 cuadros, abre en 4, cada 2–5 s (sobre los párpados de la expresión).
    rnd = random.Random(a.semilla)
    pp = ficha["cara"]["parpados"]
    abierto = base.get("parpados", 0)
    for c in (f0, f1):
        for lado in ("L", "R"):
            pb = rig.pose.bones[pp[lado]]
            pb.location = Vector(pp["cerrar"]) * abierto
            pb.keyframe_insert("location", frame=c)
    t = rnd.uniform(0.6, 2.0)
    parpadeos = 0
    while f0 + int(t * FPS) + 6 < f1:
        c = f0 + int(t * FPS)
        for dc, valor in ((0, abierto), (2, 1.0), (6, abierto)):
            for lado in ("L", "R"):
                pb = rig.pose.bones[pp[lado]]
                pb.location = Vector(pp["cerrar"]) * valor
                pb.keyframe_insert("location", frame=c + dc)
        parpadeos += 1
        t += rnd.uniform(2.0, 5.0)

    info = {"expresion": a.expresion, "habla": bool(a.habla), "claves_labios": len(usados), "parpadeos": parpadeos,
            "cuadros": f1 - f0 + 1}
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    info.update({"salida": a.salida, "segundos": round(time.time() - t0, 1)})
    comun.resultado(info)


if __name__ == "__main__":
    main()
