"""Importa personajes y animaciones de Mixamo (FBX) a la biblioteca del estudio.

  personaje:   blender -b --factory-startup -P mixamo_importar.py -- personaje --fbx Remy.fbx \
                   --nombre remy --carpeta <biblioteca/personajes/remy> [--altura 1.75]
               → personaje.blend (texturas empaquetadas, materiales mejorados), vista.png, personaje.json

  animaciones: blender -b --factory-startup -P mixamo_importar.py -- animaciones --carpeta_fbx <entrada> \
                   --salida <biblioteca/animaciones/mixamo.blend> [--indice mixamo_indice.json]
               → un .blend con todas las acciones + mixamo.json (catálogo con duración y desplazamiento)

Personajes y animaciones de Mixamo comparten el esqueleto «mixamorig:*», así que las animaciones se
aplican directamente, sin adaptación.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def importar_fbx(ruta: str) -> list[bpy.types.Object]:
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=ruta, use_anim=True, automatic_bone_orientation=False,
                             ignore_leaf_bones=False)
    return [o for o in bpy.context.scene.objects if o not in antes]


def caja_evaluada(objetos) -> tuple[Vector, Vector]:
    """Caja envolvente de las mallas ya deformadas (con armature y escalas aplicadas)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mins, maxs = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in objetos:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        m = ev.to_mesh()
        for v in m.vertices:
            p = ev.matrix_world @ v.co
            mins = Vector(map(min, mins, p))
            maxs = Vector(map(max, maxs, p))
        ev.to_mesh_clear()
    return mins, maxs


def nodo_imagen(nt, nombre_parcial: str):
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image and nombre_parcial.lower() in n.image.name.lower():
            return n
    return None


def imagen_por_nombre(nombre_parcial: str):
    for img in bpy.data.images:
        if nombre_parcial.lower() in img.name.lower():
            return img
    return None


def mejorar_material(mat: bpy.types.Material, base_textura: str, es_piel: bool, transparente: bool) -> list[str]:
    """Conecta mapas que el importador FBX deja sueltos: brillo→rugosidad, opacidad→alfa; piel con SSS."""
    hechos = []
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return hechos
    # El importador FBX conecta el mapa de BRILLO (gloss) directo a la RUGOSIDAD, que es su inverso:
    # lo brillante queda mate y al revés. Se intercala una inversión.
    rug = bsdf.inputs["Roughness"]
    if rug.is_linked:
        origen = rug.links[0].from_node
        if origen.type == "TEX_IMAGE" and origen.image and "gloss" in origen.image.name.lower():
            origen.image.colorspace_settings.name = "Non-Color"
            inv = nt.nodes.new("ShaderNodeInvert")
            nt.links.new(origen.outputs["Color"], inv.inputs["Color"])
            nt.links.new(inv.outputs["Color"], rug)
            hechos.append("brillo→rugosidad invertido")
    brillo = imagen_por_nombre(f"{base_textura}_Gloss")
    if brillo and not bsdf.inputs["Roughness"].is_linked:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = brillo
        brillo.colorspace_settings.name = "Non-Color"
        inv = nt.nodes.new("ShaderNodeInvert")
        nt.links.new(tex.outputs["Color"], inv.inputs["Color"])
        nt.links.new(inv.outputs["Color"], bsdf.inputs["Roughness"])
        hechos.append("rugosidad")
    normal = imagen_por_nombre(f"{base_textura}_Normal")
    if normal and not bsdf.inputs["Normal"].is_linked:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = normal
        normal.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        hechos.append("normal")
    if transparente:
        opac = imagen_por_nombre(f"{base_textura}_Opacity")
        if opac and not bsdf.inputs["Alpha"].is_linked:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = opac
            opac.colorspace_settings.name = "Non-Color"
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Alpha"])
            hechos.append("opacidad")
        for attr, val in (("blend_method", "HASHED"), ("surface_render_method", "DITHERED")):
            if hasattr(mat, attr):
                try:
                    setattr(mat, attr, val)
                except TypeError:
                    pass
    if es_piel:
        bsdf.inputs["Subsurface Weight"].default_value = 0.15
        bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        bsdf.inputs["Subsurface Scale"].default_value = 0.012
        hechos.append("piel_sss")
    return hechos


