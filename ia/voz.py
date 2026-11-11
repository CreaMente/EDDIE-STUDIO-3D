"""Voz del narrador con VoxCPM2 (local, GPU) + verificación y tiempos con Whisper (stable-ts).

Se ejecuta dentro del entorno «voz» (estudio/entornos.py). Subcomandos:

  preparar   Descarga VoxCPM2 y Whisper (quedan en Drive).
  narrador   Crea N voces candidatas a partir de una descripción (diseño de voz).
  generar    Narra el guion de un proyecto con la voz elegida:
             - divide en frases, genera varias tomas por frase con la voz de referencia,
             - transcribe cada toma con Whisper y se queda con la que dice exactamente el guion,
             - une las frases casi sin pausas (estilo His Story),
             - alinea el texto completo → tiempo de inicio y fin de cada palabra.

Cada subcomando termina con una línea `RESULTADO_JSON: {...}`.
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
from ia import texto as tx  # noqa: E402

REPO_VOXCPM = "openbmb/VoxCPM2"
SR_SALIDA = 48000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def resultado(d: dict) -> None:
    print("RESULTADO_JSON: " + json.dumps(d, ensure_ascii=False), flush=True)


def dispositivo() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def cargar_voxcpm():
    from voxcpm import VoxCPM

    ruta = modelos.asegurar(REPO_VOXCPM, log)
    dev = dispositivo()
    log(f"Cargando VoxCPM2 en {dev}…")
    if dev == "cuda":
        try:
            return VoxCPM.from_pretrained(str(ruta), load_denoiser=False, optimize=True, device=dev)
        except Exception as e:  # torch.compile puede no soportar una GPU o versión nueva
            log(f"⚠️  Optimización no disponible ({type(e).__name__}: {e}); cargo sin optimizar.")
    return VoxCPM.from_pretrained(str(ruta), load_denoiser=False, optimize=False, device=dev)


def generar(modelo, semilla: int, **kwargs):
    """Genera audio con una semilla fija (reproducible). La versión publicada de voxcpm no acepta `seed`,
    así que se fijan las semillas de torch, numpy y random antes de llamar."""
    import inspect
    import random

    import numpy as np
    import torch

    random.seed(semilla)
    np.random.seed(semilla % (2**32))
    torch.manual_seed(semilla)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(semilla)
    if "seed" in inspect.signature(modelo._generate).parameters:
        kwargs["seed"] = semilla
    return modelo.generate(**kwargs)


def cargar_whisper(nombre: str):
    import stable_whisper

    raiz = modelos.archivo_whisper(nombre, log)
    log(f"Cargando Whisper {nombre}…")
    m = stable_whisper.load_model(nombre, device=dispositivo(), download_root=str(raiz))
    modelos.guardar_whisper(nombre, log)
    return m


def recortar(wav, sr: int, margen_s: float = 0.04):
    """Quita silencio al inicio y al final de una toma, dejando un margen pequeño."""
    import librosa
    import numpy as np

    _, (ini, fin) = librosa.effects.trim(wav, top_db=38)
    m = int(margen_s * sr)
    return np.asarray(wav[max(0, ini - m): min(len(wav), fin + m)], dtype="float32")


def a_48k(wav, sr: int):
    import librosa

    return wav if sr == SR_SALIDA else librosa.resample(wav, orig_sr=sr, target_sr=SR_SALIDA)


def cambiar_velocidad(wav, factor: float):
    """Acelera (factor > 1) o frena el audio SIN cambiar el tono de la voz (ffmpeg rubberband o atempo).
    Es procesamiento de audio, no generación con IA."""
    import subprocess
    import tempfile

    import soundfile as sf

    if abs(factor - 1.0) < 1e-3:
        return wav
    filtros = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    filtro = (f"rubberband=tempo={factor}:pitchq=quality" if " rubberband " in filtros
              else f"atempo={factor}")
    with tempfile.TemporaryDirectory() as d:
        ent, sal = f"{d}/ent.wav", f"{d}/sal.wav"
        sf.write(ent, wav, SR_SALIDA, subtype="FLOAT")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ent, "-filter:a", filtro, "-ar", str(SR_SALIDA),
                        "-c:a", "pcm_f32le", sal], check=True)
        nuevo, _ = sf.read(sal, dtype="float32")
    log(f"Velocidad ×{factor} aplicada ({filtro.split('=')[0]}).")
    return nuevo


def transcribir(whisper, wav_path: str) -> str:
    r = whisper.transcribe(wav_path, language="es", verbose=None, regroup=False)
    return (getattr(r, "text", None) or r.get("text", "")).strip()


# ───────────────────────── subcomandos ─────────────────────────

def cmd_preparar(a) -> None:
    t0 = time.time()
    modelos.asegurar(REPO_VOXCPM, log)
    cargar_whisper(a.whisper)
    resultado({"ok": True, "voxcpm": REPO_VOXCPM, "whisper": a.whisper, "segundos": round(time.time() - t0, 1),
               "dispositivo": dispositivo()})


def cmd_narrador(a) -> None:
    import soundfile as sf

    modelo = cargar_voxcpm()
    sr = modelo.tts_model.sample_rate
    whisper = cargar_whisper(a.whisper)
    carpeta = config.ruta_drive("voces", a.nombre)
    cand = carpeta / "candidatos"
    cand.mkdir(parents=True, exist_ok=True)
    texto = tx.numeros_a_palabras(a.texto)
    salidas = []
    for i in range(1, a.candidatos + 1):
        mejor = None
        # La pronunciación varía mucho entre semillas: se verifica cada intento con Whisper y se repite
        # hasta que diga la frase correctamente (o se agoten los intentos).
        for intento in range(1, a.intentos + 1):
            semilla = 1000 * i + intento
            # El espacio tras la descripción evita que el modelo pegue la descripción a la primera palabra.
            wav = generar(modelo, semilla, text=f"({a.descripcion}) {texto}", cfg_value=a.cfg,
                          inference_timesteps=a.pasos)
            wav = a_48k(recortar(wav, sr), sr)
            tmp = cand / f".prueba_{i}.wav"
            sf.write(tmp, wav, SR_SALIDA, subtype="PCM_24")
            error = tx.cer(texto, transcribir(whisper, str(tmp)))
            log(f"Candidata {i}/{a.candidatos}, intento {intento}: error {error:.1%}")
            if mejor is None or error < mejor[0]:
                mejor = (error, wav, semilla)
            tmp.unlink(missing_ok=True)
            if error <= a.cer_max:
                break
        error, wav, semilla = mejor
        ruta = cand / f"candidata_{i}.wav"
        sf.write(ruta, wav, SR_SALIDA, subtype="PCM_24")
        salidas.append({"candidata": i, "archivo": str(ruta), "segundos": round(len(wav) / SR_SALIDA, 2),
                        "cer": round(error, 4), "semilla": semilla, "aprobada": error <= a.cer_max})
    (carpeta / "narrador.json").write_text(json.dumps({
        "nombre": a.nombre, "descripcion": a.descripcion, "texto": texto, "candidatos": salidas,
        "elegida": None}, indent=2, ensure_ascii=False), encoding="utf-8")
    resultado({"ok": all(c["aprobada"] for c in salidas), "narrador": a.nombre, "candidatos": salidas,
               "siguiente_paso": "El propietario escucha las candidatas en Drive (voces/<nombre>/candidatos) "
                                 "y se elige una con voz_elegir_narrador."})


def cmd_generar(a) -> None:
    import numpy as np
    import soundfile as sf

    t0 = time.time()
    proyecto = Path(a.proyecto)
    guion = (proyecto / "guion.txt").read_text(encoding="utf-8")
    carpeta_voz = config.ruta_drive("voces", a.narrador)
    ref_wav, ref_txt = carpeta_voz / "referencia.wav", carpeta_voz / "referencia.txt"
    if not ref_wav.exists():
        raise SystemExit(f"El narrador «{a.narrador}» no tiene voz elegida. Usa voz_crear_narrador y "
                         "voz_elegir_narrador primero.")
    prompt_text = ref_txt.read_text(encoding="utf-8").strip()
    frases = tx.dividir_frases(tx.numeros_a_palabras(guion))
    if not frases:
        raise SystemExit("guion.txt está vacío")
    log(f"{len(frases)} frases, {sum(len(f.split()) for f in frases)} palabras.")

    salida = proyecto / "voz"
    (salida / "tomas").mkdir(parents=True, exist_ok=True)
    modelo = cargar_voxcpm()
    sr = modelo.tts_model.sample_rate
    whisper = cargar_whisper(a.whisper)

    elegidas, reporte_frases = [], []
    for n, frase in enumerate(frases):
        mejores = []
        intentos = 0
        while intentos < a.max_tomas:
            intentos += 1
            semilla = a.semilla + n * 100 + intentos
            wav = generar(modelo, semilla, text=frase, prompt_wav_path=str(ref_wav), prompt_text=prompt_text,
                          reference_wav_path=str(ref_wav), cfg_value=a.cfg, inference_timesteps=a.pasos)
            wav = a_48k(recortar(wav, sr), sr)
            ruta = salida / "tomas" / f"f{n:03d}_t{intentos}.wav"
            sf.write(ruta, wav, SR_SALIDA, subtype="PCM_24")
            oido = transcribir(whisper, str(ruta))
            error = tx.cer(frase, oido)
            dur = len(wav) / SR_SALIDA
            ritmo = len(frase.split()) / max(dur, 0.1)
            mejores.append({"toma": intentos, "archivo": str(ruta), "cer": round(error, 4), "oido": oido,
                            "segundos": round(dur, 2), "palabras_por_s": round(ritmo, 2), "_wav": wav})
            log(f"Frase {n + 1}/{len(frases)} toma {intentos}: error {error:.1%}, {ritmo:.1f} pal/s")
            if intentos >= a.tomas and min(m["cer"] for m in mejores) <= a.cer_max:
                break
            if error <= a.cer_excelente:
                break
        mejor = min(mejores, key=lambda m: (m["cer"], abs(m["palabras_por_s"] - 3.0)))
        elegidas.append(mejor["_wav"])
        reporte_frases.append({
            "frase": n, "texto": frase, "toma_elegida": mejor["toma"], "cer": mejor["cer"],
            "oido": mejor["oido"], "aprobada": mejor["cer"] <= a.cer_max,
            "tomas": [{k: v for k, v in m.items() if k != "_wav"} for m in mejores],
        })

    # Unión casi sin pausas (el estilo de referencia casi no tiene silencios).
    pausa = np.zeros(int(a.pausa * SR_SALIDA), dtype="float32")
    partes, tiempos_frases, t = [], [], 0.0
    for n, w in enumerate(elegidas):
        if n:
            partes.append(pausa)
            t += len(pausa) / SR_SALIDA
        tiempos_frases.append({"frase": n, "inicio": round(t, 3), "fin": round(t + len(w) / SR_SALIDA, 3)})
        partes.append(w)
        t += len(w) / SR_SALIDA
    voz = np.concatenate(partes)
    if abs(a.velocidad - 1.0) >= 1e-3:
        voz = cambiar_velocidad(voz, a.velocidad)
        for tf in tiempos_frases:  # los tiempos se escalan igual que el audio
            tf["inicio"] = round(tf["inicio"] / a.velocidad, 3)
            tf["fin"] = round(tf["fin"] / a.velocidad, 3)
    pico = float(np.max(np.abs(voz))) or 1.0
    voz = (voz / pico * 0.89).astype("float32")  # pico a -1 dBFS; la sonoridad final se ajusta en el montaje
    ruta_voz = salida / "voz.wav"
    sf.write(ruta_voz, voz, SR_SALIDA, subtype="PCM_24")

    log("Alineando cada palabra con el audio…")
    texto_completo = " ".join(frases)
    alin = whisper.align(str(ruta_voz), texto_completo, language="es")
    palabras = []
    for seg in alin.segments:
        for w in seg.words:
            p = w.word.strip()
            if not p:
                continue
            frase_idx = next((f["frase"] for f in tiempos_frases if f["inicio"] - 0.05 <= w.start <= f["fin"] + 0.05),
                             None)
            palabras.append({"i": len(palabras), "palabra": p, "inicio": round(w.start, 3),
                             "fin": round(w.end, 3), "frase": frase_idx})
    (salida / "palabras.json").write_text(json.dumps(palabras, indent=1, ensure_ascii=False), encoding="utf-8")
    (salida / "frases.json").write_text(json.dumps(
        [{**tf, "texto": frases[tf["frase"]]} for tf in tiempos_frases], indent=1, ensure_ascii=False),
        encoding="utf-8")

    duracion = len(voz) / SR_SALIDA
    n_pal = len(texto_completo.split())
    reprobadas = [r["frase"] for r in reporte_frases if not r["aprobada"]]
    reporte = {
        "ok": not reprobadas,
        "narrador": a.narrador,
        "velocidad": a.velocidad,
        "duracion_s": round(duracion, 2),
        "frases": len(frases),
        "palabras": n_pal,
        "palabras_por_s": round(n_pal / duracion, 2),
        "palabras_alineadas": len(palabras),
        "cer_promedio": round(sum(r["cer"] for r in reporte_frases) / len(reporte_frases), 4),
        "frases_con_error": reprobadas,
        "archivos": {"voz": str(ruta_voz), "palabras": str(salida / "palabras.json"),
                     "frases": str(salida / "frases.json"), "reporte": str(salida / "reporte.json")},
        "segundos_proceso": round(time.time() - t0, 1),
        "dispositivo": dispositivo(),
        "detalle": reporte_frases,
    }
    (salida / "reporte.json").write_text(json.dumps(reporte, indent=1, ensure_ascii=False), encoding="utf-8")
    resultado({k: v for k, v in reporte.items() if k != "detalle"})


def main() -> None:
    p = argparse.ArgumentParser(prog="ia.voz")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preparar")
    pp.add_argument("--whisper", default="large-v3")

    pn = sub.add_parser("narrador")
    pn.add_argument("--nombre", required=True)
    pn.add_argument("--descripcion", required=True)
    pn.add_argument("--texto", required=True)
    pn.add_argument("--candidatos", type=int, default=3)
    pn.add_argument("--cfg", type=float, default=2.0)
    pn.add_argument("--pasos", type=int, default=10)
    pn.add_argument("--intentos", type=int, default=5, help="intentos por candidata hasta pronunciar bien")
    pn.add_argument("--cer-max", type=float, default=0.05)
    pn.add_argument("--whisper", default="large-v3")

    pg = sub.add_parser("generar")
    pg.add_argument("--proyecto", required=True)
    pg.add_argument("--narrador", required=True)
    pg.add_argument("--tomas", type=int, default=3, help="tomas mínimas por frase si ninguna es excelente")
    pg.add_argument("--max-tomas", type=int, default=6)
    pg.add_argument("--cer-max", type=float, default=0.08, help="error máximo aceptable por frase")
    pg.add_argument("--cer-excelente", type=float, default=0.02, help="si una toma llega aquí, se acepta ya")
    pg.add_argument("--pausa", type=float, default=0.10, help="segundos entre frases")
    pg.add_argument("--whisper", default="large-v3")
    pg.add_argument("--velocidad", type=float, default=1.0,
                    help="acelera (>1) o frena (<1) la narración final sin cambiar el tono (0.8–1.3)")
    pg.add_argument("--cfg", type=float, default=2.0)
    pg.add_argument("--pasos", type=int, default=10)
    pg.add_argument("--semilla", type=int, default=42)

    a = p.parse_args()
    {"preparar": cmd_preparar, "narrador": cmd_narrador, "generar": cmd_generar}[a.cmd](a)


if __name__ == "__main__":
    main()
