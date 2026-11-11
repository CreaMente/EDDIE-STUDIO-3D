"""Claves de API y clave del estudio.

Las claves viven en Mi unidad/EDDIE_PRIVADO/claves.json (fuera de la carpeta de trabajo, que puede
estar compartida) y/o en Colab Secrets.
Nunca se escriben en el repositorio ni se imprimen completas.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from . import config

# Nombre → descripción. El orden es el de docs/03_APIS_Y_CLAVES.md.
CLAVES_CONOCIDAS: dict[str, str] = {
    "HF_TOKEN": "Hugging Face (modelos locales)",
    "GITHUB_TOKEN": "GitHub (repo privado)",
    "SKETCHFAB_API_TOKEN": "Sketchfab (modelos 3D)",
    "SI_API_KEY": "Smithsonian / api.data.gov (modelos 3D CC0)",
    "FREESOUND_API_KEY": "Freesound (efectos de sonido)",
    "FREESOUND_CLIENT_ID": "Freesound OAuth2",
    "FREESOUND_CLIENT_SECRET": "Freesound OAuth2",
    "FREESOUND_REFRESH_TOKEN": "Freesound OAuth2 (lo genera el sistema)",
    "BLENDERKIT_API_KEY": "BlenderKit (opcional)",
    "NGROK_AUTHTOKEN": "ngrok (opcional; sin él se usa Cloudflare)",
    "OPENVERSE_CLIENT_ID": "Openverse (opcional)",
    "OPENVERSE_CLIENT_SECRET": "Openverse (opcional)",
    "GEMINI_API_KEY": "Gemini (opcional, revisión visual automática)",
}

OBLIGATORIAS = ["HF_TOKEN"]


def archivo_claves() -> Path:
    return config.ruta_privada("claves.json")


def _proteger(ruta: Path) -> None:
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass  # Drive FUSE puede no soportar chmod; no es crítico.


def leer_archivo() -> dict[str, str]:
    p = archivo_claves()
    if not p.exists():
        return {}
    try:
        datos = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: str(v).strip() for k, v in datos.items() if isinstance(v, (str, int)) and str(v).strip()}


def guardar(nuevas: dict[str, str]) -> list[str]:
    """Combina las claves nuevas (no vacías) con las existentes. Devuelve los nombres actualizados."""
    actuales = leer_archivo()
    cambiadas = []
    for k, v in nuevas.items():
        v = (v or "").strip()
        if v and actuales.get(k) != v:
            actuales[k] = v
            cambiadas.append(k)
    p = archivo_claves()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(actuales, indent=2, ensure_ascii=False), encoding="utf-8")
    _proteger(tmp)
    tmp.replace(p)
    return cambiadas


def leer_colab_secrets(nombres) -> dict[str, str]:
    """Solo funciona dentro del kernel de Colab."""
    try:
        from google.colab import userdata  # type: ignore
    except ImportError:
        return {}
    encontradas = {}
    for n in nombres:
        try:
            v = userdata.get(n)
        except Exception:  # SecretNotFoundError, NotebookAccessError, etc.
            continue
        if v:
            encontradas[n] = str(v).strip()
    return encontradas


def cargar_todas() -> dict[str, str]:
    """Archivo de Drive + Colab Secrets (gana Colab Secrets) + variables de entorno ya puestas."""
    todas = leer_archivo()
    todas.update(leer_colab_secrets(list(CLAVES_CONOCIDAS) + list(todas)))
    for n in CLAVES_CONOCIDAS:
        if os.environ.get(n) and n not in todas:
            todas[n] = os.environ[n]
    return todas


def exportar_a_entorno(claves: dict[str, str]) -> None:
    for k, v in claves.items():
        os.environ[k] = v


def enmascarar(valor: str) -> str:
    if len(valor) <= 8:
        return "••••"
    return f"{valor[:3]}…{valor[-3:]}"


def resumen(claves: dict[str, str]) -> list[dict]:
    """Qué claves hay, sin revelar valores."""
    filas = []
    for n, desc in CLAVES_CONOCIDAS.items():
        filas.append({
            "nombre": n,
            "descripcion": desc,
            "presente": n in claves,
            "obligatoria": n in OBLIGATORIAS,
        })
    return filas


def clave_estudio(renovar: bool = False) -> str:
    """Clave que protege el servidor MCP.

    Con renovar=True (cada inicio del estudio) se genera una nueva: igual que la dirección del túnel,
    cambia en cada sesión, así una clave compartida por error deja de servir al reiniciar.
    Se guarda en Drive privado para que la sesión actual la reutilice (p. ej., si se reabre el túnel)."""
    p = config.ruta_privada("clave_estudio.txt")
    if p.exists() and not renovar:
        v = p.read_text(encoding="utf-8").strip()
        if len(v) >= 32:
            return v
    v = secrets.token_urlsafe(32)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(v, encoding="utf-8")
    _proteger(p)
    return v
