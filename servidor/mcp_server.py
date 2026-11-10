"""Servidor MCP del estudio: lo que Antigravity usa por el túnel.

- Transporte HTTP en modo JSON y sin estado (el túnel de Cloudflare no admite SSE).
- Toda petición exige `Authorization: Bearer <EDDIE_CLAVE_ESTUDIO>` (menos /salud).
- Ninguna herramienta espera más de ~85 s: lo largo va a trabajos en segundo plano.
"""

from __future__ import annotations

import hmac
import io
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from estudio import __version__, blender, claves, config, sistema, trabajos

MAX_ESPERA_S = 85
MAX_SALIDA = 20_000

INSTRUCCIONES = """Estudio de producción 3D (Blender) en Google Colab con GPU.
Regla de oro: la IA puede hacer todo menos generar video; cada fotograma sale del render de Blender.
Antes de producir, lee las instrucciones con leer_documento("AGENTS.md").
Tareas largas (render, descargas, instalaciones): usa trabajo_iniciar o blender_ejecutar y consulta con
trabajo_estado. Revisa siempre los resultados visualmente con ver_imagen u hoja_de_contacto."""

mcp = FastMCP("eddie-studio", instructions=INSTRUCCIONES)


# ───────────────────────── utilidades ─────────────────────────

def _recortar(texto: str, limite: int = MAX_SALIDA) -> str:
    if len(texto) <= limite:
        return texto
    mitad = limite // 2
    return texto[:mitad] + f"\n… [{len(texto) - limite} caracteres omitidos] …\n" + texto[-mitad:]


def _ruta(ruta: str) -> Path:
    """Rutas relativas se resuelven desde el repo del sistema."""
    p = Path(os.path.expanduser(ruta))
    return p if p.is_absolute() else (config.REPO / p)


def _entorno() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(config.REPO) + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("EDDIE_CLAVE_ESTUDIO", None)  # los subprocesos no necesitan la clave del servidor
    return env


