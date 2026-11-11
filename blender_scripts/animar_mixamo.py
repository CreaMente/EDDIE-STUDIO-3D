"""Encadena animaciones de la biblioteca Mixamo sobre un personaje Mixamo, con transiciones suaves.

Uso:
  blender -b --factory-startup -P animar_mixamo.py -- --personaje personaje.blend \
      --biblioteca mixamo.blend --salida animado.blend \
      --secuencia '[{"anim": "caminar_herido", "segundos": 4, "avance": 0.6},
                    {"anim": "herido_reposo", "segundos": 3}]' [--mezcla 10] [--hoja hoja.png]

Cada elemento de la secuencia:
  anim       clave de la animación en la biblioteca (ver mixamo.json)
  segundos   duración deseada (se repite el ciclo si hace falta). Sin esto: una vez completa.
  avance     metros por segundo hacia adelante (para caminar/correr grabados «en el lugar»)
  giro       grados a girar el personaje al empezar este tramo (+ = izquierda)

Personaje y animaciones comparten el esqueleto de Mixamo: se aplican directo, sin adaptación.
Las transiciones se hacen con pistas NLA superpuestas (fundido de `mezcla` cuadros).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402

VELOCIDADES = {"caminar": 1.3, "caminar_herido": 0.6, "correr": 3.6}  # m/s por defecto si «avance» es true


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--personaje", required=True)
    p.add_argument("--biblioteca", required=True, help="uno o varios .blend con acciones, separados por coma")
    p.add_argument("--secuencia", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--mezcla", type=int, default=10, help="cuadros de fundido entre animaciones")
    p.add_argument("--hoja", default="")
    p.add_argument("--cuadros_hoja", type=int, default=8)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()

    secuencia = json.loads(a.secuencia)
    bpy.ops.wm.open_mainfile(filepath=a.personaje)
    esc = bpy.context.scene
    esc.render.fps = 30
    rig = next(o for o in esc.objects if o.type == "ARMATURE")

    necesarias = {c["anim"] for c in secuencia}
    disponibles = set()
    for lib in [x for x in a.biblioteca.split(",") if x]:
        with bpy.data.libraries.load(lib, link=False) as (origen, destino):
            disponibles |= set(origen.actions)
            destino.actions = [n for n in origen.actions if n in necesarias and n not in bpy.data.actions]
    faltan = sorted(n for n in necesarias if n not in bpy.data.actions)
    if faltan:
        raise SystemExit(f"Animaciones que no están en la biblioteca: {faltan}. Disponibles: {sorted(disponibles)}")

    rig.animation_data_create()
    rig.animation_data.action = None
    pistas = [rig.animation_data.nla_tracks.new(), rig.animation_data.nla_tracks.new()]
    pistas[0].name, pistas[1].name = "Mixamo A", "Mixamo B"

    # El personaje Mixamo importado mira hacia -Y; el avance se calcula con su orientación actual.
    rumbo = rig.rotation_euler.z
    pos = rig.location.copy()
    rig.keyframe_insert("location", frame=1)
    rig.keyframe_insert("rotation_euler", frame=1)

    cuadro = 1
    tramos = []
    for i, clip in enumerate(secuencia):
        accion = bpy.data.actions[clip["anim"]]
        f0, f1 = accion.frame_range
        largo_ciclo = max(1.0, f1 - f0)
        objetivo = int(round(clip["segundos"] * 30)) if clip.get("segundos") else int(largo_ciclo)
        repeticiones = max(1.0, objetivo / largo_ciclo)
        inicio = cuadro if i == 0 else cuadro - a.mezcla
        tira = pistas[i % 2].strips.new(f"{i:02d}_{clip['anim']}", int(inicio), accion)
        if objetivo < largo_ciclo:
            # Más corta que la animación: se usa solo el principio (sin repetir).
            tira.action_frame_end = f0 + objetivo
            tira.frame_end = inicio + objetivo
            repeticiones = 1.0
        else:
            tira.repeat = repeticiones
        tira.blend_type = "REPLACE"
        tira.extrapolation = "NOTHING"
        if i > 0:
            tira.blend_in = a.mezcla
        if i < len(secuencia) - 1:
            tira.blend_out = a.mezcla
        fin = int(tira.frame_end)

        if clip.get("giro"):
            rig.keyframe_insert("rotation_euler", frame=inicio)
            rumbo += math.radians(clip["giro"])
            rig.rotation_euler.z = rumbo
            rig.keyframe_insert("rotation_euler", frame=inicio + a.mezcla)

        velocidad = clip.get("avance")
        if velocidad is True:
            velocidad = VELOCIDADES.get(clip["anim"], 1.2)
        rig.location = pos
        rig.keyframe_insert("location", frame=inicio if i == 0 else cuadro)
        if velocidad:
            adelante = Matrix.Rotation(rumbo, 3, "Z") @ Vector((0, -1, 0))
            pos = pos + adelante * float(velocidad) * ((fin - (inicio if i == 0 else cuadro)) / 30)
            rig.location = pos
            rig.keyframe_insert("location", frame=fin)
        tramos.append({"anim": clip["anim"], "inicio": int(inicio), "fin": fin, "repeticiones": round(repeticiones, 2),
                       "avance_m_s": velocidad or 0})
        cuadro = fin

    # Movimiento del objeto lineal (velocidad constante al caminar).
    if rig.animation_data.action:
        for fc in rig.animation_data.action.fcurves if hasattr(rig.animation_data.action, "fcurves") else []:
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"
    esc.frame_start, esc.frame_end = 1, cuadro

    info = {"tramos": tramos, "cuadros": cuadro, "segundos": round(cuadro / 30, 2), "mezcla_cuadros": a.mezcla}
    if a.hoja:
        info["hoja"] = hoja_de_contacto(rig, a.hoja, 1, cuadro, a.cuadros_hoja)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    info.update({"salida": a.salida, "segundos_proceso": round(time.time() - t0, 1)})
    comun.resultado(info)


def hoja_de_contacto(rig, ruta: str, f_ini: int, f_fin: int, n: int) -> str:
    """Render rápido (EEVEE si hay GPU, si no Workbench) de N cuadros para revisar la animación."""
    esc = bpy.context.scene
    cam_d = bpy.data.cameras.new("CamHoja")
    cam_d.lens = 35
    cam = bpy.data.objects.new("CamHoja", cam_d)
    esc.collection.objects.link(cam)
    esc.camera = cam
    esc.render.engine = "BLENDER_WORKBENCH"
    esc.display.shading.light = "STUDIO"
    esc.display.shading.color_type = "TEXTURE"
    esc.render.resolution_x, esc.render.resolution_y = 360, 640
    esc.render.image_settings.file_format = "PNG"
    carpeta = os.path.splitext(ruta)[0] + "_cuadros"
    os.makedirs(carpeta, exist_ok=True)
    cad = rig.pose.bones["mixamorig:Hips"]
    for i in range(n):
        f = int(round(f_ini + (f_fin - f_ini) * i / max(1, n - 1)))
        esc.frame_set(f)
        c = rig.matrix_world @ cad.head
        cam.location = (c.x + 2.2, c.y - 3.8, 1.2)
        direccion = Vector((c.x, c.y, 0.9)) - cam.location
        cam.rotation_euler = direccion.to_track_quat("-Z", "Y").to_euler()
        esc.render.filepath = os.path.join(carpeta, f"{i:02d}_f{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    return carpeta


if __name__ == "__main__":
    main()
