"""Utilidades compartidas por los scripts de Blender (se ejecutan dentro de Blender)."""

from __future__ import annotations

import json
import sys

import bpy


def argumentos() -> list[str]:
    """Argumentos después de '--' en la línea de comando de Blender."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def resultado(datos: dict) -> None:
    """Imprime un resultado legible por el sistema (una línea JSON con prefijo fijo)."""
    print("RESULTADO_JSON: " + json.dumps(datos, ensure_ascii=False), flush=True)


def configurar_gpu_cycles() -> dict:
    """Activa la mejor GPU disponible para Cycles: OPTIX → CUDA → HIP → ONEAPI → METAL → CPU.

    Devuelve lo que realmente quedó activo (no lo que se intentó)."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    elegido = None
    for tipo in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = tipo
        except TypeError:
            continue
        prefs.refresh_devices()
        gpus = [d for d in prefs.devices if d.type == tipo]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == tipo
            elegido = tipo
            break
    escena = bpy.context.scene
    if elegido:
        escena.cycles.device = "GPU"
        activos = [d.name for d in prefs.devices if d.use]
    else:
        prefs.compute_device_type = "NONE"
        escena.cycles.device = "CPU"
        activos = ["CPU"]
    return {"backend": elegido or "CPU", "dispositivos": activos}


RUTAS_NVOPTIX = ["/usr/share/nvidia/nvoptix.bin", "/usr/lib64-nvidia/nvoptix.bin",
                 "/usr/lib/x86_64-linux-gnu/nvidia/nvoptix.bin"]


def configurar_denoiser(escena, backend: str) -> dict:
    """Elige el eliminador de ruido que realmente funciona en esta máquina.

    El denoiser de OptiX necesita el archivo de pesos nvoptix.bin del driver; algunos contenedores
    (como Colab) traen la librería de OptiX para el trazado de rayos pero no ese archivo. En ese caso se
    usa OpenImageDenoise acelerado por la GPU (mismo resultado visual, probado en la RTX PRO 6000)."""
    import os

    escena.cycles.use_denoising = True
    nvoptix = next((r for r in RUTAS_NVOPTIX if os.path.exists(r)), None)
    if backend == "OPTIX" and nvoptix:
        escena.cycles.denoiser = "OPTIX"
    else:
        escena.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(escena.cycles, "denoising_use_gpu"):
        escena.cycles.denoising_use_gpu = backend != "CPU"
    return {
        "denoiser": escena.cycles.denoiser,
        "denoiser_en_gpu": getattr(escena.cycles, "denoising_use_gpu", None),
        "nvoptix_bin": nvoptix,
    }


def motor_eevee() -> str:
    """El identificador de EEVEE cambió entre versiones (BLENDER_EEVEE_NEXT en 4.2–4.5)."""
    ids = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    return "BLENDER_EEVEE" if "BLENDER_EEVEE" in ids else "BLENDER_EEVEE_NEXT"


def color_cinematico(escena, look: str = "AgX - Medium High Contrast") -> None:
    vs = escena.view_settings
    for transform in ("AgX", "Filmic"):
        try:
            vs.view_transform = transform
            break
        except TypeError:
            continue
    try:
        vs.look = look
    except TypeError:
        pass


def curvas_accion(accion) -> list:
    """F-curves de una acción, en Blender 4.x (accion.fcurves) y 5.x (acciones con «slots»)."""
    try:
        from bpy_extras import anim_utils

        if getattr(accion, "slots", None):
            bolsa = anim_utils.action_get_channelbag_for_slot(accion, accion.slots[0])
            if bolsa is not None:
                return list(bolsa.fcurves)
    except (ImportError, AttributeError):
        pass
    return list(getattr(accion, "fcurves", []))


def curvas_cuaternion(accion) -> dict:
    """{ruta del hueso: [fc_w, fc_x, fc_y, fc_z]} para cada hueso con las 4 curvas de rotation_quaternion."""
    grupos: dict = {}
    for fc in curvas_accion(accion):
        if fc.data_path.endswith(".rotation_quaternion") and 0 <= fc.array_index < 4:
            grupos.setdefault(fc.data_path, [None] * 4)[fc.array_index] = fc
    return {k: v for k, v in grupos.items() if all(v)}


