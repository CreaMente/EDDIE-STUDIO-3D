"""Animación del cuerpo con Kimodo (NVIDIA): texto → movimiento de esqueleto → BVH.

Se ejecuta dentro del entorno «movimiento» (estudio/entornos.py). No genera imagen: produce rotaciones
de huesos (esqueleto SOMA de 77 articulaciones) que luego Blender adapta al personaje.

Subcomandos:
  preparar   Descarga Kimodo-SOMA-RP y su codificador de texto (LLM2Vec sobre Llama 3 8B). Quedan en Drive.
  generar    Una o varias acciones encadenadas (cada una ≤ 10 s) → <salida>/<nombre>.bvh (+ .npz, .json).
  convertir  NPZ de Kimodo (formato 30 o 77 articulaciones) → BVH. Útil con los ejemplos de Kimodo.

Requisito: acceso aceptado en Hugging Face a meta-llama/Meta-Llama-3-8B-Instruct (lo usa el codificador).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudio import config, modelos  # noqa: E402

os.environ.setdefault("HF_HUB_CACHE", str(config.ruta_local("cache", "hf")))
os.environ.setdefault("TEXT_ENCODER_MODE", "local")  # sin servidor de texto aparte

MODELO = "kimodo-soma-rp"  # alias de la última versión (SOMA-RP-v1.2)
REPOS = {
    "nvidia/Kimodo-SOMA-RP-v1.2": None,
    "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp": None,
    "McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised": None,
    # Pesos base del codificador de texto (repo restringido de Meta: hay que aceptar su licencia en HF).
    # Se excluye la carpeta original/ (copia duplicada de 16 GB en otro formato).
    "meta-llama/Meta-Llama-3-8B-Instruct": ["*.json", "*.safetensors", "tokenizer*"],
}
MAX_S_POR_ACCION = 10.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def resultado(d: dict) -> None:
    print("RESULTADO_JSON: " + json.dumps(d, ensure_ascii=False), flush=True)


def dispositivo() -> str:
    import torch

    return "cuda:0" if torch.cuda.is_available() else "cpu"


def preparar_modelos() -> None:
    for repo, permitir in REPOS.items():
        try:
            modelos.asegurar_cache_hf(repo, log, permitir)
        except Exception as e:
            if "meta-llama" in repo and ("gated" in str(e).lower() or "403" in str(e) or "401" in str(e)):
                raise SystemExit(
                    "No hay acceso a meta-llama/Meta-Llama-3-8B-Instruct. El propietario debe entrar con la "
                    "cuenta de su HF_TOKEN a https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct , "
                    "aceptar la licencia y esperar la aprobación (suele tardar minutos u horas).") from e
            raise


def guardar_bvh(ruta: Path, global_rot_mats, posed_joints, skeleton, fps: float) -> None:
    """Rotaciones globales + posiciones → BVH (esqueleto SOMA 77) en T-pose estándar.

    Si el movimiento viene en el formato de 30 articulaciones, se expande a 77 con la función de Kimodo."""
    import torch
    from kimodo.exports.bvh import save_motion_bvh
    from kimodo.skeleton import SOMASkeleton30, global_rots_to_local_rots

    dev = "cpu"
    skeleton = skeleton.to(dev)
    joints_pos = torch.as_tensor(posed_joints, dtype=torch.float32, device=dev)
    joints_rot = torch.as_tensor(global_rot_mats, dtype=torch.float32, device=dev)
    local = global_rots_to_local_rots(joints_rot, skeleton)
    raiz = joints_pos[:, skeleton.root_idx, :]
    if isinstance(skeleton, SOMASkeleton30):
        out77 = skeleton.output_to_SOMASkeleton77({"local_rot_mats": local, "root_positions": raiz})
        local, raiz = out77["local_rot_mats"], out77["root_positions"]
        skeleton = skeleton.somaskel77.to(dev)
    save_motion_bvh(ruta, local, raiz, skeleton=skeleton, fps=fps, standard_tpose=True)


def cmd_preparar(a) -> None:
    t0 = time.time()
    preparar_modelos()
    resultado({"ok": True, "modelo": MODELO, "segundos": round(time.time() - t0, 1), "dispositivo": dispositivo()})


def cmd_generar(a) -> None:
    import numpy as np
    from kimodo import load_model
    from kimodo.tools import seed_everything

    textos = json.loads(a.textos)
    duraciones = [float(d) for d in json.loads(a.duraciones)]
    if len(textos) != len(duraciones) or not textos:
        raise SystemExit("textos y duraciones deben tener el mismo número de elementos (≥ 1)")
    largas = [d for d in duraciones if d > MAX_S_POR_ACCION]
    if largas:
        raise SystemExit(f"Cada acción dura como máximo {MAX_S_POR_ACCION} s; divide las acciones largas.")

    preparar_modelos()
    t0 = time.time()
    dev = dispositivo()
    log(f"Cargando Kimodo en {dev}…")
    modelo, nombre_modelo = load_model(MODELO, device=dev, default_family="Kimodo", return_resolved_name=True)
    fps = float(modelo.fps)
    cuadros = [max(1, int(round(d * fps))) for d in duraciones]
    seed_everything(a.semilla)
    log(f"Generando {len(textos)} acción(es), {sum(cuadros)} cuadros…")
    t1 = time.time()
    salida = modelo(textos, cuadros, constraint_lst=[], num_denoising_steps=a.pasos, num_samples=1,
                    multi_prompt=True, post_processing=True, return_numpy=True)
    t2 = time.time()

    carpeta = Path(a.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    bvh = carpeta / f"{a.nombre}.bvh"
    guardar_bvh(bvh, salida["global_rot_mats"][0], salida["posed_joints"][0], modelo.skeleton, fps)
    np.savez_compressed(carpeta / f"{a.nombre}.npz", **{k: v[0] for k, v in salida.items()
                                                        if hasattr(v, "shape") and v.shape[:1] == (1,)})
    info = {
        "ok": True, "modelo": nombre_modelo, "bvh": str(bvh), "fps": fps,
        "cuadros": int(salida["posed_joints"].shape[1]), "duracion_s": round(salida["posed_joints"].shape[1] / fps, 2),
        "acciones": [{"texto": t, "segundos": d} for t, d in zip(textos, duraciones)],
        "semilla": a.semilla, "segundos_generacion": round(t2 - t1, 2), "segundos_total": round(time.time() - t0, 1),
        "dispositivo": dev,
    }
    (carpeta / f"{a.nombre}.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
    resultado(info)


def cmd_convertir(a) -> None:
    import numpy as np
    from kimodo.skeleton import SOMASkeleton30, SOMASkeleton77

    d = np.load(a.npz)
    n = d["posed_joints"].shape[-2]
    esqueleto = SOMASkeleton30() if n == 30 else SOMASkeleton77()
    guardar_bvh(Path(a.bvh), d["global_rot_mats"], d["posed_joints"], esqueleto, a.fps)
    resultado({"ok": True, "bvh": a.bvh, "articulaciones_origen": int(n), "cuadros": int(d["posed_joints"].shape[0])})


def main() -> None:
    p = argparse.ArgumentParser(prog="ia.movimiento")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar")
    g = sub.add_parser("generar")
    g.add_argument("--textos", required=True, help='lista JSON, p. ej. ["A person walks forward."]')
    g.add_argument("--duraciones", required=True, help="lista JSON de segundos por acción (≤ 10 cada una)")
    g.add_argument("--salida", required=True)
    g.add_argument("--nombre", default="movimiento")
    g.add_argument("--semilla", type=int, default=42)
    g.add_argument("--pasos", type=int, default=100)
    c = sub.add_parser("convertir")
    c.add_argument("--npz", required=True)
    c.add_argument("--bvh", required=True)
    c.add_argument("--fps", type=float, default=30.0)
    a = p.parse_args()
    {"preparar": cmd_preparar, "generar": cmd_generar, "convertir": cmd_convertir}[a.cmd](a)


if __name__ == "__main__":
    main()
