"""Monta una toma con un personaje ya animado y la renderiza a MP4 vertical.

Uso:
  blender -b --factory-startup -P escena_toma.py -- --animado animado.blend --salida toma.mp4 \
      --hdri estudio.hdr --piso '{"color": ".../color.jpg", "normal": "...", "rugosidad": "..."}' \
      [--motor EEVEE|CYCLES] [--muestras 64] [--escala 100] [--audio voz.wav] [--cuadros 1-120]
      [--carpeta_cuadros /content/eddie/cuadros/…] [--bloques 3]

Escena: iluminación HDRI (Poly Haven) + luz principal suave, piso con textura PBR, cámara de 35 mm que
sigue la cadera del personaje con un acercamiento lento (la cámara nunca se queda quieta) y desenfoque
de fondo. Render de cuadros PNG y codificación H.264 (con el audio si se pasa).

Velocidad: los cuadros se escriben en el disco local (no en Drive) y, con Cycles, el rango se reparte en
--bloques procesos de Blender en paralelo sobre la misma GPU (cada cuadro pequeño no la llena sola).
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
from mathutils import Euler, Vector

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


# Planos predefinidos (estilo de los videos de historias: gran angular cerca de la cara, contrapicados,
# cámara en mano). distancia en m al objetivo; altura_rel = altura de la cámara respecto al objetivo.
PLANOS = {
    "general":      {"objetivo": "cadera", "lente": 24, "distancia": 3.6, "altura_rel": 0.35, "acercamiento": 0.15,
                     "temblor": 0.4, "suavizado": 12},
    "medio":        {"objetivo": "pecho", "lente": 28, "distancia": 1.7, "altura_rel": 0.10, "acercamiento": 0.15,
                     "temblor": 0.5, "suavizado": 8},
    "primer_plano": {"objetivo": "cabeza", "lente": 24, "distancia": 0.85, "altura_rel": 0.0, "acercamiento": 0.12,
                     "temblor": 0.6, "suavizado": 5},
    "primerisimo":  {"objetivo": "cabeza", "lente": 16, "distancia": 0.45, "altura_rel": -0.04, "acercamiento": 0.10,
                     "temblor": 0.8, "inclinacion": 6, "suavizado": 4},
    "contrapicado": {"objetivo": "cabeza", "lente": 18, "distancia": 1.0, "altura_rel": -0.75, "acercamiento": 0.15,
                     "temblor": 0.6, "inclinacion": -5, "suavizado": 6},
    "picado":       {"objetivo": "cabeza", "lente": 24, "distancia": 1.5, "altura_rel": 0.95, "acercamiento": 0.15,
                     "temblor": 0.5, "suavizado": 6},
    "detalle_pies": {"objetivo": "pies", "lente": 35, "distancia": 0.9, "altura_rel": 0.15, "acercamiento": 0.2,
                     "temblor": 0.5, "suavizado": 6},
    "detalle_manos": {"objetivo": "manos", "lente": 35, "distancia": 0.7, "altura_rel": 0.10, "acercamiento": 0.2,
                      "temblor": 0.6, "suavizado": 5},
}

HUESOS_OBJETIVO = {
    "cadera": (["mixamorig:Hips"], ["DEF-Pelvis"], ["DEF-Hips"], ["Hips"]),
    "pecho": (["mixamorig:Spine2"], ["DEF-Chest"], ["DEF-Spine3"], ["DEF-RibCage"]),
    "cabeza": (["mixamorig:Head"], ["DEF-Head"], ["Head"]),
    "pies": (["mixamorig:LeftFoot", "mixamorig:RightFoot"], ["DEF-Foot.L", "DEF-Foot.R"]),
    "manos": (["mixamorig:LeftHand", "mixamorig:RightHand"], ["DEF-Hand.L", "DEF-Hand.R"],
              ["DEF-Wrist.L", "DEF-Wrist.R"]),
}


def huesos_objetivo(rig, objetivo: str) -> list:
    for grupo in HUESOS_OBJETIVO[objetivo]:
        if all(n in rig.pose.bones for n in grupo):
            return [rig.pose.bones[n] for n in grupo]
    raise SystemExit(f"No encuentro huesos para el objetivo «{objetivo}» en {rig.name}")


def trayectoria(rig, huesos: list, f_ini: int, f_fin: int) -> dict[int, Vector]:
    esc = bpy.context.scene
    pos = {}
    for f in range(f_ini, f_fin + 1):
        esc.frame_set(f)
        pos[f] = sum(((rig.matrix_world @ pb.head) for pb in huesos), Vector()) / len(huesos)
    return pos


def suavizar(pos: dict[int, Vector], ventana: int) -> dict[int, Vector]:
    claves = sorted(pos)
    salida = {}
    for i, f in enumerate(claves):
        vecinos = claves[max(0, i - ventana): i + ventana + 1]
        salida[f] = sum((pos[k] for k in vecinos), Vector()) / len(vecinos)
    return salida


def mirada(rig, hueso_ojos: str, cam, f_ini: int, f_fin: int, modo: str) -> str:
    """Dónde miran los ojos del personaje: «camara» (al espectador, como en los videos de historias) o
    «frente» (hacia donde camina). Se añade una restricción al control de mirada del rig que copia la
    posición de un objeto guía animado cuadro a cuadro (funciona sin importar cómo esté armado el rig)."""
    if not hueso_ojos or hueso_ojos not in rig.pose.bones or modo not in ("camara", "frente"):
        return "rig"
    esc = bpy.context.scene
    guia = bpy.data.objects.new("GuiaMirada", None)
    esc.collection.objects.link(guia)
    c = rig.pose.bones[hueso_ojos].constraints.new("COPY_LOCATION")
    c.target = guia
    cabeza = huesos_objetivo(rig, "cabeza")
    for f in range(f_ini, f_fin + 1):
        esc.frame_set(f)
        h = sum(((rig.matrix_world @ pb.head) for pb in cabeza), Vector()) / len(cabeza)
        h.z += 0.08  # a la altura de los ojos
        if modo == "camara":
            guia.location = cam.matrix_world.to_translation()
        else:
            adelante = rig.matrix_world.to_3x3() @ Vector((0, -1, 0))
            adelante.z = 0
            guia.location = h + adelante.normalized() * 1.5
        guia.keyframe_insert("location", frame=f)
    return modo


def camara_seguimiento(rig, f_ini: int, f_fin: int, conf: dict) -> bpy.types.Object:
    """Cámara que sigue al objetivo con un acercamiento suave, inclinación y temblor de mano.

    conf: plano (preset) + cualquiera de objetivo, lente, distancia, altura_rel o altura (absoluta),
    angulo (grados alrededor del personaje; 0 = de frente), acercamiento, inclinacion, temblor (grados),
    suavizado (cuadros), apertura (f-stop)."""
    from mathutils import noise

    c = dict(PLANOS.get(conf.get("plano", "general"), PLANOS["general"]))
    c.update({k: v for k, v in conf.items() if v is not None})
    esc = bpy.context.scene
    pos = suavizar(trayectoria(rig, huesos_objetivo(rig, c["objetivo"]), f_ini, f_fin), ventana=int(c["suavizado"]))
    foco = bpy.data.objects.new("ObjetivoCamara", None)
    esc.collection.objects.link(foco)
    cam_d = bpy.data.cameras.new("Camara")
    cam_d.lens = float(c["lente"])
    cam_d.clip_start = 0.02
    cam_d.dof.use_dof = True
    cam_d.dof.focus_object = foco
    cam_d.dof.aperture_fstop = float(c.get("apertura", 2.8 if c["distancia"] > 1.2 else 2.0))
    cam = bpy.data.objects.new("Camara", cam_d)
    cam.rotation_mode = "QUATERNION"
    esc.collection.objects.link(cam)
    esc.camera = cam
    total = max(1, f_fin - f_ini)
    ang = math.radians(float(c.get("angulo", 25)))
    semilla = float(c.get("semilla", 7.3))
    for f in range(f_ini, f_fin + 1):
        t = (f - f_ini) / total
        suave = t * t * (3 - 2 * t)  # el acercamiento arranca y termina suave
        d = float(c["distancia"]) * (1 - float(c["acercamiento"]) * suave)
        o = pos[f]
        z = float(conf["altura"]) if "altura" in conf else o.z + float(c["altura_rel"])
        foco.location = o
        foco.keyframe_insert("location", frame=f)
        cam.location = (o.x + d * math.sin(ang), o.y - d * math.cos(ang), z)
        cam.keyframe_insert("location", frame=f)
        mira = (o - Vector(cam.location)).to_track_quat("-Z", "Y")
        # Inclinación (plano holandés) + temblor de cámara en mano (ruido suave, no aleatorio por cuadro).
        tiempo = f / 30.0
        temblor = math.radians(float(c.get("temblor", 0)))
        rx = temblor * noise.noise(Vector((tiempo * 0.9, semilla, 0.0)))
        ry = temblor * noise.noise(Vector((semilla, tiempo * 0.9, 1.7)))
        rz = math.radians(float(c.get("inclinacion", 0))) + 0.5 * temblor * noise.noise(Vector((2.1, semilla, tiempo)))
        local = Euler((rx, ry, rz), "XYZ").to_quaternion()
        cam.rotation_quaternion = mira @ local
        cam.keyframe_insert("rotation_quaternion", frame=f)
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
    p.add_argument("--camara", default='{"plano": "general"}',
                   help='JSON: {"plano": "primerisimo", "angulo": 20, "lente": 16, ...} (ver PLANOS)')
    p.add_argument("--hdri_rotacion", type=float, default=0)
    p.add_argument("--carpeta_cuadros", default="", help="dónde escribir los PNG (mejor disco local)")
    p.add_argument("--bloques", type=int, default=1, help="procesos de render en paralelo (solo Cycles)")
    p.add_argument("--look", type=float, default=1.0, help="fuerza del acabado de cámara (0 = sin look)")
    p.add_argument("--ojos", default="", help="control de mirada del rig (elenco), p. ej. TGT-Eyes")
    a = p.parse_args(comun.argumentos())
    t0 = time.time()

    bpy.ops.wm.open_mainfile(filepath=a.animado)
    esc = bpy.context.scene
    rig = max((o for o in esc.objects if o.type == "ARMATURE"), key=lambda o: len(o.data.bones))
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

    conf_cam = json.loads(a.camara or "{}")
    cam = camara_seguimiento(rig, f_ini, f_fin, conf_cam)
    modo_mirada = mirada(rig, a.ojos, cam, f_ini, f_fin, conf_cam.get("mirada", "camara"))

    r = esc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, a.escala
    r.fps = 30
    info = {"motor": a.motor, "cuadros": f_fin - f_ini + 1, "mirada": modo_mirada,
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
    r.use_persistent_data = True  # no reconstruye la escena en la GPU en cada cuadro
    comun.color_cinematico(esc)
    info.update(comun.aplicar_look(esc, a.look))

    carpeta = a.carpeta_cuadros or (os.path.splitext(a.salida)[0] + "_cuadros")
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta)
    os.makedirs(carpeta)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    r.image_settings.file_format = "PNG"
    r.filepath = os.path.join(carpeta, "")
    t1 = time.time()
    n = f_fin - f_ini + 1
    bloques = max(1, min(a.bloques, n // 15)) if a.motor == "CYCLES" else 1
    if bloques > 1:
        info["bloques"] = render_en_bloques(carpeta, f_ini, f_fin, bloques)
    else:
        bpy.ops.render.render(animation=True)
    t2 = time.time()

    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-start_number", str(f_ini),
           "-i", os.path.join(carpeta, "%04d.png")]
    if a.audio and os.path.exists(a.audio):
        cmd += ["-i", a.audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            a.salida]
    subprocess.run(cmd, check=True)
    info.update({"salida": a.salida, "carpeta_cuadros": carpeta, "segundos_render": round(t2 - t1, 1),
                 "segundos_por_cuadro": round((t2 - t1) / n, 2), "segundos_total": round(time.time() - t0, 1),
                 "con_audio": bool(a.audio and os.path.exists(a.audio))})
    comun.resultado(info)


def render_en_bloques(carpeta: str, f_ini: int, f_fin: int, bloques: int) -> list[dict]:
    """Guarda la escena preparada y la renderiza con N procesos de Blender en paralelo (rangos contiguos)."""
    escena = os.path.join(carpeta, "_escena.blend")
    bpy.ops.wm.save_as_mainfile(filepath=escena, copy=True)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_bloque.py")
    n = f_fin - f_ini + 1
    cortes = [f_ini + round(n * k / bloques) for k in range(bloques + 1)]
    procesos = []
    for k in range(bloques):
        ini, fin = cortes[k], cortes[k + 1] - 1
        registro = open(os.path.join(carpeta, f"_bloque_{k}.log"), "w")
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", escena, "-P", script, "--",
               "--ini", str(ini), "--fin", str(fin)]
        procesos.append((subprocess.Popen(cmd, stdout=registro, stderr=subprocess.STDOUT), registro, ini, fin))
    print(f"[bloques] {bloques} procesos: " + ", ".join(f"{i}-{f}" for _, _, i, f in procesos), flush=True)
    hechos, fallas = [], []
    for proc, registro, ini, fin in procesos:
        proc.wait()
        registro.close()
        texto = open(registro.name, errors="replace").read()
        linea = next((l for l in texto.splitlines() if l.startswith("RESULTADO_JSON: ")), None)
        if proc.returncode != 0 or not linea:
            fallas.append(f"bloque {ini}-{fin} (código {proc.returncode}):\n" + "\n".join(texto.splitlines()[-25:]))
        else:
            r = json.loads(linea[len("RESULTADO_JSON: "):])
            hechos.append({"cuadros": f"{ini}-{fin}", "segundos": r.get("segundos"), "backend": r.get("backend")})
    if fallas:
        raise SystemExit("Falló el render por bloques:\n" + "\n\n".join(fallas))
    os.remove(escena)
    return hechos


if __name__ == "__main__":
    main()
