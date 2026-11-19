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
| 2 | La fusión combinada hunde fragmentos que una sola búsqueda encuentra arriba (N02: 2.º → 17.º) | ídem | Sigue: BM25 por defecto |
| 3 | Las preguntas que necesitan fórmula + tabla (N04, L03, N08) no recuperan todas las fuentes | ídem | Sigue en consultas; en fichas las cuentas las hace el validador |
| 4 | El emparejamiento 2014 → 2024 se hace por título: falla si el título cambió | `responder.emparejar()` | Sigue |
| 5 | No había validador de fichas | — | Corregido: 6/6 veredictos y motivos (`python -m asistente.fichas`) |
| 6 | No hay herramienta de monstruos (dnd5eapi) | — | Fuera de alcance: L09 y F01 se evalúan sin ella |
| 7 | No había evaluación completa | — | Corregido. [PENDIENTE: resultados de Haiku y Sonnet en Colab] |
| 8 | Algunas cabeceras de tabla de varias líneas quedan desordenadas al convertir el PDF | `corpus/srd521.md`, p. 71 | Sigue |
| 9 | Los datos personales de las fichas llegarían al modelo | — | Corregido: seudonimización y test sobre la petición enviada |
| 10 | Inyección en la ficha (F03) | — | El veredicto lo pone el código; si la explicación del modelo dice «legal», se marca para revisarla a mano. [PENDIENTE: medir] |
| 11 | Respuesta cortada a 1000 tokens con texto visible corto | `resultados/cuaderno_ejecutado_avance.ipynb` | Corregido: `max_tokens` 4000; se guardan `stop_reason` y los tipos de bloque, y una respuesta cortada cuenta como fallo. [PENDIENTE: confirmar la causa con los bloques registrados] |
| 12 | El modelo no relaciona «ataque» con «prueba con d20» (L01) | ídem | Mejorado en parte: sinónimos de la guía oficial («tirada de ataque» → «prueba con d20»). «Ataca» o «atacar» no se amplían, porque la guía no lo dice. Alternativa medible: `--reformular`. [PENDIENTE: ver L01 en Colab] |
| 13 | La frase de abstención aparecía dentro de respuestas correctas | ídem, sorpresa | Corregido: instrucción v2 y abstención solo si la respuesta empieza por la frase |
| 14 | Mucho ruido del SRD 5.1 en el contexto (6 de 10 en la sorpresa) | ídem | Corregido: solo fragmentos de 2014 con pareja en 2024 y como mucho 1 (`DECISIONES.md`, fila 5) |
| 15 | La puntuación automática busca términos: puede contar como acierto o fallo algo que no lo es | — | Se leen a mano todos los fallos y una muestra de aciertos |
| 16 | Conjunto pequeño (20 casos, no los 64 del plan): una diferencia de un caso entre configuraciones no es significativa | — | Declarado |
| 17 | El validador no comprueba conjuros, espacios de conjuro ni equipo | `datos/tablas_srd.json` | Declarado. Los valores de las tablas se copiaron del corpus y se comprobaron sobre el PDF con otro extractor (pdftotext): pp. 23, 25, 26, 70, 89, 90-93 y 94 |
| 18 | Al explicar una ficha, el modelo recibía la introducción del apartado y no la tabla de costes | `responder.fragmentos_de()` | Corregido: cada comprobación cita su tabla y el trasfondo o rasgo usado; test |
| 19 | El caso N03 aceptaba «Con» en `requiere`: cualquier «con» contaba como acierto | `casos/casos_prueba.json` | Corregido: «modificador por Con» |
