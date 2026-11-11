"""Pesos de los modelos de IA: se descargan una vez y quedan en Drive.

Orden para tener un modelo en el disco rápido de la sesión (<LOCAL>/modelos/<nombre>):
  1. Ya está en el disco local → listo.
  2. Hay copia completa en Drive (<DRIVE>/modelos_ia/<nombre>) → se copia (más rápido que internet).
  3. Se descarga de Hugging Face y se guarda la copia en Drive para las próximas sesiones.

Una carpeta solo cuenta como completa si tiene el archivo `.completo` (evita usar copias a medias).
Este módulo solo usa la librería estándar más huggingface_hub (presente en los entornos de IA).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import config

MARCA = ".completo"


def _nombre(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def _completa(p: Path) -> bool:
    return (p / MARCA).exists()


def _copiar(origen: Path, destino: Path) -> None:
    tmp = destino.with_name(destino.name + ".parcial")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(origen, tmp)
    if destino.exists():
        shutil.rmtree(destino)
    tmp.rename(destino)


def asegurar(repo_id: str, registro=print, permitir: list[str] | None = None) -> Path:
    local = config.ruta_local("modelos", _nombre(repo_id))
    if _completa(local):
        return local
    en_drive = config.ruta_drive("modelos_ia", _nombre(repo_id))
    if _completa(en_drive):
        registro(f"Modelo {repo_id}: copiando desde Drive…")
        local.parent.mkdir(parents=True, exist_ok=True)
        _copiar(en_drive, local)
        return local

    from huggingface_hub import snapshot_download

    registro(f"Modelo {repo_id}: descargando de Hugging Face…")
    local.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id, local_dir=str(local), token=os.environ.get("HF_TOKEN") or None,
                      allow_patterns=permitir)
    (local / MARCA).touch()
    if config.DRIVE.exists():
        try:
            registro(f"Modelo {repo_id}: guardando copia en Drive para las próximas sesiones…")
            en_drive.parent.mkdir(parents=True, exist_ok=True)
            _copiar(local, en_drive)
        except OSError as e:
            registro(f"⚠️  No se pudo guardar la copia en Drive ({e}); se descargará de nuevo la próxima vez.")
    return local


def archivo_whisper(nombre: str, registro=print) -> Path:
    """Carpeta con el .pt de Whisper (openai-whisper), persistida en Drive igual que los modelos."""
    local = config.ruta_local("modelos", "whisper")
    local.mkdir(parents=True, exist_ok=True)
    pt = local / f"{nombre}.pt"
    if pt.exists():
        return local
    en_drive = config.ruta_drive("modelos_ia", "whisper", f"{nombre}.pt")
    if en_drive.exists() and en_drive.stat().st_size > 1_000_000:
        registro(f"Whisper {nombre}: copiando desde Drive…")
        shutil.copyfile(en_drive, pt)
    return local


def guardar_whisper(nombre: str, registro=print) -> None:
    pt = config.ruta_local("modelos", "whisper", f"{nombre}.pt")
    en_drive = config.ruta_drive("modelos_ia", "whisper", f"{nombre}.pt")
    if pt.exists() and config.DRIVE.exists() and not en_drive.exists():
        try:
            en_drive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pt, en_drive)
            registro(f"Whisper {nombre}: copia guardada en Drive.")
        except OSError as e:
            registro(f"⚠️  No se pudo guardar Whisper en Drive ({e}).")
