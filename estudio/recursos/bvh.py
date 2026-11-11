"""Preparación de archivos BVH antes de llevarlos a Blender (Python puro, sin dependencias).

recortar(...) toma un tramo de un BVH largo (p. ej. una toma de 100STYLE de varios minutos), lo pasa a
30 cuadros/s y, si se pide, lo deja «en el lugar» como las animaciones Mixamo «in place»:
  - se resta la trayectoria de la cadera suavizada (1 s): queda el balanceo natural, no el recorrido;
  - se quita el rumbo (giro de todo el cuerpo) suavizado: el personaje mira siempre hacia adelante;
  - se mide la velocidad media del recorrido original (m/s) para avanzar igual en la toma.
"""

from __future__ import annotations

import math
from pathlib import Path


def leer(ruta: Path) -> tuple[list[str], list[list[float]], float, list[str]]:
    """(líneas de cabecera hasta MOTION incluida, cuadros, segundos por cuadro, canales de la raíz)."""
    lineas = Path(ruta).read_text(encoding="utf-8", errors="ignore").splitlines()
    i = next(k for k, x in enumerate(lineas) if x.strip().upper() == "MOTION")
    cabecera = lineas[:i + 1]
    dt = float(lineas[i + 2].split(":")[1])
    cuadros = [[float(v) for v in x.split()] for x in lineas[i + 3:] if x.strip()]
    raiz = next(x for x in cabecera if "CHANNELS" in x).split()[2:]
    return cabecera, cuadros, dt, raiz


def _suavizar(valores: list[float], ventana: int) -> list[float]:
    n, mitad = len(valores), max(1, ventana // 2)
    acum = [0.0]
    for v in valores:
        acum.append(acum[-1] + v)
    salida = []
    for k in range(n):
        a, b = max(0, k - mitad), min(n, k + mitad + 1)
        salida.append((acum[b] - acum[a]) / (b - a))
    return salida


def _desenrollar(grados: list[float]) -> list[float]:
    salida, previo = [], None
    for g in grados:
        if previo is not None:
            while g - previo > 180:
                g -= 360
            while g - previo < -180:
                g += 360
        salida.append(g)
        previo = g
    return salida


def tramo_mas_recto(origen: Path, ini: int, fin: int, cuadros: int) -> int:
    """Inicio (en cuadros del original) del tramo de «cuadros» con menos cambio de rumbo dentro de [ini, fin].
    En 100STYLE el actor camina por el estudio y da vueltas: un tramo con una curva cruza las piernas al
    dejarlo en el lugar."""
    _, todos, dt, raiz = leer(origen)
    fin = min(fin, len(todos))
    if fin - ini <= cuadros or "Yrotation" not in raiz:
        return ini
    iyaw = raiz.index("Yrotation")
    yaw = _suavizar(_desenrollar([c[iyaw] for c in todos[ini:fin]]), int(round(1 / dt)))
    paso = max(1, int(round(0.25 / dt)))
    mejor, inicio = None, ini
    for k in range(0, len(yaw) - cuadros, paso):
        ventana = yaw[k:k + cuadros]
        cambio = max(ventana) - min(ventana)
        if mejor is None or cambio < mejor:
            mejor, inicio = cambio, ini + k
    return inicio


def recortar(origen: Path, destino: Path, desde: int = 0, cuadros: int | None = None, fps: float = 30.0,
             en_lugar: bool = False, unidad_m: float = 0.01) -> dict:
    """Escribe un BVH recortado y remuestreado. desde/cuadros en cuadros del ORIGINAL."""
    cabecera, todos, dt, raiz = leer(origen)
    fps_origen = 1.0 / dt
    paso = max(1, int(round(fps_origen / fps)))
    fin = len(todos) if cuadros is None else min(len(todos), desde + cuadros)
    tramo = [list(c) for c in todos[desde:fin]]
    if len(tramo) < paso * 2:
        raise ValueError(f"tramo demasiado corto ({len(tramo)} cuadros)")
    ix, iy, iz = (raiz.index(f"{e}position") for e in "XYZ")
    info = {"fps_origen": round(fps_origen, 2), "paso": paso, "cuadros": 0, "velocidad_m_s": 0.0, "en_lugar": en_lugar}
    ventana = int(round(fps_origen))  # 1 s
    xs, zs = [c[ix] for c in tramo], [c[iz] for c in tramo]
    sx, sz = _suavizar(xs, ventana), _suavizar(zs, ventana)
    # Velocidad: recorrido de la cadera medido cada 1 s (dos pasos: el balanceo lateral se anula y no hay
    # el encogimiento del promedio en los bordes del tramo).
    marcas = list(range(0, len(tramo), ventana))
    recorrido = sum(math.hypot(xs[b] - xs[a], zs[b] - zs[a]) for a, b in zip(marcas, marcas[1:]))
    info["velocidad_m_s"] = round(recorrido * unidad_m / max(dt, (marcas[-1] - marcas[0]) * dt), 3)
    if en_lugar:
        x0, z0 = sx[0], sz[0]
        for k, c in enumerate(tramo):
            c[ix] = c[ix] - sx[k] + x0
            c[iz] = c[iz] - sz[k] + z0
        if "Yrotation" in raiz and raiz.index("Yrotation") == 3:  # orden Y X Z: Y es el rumbo en el mundo
            iyaw = 3
            yaw = _desenrollar([c[iyaw] for c in tramo])
            syaw = _suavizar(yaw, ventana)
            for k, c in enumerate(tramo):
                c[iyaw] = yaw[k] - syaw[k]
            info["rumbo_quitado_grados"] = round(max(syaw) - min(syaw), 1)
    salida_cuadros = tramo[::paso]
    info["cuadros"] = len(salida_cuadros)
    info["segundos"] = round(len(salida_cuadros) / fps, 2)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(cabecera) + f"\nFrames: {len(salida_cuadros)}\nFrame Time: {1.0 / fps:.6f}\n"
    texto += "\n".join(" ".join(f"{v:.6f}" for v in c) for c in salida_cuadros) + "\n"
    tmp = destino.with_name(destino.name + ".parcial")
    tmp.write_text(texto, encoding="utf-8")
    tmp.replace(destino)
    del iy
    return info
