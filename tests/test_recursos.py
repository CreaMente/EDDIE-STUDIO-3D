"""Pruebas del sistema de recursos (sin internet ni Blender). Uso: python3 tests/test_recursos.py

Comprueban las reglas que no se pueden romper: la compuerta de licencias, que el catálogo no retroceda un
recurso ya descargado, que una descarga cortada continúe y que nunca se sobrescriba un archivo, el recorte
de BVH y que el ingestor nunca borre lo que entra.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
TMP = Path(tempfile.mkdtemp(prefix="eddie_recursos_"))
os.environ.update({"EDDIE_DRIVE": str(TMP / "drive" / "EDDIE_STUDIO"), "EDDIE_PRIVADO": str(TMP / "drive" / "PRIV"),
                   "EDDIE_LOCAL": str(TMP / "local")})
(TMP / "drive" / "EDDIE_STUDIO").mkdir(parents=True)
(TMP / "drive" / "PRIV").mkdir(parents=True)

from estudio.recursos import bvh, catalogo, descargas, ingestor, licencias  # noqa: E402

descargas.MARGEN_LOCAL_GB = 0.0  # la prueba no depende del disco libre de la máquina

OK = []


def caso(nombre):
    def dec(f):
        f()
        OK.append(nombre)
        print(f"✔ {nombre}")
        return f
    return dec


def evidencia(fuente: str):
    licencias._guardar(fuente, {"fuente": fuente, "ok": True, "licencia": "CC0-1.0", "url_licencia": "x",
                                "fecha": "hoy", "epoca": time.time()})
    licencias._cache.pop(fuente, None)


@caso("licencias: excluidas, pendientes y desconocidas se rechazan")
def _():
    assert not licencias.verificar("lafan1")["ok"]
    assert "excluida" in licencias.verificar("objaverse")["motivo"]
    assert not licencias.verificar("mixamo")["ok"]  # pendiente sin evidencia
    assert not licencias.verificar("no_existe")["ok"]
    try:
        licencias.exigir("amass")
        raise AssertionError("debió rechazar")
    except licencias.LicenciaNoVerificada:
        pass


@caso("licencias: evidencia manual exige las frases oficiales y la URL registrada")
def _():
    url = licencias.fuentes()["mixamo"]["url_licencia"]
    assert not licencias.guardar_manual("mixamo", url, "texto sin la frase")["ok"]
    try:
        licencias.guardar_manual("mixamo", "https://otro.sitio/", "royalty free")
        raise AssertionError("debió rechazar la URL")
    except SystemExit:
        pass
    assert licencias.guardar_manual("mixamo", url, "... characters and animations are royalty free ...")["ok"]
    assert licencias.verificar("mixamo")["ok"]
    try:
        licencias.guardar_manual("lafan1", "x", "royalty free")
        raise AssertionError("una excluida no se puede habilitar")
    except SystemExit:
        pass


@caso("catálogo: registrar de nuevo no retrocede un recurso descargado")
def _():
    catalogo.registrar({"id": "polyhaven:hdri:x", "fuente": "polyhaven", "tipo": "hdri", "clave": "x", "nombre": "Cielo"})
    catalogo.marcar("polyhaven:hdri:x", "aprobado", "/r/x.hdr", 123)
    catalogo.registrar({"id": "polyhaven:hdri:x", "fuente": "polyhaven", "tipo": "hdri", "clave": "x", "nombre": "Cielo 2"})
    r = catalogo.obtener("polyhaven:hdri:x")
    assert r["estado"] == "aprobado" and r["ruta"] == "/r/x.hdr" and r["nombre"] == "Cielo 2"
    assert catalogo.buscar("cielo")[0]["clave"] == "x"
    ruta = catalogo.guardar()
    assert Path(ruta).exists() and list((Path(ruta).parent / "respaldos").glob("catalogo_*.db"))


class Servidor(http.server.SimpleHTTPRequestHandler):
    cortar = True

    def log_message(self, *a):
        pass

    def do_GET(self):
        datos = (TMP / "web" / "archivo.bin").read_bytes()
        rango = self.headers.get("Range")
        if rango:
            ini = int(rango.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{len(datos) - 1}/{len(datos)}")
            self.send_header("Content-Length", str(len(datos) - ini))
            self.end_headers()
            self.wfile.write(datos[ini:])
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        if Servidor.cortar:  # primera vez: se corta a la mitad
            Servidor.cortar = False
            self.wfile.write(datos[:len(datos) // 2])
            return
        self.wfile.write(datos)


@caso("descargas: continúan tras un corte, verifican md5 y no sobrescriben")
def _():
    import hashlib
    (TMP / "web").mkdir()
    datos = os.urandom(300_000)
    (TMP / "web" / "archivo.bin").write_bytes(datos)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/archivo.bin"
    destino = TMP / "drive" / "EDDIE_STUDIO" / "biblioteca" / "x.bin"
    n = descargas.bajar(url, destino, tam=len(datos), md5=hashlib.md5(datos).hexdigest(), registro=lambda *_: None)
    assert n == len(datos) and destino.read_bytes() == datos and not destino.with_name("x.bin.parcial").exists()
    assert descargas.bajar(url, destino, tam=len(datos)) == len(datos)  # ya está: no se baja de nuevo
    try:
        descargas.bajar(url, destino, tam=len(datos) + 1)
        raise AssertionError("no debe sobrescribir un archivo distinto")
    except FileExistsError:
        pass
    srv.shutdown()


@caso("bvh: recorte a 30 cuadros/s, en el lugar y sin rumbo")
def _():
    cab = ("HIERARCHY\nROOT Hips\n{\n OFFSET 0 0 0\n CHANNELS 6 Xposition Yposition Zposition Yrotation Xrotation Zrotation\n"
           " End Site\n {\n  OFFSET 0 10 0\n }\n}\nMOTION\n")
    filas = [f"{k * 1.0:.3f} 95.0 0.0 {k * 0.1:.3f} 0.0 0.0" for k in range(600)]  # camina en X y gira despacio
    origen = TMP / "a.bvh"
    origen.write_text(cab + f"Frames: 600\nFrame Time: 0.016667\n" + "\n".join(filas) + "\n")
    info = bvh.recortar(origen, TMP / "b.bvh", desde=60, cuadros=240, fps=30, en_lugar=True)
    _, cuadros, dt, _ = bvh.leer(TMP / "b.bvh")
    assert info["paso"] == 2 and len(cuadros) == 120 and abs(dt - 1 / 30) < 1e-4
    assert abs(info["velocidad_m_s"] - 0.6) < 0.05  # 1 cm por cuadro a 60 cuadros/s
    xs = [c[0] for c in cuadros[20:-20]]
    assert max(xs) - min(xs) < 1.0  # quedó en el lugar
    assert all(abs(x) < 1.0 for x in xs)  # y centrado en el origen (no donde estaba el actor)
    yaws = [c[3] for c in cuadros[20:-20]]
    assert "rumbo_quitado_grados" in info and max(abs(y) for y in yaws) < 3.0  # sin rumbo: mira al frente
    assert bvh.tramo_mas_recto(origen, 0, 600, 120) >= 0


@caso("ingestor: verifica licencia, extrae, cataloga, no repite y no borra originales")
def _():
    evidencia("quaternius")
    base = ingestor.entrada() / "quaternius"
    base.mkdir(parents=True, exist_ok=True)
    zp = base / "Universal Animation Library[Standard].zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("UAL/Animations.glb", b"glb")
        z.writestr("__MACOSX/._x", b"x")
        z.writestr("../fuera.txt", b"no")
    os.utime(zp, (time.time() - 120, time.time() - 120))
    r = ingestor.revisar(lambda *_: None)
    assert len(r["ingresados"]) == 1 and r["ingresados"][0]["archivos_3d"] == 1
    paquete = Path(r["ingresados"][0]["paquete"])
    assert (paquete / "UAL" / "Animations.glb").exists() and (paquete / "LICENCIA.txt").exists()
    assert not (paquete.parent / "fuera.txt").exists()
    procesados = list((ingestor.entrada().parent / "_procesados").rglob("*.zip"))
    assert procesados and not zp.exists()  # el original se movió, no se borró
    # el mismo archivo otra vez → repetido
    import shutil
    shutil.copy2(procesados[0], zp)
    os.utime(zp, (time.time() - 120, time.time() - 120))
    assert ingestor.revisar(lambda *_: None)["repetidos"]
    # una fuente sin licencia verificada va a revisión
    otro = ingestor.entrada() / "rokoko" / "clip.fbx"
    otro.parent.mkdir(parents=True, exist_ok=True)
    otro.write_bytes(b"fbx")
    os.utime(otro, (time.time() - 120, time.time() - 120))
    assert ingestor.revisar(lambda *_: None)["a_revision"]
    assert list((ingestor.entrada().parent / "_revision").glob("clip*.fbx"))


if __name__ == "__main__":
    catalogo.cerrar()
    print(f"\n{len(OK)} pruebas correctas · carpeta temporal {TMP}")