def invertir_curvas(curvas, desde: int = 0) -> None:
    """Cambia q por -q (misma rotación) a partir de la clave «desde»."""
    for fc in curvas:
        for kp in list(fc.keyframe_points)[desde:]:
            kp.co[1] = -kp.co[1]
            kp.handle_left[1] = -kp.handle_left[1]
            kp.handle_right[1] = -kp.handle_right[1]
        fc.update()


def cuaterniones_continuos(accion) -> int:
    """Evita saltos q → -q entre claves seguidas (el NLA y la interpolación mezclan canal por canal,
    y un salto de signo hace girar el hueso 360°). Devuelve cuántas claves cambió de signo."""
    cambiadas = 0
    for curvas in curvas_cuaternion(accion).values():
        n = len(curvas[0].keyframe_points)
        if any(len(fc.keyframe_points) != n for fc in curvas):
            continue
        # Se leen todos los valores, se deciden los signos y se escribe una sola vez (fc.update() a mitad
        # del recorrido invalida las referencias a las claves).
        valores = [[kp.co[1] for kp in fc.keyframe_points] for fc in curvas]
        signos = [1.0] * n
        for j in range(1, n):
            punto = sum(signos[j - 1] * valores[k][j - 1] * valores[k][j] for k in range(4))
            signos[j] = 1.0 if punto >= 0 else -1.0
        if all(x > 0 for x in signos):
            continue
        for fc in curvas:
            for kp, sg in zip(fc.keyframe_points, signos):
                if sg < 0:
                    kp.co[1] = -kp.co[1]
                    kp.handle_left[1] = -kp.handle_left[1]
                    kp.handle_right[1] = -kp.handle_right[1]
            fc.update()
        cambiadas += sum(1 for x in signos if x < 0)
    return cambiadas


def evaluar_cuaternion(curvas, cuadro: float):
    return [fc.evaluate(cuadro) for fc in curvas]


def aplicar_look(escena, fuerza: float = 1.0) -> dict:
    """Acabado de cámara en el compositor de Blender (no es IA: es parte del render de Blender).

    Brillo suave en las luces fuertes (bloom), un toque de aberración cromática en los bordes y viñeta,
    como en los videos de referencia. Requiere Blender 5.x (compositor por grupos de nodos)."""
    if fuerza <= 0:
        return {"look": False}
    if not hasattr(escena, "compositing_node_group"):
        return {"look": False, "look_aviso": "compositor de Blender 4.x: look no aplicado"}
    g = bpy.data.node_groups.new("Look_EDDIE", "CompositorNodeTree")
    g.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    n = g.nodes
    capa = n.new("CompositorNodeRLayers")
    brillo = n.new("CompositorNodeGlare")
    brillo.inputs["Type"].default_value = "Bloom"
    brillo.inputs["Threshold"].default_value = 0.9
    brillo.inputs["Strength"].default_value = 0.18 * fuerza
    brillo.inputs["Size"].default_value = 0.6
    lente = n.new("CompositorNodeLensdist")
    lente.inputs["Dispersion"].default_value = 0.008 * fuerza
    lente.inputs["Fit"].default_value = True
    elipse = n.new("CompositorNodeEllipseMask")
    elipse.inputs["Size"].default_value = (0.92, 0.98)
    desenfoque = n.new("CompositorNodeBlur")
    desenfoque.inputs["Size"].default_value = (220.0, 220.0)
    rango = n.new("ShaderNodeMapRange")
    rango.inputs["To Min"].default_value = 1.0 - 0.28 * fuerza
    mezcla = n.new("ShaderNodeMix")
    mezcla.data_type = "RGBA"
    mezcla.blend_type = "MULTIPLY"
    mezcla.inputs["Factor"].default_value = 1.0
    salida = n.new("NodeGroupOutput")
    enl = g.links.new
    enl(capa.outputs["Image"], brillo.inputs["Image"])
    enl(brillo.outputs["Image"], lente.inputs["Image"])
    enl(elipse.outputs["Mask"], desenfoque.inputs["Image"])
    enl(desenfoque.outputs["Image"], rango.inputs["Value"])
    enl(lente.outputs["Image"], mezcla.inputs["A"])
    enl(rango.outputs["Result"], mezcla.inputs["B"])
    enl(mezcla.outputs["Result"], salida.inputs[0])
    escena.compositing_node_group = g
    return {"look": True, "look_fuerza": fuerza}
