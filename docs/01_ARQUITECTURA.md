# EDDIE STUDIO 3D — Arquitectura del sistema

Sistema para producir videos verticales estilo **«¿Qué pasaría si…?»** (formato His Story) con
**3D renderizado de verdad** en Blender, **automatizado por IA de principio a fin**.

> **Regla de oro:** la IA puede hacer **todo**: guion, voz, dirección, crear modelos 3D, texturas,
> esqueletos, animación del cuerpo (Kimodo), animación de la cara (Audio2Face), música, revisión de
> calidad. Lo único **prohibido** son los **generadores de video** (Wan, Veo, Flow, Kling, Sora,
> HunyuanVideo, LTX y similares) y cualquier modelo que dibuje o retoque los fotogramas finales.
> **Cada fotograma sale del render de Blender.** Así la consistencia es total: un personaje es un
> modelo 3D y la cámara solo se mueve a su alrededor.

- **Cerebro:** Google Antigravity. Recibe tu pedido, escribe el guion, decide las tomas y usa las herramientas.
- **Estudio:** Google Colab de pago con RTX PRO 6000 (96 GB VRAM). Ahí se instalan y corren todas las herramientas.
- **Memoria permanente:** Google Drive Pro. Guarda la biblioteca 3D, los modelos de voz, los proyectos y las entregas.
- **Código:** este repositorio. Colab lo clona en cada sesión, así que una sesión cortada no pierde nada.

---

## 1. Flujo completo de un video

```
Tú, en Antigravity:
  "Video de 120 s: ¿qué pasaría si te rompes la rodilla y no te ponen yeso? Calidad máxima."
        │
        ▼
 1. INVESTIGACIÓN Y GUION ...... Antigravity: datos con fuente, guion con la fórmula His Story
 2. VOZ ........................ VoxCPM2 local: 3 tomas por frase; Whisper verifica cada una
 3. TIEMPOS .................... WhisperX: cada palabra y fonema con su tiempo exacto
 4. PLAN DE TOMAS (JSON) ....... Antigravity: tomas alineadas a la voz (escenario, elenco, acciones
                                 en texto, cámara, luz, objetos)
 5. RECURSOS ................... por cada objeto, personaje o escenario:
                                 biblioteca → Poly Haven / Sketchfab / Smithsonian →
                                 IA 3D (imagen de concepto → TRELLIS.2 → modelo con textura) →
                                 auto-rig (UniRig) si debe moverse. Todo queda en la biblioteca.
 6. ANIMACIÓN DEL CUERPO ....... Kimodo (texto → movimiento) o capturas de la biblioteca;
                                 adaptación al esqueleto del personaje, pies bloqueados en el piso,
                                 suavizado y transiciones entre acciones
 7. ANIMACIÓN DE LA CARA ....... Audio2Face-3D: labios, mandíbula, ojos y emoción a partir de la voz;
                                 parpadeos y miradas automáticos
 8. ARMADO EN BLENDER .......... escenas por toma, cámara cinematográfica, luces del preset
 9. PREVIA + REVISIÓN IA ....... hoja de fotos por toma; Gemma 4 (visión, local) y Antigravity la
                                 revisan contra el plan y corrigen automáticamente
10. RENDER ..................... GPU: EEVEE (rápido) o Cycles + eliminación de ruido (máxima),
                                 por bloques que se retoman si se cae la sesión
11. SONIDO Y MONTAJE ........... música ACE-Step, efectos, mezcla a -14 LUFS, MP4 1080x1920
12. CONTROL DE CALIDAD ......... comprobaciones automáticas (§5) + revisión visual final
13. ENTREGA .................... Drive /entregas/ → tu PC → Antigravity te entrega el MP4
```

Cada etapa escribe un **reporte JSON** con lo que hizo, lo que encontró y lo que decidió. Si algo falla,
el sistema aplica su plan B (§4) y lo anota. **Nunca marca "aprobado" algo que no se comprobó mirando la
imagen y el audio.**

### Gestor de GPU
Los 96 GB de VRAM se reparten **por etapa**: cada modelo de IA se carga, trabaja en lote y se descarga
antes del siguiente. Por ejemplo: voz → Audio2Face → Kimodo → TRELLIS.2 → render. Así nunca chocan
por memoria y Blender tiene la GPU completa al renderizar. Los pesos viven en Drive y se copian al
disco local al iniciar la etapa.

---

## 2. Cómo se conecta Antigravity con Colab: túnel MCP (decisión del propietario)

