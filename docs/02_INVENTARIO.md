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
| Google Antigravity | El cerebro: guion, plan y uso de las herramientas | Google | ya lo tienes |
| [`googlecolab/colab-mcp`](https://github.com/googlecolab/colab-mcp) + `uv` | Conecta Antigravity con tu pestaña de Colab (crear y ejecutar celdas) | Apache-2.0 | auto (`uvx`) |
| Google Drive para escritorio | Que los MP4 de `entregas/` aparezcan en tu PC y Antigravity los entregue | Google | manual (instalar) |
| Chrome con la pestaña de Colab abierta | El MCP oficial trabaja a través de esa pestaña | — | — |

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

## 6. IA permitida (solo datos y audio, **nunca imagen**)

Estas piezas no generan fotogramas: producen voz, tiempos o datos de esqueleto. Todo lo que se ve
sigue siendo render 3D. Las marcadas **APAGADO** solo se activan si tú lo autorizas.

| Componente | Para qué | Licencia | Obtención | Estado |
|---|---|---|---|---|
| **Google Cloud TTS — Chirp 3 HD** | Voz principal en español, muy natural | Comercial. 1 millón de caracteres gratis al mes (≈ 500 videos de 2 min); requiere tener facturación activada | clave | Principal |
| **Chatterbox Multilingual** (Resemble AI) | Voz local en la GPU, español, clonación con tu consentimiento | MIT (incluye marca de agua inaudible) | auto | Respaldo |
| Kokoro-82M | Voz local rápida | Apache-2.0 | auto | Segundo respaldo |
| **faster-whisper large-v3** + WhisperX con wav2vec2 en español | Tiempos exactos de cada palabra y fonema (para sincronizar tomas y labios) | MIT / BSD / Apache | auto | Principal |
| Visemas en español (propio) + Rhubarb Lip Sync | Labios a partir de los fonemas | Propio / MIT | auto | Principal |
| **SigLIP 2** | Comprobar que el modelo descargado "parece" lo pedido; ordenar resultados de búsqueda | Apache-2.0 | auto | Principal |
| NVIDIA Kimodo / ARDY (texto → movimiento de esqueleto) | Animaciones que no existen en la biblioteca | Código Apache-2.0; pesos NVIDIA Open Model License (revisar qué checkpoint permite uso comercial) | auto | **APAGADO** |
| TRELLIS (texto o imagen → modelo 3D) | Último recurso para un objeto inexistente | MIT (verificar versión) | auto | **APAGADO** (el resultado sería geometría hecha por IA) |

## 7. Sonido y música

| Fuente | Qué trae | Licencia | Obtención | Tamaño |
|---|---|---|---|---|
| **Sonniss GDC Game Audio Bundles** (varios años) | Decenas de miles de efectos profesionales | Libre de regalías, uso comercial, sin atribución. Prohíbe entrenar IA (no lo hacemos) | manual (descarga gratis anual) | ~30 GB por paquete. Recomiendo 3 → ~90 GB |
| **Freesound** (API) | Efectos específicos que falten | Solo CC0 / CC-BY (filtro) | clave | Bajo demanda |
| Pixabay Music / YouTube Audio Library | Música de fondo | Licencias libres para videos (se registra cada pista) | manual | ~5–10 GB curados |
| *(Opcional)* ACE-Step (música generada) | Música original sin derechos de terceros | Apache-2.0 | auto | **APAGADO** |

## 8. Referencias de estilo (no se publican)

| Qué | Para qué |
|---|---|
| 10–20 shorts de His Story que te gusten (los guardas tú en Drive) | Medir con números luz, color, ritmo de cámara y cortes, igual que hizo LuisPa. **Solo para estudiar el estilo.** No se copian historias, personajes ni tomas |
| `herramientas/medir_30fps.py` del repo de LuisPa (MIT) | Base de la herramienta de medición |

---

## 9. Espacio estimado en Drive

| Bloque | Tamaño aprox. |
|---|---|
| Programas y modelos de IA permitidos | 25 GB |
| Poly Haven + ambientCG | 80–100 GB |
| Personajes, anatomía y animaciones | 10–15 GB |
| Sonido y música | 100 GB |
| Índices y fotos de la biblioteca | 5 GB |
| Proyectos (cuadros temporales, se limpian al entregar) | 20–50 GB por proyecto activo |
| **Total inicial** | **≈ 250–300 GB** |

## 10. Lo que se descarta a propósito

| Qué | Por qué |
|---|---|
| "Descargar todo internet" | Mezcla estilos, licencias dudosas, esqueletos incompatibles, terabytes. La rapidez sale de una biblioteca **preparada**, no gigante |
| Generadores de video o imagen por IA | Tu requisito: todo debe ser render 3D |
| Sitios de modelos sin licencia clara, modelos de videojuegos | Riesgo legal y archivos `.blend` con código que se ejecuta al abrir |
| Datasets de entrenamiento (como los 14.75 GB del zip anterior) | No aportan nada a la imagen |
| Túnel con servidor web propio en Colab | Las reglas de Colab lo prohíben en todos los runtimes (ver Arquitectura §2) |
