"""Animación secundaria y exageración sobre un personaje del elenco ya animado (después de cuerpo y cara).

  blender -b -P secundario.py -- --animado animado_rain.blend --ficha estudio/fichas/rain.json \
      --salida animado_rain.blend [--exagerar 0.4] [--secundario 1]

1. Seguimiento y superposición (pelo, coleta, bufanda…): cada cadena de la ficha («secundario») se simula
   como una cuerda con resorte. La punta de cada tramo es una masa que quiere volver a su reposo pero
   conserva la inercia: cuando la cabeza gira, frena o camina, la coleta llega tarde, se pasa y se asienta.
   Se hornea como claves en los controles FK (el rig sigue siendo editable).
2. Exagerar (estilo caricatura): los gestos de columna, cuello, cabeza y brazos se acentúan respecto de su
   promedio en el tiempo (los acentos crecen, la postura de base no cambia). Las piernas y la cadera no se
   tocan (los pies no patinan). 0 = nada; 0.3–0.6 = caricatura; más de 1 se vuelve grotesco.
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

# Controles del cuerpo que se acentúan al exagerar (por el hueso Mixamo al que corresponden): columna, cuello,
# cabeza, hombros y brazos. Cadera, piernas y dedos no (los pies patinarían; los dedos ya vienen de la animación).
EXAGERAR = {"Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
            "LeftForeArm", "RightForeArm", "LeftHand", "RightHand"}


def quitar_drivers_modo(rig, nombres: set) -> None:
    ad = rig.animation_data
    if ad:
        for d in [d for d in ad.drivers if d.data_path.endswith(".rotation_mode")
                  and d.data_path.split('"')[1] in nombres]:
            ad.drivers.remove(d)


def quitar_claves(accion, nombres: set) -> None:
    for fc in comun.curvas_accion(accion):
        if fc.data_path.startswith('pose.bones["') and fc.data_path.split('"')[1] in nombres:
            try:
                fc.keyframe_points.clear()
            except AttributeError:
                while fc.keyframe_points:
                    fc.keyframe_points.remove(fc.keyframe_points[0])


def simular(rig, cadenas: list[dict], f0: int, f1: int, reposo: dict | None = None, torso: str = "") -> dict:
    """Cuerda con resorte por cadena; devuelve {hueso: [cuaternión por cuadro]}. «reposo» = la pose que el
    rig trae de fábrica en cada hueso (forma del peinado): el resorte vuelve a ella, no a la recta."""
    reposo = reposo or {}
    esc = bpy.context.scene
    W = rig.matrix_world
    # 1. Marco de reposo del primer hueso de cada cadena, cuadro a cuadro (pelo sin claves = sigue a la cabeza).
    primeros = {c["huesos"][0] for c in cadenas}
    marcos = {h: [] for h in primeros}
    # Rumbo del cuerpo (giro alrededor de la vertical) para la gravedad: el pelo cuelga como en reposo pero
    # gira con el cuerpo, aunque la cabeza se incline.
    pb_torso = rig.pose.bones.get(torso) if torso else None
    frente_rep, eje_local = None, Vector((0, 0, 1))
    if pb_torso:  # el eje local del torso más horizontal en reposo sirve de «frente»
        ml = pb_torso.bone.matrix_local.to_3x3()
        candidatos = []
        for e in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
            v = W.to_3x3() @ ml @ e
            v.z = 0
            candidatos.append((v.length, e, v))
        _, eje_local, frente_rep = max(candidatos, key=lambda x: x[0])
    rumbos = []
    for f in range(f0, f1 + 1):
        esc.frame_set(f)
        for h in primeros:
            marcos[h].append(W @ rig.pose.bones[h].matrix)
        giro = 0.0
        if pb_torso and frente_rep.length > 1e-6:
            fr = (W @ pb_torso.matrix).to_3x3() @ eje_local
            fr.z = 0
            if fr.length > 1e-6:
                giro = math.atan2(frente_rep.x * fr.y - frente_rep.y * fr.x, frente_rep.dot(fr))
        rumbos.append(Matrix.Rotation(giro, 3, "Z"))
    salida = {}
    dt_frames = f1 - f0 + 1
    for c in cadenas:
        huesos = [h for h in c["huesos"] if h in rig.pose.bones]
        if not huesos:
            continue
        rig_k = float(c.get("rigidez", 0.25))      # 0–1: cuánto vuelve al reposo por cuadro
        amort = float(c.get("amortiguacion", 0.18))  # 0–1: cuánta velocidad pierde por cuadro
        largo = float(c.get("largo_m", 0.08))       # largo «visual» de cada tramo (los controles son cortos)
        maximo = math.radians(float(c.get("max_grados", 55)))
        rel = [rig.data.bones[huesos[i - 1]].matrix_local.inverted() @ rig.data.bones[huesos[i]].matrix_local
               @ reposo.get(huesos[i], Quaternion()).to_matrix().to_4x4() for i in range(1, len(huesos))]
        gravedad = float(c.get("gravedad", 0.5))   # 0 = sigue rígido a la cabeza; 1 = cuelga siempre igual
        # Dirección de cada tramo en reposo (personaje derecho), en el mundo, para la gravedad.
        A = rig.data.bones[huesos[0]].matrix_local @ reposo.get(huesos[0], Quaternion()).to_matrix().to_4x4()
        d_colgar = []
        for i in range(len(huesos)):
            if i:
                A = A @ rel[i - 1]
            d_colgar.append((W.to_3x3() @ A.to_3x3() @ Vector((0, 1, 0))).normalized())
        pos, prev = [None] * len(huesos), [None] * len(huesos)
        for h in huesos:
            salida[h] = []
        for k in range(dt_frames):
            M = marcos[huesos[0]][k]
            for i, h in enumerate(huesos):
                if i:
                    M = M_nuevo @ rel[i - 1]
                cabeza = M.to_translation()
                R = M.to_3x3().normalized()
                d_rep = (R @ Vector((0, 1, 0))).normalized()
                d_obj = d_rep.slerp((rumbos[k] @ d_colgar[i]).normalized(), gravedad).normalized() if gravedad else d_rep
                objetivo = cabeza + d_obj * largo
                if pos[i] is None:
                    pos[i] = prev[i] = objetivo.copy()
                # Verlet: inercia (con amortiguación) + resorte hacia el reposo.
                nueva = pos[i] + (pos[i] - prev[i]) * (1.0 - amort) + (objetivo - pos[i]) * rig_k
                d_sim = nueva - cabeza
                if d_sim.length < 1e-6:
                    d_sim = d_rep.copy()
                d_sim.normalize()
                ang = d_obj.angle(d_sim, 0.0)
                if ang > maximo:  # tope del balanceo alrededor de su caída: nunca da vueltas
                    d_sim = d_obj.slerp(d_sim, maximo / ang).normalized()
                prev[i], pos[i] = pos[i], cabeza + d_sim * largo
                q_mundo = d_rep.rotation_difference(d_sim)
                q_rep = R.to_quaternion()
                base = (q_rep.inverted() @ q_mundo @ q_rep).normalized()
                salida[h].append((reposo.get(h, Quaternion()) @ base).normalized())
                M_nuevo = Matrix.Translation(cabeza) @ (q_mundo.to_matrix() @ R).to_4x4()
    return salida


def exagerar(rig, accion, controles: set, factor: float, ventana: int = 9) -> int:
    """Acentúa cada control respecto de su promedio móvil (en cuaterniones). Devuelve cuántos tocó."""
    curvas = [fc for fc in comun.curvas_accion(accion)
              if fc.data_path.endswith("rotation_quaternion") and fc.data_path.split('"')[1] in controles]
    por_hueso: dict[str, dict[int, object]] = {}
    for fc in curvas:
        por_hueso.setdefault(fc.data_path.split('"')[1], {})[fc.array_index] = fc
    tocados = 0
    mitad = ventana // 2
    for hueso, fcs in por_hueso.items():
        if len(fcs) < 4:
            continue
        n = min(len(fcs[i].keyframe_points) for i in range(4))
        if n < ventana:
            continue
        qs = [Quaternion([fcs[i].keyframe_points[k].co[1] for i in range(4)]).normalized() for k in range(n)]
        for k in range(1, n):  # continuidad de signo antes de promediar
            if qs[k].dot(qs[k - 1]) < 0:
                qs[k].negate()
        nuevos = []
        for k in range(n):
            a, b = max(0, k - mitad), min(n, k + mitad + 1)
            suma = Quaternion((0, 0, 0, 0))
            for q in qs[a:b]:
                suma = Quaternion([x + y for x, y in zip(suma, q)])
            media = suma.normalized()
            d = media.inverted() @ qs[k]
            eje, ang = d.to_axis_angle()
            nuevos.append((media @ Quaternion(eje, ang * (1.0 + factor))).normalized())
        for k, q in enumerate(nuevos):
            for i in range(4):
                fcs[i].keyframe_points[k].co[1] = q[i]
        for fc in fcs.values():
            fc.update()
        tocados += 1
    return tocados


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--animado", required=True)
    p.add_argument("--ficha", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--exagerar", type=float, default=0.0)
    p.add_argument("--secundario", type=int, default=1)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()
    ficha = json.load(open(a.ficha, encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=a.animado, load_ui=False, use_scripts=False)
    esc = bpy.context.scene
    rig = max((o for o in esc.objects if o.type == "ARMATURE"), key=lambda o: len(o.data.bones))
    accion = rig.animation_data.action if rig.animation_data else None
    if accion is None:
        raise SystemExit("El personaje no tiene animación: primero transferir_personaje.py.")
    f0, f1 = esc.frame_start, esc.frame_end
    info = {"cuadros": f1 - f0 + 1}

    if a.exagerar > 0:
        controles = {t for s, t in ficha["huesos"].items() if s.split(":")[-1] in EXAGERAR} - {ficha.get("torso")}
        info["exagerados"] = exagerar(rig, accion, controles, a.exagerar)
        comun.cuaterniones_continuos(accion)
        info["exagerar"] = a.exagerar

    cadenas = ficha.get("secundario", []) if a.secundario else []
    if cadenas:
        nombres = {h for c in cadenas for h in c["huesos"] if h in rig.pose.bones}
        quitar_drivers_modo(rig, nombres)
        quitar_claves(accion, nombres)
        reposo = {}
        for h in nombres:  # se conserva la forma del peinado que trae el personaje
            pb = rig.pose.bones[h]
            reposo[h] = (pb.rotation_quaternion.copy() if pb.rotation_mode == "QUATERNION"
                         else pb.rotation_euler.to_quaternion() if pb.rotation_mode != "AXIS_ANGLE"
                         else Quaternion(pb.rotation_axis_angle[1:], pb.rotation_axis_angle[0])).normalized()
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = reposo[h]
        # Las mallas no hacen falta para mover el esqueleto: se ocultan mientras se simula (mucho más rápido).
        ocultas = [o for o in esc.objects if o.type == "MESH" and not o.hide_viewport]
        for o in ocultas:
            o.hide_viewport = True
        poses = simular(rig, cadenas, f0, f1, reposo, ficha.get("torso", ""))
        for o in ocultas:
            o.hide_viewport = False
        for h, lista in poses.items():
            pb = rig.pose.bones[h]
            for k, q in enumerate(lista):
                pb.rotation_quaternion = q
                pb.keyframe_insert("rotation_quaternion", frame=f0 + k)
        comun.cuaterniones_continuos(accion)
        angs = {}
        for h, lista in poses.items():  # cuánto se aparta del peinado de reposo
            d = [reposo[h].rotation_difference(q).angle for q in lista]
            angs[h] = round(max(math.degrees(min(x, 2 * math.pi - x)) for x in d), 1)
        info["secundario"] = {"cadenas": len(cadenas), "huesos": len(poses), "giro_max_grados": angs}

    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    info.update({"salida": a.salida, "segundos": round(time.time() - t0, 1)})
    comun.resultado(info)


if __name__ == "__main__":
    main()
