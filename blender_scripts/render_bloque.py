"""Renderiza un rango de cuadros de una escena ya preparada (render por bloques en paralelo).

  blender -b --factory-startup escena.blend -P render_bloque.py -- --ini 1 --fin 120

La escena trae cámara, luces, materiales, muestras y ruta de salida. Aquí solo se vuelve a elegir la GPU
(es una preferencia de Blender y no se guarda en el .blend) y se renderiza el rango pedido.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ini", type=int, required=True)
    p.add_argument("--fin", type=int, required=True)
    a = p.parse_args(comun.argumentos())
    esc = bpy.context.scene
    info = comun.configurar_gpu_cycles()
    info.update(comun.configurar_denoiser(esc, info["backend"]))
    esc.render.use_persistent_data = True
    esc.frame_start, esc.frame_end = a.ini, a.fin
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    info.update({"ini": a.ini, "fin": a.fin, "segundos": round(time.time() - t0, 1)})
    comun.resultado(info)


if __name__ == "__main__":
    main()
