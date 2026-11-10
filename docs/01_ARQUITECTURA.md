# EDDIE STUDIO 3D — Arquitectura del sistema

Sistema para producir videos verticales estilo **«¿Qué pasaría si…?»** (formato His Story) con
**3D renderizado de verdad** en Blender. **Ningún fotograma se genera con IA.** Todo lo que se ve es
geometría, materiales, luces y cámara renderizados.

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
 1. INVESTIGACIÓN Y GUION ........ Antigravity: datos con fuente, guion con la fórmula His Story
 2. VOZ .......................... Colab: narración en español, más tiempos de cada palabra y fonema
 3. PLAN DE TOMAS (JSON) ......... Antigravity: tomas alineadas a la voz (escenario, personajes,
                                   acciones, cámara, luz, objetos)
 4. VALIDACIÓN DEL PLAN .......... Colab: ¿existe cada recurso? Lo que falte se busca automáticamente:
                                   biblioteca → Poly Haven → Sketchfab → Smithsonian → procedural
                                   → reencuadre. Nada queda sin resolver antes de renderizar.
 5. ARMADO EN BLENDER ............ Colab: escena por toma, animación, labios, cámara y luces
 6. PREVIA ....................... Colab: hoja de fotos de cada toma. Antigravity la revisa con
                                   visión y corrige.
 7. RENDER ....................... Colab GPU: EEVEE (rápido) o Cycles (máxima), por bloques que se
                                   pueden retomar
 8. SONIDO Y MONTAJE ............. Colab: música, efectos, mezcla a -14 LUFS, MP4 1080x1920
 9. CONTROL DE CALIDAD ........... Colab: comprobaciones automáticas (§5) y revisión visual final
10. ENTREGA ...................... Drive /entregas/ → Drive para escritorio → Antigravity te da el MP4
```

Cada etapa escribe un **reporte JSON** con lo que hizo, lo que encontró y lo que decidió. Si algo falla,
el sistema aplica su plan B (§4) y lo anota. **Nunca marca "aprobado" algo que no se comprobó mirando la
imagen y el audio.**

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
| Falta un objeto ("piedra", "estadio") | Biblioteca propia | Poly Haven (API, CC0) | Sketchfab (API, solo CC0 o CC-BY descargable) y Smithsonian (CC0) | Procedural (piedras, terreno, edificios simples) o reencuadre de la toma. Se anota en el reporte |
| Falta una animación | Biblioteca de capturas ya adaptada | Mezcla de capturas (caminar + gesto) | *(Opcional, desactivado)* movimiento generado por IA en esqueleto, ver Inventario §6 | Pose fija con microanimación y cámara que lo disimula |
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
Mi unidad/EDDIE_STUDIO/
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
| Personajes | Igual que la calidad de los modelos | Los gratuitos son buenos; para un elenco propio con identidad de canal, ver Inventario §3 (opciones de pago) |
| Movimiento del cuerpo | Natural (captura real) | Biblioteca adaptada al esqueleto estándar |
| Caras y labios | Nivel serie de YouTube | Personajes con controles faciales; visemas de la voz |
| Interacciones finas (abrazos, peleas, ropa física) | Media al inicio | Se agregan plantillas por tipo de interacción |

---

## 8. Fases de construcción y criterios de aceptación

No se pasa a la siguiente fase sin cumplir su criterio, comprobado con archivos reales en tu Colab.

| Fase | Qué se construye | Criterio de aceptación |
|---|---|---|
| **0. Conexión y entorno** | Libreta de arranque (claves, Drive, instalación, modelos locales, servidor MCP, túnel), Blender 5.2 LTS, estructura en Drive | Antigravity se conecta por el túnel, ejecuta un render en la GPU de un cuadro 1080x1920 con Cycles OptiX y con EEVEE, y recibe la imagen. Tiempos medidos |
| **1. Biblioteca base** | Ingesta (descarga → normalización → foto → índice → licencia) de las fuentes del Inventario; esqueleto estándar y adaptación de capturas | Búsqueda de 50 términos de prueba con el resultado correcto y licencia registrada; 100+ animaciones adaptadas sin pies que patinen |
| **2. Voz y tiempos** | TTS, alineación por palabra y fonema, visemas en español | Narración de 120 s con tiempos de palabra verificados (error < 60 ms en muestra revisada) |
| **3. Director de escena** | Plan → escenas Blender, cámaras, luces, labios, expresiones, objetos en mano | Un plan de 12 tomas se arma sin errores y pasa el control de la escena |
| **4. Render y montaje** | Render por bloques reanudable, montaje, mezcla | MP4 de 120 s completo; render interrumpido a propósito y retomado sin cuadros duplicados |
| **5. Búsqueda en internet** | Sketchfab, Smithsonian, Objaverse e indicador de calidad con SigLIP 2 | 20 objetos al azar: al menos 18 resueltos correctamente y el resto con plan B documentado |
| **6. Look y estilo** | Presets de luz y color, cámaras tipo His Story, medición contra referencias | Primer video completo aprobado por ti |
| **7. Robustez** | Reintentos, retomar tras corte, reportes, manual de Antigravity | 3 videos seguidos, de temas distintos, sin intervención manual |

### Lo que honestamente no se puede prometer
- **"100 %" significa que pasa todos los criterios de aceptación.** No significa que nunca haya que repetir una toma.
- La calidad de los personajes es el techo de la imagen. Con recursos gratuitos el resultado es profesional, pero no tendrá un elenco con identidad propia hasta que se encargue o cree uno.
- Los tiempos de render se miden en la Fase 0. Hasta entonces, cualquier número es una estimación.
