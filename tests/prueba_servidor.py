"""Prueba de punta a punta del servidor MCP con un cliente real.

Uso: python tests/prueba_servidor.py <url_base> <clave>
  (url_base sin /mcp, por ejemplo http://127.0.0.1:8765 o https://xxxx.trycloudflare.com)
Sale con código 1 si alguna comprobación falla.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

FALLOS: list[str] = []


def comprobar(nombre: str, condicion: bool, detalle="") -> None:
    print(("  ✔ " if condicion else "  ✘ ") + nombre + (f" — {detalle}" if detalle and not condicion else ""))
    if not condicion:
        FALLOS.append(nombre)


def datos(res):
    if getattr(res, "data", None) is not None:
        return res.data
    for c in res.content:
        if getattr(c, "type", "") == "text":
            try:
                return json.loads(c.text)
            except json.JSONDecodeError:
                return c.text
    return None


async def main(base: str, clave: str) -> int:
    # Clave incorrecta debe fallar.
    try:
        async with Client(StreamableHttpTransport(f"{base}/mcp", headers={"Authorization": "Bearer mala"})) as c:
            await c.list_tools()
        comprobar("rechaza clave incorrecta", False)
    except Exception:
        comprobar("rechaza clave incorrecta", True)

    t = StreamableHttpTransport(f"{base}/mcp", headers={"Authorization": f"Bearer {clave}"})
    async with Client(t) as c:
        herramientas = {h.name for h in await c.list_tools()}
        esperadas = {"estado_sistema", "ejecutar_comando", "ejecutar_python", "trabajo_iniciar",
                     "trabajo_estado", "leer_archivo", "escribir_archivo", "editar_archivo",
                     "ver_imagen", "hoja_de_contacto", "blender_ejecutar", "render_prueba",
                     "leer_documento", "reiniciar_servidor"}
        comprobar("lista de herramientas", esperadas <= herramientas, str(esperadas - herramientas))

        d = datos(await c.call_tool("estado_sistema", {}))
        comprobar("estado_sistema", isinstance(d, dict) and "gpu" in d, str(d)[:200])

        d = datos(await c.call_tool("ejecutar_comando", {"comando": "echo hola && python3 -c 'print(2+2)'"}))
        comprobar("ejecutar_comando", d["codigo_salida"] == 0 and "hola" in d["salida"] and "4" in d["salida"])

        d = datos(await c.call_tool("ejecutar_python", {"codigo": "import estudio; print(estudio.__version__)"}))
        comprobar("ejecutar_python importa estudio", d["codigo_salida"] == 0, str(d))

        ruta = f"/tmp/eddie_prueba_{int(time.time())}.txt"
        datos(await c.call_tool("escribir_archivo", {"ruta": ruta, "contenido": "uno\ndos\n"}))
        datos(await c.call_tool("editar_archivo", {"ruta": ruta, "buscar": "dos", "reemplazar": "tres"}))
        d = datos(await c.call_tool("leer_archivo", {"ruta": ruta}))
        comprobar("escribir/editar/leer archivo", "tres" in d["contenido"] and "dos" not in d["contenido"])

        d = datos(await c.call_tool("trabajo_iniciar", {"comando": "for i in 1 2 3; do echo paso $i; sleep 1; done",
                                                        "nombre": "prueba"}))
        tid = d["id"]
        d = datos(await c.call_tool("trabajo_estado", {"id": tid, "esperar_s": 20}))
        comprobar("trabajo en segundo plano", d["estado"] == "terminado" and "paso 3" in d["log"], str(d))

        d = datos(await c.call_tool("leer_documento", {"nombre": "AGENTS.md"}))
        comprobar("leer_documento AGENTS.md", isinstance(d, str) and "EDDIE" in d, str(d)[:120])

    print(f"\n{'TODO BIEN' if not FALLOS else 'FALLOS: ' + ', '.join(FALLOS)}")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1].rstrip("/"), sys.argv[2])))
