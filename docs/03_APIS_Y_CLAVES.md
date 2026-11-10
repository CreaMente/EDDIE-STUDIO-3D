# EDDIE STUDIO 3D — APIs gratuitas y claves

## ⚠️ Antes de empezar: dónde van las claves

**No me pegues las claves en el chat, ni a Antigravity, ni en ningún archivo del repo.**
Van directo a **Colab Secrets** (el icono de la llave 🔑 en el panel izquierdo de Colab):

1. Abre tu notebook en Colab → icono 🔑 **Secrets**.
2. **Add new secret** → escribe el **nombre exacto** de la tabla de abajo y pega el valor.
3. Activa **Notebook access** para ese secreto.

El sistema las lee con `google.colab.userdata.get("NOMBRE")`, nunca las imprime y nunca las guarda en
Drive ni en Git. Yo solo necesito saber **qué nombres activaste**, no los valores. Así, si un archivo o
un registro se comparte por error, tus claves no van dentro.

---

## Resumen

| # | Servicio | Para qué | Costo | Nombre(s) en Colab Secrets | ¿Obligatorio? |
|---|---|---|---|---|---|
| 1 | GitHub | Que Colab descargue el código de este repo (si es privado) | Gratis | `GITHUB_TOKEN` | Sí, si el repo es privado |
| 2 | Hugging Face | Descargar modelos de voz, alineación y SigLIP | Gratis | `HF_TOKEN` | Sí |
| 3 | Google Cloud Text-to-Speech | Voz principal (Chirp 3 HD) | 1 millón de caracteres gratis al mes; requiere facturación activada | `GOOGLE_TTS_API_KEY` | Recomendado (hay respaldo local) |
| 4 | Sketchfab | Buscar y descargar modelos 3D CC0/CC-BY | Gratis | `SKETCHFAB_API_TOKEN` | Sí |
| 5 | api.data.gov (Smithsonian) | Objetos históricos y científicos CC0 | Gratis | `SI_API_KEY` | Recomendado |
| 6 | Freesound | Efectos de sonido CC0/CC-BY | Gratis | `FREESOUND_API_KEY`, `FREESOUND_CLIENT_ID`, `FREESOUND_CLIENT_SECRET` (+ `FREESOUND_REFRESH_TOKEN`, lo genera el sistema) | Recomendado |
| 7 | BlenderKit | Muebles e interiores gratuitos | Gratis | `BLENDERKIT_API_KEY` | Opcional |
| — | Poly Haven, ambientCG, CMU, 100STYLE, Z-Anatomy, Blender Studio, Objaverse | Recursos 3D y animaciones | Gratis | *No necesitan clave* | — |

---

## Paso a paso

Los menús de estos sitios cambian seguido. Si algún nombre no coincide, busca la sección equivalente.

### 1. GitHub — `GITHUB_TOKEN`
1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. **Repository access:** *Only select repositories* → `eddie-studio-3d`.
3. **Permissions → Contents: Read-only.** Nada más.
4. Ponle vencimiento (por ejemplo 1 año) y cópialo a Colab Secrets.

### 2. Hugging Face — `HF_TOKEN`
1. Crea una cuenta en huggingface.co → **Settings → Access Tokens → Create new token**.
2. Tipo: **Read**.

### 3. Google Cloud Text-to-Speech — `GOOGLE_TTS_API_KEY`
1. console.cloud.google.com → crea un proyecto (por ejemplo `eddie-studio`).
2. **Facturación:** vincula una cuenta de facturación. Es obligatorio aunque uses solo lo gratuito.
3. **APIs y servicios → Biblioteca →** habilita **Cloud Text-to-Speech API**.
4. **APIs y servicios → Credenciales → Crear credenciales → Clave de API.**
5. **Restringe la clave:** *Restricciones de API* → solo **Cloud Text-to-Speech API**.
6. **Protección de gasto (muy recomendado):**
   - **Facturación → Presupuestos y alertas →** presupuesto de 1 USD con alerta.
   - **Cuotas:** limita los caracteres diarios del servicio.

   El sistema además lleva su propio contador mensual y cambia a la voz local antes de pasar el millón de caracteres.

### 4. Sketchfab — `SKETCHFAB_API_TOKEN`
1. Crea una cuenta gratuita en sketchfab.com.
2. **Settings → Password & API →** copia tu **API Token**.

Solo se descargan modelos marcados como descargables con licencia **CC0** o **CC-BY**. Los créditos
CC-BY se generan solos en `CREDITOS.txt` de cada video, para pegarlos en la descripción.

### 5. Smithsonian (api.data.gov) — `SI_API_KEY`
1. Entra a **api.data.gov/signup**, llena nombre y correo, y te llega la clave al correo.

### 6. Freesound — `FREESOUND_API_KEY`, `FREESOUND_CLIENT_ID`, `FREESOUND_CLIENT_SECRET`
1. Crea una cuenta en freesound.org → **freesound.org/apiv2/apply** → crea una credencial.
2. Copia **Client id** y **Client secret / API key**.
3. Para descargar el archivo **original** (no la vista previa comprimida), Freesound exige OAuth2.
   La primera vez, una celda del sistema te dará un enlace: lo abres, autorizas y pegas el código en la celda.
   El sistema guarda el `FREESOUND_REFRESH_TOKEN` resultante y te dice que lo agregues a Secrets.

### 7. BlenderKit (opcional) — `BLENDERKIT_API_KEY`
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
