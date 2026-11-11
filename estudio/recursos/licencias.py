"""Compuerta de licencias: nada se descarga sin evidencia de la licencia OFICIAL de su fuente.

Evidencia = la página oficial de la licencia leída en vivo (URL, fecha, SHA-256 del contenido y el
fragmento donde aparece cada frase exigida), guardada en <DRIVE>/biblioteca/licencias/evidencias/.
- verificada en vivo, o evidencia guardada de menos de «vigencia_dias» → se permite;
- fuente «pendiente» sin evidencia → se rechaza (se puede capturar a mano con guardar_manual);
- fuente «excluida» (no comercial o sin licencia clara) → se rechaza siempre.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.request
from pathlib import Path

from .. import config

FUENTES = Path(__file__).resolve().parent / "fuentes.json"
CABECERAS = {"User-Agent": "EDDIE-STUDIO-3D/1.0 (estudio de video personal; verificacion de licencias)"}
_cache: dict[str, dict] = {}


class LicenciaNoVerificada(Exception):
    pass


def fuentes() -> dict:
    datos = json.loads(FUENTES.read_text(encoding="utf-8"))
    return {k: v for k, v in datos.items() if not k.startswith("_") and isinstance(v, dict)}


def vigencia_dias() -> int:
    return int(json.loads(FUENTES.read_text(encoding="utf-8")).get("vigencia_dias", 90))


def carpeta_evidencias() -> Path:
    return config.ruta_drive("biblioteca", "licencias", "evidencias")


def texto_plano(contenido: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", contenido, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def leer_pagina(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def buscar_frases(texto: str, frases: list[str]) -> dict[str, str | None]:
    """{frase: fragmento alrededor} o None si no aparece (sin distinguir mayúsculas)."""
    bajo = texto.lower()
    salida = {}
    for f in frases:
        i = bajo.find(f.lower())
        salida[f] = texto[max(0, i - 100):i + len(f) + 140].strip() if i >= 0 else None
    return salida


def _guardar(nombre: str, evidencia: dict, contenido: str | None = None) -> Path:
    carpeta = carpeta_evidencias()
    carpeta.mkdir(parents=True, exist_ok=True)
    if contenido is not None:
        copia = carpeta / f"{nombre}_{time.strftime('%Y%m%d')}.html"
        if not copia.exists():
            copia.write_text(contenido, encoding="utf-8")
        evidencia["copia"] = str(copia)
    ruta = carpeta / f"{nombre}.json"
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(evidencia, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ruta)
    return ruta


def evidencia_guardada(nombre: str) -> dict | None:
    ruta = carpeta_evidencias() / f"{nombre}.json"
    try:
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None
    except (OSError, ValueError):
        return None


def _vigente(ev: dict | None) -> bool:
    return bool(ev and ev.get("ok") and time.time() - float(ev.get("epoca", 0)) < vigencia_dias() * 86400)


def _verificar_zenodo(f: dict) -> tuple[bool, str]:
    """Licencia declarada en los metadatos oficiales del registro de Zenodo."""
    try:
        datos = json.loads(leer_pagina(f"https://zenodo.org/api/records/{f['zenodo']}"))
        lic = (datos.get("metadata", {}).get("license") or {}).get("id", "")
        return lic.lower() == f["licencia_zenodo"].lower(), f"Zenodo {f['zenodo']}: license.id = {lic}"
    except Exception as e:  # noqa: BLE001
        return False, f"Zenodo no respondió: {e}"


def verificar(nombre: str, forzar: bool = False) -> dict:
    """Verifica la licencia oficial de una fuente. Devuelve la evidencia (ok True/False y motivo)."""
    if nombre in _cache and not forzar:
        return _cache[nombre]
    todas = fuentes()
    if nombre not in todas:
        return {"fuente": nombre, "ok": False, "motivo": "fuente desconocida (no está en fuentes.json)"}
    f = todas[nombre]
    if f.get("estado") == "excluida":
        r = {"fuente": nombre, "ok": False, "motivo": f"excluida: {f.get('motivo', 'licencia no comercial')}"}
        _cache[nombre] = r
        return r
    previa = evidencia_guardada(nombre)
    if previa and previa.get("manual") and _vigente(previa):
        _cache[nombre] = previa
        return previa
    if f.get("estado") != "verificada":
        r = {"fuente": nombre, "ok": False, "motivo": "licencia pendiente de verificar en su página oficial "
             "(captúrala con recursos_licencia_manual)", "url_licencia": f.get("url_licencia")}
        _cache[nombre] = r
        return r
    if not forzar and _vigente(previa) and not previa.get("manual"):
        _cache[nombre] = previa
        return previa
    try:
        contenido = leer_pagina(f["url_licencia"])
        encontradas = buscar_frases(texto_plano(contenido), f.get("frases", []))
        ok = all(v is not None for v in encontradas.values())
        ev = {"fuente": nombre, "ok": ok, "licencia": f.get("licencia"), "url_licencia": f["url_licencia"],
              "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "epoca": time.time(),
              "sha256": hashlib.sha256(contenido.encode()).hexdigest(), "frases": encontradas,
              "motivo": "" if ok else "la página oficial ya no contiene: " +
              ", ".join(k for k, v in encontradas.items() if v is None)}
        if ok and f.get("zenodo"):
            ok_z, detalle = _verificar_zenodo(f)
            ev["zenodo"] = detalle
            ev["ok"] = ok_z
            if not ok_z:
                ev["motivo"] = detalle
        _guardar(nombre, ev, contenido)
    except Exception as e:  # noqa: BLE001
        if _vigente(previa):
            ev = {**previa, "aviso": f"no se pudo releer la página ({e}); se usa la evidencia del {previa.get('fecha')}"}
        else:
            ev = {"fuente": nombre, "ok": False, "motivo": f"no se pudo leer la licencia oficial: {e}",
                  "url_licencia": f["url_licencia"]}
    _cache[nombre] = ev
    return ev


def exigir(nombre: str) -> dict:
    ev = verificar(nombre)
    if not ev.get("ok"):
        raise LicenciaNoVerificada(f"{nombre}: {ev.get('motivo')}")
    return ev


def verificar_pagina_recurso(nombre: str, url: str, contenido: str | None = None) -> dict:
    """Licencia escrita en la página de UN recurso (p. ej. cada personaje de Blender Studio)."""
    f = fuentes()[nombre]
    contenido = contenido if contenido is not None else leer_pagina(url)
    encontradas = buscar_frases(texto_plano(contenido), f.get("frases_por_recurso", []))
    return {"url": url, "ok": all(v is not None for v in encontradas.values()), "frases": encontradas,
            "sha256": hashlib.sha256(contenido.encode()).hexdigest(), "fecha": time.strftime("%Y-%m-%d %H:%M:%S")}


def guardar_manual(nombre: str, url: str, texto: str, quien: str = "propietario") -> dict:
    """Evidencia capturada a mano (navegador de Antigravity o el propietario) para fuentes cuya página
    oficial no se puede leer de forma automática. Se exige que el texto contenga las frases de la fuente."""
    todas = fuentes()
    if nombre not in todas:
        raise SystemExit(f"Fuente desconocida: {nombre}")
    f = todas[nombre]
    if f.get("estado") == "excluida":
        raise SystemExit(f"{nombre} está excluida: {f.get('motivo')}")
    if url.split("#")[0].rstrip("/") != f.get("url_licencia", "").rstrip("/") and \
            not url.startswith(f.get("url_licencia", "~")):
        raise SystemExit(f"La URL debe ser la página oficial registrada: {f.get('url_licencia')}")
    frases = f.get("frases") or []
    if not frases:
        raise SystemExit(f"{nombre} no tiene frases de licencia registradas: hay que revisarla y agregarlas a "
                         "fuentes.json antes de aceptarla.")
    encontradas = buscar_frases(re.sub(r"\s+", " ", texto), frases)
    ok = all(v is not None for v in encontradas.values())
    ev = {"fuente": nombre, "ok": ok, "manual": True, "capturada_por": quien, "url_licencia": url,
          "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "epoca": time.time(),
          "sha256": hashlib.sha256(texto.encode()).hexdigest(), "frases": encontradas,
          "motivo": "" if ok else "el texto no contiene: " + ", ".join(k for k, v in encontradas.items() if v is None)}
    _guardar(nombre, ev, texto)
    _cache.pop(nombre, None)
    return ev


def resumen() -> list[dict]:
    salida = []
    for k, f in fuentes().items():
        ev = evidencia_guardada(k)
        salida.append({"fuente": k, "nombre": f.get("nombre"), "licencia": f.get("licencia"),
                       "estado": f.get("estado"), "metodo": f.get("metodo"),
                       "evidencia": (ev or {}).get("fecha"), "evidencia_ok": (ev or {}).get("ok"),
                       "motivo": f.get("motivo") or (ev or {}).get("motivo") or ""})
    return salida
