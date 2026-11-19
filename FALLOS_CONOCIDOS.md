# Fallos conocidos (entrega final, 20 de noviembre de 2026)

Estado del sistema y lo que se sabe que todavía falla o falta. Las cifras salen de `resultados/`.

## Funciona

- Corpus: SRD 5.2.1 ES (vigente) y SRD 5.1 ES (obsoleto) convertidos de PDF a markdown y troceados por apartados, con documento, ruta y página.
- Consulta de principio a fin: pregunta → BM25 con raíces y sinónimos → contexto (vigentes primero, 2014 solo emparejado) → Claude → respuesta con cita. Decisiones y alternativas: `DECISIONES.md`.
- Validación de fichas de nivel 1 a 5 en código (`asistente/fichas.py`): coste en puntos o conjunto estándar, aumentos de trasfondo y especie, PG y bonificador por competencia, con las tablas de `datos/tablas_srd.json`. El modelo solo explica el resultado; al modelo no llegan nombre, correo ni ID.
- Evaluación completa (`asistente/evaluar.py`): consultas, fichas, coste y tiempo, con repeticiones y tabla comparativa.
- Conjunto de prueba: 20 casos (14 consultas y 6 fichas; 8 normales, 9 límite y 3 que deben fallar). Tests: `python -m pytest`.

## Falla o falta

| # | Qué | Evidencia | Estado |
|---|---|---|---|
| 1 | La recuperación encuentra todas las fuentes de pocas consultas entre los 10 primeros: BM25 6/12; Qwen3-Embedding-0.6B 6/12; bge-m3 3/12; combinada 5/12 | `resultados/recuperacion-*.json` | Mejorado: BM25 con raíces y sinónimos 8/12 (contexto del modelo 9/12). Sigue: N04 y L03 |
| 2 | La fusión combinada hunde fragmentos que una sola búsqueda encuentra arriba (N02: 2.º → 17.º) | `resultados/recuperacion-*.json` | Sigue: BM25 por defecto. Medido otra vez con la búsqueda nueva: combinada @10 6/12 con Qwen3 y 5/12 con bge-m3, frente a BM25 8/12 |
| 3 | Las preguntas que necesitan una tabla además del texto (N03, N04, N08, L03, L08) no la reciben: el modelo se abstiene o no cierra la cuenta | `resultados/*-sin-tablas-r*.json` | Corregido en parte: cada apartado entra con sus tablas, y las de modificadores y bonificador por competencia van siempre (4 de 5 casos reciben ya su tabla; falta la de rasgos de mago, N08). Motivado por estos mismos casos. [PENDIENTE: resultados en Colab] |
| 4 | El emparejamiento 2014 → 2024 se hace por título: falla si el título cambió | `responder.emparejar()` | Sigue |
| 5 | No había validador de fichas | — | Corregido: 6/6 veredictos y motivos (`python -m asistente.fichas`) |
| 6 | No hay herramienta de monstruos (dnd5eapi) | — | Fuera de alcance: L09 y F01 se evalúan sin ella |
| 7 | No había evaluación completa | — | Corregido: Haiku, Sonnet y Haiku con reformulación, tres ejecuciones cada uno (`resultados/comparacion.md`) |
| 8 | Algunas cabeceras de tabla de varias líneas quedan desordenadas al convertir el PDF | `corpus/srd521.md`, p. 71 | Sigue |
| 9 | Los datos personales de las fichas llegarían al modelo | — | Corregido: seudonimización y test sobre la petición enviada |
| 10 | Inyección en la ficha (F03) | `resultados/*-r*.json` | Medido: veredicto ilegal y ningún falso «legal» en las 9 ejecuciones; ninguna explicación marcada para revisar |
| 11 | Respuesta cortada a 1000 tokens con texto visible corto | `resultados/cuaderno_ejecutado_avance.ipynb` | Corregido: `max_tokens` 4000; se guardan `stop_reason` y los tipos de bloque, y una respuesta cortada cuenta como fallo. Causa confirmada: la API devuelve bloques `thinking` y `text`; el razonamiento interno gasta tokens de salida. 0 respuestas cortadas en 27 ejecuciones |
| 12 | El modelo no relaciona «ataque» con «prueba con d20» (L01) | ídem | Mejorado en parte: sinónimos de la guía oficial («tirada de ataque» → «prueba con d20»). «Ataca» o «atacar» no se amplían, porque la guía no lo dice. Alternativa medible: `--reformular`. [PENDIENTE: ver L01 en Colab] |
| 13 | La frase de abstención aparecía dentro de respuestas correctas | ídem, sorpresa | Corregido: instrucción v2 y abstención solo si la respuesta empieza por la frase |
| 14 | Mucho ruido del SRD 5.1 en el contexto (6 de 10 en la sorpresa) | ídem | Corregido: solo fragmentos de 2014 con pareja en 2024 y como mucho 1 (`DECISIONES.md`, fila 5) |
| 15 | La puntuación automática busca términos: puede contar como acierto o fallo algo que no lo es | — | Se leen a mano todos los fallos y una muestra de aciertos |
| 16 | Conjunto pequeño (20 casos, no los 64 del plan): una diferencia de un caso entre configuraciones no es significativa | — | Declarado |
| 17 | El validador no comprueba conjuros, espacios de conjuro ni equipo | `datos/tablas_srd.json` | Declarado. Los valores de las tablas se copiaron del corpus y se comprobaron sobre el PDF con otro extractor (pdftotext): pp. 23, 25, 26, 70, 89, 90-93 y 94 |
| 18 | Al explicar una ficha, el modelo recibía la introducción del apartado y no la tabla de costes | `responder.fragmentos_de()` | Corregido: cada comprobación cita su tabla y el trasfondo o rasgo usado; test |
| 19 | El caso N03 aceptaba «Con» en `requiere`: cualquier «con» contaba como acierto | `casos/casos_prueba.json` | Corregido: «modificador por Con» |
| 20 | La comprobación automática da por fallo respuestas correctas: L01 y L02 escriben «2 × 2 = 4» y no «−4»; L05, «un conjuro por espacio» | Lectura a mano de los fallos | No se cambian los casos después de ver las respuestas: se informa de la puntuación automática y de la lectura a mano |
| 21 | Falta el aviso de 2014 cuando su fragmento no llega al modelo (L02, L05, L08) | ídem | Sigue: es el precio de limitar el SRD 5.1 a un fragmento con pareja de título (fallos 4 y 14) |
| 22 | L09 (dificultad de un encuentro) necesita los PX de un monstruo | ídem | Fuera de alcance (sin dnd5eapi). Se abstiene o da solo los presupuestos: fallo seguro |
| 23 | En `recuperacion-Qwen3-*.json` y `recuperacion-bge-m3.json`, la columna «contexto» se calculó antes de añadir las tablas y con otra lista de candidatos | ídem | Las columnas vectorial, léxica y combinada son válidas; «contexto» no se usa de esos ficheros |
