"""Montaje del video final: tomas alineadas a la voz, texto en pantalla, música y sonoridad a -14 LUFS.

  python -m estudio.montaje --proyecto <id> --plan '[{"toma": "t01", "frase": 0},
                                                    {"toma": "t02", "frase": 2, "desde_s": 1.5},
                                                    {"toma": "t03", "palabra": 41}]'
      [--textos '[{"texto": "DÍA 3", "frase": 4}]'] [--musica ruta.wav] [--musica_db -20]
      [--fundido 0] [--nombre final] [--escala 100]

Cada elemento del plan dice qué toma (proyectos/<id>/tomas/<nombre>/toma.mp4) entra y desde dónde:
  "frase": n        empieza cuando empieza la frase n de la narración (frases.json)
  "palabra": i      empieza en la palabra i (palabras.json), para cortes a mitad de frase
  "inicio_s": t     empieza en el segundo t
  "desde_s": s      (opcional) qué segundo de la toma se muestra primero (por defecto 0)
La primera toma empieza en 0 y cada toma dura hasta que empieza la siguiente; la última, hasta la
última palabra + --cola. El corte cae --adelanto segundos antes de la palabra (se siente más natural).
Si una toma es más corta que su tramo, se congela su último cuadro y se avisa en el reporte.

Textos: {"texto": "DÍA 3", "frase": n} dura toda la frase n; también "palabra"/"inicio_s" + "segundos".

Resultado: proyectos/<id>/video/<nombre>.mp4 (copia en entregas/) + reporte con LUFS y pico real.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import blender, config
from .tomas import correr, log, slug

FPS = 30
# El AAC sube el pico real ~0.6 dB al codificar (medido en Colab: -1.50 → -0.93 dBTP), así que la mezcla
# se deja en -2.0 dBTP para que el MP4 final quede por debajo de -1.
PICO_OBJETIVO = -2.0


def duracion_medio(ruta: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(ruta)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def medir_sonoridad(ruta: Path, filtro_previo: str = "") -> dict:
    """Mide con el filtro loudnorm de ffmpeg: sonoridad integrada (LUFS), pico real (dBTP) y rango."""
    filtro = (filtro_previo + "," if filtro_previo else "") + f"loudnorm=I=-14:TP={PICO_OBJETIVO}:LRA=11:print_format=json"
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-af", filtro, "-f", "null", "-"],
                         capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out.stderr, re.S)
    if not m:
        raise RuntimeError("No pude medir la sonoridad:\n" + out.stderr[-1500:])
    return json.loads(m.group(0))


def tiempo_de(item: dict, frases: list, palabras: list, que: str) -> float | None:
    if "frase" in item:
        n = int(item["frase"])
        if not 0 <= n < len(frases):
            raise SystemExit(f"{que}: la frase {n} no existe (hay {len(frases)}: 0–{len(frases) - 1}).")
        return float(frases[n]["inicio"])
    if "palabra" in item:
        i = int(item["palabra"])
        if not 0 <= i < len(palabras):
            raise SystemExit(f"{que}: la palabra {i} no existe (hay {len(palabras)}).")
        return float(palabras[i]["inicio"])
    if "inicio_s" in item:
        return float(item["inicio_s"])
    return None


def mezclar_audio(voz: Path, musica: str, musica_db: float, duracion: float, salida: Path) -> dict:
    """Voz (+ música atenuada que baja sola cuando habla el narrador) → -14 LUFS, pico ≤ -2 dBTP.

    Normalización en dos pasadas: primero se mide y luego se corrige en modo lineal (no deforma la voz)."""
    entradas = ["-i", str(voz)]
    if musica:
        entradas += ["-stream_loop", "-1", "-i", musica]
        grafo = (f"[0:a]aresample=48000,apad,atrim=0:{duracion:.3f},asplit=2[v][vc];"
                 f"[1:a]aresample=48000,atrim=0:{duracion:.3f},volume={musica_db}dB,"
                 f"afade=t=out:st={max(0.0, duracion - 1.0):.3f}:d=1[m];"
                 f"[m][vc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];"
                 f"[v][md]amix=inputs=2:duration=first:normalize=0[mez]")
    else:
        grafo = f"[0:a]aresample=48000,apad,atrim=0:{duracion:.3f}[mez]"
    previa = salida.with_name("mezcla_previa.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", grafo, "-map", "[mez]",
                    "-ac", "2", "-c:a", "pcm_s24le", str(previa)], check=True)
    m = medir_sonoridad(previa)
    filtro = (f"loudnorm=I=-14:TP={PICO_OBJETIVO}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
              "linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(previa), "-af", filtro + ",aresample=48000",
                    "-c:a", "pcm_s24le", str(salida)], check=True)
    previa.unlink(missing_ok=True)
    return m


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.montaje")
    p.add_argument("--proyecto", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--textos", default="[]")
    p.add_argument("--musica", default="")
    p.add_argument("--musica_db", type=float, default=-20.0)
    p.add_argument("--fundido", type=int, default=0, help="cuadros de fundido entre tomas (0 = corte)")
    p.add_argument("--nombre", default="final")
    p.add_argument("--escala", type=int, default=100)
    p.add_argument("--adelanto", type=float, default=0.07)
    p.add_argument("--cola", type=float, default=0.35)
    p.add_argument("--fuente", default="")
    a = p.parse_args()
    t0 = time.time()
    if not config.drive_disponible():
        raise SystemExit(config.AVISO_DRIVE)

    proyecto = Path(a.proyecto) if Path(a.proyecto).is_absolute() else config.ruta_drive("proyectos", a.proyecto)
    dvoz = proyecto / "voz"
    if not (dvoz / "voz.wav").exists():
        raise SystemExit(f"Falta {dvoz / 'voz.wav'}: genera la voz primero (voz_generar).")
    frases = json.loads((dvoz / "frases.json").read_text(encoding="utf-8"))
    palabras = json.loads((dvoz / "palabras.json").read_text(encoding="utf-8"))
    fin_voz = float(palabras[-1]["fin"]) if palabras else duracion_medio(dvoz / "voz.wav")
    duracion = round(fin_voz + a.cola, 3)
    total = int(round(duracion * FPS))

    plan = json.loads(a.plan)
    if not plan:
        raise SystemExit("El plan está vacío.")
    # Bordes de cada toma en cuadros (contiguos, sin huecos ni solapes).
    inicios = []
    for k, item in enumerate(plan):
        t = 0.0 if k == 0 else tiempo_de(item, frases, palabras, f"toma {k} ({item.get('toma')})")
        if t is None:
            raise SystemExit(f"Toma {k} ({item.get('toma')}): indica «frase», «palabra» o «inicio_s».")
        inicios.append(0 if k == 0 else int(round(max(0.0, t - a.adelanto) * FPS)))
    bordes = inicios + [total]
    for k in range(len(plan)):
        if bordes[k + 1] - bordes[k] < 6:
            raise SystemExit(f"La toma {k} ({plan[k].get('toma')}) dura menos de 0.2 s o está fuera de orden: "
                             "revisa que las frases/palabras del plan vayan en orden creciente.")

    tmp = config.ruta_local("cuadros", proyecto.name, f"montaje_{slug(a.nombre)}")
    tmp.mkdir(parents=True, exist_ok=True)
    clips, avisos, detalle = [], [], []
    for k, item in enumerate(plan):
        ruta = Path(item["toma"])
        mp4 = ruta if ruta.suffix == ".mp4" else proyecto / "tomas" / slug(item["toma"]) / "toma.mp4"
        if not mp4.exists():
            raise SystemExit(f"No existe la toma «{item['toma']}» ({mp4}). Créala con toma_crear.")
        cuadros = bordes[k + 1] - bordes[k]
        desde = int(round(float(item.get("desde_s", 0)) * FPS))
        disponibles = int(duracion_medio(mp4) * FPS) - desde - 1
        if disponibles < 1:
            raise SystemExit(f"Toma {k}: desde_s={item.get('desde_s')} supera la duración de {mp4.name}.")
        clip = {"mp4": str(mp4), "inicio": bordes[k] + 1, "duracion": min(cuadros, disponibles), "desde": desde}
        if disponibles < cuadros:
            png = tmp / f"ultimo_{k:02d}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.1", "-i", str(mp4), "-frames:v", "1",
                            "-update", "1", str(png)], check=True)
            clip["congelar"] = {"png": str(png), "duracion": cuadros - disponibles}
            avisos.append(f"La toma {k} ({item['toma']}) es {(cuadros - disponibles) / FPS:.2f} s más corta que su "
                          "tramo: se congeló su último cuadro. Mejor: renderízala más larga.")
        clips.append(clip)
        detalle.append({"toma": item["toma"], "inicio_s": round(bordes[k] / FPS, 2),
                        "fin_s": round(bordes[k + 1] / FPS, 2), "segundos": round(cuadros / FPS, 2),
                        "congelado_s": round(clip.get("congelar", {}).get("duracion", 0) / FPS, 2)})

    fundidos = []
    if a.fundido > 0:
        for k in range(1, len(clips)):
            n = min(a.fundido, clips[k]["duracion"] // 2, clips[k - 1]["duracion"] // 2)
            if n >= 2 and not clips[k - 1].get("congelar"):
                # La toma anterior se alarga n cuadros por debajo de la siguiente para poder fundir.
                extra = int(duracion_medio(Path(clips[k - 1]["mp4"])) * FPS) - clips[k - 1]["desde"] - 1 \
                    - clips[k - 1]["duracion"]
                if extra >= n:
                    clips[k - 1]["duracion"] += n
                    fundidos.append({"entre": [k - 1, k], "cuadros": n})

    textos = []
    for t in json.loads(a.textos):
        ini = tiempo_de(t, frases, palabras, f"texto «{t.get('texto')}»")
        if ini is None:
            raise SystemExit(f"Texto «{t.get('texto')}»: indica «frase», «palabra» o «inicio_s».")
        if "segundos" in t:
            fin = ini + float(t["segundos"])
        elif "frase" in t:
            fin = float(frases[int(t["frase"])]["fin"])
        else:
            fin = ini + 2.0
        i0, i1 = int(round(ini * FPS)) + 1, int(round(fin * FPS)) + 1
        textos.append({"texto": t["texto"], "inicio": i0, "duracion": max(6, min(i1, total + 1) - i0),
                       **{k: t[k] for k in ("tamano", "altura") if k in t}})

    plan_blender = {"cuadros_total": total, "escala": a.escala, "clips": clips, "fundidos": fundidos,
                    "textos": textos, "fuente": a.fuente}
    ruta_plan = tmp / "plan.json"
    ruta_plan.write_text(json.dumps(plan_blender, indent=1, ensure_ascii=False), encoding="utf-8")
    carpeta_png = tmp / "cuadros"
    r_vse = correr(blender.comando(blender.script("montaje.py"), ["--plan", str(ruta_plan),
                                                                  "--cuadros", str(carpeta_png)]),
                   f"montaje en Blender ({len(clips)} tomas, {total} cuadros)")

    log("▶ audio: mezcla y sonoridad")
    audio = tmp / "mezcla.wav"
    musica = a.musica
    if musica and not Path(musica).is_absolute():
        musica = str(config.ruta_drive(musica))
    if musica and not Path(musica).exists():
        raise SystemExit(f"No existe la música {musica}")
    medida_previa = mezclar_audio(dvoz / "voz.wav", musica, a.musica_db, duracion, audio)

    destino = proyecto / "video" / f"{slug(a.nombre)}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    local_mp4 = tmp / "final.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", "1",
                    "-i", str(carpeta_png / "%04d.png"), "-i", str(audio),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart",
                    str(local_mp4)], check=True)
    medida = medir_sonoridad(local_mp4)
    if float(medida["input_tp"]) > -1.1:
        # Segunda pasada solo del audio: se baja lo justo para que el pico real quede en -1.2 dBTP.
        ganancia = -1.2 - float(medida["input_tp"])
        log(f"▶ pico real {medida['input_tp']} dBTP tras el AAC: ajuste de {ganancia:.2f} dB")
        corregido = tmp / "final_corregido.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(local_mp4), "-i", str(audio), "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-af", f"volume={ganancia:.2f}dB", "-c:a", "aac",
                        "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(corregido)],
                       check=True)
        corregido.replace(local_mp4)
        medida = medir_sonoridad(local_mp4)
    shutil.copyfile(local_mp4, destino)
    entrega = config.ruta_drive("entregas", f"{proyecto.name}_{slug(a.nombre)}.mp4")
    entrega.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_mp4, entrega)

    creditos = proyecto / "CREDITOS.txt"
    if musica:
        lineas = set(creditos.read_text(encoding="utf-8").splitlines()) if creditos.exists() else set()
        lineas.add(f"Música: {Path(musica).name} (revisa su licencia y crédito en la biblioteca).")
        creditos.write_text("\n".join(sorted(lineas)) + "\n", encoding="utf-8")

    lufs, pico = float(medida["input_i"]), float(medida["input_tp"])
    dur_final = duracion_medio(local_mp4)
    if not -15.0 <= lufs <= -13.0:
        avisos.append(f"Sonoridad final {lufs} LUFS (objetivo -14 ± 1).")
    if pico > -1.0:
        avisos.append(f"Pico real {pico} dBTP (máximo -1).")
    reporte = {"ok": True, "mp4": str(destino), "entrega": str(entrega), "duracion_s": round(dur_final, 2),
               "resolucion": f"{1080 * a.escala // 100}x{1920 * a.escala // 100}", "fps": FPS,
               "lufs": lufs, "pico_dbtp": pico, "lufs_antes": float(medida_previa["input_i"]),
               "tomas": detalle, "fundidos": len(fundidos), "textos": len(textos), "musica": bool(musica),
               "avisos": avisos, "cuadros_png": str(carpeta_png),
               "segundos_render_montaje": r_vse.get("segundos_render"), "segundos_total": round(time.time() - t0, 1)}
    (proyecto / "video" / f"{slug(a.nombre)}.json").write_text(json.dumps(reporte, indent=1, ensure_ascii=False),
                                                                encoding="utf-8")
    print("RESULTADO_JSON: " + json.dumps(reporte, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
