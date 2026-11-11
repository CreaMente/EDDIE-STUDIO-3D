"""Catálogo de recursos en dos niveles, en una base SQLite (escala a cientos de miles de entradas).

  estado = descubierto  → solo metadatos (lo que existe en la fuente)
           descargado   → archivos en Drive, verificados (tamaño / md5)
           aprobado     → además validado y listo para producir (lo que usan las tomas)
           rechazado / error

Se trabaja sobre una copia en el disco local de la sesión (SQLite sobre Drive es lento y frágil) y se
guarda en Drive (<DRIVE>/biblioteca/_catalogo/catalogo.db) de forma atómica, con una copia fechada por
día en _catalogo/respaldos/ (se conservan las 14 últimas). Un solo proceso escribe a la vez.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

from .. import config

COLUMNAS = ["id", "fuente", "tipo", "clave", "nombre", "categorias", "etiquetas", "licencia", "credito",
            "url_pagina", "estado", "ruta", "bytes", "extra", "actualizado"]
ESQUEMA = """
CREATE TABLE IF NOT EXISTS recursos (
  id TEXT PRIMARY KEY, fuente TEXT, tipo TEXT, clave TEXT, nombre TEXT, categorias TEXT, etiquetas TEXT,
  licencia TEXT, credito TEXT, url_pagina TEXT, estado TEXT, ruta TEXT, bytes INTEGER DEFAULT 0,
  extra TEXT, actualizado TEXT);
