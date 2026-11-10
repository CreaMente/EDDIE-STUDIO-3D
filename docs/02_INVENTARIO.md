# EDDIE STUDIO 3D — Inventario completo

Todo lo que el sistema necesita: programas, modelos, bibliotecas 3D, animaciones, sonido y servicios.

**Regla de licencias:** solo entra lo que permite **uso comercial** (videos monetizados). Se acepta:
CC0, CC-BY (con créditos automáticos), MIT, Apache-2.0, GPL (programas) y licencias libres de regalías.
**Nunca:** NC (no comercial), ND (sin derivados), "editorial", modelos extraídos de juegos ni sitios sin licencia clara.

Columnas:
- **Obtención:** `auto` = el sistema lo descarga solo; `clave` = necesita tu clave API (ver `03_APIS_Y_CLAVES.md`); `manual` = lo bajas tú una vez y lo dejas en Drive.
- **Tamaño:** aproximado, para planear el espacio en Drive.

---

## 1. Programas base (en Colab)

| Componente | Para qué | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Blender 5.2 LTS** (Linux x64) | Escenas, animación y render (Cycles OptiX / EEVEE) | GPL | auto (copia en Drive) | ~0.4 GB |
| ffmpeg | Montaje, codificación H.264/AAC, medición de audio | LGPL/GPL | auto (apt) | — |
| Python 3 + librerías: `numpy`, `opencv-python`, `trimesh`, `pygltflib`, `pyloudnorm`, `soundfile`, `librosa`, `jsonschema`, `pydantic`, `requests`, `tqdm` | Validaciones, procesamiento, esquemas | MIT / BSD / Apache | auto (pip) | ~1 GB |
| SQLite FTS5 | Índice de búsqueda de la biblioteca | Dominio público | incluido | — |

## 2. Programas en tu PC (Windows)

| Componente | Para qué | Licencia | Obtención |
|---|---|---|---|
| Google Antigravity | El cerebro: guion, plan y uso de las herramientas por el túnel | Google | ya lo tienes |
| Google Drive para escritorio | Que los MP4 de `entregas/` aparezcan en tu PC y Antigravity los entregue | Google | manual (instalar) |
| Pestaña de Colab abierta | Mantiene viva la sesión mientras trabaja | — | — |

## 2b. Servidor y túnel (en Colab)

| Componente | Para qué | Licencia | Obtención |
|---|---|---|---|
| FastMCP (Python) | Servidor MCP con las herramientas del estudio y el control del runtime | Apache-2.0 | auto (pip) |
| ngrok | Túnel HTTPS con dirección fija gratuita | Gratis con cuenta | clave (`NGROK_AUTHTOKEN`) |
| cloudflared | Túnel de respaldo sin cuenta | Apache-2.0 | auto |

---

## 3. Personajes

