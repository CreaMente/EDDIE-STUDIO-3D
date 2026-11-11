"""Utilidades de texto en español para la voz (sin dependencias pesadas, se pueden probar solas)."""

from __future__ import annotations

import re
import unicodedata

MAX_CARACTERES_FRASE = 220


_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
             "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
             "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
             "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
             6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _menor_mil(n: int) -> str:
    if n < 30:
        return _UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DECENAS[d] + (f" y {_UNIDADES[u]}" if u else "")
    if n == 100:
        return "cien"
    c, resto = divmod(n, 100)
    return _CENTENAS[c] + (f" {_menor_mil(resto)}" if resto else "")


def _apocopar(t: str) -> str:
    """'uno' → 'un' delante de mil/millón: veintiún mil, ciento un millones."""
    if t.endswith("veintiuno"):
        return t[:-len("veintiuno")] + "veintiún"
    if t.endswith("uno"):
        return t[:-1]
    return t


def entero_a_palabras(n: int) -> str:
    """Número entero en palabras (español): 1848 → 'mil ochocientos cuarenta y ocho'."""
    if n < 0:
        return "menos " + entero_a_palabras(-n)
    if n < 1000:
        return _menor_mil(n)
    if n < 1_000_000:
        miles, resto = divmod(n, 1000)
        cab = "mil" if miles == 1 else f"{_apocopar(_menor_mil(miles))} mil"
        return cab + (f" {_menor_mil(resto)}" if resto else "")
    if n < 1_000_000_000_000:
        millones, resto = divmod(n, 1_000_000)
        cab = "un millón" if millones == 1 else f"{_apocopar(entero_a_palabras(millones))} millones"
        return cab + (f" {entero_a_palabras(resto)}" if resto else "")
    return str(n)


def numeros_a_palabras(texto: str) -> str:
    """'47.000 soldados en 1848, un 30%' → 'cuarenta y siete mil soldados en mil ochocientos cuarenta y
    ocho, un treinta por ciento'. La voz y la verificación con Whisper funcionan mejor con letras."""

    def cambiar(m: re.Match) -> str:
        crudo = m.group(0)
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", crudo):  # separador de miles
            return entero_a_palabras(int(re.sub(r"[.,]", "", crudo)))
        if re.fullmatch(r"\d+", crudo):
            return entero_a_palabras(int(crudo))
        entero, dec = re.split(r"[.,]", crudo)
        dec_txt = " ".join(_UNIDADES[int(c)] for c in dec) if dec.startswith("0") else entero_a_palabras(int(dec))
        return f"{entero_a_palabras(int(entero))} coma {dec_txt}"

    texto = re.sub(r"(\d)\s?%", r"\1 por ciento", texto)
    return re.sub(r"\d{1,3}(?:[.,]\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?", cambiar, texto)


def dividir_frases(texto: str, max_caracteres: int = MAX_CARACTERES_FRASE) -> list[str]:
    """Divide el guion en frases para generarlas por separado (y repetir solo la que salga mal)."""
    texto = re.sub(r"\s+", " ", texto.replace("\n", " ")).strip()
    if not texto:
        return []
    crudas = re.split(r"(?<=[.!?…])\s+(?=[¿¡\"«A-ZÁÉÍÓÚÑ0-9])", texto)
    frases: list[str] = []
    for f in crudas:
        f = f.strip()
        while len(f) > max_caracteres:
            corte = max(f.rfind(", ", 0, max_caracteres), f.rfind("; ", 0, max_caracteres),
                        f.rfind(": ", 0, max_caracteres))
            if corte < max_caracteres // 3:
                corte = f.rfind(" ", 0, max_caracteres)
            if corte <= 0:
                break
            frases.append(f[: corte + 1].strip())
            f = f[corte + 1:].strip()
        if f:
            frases.append(f)
    return frases


def normalizar(texto: str) -> str:
    """Para comparar lo que dijo la voz con el guion: minúsculas, sin acentos ni puntuación."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9ñ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def distancia(a: str, b: str) -> int:
    """Distancia de Levenshtein (por caracteres)."""
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def cer(referencia: str, hipotesis: str) -> float:
    """Tasa de error por caracteres entre el guion y la transcripción (0 = idéntico)."""
    r, h = normalizar(numeros_a_palabras(referencia)), normalizar(numeros_a_palabras(hipotesis))
    if not r:
        return 0.0 if not h else 1.0
    return distancia(r, h) / len(r)
