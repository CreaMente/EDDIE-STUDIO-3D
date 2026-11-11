"""Une las partes de una transferencia hecha por bloques de cuadros en paralelo.

  blender -b --factory-startup -P unir_transferencias.py -- --partes p0.blend,p1.blend,p2.blend \
      --salida animado_rain.blend

La primera parte es la base; de las demás se copian sus claves (cada parte horneó solo su rango de
cuadros) a la acción del rig y del objeto. Después se asegura la continuidad de los cuaterniones en las
uniones entre partes (cada proceso eligió el signo por su cuenta).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def rig_principal(escena):
    return max((o for o in escena.objects if o.type == "ARMATURE"), key=lambda o: len(o.data.bones))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--partes", required=True)
    p.add_argument("--salida", required=True)
    a = p.parse_args(comun.argumentos())
    t0 = time.time()
    partes = [x for x in a.partes.split(",") if x]
    bpy.ops.wm.open_mainfile(filepath=partes[0], load_ui=False, use_scripts=False)
    rig = rig_principal(bpy.context.scene)
    accion = rig.animation_data.action
    curvas = {(fc.data_path, fc.array_index): fc for fc in comun.curvas_accion(accion)}
    nombre = accion.name
    claves = 0
    for ruta in partes[1:]:
        antes = set(bpy.data.actions)
        with bpy.data.libraries.load(ruta, link=False) as (origen, destino):
            destino.actions = [nombre] if nombre in origen.actions else []
        nuevas = [x for x in bpy.data.actions if x not in antes]
        if not nuevas:
            raise SystemExit(f"La parte {ruta} no tiene la acción «{nombre}».")
        for fc in comun.curvas_accion(nuevas[0]):
            destino_fc = curvas.get((fc.data_path, fc.array_index))
            if destino_fc is None:
                continue
            for kp in fc.keyframe_points:
                destino_fc.keyframe_points.insert(kp.co[0], kp.co[1], options={"FAST"})
                claves += 1
        for x in nuevas:
            bpy.data.actions.remove(x)
    for fc in curvas.values():
        fc.update()
    saltos = comun.cuaterniones_continuos(accion)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    comun.resultado({"partes": len(partes), "claves_copiadas": claves, "signos_corregidos": saltos,
                     "salida": a.salida, "segundos": round(time.time() - t0, 1)})


if __name__ == "__main__":
    main()
