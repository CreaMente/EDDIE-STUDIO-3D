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

## 5. Animaciones de captura real (biblioteca)

Todas se **adaptan una vez** a un **esqueleto estándar** del sistema y se etiquetan
("cojear", "caer", "sentarse", "tocarse la rodilla", "llorar").

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Quaternius Universal Animation Library 1 y 2** | 120+ animaciones por paquete en esqueleto universal: caminar en 8 direcciones, correr, sentarse, arrastrarse, nadar, morir… | CC0 | manual (itch.io, gratis) | ~1 GB |
| **CMU Motion Capture Database** | ~2,500 capturas de la vida cotidiana y deportes | Uso libre, incluso en productos comerciales (no se puede revender la base) | auto | ~1 GB |
| **100STYLE** | Caminatas en 100 estilos (cansado, herido, alegre, viejo…) | CC-BY 4.0 | auto | ~1.5 GB |
| *(Opcional)* Mixamo | Miles de animaciones; uso libre en tus videos | Adobe (gratis con cuenta, no redistribuible, **sin API**) | manual | — |

## 6. Modelos de IA locales (todo menos generar video)

**Regla:** la IA hace todo el trabajo, pero **ningún modelo genera ni retoca los fotogramas finales**;
esos salen siempre del render de Blender. Todo corre **localmente en tu GPU**, se instala al ejecutar
la libreta y los pesos quedan en caché en Drive. Solo se usa una API cuando es mucho mejor **y**
gratuita (hoy, ninguna supera a estas opciones locales).

Licencias verificadas hoy en las fichas oficiales de Hugging Face. Todas permiten uso comercial.

### 6.1 Voz y tiempos
| Modelo | Para qué | Licencia |
|---|---|---|
| **VoxCPM2** (OpenBMB, 2B, 48 kHz) | **Voz principal** en español; diseño de voz por descripción y clonación. La voz del narrador se guarda y es la misma en todos los videos | Apache-2.0 |
| Fun-CosyVoice3 (0.5B) | Respaldo con la misma voz de referencia | Apache-2.0 |
| Chatterbox Multilingual v3 | Respaldo; tiene ajuste para español latino | MIT (marca de agua inaudible) |
| faster-whisper large-v3 | Verifica que cada frase diga exactamente el guion; si no, se regenera | MIT |
| WhisperX + wav2vec2 español | Tiempo exacto de cada palabra y fonema | BSD / Apache-2.0 |

### 6.2 Animación
| Modelo | Para qué | Licencia |
|---|---|---|
| **NVIDIA Kimodo** (`Kimodo-SOMA-RP-v1.2`) | **Texto → movimiento del esqueleto** ("cojea apoyándose en la pared, se sienta con dolor"), con restricciones de pies, trayectoria y poses clave; también genera transiciones entre clips | NVIDIA Open Model License (comercial). **El checkpoint SMPL-X es solo para investigación: excluido** |
| **NVIDIA Audio2Face-3D v3.0** | **Cara completa a partir de la voz:** labios, lengua, mandíbula, ojos y emoción (salida de *blendshapes* tipo ARKit) | NVIDIA Open Model License (comercial) |
| Tencent HY-Motion 1.0 | Segundo modelo texto → movimiento | Tencent Hunyuan Community: **no aplica en la UE, Reino Unido ni Corea del Sur**. Solo si estás fuera de esos territorios |
| Limpieza propia (sin IA) | Pies bloqueados en el piso (IK), suavizado de curvas, sin atravesar el suelo, mezcla de clips | Propio |

### 6.3 Creación de modelos 3D
| Modelo | Para qué | Licencia |
|---|---|---|
| **Z-Image-Turbo** (Tongyi) | Imagen de concepto del objeto en el **estilo fijo del canal** (paso previo al 3D) y texturas | Apache-2.0 |
| FLUX.2-klein-4B | Alternativa para concepto y texturas | Apache-2.0 (**las variantes 9B y FLUX.2-dev son no comerciales: excluidas**) |
| **TRELLIS.2-4B** (Microsoft) | **Imagen → modelo 3D con textura PBR** | MIT |
| Step1X-3D | Alternativa imagen → 3D | Apache-2.0 |
| PartCrafter | Modelos 3D separados por partes (puertas que abren, objetos articulados) | MIT |
| **UniRig** (VAST) | Esqueleto automático para modelos generados (personajes y animales extra) | MIT |
| Puppeteer (Seed3D) | Esqueleto y pesos automáticos, alternativa | Apache-2.0 |
| Hunyuan3D-2.1 | Alternativa imagen → 3D | Tencent Community (mismas restricciones territoriales que HY-Motion) |