La libreta levanta dentro de Colab un **servidor MCP** (el estándar con el que los agentes usan
herramientas) y lo publica con un **túnel HTTPS protegido con clave**. Antigravity se conecta a esa
dirección y tiene acceso a:

- **Herramientas del estudio** (§3): voz, búsqueda, armado, render, montaje, control de calidad.
- **Control total del runtime:** terminal (`ejecutar_comando`), Python (`ejecutar_python`), scripts de
  Blender (`ejecutar_blender`), leer, escribir y listar archivos, subir y bajar archivos.
  Así puede editar y corregir el sistema por dentro.

### Túnel
| | ngrok (principal) | Cloudflare Quick Tunnel (respaldo automático) |
|---|---|---|
| Dirección | **Fija para siempre** (dominio gratuito de tu cuenta): se configura en Antigravity **una sola vez** | Cambia en cada sesión |
| Requiere | Cuenta gratuita + `NGROK_AUTHTOKEN` | Nada |
| Límite gratuito | 1 GB de transferencia y 20 mil peticiones al mes: suficiente porque los videos **no viajan por el túnel**, se entregan por Drive | Sin límite publicado; pensado para pruebas |

### Seguridad
- Cada petición exige la cabecera `Authorization: Bearer <CLAVE_ESTUDIO>`. La clave se genera al azar
  la primera vez, se guarda en tu Drive privado y no cambia entre sesiones.
- El servidor solo atiende a Antigravity. No sirve archivos al público ni actúa como proxy.
- Todo comando queda registrado en `proyectos/_registro/`.

