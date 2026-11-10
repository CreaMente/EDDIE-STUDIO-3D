"""Instalación y ejecución de Blender en modo sin interfaz."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from . import config, sistema


PAQUETES_SISTEMA = ["libegl1", "libgl1", "libxi6", "libxrender1", "libxkbcommon0", "libsm6",
                    "libxxf86vm1", "libxfixes3", "libxext6", "libxkbcommon-x11-0"]
LIBRERIAS_CLAVE = ["libEGL.so.1", "libXi.so.6", "libXrender.so.1", "libxkbcommon.so.0", "libSM.so.6"]


def dependencias_sistema(registro=print) -> list[str]:
    """Instala las librerías del sistema que Blender necesita (EGL para EEVEE sin pantalla).
    Devuelve las que faltaban."""
    try:
        cache = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        cache = ""
    faltan = [lib for lib in LIBRERIAS_CLAVE if lib not in cache]
    if faltan:
        registro(f"Instalando librerías del sistema para Blender ({', '.join(faltan)})…")
        sudo = [] if os.geteuid() == 0 else ["sudo"]
        subprocess.run(sudo + ["apt-get", "update", "-qq"], check=False, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r = subprocess.run(sudo + ["apt-get", "install", "-y", "-qq", "--no-install-recommends",
                                   *PAQUETES_SISTEMA], capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            registro("⚠️  apt-get falló: " + r.stderr.strip()[-500:])
    return faltan


def instalar(registro=print) -> Path:
    """Instala Blender en el disco local.

    Orden: ya instalado → copia guardada en Drive → descarga oficial (y se guarda en Drive).
    """
    destino = config.ruta_local("blender")
    exe = destino / f"blender-{config.BLENDER_VERSION}-linux-x64" / "blender"
    if exe.exists():
        return exe
    destino.mkdir(parents=True, exist_ok=True)
    cache = config.ruta_drive("sistema", config.BLENDER_ARCHIVO)
    archivo = config.ruta_local("tmp", config.BLENDER_ARCHIVO)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 100_000_000:
        registro(f"Blender: copiando desde Drive ({cache.stat().st_size / 1e6:.0f} MB)…")
        shutil.copyfile(cache, archivo)
    else:
        registro(f"Blender: descargando {config.BLENDER_URL} …")
        tmp = archivo.with_suffix(".parcial")
        with urllib.request.urlopen(config.BLENDER_URL, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=8 * 1024 * 1024)
        tmp.replace(archivo)
        if config.DRIVE.exists():
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archivo, cache)
                registro("Blender: copia guardada en Drive para las próximas sesiones.")
            except OSError as e:
                registro(f"Blender: no se pudo guardar copia en Drive ({e}); se descargará de nuevo la próxima vez.")
    registro("Blender: descomprimiendo…")
    with tarfile.open(archivo) as t:
        try:
            t.extractall(destino, filter="tar")
        except TypeError:  # Python sin filtros de extracción
            t.extractall(destino)
    archivo.unlink(missing_ok=True)
    if not exe.exists():
        raise RuntimeError(f"Blender no quedó en {exe}")
    return exe


def comando(script: str | Path, args: list[str] | None = None, blend: str | Path | None = None,
            factory: bool = True) -> list[str]:
    """Arma la línea de comando para correr un script de Blender sin interfaz."""
    exe = sistema.blender_bin()
    if not exe:
        raise RuntimeError("Blender no está instalado. Ejecuta estudio.blender.instalar().")
    c = [str(exe), "-b"]
    if blend:
        c.append(str(blend))
    if factory and not blend:
        c.append("--factory-startup")
    c += ["--python-exit-code", "1", "-P", str(script)]
    if args:
        c += ["--", *args]
    return c


def ejecutar(script: str | Path, args: list[str] | None = None, blend: str | Path | None = None,
             timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(comando(script, args, blend), capture_output=True, text=True, timeout=timeout)


def script(nombre: str) -> Path:
    """Ruta de un script de blender_scripts/ del repo."""
    p = config.REPO / "blender_scripts" / nombre
    if not p.exists():
        raise FileNotFoundError(p)
    return p
