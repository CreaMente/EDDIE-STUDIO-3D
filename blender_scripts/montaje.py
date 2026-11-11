"""Monta el video final en el editor de video de Blender (VSE) y lo renderiza a cuadros PNG.

  blender -b --factory-startup -P montaje.py -- --plan plan.json --cuadros /content/eddie/cuadros/…/montaje

plan.json (lo prepara estudio/montaje.py a partir de los tiempos de la voz):
  {"cuadros_total": 1650, "escala": 100,
   "clips":  [{"mp4": ".../toma.mp4", "inicio": 1, "duracion": 95, "desde": 0,
               "congelar": {"png": ".../ultimo.png", "duracion": 12}}, ...],
   "fundidos": [{"entre": [0, 1], "cuadros": 6}, ...],
   "textos": [{"texto": "DÍA 3", "inicio": 300, "duracion": 60}, ...],
   "fuente": ".../Fuente.ttf" (opcional)}

Todo cuadro sale de Blender: las tomas ya renderizadas y el texto en pantalla, compuesto aquí mismo.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def tiras(editor):
    return editor.strips if hasattr(editor, "strips") else editor.sequences  # Blender 5.x / 4.x


def nuevo_efecto(coleccion, nombre: str, tipo: str, canal: int, inicio: int, duracion: int, **entradas):
    try:  # Blender 4.x
        return coleccion.new_effect(nombre, tipo, canal, inicio, frame_end=inicio + duracion, **entradas)
    except TypeError:  # Blender 5.x
        return coleccion.new_effect(nombre, tipo, canal, inicio, length=duracion, **entradas)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True)
    p.add_argument("--cuadros", required=True, help="carpeta de salida de los PNG")
    a = p.parse_args(comun.argumentos())
    t0 = time.time()
    plan = json.loads(open(a.plan, encoding="utf-8").read())

    esc = bpy.context.scene
    for o in list(esc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    r = esc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, int(plan.get("escala", 100))
    r.fps, r.fps_base = 30, 1.0
    esc.frame_start, esc.frame_end = 1, int(plan["cuadros_total"])
    # Las tomas ya traen su color final (AgX aplicado al renderizarlas): el montaje no debe volver a
    # transformarlas, o se verían lavadas.
    esc.view_settings.view_transform = "Standard"
    esc.view_settings.look = "None"
    esc.view_settings.exposure, esc.view_settings.gamma = 0.0, 1.0
    esc.sequencer_colorspace_settings.name = "sRGB"

    editor = esc.sequence_editor_create()
    col = tiras(editor)
    clips = []
    for k, c in enumerate(plan["clips"]):
        canal = 1 + (k % 2) * 2  # 1 y 3 alternados (los fundidos van en el 5)
        tira = col.new_movie(f"toma_{k:02d}", c["mp4"], canal, int(c["inicio"]) - int(c.get("desde", 0)),
                             fit_method="FIT")
        tira.frame_final_start = int(c["inicio"])
        tira.frame_final_end = int(c["inicio"]) + int(c["duracion"])
        clips.append(tira)
        if c.get("congelar"):
            fin = int(c["inicio"]) + int(c["duracion"])
            img = col.new_image(f"congelar_{k:02d}", c["congelar"]["png"], canal + 1, fin, fit_method="FIT")
            img.frame_final_duration = int(c["congelar"]["duracion"])

    for fu in plan.get("fundidos", []):
        i, j = fu["entre"]
        # Su largo es el solape de las dos tomas (la anterior se alargó «cuadros» por debajo de la siguiente).
        nuevo_efecto(col, f"fundido_{i:02d}", "CROSS", 5, int(clips[j].frame_final_start),
                     int(fu["cuadros"]), input1=clips[i], input2=clips[j])

    fuente = None
    if plan.get("fuente") and os.path.exists(plan["fuente"]):
        fuente = bpy.data.fonts.load(plan["fuente"])
    for k, t in enumerate(plan.get("textos", [])):
        tx = nuevo_efecto(col, f"texto_{k:02d}", "TEXT", 7 + k % 2, int(t["inicio"]), int(t["duracion"]))
        tx.text = t["texto"]
        tx.font_size = int(t.get("tamano", 120))
        tx.location = (0.5, float(t.get("altura", 0.86)))  # arriba, sin tapar caras
        tx.anchor_x, tx.anchor_y = "CENTER", "CENTER"
        tx.color = (1, 1, 1, 1)
        if hasattr(tx, "use_outline"):
            tx.use_outline, tx.outline_color, tx.outline_width = True, (0, 0, 0, 1), 0.06
        tx.use_shadow, tx.shadow_color = True, (0, 0, 0, 0.6)
        if fuente:
            tx.font = fuente

    # Subtítulos palabra por palabra (grupos cortos en el centro, como en los videos de historias).
    fuente_sub = None
    if plan.get("fuente_subtitulos") and os.path.exists(plan["fuente_subtitulos"]):
        fuente_sub = bpy.data.fonts.load(plan["fuente_subtitulos"])
    for k, t in enumerate(plan.get("subtitulos", [])):
        tx = nuevo_efecto(col, f"sub_{k:03d}", "TEXT", 9 + k % 2, int(t["inicio"]), int(t["duracion"]))
        tx.text = t["texto"]
        tx.font_size = int(plan.get("subtitulos_tamano", 92))
        tx.location = (0.5, float(plan.get("subtitulos_altura", 0.40)))
        tx.anchor_x, tx.anchor_y = "CENTER", "CENTER"
        tx.wrap_width = 0.96
        tx.color = (1, 1, 1, 1)
        if hasattr(tx, "use_outline"):
            tx.use_outline, tx.outline_color, tx.outline_width = True, (0, 0, 0, 1), 0.05
        tx.use_shadow, tx.shadow_color = True, (0, 0, 0, 0.75)
        if hasattr(tx, "shadow_offset"):
            tx.shadow_offset, tx.shadow_blur = 0.06, 0.25
        if fuente_sub:
            tx.font = fuente_sub
        else:
            tx.use_bold = True

    if os.path.isdir(a.cuadros):
        shutil.rmtree(a.cuadros)
    os.makedirs(a.cuadros)
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.filepath = os.path.join(a.cuadros, "")
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    comun.resultado({"cuadros": esc.frame_end, "carpeta": a.cuadros, "clips": len(clips),
                     "textos": len(plan.get("textos", [])), "segundos_render": round(time.time() - t1, 1),
                     "segundos": round(time.time() - t0, 1)})


if __name__ == "__main__":
    main()
