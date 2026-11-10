"""Genera colab/EDDIE_STUDIO.ipynb (editar aquí y volver a ejecutar, no a mano)."""

import json
from pathlib import Path

REPO = "CreaMente/EDDIE-STUDIO-3D"
RAMA = "claude/happy-shannon-dzepo9"


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.strip("\n").splitlines(True)}


def code(texto, titulo=None):
    meta = {"cellView": "form"} if titulo else {}
    return {"cell_type": "code", "execution_count": None, "metadata": meta, "outputs": [],
            "source": texto.strip("\n").splitlines(True)}


INTRO = """
# 🎬 EDDIE STUDIO 3D

Estudio de videos 3D renderizados en Blender, dirigido por **Antigravity** a través de un túnel.

**Antes de empezar:** `Entorno de ejecución → Cambiar tipo de entorno de ejecución` → elige la GPU
**RTX PRO 6000** (o la más potente disponible).

| Paso | Cuándo |
|---|---|
| **1. Claves** | Solo la primera vez, o cuando agregues una clave nueva |
| **2. Iniciar** | Cada vez que vayas a trabajar. Al final muestra la dirección y la clave para Antigravity |
| **3. Detener** | Opcional: apaga el servidor y el túnel |

La celda 2 se queda corriendo a propósito: mantiene viva la sesión y muestra lo que hace Antigravity.
"""

CLAVES = r'''
#@title 🔑 1. Claves de API (solo la primera vez)
#@markdown Las claves se piden en campos ocultos y se guardan en **tu Drive privado**
#@markdown (`EDDIE_STUDIO/privado/claves.json`). No quedan escritas en esta libreta.
#@markdown Pulsa **Enter** sin escribir nada para saltar una clave.
CAMBIAR_CLAVES_EXISTENTES = False #@param {type:"boolean"}

import json, os, pathlib, getpass
from google.colab import drive
if not os.path.isdir("/content/drive/MyDrive"):
    drive.mount("/content/drive")

CLAVES = [
    ("HF_TOKEN", "Hugging Face (obligatoria)"),
    ("GITHUB_TOKEN", "GitHub (si el repo es privado)"),
    ("SKETCHFAB_API_TOKEN", "Sketchfab"),
    ("SI_API_KEY", "Smithsonian / api.data.gov"),
    ("FREESOUND_API_KEY", "Freesound: API key"),
    ("FREESOUND_CLIENT_ID", "Freesound: Client ID"),
    ("FREESOUND_CLIENT_SECRET", "Freesound: Client secret"),
    ("BLENDERKIT_API_KEY", "BlenderKit (opcional)"),
    ("NGROK_AUTHTOKEN", "ngrok (opcional)"),
    ("GEMINI_API_KEY", "Gemini (opcional)"),
]
ruta = pathlib.Path("/content/drive/MyDrive/EDDIE_STUDIO/privado/claves.json")
ruta.parent.mkdir(parents=True, exist_ok=True)
guardadas = json.loads(ruta.read_text()) if ruta.exists() else {}
for nombre, desc in CLAVES:
    if nombre in guardadas and not CAMBIAR_CLAVES_EXISTENTES:
        print(f"✔ {nombre:<24} ya guardada")
        continue
    valor = getpass.getpass(f"{desc} — {nombre}: ").strip()
    if valor:
        guardadas[nombre] = valor
        print(f"✔ {nombre:<24} guardada")
    else:
        print(f"· {nombre:<24} (saltada)")
ruta.write_text(json.dumps(guardadas, indent=2))
print(f"\nListo: {len(guardadas)} claves en tu Drive privado.")
if "HF_TOKEN" not in guardadas:
    print("⚠️  Falta HF_TOKEN: sin ella no se pueden descargar los modelos de IA.")
'''

INICIAR = r'''
#@title 🚀 2. Iniciar el estudio
RAMA = "__RAMA__" #@param {type:"string"}
ABRIR_TUNEL_CON_NGROK = False #@param {type:"boolean"}
#@markdown Por defecto el túnel es de Cloudflare (temporal, sin cuenta). La dirección cambia en cada inicio.

import json, os, pathlib, subprocess, sys, importlib
from google.colab import drive
if not os.path.isdir("/content/drive/MyDrive"):
    drive.mount("/content/drive")

REPO = "__REPO__"
DESTINO = "/content/eddie-studio-3d"
claves = {}
ruta_claves = pathlib.Path("/content/drive/MyDrive/EDDIE_STUDIO/privado/claves.json")
if ruta_claves.exists():
    claves = json.loads(ruta_claves.read_text())
token = claves.get("GITHUB_TOKEN")
try:
    from google.colab import userdata
    token = userdata.get("GITHUB_TOKEN") or token
except Exception:
    pass

def git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} falló:\n{r.stderr[-1500:]}")
    return r.stdout

# Credencial de GitHub solo en esta sesión (no se imprime ni queda en la URL).
if token:
    pathlib.Path("~/.git-credentials").expanduser().write_text(f"https://x-access-token:{token}@github.com\n")
    git("config", "--global", "credential.helper", "store")
url = f"https://github.com/{REPO}.git"
if os.path.isdir(f"{DESTINO}/.git"):
    git("fetch", "--depth", "50", "origin", RAMA, cwd=DESTINO)
    git("checkout", "-B", RAMA, f"origin/{RAMA}", cwd=DESTINO)
    git("reset", "--hard", f"origin/{RAMA}", cwd=DESTINO)
else:
    git("clone", "--depth", "50", "--branch", RAMA, url, DESTINO)
print("Código:", git("log", "-1", "--format=%h %s", cwd=DESTINO).strip())

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{DESTINO}/requirements.txt"], check=True)
if DESTINO not in sys.path:
    sys.path.insert(0, DESTINO)
os.chdir(DESTINO)
for m in [m for m in list(sys.modules) if m == "estudio" or m.startswith("estudio.")]:
    del sys.modules[m]
from estudio import arranque

info = arranque.iniciar(preferir_ngrok=ABRIR_TUNEL_CON_NGROK)
arranque.vigilar()
'''.replace("__RAMA__", RAMA).replace("__REPO__", REPO)

CONEXION = r'''
#@title 📋 Ver otra vez la dirección y la clave
import json, pathlib
p = pathlib.Path("/content/drive/MyDrive/EDDIE_STUDIO/privado/conexion_actual.json")
print(json.dumps(json.loads(p.read_text()), indent=2) if p.exists() else "Aún no se ha iniciado el estudio.")
'''

DETENER = r'''
#@title 🛑 3. Detener servidor y túnel
import sys
sys.path.insert(0, "/content/eddie-studio-3d")
from estudio import arranque
arranque.detener_todo()
print("Estudio detenido.")
'''

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "G4", "machine_shape": "hm"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": [md(INTRO), code(CLAVES, True), code(INICIAR, True), code(CONEXION, True), code(DETENER, True)],
}

destino = Path(__file__).with_name("EDDIE_STUDIO.ipynb")
destino.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("Escrito", destino)
