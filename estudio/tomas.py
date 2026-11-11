"""Orquestador de tomas: biblioteca Mixamo, animación (Mixamo + Kimodo) y render a MP4.

  python -m estudio.tomas mixamo
      Importa a la biblioteca todo lo nuevo de <DRIVE>/biblioteca/_entrada/mixamo/{personajes,animaciones}.

  python -m estudio.tomas toma --proyecto <id> --nombre t01 --personaje remy \
      --secuencia '[{"anim": "caminar_herido", "segundos": 4, "avance": true},
                    {"kimodo": "A person holds their left knee in pain and limps.", "segundos": 5},
                    {"anim": "herido_reposo", "segundos": 3}]'
      [--motor EEVEE|CYCLES] [--muestras 64] [--escala 100] [--hdri brown_photostudio_02]
      [--piso laminate_floor_02] [--audio voz.wav] [--camara '{"angulo": 25, "distancia": 4.2}']

Elementos de la secuencia:
  {"anim": clave}            animación de la biblioteca Mixamo (ver biblioteca_listar)
  {"kimodo": "texto en inglés", "segundos": n}   acción generada con Kimodo (≤ 10 s)
  {"kimodo": ["acción simple 1", "acción simple 2"], "segundos": [2, 3]}   varias acciones encadenadas
  {"bvh": ruta, "segundos": n}                    movimiento BVH ya existente (SOMA)
  + opcionales: "segundos", "avance" (m/s o true), "giro" (grados), "mezcla" (cuadros de fundido de entrada)

Resultado en <DRIVE>/proyectos/<id>/tomas/<nombre>/: toma.mp4, animado.blend, reporte.json.
Cada paso imprime su progreso; al final una línea RESULTADO_JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from . import blender, config, elenco, entornos, polyhaven


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def correr(cmd: list[str], etiqueta: str) -> dict:
    """Ejecuta un paso, muestra su salida importante y devuelve su RESULTADO_JSON."""
    log(f"▶ {etiqueta}")
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    resultado, cola = None, []
    for linea in proc.stdout:
        linea = linea.rstrip()
        cola = (cola + [linea])[-40:]
        if linea.startswith("RESULTADO_JSON: "):
            resultado = json.loads(linea[len("RESULTADO_JSON: "):])
        elif linea.startswith("[") or "Error" in linea or "Traceback" in linea:
            print("   " + linea[:300], flush=True)
    proc.wait()
    if proc.returncode != 0 or resultado is None:
        raise RuntimeError(f"Falló «{etiqueta}» (código {proc.returncode}). Últimas líneas:\n" + "\n".join(cola))
    log(f"✔ {etiqueta} ({time.time() - t0:.0f} s)")
    return resultado


def ruta_personaje(nombre: str) -> Path:
    return config.ruta_drive("biblioteca", "personajes", slug(nombre), "personaje.blend")


def biblioteca_mixamo() -> Path:
    return config.ruta_drive("biblioteca", "animaciones", "mixamo.blend")


# ───────────────────────── importación Mixamo ─────────────────────────

def cmd_mixamo(a) -> None:
    entrada = config.ruta_drive("biblioteca", "_entrada", "mixamo")
    script = blender.script("mixamo_importar.py")
    hechos = {"personajes": [], "animaciones": None}
    for fbx in sorted((entrada / "personajes").glob("*.fbx")):
        destino = ruta_personaje(fbx.stem)
        if destino.exists() and not a.forzar:
            continue
        r = correr(blender.comando(script, ["personaje", "--fbx", str(fbx), "--nombre", slug(fbx.stem),
                                            "--carpeta", str(destino.parent), "--altura", str(a.altura)]),
                   f"personaje {fbx.stem}")
        hechos["personajes"].append({"nombre": r["nombre"], "vista": r["vista"], "altura_m": r["altura_m"]})
    anims = entrada / "animaciones"
    fbxs = sorted(anims.glob("*.fbx"))
    blend = biblioteca_mixamo()
    if fbxs and (a.forzar or not blend.exists() or max(f.stat().st_mtime for f in fbxs) > blend.stat().st_mtime):
        indice = anims / "mixamo_indice.json"
        r = correr(blender.comando(script, ["animaciones", "--carpeta_fbx", str(anims), "--salida", str(blend),
                                            "--indice", str(indice) if indice.exists() else ""]),
                   f"{len(fbxs)} animaciones")
        hechos["animaciones"] = {"total": r["animaciones"], "errores": r["errores"], "claves": r["claves"]}
    print("RESULTADO_JSON: " + json.dumps({"ok": True, **hechos}, ensure_ascii=False), flush=True)


# ───────────────────────── toma completa ─────────────────────────

def acciones_kimodo(item: dict) -> tuple[list[str], list[float]]:
    """{"kimodo": "texto" | ["acción 1", "acción 2", …], "segundos": n | [n1, n2, …]} → textos y duraciones.

    Kimodo sigue mucho mejor varias acciones simples encadenadas (multi-prompt) que una frase con «then…»."""
    textos = item["kimodo"] if isinstance(item["kimodo"], list) else [item["kimodo"]]
    seg = item.get("segundos", 3.0 * len(textos))
    duraciones = [float(x) for x in seg] if isinstance(seg, list) else [float(seg) / len(textos)] * len(textos)
    if len(duraciones) != len(textos):
        raise SystemExit(f"Kimodo: {len(textos)} acciones pero {len(duraciones)} duraciones en «segundos».")
    if any(d > 10.0 or d < 0.5 for d in duraciones):
        raise SystemExit("Kimodo: cada acción debe durar entre 0.5 y 10 s; divide las largas en acciones más simples.")
    return [str(t) for t in textos], duraciones


def cmd_toma(a) -> None:
    t0 = time.time()
    proyecto = Path(a.proyecto) if os.path.isabs(a.proyecto) else config.ruta_drive("proyectos", a.proyecto)
    carpeta = proyecto / "tomas" / slug(a.nombre)
    carpeta.mkdir(parents=True, exist_ok=True)
    # Personaje del elenco (Blender Studio, con cara): el movimiento se arma sobre el esqueleto Mixamo
    # de la biblioteca y después se transfiere a su rig.
    ficha = elenco.ficha(a.personaje)
    personaje = ruta_personaje(a.esqueleto if ficha else a.personaje)
    if not personaje.exists():
        raise SystemExit(f"No existe el personaje «{a.esqueleto if ficha else a.personaje}» en la biblioteca "
                         f"({personaje}). Usa mixamo_importar o biblioteca_listar.")
    secuencia = json.loads(a.secuencia)
    bibliotecas = [str(biblioteca_mixamo())]
    pasos = {}

    # 1. Acciones generadas con Kimodo (o BVH dados) → adaptadas al personaje → acciones con nombre.
    for i, item in enumerate(secuencia):
        if "kimodo" in item or "bvh" in item:
            nombre_acc = f"kimodo_{i:02d}"
            bvh = item.get("bvh")
            if "kimodo" in item:
                entornos.asegurar("movimiento", log)
                textos, duraciones = acciones_kimodo(item)
                r = correr(entornos.comando("movimiento", "ia.movimiento", "generar",
                                            "--textos", json.dumps(textos),
                                            "--duraciones", json.dumps(duraciones),
                                            "--salida", str(carpeta / "kimodo"), "--nombre", nombre_acc,
                                            "--semilla", str(item.get("semilla", 42))),
                           f"Kimodo: «{' → '.join(textos)[:80]}»")
                bvh = r["bvh"]
                pasos[nombre_acc] = r
            blend_acc = carpeta / "kimodo" / f"{nombre_acc}.blend"
            correr(blender.comando(blender.script("animar_personaje.py"),
                                   ["--personaje", str(personaje), "--bvh", str(bvh), "--salida", str(blend_acc),
                                    "--accion", nombre_acc]),
                   f"adaptar movimiento {nombre_acc} al personaje")
            bibliotecas.append(str(blend_acc))
            item = {k: v for k, v in item.items() if k not in ("kimodo", "bvh", "semilla", "segundos")}
            item["anim"] = nombre_acc  # se usa completa: su duración ya es la pedida
            secuencia[i] = item

    # 2. Encadenar animaciones.
    animado = carpeta / "animado.blend"
    pasos["animacion"] = correr(blender.comando(blender.script("animar_mixamo.py"),
                                                ["--personaje", str(personaje), "--biblioteca", ",".join(bibliotecas),
                                                 "--secuencia", json.dumps(secuencia), "--salida", str(animado),
                                                 "--mezcla", str(a.mezcla)]),
                                "encadenar animaciones")

    # 2b. Elenco: transferir al rig del personaje y animar su cara (labios, expresión, parpadeo).
    if ficha:
        blend_elenco = elenco.preparar(a.personaje, log)
        ruta_ficha = elenco.FICHAS / f"{ficha['nombre']}.json"
        transferido = carpeta / f"animado_{ficha['nombre']}.blend"
        pasos["transferencia"] = correr(blender.comando(blender.script("transferir_personaje.py"),
                                                        ["--fuente", str(animado), "--personaje", str(blend_elenco),
                                                         "--ficha", str(ruta_ficha), "--salida", str(transferido)]),
                                        f"pasar el movimiento a {ficha['titulo']}")
        args_cara = ["--animado", str(transferido), "--ficha", str(ruta_ficha), "--salida", str(transferido),
                     "--expresion", a.expresion, "--intensidad", str(a.intensidad)]
        if a.habla:
            palabras = proyecto / "voz" / "palabras.json"
            if not palabras.exists():
                raise SystemExit("habla=true necesita la voz del proyecto (voz_generar) para sincronizar los labios.")
            desde = a.voz_desde
            if a.frase >= 0:
                frases = json.loads((proyecto / "voz" / "frases.json").read_text(encoding="utf-8"))
                desde = max(0.0, float(frases[a.frase]["inicio"]) - 0.07)  # igual que el corte del montaje
            args_cara += ["--palabras", str(palabras), "--desde_s", str(desde), "--habla", "1"]
        pasos["cara"] = correr(blender.comando(blender.script("cara_personaje.py"), args_cara),
                               f"cara de {ficha['titulo']} ({a.expresion}{', habla' if a.habla else ''})")
        animado = transferido

    # 3. Escenario (Poly Haven) y render.
    res_hdri = "4k" if a.escala >= 100 else "2k"
    hdri = polyhaven.hdri(a.hdri, res_hdri)
    piso = polyhaven.textura(a.piso, "2k" if a.escala >= 100 else "1k")
    cuadros = config.ruta_local("cuadros", proyecto.name, slug(a.nombre))
    args = ["--animado", str(animado), "--salida", str(carpeta / "toma.mp4"), "--hdri", str(hdri),
            "--piso", json.dumps(piso), "--motor", a.motor, "--muestras", str(a.muestras), "--escala", str(a.escala),
            "--carpeta_cuadros", str(cuadros), "--bloques", str(a.bloques)]
    camara = json.loads(a.camara or "{}")
    if "hdri_rotacion" in camara:
        args += ["--hdri_rotacion", str(camara.pop("hdri_rotacion"))]
    args += ["--camara", json.dumps(camara or {"plano": "general"})]
    if a.audio:
        args += ["--audio", a.audio]
    pasos["render"] = correr(blender.comando(blender.script("escena_toma.py"), args), "render de la toma")

    creditos = proyecto / "CREDITOS.txt"
    lineas = set(creditos.read_text(encoding="utf-8").splitlines()) if creditos.exists() else set()
    lineas |= {f"Iluminación HDRI «{a.hdri}» y textura «{a.piso}»: Poly Haven (polyhaven.com), CC0.",
               "Animaciones: Mixamo (Adobe), uso libre de regalías."}
    if ficha:
        lineas.add(f"Personaje: {ficha['credito']} — licencia CC-BY 4.0 (creativecommons.org/licenses/by/4.0).")
    else:
        lineas.add("Personajes: Mixamo (Adobe), uso libre de regalías.")
    if any(k.startswith("kimodo_") for k in pasos):
        lineas.add("Animación generada con NVIDIA Kimodo (NVIDIA Open Model License); "
                   "codificador de texto Built with Meta Llama 3.")
    creditos.write_text("\n".join(sorted(lineas)) + "\n", encoding="utf-8")

    reporte = {"ok": True, "mp4": str(carpeta / "toma.mp4"), "carpeta": str(carpeta), "cuadros_png": str(cuadros),
               "segundos_video": pasos["animacion"]["segundos"], "secuencia": secuencia,
               "render": {k: pasos["render"].get(k) for k in ("motor", "resolucion", "cuadros", "segundos_por_cuadro",
                                                              "segundos_render", "backend", "con_audio", "bloques")},
               "segundos_total": round(time.time() - t0, 1)}
    (carpeta / "reporte.json").write_text(json.dumps(reporte, indent=1, ensure_ascii=False), encoding="utf-8")
    print("RESULTADO_JSON: " + json.dumps(reporte, ensure_ascii=False), flush=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.tomas")
    sub = p.add_subparsers(dest="cmd", required=True)
    pm = sub.add_parser("mixamo")
    pm.add_argument("--altura", type=float, default=1.75)
    pm.add_argument("--forzar", action="store_true")
    pt = sub.add_parser("toma")
    pt.add_argument("--proyecto", required=True)
    pt.add_argument("--nombre", default="toma")
    pt.add_argument("--personaje", required=True)
    pt.add_argument("--secuencia", required=True)
    pt.add_argument("--motor", default="CYCLES", choices=["EEVEE", "CYCLES"])
    pt.add_argument("--muestras", type=int, default=64)
    pt.add_argument("--escala", type=int, default=100)
    pt.add_argument("--hdri", default="brown_photostudio_02")
    pt.add_argument("--piso", default="laminate_floor_02")
    pt.add_argument("--audio", default="")
    pt.add_argument("--camara", default="")
    pt.add_argument("--mezcla", type=int, default=10)
    pt.add_argument("--bloques", type=int, default=3)
    pt.add_argument("--esqueleto", default="remy", help="personaje Mixamo base para el elenco")
    pt.add_argument("--expresion", default="neutral")
    pt.add_argument("--intensidad", type=float, default=1.0)
    pt.add_argument("--habla", type=int, default=0)
    pt.add_argument("--frase", type=int, default=-1, help="frase de la voz que dice en esta toma")
    pt.add_argument("--voz_desde", type=float, default=0.0)
    a = p.parse_args()
    if not config.drive_disponible():
        raise SystemExit(config.AVISO_DRIVE)
    {"mixamo": cmd_mixamo, "toma": cmd_toma}[a.cmd](a)


if __name__ == "__main__":
    main()
