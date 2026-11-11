"""Descargas seguras: reanudables, verificadas, sin sobrescribir nunca, con control de espacio.

- Se escribe a «<archivo>.parcial» y se renombra al terminar (un corte nunca deja un archivo a medias
  con el nombre final). Si se corta, la siguiente vez continúa desde donde quedó (Range).
- Si el archivo final ya existe con el tamaño esperado, no se vuelve a bajar (no se sobrescribe).
- Se verifica tamaño y md5/sha256 cuando la fuente los publica.
- Antes de cada archivo se revisa el espacio: margen libre en Drive y en el disco local (Drive en Colab
  sube en segundo plano desde una caché local: si el disco local se llena, se espera a que se vacíe).
"""

from __future__ import annotations

import hashlib
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config

CABECERAS = {"User-Agent": "EDDIE-STUDIO-3D/1.0 (estudio de video personal)"}
MARGEN_DRIVE_GB = 5.0
MARGEN_LOCAL_GB = 15.0
_ultimo_por_host: dict[str, float] = {}
_candado = threading.Lock()
PAUSA_HOST = {"ambientcg.com": 0.25, "api.polyhaven.com": 0.05, "studio.blender.org": 1.0, "zenodo.org": 1.0}


class SinEspacio(Exception):
    pass


def _ritmo(url: str) -> None:
    host = urllib.parse.urlparse(url).netloc
    pausa = PAUSA_HOST.get(host, 0.1)
    with _candado:
        espera = _ultimo_por_host.get(host, 0) + pausa - time.time()
        _ultimo_por_host[host] = max(time.time(), _ultimo_por_host.get(host, 0) + pausa)
    if espera > 0:
        time.sleep(espera)


def libre_gb(ruta: Path) -> float | None:
    """GB libres donde está «ruta»; None si el sistema de archivos no lo informa."""
    p = Path(ruta)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        uso = shutil.disk_usage(p)
    except OSError:
        return None
    return uso.free / 1e9 if uso.total > 1e9 else None


_cuota = {"t": 0.0, "libre": None}


def drive_libre_gb() -> float | None:
    """Cuota libre REAL de Drive (API), consultada como mucho cada 5 min. El espacio del montaje
    /content/drive es el disco de la máquina de Colab, no Drive: no sirve para esto."""
    if time.time() - _cuota["t"] > 300:
        from ..drive import cuota
        q = cuota()
        _cuota.update({"t": time.time(), "libre": (q or {}).get("libre_gb")})
    return _cuota["libre"]


def esperar_espacio(destino: Path, necesarios: int = 0, registro=print) -> None:
    """Drive con margen (si no, SinEspacio) y disco local con margen (si no, espera a que Drive suba)."""
    libre = drive_libre_gb()
    if libre is not None and libre - necesarios / 1e9 < MARGEN_DRIVE_GB:
        raise SinEspacio(f"Quedan {libre:.1f} GB en la cuota de Drive (margen {MARGEN_DRIVE_GB} GB).")
    local = Path("/content") if Path("/content").exists() else config.LOCAL
    esperado = 0
    while (libre_gb(local) or 1e9) < MARGEN_LOCAL_GB and esperado < 1800:
        if esperado == 0:
            registro(f"   disco local con {libre_gb(local):.1f} GB libres: espero a que Drive termine de subir…")
        time.sleep(30)
        esperado += 30


def _hash(ruta: Path, algoritmo: str) -> str:
    h = hashlib.new(algoritmo)
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(8 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def bajar(url: str, destino: Path, tam: int | None = None, md5: str | None = None, sha256: str | None = None,
          reintentos: int = 5, registro=print) -> int:
    """Descarga url → destino. Devuelve los bytes del archivo final. No sobrescribe un archivo existente."""
    destino = Path(destino)
    if destino.exists() and (tam is None or destino.stat().st_size == tam):
        return destino.stat().st_size
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe con otro tamaño ({destino.stat().st_size} ≠ {tam}); "
                              "no se sobrescribe. Revísalo a mano.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    esperar_espacio(destino, tam or 0, registro)
    parcial = destino.with_name(destino.name + ".parcial")
    error: Exception | None = None
    for intento in range(reintentos):
        try:
            _ritmo(url)
            ya = parcial.stat().st_size if parcial.exists() else 0
            if tam and ya > tam:
                parcial.unlink()
                ya = 0
            cab = dict(CABECERAS)
            if ya:
                cab["Range"] = f"bytes={ya}-"
            req = urllib.request.Request(url, headers=cab)
            with urllib.request.urlopen(req, timeout=120) as r:
                if ya and r.status != 206:  # el servidor no admite continuar: se empieza de nuevo
                    ya = 0
                with open(parcial, "ab" if ya else "wb") as f:
                    shutil.copyfileobj(r, f, length=4 << 20)
            real = parcial.stat().st_size
            if tam and real != tam:
                raise IOError(f"tamaño {real} ≠ {tam}")
            if md5 and _hash(parcial, "md5") != md5.lower():
                parcial.unlink()
                raise IOError("md5 no coincide (archivo dañado): se baja de nuevo")
            if sha256 and _hash(parcial, "sha256") != sha256.lower():
                parcial.unlink()
                raise IOError("sha256 no coincide (archivo dañado): se baja de nuevo")
            parcial.replace(destino)
            return real
        except urllib.error.HTTPError as e:
            error = e
            if e.code in (401, 403, 404, 410):
                break  # no tiene sentido reintentar
            time.sleep(2 ** intento)
        except (OSError, IOError) as e:
            error = e
            time.sleep(2 ** intento)
    raise IOError(f"No se pudo bajar {url}: {error}")


def sha256_de(ruta: Path) -> str:
    return _hash(Path(ruta), "sha256")
