# Decisiones de diseño

Cada decisión, con la alternativa descartada y el dato que la sostiene. Las cifras salen de `resultados/`; lo que falta por medir va marcado como [PENDIENTE]. Los fallos y cómo se corrigieron están en `FALLOS_CONOCIDOS.md`.

| # | Decisión | Descartado | Dato | Dónde |
|---|---|---|---|---|
| 1 | Corpus: SRD 5.2.1 ES; el SRD 5.1 ES entra marcado como obsoleto | Corpus en inglés; solo 2024 | Pregunta, corpus y cita en el mismo idioma; los casos límite necesitan la regla de 2014 para avisar del cambio | `asistente/corpus.py` |
| 2 | Búsqueda por palabras (BM25) | Por significado (Qwen3-Embedding, bge-m3) y combinada | Con la búsqueda nueva, @10: BM25 8/12; combinada 6/12 (Qwen3) y 5/12 (bge-m3); por significado 6/12 y 3/12. La fusión hunde fragmentos (N02: 2.º → 17.º) | `resultados/recuperacion-*.json` |
| 3 | BM25 con raíces de las palabras y sinónimos de 2014 → 2024 | BM25 sin más; solo raíces; solo sinónimos | Recall@5 4 → 7 de 12; @10 6 → 8; con todas sus fuentes en el contexto 8 → 9. Solo sinónimos: contexto 7. Comprobado con 12 consultas de contraste escritas después y no usadas para decidir: @10 5 → 7, contexto 6 → 9 (casi todo por las raíces) | `resultados/recuperacion-bm25*.json`, `casos/consultas_contraste.json` |
| 4 | Los sinónimos salen de la guía oficial de conversión (`converting-to-srd-5.2.1.pdf`) | Una lista hecha mirando los casos que fallan | Evita ajustar el sistema a los casos de prueba | `datos/sinonimos.json` |
| 5 | Del SRD 5.1, solo fragmentos con pareja de título en 2024 y como mucho 1 | Sin límite, 2 o ninguno | Con 1: contexto 9/12 y fragmento de 2014 esperado en 4 de 6 casos límite. Con 2 o sin límite: 8/12 y 4/6. Con 0: 0/6 | `responder.seleccionar()` |
| 5b | El modelo recibe 10 fragmentos | 5, 7 o 15 | Consultas con todas sus fuentes en el contexto: 7, 8, 9 y 9 de 12; con 15 crece el mensaje un 36 % sin ganar ninguna | `responder.K` |
| 6 | `max_tokens` = 4000 y se registra `stop_reason` | 1000 | Respuesta cortada en el avance (5813 + 1000 tokens, texto visible corto) | `resultados/cuaderno_ejecutado_avance.ipynb` |
| 7 | Sin `temperature`; tres ejecuciones por modelo | `temperature = 0` | La API de los modelos actuales no la acepta; la variabilidad se mide repitiendo | `responder.llamar()` |
| 8 | Abstención: la respuesta empieza por «No está en el SRD 5.2.1.» | Buscar la frase en cualquier parte | En el avance la frase apareció dentro de una respuesta correcta | `responder.abstiene()` |
| 9 | El veredicto de una ficha lo decide el código; el modelo solo lo explica | Que el modelo calcule o decida | El validador acierta 6 de 6 fichas; la orden escrita en la historia de F03 no puede cambiar el veredicto | `asistente/fichas.py` |
| 10 | Tablas del SRD como datos, con apartado y página | Valores en el código | Ampliar niveles es añadir datos; un test comprueba que cada fuente existe en el corpus | `datos/tablas_srd.json` |
| 11 | Nombre, correo e ID se sustituyen por un seudónimo antes de llamar | Enviar la ficha entera | El validador no los necesita; un test revisa la petición enviada | `fichas.seudonimizar()` |
| 12 | Puntuación automática: números y palabras cortas como palabra entera | Buscar subcadenas | «6» contaba dentro de «16» o «1d6» | `evaluar.aparece()` |
| 13 | Candidato: Claude Haiku 5.5; se compara con Sonnet 5.5 | Opus 5.5 (coste), GPT-OSS-20B (memoria de la GPU), Qwen local (tiempo) | [PENDIENTE: resultados de Colab] | `resultados/comparacion.md` |
| 14 | Reformular la pregunta con un modelo antes de buscar: opción `--reformular`, desactivada | Activarla por defecto | Una llamada más por consulta. [PENDIENTE: Haiku ×3 con y sin reformular] | `responder.reformular()` |
| 15 | No enrutar a Sonnet según haya fragmentos de 2014 (queda la opción `--enrutar`) | Haiku por defecto y Sonnet cuando el contexto trae 2014 | El criterio no separa: hay fragmentos de 2014 entre los primeros puestos en 12 de 14 consultas del conjunto y en 12 de 12 de contraste; sería casi siempre Sonnet | `responder.responder()` |
| 16 | Cada apartado entra con sus tablas, y las de modificadores y bonificador por competencia van siempre en el contexto | Solo los fragmentos que trae la búsqueda | Sin tablas, el modelo se abstiene o no cierra la cuenta en N03, N04, N08, L03 y L08 en las 9 ejecuciones; con ellas, la tabla llega en 4 de esos 5 casos y el mensaje crece un 12 %. Motivado por estos casos. [PENDIENTE: resultados en Colab] | `responder.anadir_tablas()`, `resultados/*-sin-tablas-r*.json` |

