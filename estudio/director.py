"""Director: de un guion técnico (storyboard) al video final, en un solo trabajo.

  python -m estudio.director --proyecto <id> --guion guion_tecnico.json [--calidad borrador|final] [--forzar]

El guion técnico dice, para cada toma, qué pasa (personaje, acciones, objetos, escenario, plano,
expresión) y cuándo entra según la narración. El director:
  1. calcula cuánto debe durar cada toma (de su frase/palabra hasta que entra la siguiente, + margen);
  2. renderiza cada toma (toma_crear) alargando la última pose si la acción es más corta, y con los
     labios sincronizados desde el segundo exacto en que entra la toma;
  3. monta el video (subtítulos, textos, música, -14 LUFS).
Para iterar rápido: una toma cuyo guion y calidad no cambiaron NO se vuelve a renderizar (--forzar lo
obliga). Así se puede corregir una toma y volver a producir solo esa.

Formato del guion técnico (JSON):
{
  "personaje": "rain",                 ← protagonista por defecto
  "escenario": "habitacion",           ← escenario por defecto (nombre o {"tipo": …})
  "tomas": [
    {"nombre": "t01", "frase": 0,       ← entra cuando empieza la frase 0 («palabra»: i / «inicio_s»: t)
     "secuencia": [{"anim": "caminar", "segundos": 2, "avance": true}, {"anim": "abrir_puerta"}],
     "camara": {"plano": "general", "angulo": 110, "movimiento": "lateral"},
     "expresion": "miedo", "habla": false,
     "desde_s": 0.9},                   ← (opcional) salta el inicio de la acción: la toma entra ya en movimiento
    …
  ],
  "textos": [{"texto": "DÍA 3", "frase": 4}], "musica": "", "fundido": 0
}
Cualquier campo de toma_crear vale por toma (personaje, escenario, objetos, hdri, expresion, intensidad…).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from . import config
from .montaje import tiempo_de
from .tomas import log, slug

PERFILES = {"borrador": (25, 16), "previa": (50, 32), "final": (100, 128)}
MARGEN_S = 0.35


def correr_modulo(modulo: str, args: list[str], etiqueta: str) -> dict:
    log(f"▶ {etiqueta}")
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", modulo, *args], capture_output=True, text=True)
    salida = proc.stdout + proc.stderr
    for linea in salida.splitlines():
        if linea.startswith("[") and "▶" in linea or "✔" in linea:
            print("   " + linea[:200], flush=True)
    linea = next((x for x in reversed(salida.splitlines()) if x.startswith("RESULTADO_JSON: ")), None)
    if proc.returncode != 0 or not linea:
        raise RuntimeError(f"Falló «{etiqueta}»:\n" + "\n".join(salida.splitlines()[-40:]))
    log(f"✔ {etiqueta} ({time.time() - t0:.0f} s)")
    return json.loads(linea[len("RESULTADO_JSON: "):])


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.director")
    p.add_argument("--proyecto", required=True)
    p.add_argument("--guion", required=True, help="ruta a un JSON o el JSON mismo")
    p.add_argument("--calidad", default="borrador", choices=list(PERFILES))
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--solo", default="", help="nombres de tomas a rehacer, separados por coma")
    p.add_argument("--nombre_video", default="")
    a = p.parse_args()
    t0 = time.time()
    if not config.drive_disponible():
        raise SystemExit(config.AVISO_DRIVE)
    proyecto = Path(a.proyecto) if Path(a.proyecto).is_absolute() else config.ruta_drive("proyectos", a.proyecto)
    guion = json.loads(Path(a.guion).read_text(encoding="utf-8") if not a.guion.strip().startswith("{") else a.guion)
    (proyecto / "guion_tecnico.json").write_text(json.dumps(guion, indent=1, ensure_ascii=False), encoding="utf-8")
    voz = proyecto / "voz"
    if not (voz / "palabras.json").exists():
        raise SystemExit("Primero genera la voz del proyecto (voz_generar): las tomas se miden con ella.")
    frases = json.loads((voz / "frases.json").read_text(encoding="utf-8"))
    palabras = json.loads((voz / "palabras.json").read_text(encoding="utf-8"))
    fin_voz = float(palabras[-1]["fin"]) + MARGEN_S

    tomas = guion.get("tomas", [])
    if not tomas:
        raise SystemExit("El guion técnico no tiene tomas.")
    inicios = []
    for k, t in enumerate(tomas):
        ini = 0.0 if k == 0 else tiempo_de(t, frases, palabras, f"toma {t.get('nombre', k)}")
        if ini is None:
            raise SystemExit(f"Toma {t.get('nombre', k)}: indica «frase», «palabra» o «inicio_s».")
        inicios.append(ini)
    if any(b <= a_ for a_, b in zip(inicios, inicios[1:])):
        raise SystemExit("Las tomas deben ir en orden de tiempo (cada una empieza después de la anterior).")
    escala, muestras = PERFILES[a.calidad]
    solo = {x.strip() for x in a.solo.split(",") if x.strip()}
    reporte_tomas = []

    for k, t in enumerate(tomas):
        nombre = slug(t.get("nombre") or f"t{k + 1:02d}")
        fin = inicios[k + 1] if k + 1 < len(tomas) else fin_voz
        duracion = round(fin - inicios[k] + float(t.get("desde_s", 0)) + MARGEN_S, 2)
        desde_voz = max(0.0, inicios[k] - 0.07)  # como el corte del montaje
        personaje = t.get("personaje", guion.get("personaje", "remy"))
        escenario = t.get("escenario", guion.get("escenario", "estudio"))
        args = ["toma", "--proyecto", str(proyecto), "--nombre", nombre, "--personaje", personaje,
                "--secuencia", json.dumps(t["secuencia"], ensure_ascii=False), "--motor", "CYCLES",
                "--muestras", str(muestras), "--escala", str(escala), "--duracion_min", str(duracion),
                "--escenario", json.dumps(escenario, ensure_ascii=False) if isinstance(escenario, dict) else escenario,
                "--camara", json.dumps(t.get("camara", {"plano": "medio"})),
                "--expresion", t.get("expresion", "neutral"), "--intensidad", str(t.get("intensidad", 1.0)),
                "--objetos", json.dumps(t.get("objetos", []), ensure_ascii=False),
                "--bloques", str(t.get("bloques", 3))]
        if t.get("habla"):
            args += ["--habla", "1", "--voz_desde", str(desde_voz)]
        if t.get("hdri"):
            args += ["--hdri", t["hdri"]]
        huella = hashlib.sha1(json.dumps([args, t], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        carpeta = proyecto / "tomas" / nombre
        previa = carpeta / "huella.txt"
        mp4 = carpeta / "toma.mp4"
        rehacer = a.forzar or (solo and nombre in solo) or not mp4.exists() or \
            not previa.exists() or previa.read_text().strip() != huella
        if solo and nombre not in solo and mp4.exists():
            rehacer = False
        if not rehacer:
            log(f"= toma {nombre}: sin cambios, se reutiliza")
            reporte_tomas.append({"toma": nombre, "reutilizada": True, "segundos": duracion})
            continue
        r = correr_modulo("estudio.tomas", args, f"toma {nombre} ({personaje}, {duracion:.1f} s)")
        carpeta.mkdir(parents=True, exist_ok=True)
        previa.write_text(huella, encoding="utf-8")
        reporte_tomas.append({"toma": nombre, "segundos": duracion, "segundos_proceso": r.get("segundos_total"),
                              "render": r.get("render", {})})

    plan = []
    for k, t in enumerate(tomas):
        e = {"toma": slug(t.get("nombre") or f"t{k + 1:02d}")}
        for clave in ("frase", "palabra", "inicio_s", "desde_s"):
            if clave in t:
                e[clave] = t[clave]
        if k and len(e) == 1:
            e["inicio_s"] = inicios[k]
        plan.append(e)
    args_m = ["--proyecto", str(proyecto), "--plan", json.dumps(plan, ensure_ascii=False),
              "--textos", json.dumps(guion.get("textos", []), ensure_ascii=False),
              "--fundido", str(int(guion.get("fundido", 0))), "--escala", str(escala),
              "--nombre", a.nombre_video or a.calidad,
              "--subtitulos", "0" if guion.get("subtitulos") is False else "1"]
    if guion.get("musica"):
        args_m += ["--musica", guion["musica"], "--musica_db", str(guion.get("musica_db", -20))]
    montaje = correr_modulo("estudio.montaje", args_m, "montaje del video")
    reporte = {"ok": True, "video": montaje.get("mp4"), "entrega": montaje.get("entrega"),
               "duracion_s": montaje.get("duracion_s"), "lufs": montaje.get("lufs"),
               "pico_dbtp": montaje.get("pico_dbtp"), "avisos": montaje.get("avisos"), "tomas": reporte_tomas,
               "segundos_total": round(time.time() - t0, 1)}
    (proyecto / "video" / "director.json").write_text(json.dumps(reporte, indent=1, ensure_ascii=False),
                                                      encoding="utf-8")
    print("RESULTADO_JSON: " + json.dumps(reporte, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
