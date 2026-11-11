"""100STYLE → biblioteca de animaciones del estudio (esqueleto Mixamo), lista para {"anim": …}.

Por cada estilo (en procesos de Blender en paralelo):
  1. se toma de cada BVH el tramo útil oficial (Frame_Cuts.csv), unos segundos, a 30 cuadros/s y
     «en el lugar» (como las animaciones Mixamo in place; su velocidad real queda en el catálogo para
     que «avance: true» avance igual que el actor);
  2. se adapta al esqueleto remy (mismo método medido para Kimodo) con manos relajadas;
  3. se valida: huesos emparejados, saltos de rotación entre cuadros, altura de la cadera.
Resultado: biblioteca/animaciones/estilos100/<Estilo>.blend + estilos100.json (claves → archivo).
"""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .. import blender, config
from . import bvh, catalogo
from .proveedores import estilos100 as e100

MAPA = config.REPO / "estudio" / "esqueletos" / "estilos100.json"
SALTO_MAX = 25.0  # grados entre dos cuadros seguidos: más que eso es un hueso que «da la vuelta»
# Corriendo, brazos y antebrazos se mueven de verdad más rápido (medido: 26–27° en «apurado» correr/caminar,
# limpios a la vista). Un hueso que da la vuelta salta ~90–180°: 35° sigue atrapándolo.
SALTO_MAX_RAPIDO = 35.0
TIPOS_RAPIDOS = {"FR", "BR", "SR"}


def tipo_de(clave: str) -> str:
    # el sufijo más largo primero: «caminar_atras» no debe confundirse con «caminar»
    return max((t for t in e100.TIPOS if clave.endswith("_" + e100.TIPOS[t][0])), key=lambda t: len(e100.TIPOS[t][0]))


def carpeta() -> Path:
    return config.ruta_drive("biblioteca", "animaciones", "estilos100")


def catalogo_estilos() -> dict:
    ruta = carpeta() / "estilos100.json"
    cat = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    for v in cat.values():  # Drive puede montarse en otra ruta en otra sesión
        v["blend"] = str(carpeta() / Path(v["blend"]).name)
    return cat


def _guardar_catalogo(cat: dict) -> None:
    ruta = carpeta() / "estilos100.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ruta)


def _un_estilo(estilo: str, tipos: list[str], esqueleto: Path, dedos: str) -> dict:
    cortes = e100.cortes().get(estilo, {})
    tmp = config.ruta_local("recursos", "100style", estilo)
    tmp.mkdir(parents=True, exist_ok=True)
    bvhs, claves, info = [], [], {}
    for t in tipos:
        origen = e100.ruta_bvh(estilo, t)
        if t not in cortes or not origen.exists():
            continue
        ini, fin = cortes[t]
        segundos = e100.TIPOS[t][1]
        _, cuadros, dt, _ = bvh.leer(origen)
        n = min(fin - ini, int(round(segundos / dt)))
        desde = bvh.tramo_mas_recto(origen, ini, fin, n)
        destino = tmp / f"{estilo}_{t}.bvh"
        info[e100.clave(estilo, t)] = bvh.recortar(origen, destino, desde=desde, cuadros=n, fps=30.0, en_lugar=True)
        info[e100.clave(estilo, t)]["desde"] = desde
        bvhs.append(str(destino))
        claves.append(e100.clave(estilo, t))
    if not bvhs:
        return {"estilo": estilo, "error": "sin BVH"}
    salida = carpeta() / f"{estilo}.blend"
    cmd = blender.comando(blender.script("animar_personaje.py"),
                          ["--personaje", str(esqueleto), "--bvh", ",".join(bvhs), "--accion", ",".join(claves),
                           "--mapa", str(MAPA), "--salida", str(salida)] + (["--dedos_de", dedos] if dedos else [])
                          + ["--calibracion", str(e100.ruta_bvh("Neutral", "ID"))])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    linea = next((x for x in reversed(proc.stdout.splitlines()) if x.startswith("RESULTADO_JSON: ")), None)
    if proc.returncode != 0 or not linea:
        return {"estilo": estilo, "error": (proc.stdout + proc.stderr)[-800:]}
    r = json.loads(linea[len("RESULTADO_JSON: "):])
    acciones = r.get("acciones") or {claves[0]: r}
    return {"estilo": estilo, "blend": str(salida), "acciones": acciones, "recorte": info}


