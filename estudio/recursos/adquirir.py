"""Adquisición automática de recursos: licencias → catálogo → descarga → validación → biblioteca.

  python -m estudio.recursos.adquirir verificar   [--fuentes a,b]
  python -m estudio.recursos.adquirir descubrir   [--fuentes a,b]            (solo catálogo, no baja nada)
  python -m estudio.recursos.adquirir estimar     [--fuentes a,b] [--perfil produccion]
  python -m estudio.recursos.adquirir descargar   [--fuentes a,b] [--tipos …] [--perfil …] [--limite_gb 330]
                                                  [--max 0] [--hilos 6] [--prueba]
  python -m estudio.recursos.adquirir estado
  python -m estudio.recursos.adquirir buscar      --texto "silla madera" [--tipo modelo]
  python -m estudio.recursos.adquirir ingresar    (procesa biblioteca/_entrada/navegador/)
  python -m estudio.recursos.adquirir convertir   [--estilos Old,Zombie] [--tipos ID,FW] [--hilos 6]
  python -m estudio.recursos.adquirir licencia_manual --fuente mixamo --url … --texto_archivo pagina.txt
  python -m estudio.recursos.adquirir reporte

Todo es reanudable: si se corta (o se cierra Colab), volver a ejecutar continúa donde quedó.
Nunca se sobrescribe ni se borra nada de la biblioteca existente.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .. import config
from . import catalogo, licencias
from .descargas import SinEspacio
from .proveedores import AUTOMATICOS, modulo

PRIORIDAD = {"polyhaven": 0, "ambientcg": 1, "estilos100": 2, "blender_studio": 3}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def resultado(d: dict) -> None:
    print("RESULTADO_JSON: " + json.dumps(d, ensure_ascii=False), flush=True)


def _fuentes(texto: str) -> list[str]:
    pedidas = [x.strip() for x in (texto or "").split(",") if x.strip()] or AUTOMATICOS
    raras = [x for x in pedidas if x not in AUTOMATICOS]
    if raras:
        raise SystemExit(f"Fuentes sin descarga automática: {raras}. Automáticas: {AUTOMATICOS}. Las de navegador "
                         "(quaternius, kenney, mixamo) se bajan a biblioteca/_entrada/navegador/<fuente>/ y se "
                         "procesan con «ingresar».")
    return sorted(pedidas, key=lambda f: PRIORIDAD.get(f, 9))


# ───────────────────────── licencias ─────────────────────────

def cmd_verificar(a) -> None:
    nombres = [x for x in a.fuentes.split(",") if x] if a.fuentes else list(licencias.fuentes())
    salida = {}
    for n in nombres:
        ev = licencias.verificar(n, forzar=True)
        salida[n] = {"ok": ev.get("ok"), "motivo": ev.get("motivo", ""), "fecha": ev.get("fecha"),
                     "url": ev.get("url_licencia")}
        log(f"{'✔' if ev.get('ok') else '✘'} {n}: {ev.get('motivo') or ev.get('licencia')}")
    resultado({"ok": True, "fuentes": salida})


def cmd_licencia_manual(a) -> None:
    texto = Path(a.texto_archivo).read_text(encoding="utf-8", errors="ignore")
    ev = licencias.guardar_manual(a.fuente, a.url, licencias.texto_plano(texto), a.quien)
    resultado({"ok": ev["ok"], "evidencia": ev})


# ───────────────────────── catálogo ─────────────────────────

def descubrir(fuentes: list[str]) -> dict[str, list[dict]]:
    salida = {}
    for f in fuentes:
        licencias.exigir(f)
        entradas = modulo(f).descubrir(log)
        for e in entradas:
            catalogo.registrar(e)
        catalogo.abrir().commit()
        salida[f] = entradas
    catalogo.guardar()
    return salida


def cmd_descubrir(a) -> None:
    d = descubrir(_fuentes(a.fuentes))
    resultado({"ok": True, "descubiertos": {k: len(v) for k, v in d.items()}, "catalogo": catalogo.resumen()})


def cmd_estimar(a) -> None:
    fuentes = _fuentes(a.fuentes)
    descubrir(fuentes)
    totales = {}
    for f in fuentes:
        mod = modulo(f)
        por_tipo: dict = {}
        filas = [r for r in catalogo.listar(fuente=f) if r["estado"] != "rechazado"]
        if a.tipos:
            filas = [r for r in filas if r["tipo"] in a.tipos.split(",")]

        def una(r):
            try:
                return r["tipo"], mod.estimar(r, a.perfil)
            except Exception:  # noqa: BLE001
                return r["tipo"], None

        with ThreadPoolExecutor(a.hilos) as ex:
            for tipo, b in ex.map(una, filas):
                t = por_tipo.setdefault(tipo, {"n": 0, "gb": 0.0, "sin_dato": 0})
                t["n"] += 1
                if b is None:
                    t["sin_dato"] += 1
                else:
                    t["gb"] += b / 1e9
        for t in por_tipo.values():
            t["gb"] = round(t["gb"], 1)
        totales[f] = por_tipo
        log(f"{f}: {por_tipo}")
    gb = round(sum(t["gb"] for p in totales.values() for t in p.values()), 1)
    resultado({"ok": True, "perfil": a.perfil, "estimado": totales, "gb_total": gb})


# ───────────────────────── descarga ─────────────────────────

def validar(entrada: dict, r: dict) -> tuple[bool, str]:
    """Validación de integridad y estructura (el contenido visual se valida con renders de prueba)."""
    ruta = Path(r["ruta"])
    if not ruta.exists():
        return False, "la ruta no existe después de bajar"
    if r.get("bytes", 0) <= 0:
        return False, "0 bytes"
    if entrada["fuente"] == "polyhaven" and entrada["tipo"] == "modelo":
        for carpeta in r["extra"].get("rutas", [r["ruta"]]):
            c = Path(carpeta)
            gltf = next(iter(c.glob("*.gltf")), None)
            if not gltf:
                return False, "sin .gltf"
            datos = json.loads(gltf.read_text(encoding="utf-8"))
            faltan = [x.get("uri") for x in datos.get("buffers", []) + datos.get("images", [])
                      if x.get("uri") and not x["uri"].startswith("data:") and not (c / x["uri"]).exists()]
            if faltan:
                return False, f"faltan archivos del glTF: {faltan[:3]}"
    if entrada["fuente"] == "ambientcg" and entrada["tipo"] in ("material", "decal", "atlas"):
        for carpeta in r["extra"].get("rutas", [r["ruta"]]):
            mapas = json.loads((Path(carpeta) / "mapas.json").read_text(encoding="utf-8"))
            if "color" not in mapas:
                return False, "sin mapa de color"
    return True, ""


def estado_final(entrada: dict) -> str:
    """Qué queda listo para producir sin más pasos."""
    if entrada["tipo"] in ("hdri", "textura", "modelo", "material", "decal", "atlas"):
        return "aprobado"
    return "descargado"  # personajes (falta ficha) y animaciones BVH (falta convertir)


def cmd_descargar(a) -> None:
    t0 = time.time()
    fuentes = _fuentes(a.fuentes)
    limite = a.limite_gb * 1e9
    log(f"Fuentes: {fuentes} · perfil {a.perfil} · límite {a.limite_gb} GB · ya en Drive "
        f"{catalogo.bytes_en_drive() / 1e9:.1f} GB")
    rechazadas = {}
    for f in list(fuentes):
        ev = licencias.verificar(f)
        if not ev.get("ok"):
            rechazadas[f] = ev.get("motivo")
            fuentes.remove(f)
            log(f"✘ {f}: no se descarga ({ev.get('motivo')})")
        else:
            log(f"✔ licencia {f}: {ev.get('licencia')} (evidencia {ev.get('fecha')})")
    if not a.sin_descubrir:
        descubrir(fuentes)
    hechos, errores, omitidos = {}, {}, 0
    detener = None
    for f in fuentes:
        mod = modulo(f)
        pendientes = [r for r in catalogo.listar(fuente=f) if r["estado"] in ("descubierto", "error")]
        if a.tipos:
            pendientes = [r for r in pendientes if r["tipo"] in a.tipos.split(",")]
        pendientes.sort(key=lambda r: -float((r.get("extra") or {}).get("descargas")
                                             or (r.get("extra") or {}).get("popularidad") or 0))
        if a.max:
            pendientes = pendientes[:a.max]
        log(f"── {f}: {len(pendientes)} por bajar")
        hechos[f] = 0
        hilos = a.hilos if f in ("polyhaven", "ambientcg") else 1

        uso = [catalogo.bytes_en_drive()]  # se actualiza en este hilo; los trabajadores solo lo leen

        def una(r):
            if uso[0] >= limite:
                raise SinEspacio(f"se alcanzó el límite de {a.limite_gb} GB")
            return r, mod.descargar(r, a.perfil, log)

        with ThreadPoolExecutor(hilos) as ex:
            futuros = {ex.submit(una, r): r for r in pendientes}
            for k, fut in enumerate(as_completed(futuros), 1):
                r = futuros[fut]
                try:
                    _, res = fut.result()
                    ok, motivo = validar(r, res)
                    uso[0] += res.get("bytes", 0)
                    if ok:
                        catalogo.marcar(r["id"], estado_final(r), res["ruta"], res["bytes"], res.get("extra"))
                        hechos[f] += 1
                    else:
                        catalogo.marcar(r["id"], "rechazado", res["ruta"], res["bytes"], {"motivo": motivo})
                        errores[r["id"]] = motivo
                except SinEspacio as e:
                    detener = str(e)
                    omitidos += 1
                except Exception as e:  # noqa: BLE001
                    errores[r["id"]] = str(e)[-300:]
                    catalogo.marcar(r["id"], "error", extra={"motivo": str(e)[-300:]})
                if k % 25 == 0 or k == len(pendientes):
                    catalogo.abrir().commit()
                    log(f"   {f}: {k}/{len(pendientes)} · {catalogo.bytes_en_drive() / 1e9:.1f} GB en Drive · "
                        f"{len(errores)} errores")
                if k % 200 == 0:
                    catalogo.guardar()
                if detener:
                    for otro in futuros:
                        otro.cancel()
        catalogo.guardar()
        if detener:
            log(f"⏸ {detener}")
            break
    reporte = escribir_reportes()
    resultado({"ok": not detener, "detenido": detener, "descargados": hechos, "errores": len(errores),
               "ejemplos_error": dict(list(errores.items())[:10]), "omitidos_por_espacio": omitidos,
               "fuentes_rechazadas": rechazadas, "gb_en_drive": round(catalogo.bytes_en_drive() / 1e9, 1),
               "reportes": reporte, "segundos": round(time.time() - t0)})


# ───────────────────────── consultas ─────────────────────────

def cmd_estado(a) -> None:
    from .descargas import libre_gb
    resultado({"ok": True, "catalogo": catalogo.resumen(), "licencias": licencias.resumen(),
               "drive_libre_gb": libre_gb(config.DRIVE)})


def cmd_buscar(a) -> None:
    filas = catalogo.buscar(a.texto, a.tipo, a.fuente, a.estados, a.limite)
    resultado({"ok": True, "resultados": [{k: r[k] for k in ("id", "tipo", "clave", "nombre", "estado", "ruta",
                                                             "licencia", "credito")} for r in filas]})


def escribir_reportes() -> dict:
    carpeta = config.ruta_drive("biblioteca", "_catalogo", "reportes")
    carpeta.mkdir(parents=True, exist_ok=True)
    res = catalogo.resumen()
    lic = licencias.resumen()
    lineas = ["# Reporte de recursos", f"Fecha: {time.strftime('%Y-%m-%d %H:%M')}",
              f"Total en Drive: {res['gb_total']} GB", "", "| Fuente | Tipo | Estado | N | GB |", "|---|---|---|---|---|"]
    for f, tipos in res["por_fuente"].items():
        for t, estados in tipos.items():
            for e, d in estados.items():
                lineas.append(f"| {f} | {t} | {e} | {d['n']} | {d['gb']} |")
    lineas += ["", "## Licencias", "| Fuente | Licencia | Estado | Evidencia | Método |", "|---|---|---|---|---|"]
    for x in lic:
        lineas.append(f"| {x['fuente']} | {x['licencia']} | {x['estado']} | {x['evidencia'] or '—'} | "
                      f"{x['metodo'] or '—'} |")
    (carpeta / "REPORTE_RECURSOS.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    errores = catalogo.listar(estado="error,rechazado")
    (carpeta / "ERRORES.json").write_text(json.dumps([{"id": r["id"], "motivo": (r.get("extra") or {}).get("motivo")}
                                                      for r in errores], indent=1, ensure_ascii=False),
                                          encoding="utf-8")
    creditos = sorted({r["credito"] for r in catalogo.listar(estado="aprobado,descargado") if r.get("credito")})
    (carpeta / "CREDITOS_BIBLIOTECA.txt").write_text("\n".join(creditos) + "\n", encoding="utf-8")
    return {"carpeta": str(carpeta), "errores": len(errores)}


def cmd_reporte(a) -> None:
    resultado({"ok": True, **escribir_reportes(), "catalogo": catalogo.resumen()})


def cmd_ingresar(a) -> None:
    from .ingestor import revisar
    resultado(revisar(log))


def cmd_convertir(a) -> None:
    from .convertir import convertir_estilos
    resultado(convertir_estilos(a.estilos, a.tipos, a.hilos, a.forzar, a.esqueleto, log))


def main() -> None:
    p = argparse.ArgumentParser(prog="estudio.recursos.adquirir")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nombre in ("verificar", "descubrir", "estimar", "descargar"):
        s = sub.add_parser(nombre)
        s.add_argument("--fuentes", default="")
        s.add_argument("--tipos", default="")
        s.add_argument("--perfil", default="produccion", choices=["produccion", "ligero", "alta"])
        s.add_argument("--limite_gb", type=float, default=330.0)
        s.add_argument("--max", type=int, default=0, help="máximo de recursos por fuente (0 = todos)")
        s.add_argument("--hilos", type=int, default=6)
        s.add_argument("--sin_descubrir", action="store_true")
    s = sub.add_parser("estado")
    s = sub.add_parser("reporte")
    s = sub.add_parser("ingresar")
    s = sub.add_parser("buscar")
    s.add_argument("--texto", default="")
    s.add_argument("--tipo", default="")
    s.add_argument("--fuente", default="")
    s.add_argument("--estados", default="descargado,aprobado")
    s.add_argument("--limite", type=int, default=30)
    s = sub.add_parser("convertir")
    s.add_argument("--estilos", default="")
    s.add_argument("--tipos", default="ID,FW,FR,BW,SW")
    s.add_argument("--hilos", type=int, default=6)
    s.add_argument("--forzar", action="store_true")
    s.add_argument("--esqueleto", default="remy")
    s = sub.add_parser("licencia_manual")
    s.add_argument("--fuente", required=True)
    s.add_argument("--url", required=True)
    s.add_argument("--texto_archivo", required=True)
    s.add_argument("--quien", default="propietario")
    a = p.parse_args()
    if not config.drive_disponible():
        raise SystemExit(config.AVISO_DRIVE)
    try:
        globals()[f"cmd_{a.cmd}"](a)
    except licencias.LicenciaNoVerificada as e:
        resultado({"ok": False, "error": f"Licencia no verificada: {e}"})
        sys.exit(2)
    except Exception:
        traceback.print_exc()
        raise
    finally:
        catalogo.cerrar()


if __name__ == "__main__":
    main()