CREATE INDEX IF NOT EXISTS i_fuente ON recursos(fuente, tipo, estado);
CREATE INDEX IF NOT EXISTS i_clave ON recursos(clave);
"""
_conexion: sqlite3.Connection | None = None


def ruta_drive() -> Path:
    return config.ruta_drive("biblioteca", "_catalogo", "catalogo.db")


def ruta_local() -> Path:
    return config.ruta_local("recursos", "catalogo.db")


def abrir(solo_lectura: bool = False) -> sqlite3.Connection:
    global _conexion
    if _conexion is not None:
        return _conexion
    local, remota = ruta_local(), ruta_drive()
    local.parent.mkdir(parents=True, exist_ok=True)
    if remota.exists() and (not local.exists() or remota.stat().st_mtime > local.stat().st_mtime + 1):
        shutil.copy2(remota, local)
    con = sqlite3.connect(str(local), timeout=60)
    con.row_factory = sqlite3.Row
    if not solo_lectura:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(ESQUEMA)
    _conexion = con
    return con


def cerrar() -> None:
    global _conexion
    if _conexion is not None:
        _conexion.close()
        _conexion = None


def guardar() -> str:
    """Copia la base local a Drive (atómico) y deja un respaldo fechado del día."""
    con = abrir()
    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    remota = ruta_drive()
    remota.parent.mkdir(parents=True, exist_ok=True)
    tmp = remota.with_suffix(".db.tmp")
    shutil.copy2(ruta_local(), tmp)
    tmp.replace(remota)
    respaldos = remota.parent / "respaldos"
    respaldos.mkdir(exist_ok=True)
    del_dia = respaldos / f"catalogo_{time.strftime('%Y%m%d')}.db"
    shutil.copy2(remota, del_dia)
    for viejo in sorted(respaldos.glob("catalogo_*.db"))[:-14]:
        viejo.unlink()
    return str(remota)


def _fila(d: dict) -> dict:
    fila = {k: d.get(k) for k in COLUMNAS}
    for k in ("categorias", "etiquetas"):
        if isinstance(fila[k], (list, tuple, set)):
            fila[k] = ",".join(str(x) for x in fila[k])
    if isinstance(fila["extra"], dict):
        fila["extra"] = json.dumps(fila["extra"], ensure_ascii=False)
    fila["actualizado"] = time.strftime("%Y-%m-%d %H:%M:%S")
    fila["bytes"] = int(fila["bytes"] or 0)
    return fila


def registrar(d: dict) -> None:
    """Agrega o actualiza metadatos SIN retroceder el estado (un recurso descargado no vuelve a «descubierto»)."""
    con = abrir()
    fila = _fila(d)
    previo = con.execute("SELECT estado, ruta, bytes FROM recursos WHERE id=?", (fila["id"],)).fetchone()
    if previo and previo["estado"] in ("descargado", "aprobado") and fila.get("estado") in (None, "descubierto"):
        fila["estado"], fila["ruta"], fila["bytes"] = previo["estado"], previo["ruta"], previo["bytes"]
    fila["estado"] = fila["estado"] or "descubierto"
    con.execute(f"INSERT OR REPLACE INTO recursos ({','.join(COLUMNAS)}) VALUES ({','.join('?' * len(COLUMNAS))})",
                [fila[k] for k in COLUMNAS])


def marcar(id_: str, estado: str, ruta: str | None = None, bytes_: int | None = None, extra: dict | None = None) -> None:
    con = abrir()
    previo = obtener(id_)
    if previo is None:
        raise KeyError(id_)
    nuevo_extra = {**(previo.get("extra") or {}), **(extra or {})}
    con.execute("UPDATE recursos SET estado=?, ruta=COALESCE(?, ruta), bytes=COALESCE(?, bytes), extra=?, "
                "actualizado=? WHERE id=?", (estado, ruta, bytes_, json.dumps(nuevo_extra, ensure_ascii=False),
                                              time.strftime("%Y-%m-%d %H:%M:%S"), id_))


def _dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    try:
        d["extra"] = json.loads(d["extra"]) if d.get("extra") else {}
    except ValueError:
        d["extra"] = {}
    return d


def obtener(id_: str) -> dict | None:
    r = abrir().execute("SELECT * FROM recursos WHERE id=?", (id_,)).fetchone()
    return _dict(r) if r else None


def listar(fuente: str = "", tipo: str = "", estado: str = "", limite: int = 0) -> list[dict]:
    sql, args = "SELECT * FROM recursos WHERE 1=1", []
    for col, val in (("fuente", fuente), ("tipo", tipo), ("estado", estado)):
        if val:
            valores = [v for v in val.split(",") if v]
            sql += f" AND {col} IN ({','.join('?' * len(valores))})"
            args += valores
    sql += " ORDER BY fuente, tipo, clave" + (f" LIMIT {int(limite)}" if limite else "")
    return [_dict(r) for r in abrir().execute(sql, args)]


def buscar(texto: str = "", tipo: str = "", fuente: str = "", estados: str = "descargado,aprobado",
           limite: int = 30) -> list[dict]:
    """Búsqueda por palabras (todas deben aparecer en nombre, clave, categorías o etiquetas)."""
    sql, args = "SELECT * FROM recursos WHERE 1=1", []
    for col, val in (("tipo", tipo), ("fuente", fuente), ("estado", estados)):
        if val:
            valores = [v for v in val.split(",") if v]
            sql += f" AND {col} IN ({','.join('?' * len(valores))})"
            args += valores
    for palabra in texto.lower().split():
        sql += " AND lower(coalesce(nombre,'')||' '||coalesce(clave,'')||' '||coalesce(categorias,'')||' '||" \
               "coalesce(etiquetas,'')) LIKE ?"
        args.append(f"%{palabra}%")
    sql += f" ORDER BY CASE estado WHEN 'aprobado' THEN 0 ELSE 1 END, clave LIMIT {int(limite)}"
    return [_dict(r) for r in abrir().execute(sql, args)]


def resumen() -> dict:
    filas = abrir().execute("SELECT fuente, tipo, estado, COUNT(*) n, SUM(bytes) b FROM recursos "
                            "GROUP BY fuente, tipo, estado ORDER BY fuente, tipo").fetchall()
    salida: dict = {}
    total = 0
    for f in filas:
        d = salida.setdefault(f["fuente"], {}).setdefault(f["tipo"], {})
        d[f["estado"]] = {"n": f["n"], "gb": round((f["b"] or 0) / 1e9, 2)}
        total += f["b"] or 0
    return {"por_fuente": salida, "gb_total": round(total / 1e9, 2)}


def bytes_en_drive() -> int:
    r = abrir().execute("SELECT SUM(bytes) FROM recursos WHERE estado IN ('descargado','aprobado')").fetchone()
    return int(r[0] or 0)