def convertir_estilos(estilos: str = "", tipos: str = "ID,FW,FR,BW,SW", hilos: int = 6, forzar: bool = False,
                      esqueleto: str = "remy", registro=print) -> dict:
    from ..tomas import biblioteca_mixamo, ruta_personaje
    t0 = time.time()
    e100.preparar(registro)
    pedidos = [x.strip() for x in estilos.split(",") if x.strip()] or sorted(e100.estilos())
    tipos_l = [x for x in tipos.split(",") if x in e100.TIPOS]
    cat = catalogo_estilos()
    if not forzar:
        hechos = {v["estilo"] for v in cat.values()}
        pedidos = [e for e in pedidos if e not in hechos]
    personaje = ruta_personaje(esqueleto)
    if not personaje.exists():
        raise SystemExit(f"No existe el esqueleto «{esqueleto}» en la biblioteca ({personaje}).")
    mix = biblioteca_mixamo()
    dedos = f"{mix}:parado_reposo" if mix.exists() else ""
    descripcion = e100.estilos()
    aprobadas, rechazadas, fallas = 0, {}, {}
    registro(f"100STYLE: convirtiendo {len(pedidos)} estilos ({','.join(tipos_l)}) en {hilos} procesos…")
    with ThreadPoolExecutor(hilos) as ex:
        futuros = [ex.submit(_un_estilo, e, tipos_l, personaje, dedos) for e in pedidos]
        for k, fut in enumerate(as_completed(futuros), 1):
            r = fut.result()
            if r.get("error"):
                fallas[r["estilo"]] = r["error"]
                continue
            for clave, acc in r["acciones"].items():
                val = acc.get("validacion", {})
                rec = r["recorte"].get(clave, {})
                motivo = ""
                if acc.get("huesos_emparejados", 0) < 20:
                    motivo = f"solo {acc.get('huesos_emparejados')} huesos emparejados"
                elif val.get("salto_max_grados", 0) > (SALTO_MAX_RAPIDO if tipo_de(clave) in TIPOS_RAPIDOS
                                                       or "Rushed" == r["estilo"] else SALTO_MAX):
                    motivo = f"salto de {val['salto_max_grados']}° en {val.get('hueso_salto')}"
                tipo = tipo_de(clave)
                entrada = {"clave": clave, "origen": "100style", "estilo": r["estilo"], "tipo": tipo,
                           "descripcion": descripcion.get(r["estilo"], ""), "blend": r["blend"],
                           "segundos": rec.get("segundos"), "en_lugar": True,
                           "velocidad_m_s": round(rec.get("velocidad_m_s", 0) * acc.get("escala_traslacion", 1), 2),
                           "categoria": "estilo", "validacion": val}
                id_ = f"estilos100:animacion:{clave}"
                if motivo:
                    rechazadas[clave] = motivo
                    if catalogo.obtener(id_):
                        catalogo.marcar(id_, "rechazado", extra={"motivo": motivo, **entrada})
                    continue
                cat[clave] = entrada
                aprobadas += 1
                if catalogo.obtener(id_):
                    catalogo.marcar(id_, "aprobado", r["blend"], extra=entrada)
            _guardar_catalogo(cat)
            catalogo.abrir().commit()
            registro(f"   {k}/{len(pedidos)} {r['estilo']}: {len(r['acciones'])} acciones")
    catalogo.guardar()
    return {"ok": not fallas, "estilos": len(pedidos), "aprobadas": aprobadas, "rechazadas": rechazadas,
            "fallas": {k: v[-300:] for k, v in fallas.items()}, "total_biblioteca": len(cat),
            "segundos": round(time.time() - t0)}
