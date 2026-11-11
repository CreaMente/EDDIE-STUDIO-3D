"""Convierte un link de carpeta de Google Drive en su ruta dentro de Colab.

En Colab, Drive se monta en /content/drive y cada archivo expone su id en el atributo extendido
`user.drive.id`. Se busca la carpeta por ese atributo. Si no aparece (por ejemplo, una carpeta
compartida contigo que no está en "Mi unidad"), se usa la API de Drive para reconstruir la ruta.
"""

from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path

RAIZ = Path("/content/drive")
PATRONES_ID = [
    r"/folders/([A-Za-z0-9_-]{10,})",
    r"[?&]id=([A-Za-z0-9_-]{10,})",
    r"^([A-Za-z0-9_-]{20,})$",
]


class CarpetaNoEncontrada(RuntimeError):
    pass


def extraer_id(link: str) -> str | None:
    link = (link or "").strip()
    for patron in PATRONES_ID:
        m = re.search(patron, link)
        if m:
            return m.group(1)
    return None


def _id_de(ruta: Path) -> str | None:
    try:
        return os.getxattr(ruta, "user.drive.id").decode().strip()
    except (OSError, AttributeError):
        return None


def buscar_por_atributo(fid: str, raices: list[Path], profundidad: int = 5,
                        max_carpetas: int = 20000) -> Path | None:
    """Búsqueda en anchura por carpetas (solo carpetas, limitada para no tardar)."""
    cola = deque((r, 0) for r in raices if r.exists())
    vistas = 0
    while cola and vistas < max_carpetas:
        actual, nivel = cola.popleft()
        vistas += 1
        if _id_de(actual) == fid:
            return actual
        if nivel >= profundidad:
            continue
        try:
            hijos = sorted((h for h in actual.iterdir() if h.is_dir()), key=lambda h: h.name)
        except OSError:
            continue
        cola.extend((h, nivel + 1) for h in hijos)
    return None


def buscar_por_api(fid: str) -> Path | None:
    """Reconstruye la ruta con la API de Drive (pide autorización en Colab)."""
    try:
        from google.colab import auth  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        return None
    auth.authenticate_user()
    svc = build("drive", "v3", cache_discovery=False)
    partes = []
    actual = fid
    for _ in range(40):
        f = svc.files().get(fileId=actual, fields="id,name,parents,driveId",
                            supportsAllDrives=True).execute()
        padres = f.get("parents") or []
        if not padres:
            if f.get("driveId"):  # unidad compartida
                base = RAIZ / "Shareddrives" / svc.drives().get(driveId=f["driveId"]).execute()["name"]
            elif f["id"] == svc.files().get(fileId="root", fields="id").execute()["id"]:
                base = RAIZ / "MyDrive"
            else:
                return None  # compartida contigo sin acceso directo en "Mi unidad"
            return base.joinpath(*reversed(partes))
        partes.append(f["name"])
        actual = padres[0]
    return None


def resolver(link: str, crear_si_vacio: str = "EDDIE_STUDIO") -> Path:
    """Link de carpeta → ruta montada. Sin link: Mi unidad/<crear_si_vacio>."""
    if not (link or "").strip():
        p = RAIZ / "MyDrive" / crear_si_vacio
        p.mkdir(parents=True, exist_ok=True)
        return p
    fid = extraer_id(link)
    if not fid:
        raise CarpetaNoEncontrada(f"No reconozco el link de Drive: {link!r}. Copia el link de la carpeta "
                                  "(https://drive.google.com/drive/folders/…).")
    # Carpetas con acceso directo: Colab las expone en .shortcut-targets-by-id/<id>/<nombre>.
    atajo = RAIZ / ".shortcut-targets-by-id" / fid
    hijos = [h for h in atajo.iterdir() if h.is_dir()] if atajo.is_dir() else []
    p = hijos[0] if len(hijos) == 1 else None
    if p is None:
        p = buscar_por_atributo(fid, [RAIZ / "MyDrive", RAIZ / "Shareddrives"])
    if p is None:
        p = buscar_por_api(fid)
    if p is None or not p.exists():
        raise CarpetaNoEncontrada(
            "No encontré esa carpeta en tu Drive montado. Si es una carpeta compartida contigo, en Drive haz "
            "clic derecho → Organizar → «Agregar acceso directo» a Mi unidad, y vuelve a ejecutar.")
    return p
