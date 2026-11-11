"""Aplica un movimiento de Kimodo (BVH, esqueleto SOMA 77 en T-pose) a un personaje MPFB (rig «mixamo»).

Uso:
  blender -b --factory-startup -P animar_personaje.py -- --personaje personaje.blend --bvh mov.bvh \
      --salida animado.blend [--hoja hoja.png --cuadros 8]

Método (retargeting por dirección de huesos, independiente de la pose de reposo):
  1. El personaje MPFB está en A-pose y el BVH en T-pose. Para cada hueso se calcula su «reposo en T»:
     la rotación mínima que lleva su dirección de reposo a la dirección del hueso equivalente de SOMA.
  2. En cada cuadro: rotación_mundo_destino = (pose_SOMA · reposo_SOMA⁻¹) · reposo_en_T_destino.
  3. Se convierten a rotaciones locales (de padre a hijo) y se hornean como claves.
  4. La cadera se desplaza como en el BVH, escalada por la diferencia de estatura.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402

# SOMA (Kimodo) → mixamo (MPFB). Los dedos de SOMA tienen un hueso más (metacarpo) en índice a meñique.
MAPA = {
    "Hips": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Chest": "Spine2",
    "Neck1": "Neck", "Head": "Head",
}
for lado in ("Left", "Right"):
    MAPA.update({
        f"{lado}Shoulder": f"{lado}Shoulder", f"{lado}Arm": f"{lado}Arm", f"{lado}ForeArm": f"{lado}ForeArm",
        f"{lado}Hand": f"{lado}Hand",
        f"{lado}Leg": f"{lado}UpLeg", f"{lado}Shin": f"{lado}Leg", f"{lado}Foot": f"{lado}Foot",
        f"{lado}ToeBase": f"{lado}ToeBase",
    })
    for i in (1, 2, 3):
        MAPA[f"{lado}HandThumb{i}"] = f"{lado}HandThumb{i}"
    for dedo in ("Index", "Middle", "Ring", "Pinky"):
        for i in (1, 2, 3):
            MAPA[f"{lado}Hand{dedo}{i + 1}"] = f"{lado}Hand{dedo}{i}"


def buscar_hueso(arm, nombre: str):
    """Encuentra un hueso aunque tenga prefijo (mixamorig:Hips, etc.)."""
    if nombre in arm.data.bones:
        return arm.data.bones[nombre]
    for b in arm.data.bones:
        if b.name.split(":")[-1] == nombre:
            return b
    return None


def rot(m: Matrix) -> Quaternion:
    return m.to_quaternion().normalized()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--personaje", required=True)
    p.add_argument("--bvh", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--hoja", default="")
    p.add_argument("--cuadros", type=int, default=8)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()

    bpy.ops.wm.open_mainfile(filepath=a.personaje)
    esc = bpy.context.scene
    destino = next(o for o in esc.objects if o.type == "ARMATURE")

    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.import_anim.bvh(filepath=a.bvh, global_scale=0.01, axis_forward="-Z", axis_up="Y",
                            rotate_mode="NATIVE", use_fps_scale=False, update_scene_fps=True,
                            update_scene_duration=True)
    fuente = bpy.context.selected_objects[0]
    fuente.name = "kimodo_fuente"
    bpy.context.view_layer.update()

    pares = []
    for s_nombre, t_nombre in MAPA.items():
        sb, tb = buscar_hueso(fuente, s_nombre), buscar_hueso(destino, t_nombre)
        if sb and tb:
            pares.append((sb.name, tb.name))
    if len(pares) < 15:
        raise SystemExit(f"Solo se emparejaron {len(pares)} huesos: ¿el personaje tiene el rig mixamo?")

    Ws, Wt = fuente.matrix_world, destino.matrix_world

    def dir_mundo(arm_w, bone):
        return (arm_w.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()

    # ¿Miran hacia el mismo lado? Se compara hacia dónde apunta el brazo izquierdo en reposo.
    s_izq, t_izq = buscar_hueso(fuente, "LeftArm"), buscar_hueso(destino, "LeftArm")
    giro = False
    if s_izq and t_izq and dir_mundo(Ws, s_izq).x * dir_mundo(Wt, t_izq).x < 0:
        fuente.rotation_euler.z += math.pi
        bpy.context.view_layer.update()
        Ws = fuente.matrix_world
        giro = True

    # Reposo en mundo y «reposo en T» del destino.
    s_rest = {s: rot(Ws @ fuente.data.bones[s].matrix_local) for s, _ in pares}
    t_rest_T = {}
    for s, t in pares:
        tb = destino.data.bones[t]
        sb = fuente.data.bones[s]
        alinear = dir_mundo(Wt, tb).rotation_difference(dir_mundo(Ws, sb))
        t_rest_T[t] = (alinear @ rot(Wt @ tb.matrix_local)).normalized()
    mapa_t = {t: s for s, t in pares}

    # Escala de la traslación de la cadera según la estatura de cada esqueleto.
    s_cad, t_cad = fuente.data.bones[mapa_t[next(t for t in mapa_t if t.endswith("Hips"))]], None
    t_cad = next(destino.data.bones[t] for t in mapa_t if t.endswith("Hips"))
    altura_s = (Ws @ s_cad.head_local).z
    altura_t = (Wt @ t_cad.head_local).z
    escala = altura_t / altura_s if altura_s > 1e-4 else 1.0
    s_cad_rest = Ws @ s_cad.head_local
    t_cad_rest = Wt @ t_cad.head_local

    accion = fuente.animation_data.action
    f_ini, f_fin = (int(x) for x in accion.frame_range)
    esc.frame_start, esc.frame_end = f_ini, f_fin

    orden = [b for b in destino.data.bones]  # bones ya viene en orden padre→hijo
    Wt_rot_inv = rot(Wt).inverted()
    for pb in destino.pose.bones:
        pb.rotation_mode = "QUATERNION"

    for f in range(f_ini, f_fin + 1):
        esc.frame_set(f)
        pose_arm = {}  # rotación de pose en espacio del armature destino
        for b in orden:
            rest_arm = rot(b.matrix_local)
            if b.name in mapa_t:
                s = mapa_t[b.name]
                s_pose_mundo = rot(Ws @ fuente.pose.bones[s].matrix)
                delta = s_pose_mundo @ s_rest[s].inverted()
                pose_arm[b.name] = Wt_rot_inv @ (delta @ t_rest_T[b.name])
            elif b.parent:
                pose_arm[b.name] = pose_arm[b.parent.name] @ rot(b.parent.matrix_local).inverted() @ rest_arm
            else:
                pose_arm[b.name] = rest_arm
            if b.parent:
                padre_rest = rot(b.parent.matrix_local)
                basis = rest_arm.inverted() @ padre_rest @ pose_arm[b.parent.name].inverted() @ pose_arm[b.name]
            else:
                basis = rest_arm.inverted() @ pose_arm[b.name]
            pb = destino.pose.bones[b.name]
            pb.rotation_quaternion = basis.normalized()
            pb.keyframe_insert("rotation_quaternion", frame=f)

        # Traslación de la cadera (en el espacio de reposo del hueso).
        s_cad_mundo = Ws @ fuente.pose.bones[s_cad.name].head
        deseada_mundo = t_cad_rest + (s_cad_mundo - s_cad_rest) * escala
        deseada_arm = Wt.inverted() @ deseada_mundo
        pb = destino.pose.bones[t_cad.name]
        pb.location = rot(t_cad.matrix_local).inverted() @ (deseada_arm - t_cad.head_local)
        pb.keyframe_insert("location", frame=f)

    bpy.data.objects.remove(fuente, do_unlink=True)

    # Pies al piso: el punto más bajo de los dedos en todo el clip debe quedar a ras del suelo.
    dedos = [destino.pose.bones[t] for t in mapa_t if t.endswith("ToeBase") or t.endswith("Foot")]
    piso_rest = min((Wt @ destino.data.bones[pb.name].head_local).z for pb in dedos)
    minimo = float("inf")
    for f in range(f_ini, f_fin + 1, 2):
        esc.frame_set(f)
        minimo = min(minimo, min((Wt @ pb.head).z for pb in dedos))
    # Solo se sube si algún pie atraviesa el piso (bajar podría dejar los pies flotando en saltos).
    correccion = piso_rest - minimo if minimo < piso_rest - 0.005 else 0.0
    if correccion:
        destino.location.z += correccion

    info = {"huesos_emparejados": len(pares), "cuadros": f_fin - f_ini + 1, "fps": esc.render.fps,
            "escala_traslacion": round(escala, 4), "giro_180": giro, "correccion_piso_m": round(correccion, 4)}

    if a.hoja:
        info["hoja"] = hoja_de_contacto(destino, a.hoja, f_ini, f_fin, a.cuadros)

    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    info.update({"salida": a.salida, "segundos": round(time.time() - t0, 1)})
    comun.resultado(info)


def hoja_de_contacto(rig, ruta: str, f_ini: int, f_fin: int, n: int) -> str:
    """Render rápido (Workbench) de N cuadros del movimiento para revisarlo de un vistazo."""
    esc = bpy.context.scene
    cuerpo = next(o for o in esc.objects if o.type == "MESH" and o.parent == rig) if any(
        o.parent == rig for o in esc.objects) else None
    cam_d = bpy.data.cameras.new("CamHoja")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 3.2
    cam = bpy.data.objects.new("CamHoja", cam_d)
    cam.location = (3.5, -6.0, 1.1)
    cam.rotation_euler = (math.radians(88), 0, math.radians(30))
    esc.collection.objects.link(cam)
    esc.camera = cam
    esc.render.engine = "BLENDER_WORKBENCH"
    esc.display.shading.light = "STUDIO"
    esc.display.shading.color_type = "MATERIAL"
    esc.render.resolution_x, esc.render.resolution_y = 360, 640
    esc.render.image_settings.file_format = "PNG"
    carpeta = os.path.splitext(ruta)[0] + "_cuadros"
    os.makedirs(carpeta, exist_ok=True)
    rutas = []
    for i in range(n):
        f = int(round(f_ini + (f_fin - f_ini) * i / max(1, n - 1)))
        esc.frame_set(f)
        # La cámara sigue a la cadera para que el personaje no salga de cuadro si se desplaza.
        cad = next(pb for pb in rig.pose.bones if pb.name.endswith("Hips"))
        c = rig.matrix_world @ cad.head
        cam.location = (c.x + 3.5, c.y - 6.0, 1.1)
        esc.render.filepath = os.path.join(carpeta, f"{i:02d}_f{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        rutas.append(esc.render.filepath)
    bpy.data.objects.remove(cam, do_unlink=True)
    del cuerpo
    return carpeta


if __name__ == "__main__":
    main()