| Fuente | Qué trae | Licencia | Obtención | Nota |
|---|---|---|---|---|
| **MPFB2** (MakeHuman para Blender) | Humanos paramétricos: edad, cuerpo, etnia, ropa; esqueleto con controles de cara | Programa GPL; recursos CC0 / CC-BY según paquete | auto | Fuente principal de **gente común** del formato «¿qué pasaría si?». Se le da un estilo propio de piel y materiales |
| **[Blender Studio Characters](https://studio.blender.org/characters/)** (Rain, Snow, Ellie, Victoria, Einar, Phil, Vincent…) | Personajes estilizados profesionales con esqueleto y cara animable | CC-BY (crédito "Blender Foundation", se verifica por personaje) | auto | Calidad de estudio. Se descargan sin cuenta: comprobado con Rain v3 (64 MB) |
| **Quaternius Universal Base Characters** | 6 personajes base compatibles con su biblioteca de animaciones | CC0 | manual (itch.io, gratis) | Útiles para extras y multitudes |
| **Z-Anatomy** | Atlas anatómico completo: huesos, músculos, órganos, nervios | CC-BY-SA 4.0 | auto (GitHub) | **Clave para «¿qué pasaría si…?» del cuerpo.** Se **excluyen** sus piezas NC (oído interno, un riñón) |
| BodyParts3D | Anatomía complementaria | CC-BY-SA 2.1 JP | auto | Opcional |
| *(De pago, opcional)* Character Creator 5 + ActorCore | Elenco propio con identidad de canal, caras de alta calidad | Comercial (licencia de pago) | manual | Recomendado cuando el canal crezca |
| *(De pago, opcional)* Encargo a artista 3D | Personajes fijos exclusivos | Contrato | manual | Máxima identidad |

## 4. Escenarios, objetos y materiales

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **[Poly Haven](https://polyhaven.com/our-api)** | 521 modelos, 997 HDRI (iluminación real), 869 texturas (cifras consultadas hoy en su API) | CC0. Su API es gratis incluso para uso comercial desde julio de 2026; piden mencionar que los recursos son de Poly Haven | auto (API sin clave) | ~60–80 GB a 2K/4K |
| **[ambientCG](https://ambientcg.com/)** | ~2,900 materiales PBR | CC0 | auto (API sin clave) | ~20 GB (selección 2K) |
| **Sketchfab** (API v3) | Cientos de miles de modelos; se filtran solo descargables con CC0 o CC-BY | CC0 / CC-BY por modelo | clave | Bajo demanda |
| **Smithsonian Open Access** | Objetos históricos y científicos escaneados | CC0 | clave (api.data.gov) | Bajo demanda |
| **Objaverse 1.0** (índice) | Índice de ~800 mil modelos con su licencia, para buscar sin conexión y descargar del espejo de Hugging Face | Licencia por objeto (se filtra igual que Sketchfab) | auto | ~2 GB de índice |
| **BlenderKit** (recursos gratis) | Muebles, interiores, objetos de buena calidad | Libre de regalías / CC0 | clave | Bajo demanda. La descarga automática sin interfaz **se verifica en la Fase 5** |
| Kenney / Quaternius (escenarios) | Objetos sencillos de relleno | CC0 | manual | ~2 GB. Solo para fondos lejanos (estilo low-poly) |
| **Escenarios propios del sistema** | Casa, cocina, baño, recámara, sala, hospital, consultorio, calle, escuela, oficina, parque, gimnasio, estadio, vista microscópica | Propios, armados con lo anterior | Se construyen en la Fase 1/6 | — |

## 5. Animaciones (captura de movimiento real, no IA)

Todas se **adaptan una vez** a un **esqueleto estándar** del sistema y se etiquetan
("cojear", "caer", "sentarse", "tocarse la rodilla", "llorar").

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Quaternius Universal Animation Library 1 y 2** | 120+ animaciones por paquete en esqueleto universal: caminar en 8 direcciones, correr, sentarse, arrastrarse, nadar, morir… | CC0 | manual (itch.io, gratis) | ~1 GB |
| **CMU Motion Capture Database** | ~2,500 capturas de la vida cotidiana y deportes | Uso libre, incluso en productos comerciales (no se puede revender la base) | auto | ~1 GB |
| **100STYLE** | Caminatas en 100 estilos (cansado, herido, alegre, viejo…) | CC-BY 4.0 | auto | ~1.5 GB |
| *(Opcional)* Mixamo | Miles de animaciones; uso libre en tus videos | Adobe (gratis con cuenta, no redistribuible, **sin API**) | manual | — |

## 6. Modelos de IA locales (solo audio y datos, **nunca imagen**)

**Regla:** todo corre **localmente en tu GPU** y se instala al ejecutar la libreta. Los pesos quedan en
caché en Drive para no bajarlos cada vez. Solo se usa una API cuando la versión con API es mucho mejor
**y** gratuita. Para voz no es el caso: los modelos abiertos de 2026 alcanzan a las APIs gratuitas, así
que **la voz es 100 % local**.

Estas piezas no generan fotogramas. Todo lo que se ve sigue siendo render 3D. Licencias verificadas
hoy en las fichas oficiales de Hugging Face.

| Componente | Para qué | Licencia | Estado |
|---|---|---|---|
| **VoxCPM2** (OpenBMB, 2B, 48 kHz, 30 idiomas con español) | **Voz principal.** Diseño de voz por descripción ("narrador masculino, latino, cálido, enérgico") y clonación | Apache-2.0, uso comercial | Principal |
| **Fun-CosyVoice3** (Alibaba FunAudioLLM, 0.5B) | Segunda voz y respaldo, con la misma referencia del narrador | Apache-2.0 | Respaldo |
| **Chatterbox Multilingual v3** (Resemble AI) | Respaldo; tiene ajuste para español latino | MIT (marca de agua inaudible) | Respaldo |
| Qwen3-TTS 1.7B (VoiceDesign / CustomVoice) | Muy buena en español y con control de emoción por instrucción | Apache-2.0 | **Pendiente:** tenías una regla de "0 % Qwen". ¿La mantienes? |
| **faster-whisper large-v3** | Transcribe cada toma de voz para comprobar que dice exactamente el guion (si no, se regenera) | MIT | Principal |
| **WhisperX + wav2vec2 español** | Tiempos exactos de cada palabra y fonema, para sincronizar tomas y labios | BSD / Apache-2.0 | Principal |
| Visemas en español (propio) + Rhubarb Lip Sync | Labios a partir de los fonemas | Propio / MIT | Principal |
| **SigLIP 2** (so400m) | Comprobar que un modelo descargado "parece" lo pedido; ordenar búsquedas | Apache-2.0 | Principal |
| **ACE-Step 1.5 XL** | Música original de fondo generada localmente, sin reclamos de derechos | MIT | Principal (más biblioteca curada) |
| **NVIDIA Kimodo SOMA** (checkpoint `Kimodo-SOMA-RP-v1.2`) | Texto → movimiento de esqueleto, para acciones que no estén en la biblioteca de capturas | NVIDIA Open Model License (permite uso comercial). **El checkpoint SMPL-X es solo para investigación: excluido** | Instalado, **se activa con tu permiso** (es movimiento generado por IA, no imagen) |
| OpenImageDenoise / OptiX Denoiser | Quitar el ruido del render de Cycles (estándar de la industria, no inventa contenido) | Apache-2.0 / NVIDIA | Principal |

**Descartados por licencia no comercial:** OmniVoice (pesos CC-BY-NC), XTTS-v2 (CPML), F5-TTS base
(CC-BY-NC), MMAudio (CC-BY-NC), Fish Speech (CC-BY-NC-SA).

**Descartado por tu regla de "nada de IA en imagen":** generadores de modelos 3D por IA (TRELLIS y similares).

### APIs que se mantienen (no hay alternativa local)
Solo **fuentes de datos**, no modelos: Sketchfab, Smithsonian, Freesound, BlenderKit, Poly Haven y
ambientCG. Son bibliotecas en internet; no existe una versión "local" de su contenido salvo descargarlo,
que es justo lo que hace el sistema.

## 7. Sonido y música

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Sonniss GDC Game Audio Bundles** (varios años) | Decenas de miles de efectos profesionales | Libre de regalías, uso comercial, sin atribución. Prohíbe entrenar IA (no lo hacemos) | manual (descarga gratis anual) | ~30 GB por paquete. Recomiendo 3 → ~90 GB |
| **Freesound** (API) | Efectos específicos que falten | Solo CC0 / CC-BY (filtro) | clave | Bajo demanda |
| Pixabay Music / YouTube Audio Library | Música de fondo | Licencias libres para videos (se registra cada pista) | manual | ~5–10 GB curados |
| ACE-Step 1.5 XL (local, ver §6) | Música original generada en tu GPU | MIT | auto | ~10 GB de pesos |

## 8. Referencias de estilo (no se publican)

| Qué | Para qué |
|---|---|
| 10–20 shorts de His Story que te gusten (los guardas tú en Drive) | Medir con números luz, color, ritmo de cámara y cortes, igual que hizo LuisPa. **Solo para estudiar el estilo.** No se copian historias, personajes ni tomas |
| `herramientas/medir_30fps.py` del repo de LuisPa (MIT) | Base de la herramienta de medición |

---

## 9. Espacio estimado en Drive

| Bloque | Tamaño aprox. |
|---|---|
| Programas y modelos de IA locales (voz, Whisper, SigLIP, música, movimiento) | 50–70 GB |
| Poly Haven + ambientCG | 80–100 GB |
| Personajes, anatomía y animaciones | 10–15 GB |
| Sonido y música | 100 GB |
| Índices y fotos de la biblioteca | 5 GB |
| Proyectos (cuadros temporales, se limpian al entregar) | 20–50 GB por proyecto activo |
| **Total inicial** | **≈ 300–350 GB** |

## 10. Lo que se descarta a propósito

| Qué | Por qué |
|---|---|
| "Descargar todo internet" | Mezcla estilos, licencias dudosas, esqueletos incompatibles, terabytes. La rapidez sale de una biblioteca **preparada**, no gigante |
| Generadores de video o imagen por IA | Tu requisito: todo debe ser render 3D |
| Sitios de modelos sin licencia clara, modelos de videojuegos | Riesgo legal y archivos `.blend` con código que se ejecuta al abrir |
| Datasets de entrenamiento (como los 14.75 GB del zip anterior) | No aportan nada a la imagen |
| Voz por API (Google Chirp, ElevenLabs) | Los modelos locales de 2026 están a la par de lo gratuito; ElevenLabs solo permite uso comercial en planes de pago |
