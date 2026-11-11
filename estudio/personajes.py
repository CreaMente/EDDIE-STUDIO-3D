"""Personajes humanos con MPFB (MakeHuman para Blender), sin interfaz gráfica.

- La extensión MPFB se instala en Blender desde extensions.blender.org (GPL).
- Los paquetes de recursos CC0 de MakeHuman (piel, ojos, ropa, cabello…) se descargan UNA vez a
  Drive (<DRIVE>/biblioteca/_paquetes/mpfb/) y en cada sesión se extraen en la carpeta de datos de MPFB.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from . import config, sistema

BASE = "https://files2.makehumancommunity.org/asset_packs"
# Solo paquetes CC0 (uso comercial sin atribución).
PAQUETES_MPFB = {
    "makehuman_system_assets": f"{BASE}/makehuman_system_assets/makehuman_system_assets_cc0.zip",
    "skins01": f"{BASE}/skins01/skins01_cc0.zip",
    "eyebrows01": f"{BASE}/eyebrows01/eyebrows01_cc0.zip",
    "eyelashes01": f"{BASE}/eyelashes01/eyelashes01_cc0.zip",
    "hair01": f"{BASE}/hair01/hair01_cc0.zip",
    "shirts01": f"{BASE}/shirts01/shirts01_cc0.zip",
    "pants01": f"{BASE}/pants01/pants01_cc0.zip",
    "shoes01": f"{BASE}/shoes01/shoes01_cc0.zip",
}


def carpeta_extensiones() -> Path:
    return Path(os.environ["BLENDER_USER_RESOURCES"]) / "extensions"


def carpeta_datos_mpfb() -> Path:
    """Carpeta de datos de usuario de MPFB (donde viven los paquetes instalados)."""
    return carpeta_extensiones() / ".user" / "blender_org" / "mpfb" / "data"


def mpfb_instalado() -> bool:
    return (carpeta_extensiones() / "blender_org" / "mpfb" / "__init__.py").exists()


def instalar_mpfb(registro=print) -> None:
    if mpfb_instalado():
        return
    exe = sistema.blender_bin()
    if not exe:
        raise RuntimeError("Blender no está instalado")
    registro("MPFB: instalando la extensión desde extensions.blender.org…")
    r = subprocess.run([str(exe), "--online-mode", "-c", "extension", "install", "-s", "-e", "mpfb"],
                       capture_output=True, text=True, timeout=600)
    if not mpfb_instalado():
        raise RuntimeError("No se pudo instalar MPFB:\n" + (r.stdout + r.stderr)[-2000:])
    registro("MPFB: instalada.")


def _descargar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".parcial")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EDDIE-STUDIO-3D)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=8 * 1024 * 1024)
    tmp.replace(destino)


def _extraer_paquete(zip_path: Path, destino: Path) -> None:
    """Igual que MPFB: el zip contiene una raíz con 'packs' (a veces dentro de una carpeta extra)."""
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            for m in zf.infolist():
                if not m.filename.startswith("__MACOSX"):
                    zf.extract(m, tmp)
        raiz = Path(tmp)
        if "packs" not in os.listdir(raiz):
            dirs = [d for d in raiz.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(dirs) == 1 and (dirs[0] / "packs").exists():
                raiz = dirs[0]
        destino.mkdir(parents=True, exist_ok=True)
        for e in raiz.iterdir():
            if e.name.startswith("."):
                continue
            if e.is_dir():
                shutil.copytree(e, destino / e.name, dirs_exist_ok=True)
            else:
                shutil.copy2(e, destino / e.name)


def instalar_paquetes(registro=print, nombres: list[str] | None = None) -> list[str]:
    """Descarga (una vez, a Drive) y extrae los paquetes CC0 en MPFB. Devuelve los instalados."""
    datos = carpeta_datos_mpfb()
    marcas = datos / ".paquetes_eddie"
    marcas.mkdir(parents=True, exist_ok=True)
    instalados = []
    for nombre, url in PAQUETES_MPFB.items():
        if nombres and nombre not in nombres:
            continue
        if (marcas / nombre).exists():
            instalados.append(nombre)
            continue
        zip_drive = config.ruta_drive("biblioteca", "_paquetes", "mpfb", Path(url).name)
        if not zip_drive.exists():
            registro(f"MPFB: descargando paquete {nombre} (se guarda en Drive)…")
            _descargar(url, zip_drive)
        registro(f"MPFB: instalando paquete {nombre}…")
        _extraer_paquete(zip_drive, datos)
        (marcas / nombre).touch()
        instalados.append(nombre)
    return instalados


def preparar(registro=print) -> dict:
    instalar_mpfb(registro)
    paquetes = instalar_paquetes(registro)
    return {"mpfb": True, "paquetes": paquetes, "datos": str(carpeta_datos_mpfb())}
