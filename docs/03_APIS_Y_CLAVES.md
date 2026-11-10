# EDDIE STUDIO 3D — APIs gratuitas y claves

## Dónde van las claves

**La primera celda de la libreta te pide cada clave en un campo oculto.** Las pegas **una sola vez** y
se guardan en un archivo privado de tu Drive (`Mi unidad/EDDIE_STUDIO/privado/claves.json`); no quedan
escritas dentro de la libreta. Desde
entonces se cargan solas en cada ejecución. También funciona si las pones en **Colab Secrets** (el
icono 🔑) con los mismos nombres; si una clave está en los dos lugares, gana Colab Secrets.

Las claves **nunca** se guardan en GitHub ni en los reportes, y nunca se imprimen completas.

---

## Resumen

| # | Servicio | Para qué | Costo | Nombre de la clave | ¿Obligatorio? |
|---|---|---|---|---|---|
| 1 | ngrok | Túnel con dirección fija (alternativa) | Gratis | `NGROK_AUTHTOKEN` | **No.** El túnel por defecto es Cloudflare temporal, sin cuenta |
| 2 | **Hugging Face** | Descargar los modelos locales (voz, Whisper, SigLIP, música, movimiento) | Gratis | `HF_TOKEN` | Sí |
| 3 | GitHub | Que Colab descargue el código de este repo (si es privado) | Gratis | `GITHUB_TOKEN` | Sí, si el repo es privado |
| 4 | Sketchfab | Buscar y descargar modelos 3D CC0/CC-BY | Gratis | `SKETCHFAB_API_TOKEN` | Sí |
| 5 | api.data.gov (Smithsonian) | Objetos históricos y científicos CC0 | Gratis | `SI_API_KEY` | Recomendado |
| 6 | Freesound | Efectos de sonido CC0/CC-BY | Gratis | `FREESOUND_API_KEY`, `FREESOUND_CLIENT_ID`, `FREESOUND_CLIENT_SECRET` (+ `FREESOUND_REFRESH_TOKEN`, lo genera el sistema) | Recomendado |
| 7 | BlenderKit | Muebles e interiores gratuitos | Gratis | `BLENDERKIT_API_KEY` | Opcional |
| — | Poly Haven, ambientCG, CMU, 100STYLE, Z-Anatomy, Blender Studio, Objaverse | Recursos 3D y animaciones | Gratis | *No necesitan clave* | — |

La **clave del estudio** (`CLAVE_ESTUDIO`, la que pegas en Antigravity) **no la creas tú**: la libreta
la genera la primera vez y la guarda en tu Drive privado.

---

## Paso a paso

Los menús de estos sitios cambian seguido. Si algún nombre no coincide, busca la sección equivalente.

### GitHub — `GITHUB_TOKEN`
1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. **Repository access:** *Only select repositories* → `eddie-studio-3d`.
3. **Permissions → Contents: Read-only.** Nada más.
4. Ponle vencimiento (por ejemplo 1 año) y pégalo en el formulario de la libreta.

### Hugging Face — `HF_TOKEN`
1. Crea una cuenta en huggingface.co → **Settings → Access Tokens → Create new token**.
2. Tipo: **Read**.
3. Con tu sesión iniciada, abre la página de estos modelos y acepta sus términos (algunos lo piden antes de descargar):
   - `nvidia/Kimodo-SOMA-RP-v1.2` (movimiento, NVIDIA Open Model License)
   - Si alguno más lo pide, la libreta te dirá exactamente cuál.

### ngrok (opcional) — `NGROK_AUTHTOKEN`
1. Crea una cuenta gratuita en ngrok.com.
2. **Getting Started → Your Authtoken →** copia el token.
3. **Domains:** el plan gratuito te asigna **un dominio fijo** (algo como `tu-nombre.ngrok-free.app`). La
   libreta lo detecta y lo usa siempre, así la dirección en Antigravity **nunca cambia**.

### Sketchfab — `SKETCHFAB_API_TOKEN`
1. Crea una cuenta gratuita en sketchfab.com.
2. **Settings → Password & API →** copia tu **API Token**.

Solo se descargan modelos marcados como descargables con licencia **CC0** o **CC-BY**. Los créditos
CC-BY se generan solos en `CREDITOS.txt` de cada video, para pegarlos en la descripción.

### Smithsonian (api.data.gov) — `SI_API_KEY`
1. Entra a **api.data.gov/signup**, llena nombre y correo, y te llega la clave al correo.

### Freesound — `FREESOUND_API_KEY`, `FREESOUND_CLIENT_ID`, `FREESOUND_CLIENT_SECRET`
1. Crea una cuenta en freesound.org → **freesound.org/apiv2/apply** → crea una credencial.
2. Copia **Client id** y **Client secret / API key**.
3. Para descargar el archivo **original** (no la vista previa comprimida), Freesound exige OAuth2.
   La primera vez, una celda del sistema te dará un enlace: lo abres, autorizas y pegas el código en la celda.
   El sistema guarda el `FREESOUND_REFRESH_TOKEN` resultante en tu Drive privado.

### BlenderKit (opcional) — `BLENDERKIT_API_KEY`
1. Crea una cuenta en blenderkit.com → tu **perfil → API Key**.

La descarga automática sin interfaz gráfica se comprueba en la Fase 5. Si no funciona de forma
confiable, se desactiva sin afectar lo demás.

---

## Descargas manuales (una sola vez, a tu Drive)

Estas fuentes no tienen API o piden aceptar términos en su web. Bájalas y déjalas en
`Mi unidad/EDDIE_STUDIO/biblioteca/_entrada/` y el sistema las procesa.

| Qué | Dónde | Carpeta de entrada |
|---|---|---|
| Quaternius **Universal Animation Library** 1 y 2 (versión gratuita "Standard") | quaternius.itch.io | `_entrada/quaternius/` |
| Quaternius **Universal Base Characters** | quaternius.itch.io | `_entrada/quaternius/` |
| **Sonniss GDC Game Audio Bundle** (los 3 años más recientes) | sonniss.com/gameaudiogdc | `_entrada/sonniss/` |
| Música (Pixabay Music / YouTube Audio Library), con su página de licencia | pixabay.com/music, YouTube Studio | `_entrada/musica/` |
| *(Opcional)* Mixamo | mixamo.com (cuenta Adobe) | `_entrada/mixamo/` |

---

## Seguridad pendiente en tu Drive

Tus propios informes del Drive (`ESTADO_ACTUAL.md` y `BLOQUEOS_REALES.md`) detectaron que la carpeta
compartida tiene el enlace público con permiso de **Editor**. Cualquiera con el enlace puede borrar o
cambiar archivos.

**Cámbialo a "Lector" o "Restringido"** en Drive: Compartir → Acceso general. Sobre todo porque ahí vivirá tu biblioteca.
