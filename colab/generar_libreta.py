"""Genera colab/EDDIE_STUDIO.ipynb (editar aquí y volver a ejecutar, no a mano)."""

import json
from pathlib import Path

REPO = "CreaMente/EDDIE-STUDIO-3D"
RAMA = "claude/happy-shannon-dzepo9"

INTRO = """
# 🎬 EDDIE STUDIO 3D

1. **GPU:** `Entorno de ejecución → Cambiar tipo de entorno de ejecución` → **RTX PRO 6000**.
2. **Completa la celda de abajo:**
   - la URL de tu carpeta de Drive (puede ser de otra cuenta: compártela con la cuenta de este Colab como Editor);
   - tus claves (solo la primera vez).
3. **Ejecútala** (▶). Autoriza cuando lo pida (Drive y acceso a la API).
4. Al final aparece un panel con la configuración y el botón **📋 Copiar** para pegarla en Antigravity.

La celda se queda corriendo a propósito: mantiene viva la sesión y muestra lo que hace Antigravity.
Para apagar todo: `Entorno de ejecución → Desconectar y borrar el entorno de ejecución`.
"""

CELDA = r'''
#@title 🎬 EDDIE STUDIO 3D — configurar e iniciar
#@markdown ## 📁 Carpeta de trabajo en Google Drive (URL)
#@markdown Pega la URL de la carpeta donde vivirán la biblioteca, los proyectos y los videos
#@markdown (si la dejas vacía, te la pedirá al ejecutar). **Puede ser de otra cuenta de Google:**
#@markdown compártela con la cuenta de este Colab como **Editor** (la celda te dice el correo exacto).
URL_CARPETA_DRIVE = "" #@param {type:"string"}

#@markdown ---
#@markdown ## 🔑 Claves de API
#@markdown Solo la primera vez. Se guardan en `Mi unidad/EDDIE_PRIVADO/` de la cuenta de Colab (privada,
#@markdown **fuera** de la carpeta de trabajo). Después de la primera ejecución bórralas de estos campos.
HF_TOKEN = "" #@param {type:"string"}
GITHUB_TOKEN = "" #@param {type:"string"}
SKETCHFAB_API_TOKEN = "" #@param {type:"string"}
SI_API_KEY = "" #@param {type:"string"}
FREESOUND_API_KEY = "" #@param {type:"string"}
FREESOUND_CLIENT_ID = "" #@param {type:"string"}
FREESOUND_CLIENT_SECRET = "" #@param {type:"string"}
BLENDERKIT_API_KEY = "" #@param {type:"string"}
GEMINI_API_KEY = "" #@param {type:"string"}
NGROK_AUTHTOKEN = "" #@param {type:"string"}

#@markdown ---
#@markdown ## ⚙️ Opciones
TUNEL = "cloudflare (temporal, sin cuenta)" #@param ["cloudflare (temporal, sin cuenta)", "ngrok (requiere NGROK_AUTHTOKEN)"]
RAMA = "__RAMA__" #@param {type:"string"}

# ─────────────────────────── no hace falta editar debajo ───────────────────────────
import json, os, pathlib, subprocess, sys, time

def paso(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# 1. URL de la carpeta de trabajo y Drive de la cuenta de Colab (para las claves)
URL_CARPETA_DRIVE = URL_CARPETA_DRIVE.strip() or input("📁 Pega la URL de la carpeta de Google Drive: ").strip()
if not URL_CARPETA_DRIVE:
    raise SystemExit("Hace falta la URL de la carpeta de Drive.")
from google.colab import drive as _gdrive
if not os.path.isdir("/content/drive/MyDrive"):
    _gdrive.mount("/content/drive")
PRIVADO = pathlib.Path("/content/drive/MyDrive/EDDIE_PRIVADO")
PRIVADO.mkdir(parents=True, exist_ok=True)

# 2. Claves: las nuevas del formulario se combinan con las guardadas
_nombres = ["HF_TOKEN", "GITHUB_TOKEN", "SKETCHFAB_API_TOKEN", "SI_API_KEY", "FREESOUND_API_KEY",
            "FREESOUND_CLIENT_ID", "FREESOUND_CLIENT_SECRET", "BLENDERKIT_API_KEY", "GEMINI_API_KEY",
            "NGROK_AUTHTOKEN"]
_archivo = PRIVADO / "claves.json"
_claves = json.loads(_archivo.read_text()) if _archivo.exists() else {}
_nuevas = [n for n in _nombres if str(globals().get(n, "")).strip()]
for n in _nuevas:
    _claves[n] = str(globals()[n]).strip()
_archivo.write_text(json.dumps(_claves, indent=2))
paso(f"Claves: {len(_claves)} guardadas" + (f" ({len(_nuevas)} nuevas)" if _nuevas else ""))

# 3. Código del sistema (GitHub)
REPO, DESTINO = "__REPO__", "/content/eddie-studio-3d"
def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} falló. ¿Falta o venció GITHUB_TOKEN?\n{r.stderr[-800:]}")
    return r.stdout
if _claves.get("GITHUB_TOKEN"):
    pathlib.Path("~/.git-credentials").expanduser().write_text(
        f"https://x-access-token:{_claves['GITHUB_TOKEN']}@github.com\n")
    _git("config", "--global", "credential.helper", "store")
if os.path.isdir(f"{DESTINO}/.git"):
    _git("fetch", "--depth", "50", "origin", RAMA, cwd=DESTINO)
    _git("checkout", "-B", RAMA, f"origin/{RAMA}", cwd=DESTINO)
    _git("reset", "--hard", f"origin/{RAMA}", cwd=DESTINO)
else:
    _git("clone", "--depth", "50", "--branch", RAMA, f"https://github.com/{REPO}.git", DESTINO)
paso("Código: " + _git("log", "-1", "--format=%h %s", cwd=DESTINO).strip())
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{DESTINO}/requirements.txt"], check=True)

# 4. Carpeta de trabajo y arranque
if DESTINO not in sys.path:
    sys.path.insert(0, DESTINO)
os.chdir(DESTINO)
for _m in [m for m in list(sys.modules) if m == "estudio" or m.startswith("estudio.")]:
    del sys.modules[_m]
from estudio import arranque, config, drive as edrive
try:
    _carpeta = edrive.conectar_por_url(URL_CARPETA_DRIVE, registro=paso)
except edrive.CarpetaNoEncontrada as e:
    print("\n❌ " + str(e))
    raise SystemExit()
config.establecer_rutas(drive=_carpeta, privado=PRIVADO)
paso(f"Carpeta de trabajo: {_carpeta}")

info = arranque.iniciar(preferir_ngrok=TUNEL.startswith("ngrok"), panel=True)
arranque.vigilar()
'''.replace("__RAMA__", RAMA).replace("__REPO__", REPO)

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "name": "EDDIE_STUDIO.ipynb"},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": INTRO.strip("\n").splitlines(True)},
        {"cell_type": "code", "execution_count": None, "metadata": {"cellView": "form"}, "outputs": [],
         "source": CELDA.strip("\n").splitlines(True)},
    ],
}

destino = Path(__file__).with_name("EDDIE_STUDIO.ipynb")
destino.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("Escrito", destino)
