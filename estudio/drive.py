"""Conexión a una carpeta de Google Drive por su URL, aunque sea de otra cuenta.

Colab solo puede montar el Drive de la cuenta con la que se abrió Colab. Para usar una carpeta de
otra cuenta:
  1. La cuenta dueña comparte la carpeta con la cuenta de Colab como **Editor**.
  2. Este módulo (con la API de Drive y la autorización de Colab) verifica el acceso, crea un acceso
     directo a la carpeta en "Mi unidad" de la cuenta de Colab y monta Drive.
  3. La carpeta aparece en /content/drive/.shortcut-targets-by-id/<id>/<nombre> y el sistema la usa
     como una carpeta normal.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from pathlib import Path

RAIZ = Path("/content/drive")
TIPO_CARPETA = "application/vnd.google-apps.folder"
TIPO_ATAJO = "application/vnd.google-apps.shortcut"
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


# ───────────────────────── API de Drive ─────────────────────────

def servicio():
    """Cliente de la API de Drive con la autorización de la cuenta de Colab."""
    from google.colab import auth  # type: ignore
    from googleapiclient.discovery import build  # type: ignore

    auth.authenticate_user()
    # Aviso inofensivo de la librería en cada llamada; se silencia para no ensuciar la salida.
    logging.getLogger("google_auth_httplib2").setLevel(logging.ERROR)
    return build("drive", "v3", cache_discovery=False)


def cuenta_actual(svc) -> str:
    return svc.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]


def revisar_carpeta(svc, fid: str, correo: str) -> dict:
    """Comprueba que la cuenta de Colab vea la carpeta y pueda escribir en ella."""
    from googleapiclient.errors import HttpError  # type: ignore

    try:
        f = svc.files().get(fileId=fid, supportsAllDrives=True,
                            fields="id,name,mimeType,driveId,owners(emailAddress,me),"
                                   "capabilities(canAddChildren)").execute()
    except HttpError as e:
        if e.resp.status in (403, 404):
            raise CarpetaNoEncontrada(
                f"La cuenta de Colab ({correo}) no tiene acceso a esa carpeta.\n"
                f"Desde la cuenta dueña de la carpeta: clic derecho → Compartir → agrega {correo} "
                "como «Editor» → Enviar. Luego vuelve a ejecutar la celda.") from e
        raise
    if f.get("mimeType") != TIPO_CARPETA:
        raise CarpetaNoEncontrada("Esa URL no es de una carpeta. Copia el link de la carpeta (…/drive/folders/…).")
    if not f.get("capabilities", {}).get("canAddChildren"):
        raise CarpetaNoEncontrada(
            f"La cuenta de Colab ({correo}) puede ver la carpeta pero no escribir en ella.\n"
            f"Desde la cuenta dueña: Compartir → cambia {correo} a «Editor».")
    return f


def es_publica(svc, fid: str) -> str | None:
    """Devuelve el rol público ('writer', 'reader'…) si la carpeta está abierta a cualquiera con el link."""
    try:
        perms = svc.permissions().list(fileId=fid, supportsAllDrives=True,
                                       fields="permissions(type,role)").execute().get("permissions", [])
    except Exception:
        return None
    for p in perms:
        if p.get("type") == "anyone":
            return p.get("role")
    return None


def asegurar_atajo(svc, carpeta: dict) -> None:
    """Crea en 'Mi unidad' de la cuenta de Colab un acceso directo a la carpeta (si no existe)."""
    q = f"mimeType='{TIPO_ATAJO}' and trashed=false and 'root' in parents"
    token = None
    while True:
        r = svc.files().list(q=q, fields="nextPageToken,files(id,shortcutDetails(targetId))",
                             pageToken=token, pageSize=200).execute()
        if any(a.get("shortcutDetails", {}).get("targetId") == carpeta["id"] for a in r.get("files", [])):
            return
        token = r.get("nextPageToken")
        if not token:
            break
    svc.files().create(body={
        "name": carpeta["name"],
        "mimeType": TIPO_ATAJO,
        "parents": ["root"],
        "shortcutDetails": {"targetId": carpeta["id"]},
    }, fields="id").execute()


def ruta_propia(svc, fid: str) -> Path | None:
    """Ruta montada de una carpeta que está en 'Mi unidad' o en una unidad compartida."""
    partes, actual = [], fid
    raiz = svc.files().get(fileId="root", fields="id").execute()["id"]
    for _ in range(40):
        if actual == raiz:
            return (RAIZ / "MyDrive").joinpath(*reversed(partes))
        f = svc.files().get(fileId=actual, fields="id,name,parents,driveId", supportsAllDrives=True).execute()
        padres = f.get("parents") or []
        if not padres:
            if f.get("driveId"):
                nombre = svc.drives().get(driveId=f["driveId"]).execute()["name"]
                return (RAIZ / "Shareddrives" / nombre).joinpath(*reversed(partes))
            return None
        partes.append(f["name"])
        actual = padres[0]
    return None


# ───────────────────────── montaje ─────────────────────────

def _id_de(ruta: Path) -> str | None:
    try:
        return os.getxattr(ruta, "user.drive.id").decode().strip()
    except (OSError, AttributeError):
        return None


def buscar_por_atributo(fid: str, raices: list[Path], profundidad: int = 5,
                        max_carpetas: int = 20000) -> Path | None:
    """Búsqueda en anchura por carpetas montadas usando el atributo user.drive.id."""
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


def _por_atajo(fid: str) -> Path | None:
    atajo = RAIZ / ".shortcut-targets-by-id" / fid
    try:
        hijos = [h for h in atajo.iterdir() if h.is_dir()] if atajo.is_dir() else []
    except OSError:
        return None
    return hijos[0] if len(hijos) == 1 else None


def montar(forzar: bool = False) -> None:
    from google.colab import drive  # type: ignore

    if forzar or not (RAIZ / "MyDrive").is_dir():
        drive.mount(str(RAIZ), force_remount=forzar)


def conectar_por_url(url: str, registro=print) -> Path:
    """URL de carpeta (de cualquier cuenta) → ruta montada lista para usar."""
    fid = extraer_id(url)
    if not fid:
        raise CarpetaNoEncontrada(f"No reconozco esa URL de Drive: {url!r}. "
                                  "Copia el link de la carpeta (https://drive.google.com/drive/folders/…).")
    svc = servicio()
    correo = cuenta_actual(svc)
    registro(f"Cuenta de Colab: {correo}")
    carpeta = revisar_carpeta(svc, fid, correo)
    registro(f"Carpeta encontrada: «{carpeta['name']}» (con permiso de escritura)")
    rol = es_publica(svc, fid)
    if rol:
        registro(f"⚠️  La carpeta es pública para cualquiera con el link (rol: {rol}). "
                 "Recomendado: Compartir → Acceso general → «Restringido».")

    propia = any(o.get("me") for o in carpeta.get("owners", [])) or bool(carpeta.get("driveId"))
    if propia:
        montar()
        p = ruta_propia(svc, fid)
        if p and p.exists():
            return p
    asegurar_atajo(svc, carpeta)
    montar()
    # Drive tarda unos segundos en reflejar un acceso directo nuevo en el montaje.
    for intento in range(36):
        p = _por_atajo(fid) or (buscar_por_atributo(fid, [RAIZ / "MyDrive"], profundidad=1) if intento % 6 == 5 else None)
        if p:
            return p
        if intento == 12:
            registro("Esperando a que Drive muestre la carpeta… (remontando)")
            montar(forzar=True)
        time.sleep(5)
    raise CarpetaNoEncontrada(
        "Drive no mostró la carpeta a tiempo. Vuelve a ejecutar la celda; si persiste: "
        "Entorno de ejecución → Desconectar y borrar el entorno de ejecución, y ejecuta de nuevo.")


def resolver(link: str, crear_si_vacio: str = "EDDIE_STUDIO") -> Path:
    """Compatibilidad: sin link usa Mi unidad/<crear_si_vacio> de la cuenta de Colab."""
    if not (link or "").strip():
        montar()
        p = RAIZ / "MyDrive" / crear_si_vacio
        p.mkdir(parents=True, exist_ok=True)
        return p
    return conectar_por_url(link)