def _ejecutar(args, timeout_s: float, cwd: str | None = None, shell: bool = False) -> dict:
    timeout_s = max(1.0, min(float(timeout_s), MAX_ESPERA_S))
    t0 = time.time()
    try:
        r = subprocess.run(args, shell=shell, cwd=cwd or str(config.REPO), capture_output=True,
                           text=True, timeout=timeout_s, env=_entorno(),
                           executable="/bin/bash" if shell else None)
        return {
            "codigo_salida": r.returncode,
            "salida": _recortar(r.stdout),
            "errores": _recortar(r.stderr, 8000),
            "duracion_s": round(time.time() - t0, 2),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "codigo_salida": None,
            "error": f"Pasó el límite de {timeout_s:.0f} s. Para tareas largas usa trabajo_iniciar.",
            "salida": _recortar((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")),
        }


def _imagen(ruta: Path, ancho_max: int) -> Image:
    from PIL import Image as PILImage

    with PILImage.open(ruta) as im:
        im = im.convert("RGB")
        if max(im.size) > ancho_max:
            im.thumbnail((ancho_max, ancho_max))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
    return Image(data=buf.getvalue(), format="jpeg")


# ───────────────────────── rutas HTTP ─────────────────────────

@mcp.custom_route("/salud", methods=["GET"])
async def salud(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


class AutenticacionBearer:
    """Middleware ASGI: exige la clave del estudio en todas las rutas salvo /salud."""

    def __init__(self, app, clave: str):
        self.app = app
        self.esperada = f"Bearer {clave}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") != "/salud":
            recibida = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not hmac.compare_digest(recibida, self.esperada):
                resp = JSONResponse({"error": "No autorizado: falta o es incorrecta la clave del estudio"},
                                    status_code=401)
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ───────────────────────── sistema ─────────────────────────

@mcp.tool
def estado_sistema() -> dict:
    """Diagnóstico: GPU, RAM, discos, Drive, Blender, ffmpeg, túnel y qué claves de API hay (sin valores)."""
    presentes = sorted(k for k in claves.CLAVES_CONOCIDAS if os.environ.get(k))
    d = sistema.diagnostico(presentes)
    d["version_estudio"] = __version__
    d["trabajos_recientes"] = trabajos.listar(5)
    return d


@mcp.tool
def leer_documento(nombre: str = "AGENTS.md") -> str:
    """Lee la documentación del sistema. Ej.: 'AGENTS.md', 'docs/01_ARQUITECTURA.md',
    'docs/02_INVENTARIO.md', '.agents/rules/eddie-studio.md'. Con nombre='' lista los documentos."""
    if not nombre:
        docs = [str(p.relative_to(config.REPO)) for p in config.REPO.rglob("*.md")
                if ".git" not in p.parts]
        return "\n".join(sorted(docs))
    p = (config.REPO / nombre).resolve()
    if config.REPO.resolve() not in p.parents and p != config.REPO.resolve():
        return "Solo se pueden leer documentos del repositorio."
    if not p.exists():
        return f"No existe {nombre}. Usa leer_documento('') para ver la lista."
    return _recortar(p.read_text(encoding="utf-8"), 60_000)


@mcp.tool
def actualizar_codigo(rama: str = "") -> dict:
    """Trae la última versión del código desde GitHub (git pull). Luego usa reiniciar_servidor
    para que el servidor cargue los cambios."""
    cmd = "git fetch --depth 50 origin" + (f" {shlex.quote(rama)}" if rama else "")
    cmd += " && git reset --hard " + (f"origin/{shlex.quote(rama)}" if rama else "@{u}")
    cmd += " && git log -1 --format='%h %s'"
    return _ejecutar(cmd, 80, shell=True)


@mcp.tool
def reiniciar_servidor() -> dict:
    """Reinicia este servidor (por ejemplo, tras editar su código). Vuelve en ~3 s con la misma
    dirección y clave. Los trabajos en segundo plano NO se detienen."""
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return {"ok": True, "mensaje": "Reiniciando; vuelve a llamar en unos segundos."}


# ───────────────────────── ejecución ─────────────────────────

@mcp.tool
def ejecutar_comando(comando: str, directorio: str = "", timeout_s: float = 60) -> dict:
    """Ejecuta un comando de bash en Colab y devuelve su salida (máx. 85 s; para más, trabajo_iniciar).
    Directorio por defecto: el repo del sistema."""
    return _ejecutar(comando, timeout_s, cwd=str(_ruta(directorio)) if directorio else None, shell=True)


@mcp.tool
def ejecutar_python(codigo: str, timeout_s: float = 60) -> dict:
    """Ejecuta código Python en un proceso nuevo (con el paquete `estudio` importable).
    Imprime con print() lo que quieras ver. Máx. 85 s."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=config.ruta_local("tmp")) as f:
        f.write(codigo)
        ruta = f.name
    try:
        return _ejecutar([sys.executable, ruta], timeout_s)
    finally:
        Path(ruta).unlink(missing_ok=True)


@mcp.tool
def trabajo_iniciar(comando: str, nombre: str = "", directorio: str = "") -> dict:
    """Inicia un comando de bash largo en segundo plano (render, descargas, instalaciones).
    Devuelve un id; consulta con trabajo_estado(id)."""
    return trabajos.iniciar(comando, nombre, str(_ruta(directorio)) if directorio else str(config.REPO),
                            entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


@mcp.tool
def trabajo_estado(id: str, lineas_log: int = 40, esperar_s: float = 0) -> dict:
    """Estado de un trabajo (corriendo / terminado / fallido / interrumpido / cancelado) y las últimas
    líneas de su registro. esperar_s (máx. 80) espera a que termine antes de responder."""
    if esperar_s > 0:
        trabajos.esperar(id, min(esperar_s, 80))
    return trabajos.estado(id, max(0, min(lineas_log, 400)))


@mcp.tool
def trabajo_listar(limite: int = 20) -> list[dict]:
    """Lista los trabajos recientes."""
    return trabajos.listar(limite)


@mcp.tool
def trabajo_cancelar(id: str) -> dict:
    """Detiene un trabajo en segundo plano."""
    return trabajos.cancelar(id)


# ───────────────────────── archivos ─────────────────────────

@mcp.tool
def listar_directorio(ruta: str = ".", patron: str = "*", recursivo: bool = False, limite: int = 300) -> dict:
    """Lista archivos y carpetas con tamaño. Rutas relativas = desde el repo.
    Útiles: /content/drive/MyDrive/EDDIE_STUDIO (Drive) y /content/eddie (disco local)."""
    base = _ruta(ruta)
    if not base.exists():
        return {"error": f"No existe {base}"}
    it = base.rglob(patron) if recursivo else base.glob(patron)
    filas = []
    for p in it:
        if ".git" in p.parts:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        filas.append({"ruta": str(p), "tipo": "carpeta" if p.is_dir() else "archivo",
                      "bytes": st.st_size if p.is_file() else None})
        if len(filas) >= limite:
            break
    return {"base": str(base), "total_mostrado": len(filas), "elementos": filas}


@mcp.tool
def leer_archivo(ruta: str, linea_inicio: int = 1, max_lineas: int = 400) -> dict:
    """Lee un archivo de texto (con números de línea)."""
    p = _ruta(ruta)
    if not p.is_file():
        return {"error": f"No existe el archivo {p}"}
    lineas = p.read_text(encoding="utf-8", errors="replace").splitlines()
    ini = max(1, linea_inicio)
    sel = lineas[ini - 1: ini - 1 + max(1, min(max_lineas, 2000))]
    cuerpo = "\n".join(f"{ini + i:>6}  {ln}" for i, ln in enumerate(sel))
    return {"ruta": str(p), "total_lineas": len(lineas), "contenido": _recortar(cuerpo, 60_000)}


@mcp.tool
def escribir_archivo(ruta: str, contenido: str, anexar: bool = False) -> dict:
    """Crea o reemplaza (o anexa) un archivo de texto. Crea las carpetas que falten."""
    p = _ruta(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a" if anexar else "w", encoding="utf-8") as f:
        f.write(contenido)
    return {"ok": True, "ruta": str(p), "bytes": p.stat().st_size}


@mcp.tool
def editar_archivo(ruta: str, buscar: str, reemplazar: str, todas: bool = False) -> dict:
    """Reemplaza texto exacto en un archivo. Si `buscar` aparece varias veces y todas=False, falla
    para evitar cambios ambiguos."""
    p = _ruta(ruta)
    if not p.is_file():
        return {"error": f"No existe el archivo {p}"}
    texto = p.read_text(encoding="utf-8")
    n = texto.count(buscar)
    if n == 0:
        return {"error": "No se encontró el texto a buscar"}
    if n > 1 and not todas:
        return {"error": f"El texto aparece {n} veces; amplía el fragmento o usa todas=True"}
    p.write_text(texto.replace(buscar, reemplazar), encoding="utf-8")
    return {"ok": True, "ruta": str(p), "reemplazos": n if todas else 1}


@mcp.tool
def ver_imagen(ruta: str, ancho_max: int = 1024) -> Image:
    """Devuelve una imagen (PNG/JPG/EXR convertida) para revisarla visualmente."""
    p = _ruta(ruta)
    if not p.is_file():
        raise FileNotFoundError(f"No existe {p}")
    return _imagen(p, max(256, min(ancho_max, 2048)))


@mcp.tool
def hoja_de_contacto(ruta: str, cuadros: int = 24, columnas: int = 6) -> Image:
    """Hoja con N cuadros repartidos de un video (MP4) o de una carpeta de imágenes.
    Para revisar una toma o un video completo de un vistazo."""
    from PIL import Image as PILImage, ImageDraw

    p = _ruta(ruta)
    cuadros = max(1, min(cuadros, 60))
    tmp = Path(tempfile.mkdtemp(dir=config.ruta_local("tmp")))
    if p.is_dir():
        imgs = sorted(x for x in p.iterdir() if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".exr"))
        if not imgs:
            raise FileNotFoundError(f"No hay imágenes en {p}")
        paso = max(1, len(imgs) / cuadros)
        sel = [imgs[min(len(imgs) - 1, int(i * paso))] for i in range(min(cuadros, len(imgs)))]
        etiquetas = [x.stem for x in sel]
    elif p.is_file():
        info = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
            capture_output=True, text=True, timeout=30).stdout or "{}")
        dur = float(info.get("format", {}).get("duration", 0) or 0)
        if dur <= 0:
            raise ValueError("No se pudo leer la duración del video")
        sel, etiquetas = [], []
        for i in range(cuadros):
            t = dur * (i + 0.5) / cuadros
            out = tmp / f"{i:03d}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(p), "-frames:v", "1",
                            "-vf", "scale=360:-2", "-y", str(out)], timeout=60)
            if out.exists():
                sel.append(out)
                etiquetas.append(f"{t:.1f}s")
    else:
        raise FileNotFoundError(f"No existe {p}")

    miniaturas = []
    for x, et in zip(sel, etiquetas):
        with PILImage.open(x) as im:
            im = im.convert("RGB")
            im.thumbnail((360, 640))
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 8 + 7 * len(et), 18], fill=(0, 0, 0))
            d.text((4, 3), et, fill=(255, 255, 255))
            miniaturas.append(im.copy())
    w = max(m.width for m in miniaturas)
    h = max(m.height for m in miniaturas)
    columnas = max(1, min(columnas, len(miniaturas)))
    filas = math.ceil(len(miniaturas) / columnas)
    hoja = PILImage.new("RGB", (columnas * w, filas * h), (20, 20, 20))
    for i, m in enumerate(miniaturas):
        hoja.paste(m, ((i % columnas) * w, (i // columnas) * h))
    destino = config.ruta_local("tmp", f"hoja_{int(time.time())}.jpg")
    hoja.save(destino, quality=88)
    return _imagen(destino, 2048)


@mcp.tool
def info_medio(ruta: str) -> dict:
    """Información técnica de un video, audio o imagen (ffprobe): duración, resolución, fps, códecs."""
    p = _ruta(ruta)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    d = json.loads(r.stdout)
    streams = [{k: s.get(k) for k in ("codec_type", "codec_name", "width", "height", "r_frame_rate",
                                       "pix_fmt", "sample_rate", "channels", "duration", "nb_frames")}
               for s in d.get("streams", [])]
    f = d.get("format", {})
    return {"ruta": str(p), "duracion_s": float(f.get("duration", 0) or 0),
            "bytes": int(f.get("size", 0) or 0), "streams": streams}


# ───────────────────────── Blender ─────────────────────────

def _blender_trabajo(codigo: str, script: str, argumentos: list[str] | None, archivo_blend: str,
                     segundo_plano: bool, nombre: str) -> dict:
    if bool(codigo) == bool(script):
        return {"error": "Pasa exactamente uno: codigo o script"}
    if codigo:
        ruta = config.ruta_local("tmp", f"bpy_{int(time.time() * 1000)}.py")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(codigo, encoding="utf-8")
    else:
        ruta = _ruta(script)
        if not ruta.is_file():
            return {"error": f"No existe el script {ruta}"}
    try:
        cmd = blender.comando(ruta, argumentos or [], _ruta(archivo_blend) if archivo_blend else None)
    except RuntimeError as e:
        return {"error": str(e)}
    t = trabajos.iniciar(shlex.join(cmd), nombre or f"blender {Path(ruta).name}", str(config.REPO),
                         entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})
    if segundo_plano:
        return t
    return trabajos.esperar(t["id"], 80)


@mcp.tool
def blender_ejecutar(codigo: str = "", script: str = "", argumentos: list[str] | None = None,
                     archivo_blend: str = "", segundo_plano: bool = True, nombre: str = "") -> dict:
    """Ejecuta Python dentro de Blender sin interfaz (bpy). Pasa `codigo` o la ruta de un `script`
    (relativa al repo, p. ej. 'blender_scripts/render_prueba.py'). Con segundo_plano=True devuelve
    un id de trabajo; con False espera hasta 80 s. Los scripts imprimen su resultado en una línea
    'RESULTADO_JSON: {...}' del registro."""
    return _blender_trabajo(codigo, script, argumentos, archivo_blend, segundo_plano, nombre)


@mcp.tool
def render_prueba(motor: str = "CYCLES", ancho: int = 1080, alto: int = 1920, muestras: int = 128) -> dict:
    """Render de prueba de una escena de referencia para medir la GPU (motor: CYCLES o EEVEE).
    Devuelve un id de trabajo; al terminar, el log trae los tiempos y la imagen queda en
    /content/eddie/tmp/render_prueba_<MOTOR>.png (revísala con ver_imagen)."""
    motor = motor.upper()
    if motor not in ("CYCLES", "EEVEE"):
        return {"error": "motor debe ser CYCLES o EEVEE"}
    salida = config.ruta_local("tmp", f"render_prueba_{motor}.png")
    return _blender_trabajo("", "blender_scripts/render_prueba.py",
                            ["--motor", motor, "--ancho", str(ancho), "--alto", str(alto),
                             "--muestras", str(muestras), "--salida", str(salida)],
                            "", True, f"render_prueba {motor}")


# ───────────────────────── arranque ─────────────────────────

def crear_app():
    clave = os.environ.get("EDDIE_CLAVE_ESTUDIO", "")
    if len(clave) < 32:
        raise SystemExit("Falta EDDIE_CLAVE_ESTUDIO (mín. 32 caracteres). Inicia con estudio.arranque.")
    app = mcp.http_app(path="/mcp", json_response=True, stateless_http=True)
    return AutenticacionBearer(app, clave), app


def main() -> None:
    import uvicorn

    config.ruta_local("tmp").mkdir(parents=True, exist_ok=True)
    # El middleware deja pasar los eventos "lifespan" a la app de FastMCP (los necesita al iniciar).
    envuelta, _ = crear_app()
    uvicorn.run(envuelta, host="127.0.0.1", port=config.PUERTO_SERVIDOR, log_level="info",
                timeout_keep_alive=30)


if __name__ == "__main__":
    main()
