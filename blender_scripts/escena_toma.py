"""Monta una toma con un personaje ya animado y la renderiza a MP4 vertical.

Uso:
  blender -b --factory-startup -P escena_toma.py -- --animado animado.blend --salida toma.mp4 \
      --hdri estudio.hdr --piso '{"color": ".../color.jpg", "normal": "...", "rugosidad": "..."}' \
      [--motor EEVEE|CYCLES] [--muestras 64] [--escala 100] [--audio voz.wav] [--cuadros 1-120]

Escena: iluminación HDRI (Poly Haven) + luz principal suave, piso con textura PBR, cámara de 35 mm que
sigue la cadera del personaje con un acercamiento lento (la cámara nunca se queda quieta) y desenfoque
de fondo. Render de cuadros PNG y codificación H.264 (con el audio si se pasa).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def material_piso(texturas: dict, repeticion: float) -> bpy.types.Material:
    m = bpy.data.materials.new("Piso")
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapeo = nt.nodes.new("ShaderNodeMapping")
    mapeo.inputs["Scale"].default_value = (repeticion, repeticion, 1)
    nt.links.new(coord.outputs["UV"], mapeo.inputs["Vector"])

    def imagen(ruta, no_color=False):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(ruta)
        if no_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mapeo.outputs["Vector"], n.inputs["Vector"])
        return n

    if texturas.get("color"):
        nt.links.new(imagen(texturas["color"]).outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.35, 0.3, 0.26, 1)
    if texturas.get("rugosidad"):
        nt.links.new(imagen(texturas["rugosidad"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if texturas.get("normal"):
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(imagen(texturas["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def mundo_hdri(ruta: str, intensidad: float, rotacion_grados: float) -> None:
    mundo = bpy.data.worlds.new("MundoHDRI")
    nt = mundo.node_tree
    fondo = nt.nodes["Background"]
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ruta)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapeo = nt.nodes.new("ShaderNodeMapping")
    mapeo.inputs["Rotation"].default_value = (0, 0, math.radians(rotacion_grados))
    nt.links.new(coord.outputs["Generated"], mapeo.inputs["Vector"])
    nt.links.new(mapeo.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], fondo.inputs["Color"])
    fondo.inputs["Strength"].default_value = intensidad
    bpy.context.scene.world = mundo


def trayectoria_cadera(rig, f_ini: int, f_fin: int) -> dict[int, Vector]:
    esc = bpy.context.scene
    cad = next(pb for pb in rig.pose.bones if pb.name.endswith("Hips"))
    pos = {}
    for f in range(f_ini, f_fin + 1):
        esc.frame_set(f)
        pos[f] = (rig.matrix_world @ cad.head).copy()
    return pos


def suavizar(pos: dict[int, Vector], ventana: int) -> dict[int, Vector]:
    claves = sorted(pos)
    salida = {}
    for i, f in enumerate(claves):
        vecinos = claves[max(0, i - ventana): i + ventana + 1]
        salida[f] = sum((pos[k] for k in vecinos), Vector()) / len(vecinos)
    return salida


def camara_seguimiento(rig, f_ini: int, f_fin: int, lente: float, distancia: float, altura: float,
                       angulo: float, acercamiento: float) -> bpy.types.Object:
    esc = bpy.context.scene
    pos = suavizar(trayectoria_cadera(rig, f_ini, f_fin), ventana=12)
    objetivo = bpy.data.objects.new("ObjetivoCamara", None)
    esc.collection.objects.link(objetivo)
    cam_d = bpy.data.cameras.new("Camara")
    cam_d.lens = lente
    cam_d.dof.use_dof = True
    cam_d.dof.focus_object = objetivo
    cam_d.dof.aperture_fstop = 2.8
    cam = bpy.data.objects.new("Camara", cam_d)
    esc.collection.objects.link(cam)
    seguir = cam.constraints.new("TRACK_TO")
    seguir.target = objetivo
    seguir.track_axis, seguir.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    esc.camera = cam
    total = max(1, f_fin - f_ini)
    for f in range(f_ini, f_fin + 1):
        t = (f - f_ini) / total
        suave = t * t * (3 - 2 * t)  # el acercamiento arranca y termina suave
        d = distancia * (1 - acercamiento * suave)
        c = pos[f]
        objetivo.location = (c.x, c.y, c.z + 0.35)  # a la altura del pecho
        objetivo.keyframe_insert("location", frame=f)
        cam.location = (c.x + d * math.sin(math.radians(angulo)), c.y - d * math.cos(math.radians(angulo)), altura)
        cam.keyframe_insert("location", frame=f)
    return cam


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--animado", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--hdri", required=True)
    p.add_argument("--piso", default="{}")
    p.add_argument("--motor", default="EEVEE", choices=["EEVEE", "CYCLES"])
    p.add_argument("--muestras", type=int, default=64)
    p.add_argument("--escala", type=int, default=100, help="porcentaje de 1080x1920")
    p.add_argument("--audio", default="")
    p.add_argument("--cuadros", default="", help="rango ini-fin; vacío = todo el movimiento")
    p.add_argument("--lente", type=float, default=35)
    p.add_argument("--distancia", type=float, default=4.2)
    p.add_argument("--altura_camara", type=float, default=1.45)
    p.add_argument("--angulo", type=float, default=25, help="grados alrededor del personaje")
    p.add_argument("--acercamiento", type=float, default=0.25, help="fracción que se acerca durante la toma")
    p.add_argument("--hdri_rotacion", type=float, default=0)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()

    bpy.ops.wm.open_mainfile(filepath=a.animado)
    esc = bpy.context.scene
    rig = next(o for o in esc.objects if o.type == "ARMATURE")
    for o in [o for o in esc.objects if o.type in ("CAMERA", "LIGHT")]:
        bpy.data.objects.remove(o, do_unlink=True)
    if a.cuadros:
        ini, fin = (int(x) for x in a.cuadros.split("-"))
        esc.frame_start, esc.frame_end = ini, fin
    f_ini, f_fin = esc.frame_start, esc.frame_end

    mundo_hdri(a.hdri, 1.0, a.hdri_rotacion)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    piso = bpy.context.object
    piso.data.materials.append(material_piso(json.loads(a.piso), repeticion=14))
    luz_d = bpy.data.lights.new("Principal", "AREA")
    luz_d.energy, luz_d.size, luz_d.color = 350, 3.0, (1.0, 0.92, 0.82)
    luz = bpy.data.objects.new("Principal", luz_d)
    luz.location = (3.0, -3.0, 4.0)
    esc.collection.objects.link(luz)
    apunta = luz.constraints.new("TRACK_TO")
    apunta.target = rig
    apunta.track_axis, apunta.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"

    camara_seguimiento(rig, f_ini, f_fin, a.lente, a.distancia, a.altura_camara, a.angulo, a.acercamiento)

    r = esc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, a.escala
    r.fps = 30
    info = {"motor": a.motor, "cuadros": f_fin - f_ini + 1,
            "resolucion": f"{1080 * a.escala // 100}x{1920 * a.escala // 100}"}
    if a.motor == "CYCLES":
        r.engine = "CYCLES"
        info.update(comun.configurar_gpu_cycles())
        esc.cycles.samples = a.muestras
        esc.cycles.use_adaptive_sampling = True
        info.update(comun.configurar_denoiser(esc, info["backend"]))
    else:
        r.engine = comun.motor_eevee()
        ee = esc.eevee
        for attr, val in (("taa_render_samples", a.muestras), ("use_raytracing", True), ("use_shadows", True)):
            if hasattr(ee, attr):
                setattr(ee, attr, val)
    r.use_motion_blur = True
    comun.color_cinematico(esc)

    carpeta = os.path.splitext(a.salida)[0] + "_cuadros"
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta)
    os.makedirs(carpeta)
    r.image_settings.file_format = "PNG"
    r.filepath = os.path.join(carpeta, "")
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    t2 = time.time()

    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-start_number", str(f_ini),
           "-i", os.path.join(carpeta, "%04d.png")]
    if a.audio and os.path.exists(a.audio):
        cmd += ["-i", a.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            a.salida]
    subprocess.run(cmd, check=True)
    n = f_fin - f_ini + 1
    info.update({"salida": a.salida, "carpeta_cuadros": carpeta, "segundos_render": round(t2 - t1, 1),
                 "segundos_por_cuadro": round((t2 - t1) / n, 2), "segundos_total": round(time.time() - t0, 1),
                 "con_audio": bool(a.audio and os.path.exists(a.audio))})
    comun.resultado(info)


if __name__ == "__main__":
    main()
