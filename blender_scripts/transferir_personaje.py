"""Transfiere el movimiento de un esqueleto Mixamo animado a un personaje con rig propio (Blender Studio).

  blender -b --factory-startup -P transferir_personaje.py -- --fuente animado.blend \
      --personaje rain_v3.2.blend --ficha estudio/fichas/rain.json --salida animado_rain.blend

La fuente es el resultado de animar_mixamo.py (Remy con las animaciones encadenadas, fundidos, avance
y acciones de Kimodo). El personaje destino tiene un rig de producción (CloudRig) con controles FK/IK y
cara completa; la ficha dice qué control corresponde a cada hueso de Mixamo.

Método (igual que animar_personaje.py, pero sobre los controles del rig):
  1. Se ponen brazos, piernas y columna en modo FK (propiedades «ik_*» = 0).
  2. Para cada control: rotación en el mundo = (pose de la fuente · reposo de la fuente⁻¹) · reposo del
     control. Solo los huesos largos de brazos, piernas y dedos se alinean por dirección (T/A-pose).
  3. Se asigna la matriz en el espacio del armature (Blender resuelve padres y restricciones) por niveles
     de jerarquía, con una actualización entre niveles, y se hornea una clave por cuadro.
  4. El torso se desplaza como la cadera de la fuente, escalado por la altura de cadera.
  5. Anclaje al piso: los pies del personaje quedan a la altura de los de la fuente.
Se verifica midiendo el ángulo entre los huesos de deformación del personaje y los de la fuente.

Los scripts que traen los archivos de Blender Studio (interfaz del rig) NO se ejecutan: solo se usan
los datos del personaje.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402

ALINEAR = ("Arm", "ForeArm", "UpLeg", "Leg", "Thumb", "Index", "Middle", "Ring", "Pinky")
NO_FK = ("stretch", "pole", "parent", "follow", "hinge", "grab", "full")


def rot(m: Matrix) -> Quaternion:
    return m.to_quaternion().normalized()


def dir_mundo(W: Matrix, b) -> Vector:
    return (W.to_3x3() @ (b.tail_local - b.head_local)).normalized()


def poner_fk(rig) -> list[str]:
    """Todas las propiedades «ik_*» de cambio IK/FK a 0 (brazos, piernas, columna y dedos en FK)."""
    cambiadas = []
    for pb in rig.pose.bones:
        for k in list(pb.keys()):
            if k.startswith("ik_") and not any(x in k for x in NO_FK) and isinstance(pb[k], (int, float)):
                pb[k] = 0.0 if isinstance(pb[k], float) else 0
                cambiadas.append(f"{pb.name}.{k}")
    return cambiadas


def profundidad_efectiva(rig, nombre: str, memo: dict, visitando: set | None = None) -> int:
    """Nivel de evaluación de un hueso contando su padre Y los huesos que sigue por restricciones
    (bisagras, «Armature», «Child Of»…), que en estos rigs hacen de padre real. Se ignoran las
    restricciones que copian la cadena IK (están en 0 en modo FK)."""
    if nombre in memo:
        return memo[nombre]
    visitando = visitando or set()
    if nombre in visitando:
        return 0
    visitando.add(nombre)
    pb = rig.pose.bones[nombre]
    deps = [pb.parent.name] if pb.parent else []
    for c in pb.constraints:
        objetivos = [getattr(c, "subtarget", "")]
        if c.type == "ARMATURE":
            objetivos = [t.subtarget for t in c.targets]
        for t in objetivos:
            if t and t in rig.pose.bones and not t.startswith("IK-") and not c.name.startswith("ik_"):
                deps.append(t)
    memo[nombre] = 1 + max((profundidad_efectiva(rig, d, memo, visitando) for d in deps), default=-1)
    return memo[nombre]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fuente", required=True)
    p.add_argument("--personaje", required=True)
    p.add_argument("--ficha", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--max_cuadros", type=int, default=0, help="solo para pruebas rápidas")
    p.add_argument("--rango", default="", help="ini-fin: solo esos cuadros (transferencia por bloques en paralelo)")
    a = p.parse_args(comun.argumentos())
    t0 = time.time()
    ficha = json.loads(open(a.ficha, encoding="utf-8").read())

    bpy.ops.wm.open_mainfile(filepath=a.personaje, load_ui=False, use_scripts=False)
    esc = bpy.context.scene
    destino = max((o for o in esc.objects if o.type == "ARMATURE"), key=lambda o: len(o.data.bones))

    # Esqueleto Mixamo animado (con sus pistas NLA) desde el resultado de animar_mixamo.py.
    antes = set(bpy.data.objects)
    with bpy.data.libraries.load(a.fuente, link=False) as (origen, dest):
        dest.objects = list(origen.objects)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    fuente = next(o for o in nuevos if o.type == "ARMATURE" and any(b.name.startswith("mixamorig:")
                                                                      for b in o.data.bones))
    for o in nuevos:  # mallas, cámaras y luces de la fuente: no se necesitan
        if o is not fuente:
            bpy.data.objects.remove(o, do_unlink=True)
    esc.collection.objects.link(fuente)
    tiras = [t for pista in fuente.animation_data.nla_tracks for t in pista.strips]
    esc.render.fps = 30
    esc.frame_start, esc.frame_end = 1, int(max(t.frame_end for t in tiras))
    if a.max_cuadros:
        esc.frame_end = min(esc.frame_end, a.max_cuadros)
    fuente.hide_render = True  # (no hide_viewport: un objeto oculto en la vista no se evalúa)
    bpy.context.view_layer.update()

    # Las mallas no hacen falta para calcular la transferencia: ocultarlas evita deformarlas en cada
    # actualización (mucho más rápido). Se restauran antes de guardar.
    ocultas = [o for o in esc.objects if o.type in ("MESH", "CURVES", "CURVE") and not o.hide_viewport]
    for o in ocultas:
        o.hide_viewport = True
    fk = poner_fk(destino)
    destino.update_tag()  # sin esto Blender no vuelve a leer las propiedades y los drivers siguen en IK
    bpy.context.view_layer.update()
    pares = [(s, t) for s, t in ficha["huesos"].items() if s in fuente.data.bones and t in destino.data.bones]
    faltan = [t for s, t in ficha["huesos"].items() if t not in destino.data.bones]
    if len(pares) < 15:
        raise SystemExit(f"Solo {len(pares)} controles emparejados; faltan en el rig: {faltan[:10]}")
    torso = ficha["torso"]

    # Reposo con la orientación inicial de la fuente (su objeto se desplaza y gira durante la toma).
    esc.frame_set(esc.frame_start)
    Ws, Wt = fuente.matrix_world.copy(), destino.matrix_world.copy()
    s_rest = {s: rot(Ws @ fuente.data.bones[s].matrix_local) for s, _ in pares}
    t_rest = {}
    for s, t in pares:
        tb, sb = destino.data.bones[t], fuente.data.bones[s]
        base = rot(Wt @ tb.matrix_local)
        if any(s.split(":")[-1].replace("Left", "").replace("Right", "").startswith(k) for k in ALINEAR):
            base = (dir_mundo(Wt, tb).rotation_difference(dir_mundo(Ws, sb)) @ base).normalized()
        t_rest[t] = base
    s_cad = fuente.data.bones["mixamorig:Hips"]
    t_cad = destino.data.bones[torso]
    escala = (Wt @ t_cad.head_local).z / max(1e-4, (Ws @ s_cad.head_local).z)
    print(f"[diag] Ws={[round(x, 4) for x in Ws.to_scale()]} cadera_fuente={tuple(round(x, 3) for x in Ws @ s_cad.head_local)} "
          f"torso_destino={tuple(round(x, 3) for x in Wt @ t_cad.head_local)} escala={escala:.3f}", flush=True)
    s_cad_rest, t_cad_rest = Ws @ s_cad.head_local, Wt @ t_cad.head_local

    niveles: dict[int, list] = {}
    memo: dict = {}
    for s, t in pares:
        niveles.setdefault(profundidad_efectiva(destino, t, memo), []).append((s, t))
    orden = [niveles[k] for k in sorted(niveles)]
    # Algunos rigs (CloudRig) fijan el modo de rotación de los controles con un driver; si se deja, las
    # claves en cuaternión se ignoran. Se quitan solo esos drivers, en los controles que se animan.
    controles = {t for _, t in pares}
    ad = destino.animation_data
    if ad:
        for d in [d for d in ad.drivers if d.data_path.endswith(".rotation_mode")
                  and d.data_path.split('"')[1] in controles]:
            ad.drivers.remove(d)
    for t in controles:
        destino.pose.bones[t].rotation_mode = "QUATERNION"
    destino.animation_data_create()
    destino.animation_data.action = bpy.data.actions.new(f"{ficha['nombre']}_cuerpo")

    previo: dict[str, Quaternion] = {}
    f0, f1 = esc.frame_start, esc.frame_end
    if a.rango:  # el reposo se tomó siempre en el cuadro 1; aquí solo se limita qué cuadros se hornean
        f0, f1 = (int(x) for x in a.rango.split("-"))
    tiempos = {"frame_set": 0.0, "actualizar": 0.0, "calcular": 0.0}
    for f in range(f0, f1 + 1):
        tt = time.time()
        esc.frame_set(f)
        tiempos["frame_set"] += time.time() - tt
        Wf = fuente.matrix_world.copy()
        # Desplazamiento y giro de todo el personaje = los del objeto Mixamo (avance al caminar, «giro»).
        M = Wf @ Ws.inverted()
        destino.matrix_world = M @ Wt
        destino.keyframe_insert("location", frame=f)
        destino.keyframe_insert("rotation_euler", frame=f)
        bpy.context.view_layer.update()
        Wtf = destino.matrix_world.copy()
        for nivel in orden:
            for s, t in nivel:
                pb = destino.pose.bones[t]
                delta = rot(Wf @ fuente.pose.bones[s].matrix) @ s_rest[s].inverted()
                q_mundo = (delta @ t_rest[t]).normalized()
                actual = Wtf @ pb.matrix
                pos = actual.to_translation()
                if t == torso:
                    # Cadera en el espacio del primer cuadro (sin el avance, que ya lleva el objeto).
                    h1 = M.inverted() @ (Wf @ fuente.pose.bones[s].head)
                    pos = M @ (t_cad_rest + (h1 - s_cad_rest) * escala)
                deseada = Matrix.Translation(pos) @ q_mundo.to_matrix().to_4x4()
                pb.matrix = Wtf.inverted() @ deseada
                if t != torso:
                    pb.location = (0.0, 0.0, 0.0)  # solo rotación: la posición la dan sus padres
                q = pb.rotation_quaternion.normalized()
                if t in previo and previo[t].dot(q) < 0:
                    q.negate()
                pb.rotation_quaternion = previo[t] = q
                pb.keyframe_insert("rotation_quaternion", frame=f)
                if t == torso:
                    pb.keyframe_insert("location", frame=f)
            tt = time.time()
            bpy.context.view_layer.update()
            tiempos["actualizar"] += time.time() - tt

    # Anclaje al piso: los dedos del personaje a la altura de los de la fuente (por cuadro).
    pb_torso = destino.pose.bones[torso]
    a_hueso = rot(t_cad.matrix_local).inverted()
    a_arm = Wt.inverted().to_3x3()
    contacto = [(s, t) for s, t in pares if s.endswith(("ToeBase", "Foot"))]
    ajustes = []
    for f in range(f0, f1 + 1):
        esc.frame_set(f)
        alto_s = min((fuente.matrix_world @ fuente.pose.bones[s].head).z for s, _ in contacto)
        alto_t = min((destino.matrix_world @ destino.pose.bones[t].head).z for _, t in contacto)
        dz = alto_s - alto_t
        ajustes.append(dz)
        pb_torso.location = pb_torso.location + a_hueso @ (a_arm @ Vector((0.0, 0.0, dz)))
        pb_torso.keyframe_insert("location", frame=f)

    # Verificación: el hueso de deformación del personaje debe girar lo mismo que el de la fuente respecto
    # a su reposo (brazos y piernas: misma dirección que la fuente, porque se alinearon en reposo).
    errores = {}
    verif = [(s, d) for s, d in ficha.get("verificar", {}).items() if s in fuente.pose.bones and d in destino.pose.bones]
    d_rest = {d: dir_mundo(Wt, destino.data.bones[d]) for _, d in verif}
    for f in range(f0, f1 + 1, max(1, (f1 - f0) // 12)):
        esc.frame_set(f)
        Wf = fuente.matrix_world
        for s, d in verif:
            sp = fuente.pose.bones[s]
            dd = (destino.matrix_world.to_3x3() @ (destino.pose.bones[d].tail - destino.pose.bones[d].head)).normalized()
            if any(s.split(":")[-1].replace("Left", "").replace("Right", "").startswith(k) for k in ALINEAR):
                esperado = (Wf.to_3x3() @ (sp.tail - sp.head)).normalized()
            else:
                delta = rot(Wf @ sp.matrix) @ s_rest[s].inverted() if s in s_rest else Quaternion()
                esperado = delta @ d_rest[d]
            errores[d] = max(errores.get(d, 0.0), math.degrees(esperado.angle(dd)))

    bpy.data.objects.remove(fuente, do_unlink=True)
    for o in ocultas:
        o.hide_viewport = False
    info = {"personaje": ficha["nombre"], "controles": len(pares), "faltan": faltan, "propiedades_fk": len(fk),
            "cuadros": f1 - f0 + 1, "escala_cadera": round(escala, 3), "niveles": len(orden),
            "tiempos_s": {k: round(v, 1) for k, v in tiempos.items()},
            "anclaje_m": {"min": round(min(ajustes), 3), "max": round(max(ajustes), 3)},
            "error_max_grados": {k: round(v, 1) for k, v in sorted(errores.items(), key=lambda x: -x[1])}}
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    info.update({"salida": a.salida, "segundos": round(time.time() - t0, 1)})
    comun.resultado(info)


if __name__ == "__main__":
    main()