def vista_previa(objetos, rig, ruta: str) -> dict:
    esc = bpy.context.scene
    mins, maxs = caja_evaluada(objetos)
    altura = maxs.z - mins.z
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, mins.z))
    piso = bpy.context.object
    m = bpy.data.materials.new("PisoVista")
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.33, 0.36, 1)
    piso.data.materials.append(m)
    centro = (mins + maxs) / 2
    objetivo = bpy.data.objects.new("ObjetivoVista", None)
    objetivo.location = (centro.x, centro.y, mins.z + altura * 0.55)
    esc.collection.objects.link(objetivo)
    temporales = [piso, objetivo]

    def luz(nombre, energia, color, loc, tam):
        d = bpy.data.lights.new(nombre, "AREA")
        d.energy, d.color, d.size = energia, color, tam
        o = bpy.data.objects.new(nombre, d)
        o.location = loc
        esc.collection.objects.link(o)
        c = o.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = objetivo, "TRACK_NEGATIVE_Z", "UP_Y"
        temporales.append(o)

    luz("Principal", 650, (1.0, 0.9, 0.8), (2.5, -3.0, 2.8), 2.0)
    luz("Relleno", 200, (0.75, 0.85, 1.0), (-3.0, -2.0, 1.8), 3.0)
    luz("Contra", 450, (1.0, 1.0, 1.0), (0.0, 3.0, 2.5), 1.5)
    mundo = bpy.data.worlds.new("MundoVista")
    mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
    esc.world = mundo
    cam_d = bpy.data.cameras.new("CamVista")
    cam_d.lens = 50
    cam = bpy.data.objects.new("CamVista", cam_d)
    d = altura * 2.6
    cam.location = (centro.x + d * math.sin(math.radians(25)), centro.y - d * math.cos(math.radians(25)),
                    mins.z + altura * 0.6)
    esc.collection.objects.link(cam)
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = objetivo, "TRACK_NEGATIVE_Z", "UP_Y"
    esc.camera = cam
    temporales.append(cam)
    r = esc.render
    r.engine = "CYCLES"
    info = comun.configurar_gpu_cycles()
    esc.cycles.samples = 64
    info.update(comun.configurar_denoiser(esc, info["backend"]))
    r.resolution_x, r.resolution_y, r.resolution_percentage = 720, 1280, 100
    r.image_settings.file_format = "PNG"
    r.filepath = ruta
    comun.color_cinematico(esc)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    info["segundos_render"] = round(time.time() - t0, 2)
    for o in temporales:
        bpy.data.objects.remove(o, do_unlink=True)
    return info


