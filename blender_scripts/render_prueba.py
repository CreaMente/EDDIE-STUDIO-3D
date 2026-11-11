"""Render de prueba: escena de referencia para medir la GPU y comprobar la instalación.

Uso:
  blender -b --factory-startup -P render_prueba.py -- --motor CYCLES --ancho 1080 --alto 1920 \
      --muestras 128 --salida /content/eddie/tmp/render_prueba_CYCLES.png
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def material(nombre, color, rugosidad=0.5, sss=0.0, metal=0.0):
    m = bpy.data.materials.new(nombre)
    if bpy.app.version < (5, 0, 0):
        m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rugosidad
    b.inputs["Metallic"].default_value = metal
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        b.inputs["Subsurface Scale"].default_value = 0.05
    return m


def asignar(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def construir_escena():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    esc = bpy.context.scene

    # Habitación: piso y dos paredes.
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    asignar(bpy.context.object, material("Piso", (0.36, 0.25, 0.17), 0.45))
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3, 6), rotation=(math.radians(90), 0, 0))
    asignar(bpy.context.object, material("Pared", (0.75, 0.70, 0.62), 0.8))
    bpy.ops.mesh.primitive_plane_add(size=12, location=(-3, 0, 6), rotation=(0, math.radians(90), 0))
    asignar(bpy.context.object, material("Pared2", (0.55, 0.62, 0.70), 0.8))

    # Mesa.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.9, depth=0.06, location=(0.4, 0.8, 0.75))
    asignar(bpy.context.object, material("Madera", (0.30, 0.16, 0.08), 0.35))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.75, location=(0.4, 0.8, 0.375))
    asignar(bpy.context.object, material("Metal", (0.8, 0.8, 0.8), 0.25, metal=1.0))

    # "Personaje" de referencia: cabeza con piel (subsurface) y cuerpo.
    bpy.ops.mesh.primitive_monkey_add(size=0.55, location=(-0.4, 0.2, 1.62), rotation=(math.radians(10), 0, math.radians(-20)))
    cabeza = bpy.context.object
    mod = cabeza.modifiers.new("Sub", "SUBSURF")
    mod.levels = mod.render_levels = 2
    bpy.ops.object.shade_smooth()
    asignar(cabeza, material("Piel", (0.80, 0.55, 0.42), 0.45, sss=0.25))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.38, location=(-0.4, 0.25, 0.95))
    cuerpo = bpy.context.object
    cuerpo.scale = (1.0, 0.75, 1.45)
    bpy.ops.object.shade_smooth()
    asignar(cuerpo, material("Ropa", (0.10, 0.25, 0.55), 0.7))

    # Objetos sobre la mesa.
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.14, subdivisions=4, location=(0.6, 0.6, 0.92))
    bpy.ops.object.shade_smooth()
    asignar(bpy.context.object, material("Vidrio", (0.9, 0.3, 0.2), 0.05))

    # Luces: principal cálida, relleno frío, contraluz.
    def luz(nombre, tipo, energia, color, loc, rot, tam=1.0):
        d = bpy.data.lights.new(nombre, tipo)
        d.energy = energia
        d.color = color
        if tipo == "AREA":
            d.size = tam
        o = bpy.data.objects.new(nombre, d)
        o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        esc.collection.objects.link(o)

    luz("Principal", "AREA", 260, (1.0, 0.85, 0.7), (3.0, -2.5, 3.5), (55, 0, 50), 2.0)
    luz("Relleno", "AREA", 60, (0.7, 0.8, 1.0), (-2.5, -3.0, 2.0), (65, 0, -35), 3.0)
    luz("Contra", "AREA", 220, (1.0, 0.95, 0.9), (-1.0, 2.5, 3.0), (-50, 0, 180), 1.0)

    mundo = bpy.data.worlds.new("Mundo")
    if bpy.app.version < (5, 0, 0):
        mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.08, 1)
    esc.world = mundo

    # Cámara vertical con profundidad de campo enfocada en la cabeza.
    cam_d = bpy.data.cameras.new("Camara")
    cam_d.lens = 40
    cam_d.dof.use_dof = True
    cam_d.dof.focus_object = cabeza
    cam_d.dof.aperture_fstop = 2.2
    cam = bpy.data.objects.new("Camara", cam_d)
    cam.location = (1.2, -4.2, 1.7)
    esc.collection.objects.link(cam)
    trk = cam.constraints.new("TRACK_TO")
    trk.target = cabeza
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"
    esc.camera = cam
    comun.color_cinematico(esc)
    return esc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--motor", default="CYCLES")
    p.add_argument("--ancho", type=int, default=1080)
    p.add_argument("--alto", type=int, default=1920)
    p.add_argument("--muestras", type=int, default=128)
    p.add_argument("--salida", required=True)
    a = p.parse_args(comun.argumentos())

    t0 = time.time()
    esc = construir_escena()
    r = esc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = a.ancho, a.alto, 100
    r.image_settings.file_format = "PNG"
    r.filepath = a.salida
    info = {"motor": a.motor, "resolucion": f"{a.ancho}x{a.alto}", "blender": bpy.app.version_string}

    if a.motor == "CYCLES":
        r.engine = "CYCLES"
        info.update(comun.configurar_gpu_cycles())
        esc.cycles.samples = a.muestras
        esc.cycles.use_adaptive_sampling = True
        info.update(comun.configurar_denoiser(esc, info["backend"]))
        info["muestras"] = a.muestras
    else:
        r.engine = comun.motor_eevee()
        try:
            esc.eevee.taa_render_samples = min(a.muestras, 64)
        except AttributeError:
            pass

    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    t2 = time.time()
    info.update({
        "segundos_preparacion": round(t1 - t0, 2),
        "segundos_render": round(t2 - t1, 2),
        "salida": a.salida,
        "existe": os.path.exists(a.salida),
    })
    comun.resultado(info)


if __name__ == "__main__":
    main()
