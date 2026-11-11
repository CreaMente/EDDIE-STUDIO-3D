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

from estudio import __version__, blender, claves, config, entornos, sistema, trabajos

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
def trabajo_listar(limite: int = 20) -> dict:
    """Lista los trabajos recientes."""
    return {"trabajos": trabajos.listar(limite)}


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


# ───────────────────────── proyectos ─────────────────────────

def _slug(texto: str) -> str:
    import re
    import unicodedata

    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:50] or "proyecto"


def _proyecto(id_o_ruta: str) -> Path:
    p = Path(id_o_ruta)
    return p if p.is_absolute() else config.ruta_drive("proyectos", id_o_ruta)


@mcp.tool
def proyecto_crear(titulo: str, guion: str = "", duracion_objetivo_s: float = 0) -> dict:
    """Crea un proyecto de video en Drive: proyectos/<fecha>-<titulo>/.
    `guion` es SOLO el texto que dirá el narrador (se guarda en guion.txt). Devuelve el id del proyecto."""
    pid = time.strftime("%Y%m%d-%H%M") + "-" + _slug(titulo)
    d = config.ruta_drive("proyectos", pid)
    d.mkdir(parents=True, exist_ok=True)
    if guion.strip():
        (d / "guion.txt").write_text(guion.strip() + "\n", encoding="utf-8")
    (d / "proyecto.json").write_text(json.dumps({
        "id": pid, "titulo": titulo, "duracion_objetivo_s": duracion_objetivo_s,
        "creado": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"id": pid, "carpeta": str(d), "guion_guardado": bool(guion.strip())}


@mcp.tool
def proyecto_listar() -> dict:
    """Lista los proyectos guardados en Drive (más recientes primero)."""
    base = config.ruta_drive("proyectos")
    filas = []
    if base.exists():
        for d in sorted((x for x in base.iterdir() if x.is_dir() and not x.name.startswith("_")), reverse=True):
            meta = d / "proyecto.json"
            info = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {"id": d.name}
            info["tiene_voz"] = (d / "voz" / "voz.wav").exists()
            filas.append(info)
    return {"proyectos": filas}


# ───────────────────────── voz (Fase 2) ─────────────────────────

def _trabajo_ia(entorno: str, modulo: str, args: list[str], nombre: str) -> dict:
    """Trabajo en segundo plano: asegura el entorno aislado y corre el módulo de IA dentro de él."""
    if not config.drive_disponible():
        return {"error": config.AVISO_DRIVE}
    asegurar = (f'"{sys.executable}" -c "from estudio import entornos; '
                f"entornos.asegurar('{entorno}')\"")
    cmd = asegurar + " && " + shlex.join(entornos.comando(entorno, modulo, *args))
    return trabajos.iniciar(cmd, nombre, str(config.REPO), entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


@mcp.tool
def voz_preparar(whisper: str = "large-v3") -> dict:
    """Instala el entorno de voz y descarga VoxCPM2 + Whisper (la primera vez tarda varios minutos;
    después quedan en Drive). Devuelve un id de trabajo."""
    return _trabajo_ia("voz", "ia.voz", ["preparar", "--whisper", whisper], "voz: preparar")


@mcp.tool
def voz_crear_narrador(nombre: str, descripcion: str, texto_muestra: str, candidatos: int = 3,
                       whisper: str = "large-v3") -> dict:
    """Crea la voz fija del canal con diseño de voz (VoxCPM2). Genera N candidatas en
    Drive: voces/<nombre>/candidatos/. La descripción va en inglés o español, p. ej.
    'Hombre adulto latinoamericano, voz cálida y enérgica de narrador de documentales, ritmo ágil'.
    El texto de muestra debe ser una o dos frases naturales (~10 s). Cada candidata se verifica con
    Whisper y se repite hasta que pronuncie bien la frase. Devuelve un id de trabajo.
    Después el PROPIETARIO escucha las candidatas y se elige una con voz_elegir_narrador."""
    return _trabajo_ia("voz", "ia.voz", ["narrador", "--nombre", _slug(nombre), "--descripcion", descripcion,
                                         "--texto", texto_muestra, "--candidatos", str(max(1, min(candidatos, 6))),
                                         "--whisper", whisper],
                       f"voz: narrador {nombre}")


@mcp.tool
def voz_elegir_narrador(nombre: str, candidata: int) -> dict:
    """Fija la candidata elegida como voz de referencia del narrador (todos los videos la usarán)."""
    import shutil

    carpeta = config.ruta_drive("voces", _slug(nombre))
    meta_p = carpeta / "narrador.json"
    origen = carpeta / "candidatos" / f"candidata_{candidata}.wav"
    if not meta_p.exists() or not origen.exists():
        return {"error": f"No existe la candidata {candidata} del narrador «{nombre}»"}
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    shutil.copyfile(origen, carpeta / "referencia.wav")
    (carpeta / "referencia.txt").write_text(meta["texto"], encoding="utf-8")
    meta["elegida"] = candidata
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "narrador": _slug(nombre), "referencia": str(carpeta / "referencia.wav")}


@mcp.tool
def voz_generar(proyecto: str, narrador: str, tomas: int = 3, max_tomas: int = 6, pausa_s: float = 0.10,
                whisper: str = "large-v3", velocidad: float = 1.0) -> dict:
    """Narra guion.txt del proyecto con la voz del narrador (VoxCPM2 en la GPU). Por cada frase genera
    varias tomas, Whisper verifica que diga exactamente el guion y se elige la mejor. Resultado en
    proyectos/<id>/voz/: voz.wav (48 kHz), palabras.json (inicio/fin de cada palabra), frases.json y
    reporte.json. `velocidad` (0.8–1.3) acelera o frena la narración final sin cambiar el tono: si el
    reporte da palabras_por_s < 3.0, vuelve a generar con velocidad ≈ 3.3 / palabras_por_s.
    Devuelve un id de trabajo."""
    d = _proyecto(proyecto)
    if not (d / "guion.txt").exists():
        return {"error": f"No existe {d / 'guion.txt'}. Crea el proyecto con su guion primero."}
    return _trabajo_ia("voz", "ia.voz", ["generar", "--proyecto", str(d), "--narrador", _slug(narrador),
                                         "--tomas", str(tomas), "--max-tomas", str(max_tomas),
                                         "--pausa", str(pausa_s), "--whisper", whisper,
                                         "--velocidad", str(max(0.8, min(float(velocidad), 1.3)))],
                       f"voz: generar {d.name}")


# ───────────────────────── biblioteca y tomas (Fases 1 y 3) ─────────────────────────

def _trabajo_estudio(args: list[str], nombre: str) -> dict:
    """Trabajo en segundo plano con el orquestador de tomas (python -m estudio.tomas …)."""
    if not config.drive_disponible():
        return {"error": config.AVISO_DRIVE}
    return trabajos.iniciar(shlex.join([sys.executable, "-m", "estudio.tomas", *args]), nombre, str(config.REPO),
                            entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


@mcp.tool
def mixamo_importar(forzar: bool = False) -> dict:
    """Importa a la biblioteca lo nuevo de biblioteca/_entrada/mixamo/: personajes (FBX con piel, T-pose)
    y animaciones (FBX sin piel). Ajusta estatura a 1.75 m, mejora materiales y crea el catálogo.
    Devuelve un id de trabajo."""
    return _trabajo_estudio(["mixamo"] + (["--forzar"] if forzar else []), "biblioteca: importar Mixamo")


@mcp.tool
def biblioteca_listar() -> dict:
    """Personajes (con su foto de vista) y animaciones disponibles (clave, duración, si es en el lugar)."""
    base = config.ruta_drive("biblioteca")
    personajes = []
    for j in sorted((base / "personajes").glob("*/personaje.json")):
        d = json.loads(j.read_text(encoding="utf-8"))
        personajes.append({"nombre": d.get("nombre"), "origen": d.get("origen", "mpfb"), "vista": d.get("vista"),
                           "altura_m": d.get("altura_m")})
    cat = base / "animaciones" / "mixamo.json"
    animaciones = []
    if cat.exists():
        for a in json.loads(cat.read_text(encoding="utf-8"))["animaciones"]:
            animaciones.append({k: a.get(k) for k in ("clave", "mixamo", "segundos", "en_lugar", "categoria",
                                                      "interaccion")})
    from estudio import elenco

    reparto = [{"nombre": n, "titulo": f["titulo"], "cara": "cara" in f,
                "descargado": (elenco.carpeta(n) / ".completo").exists(), "credito": f["credito"]}
               for n, f in elenco.fichas().items()]
    catalogo_obj = json.loads((config.REPO / "estudio" / "objetos.json").read_text(encoding="utf-8"))
    escenarios = json.loads((config.REPO / "estudio" / "escenarios.json").read_text(encoding="utf-8"))
    return {"elenco": reparto, "personajes": personajes, "animaciones": animaciones,
            "objetos": sorted(k for k in catalogo_obj if not k.startswith("_")),
            "escenarios": sorted(k for k in escenarios if not k.startswith("_")),
            "nota": "elenco = protagonistas con cara animable (labios, expresiones): úsalos en las tomas con "
                    "personas. personajes = esqueletos Mixamo (remy) que sirven de base. Acciones que no estén "
                    "aquí: usa {\"kimodo\": \"descripción en inglés\"} en la secuencia."}


@mcp.tool
def elenco_preparar(nombre: str = "") -> dict:
    """Descarga a Drive los personajes del elenco (Blender Studio, CC-BY, cara completa). Vacío = todos.
    Solo hace falta una vez; toma_crear también lo hace solo si falta. Devuelve un id de trabajo."""
    args = ["preparar"] + (["--nombre", nombre] if nombre else [])
    if not config.drive_disponible():
        return {"error": config.AVISO_DRIVE}
    return trabajos.iniciar(shlex.join([sys.executable, "-m", "estudio.elenco", *args]), "elenco: preparar",
                            str(config.REPO), entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


@mcp.tool
def movimiento_preparar() -> dict:
    """Instala Kimodo y descarga su modelo y codificador de texto (Llama 3 8B, ~17 GB; queda en Drive).
    Requiere que el propietario haya aceptado la licencia de meta-llama/Meta-Llama-3-8B-Instruct en
    Hugging Face con la cuenta de su HF_TOKEN. Devuelve un id de trabajo."""
    return _trabajo_ia("movimiento", "ia.movimiento", ["preparar"], "movimiento: preparar Kimodo")


@mcp.tool
def toma_crear(proyecto: str, personaje: str, secuencia: list[dict], nombre: str = "toma",
               motor: str = "CYCLES", calidad: str = "final", hdri: str = "",
               piso: str = "laminate_floor_02", con_voz: bool = False, camara: dict | None = None,
               bloques: int = 3, expresion: str = "neutral", intensidad: float = 1.0, habla: bool = False,
               frase: int = -1, escenario: str | dict = "estudio", objetos: list[dict] | None = None) -> dict:
    """Arma y renderiza una toma 3D a MP4 vertical 1080x1920.

    secuencia: lista de tramos, en orden. Cada tramo es uno de:
      {"anim": "caminar_herido", "segundos": 4, "avance": true}   ← animación de la biblioteca Mixamo
      {"kimodo": "A person holds their knee in pain.", "segundos": 5}  ← acción nueva con IA (texto EN INGLÉS)
      {"kimodo": ["A person stops walking.", "A person kneels on their left knee.",
                  "A person stands up slowly."], "segundos": [1.5, 3, 2.5]}  ← varias acciones simples
        encadenadas (mucho mejor que una frase con «then…»; ≤ 10 s cada una)
    opcionales por tramo: "segundos", "avance" (m/s o true), "giro" (grados), "mezcla" (cuadros de
    fundido con el tramo anterior; usa 15–20 si las poses de unión son muy distintas).
    motor: "CYCLES" (recomendado: usa la GPU con OptiX). "EEVEE" en Colab cae a CPU (sin EGL de NVIDIA).
    calidad: "borrador" (25 %, 16 muestras), "previa" (50 %, 32) o "final" (100 %, 64; Cycles: 128).
    personaje: del elenco ("rain", "snow": cara animable, ver biblioteca_listar) o un Mixamo ("remy").
    escenario: "estudio", "habitacion", "dormitorio", "pasillo", "ascensor", "oficina", "hospital",
      "exterior", "parque" (estudio/escenarios.json) o {"tipo": "oficina", "pared": "<textura Poly Haven>",
      "piso": …, "luz": "calida"|"fluorescente", "muebles": ["escritorio", "planta", …]}. La sala se arma sola
      alrededor del recorrido y de la cámara, con luces de techo y muebles contra las paredes.
    Objetos e interacción: las animaciones con interacción (abrir_puerta, recoger_objeto, beber,
      mensajear_celular, sentarse…) colocan su objeto solas: la puerta con la manija donde llega la mano y
      girando con ella, la silla bajo la cadera, el celular o la taza en la mano. En un tramo se puede pedir
      "objeto": "taza" (catálogo estudio/objetos.json) o {"tipo": "caja", "interaccion": "agarrar"|"soltar"|
      "lanzar"|"mano"|"caja"|"sentarse"|"puerta"|"tocar"|"boton", "mano": "R"|"L", "desfase": [x, y, z] (m, ejes de
      la mano: si el objeto queda tapado por la mano), "escala": 1.0}; "objeto": false lo quita.
    hdri: vacío = el del escenario (id de Poly Haven).
    expresion (elenco): neutral, alegria, dolor, sorpresa, miedo, tristeza, enojo, asco, pensativo;
      intensidad 0–1.5.
    habla + frase (elenco): mueve los labios con la frase n de la narración (voz/frases.json). Úsalo cuando
      el protagonista cuenta la historia en primera persona y se le ve la cara.
    camara: {"plano": "primerisimo"} con planos predefinidos: general, medio, primer_plano, primerisimo
      (gran angular pegado a la cara), contrapicado, picado, detalle_pies, detalle_manos. Ajustes opcionales:
      angulo (grados alrededor; 0 = de frente), lente, distancia, altura_rel, acercamiento, inclinacion
      (plano holandés, grados), temblor (cámara en mano, grados), objetivo (cabeza, pecho, cadera, pies, manos),
      mirada (elenco): "camara" (mira al espectador, por defecto) o "frente" (hacia donde va).
    con_voz: añade proyectos/<id>/voz/voz.wav como audio.
    bloques: procesos de render en paralelo sobre la GPU (Cycles). Los PNG quedan en el disco local
    (/content/eddie/cuadros/<proyecto>/<toma>/, ruta en «cuadros_png» del resultado) y el MP4 en Drive.
    Devuelve un id de trabajo; al terminar revisa el MP4 con hoja_de_contacto."""
    perfiles = {"borrador": (25, 16), "previa": (50, 32), "final": (100, 128 if motor.upper() == "CYCLES" else 64)}
    escala, muestras = perfiles.get(calidad, perfiles["final"])
    d = _proyecto(proyecto)
    args = ["toma", "--proyecto", str(d), "--nombre", nombre, "--personaje", personaje,
            "--secuencia", json.dumps(secuencia, ensure_ascii=False), "--motor", motor.upper(),
            "--muestras", str(muestras), "--escala", str(escala), "--piso", piso,
            "--bloques", str(max(1, min(int(bloques), 8))),
            "--expresion", expresion, "--intensidad", str(intensidad), "--habla", "1" if habla else "0",
            "--frase", str(int(frase)),
            "--escenario", json.dumps(escenario, ensure_ascii=False) if isinstance(escenario, dict) else escenario,
            "--objetos", json.dumps(objetos or [], ensure_ascii=False)]
    if hdri:
        args += ["--hdri", hdri]
    if con_voz:
        args += ["--audio", str(d / "voz" / "voz.wav")]
    if camara:
        args += ["--camara", json.dumps(camara)]
    return _trabajo_estudio(args, f"toma {nombre} ({calidad})")


# ───────────────────────── montaje (Fase 4) ─────────────────────────

@mcp.tool
def video_montar(proyecto: str, plan: list[dict], textos: list[dict] | None = None, musica: str = "",
                 musica_db: float = -20.0, fundido: int = 0, nombre: str = "final", calidad: str = "final",
                 subtitulos: bool = True) -> dict:
    """Monta el video final en Blender: las tomas del proyecto alineadas a la narración, texto en pantalla,
    música opcional y audio a -14 LUFS (pico ≤ -1 dBTP). H.264 + AAC 1080x1920 30 fps.

    plan: una entrada por toma, en orden. La primera empieza en 0; cada una dura hasta que empieza la
    siguiente y la última hasta la última palabra. Dónde empieza cada toma (desde la segunda):
      {"toma": "t02", "frase": 1}           al empezar la frase 1 (proyectos/<id>/voz/frases.json)
      {"toma": "t03", "palabra": 37}        en la palabra 37 (voz/palabras.json), corte a mitad de frase
      {"toma": "t04", "inicio_s": 12.4}     en el segundo 12.4
      + "desde_s": 1.5 (opcional) para usar la toma a partir de su segundo 1.5.
    Cada toma debe durar al menos su tramo: si es más corta se congela su último cuadro y sale un aviso.
    textos: [{"texto": "DÍA 3", "frase": 4}] (dura la frase) o con "palabra"/"inicio_s" + "segundos".
      Opcionales: "tamano" (px, 120), "altura" (0–1, 0.86 = arriba).
    musica: ruta (absoluta o relativa a la carpeta del estudio en Drive); baja sola cuando habla el narrador.
    fundido: cuadros de fundido entre tomas (0 = corte directo, lo normal en el formato).
    calidad: "final" (1080x1920) o "borrador" (25 %, para revisar tiempos rápido).
    subtitulos: palabra por palabra (grupos de 1–3) en el centro, como en los videos de historias.
    Resultado: proyectos/<id>/video/<nombre>.mp4 + copia en entregas/. Devuelve un id de trabajo."""
    d = _proyecto(proyecto)
    args = ["--proyecto", str(d), "--plan", json.dumps(plan, ensure_ascii=False),
            "--textos", json.dumps(textos or [], ensure_ascii=False), "--musica_db", str(musica_db),
            "--fundido", str(max(0, int(fundido))), "--nombre", nombre,
            "--escala", "25" if calidad == "borrador" else "100", "--subtitulos", "1" if subtitulos else "0"]
    if musica:
        args += ["--musica", musica]
    if not config.drive_disponible():
        return {"error": config.AVISO_DRIVE}
    return trabajos.iniciar(shlex.join([sys.executable, "-m", "estudio.montaje", *args]), f"montaje {nombre}",
                            str(config.REPO), entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


# ───────────────────────── director (historia completa) ─────────────────────────

@mcp.tool
def video_producir(proyecto: str, guion_tecnico: dict, calidad: str = "borrador", forzar: bool = False,
                   solo: str = "") -> dict:
    """Produce el video completo desde un guion técnico: todas las tomas + montaje, en un solo trabajo.
    Requiere la voz del proyecto (voz_generar). Formato:
      {"personaje": "rain", "escenario": "habitacion",
       "tomas": [{"nombre": "t01", "frase": 0, "secuencia": [...], "camara": {"plano": ...},
                  "expresion": "miedo", "habla": true, "escenario": ..., "objetos": [...]}, ...],
       "textos": [{"texto": "DÍA 3", "frase": 4}], "musica": ""}
    Cada toma entra en su frase («frase»), palabra («palabra») o segundo («inicio_s») y dura hasta la
    siguiente: si su acción es más corta, sostiene la última pose. habla=true sincroniza los labios con lo
    que se narra en ese momento. Las tomas sin cambios no se vuelven a renderizar (para iterar rápido);
    forzar=true rehace todas y solo="t03,t05" rehace solo esas. calidad: borrador, previa o final.
    Devuelve un id de trabajo; el resultado trae la ruta del video y el reporte de cada toma."""
    d = _proyecto(proyecto)
    if not config.drive_disponible():
        return {"error": config.AVISO_DRIVE}
    args = ["--proyecto", str(d), "--guion", json.dumps(guion_tecnico, ensure_ascii=False), "--calidad", calidad]
    if forzar:
        args.append("--forzar")
    if solo:
        args += ["--solo", solo]
    return trabajos.iniciar(shlex.join([sys.executable, "-m", "estudio.director", *args]),
                            f"producir video ({calidad})", str(config.REPO),
                            entorno={"PYTHONPATH": _entorno()["PYTHONPATH"]})


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