def cmd_personaje(a) -> None:
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    nuevos = importar_fbx(a.fbx)
    rig = next(o for o in nuevos if o.type == "ARMATURE")
    rig.name = f"{a.nombre}_rig"
    mallas = [o for o in nuevos if o.type == "MESH"]
    # Pose de reposo (sin la acción de 1–2 cuadros que trae el FBX) para medir y guardar limpio.
    if rig.animation_data:
        accion = rig.animation_data.action
        rig.animation_data.action = None
        if accion:
            bpy.data.actions.remove(accion)
    for pb in rig.pose.bones:
        pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
        pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    mins, maxs = caja_evaluada(mallas)
    altura_original = maxs.z - mins.z
    if a.altura > 0 and altura_original > 0:
        f = a.altura / altura_original
        rig.scale = rig.scale * f
        bpy.context.view_layer.update()
        mins, maxs = caja_evaluada(mallas)
        rig.location.z -= mins.z  # pies en el piso
        bpy.context.view_layer.update()
        mins, maxs = caja_evaluada(mallas)

    mejoras = {}
    for o in mallas:
        for mat in o.data.materials:
            if not mat or not mat.use_nodes:
                continue
            nombre = o.name.lower()
            base = {"body": "Body", "tops": "Top", "bottoms": "Bottom", "shoes": "Shoes", "hair": "Hair",
                    "eyelashes": "Eyelash", "eyes": "Eye"}.get(nombre, o.name)
            prefijo = next((img.name.rsplit("_", 1)[0] for img in bpy.data.images if f"_{base}_" in img.name), None)
            mejoras[o.name] = mejorar_material(mat, prefijo or base, es_piel=nombre == "body",
                                               transparente=nombre in ("hair", "eyelashes"))

    os.makedirs(a.carpeta, exist_ok=True)
    vista = vista_previa(mallas, rig, os.path.join(a.carpeta, "vista.png"))
    try:
        bpy.ops.file.pack_all()
    except RuntimeError:
        pass
    blend = os.path.join(a.carpeta, "personaje.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    info = {"nombre": a.nombre, "origen": "mixamo", "blend": blend, "vista": os.path.join(a.carpeta, "vista.png"),
            "rig": rig.name, "esqueleto": "mixamo", "huesos": len(rig.data.bones),
            "altura_original": round(altura_original, 3), "altura_m": round(maxs.z - mins.z, 3),
            "mallas": [o.name for o in mallas], "materiales_mejorados": mejoras, "render_vista": vista,
            "segundos": round(time.time() - t0, 1)}
    with open(os.path.join(a.carpeta, "personaje.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1, ensure_ascii=False)
    comun.resultado(info)


def cmd_animaciones(a) -> None:
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    indice = {}
    for ruta_indice in [x for x in (a.indice or "").split(",") if x and os.path.exists(x)]:
        with open(ruta_indice, encoding="utf-8") as f:  # varios índices: uno por tanda de descargas
            for e in json.load(f).get("animaciones", []):
                if e.get("estado") == "OK":
                    indice[e["archivo"]] = e
    correcciones = {}
    if a.correcciones and os.path.exists(a.correcciones):
        with open(a.correcciones, encoding="utf-8") as f:
            correcciones = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    catalogo, errores, omitidas = [], [], []
    for nombre in sorted(os.listdir(a.carpeta_fbx)):
        if not nombre.lower().endswith(".fbx"):
            continue
        if nombre in correcciones and correcciones[nombre] is None:
            omitidas.append(nombre)  # la búsqueda trajo otra animación: no se importa
            continue
        ruta = os.path.join(a.carpeta_fbx, nombre)
        try:
            nuevos = importar_fbx(ruta)
            rig = next(o for o in nuevos if o.type == "ARMATURE")
            accion = rig.animation_data.action
            datos = {**indice.get(nombre, {}), **(correcciones.get(nombre) or {})}
            clave = datos.get("nombre") or slug(os.path.splitext(nombre)[0])
            accion.name = clave
            accion.use_fake_user = True
            f0, f1 = (int(x) for x in accion.frame_range)
            # Desplazamiento de la cadera entre el primer y el último cuadro (≈ 0 en animaciones «in place»).
            esc = bpy.context.scene
            cad = rig.pose.bones["mixamorig:Hips"]
            esc.frame_set(f0)
            p0 = rig.matrix_world @ cad.head
            esc.frame_set(f1)
            p1 = rig.matrix_world @ cad.head
            catalogo.append({
                "clave": clave, "mixamo": os.path.splitext(nombre)[0], "archivo": nombre,
                "cuadros": f1 - f0 + 1, "segundos": round((f1 - f0 + 1) / 30, 2),
                "desplazamiento_m": [round(x, 3) for x in (p1 - p0)],
                "en_lugar": bool(datos.get("en_lugar")) or (p1 - p0).xy.length < 0.05,
                "busqueda": datos.get("busqueda"),
                "categoria": datos.get("categoria"),
                "interaccion": datos.get("interaccion"),
            })
            for o in nuevos:
                bpy.data.objects.remove(o, do_unlink=True)
        except Exception as e:  # una animación rota no detiene la importación
            errores.append({"archivo": nombre, "error": f"{type(e).__name__}: {e}"})
    for arm in list(bpy.data.armatures):
        if arm.users == 0:
            bpy.data.armatures.remove(arm)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=True)
    cat_ruta = os.path.splitext(a.salida)[0] + ".json"
    with open(cat_ruta, "w", encoding="utf-8") as f:
        json.dump({"biblioteca": a.salida, "animaciones": catalogo, "errores": errores}, f, indent=1,
                  ensure_ascii=False)
    comun.resultado({"ok": not errores, "animaciones": len(catalogo), "errores": errores, "omitidas": omitidas,
                     "catalogo": cat_ruta,
                     "blend": a.salida, "claves": [c["clave"] for c in catalogo],
                     "segundos": round(time.time() - t0, 1)})


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("personaje")
    pp.add_argument("--fbx", required=True)
    pp.add_argument("--nombre", required=True)
    pp.add_argument("--carpeta", required=True)
    pp.add_argument("--altura", type=float, default=1.75,
                    help="estatura real en metros (los FBX de Mixamo llegan con escala incorrecta; 0 = no tocar)")
    pa = sub.add_parser("animaciones")
    pa.add_argument("--carpeta_fbx", required=True)
    pa.add_argument("--salida", required=True)
    pa.add_argument("--indice", default="")
    pa.add_argument("--correcciones", default="")
    a = p.parse_args(comun.argumentos())
    {"personaje": cmd_personaje, "animaciones": cmd_animaciones}[a.cmd](a)


if __name__ == "__main__":
    main()
