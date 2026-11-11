"""Panel de conexión para Colab (HTML con botón de copiar)."""

from __future__ import annotations

import html
import json


def panel_html(info: dict) -> str:
    cfg = json.dumps(info["antigravity"], indent=2, ensure_ascii=False)
    d = info.get("diagnostico", {})
    gpu = d.get("gpu") or []
    gpu_txt = f'{gpu[0]["nombre"]} · {round(gpu[0]["vram_total_mb"] / 1024)} GB' if gpu else "Sin GPU detectada"
    claves = d.get("claves_presentes") or []
    url = html.escape(info["url"] + "/mcp")
    carpeta = str(info.get("drive", "—"))
    if "/drive/" in carpeta:
        carpeta = carpeta.split("/drive/", 1)[1].replace("MyDrive", "Mi unidad", 1)
    filas = [
        ("GPU", gpu_txt),
        ("Blender", d.get("blender") or "—"),
        ("Carpeta de trabajo", carpeta),
        ("Claves cargadas", ", ".join(claves) if claves else "ninguna"),
        ("Túnel", f'{info.get("tipo_tunel", "cloudflare")} (temporal: cambia en cada inicio)'),
    ]
    tabla = "".join(
        f'<tr><td style="padding:4px 18px 4px 0;color:#8b95a7;white-space:nowrap;vertical-align:top">'
        f'{html.escape(k)}</td><td style="padding:4px 0;color:#e7ecf3">{html.escape(str(v))}</td></tr>'
        for k, v in filas)
    cfg_js = json.dumps(cfg)
    return f"""
<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0f141c;color:#e7ecf3;
            border:1px solid #2a3443;border-radius:12px;padding:20px 22px;max-width:860px">
  <div style="font-size:20px;font-weight:700;margin-bottom:2px">🎬 EDDIE STUDIO 3D — listo</div>
  <div style="color:#8b95a7;margin-bottom:14px">Iniciado en {info.get("segundos", 0):.0f} s</div>
  <table style="border-collapse:collapse;font-size:14px;margin-bottom:16px;color:#e7ecf3">{tabla}</table>
  <div style="font-weight:600;margin:6px 0">Pega esto en Antigravity</div>
  <div style="color:#8b95a7;font-size:13px;margin-bottom:8px">
    Panel del agente → ⋯ → MCP Servers → Manage MCP Servers → View raw config →
    reemplaza el bloque <code>eddie-studio</code> → guarda → Refresh.</div>
  <pre id="eddie-cfg" style="background:#070a0f;border:1px solid #2a3443;border-radius:8px;padding:12px;
       font-size:13px;overflow:auto;margin:0 0 10px">{html.escape(cfg)}</pre>
  <button onclick='navigator.clipboard.writeText({cfg_js}).then(()=>{{this.innerText="✔ Copiado"}})'
          style="background:#3b82f6;color:white;border:0;border-radius:8px;padding:9px 16px;font-size:14px;
                 cursor:pointer;font-weight:600">📋 Copiar configuración</button>
  <div style="margin-top:14px;font-size:13px;color:#8b95a7">
    Dirección: <code style="color:#e7ecf3">{url}</code><br>
    Primera instrucción sugerida para Antigravity:
    <i>«Conéctate al estudio, haz la prueba de la Fase 0 de AGENTS.md y dime los tiempos de render.»</i><br>
    Deja esta pestaña abierta: la celda sigue corriendo para mantener viva la sesión.</div>
</div>"""


def mostrar(info: dict) -> None:
    try:
        from IPython.display import HTML, display  # type: ignore
        display(HTML(panel_html(info)))
    except ImportError:
        print(json.dumps(info["antigravity"], indent=2))
