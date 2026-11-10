# EDDIE STUDIO 3D — Cómo usarlo

## Una sola vez

1. **Activa las APIs** de `docs/03_APIS_Y_CLAVES.md`. Como mínimo **Hugging Face** y, si el repo es
   privado, **GitHub**.
2. **Abre la libreta en Colab.** Elige una de estas dos formas:
   - **Desde GitHub:** en Colab, `Archivo → Abrir cuaderno → GitHub`. Autoriza el acceso a tus repos
     privados y abre `CreaMente/EDDIE-STUDIO-3D` → `colab/EDDIE_STUDIO.ipynb`. Elige la rama
     `claude/happy-shannon-dzepo9` hasta que se fusione con `main`.
   - **Desde tu Drive:** descarga `colab/EDDIE_STUDIO.ipynb` de GitHub, súbelo a tu Drive y ábrelo con Colab.
3. **Elige la GPU:** `Entorno de ejecución → Cambiar tipo de entorno de ejecución` → **RTX PRO 6000**.
4. **Ejecuta la celda 🔑 1. Claves.**
   - Autoriza Drive.
   - Pega cada clave cuando la pida; deja vacío y pulsa Enter para saltar una.
5. **En Antigravity, abre como espacio de trabajo una copia local de este repositorio:**
   ```bash
   git clone https://github.com/CreaMente/EDDIE-STUDIO-3D.git
   ```
   Así Antigravity lee `AGENTS.md` y `.agents/rules/` y sabe cómo trabajar.

## Cada vez que vayas a trabajar

1. **En Colab, ejecuta 🚀 2. Iniciar.**
   - La primera vez tarda más: descarga Blender y lo guarda en Drive.
   - Al final verás la dirección, la clave y un bloque JSON.
2. **En Antigravity**, panel del agente → `⋯` → **MCP Servers → Manage MCP Servers → View raw config**:
   - pega el bloque (si ya había un `eddie-studio`, reemplázalo);
   - guarda y pulsa **Refresh**.
3. **Pídele lo que quieras.** Para la primera sesión:
   > Conéctate al estudio, haz la prueba de la Fase 0 de AGENTS.md y dime los tiempos de render de la GPU.
4. **Deja la pestaña de Colab abierta** mientras trabaja. La celda 2 queda corriendo a propósito.

Si se cae la sesión de Colab: vuelve a ejecutar la celda 2 y actualiza el bloque en Antigravity, porque
la dirección es nueva.
- Lo guardado en Drive (claves, Blender, biblioteca, proyectos) no se pierde.
- Lo que estaba en `/content/eddie` sí se pierde: renders temporales y trabajos en curso.

## Qué puede hacer Antigravity por el túnel

| Herramienta | Para qué |
|---|---|
| `estado_sistema` | GPU, RAM, discos, Blender, claves presentes |
| `ejecutar_comando`, `ejecutar_python` | Terminal y Python (hasta 85 s por llamada) |
| `trabajo_iniciar`, `trabajo_estado`, `trabajo_listar`, `trabajo_cancelar` | Tareas largas en segundo plano |
| `leer_archivo`, `escribir_archivo`, `editar_archivo`, `listar_directorio` | Archivos de Colab y de tu Drive |
| `ver_imagen`, `hoja_de_contacto`, `info_medio` | Revisar renders y videos visualmente |
| `blender_ejecutar`, `render_prueba` | Blender sin interfaz (bpy), en la GPU |
| `leer_documento` | Leer la documentación del sistema |
| `actualizar_codigo`, `reiniciar_servidor` | Traer cambios de GitHub y recargar el servidor |

## Seguridad
- **La clave del estudio protege el túnel.** Sin ella nadie puede usar el servidor.
  - Se guarda en `EDDIE_STUDIO/privado/clave_estudio.txt`.
  - Si crees que se filtró, borra ese archivo y reinicia: se genera otra.
- **Tu carpeta de Drive compartida como "Editor público" sigue siendo un riesgo.** Cámbiala a "Restringido".
- El túnel es tu agente controlando tu propio cómputo. Las reglas de Colab prohíben "servicios web" no
  relacionados con el cómputo interactivo. Es un riesgo que decidiste aceptar (ver Arquitectura §2).
