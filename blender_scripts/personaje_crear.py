"""Crea un personaje humano con MPFB y lo guarda en la biblioteca, con una foto de revisión.

Uso (dentro de Blender sin interfaz):
  blender -b --factory-startup -P personaje_crear.py -- --nombre carlos --genero 1 --edad 32 \
      --peso 0.5 --musculo 0.55 --altura 0.55 --etnia latina --piel auto --pelo auto \
      --ropa shirt,pants,shoes --carpeta <biblioteca/personajes/carlos>

Resultado en la carpeta: personaje.blend (texturas empaquetadas), vista.png y personaje.json.
El esqueleto es el «mixamo» de MPFB (nombres mixamorig:*), compatible con la adaptación de Kimodo.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import sys
import time

import addon_utils
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def mpfb(modulo: str, clave: str):
    """Las extensiones de Blender viven en un paquete de nombre variable (bl_ext.<repo>.mpfb)."""
    for nombre in list(sys.modules):
        if nombre.endswith(modulo):
            return getattr(importlib.import_module(nombre), clave)
    raise ImportError(f"No encuentro {modulo}: ¿está instalada y activada la extensión MPFB?")


def activar_mpfb() -> None:
    for mod in addon_utils.modules():
        if mod.__name__.endswith(".mpfb"):
            addon_utils.enable(mod.__name__, default_set=True, persistent=True)
            return
    raise RuntimeError("La extensión MPFB no está instalada (usa personaje_preparar).")


def edad_a_valor(anios: float) -> float:
    """Años → valor del control de edad de MakeHuman (0 = 1 año, 0.1875 = 11, 0.5 = 25, 1 = 90)."""
    a = max(1.0, min(90.0, anios))
    if a < 11:
        return (a - 1) / 10 * 0.1875
    if a < 25:
        return 0.1875 + (a - 11) / 14 * (0.5 - 0.1875)
    return 0.5 + (a - 25) / 65 * 0.5


ETNIAS = {
    "latina": {"african": 0.15, "asian": 0.25, "caucasian": 0.60},
    "caucasica": {"african": 0.0, "asian": 0.0, "caucasian": 1.0},
    "africana": {"african": 1.0, "asian": 0.0, "caucasian": 0.0},
    "asiatica": {"african": 0.0, "asian": 1.0, "caucasian": 0.0},
    "mixta": {"african": 0.33, "asian": 0.33, "caucasian": 0.34},
}


def buscar(AssetService, subdir: str, deseo: str, preferidos: list[str]) -> str | None:
    """Encuentra un recurso por fragmento de nombre; con 'auto' usa la primera opción preferida que exista."""
    disponibles = [str(p) for p in AssetService.list_mhclo_assets(subdir)] if subdir != "skins" else \
        [str(p) for p in AssetService.list_mhmat_assets("skins")]
    if not disponibles:
        return None
    candidatos = preferidos if deseo in ("", "auto") else [deseo]
    for c in candidatos:
        for d in disponibles:
            if c.lower() in os.path.basename(d).lower() or c.lower() in d.lower():
                return d
    return disponibles[0] if deseo in ("", "auto") else None


def vista_previa(geo, ruta: str) -> dict:
    esc = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    piso = bpy.context.object
    m = bpy.data.materials.new("PisoVista")
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.33, 0.36, 1)
    piso.data.materials.append(m)
    altura = max((geo.matrix_world @ v.co).z for v in geo.data.vertices)

    def luz(nombre, energia, color, loc, tam):
        d = bpy.data.lights.new(nombre, "AREA")
        d.energy, d.color, d.size = energia, color, tam
        o = bpy.data.objects.new(nombre, d)
        o.location = loc
        esc.collection.objects.link(o)
        c = o.constraints.new("TRACK_TO")
        c.target = geo
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"

    luz("Principal", 600, (1.0, 0.9, 0.8), (2.5, -3.0, 2.8), 2.0)
    luz("Relleno", 180, (0.75, 0.85, 1.0), (-3.0, -2.0, 1.8), 3.0)
    luz("Contra", 400, (1.0, 1.0, 1.0), (0.0, 3.0, 2.5), 1.5)
    mundo = bpy.data.worlds.new("MundoVista")
    mundo.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
    esc.world = mundo

    objetivo = bpy.data.objects.new("ObjetivoCam", None)
    objetivo.location = (0, 0, altura * 0.55)
    esc.collection.objects.link(objetivo)
    cam_d = bpy.data.cameras.new("CamVista")
    cam_d.lens = 50
    cam = bpy.data.objects.new("CamVista", cam_d)
    distancia = altura * 2.6
    cam.location = (distancia * math.sin(math.radians(25)), -distancia * math.cos(math.radians(25)), altura * 0.6)
    esc.collection.objects.link(cam)
    c = cam.constraints.new("TRACK_TO")
    c.target = objetivo
    c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    esc.camera = cam

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
    for o in (piso, cam, objetivo):
        bpy.data.objects.remove(o, do_unlink=True)
    for o in [o for o in esc.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    return info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--nombre", required=True)
    p.add_argument("--genero", type=float, default=1.0, help="0 = mujer, 1 = hombre")
    p.add_argument("--edad", type=float, default=30)
    p.add_argument("--peso", type=float, default=0.5)
    p.add_argument("--musculo", type=float, default=0.5)
    p.add_argument("--altura", type=float, default=0.5)
    p.add_argument("--etnia", default="latina", choices=list(ETNIAS))
    p.add_argument("--piel", default="auto")
    p.add_argument("--pelo", default="auto", help="fragmento del nombre del pelo, 'auto' o 'ninguno'")
    p.add_argument("--ropa", default="auto", help="fragmentos separados por coma, 'auto' o 'ninguna'")
    p.add_argument("--carpeta", required=True)
    a = p.parse_args(comun.argumentos())

    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    activar_mpfb()
    HumanService = mpfb("mpfb.services.humanservice", "HumanService")
    TargetService = mpfb("mpfb.services.targetservice", "TargetService")
    AssetService = mpfb("mpfb.services.assetservice", "AssetService")
    AssetService.update_all_asset_lists()

    md = TargetService.get_default_macro_info_dict()
    md["gender"] = max(0.0, min(1.0, a.genero))
    md["age"] = edad_a_valor(a.edad)
    md["weight"] = max(0.0, min(1.0, a.peso))
    md["muscle"] = max(0.0, min(1.0, a.musculo))
    md["height"] = max(0.0, min(1.0, a.altura))
    md["race"] = dict(ETNIAS[a.etnia])

    geo = HumanService.create_human(macro_detail_dict=md)
    geo.name = f"{a.nombre}_cuerpo"
    rig = HumanService.add_builtin_rig(geo, "mixamo")
    rig.name = f"{a.nombre}_rig"

    usados, faltan = {}, []
    hombre = a.genero >= 0.5
    piel_pref = ["young_caucasian_male" if hombre else "young_caucasian_female",
                 "middleage_caucasian_male" if hombre else "middleage_caucasian_female", "default"]
    if a.etnia == "africana":
        piel_pref.insert(0, "young_african_male" if hombre else "young_african_female")
    if a.etnia == "asiatica":
        piel_pref.insert(0, "young_asian_male" if hombre else "young_asian_female")
    piel = buscar(AssetService, "skins", a.piel, piel_pref)
    if piel:
        HumanService.set_character_skin(piel, geo, skin_type="ENHANCED_SSS")
        usados["piel"] = os.path.basename(piel)
    else:
        # Sin paquetes de pieles: material procedural por capas de MPFB (no necesita archivos externos).
        HumanService.set_character_skin(None, geo, skin_type="LAYERED")
        usados["piel"] = "procedural (LAYERED)"
        faltan.append("piel (paquete skins01 no instalado)")

    partes = [("eyes", "auto", ["high-poly", "low-poly"], "Eyes"),
              ("eyebrows", "auto", ["eyebrow001"], "Eyebrows"),
              ("eyelashes", "auto", ["eyelashes01"], "Eyelashes"),
              ("teeth", "auto", ["teeth_base"], "Teeth"),
              ("tongue", "auto", ["tongue01"], "Tongue")]
    if a.pelo != "ninguno":
        partes.append(("hair", a.pelo, ["short02", "short04", "short01"] if hombre else ["long01", "ponytail01", "bob01"],
                       "Hair"))
    if a.ropa != "ninguna":
        frags = ["shirt", "pants", "shoes"] if a.ropa == "auto" else [f.strip() for f in a.ropa.split(",") if f.strip()]
        for f in frags:
            partes.append(("clothes", f, [f], "Clothes"))
    for subdir, deseo, pref, tipo in partes:
        ruta = buscar(AssetService, subdir, deseo if tipo != "Clothes" else "auto", pref)
        if not ruta:
            faltan.append(f"{subdir}:{deseo}")
            continue
        try:
            HumanService.add_mhclo_asset(ruta, geo, asset_type=tipo, subdiv_levels=1)
            usados.setdefault(subdir, []).append(os.path.basename(ruta))
        except Exception as e:  # un recurso roto no debe impedir crear el personaje
            faltan.append(f"{subdir}:{os.path.basename(ruta)} ({type(e).__name__}: {e})")

    os.makedirs(a.carpeta, exist_ok=True)
    vista = vista_previa(geo, os.path.join(a.carpeta, "vista.png"))
    try:
        bpy.ops.file.pack_all()
    except RuntimeError:
        pass
    blend = os.path.join(a.carpeta, "personaje.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)

    altura_m = max((geo.matrix_world @ v.co).z for v in geo.data.vertices)
    disponibles = {s: sorted(os.path.basename(str(x)) for x in AssetService.list_mhclo_assets(s))
                   for s in ("hair", "clothes", "eyebrows")}
    disponibles["skins"] = sorted(os.path.basename(str(x)) for x in AssetService.list_mhmat_assets("skins"))
    info = {
        "nombre": a.nombre, "blend": blend, "vista": os.path.join(a.carpeta, "vista.png"),
        "rig": rig.name, "esqueleto": "mixamo", "huesos": len(rig.data.bones), "altura_m": round(altura_m, 3),
        "parametros": {"genero": a.genero, "edad": a.edad, "peso": a.peso, "musculo": a.musculo,
                       "altura": a.altura, "etnia": a.etnia},
        "recursos": usados, "faltan": faltan, "render_vista": vista,
        "segundos": round(time.time() - t0, 1),
    }
    with open(os.path.join(a.carpeta, "personaje.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=1, ensure_ascii=False)
    info["disponibles"] = disponibles
    comun.resultado(info)


if __name__ == "__main__":
    main()
