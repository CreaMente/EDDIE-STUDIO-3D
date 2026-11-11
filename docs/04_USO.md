# EDDIE STUDIO 3D — Cómo usarlo

## Todo desde una sola celda

1. **Abre la libreta en Colab.** Elige una de estas dos formas:
   - **Desde GitHub:** en Colab, `Archivo → Abrir cuaderno → GitHub`. Autoriza tus repos privados y abre
     `CreaMente/EDDIE-STUDIO-3D` → `colab/EDDIE_STUDIO.ipynb` (rama `claude/happy-shannon-dzepo9`).
   - **Desde Drive:** descarga `colab/EDDIE_STUDIO.ipynb` de GitHub, súbelo a tu Drive y ábrelo con Colab.
2. **GPU:** `Entorno de ejecución → Cambiar tipo de entorno de ejecución` → **RTX PRO 6000**.
3. **Completa la celda:**
   - **URL de la carpeta de Drive** donde vivirán la biblioteca, los proyectos y los videos. Si la dejas
     vacía, la celda te la pide al ejecutar.
     - **Puede ser de otra cuenta de Google** (tu Colab y tu Drive son cuentas distintas). Desde la cuenta
       dueña, comparte la carpeta con la cuenta de Colab como **Editor**. Si falta, la celda te dice
       exactamente a qué correo compartirla.
     - El sistema verifica el acceso, crea un acceso directo en el Drive de Colab y trabaja dentro de tu
       carpeta. Si la carpeta es pública con link, te lo advierte.
   - **Claves:** pégalas la primera vez. Se guardan en `Mi unidad/EDDIE_PRIVADO/`, siempre privada y
     separada de la carpeta de trabajo. Después puedes borrarlas del formulario.
   - **Opciones:** túnel (Cloudflare temporal por defecto) y rama del código.
4. **Ejecuta la celda (▶)** y autoriza con la cuenta de Colab las dos ventanas que aparecen (montar
   Drive y acceso a la API de Drive).
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
| `proyecto_crear`, `proyecto_listar` | Proyectos de video en tu Drive |
| `voz_preparar`, `voz_crear_narrador`, `voz_elegir_narrador`, `voz_generar` | Voz fija del canal y narración verificada con tiempos por palabra |
| `mixamo_importar`, `biblioteca_listar`, `movimiento_preparar` | Personajes y animaciones Mixamo; Kimodo (texto → movimiento) |
| `elenco_preparar` | Descarga el elenco con cara animable (Blender Studio, CC-BY) |
| `toma_crear` | Toma 3D animada (Mixamo + Kimodo → elenco con cara, labios y expresión) con planos estilo historia |
| `video_montar` | Video final: tomas alineadas a la voz, texto en pantalla, música y -14 LUFS |

## Seguridad
- **La clave del estudio protege el túnel.** Sin ella nadie puede usar el servidor.
  - **Cambia en cada inicio**, igual que la dirección del túnel. Una clave compartida por error deja de
    servir al volver a ejecutar la celda.
  - Durante la sesión se guarda en `Mi unidad/EDDIE_PRIVADO/clave_estudio.txt`.
- **Tu carpeta de Drive compartida como "Editor público" sigue siendo un riesgo.** Cámbiala a "Restringido".
- El túnel es tu agente controlando tu propio cómputo. Las reglas de Colab prohíben "servicios web" no
  relacionados con el cómputo interactivo. Es un riesgo que decidiste aceptar (ver Arquitectura §2).
