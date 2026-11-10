# EDDIE STUDIO 3D

Sistema para producir videos verticales estilo **«¿Qué pasaría si…?»** (formato His Story) con **3D
renderizado de verdad en Blender**, automatizado por IA de principio a fin: guion, voz, modelos 3D,
animación del cuerpo (Kimodo) y de la cara (Audio2Face), música y revisión. **Prohibidos los generadores
de video** (Wan, Veo, Flow…): cada fotograma sale del render de Blender.

- **Cerebro:** Google Antigravity, conectado por túnel. Recibe el pedido, escribe el guion, planea las tomas y usa las herramientas.
- **Estudio:** Google Colab con RTX PRO 6000. Voz, armado de escenas, render y montaje.
- **Memoria:** Google Drive Pro. Biblioteca 3D, modelos, proyectos y entregas.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/01_ARQUITECTURA.md`](docs/01_ARQUITECTURA.md) | Flujo completo, conexión Antigravity ↔ Colab, herramientas, planes de respaldo, control de calidad, organización en Drive y fases con criterios de aceptación |
| [`docs/02_INVENTARIO.md`](docs/02_INVENTARIO.md) | Todos los programas, personajes, escenarios, animaciones, voz, sonido y servicios, con su licencia y tamaño |
| [`docs/03_APIS_Y_CLAVES.md`](docs/03_APIS_Y_CLAVES.md) | APIs gratuitas que debes activar, paso a paso, y cómo cargarlas en la libreta |
| [`docs/04_USO.md`](docs/04_USO.md) | **Cómo usarlo:** libreta de Colab, conexión con Antigravity, herramientas disponibles |
| [`AGENTS.md`](AGENTS.md) y [`.agents/rules/`](.agents/rules/) | Instrucciones que Antigravity lee automáticamente |

## Estado

| Fase | Estado |
|---|---|
| 0. Conexión y entorno | **Construida y probada** (servidor, herramientas, Blender 5.2, render Cycles/EEVEE). Falta: túnel y GPU reales en tu Colab |
| 1–7 | Pendientes (ver `docs/01_ARQUITECTURA.md` §8) |

## Estructura
```
colab/EDDIE_STUDIO.ipynb   libreta (se genera con colab/generar_libreta.py)
estudio/                   núcleo: configuración, claves, trabajos, Blender, túnel, arranque
servidor/mcp_server.py     servidor MCP que usa Antigravity
blender_scripts/           scripts que corren dentro de Blender
tests/prueba_servidor.py   prueba de punta a punta del servidor
```