### Riesgo aceptado por el propietario
Las [reglas de Colab](https://research.google.com/colaboratory/faq.html) prohíben en todos los
runtimes los "web service offerings not related to interactive compute with Colab" y "connecting to
remote proxies". Este uso es tu propio agente controlando tu propio cómputo, pero Google podría
interpretarlo distinto. Para reducir el riesgo:
- la celda queda **activa y visible** mostrando el registro;
- no se sirve contenido a terceros;
- los MP4 salen por Drive, no por el túnel.

**Respaldo sin túnel**, si algún día lo necesitas: el conector oficial
[`googlecolab/colab-mcp`](https://github.com/googlecolab/colab-mcp), donde Antigravity crea y ejecuta
celdas en la pestaña abierta. El paquete `estudio` funciona igual con ambos.

---

## 3. Paquete `estudio` (las herramientas que usa Antigravity)

Todas devuelven JSON con `ok`, `detalles`, `advertencias` y `archivos`. Ninguna falla en silencio.

| Función | Qué hace |
|---|---|
| `estudio.iniciar(calidad)` | Monta Drive, copia Blender, modelos y el índice al disco local de Colab, verifica la GPU (OptiX), las claves y el espacio. Devuelve un diagnóstico |
| `estudio.nuevo_proyecto(titulo, duracion_s, calidad)` | Crea `proyectos/<id>/` con su estructura |
| `estudio.voz(id, guion, voz)` | Narración, tiempos por palabra y fonema, visemas para los labios |
| `estudio.buscar(consulta, tipo, estilo)` | Busca en la biblioteca y, si no está, en internet. Normaliza, verifica y guarda en la biblioteca |
| `estudio.validar_plan(id, plan)` | Comprueba el plan contra el esquema y la biblioteca. Resuelve faltantes o propone reencuadres |
| `estudio.armar(id)` | Construye las escenas `.blend` por toma |
| `estudio.previa(id, tomas)` | Fotos sueltas y hoja de contacto por toma, para revisión visual |
| `estudio.render(id, calidad)` | Render por bloques en la GPU. Si la sesión se corta, se retoma |
| `estudio.montar(id)` | Voz, música, efectos, mezcla y MP4 |
| `estudio.qc(id)` | Todas las comprobaciones de §5 |
| `estudio.entregar(id)` | Copia el MP4 y el reporte final a `entregas/` |
| `estudio.estado(id)` | En qué etapa va y qué falta, para retomar tras un corte |

Antigravity también recibe un **manual del director** (`.agents/` en este repo) con la fórmula del
guion, el esquema del plan, la librería de cámaras y las reglas de estilo. Así sabe usar las
herramientas igual cada vez.

### Plan de tomas (resumen del esquema)
```json
{
  "formato": "vertical_1080x1920", "fps": 30, "calidad": "maxima",
  "elenco": {"protagonista": {"personaje": "lib:humano/joven_01", "vestuario": "casual_02"}},
  "tomas": [
    {
      "id": "T03", "desde_palabra": 41, "hasta_palabra": 58,
      "escenario": "lib:interior/cocina_01", "luz": "dia_calida",
      "acciones": [{"actor": "protagonista", "anim": "lib:mocap/cojear_dolor_01", "inicio_s": 0.0}],
      "expresion": [{"actor": "protagonista", "cara": "dolor", "intensidad": 0.8}],
      "objetos": [{"ref": "buscar:muleta de aluminio", "colocar": "mano_derecha"}],
      "camara": {"preset": "zapatos_a_cara", "lente_mm": 35, "enfoque": "protagonista.cabeza"},
      "transicion": "corte_suave"
    }
  ]
}
```

---

## 4. Que no se frene: cadenas de respaldo

| Problema | Plan A | Plan B | Plan C | Último recurso |
|---|---|---|---|---|
| Falta un objeto ("piedra", "estadio") | Biblioteca propia | Poly Haven, Sketchfab (solo CC0/CC-BY) y Smithsonian | **IA 3D:** imagen de concepto (Z-Image) → modelo con textura (TRELLIS.2) en el estilo del canal | Procedural (piedras, terreno, edificios) o reencuadre. Se anota en el reporte |
| Falta un personaje secundario | Biblioteca de personajes | MPFB2: humano paramétrico a partir de la descripción | IA 3D + auto-rig (UniRig / Puppeteer) | Silueta en segundo plano o fuera de foco |
| Falta una animación | Capturas reales de la biblioteca (máxima fidelidad) | **Kimodo:** texto → movimiento, con restricciones de pies y trayectoria | Combinación de clips con transiciones generadas | Pose con microanimación y cámara que lo disimula |
| Una frase de voz sale mal (Whisper no reconoce el texto) | Se regenera con otra semilla (se generan 3 tomas por frase y se elige la mejor) | Fun-CosyVoice3 con la misma voz de referencia | Chatterbox | Se marca en el reporte |
| La sesión de Colab se corta | Se retoma desde el último bloque renderizado (`estudio.estado`) | — | — | — |
| La GPU no da OptiX | CUDA | — | — | CPU, avisando el tiempo |
| El render tarda más de lo estimado | Bajar muestras con eliminación de ruido | EEVEE en vez de Cycles en tomas lejanas | — | — |

**Todo recurso descargado** se normaliza y se guarda en la biblioteca con: licencia, autor, fuente,
escala real, orientación, materiales corregidos, foto de prueba y etiquetas. La segunda vez ya está listo.

---

## 5. Control de calidad automático

| Etapa | Comprobaciones |
|---|---|
| Recurso importado | Escala real (una persona mide unos 1.7 m), sin geometría rota, texturas presentes, polígonos dentro del presupuesto, licencia comercial registrada |
| Escena armada | Cámara fuera de los objetos, protagonista visible (cobertura de la máscara de objeto), pies tocando el suelo, sin cuerpos atravesados, objetos en la mano dentro de 2 cm |
| Fotogramas | Sin cuadros negros ni vacíos, exposición dentro de rango (histograma), sin saltos bruscos entre cuadros salvo en cortes planificados |
| Audio | -14 LUFS integrados, pico real ≤ -1 dBTP, voz y video con la misma duración, sin silencios > 1 s |
| Video final | 1080x1920, 30 fps, H.264 + AAC, duración pedida ±0.2 s, todos los cuadros presentes |
| Visual | Antigravity revisa la hoja de contacto (24 cuadros) contra la lista de tomas y el estilo |
| Estilo | Medición contra referencias como hace `medir_30fps.py` de LuisPa: brillo, saturación, % de cuadros con cámara en movimiento, cortes |

---

## 6. Drive Pro: organización

```
Mi unidad/EDDIE_PRIVADO/     claves de API, clave del estudio, conexión actual (siempre privada)

<carpeta de trabajo del link> (por defecto Mi unidad/EDDIE_STUDIO/)
├── sistema/          blender-5.2-linux.tar.xz, ruedas de Python precompiladas
├── modelos_ia/       voz (VoxCPM2, CosyVoice3, Chatterbox), Whisper, SigLIP 2, música   (~40–60 GB)
├── voces/            la voz fija del narrador (referencia) para que todos los videos suenen igual
├── biblioteca/
│   ├── indice.sqlite   búsqueda por texto y etiquetas, más vectores de imagen
│   ├── personajes/ escenarios/ objetos/ anatomia/
│   ├── animaciones/    ya adaptadas al esqueleto estándar
│   ├── hdri/ texturas/ sonidos/ musica/
│   └── licencias/      un registro por recurso, más CREDITOS generados por video
├── proyectos/<id>/   guion, voz, plan, .blend, cuadros, reportes
└── entregas/         MP4 finales y su reporte
```

**Arranque de cada sesión** (una celda): monta Drive, clona el repo y copia al disco local de Colab
solo lo que hace falta (Blender, modelos de voz, índice y los recursos del proyecto). Así no se
leen miles de archivos chicos por Drive, que es lento. Objetivo: listo en menos de 5 minutos.
Se medirá en la Fase 0.

---

## 7. Calidad: qué se puede lograr y de qué depende

| Pieza | Calidad esperada | Depende de |
|---|---|---|
| Imagen (luz, materiales, desenfoque, desenfoque de movimiento) | Muy alta, nivel cine | Presets de luz y color ajustados una vez (Fase 6) |
| Personajes protagonistas | Alta y **idéntica en todos los videos** | Elenco fijo (MPFB2/Blender Studio) con cara preparada para Audio2Face; más adelante, elenco propio encargado |
| Personajes y objetos generados por IA (TRELLIS.2) | Buena para objetos y extras; menor que un modelo hecho a mano en caras | Se usan para objetos, extras y fondos; los protagonistas usan el elenco fijo |
| Movimiento del cuerpo | Natural (capturas reales y Kimodo) | Limpieza automática: pies bloqueados, suavizado, transiciones |
| Caras y labios | Nivel serie de YouTube o mejor | Audio2Face-3D a partir de la voz, con emoción |
| Interacciones finas (abrazos, peleas, ropa física) | Media al inicio | Se agregan plantillas por tipo de interacción |

---

## 8. Fases de construcción y criterios de aceptación

No se pasa a la siguiente fase sin cumplir su criterio, comprobado con archivos reales en tu Colab.

| Fase | Qué se construye | Criterio de aceptación |
|---|---|---|
| **0. Conexión y entorno** | Libreta de arranque (claves, Drive, instalación, modelos locales, servidor MCP, túnel), Blender 5.2 LTS, estructura en Drive | Antigravity se conecta por el túnel, ejecuta un render en la GPU de un cuadro 1080x1920 con Cycles OptiX y con EEVEE, y recibe la imagen. Tiempos medidos |
| **1. Biblioteca base** | Ingesta (descarga → normalización → foto → índice → licencia) de las fuentes del Inventario; esqueleto estándar y adaptación de capturas | Búsqueda de 50 términos de prueba con el resultado correcto y licencia registrada; 100+ animaciones adaptadas sin pies que patinen |
| **2. Voz y tiempos** | TTS, alineación por palabra y fonema, visemas en español | Narración de 120 s con tiempos de palabra verificados (error < 60 ms en muestra revisada) |
| **3. Director de escena y animación** | Plan → escenas Blender, cámaras, luces; Kimodo + adaptación de esqueleto + limpieza de pies; Audio2Face en la cara; objetos en mano | Un plan de 12 tomas se arma sin errores y pasa el control de la escena; ningún pie patina > 2 cm |
| **4. Render y montaje** | Render por bloques reanudable, montaje, mezcla | MP4 de 120 s completo; render interrumpido a propósito y retomado sin cuadros duplicados |
| **5. Recursos automáticos** | Sketchfab, Smithsonian, Objaverse, SigLIP 2; generación IA 3D (Z-Image → TRELLIS.2) y auto-rig | 20 objetos al azar: los 20 resueltos (descargados o generados), con escala y estilo correctos |
| **6. Look y estilo** | Presets de luz y color, cámaras tipo His Story, medición contra referencias | Primer video completo aprobado por ti |
| **7. Robustez** | Reintentos, retomar tras corte, reportes, manual de Antigravity | 3 videos seguidos, de temas distintos, sin intervención manual |

### Lo que honestamente no se puede prometer
- **"100 %" significa que pasa todos los criterios de aceptación.** No significa que nunca haya que repetir una toma.
- La calidad de los personajes es el techo de la imagen. Con recursos gratuitos el resultado es profesional, pero no tendrá un elenco con identidad propia hasta que se encargue o cree uno.
- Los tiempos de render se miden en la Fase 0. Hasta entonces, cualquier número es una estimación.
