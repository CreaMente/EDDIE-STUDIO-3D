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


KIMODO_BIB = Path(__file__).resolve().parent / "kimodo_biblioteca.json"


def catalogo_kimodo() -> dict:
    """Acciones de la biblioteca Kimodo ya generadas: {clave: {segundos, categoria, interaccion, blend}}."""
    ruta = config.ruta_drive("biblioteca", "animaciones", "kimodo", "kimodo.json")
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def cmd_kimodo_biblioteca(a) -> None:
    """Genera con Kimodo (una sola vez) las acciones de estudio/kimodo_biblioteca.json que falten y las
    deja en la biblioteca, adaptadas al esqueleto Mixamo, listas para usar como {"anim": clave}."""
    definiciones = {k: v for k, v in json.loads(KIMODO_BIB.read_text(encoding="utf-8")).items() if k[0] != "_"}
    carpeta = config.ruta_drive("biblioteca", "animaciones", "kimodo")
    carpeta.mkdir(parents=True, exist_ok=True)
    cat = catalogo_kimodo()
    esqueleto = ruta_personaje(a.esqueleto)
    pedidas = [x.strip() for x in a.nombre.split(",") if x.strip()] or list(definiciones)
    hechas, fallas = [], {}
    for clave in pedidas:
        if clave not in definiciones:
            fallas[clave] = "no está en estudio/kimodo_biblioteca.json"
            continue
        if clave in cat and Path(cat[clave]["blend"]).exists() and not a.forzar:
            continue
        d = definiciones[clave]
        try:
            entornos.asegurar("movimiento", log)
            r = correr(entornos.comando("movimiento", "ia.movimiento", "generar", "--textos", json.dumps(d["textos"]),
                                        "--duraciones", json.dumps(d["segundos"]), "--salida", str(carpeta),
                                        "--nombre", clave, "--semilla", str(d.get("semilla", 42))),
                       f"Kimodo: {clave}")
            blend = carpeta / f"{clave}.blend"
            correr(blender.comando(blender.script("animar_personaje.py"),
                                   ["--personaje", str(esqueleto), "--bvh", r["bvh"], "--salida", str(blend),
                                    "--accion", clave]), f"adaptar {clave} al esqueleto")
            cat[clave] = {"clave": clave, "origen": "kimodo", "segundos": r.get("duracion_s"),
                          "categoria": d.get("categoria", ""), "interaccion": d.get("interaccion", ""),
                          "textos": d["textos"], "blend": str(blend)}
            (carpeta / "kimodo.json").write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
            hechas.append(clave)
        except Exception as e:  # una que falle no detiene las demás
            fallas[clave] = str(e)[-600:]
    print("RESULTADO_JSON: " + json.dumps({"ok": not fallas, "generadas": hechas, "fallas": fallas,
                                           "total": len(cat)}, ensure_ascii=False), flush=True)


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
        indices = ",".join(str(x) for x in sorted(anims.glob("mixamo_indice*.json")))
        r = correr(blender.comando(script, ["animaciones", "--carpeta_fbx", str(anims), "--salida", str(blend),
                                            "--indice", indices, "--correcciones",
                                            str(Path(__file__).resolve().parent / "mixamo_correcciones.json")]),
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


CATALOGO_OBJETOS = Path(__file__).resolve().parent / "objetos.json"
ESCENARIOS = Path(__file__).resolve().parent / "escenarios.json"
# interacción de una animación (catálogo Mixamo) → tipo de interacción y objeto por defecto
INTERACCIONES = {"puerta": ("puerta", "puerta"), "tocar": ("tocar", "puerta"), "boton": ("boton", "boton"),
                 "agarrar": ("agarrar", "botella"), "soltar": ("soltar", "libro"), "lanzar": ("lanzar", "botella"),
                 "telefono": ("mano", "telefono"), "taza": ("mano", "taza"), "libro": ("mano", "libro"),
                 "caja": ("caja", "caja"), "sentarse": ("sentarse", "silla"), "sentado": ("sentarse", "silla")}


# Para animaciones importadas antes de que el catálogo guardara la interacción (primera tanda).
INTERACCION_POR_CLAVE = {"abrir_puerta": "puerta:R", "cerrar_puerta": "puerta:R", "tocar_puerta": "tocar:R",
                         "recoger_objeto": "agarrar:R", "beber": "taza:R", "mensajear_celular": "telefono:R",
                         "hablar_telefono": "telefono:R", "sentarse": "sentarse", "sentado_reposo": "sentado",
                         "levantarse_silla": "sentado", "dejar_objeto": "soltar:R", "lanzar": "lanzar:R",
                         "presionar_boton": "boton:R", "levantar_caja": "agarrar:R:caja", "cargar_caja": "caja",
                         "girar_con_caja": "caja"}


def resolver_objeto(tipo: str) -> dict:
    """Tipo del catálogo → cómo construirlo en Blender (procedural o glTF de Poly Haven ya descargado)."""
    cat = json.loads(CATALOGO_OBJETOS.read_text(encoding="utf-8"))
    if tipo not in cat:
        raise SystemExit(f"Objeto «{tipo}» no está en el catálogo. Opciones: {sorted(k for k in cat if k[0] != '_')}")
    d = dict(cat[tipo])
    d["tipo"] = tipo
    if "polyhaven" in d:
        d["ruta"] = polyhaven.modelo(d["polyhaven"])
    return d


def interacciones_de(secuencia: list, tramos: list) -> list[dict]:
    """Objetos de la toma: los que pide cada tramo («objeto») y los que trae la animación (catálogo)."""
    catalogo = dict(catalogo_kimodo())
    cat_path = biblioteca_mixamo().with_suffix(".json")
    if cat_path.exists():
        catalogo.update({x["clave"]: x for x in json.loads(cat_path.read_text(encoding="utf-8"))["animaciones"]})
    salida = []
    for item, tramo in zip(secuencia, tramos):
        pedido = item.get("objeto")
        todas = (catalogo.get(item.get("anim"), {}) or {}).get("interaccion") or \
            INTERACCION_POR_CLAVE.get(item.get("anim", ""), "")
        if pedido is False or (not pedido and not todas):
            continue
        # varias interacciones en una animación («sentado,telefono:R»); un «objeto» pedido reemplaza la última
        lista = [x for x in todas.split(",") if x] or [""]
        for inter in lista[:-1]:
            clave, _, mano = inter.partition(":")
            t_int, obj = INTERACCIONES.get(clave, ("mano", None))
            if obj:
                d = resolver_objeto(obj) if t_int not in ("puerta", "tocar", "boton") else {"tipo": obj}
                d.update({"interaccion": t_int, "mano": mano or "R", "desde": tramo["inicio"], "hasta": tramo["fin"]})
                salida.append(d)
        inter = lista[-1]
        partes = inter.split(":")  # «agarrar:R» o «agarrar:R:caja» (tipo:mano:objeto)
        clave, mano = partes[0], (partes[1] if len(partes) > 1 else "")
        tipo_int, obj_def = INTERACCIONES.get(clave, ("mano", None))
        if len(partes) > 2 and partes[2]:
            obj_def = partes[2]
        if isinstance(pedido, dict):
            tipo_int = pedido.get("interaccion", tipo_int)
            mano = pedido.get("mano", mano)
            obj = pedido.get("tipo", obj_def)
        else:
            obj = pedido or obj_def
        if not obj:
            continue
        d = resolver_objeto(obj) if tipo_int not in ("puerta", "tocar", "boton") else {"tipo": obj}
        d.update({"interaccion": tipo_int, "mano": mano or "R", "desde": tramo["inicio"], "hasta": tramo["fin"]})
        salida.append(d)
    return salida


def resolver_escenario(pedido: str, escala: int) -> dict:
    """«habitacion» o {"tipo": "habitacion", "pared": …, "muebles": […]} → configuración completa con las
    texturas y modelos ya descargados (Poly Haven, CC0)."""
    tipos = json.loads(ESCENARIOS.read_text(encoding="utf-8"))
    conf = json.loads(pedido) if pedido.strip().startswith("{") else {"tipo": pedido or "estudio"}
    tipo = conf.get("tipo", "estudio")
    if tipo not in tipos:
        raise SystemExit(f"Escenario «{tipo}» desconocido. Opciones: {sorted(k for k in tipos if k[0] != '_')}")
    completo = {**tipos[tipo], **conf}
    res = "2k" if escala >= 100 else "1k"
    completo["texturas"] = {k: polyhaven.textura(completo[k], res) for k in ("pared", "piso") if completo.get(k)}
    rutas = {}
    for m in completo.get("muebles", []):
        try:
            d = resolver_objeto(m)
            if d.get("ruta"):
                rutas[m] = d["ruta"]
        except Exception as e:  # un mueble que no baja no detiene la toma
            log(f"   (mueble «{m}» omitido: {e})")
    completo["muebles_rutas"] = rutas
    return completo


def transferir_en_bloques(animado: Path, blend_elenco: Path, ruta_ficha: Path, salida: Path, cuadros: int,
                          titulo: str) -> dict:
    """Pasa el movimiento al rig del elenco repartiendo los cuadros entre varios procesos de Blender
    (cada cuadro se calcula por separado: escala con los núcleos de la máquina) y une las partes."""
    nucleos = os.cpu_count() or 2
    n = max(1, min(8, nucleos, cuadros // 30))
    log(f"▶ pasar el movimiento a {titulo} ({cuadros} cuadros en {n} procesos)")
    t0 = time.time()
    cortes = [1 + round(cuadros * k / n) for k in range(n + 1)]
    partes, procesos = [], []
    for k in range(n):
        parte = salida.with_name(f"{salida.stem}_parte{k}.blend")
        cmd = blender.comando(blender.script("transferir_personaje.py"),
                              ["--fuente", str(animado), "--personaje", str(blend_elenco), "--ficha", str(ruta_ficha),
                               "--salida", str(parte), "--rango", f"{cortes[k]}-{cortes[k + 1] - 1}"])
        partes.append(parte)
        procesos.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
    resultados = []
    for k, proc in enumerate(procesos):
        salida_txt = proc.communicate()[0]
        linea = next((x for x in salida_txt.splitlines() if x.startswith("RESULTADO_JSON: ")), None)
        if proc.returncode != 0 or not linea:
            raise RuntimeError(f"Falló la transferencia (parte {k}):\n" + "\n".join(salida_txt.splitlines()[-30:]))
        resultados.append(json.loads(linea[len("RESULTADO_JSON: "):]))
    union = correr(blender.comando(blender.script("unir_transferencias.py"),
                                   ["--partes", ",".join(str(x) for x in partes), "--salida", str(salida)]),
                   "unir las partes")
    for x in partes:
        x.unlink(missing_ok=True)
    errores: dict = {}
    for r in resultados:
        for hueso, v in r.get("error_max_grados", {}).items():
            errores[hueso] = max(errores.get(hueso, 0.0), v)
    info = {"procesos": n, "cuadros": cuadros, "error_max_grados": errores,
            "anclaje_m": {"min": min(r["anclaje_m"]["min"] for r in resultados),
                          "max": max(r["anclaje_m"]["max"] for r in resultados)},
            "signos_corregidos": union.get("signos_corregidos"), "segundos": round(time.time() - t0, 1)}
    log(f"✔ movimiento en {titulo} ({info['segundos']} s; error máx. {max(errores.values(), default=0):.1f}°)")
    return info


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
    kim = catalogo_kimodo()  # acciones de la biblioteca Kimodo que pide esta toma
    bibliotecas += sorted({kim[c["anim"]]["blend"] for c in secuencia if c.get("anim") in kim})
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
                                                 "--mezcla", str(a.mezcla), "--duracion_min", str(a.duracion_min)]),
                                "encadenar animaciones")

    # 2b. Elenco: transferir al rig del personaje y animar su cara (labios, expresión, parpadeo).
    if ficha:
        blend_elenco = elenco.preparar(a.personaje, log)
        ruta_ficha = elenco.FICHAS / f"{ficha['nombre']}.json"
        transferido = carpeta / f"animado_{ficha['nombre']}.blend"
        pasos["transferencia"] = transferir_en_bloques(animado, blend_elenco, ruta_ficha, transferido,
                                                       int(pasos["animacion"]["cuadros"]), ficha["titulo"])
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

    # 3. Escenario (Poly Haven), objetos con los que interactúa y render.
    escenario = resolver_escenario(a.escenario, a.escala)
    objetos = interacciones_de(secuencia, pasos["animacion"]["tramos"]) + json.loads(a.objetos or "[]")
    nombre_hdri = a.hdri or escenario.get("hdri") or "brown_photostudio_02"
    res_hdri = "4k" if a.escala >= 100 else "2k"
    hdri = polyhaven.hdri(nombre_hdri, res_hdri)
    piso = polyhaven.textura(a.piso, "2k" if a.escala >= 100 else "1k")
    cuadros = config.ruta_local("cuadros", proyecto.name, slug(a.nombre))
    args = ["--animado", str(animado), "--salida", str(carpeta / "toma.mp4"), "--hdri", str(hdri),
            "--piso", json.dumps(piso), "--motor", a.motor, "--muestras", str(a.muestras), "--escala", str(a.escala),
            "--carpeta_cuadros", str(cuadros), "--bloques", str(a.bloques)]
    if ficha and ficha.get("cara", {}).get("ojos"):
        args += ["--ojos", ficha["cara"]["ojos"]]
    args += ["--escenario", json.dumps(escenario, ensure_ascii=False), "--objetos", json.dumps(objetos, ensure_ascii=False)]
    camara = json.loads(a.camara or "{}")
    if "hdri_rotacion" in camara:
        args += ["--hdri_rotacion", str(camara.pop("hdri_rotacion"))]
    args += ["--camara", json.dumps(camara or {"plano": "general"})]
    if a.audio:
        args += ["--audio", a.audio]
    pasos["render"] = correr(blender.comando(blender.script("escena_toma.py"), args), "render de la toma")

    creditos = proyecto / "CREDITOS.txt"
    lineas = set(creditos.read_text(encoding="utf-8").splitlines()) if creditos.exists() else set()
    lineas |= {f"Iluminación HDRI «{nombre_hdri}», texturas y modelos 3D: Poly Haven (polyhaven.com), CC0.",
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
                                                              "segundos_render", "backend", "con_audio", "bloques",
                                                              "objetos", "escenario", "mirada")},
               "segundos_total": round(time.time() - t0, 1)}
    (carpeta / "reporte.json").write_text(json.dumps(reporte, indent=1, ensure_ascii=False), encoding="utf-8")
    print("RESULTADO_JSON: " + json.dumps(reporte, ensure_ascii=False), flush=True)


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.tomas")
    sub = p.add_subparsers(dest="cmd", required=True)
    pm = sub.add_parser("mixamo")
    pm.add_argument("--altura", type=float, default=1.75)
    pm.add_argument("--forzar", action="store_true")
    pk = sub.add_parser("kimodo_biblioteca")
    pk.add_argument("--nombre", default="", help="claves separadas por coma (vacío = todas las que falten)")
    pk.add_argument("--esqueleto", default="remy")
    pk.add_argument("--forzar", action="store_true")
    pt = sub.add_parser("toma")
    pt.add_argument("--proyecto", required=True)
    pt.add_argument("--nombre", default="toma")
    pt.add_argument("--personaje", required=True)
    pt.add_argument("--secuencia", required=True)
    pt.add_argument("--motor", default="CYCLES", choices=["EEVEE", "CYCLES"])
    pt.add_argument("--muestras", type=int, default=64)
    pt.add_argument("--escala", type=int, default=100)
    pt.add_argument("--hdri", default="", help="vacío = el del escenario")
    pt.add_argument("--escenario", default="estudio", help='nombre o JSON: {"tipo": "habitacion", "muebles": [...]}')
    pt.add_argument("--objetos", default="[]", help="interacciones extra (JSON)")
    pt.add_argument("--duracion_min", type=float, default=0.0)
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
    {"mixamo": cmd_mixamo, "toma": cmd_toma, "kimodo_biblioteca": cmd_kimodo_biblioteca}[a.cmd](a)


if __name__ == "__main__":
    main()
