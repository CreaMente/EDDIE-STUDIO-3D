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
