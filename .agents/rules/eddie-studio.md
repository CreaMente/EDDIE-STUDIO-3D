# Reglas de EDDIE STUDIO 3D

## 1. Producción
- **Regla de oro:**
  - la IA hace todo, pero **ningún generador de video**;
  - cada fotograma sale de Blender;
  - ninguna IA retoca fotogramas renderizados (los eliminadores de ruido de Cycles sí se permiten).
- **Licencias:** solo recursos y modelos con uso comercial (CC0, CC-BY con crédito, MIT, Apache-2.0,
  NVIDIA Open Model License).
  - Nunca NC, ND ni "editorial".
  - Todo recurso CC-BY se anota en `CREDITOS.txt` del proyecto.
- **Modelos Qwen:** no se usan (regla del propietario) salvo que él lo autorice.
- **Consistencia:**
  - los protagonistas son siempre los mismos modelos 3D del elenco fijo;
  - la voz del narrador es siempre la misma referencia guardada en `EDDIE_STUDIO/voces/`.

## 2. Guion «¿Qué pasaría si…?» (estilo His Story)
- **Primera frase = gancho.** La pregunta o la consecuencia más impactante, sin introducción, sin "hola", sin logo.
- **Segunda persona.** "Te rompes la rodilla…", "Tu cuerpo…". Presente.
- **Escalada temporal clara.** "En los primeros minutos…", "Al tercer día…", "Una semana después…".
  Cada etapa es más grave o más sorprendente que la anterior.
- **Mecanismo real.** Explicar *por qué* pasa, con una comparación cotidiana ("es como…").
- **Cierre con giro.** Dato final sorprendente o consecuencia irónica. El video termina en la última palabra.
- **Ritmo de narración:** frases de ~10–14 palabras, 3.0–3.8 palabras por segundo (ritmo ágil del formato), casi sin silencios.
- **Lo que se ve no se narra.** La voz agrega información, no describe la imagen.
- **Datos.** Médicos y científicos verificados, con fuente anotada arriba del `GUION.md`.
  - Si hay incertidumbre, se dice ("en la mayoría de los casos…").
  - Nada de consejos médicos peligrosos.

## 3. Imagen y cámara
- **Tomas.** Cada frase tiene su toma. Cambios de toma alineados a palabras (tiempos de WhisperX).
- **La cámara nunca está quieta.**
  - Siempre un acercamiento, una órbita lenta o un desplazamiento.
  - Movimientos que arrancan rápido y frenan suave.
  - Cortes duros solo en saltos de lugar.
- **Planos.**
  - Detalle (zapatos, mano, rodilla).
  - Medio (reacción del personaje).
  - Interior del cuerpo: corte anatómico o rayos X estilizado con anatomía 3D real.
  - Plano general para ubicar.
- **Luz y color.**
  - Luz principal cálida, sombras azuladas suaves.
  - Colores saturados pero no chillones.
  - Contraste cinematográfico (AgX).
  - Profundidad de campo en planos cercanos.
- **Personajes.** Expresión facial acorde a la frase (dolor, sorpresa, alivio). Labios sincronizados con la voz.
- **Texto en pantalla:** mínimo; solo una cifra o etapa clave ("DÍA 3"), arriba, sin tapar caras.
  Sin subtítulos salvo que se pidan.

## 4. Calidad (antes de entregar)
- **Hoja de contacto** de cada toma revisada visualmente. Revisa:
  - cámara dentro de objetos;
  - personaje fuera de cuadro;
  - pies atravesando el piso o flotando;
  - manos atravesando objetos;
  - objetos gigantes o diminutos;
  - parpadeos de luz.
- **Audio:** -14 LUFS integrados, pico ≤ -1 dBTP, sin silencios > 1 s.
- **Video:** 1080x1920, 30 fps, H.264 + AAC, duración pedida ±0.2 s.
- **Reporte final** al propietario:
  - qué se generó con IA, qué se descargó (con licencia) y qué falló;
  - cómo se resolvió lo que falló.
