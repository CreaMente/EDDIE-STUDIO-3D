"""Aplica un movimiento de Kimodo (BVH, esqueleto SOMA 77 en T-pose) a un personaje MPFB (rig «mixamo»).

Uso:
  blender -b --factory-startup -P animar_personaje.py -- --personaje personaje.blend --bvh mov.bvh \
      --salida animado.blend [--hoja hoja.png --cuadros 8]

Método (retargeting por rotaciones en el mundo, independiente de la pose de reposo):
  1. El BVH está en T-pose; el personaje puede estar en T o en A. Para brazos y piernas se calcula su
     «reposo en T»: la rotación mínima que lleva su dirección de reposo a la del hueso de SOMA. Cadera,
     columna, cabeza, manos y pies heredan la alineación de su padre (no se alinean por dirección).
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

# Huesos (nombres Mixamo sin lado) cuya dirección de reposo depende de la pose (T o A).
ALINEAR_DIRECCION = {"Arm", "ForeArm", "UpLeg", "Leg"}

# Articulaciones (nombres SOMA) que pueden apoyarse en el piso.
CONTACTO = {"Hips", "LeftShin", "RightShin", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase",
            "LeftHand", "RightHand"}


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
    p.add_argument("--accion", default="", help="nombre para la acción resultante (para usarla en una secuencia)")
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
    # Solo los huesos largos de brazos y piernas se alinean por dirección (es lo que cambia entre una pose
    # en T y una en A). El resto hereda la alineación de su padre: la dirección de huesos como la cadera,
    # los pies o las manos depende de cómo se armó cada esqueleto, no de la pose (la cadera de SOMA apunta
    # hacia abajo y la de Mixamo hacia arriba: alinearla volteaba la pelvis 156°).
    s_rest = {s: rot(Ws @ fuente.data.bones[s].matrix_local) for s, _ in pares}
    mapa_t = {t: s for s, t in pares}
    alineacion = {}
    for tb in destino.data.bones:  # en orden padre → hijo
        s = mapa_t.get(tb.name)
        if s and tb.name.split(":")[-1].replace("Left", "").replace("Right", "") in ALINEAR_DIRECCION:
            alineacion[tb.name] = dir_mundo(Wt, tb).rotation_difference(dir_mundo(Ws, fuente.data.bones[s]))
        elif tb.parent and tb.parent.name in alineacion:
            alineacion[tb.name] = alineacion[tb.parent.name]
        else:
            alineacion[tb.name] = Quaternion()
    t_rest_T = {t: (alineacion[t] @ rot(Wt @ destino.data.bones[t].matrix_local)).normalized() for _, t in pares}

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
    # Acción nueva y propia (la del BVH se llama igual que la que queremos dejar al final).
    destino.animation_data_create()
    destino.animation_data.action = bpy.data.actions.new("_retarget_tmp")

    previo = {}  # último cuaternión horneado por hueso (para no saltar de q a -q)
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
            basis = basis.normalized()
            if b.name in previo and previo[b.name].dot(basis) < 0:
                basis.negate()
            previo[b.name] = basis
            pb.rotation_quaternion = basis
            pb.keyframe_insert("rotation_quaternion", frame=f)

        # Traslación de la cadera (en el espacio de reposo del hueso).
        s_cad_mundo = Ws @ fuente.pose.bones[s_cad.name].head
        deseada_mundo = t_cad_rest + (s_cad_mundo - s_cad_rest) * escala
        deseada_arm = Wt.inverted() @ deseada_mundo
        pb = destino.pose.bones[t_cad.name]
        pb.location = rot(t_cad.matrix_local).inverted() @ (deseada_arm - t_cad.head_local)
        pb.keyframe_insert("location", frame=f)

    # Anclaje al piso cuadro a cuadro: la articulación de contacto más baja del personaje (dedos, tobillos,
    # rodillas, manos o cadera) queda a la misma altura que en el movimiento original. Así, al arrodillarse
    # o sentarse, las rodillas y la cadera tocan el piso aunque las proporciones de las piernas sean otras.
    contactos = [(s, t) for s, t in pares if s.split(":")[-1] in CONTACTO]
    pb_cad = destino.pose.bones[t_cad.name]
    a_hueso = rot(t_cad.matrix_local).inverted()
    a_arm = Wt.inverted().to_3x3()
    ajustes = []
    for f in range(f_ini, f_fin + 1):
        esc.frame_set(f)
        alto_s = min((Ws @ fuente.pose.bones[s].head).z for s, _ in contactos)
        alto_t = min((Wt @ destino.pose.bones[t].head).z for _, t in contactos)
        dz = alto_s - alto_t
        ajustes.append(dz)
        pb_cad.location = pb_cad.location + a_hueso @ (a_arm @ Vector((0.0, 0.0, dz)))
        pb_cad.keyframe_insert("location", frame=f)

    bpy.data.objects.remove(fuente, do_unlink=True)
    if accion and accion.name in bpy.data.actions:
        bpy.data.actions.remove(accion)  # la acción del BVH ya no hace falta
    if a.accion and destino.animation_data and destino.animation_data.action:
        previa = bpy.data.actions.get(a.accion)
        if previa and previa != destino.animation_data.action:
            bpy.data.actions.remove(previa)
        destino.animation_data.action.name = a.accion
        destino.animation_data.action.use_fake_user = True

    info = {"huesos_emparejados": len(pares), "cuadros": f_fin - f_ini + 1, "fps": esc.render.fps,
            "escala_traslacion": round(escala, 4), "giro_180": giro,
            "anclaje_piso_m": {"min": round(min(ajustes), 4), "max": round(max(ajustes), 4)}}

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