### 6.4 Dirección y control de calidad
| Modelo | Para qué | Licencia |
|---|---|---|
| **Gemma 4** (31B o 26B-A4B, visión) | Revisor visual **local**: mira hojas de contacto y fotos, compara con el plan y propone correcciones sin esperar a Antigravity | Apache-2.0 |
| **SigLIP 2** (so400m) | Comprueba que un modelo descargado o generado "parece" lo pedido; ordena búsquedas | Apache-2.0 |

### 6.5 Audio
| Modelo | Para qué | Licencia |
|---|---|---|
| **ACE-Step 1.5 XL** | Música original de fondo | MIT |
| Sonniss (biblioteca principal) + Freesound (manual) | Efectos de sonido reales | Libre de regalías / CC0 / CC-BY |

### 6.6 Render
| Componente | Para qué | Licencia |
|---|---|---|
| OptiX Denoiser / OpenImageDenoise | Elimina el ruido del render de Cycles con muchas menos muestras (render varias veces más rápido). No inventa contenido: limpia el ruido del cálculo de luz | NVIDIA / Apache-2.0 |

### Descartados
| Qué | Por qué |
|---|---|
| Wan, Veo / Flow, Kling, Sora, HunyuanVideo, LTX-Video, CogVideoX | **Generadores de video: prohibidos por la regla de oro** |
| Mejoradores de imagen sobre los fotogramas (upscalers con IA, img2img) | Retocarían los fotogramas finales |
| OmniVoice, XTTS-v2, F5-TTS base, Fish Speech, MMAudio, FLUX.2-dev, FLUX.2-klein-9B | Licencias no comerciales |
| Kimodo SMPL-X | Licencia de investigación de NVIDIA |
| Modelos Qwen (Qwen3-TTS, Qwen-Image, Qwen3-VL) | Tienen licencia libre, pero respeto tu regla de "0 % Qwen" hasta que me digas lo contrario. Hay alternativas equivalentes arriba |

### APIs que se mantienen
Solo **fuentes de recursos**: Sketchfab, Smithsonian, Freesound, BlenderKit, Poly Haven y ambientCG.
Son bibliotecas en internet; su contenido no se puede "generar localmente", se descarga.

## 7. Sonido y música

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Sonniss GDC Game Audio Bundles** (varios años) | Decenas de miles de efectos profesionales | Libre de regalías, uso comercial, sin atribución. Prohíbe entrenar IA (no lo hacemos) | manual (descarga gratis anual) | ~30 GB por paquete. Recomiendo 3 → ~90 GB |
| Freesound | Efectos específicos que falten (solo CC0 / CC-BY) | **La API es gratuita solo para uso no comercial**: un canal monetizado necesita licencia de MTG-UPF. Sin licencia, se descargan a mano desde la web | manual (o clave + licencia) | Bajo demanda |
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
| Programas y modelos de IA locales (voz, animación, 3D, visión, música) | 150–200 GB |
| Poly Haven + ambientCG | 80–100 GB |
| Personajes, anatomía y animaciones | 10–15 GB |
| Sonido y música | 100 GB |
| Índices y fotos de la biblioteca | 5 GB |
| Proyectos (cuadros temporales, se limpian al entregar) | 20–50 GB por proyecto activo |
| **Total inicial** | **≈ 400–500 GB** |

## 10. Lo que se descarta a propósito

| Qué | Por qué |
|---|---|
| "Descargar todo internet" | Mezcla estilos, licencias dudosas, esqueletos incompatibles, terabytes. La rapidez sale de una biblioteca **preparada**, no gigante |
| Generadores de video por IA | Regla de oro: todo fotograma sale de Blender |
| Sitios de modelos sin licencia clara, modelos de videojuegos | Riesgo legal y archivos `.blend` con código que se ejecuta al abrir |
| Datasets de entrenamiento (como los 14.75 GB del zip anterior) | No aportan nada a la imagen |
| Voz por API (Google Chirp, ElevenLabs) | Los modelos locales de 2026 están a la par de lo gratuito; ElevenLabs solo permite uso comercial en planes de pago |
