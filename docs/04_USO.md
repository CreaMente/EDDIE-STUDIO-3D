# EDDIE STUDIO 3D — Cómo usarlo

## Todo desde una sola celda

1. **Abre la libreta en Colab.** Elige una de estas dos formas:
   - **Desde GitHub:** en Colab, `Archivo → Abrir cuaderno → GitHub`. Autoriza tus repos privados y abre
     `CreaMente/EDDIE-STUDIO-3D` → `colab/EDDIE_STUDIO.ipynb` (rama `claude/happy-shannon-dzepo9`).
   - **Desde Drive:** descarga `colab/EDDIE_STUDIO.ipynb` de GitHub, súbelo a tu Drive y ábrelo con Colab.
2. **GPU:** `Entorno de ejecución → Cambiar tipo de entorno de ejecución` → **RTX PRO 6000**.
3. **Completa la celda:**
   - **Carpeta de Drive:** el link de la carpeta donde vivirán la biblioteca, los proyectos y los
     videos. Si es una carpeta compartida contigo, primero agrégale un acceso directo en "Mi unidad".
     Vacío = `Mi unidad/EDDIE_STUDIO`.
   - **Claves:** pégalas la primera vez. Se guardan en `Mi unidad/EDDIE_PRIVADO/`, siempre privada y
     separada de la carpeta de trabajo. Después puedes borrarlas del formulario.
   - **Opciones:** túnel (Cloudflare temporal por defecto) y rama del código.
4. **Ejecuta la celda (▶)** y autoriza Drive.
   - La primera vez tarda unos minutos más: descarga Blender y lo guarda en tu carpeta de trabajo.
5. **Al terminar aparece el panel "EDDIE STUDIO 3D — listo"** con GPU, Blender, carpeta y claves
   cargadas, y la **configuración para Antigravity** con el botón **📋 Copiar configuración**.
6. **En Antigravity:**
   - panel del agente → `⋯` → **MCP Servers → Manage MCP Servers → View raw config**;
   - pega (reemplaza el bloque `eddie-studio` si ya existía), guarda y pulsa **Refresh**.
7. **En Antigravity, abre como espacio de trabajo una copia local de este repositorio**, para que lea
   `AGENTS.md` y `.agents/rules/`. Primera instrucción sugerida:
   > Conéctate al estudio, haz la prueba de la Fase 0 de AGENTS.md y dime los tiempos de render de la GPU.

**Deja la pestaña de Colab abierta:** la celda sigue corriendo a propósito.

Si la sesión se cae, vuelve a ejecutar la celda y pega la nueva configuración: el túnel es temporal y cambia.
- **No se pierde:** claves, Blender, biblioteca y proyectos, porque viven en Drive.
- **Sí se pierde:** lo temporal en `/content/eddie`.

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
  - Se guarda en `Mi unidad/EDDIE_PRIVADO/clave_estudio.txt`.
  - Si crees que se filtró, borra ese archivo y reinicia: se genera otra.
- **Tu carpeta de Drive compartida como "Editor público" sigue siendo un riesgo.** Cámbiala a "Restringido".
- El túnel es tu agente controlando tu propio cómputo. Las reglas de Colab prohíben "servicios web" no
  relacionados con el cómputo interactivo. Es un riesgo que decidiste aceptar (ver Arquitectura §2).
