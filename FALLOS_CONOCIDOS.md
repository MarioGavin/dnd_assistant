# Fallos conocidos (avance, 15 de noviembre de 2026)

Estado del prototipo y lo que se sabe que todavía falla o falta.

## Funciona

- Corpus: SRD 5.2.1 ES (vigente) y SRD 5.1 ES (obsoleto) convertidos de PDF a markdown y troceados por apartados, con documento, ruta y página. 33 tests pasan.
- Consulta de principio a fin: pregunta → búsqueda → contexto con los fragmentos numerados → Claude Haiku 5.5 → respuesta con cita. Probado con 3 consultas: el contemplador se abstiene correctamente y la sorpresa da la regla de 2024 y avisa del cambio de 2014 (unos 0,001 $ y 3-5 s por consulta).
- Conjunto de prueba: 20 casos (8 normales, 9 límite, 3 que deben fallar), 6 de ellos fichas de personaje.
- Evaluación de la recuperación por apartado (recall@5 y @10), sin coste.

## Falla o falta

| # | Qué | Evidencia | Previsto |
|---|---|---|---|
| 1 | La recuperación encuentra todas las fuentes de solo 5-6 de 12 consultas entre los 10 primeros fragmentos, con cualquier configuración: BM25 6/12; por significado Qwen3-Embedding-0.6B 6/12, bge-m3 3/12; combinada 5/12 con los dos | `resultados/cuaderno_ejecutado_avance.ipynb` | Analizar caso a caso; probar más candidatos por lista y una lista de sinónimos del SRD |
| 2 | La fusión combinada hunde fragmentos que una sola búsqueda encuentra arriba: «Caídas» es 2.º por significado y 17.º en la combinada (N02); «Cansancio» 9.º → 19.º (L02). Es el mismo efecto que el ejemplo de la asignatura (caso de la aguja) | ídem | Medir la fusión con pesos o con más candidatos; no se corrige mirando solo estos casos |
| 3 | Las preguntas que necesitan varias fuentes (fórmula + tabla: N04, L03, N08) no recuperan todas: la fórmula de «Rellena los números» (p. 24) no aparece en ninguna búsqueda | ídem | Que los cálculos los haga la herramienta con las tablas del SRD, sin depender de recuperar la fórmula |
| 4 | El emparejamiento 2014 → 2024 se hace por título del apartado: falla si el título cambió entre ediciones | `asistente/responder.py`, `emparejar()` | Tabla de correspondencias revisada a mano para los apartados de los casos límite |
| 5 | No hay validador de fichas: las 6 fichas del conjunto no tienen todavía veredicto | — | Calculadoras (coste en puntos, PG, competencia, espacios de conjuro) con tests |
| 6 | No hay herramienta de monstruos (dnd5eapi): L09 y F01 no pueden comprobarse | — | Consulta a dnd5eapi con caché local |
| 7 | La evaluación completa (respuesta, cita, abstención, coste y tiempo con el modelo) no está implementada | `asistente/evaluar.py` | Modo completo y comparación Haiku / Sonnet / Qwen |
| 8 | Algunas cabeceras de tabla de varias líneas quedan desordenadas al convertir el PDF (las filas de datos son correctas) | `corpus/srd521.md`, p. 71 | Revisión manual por muestreo (`corpus/muestra_revision.md`) |
| 9 | Los datos personales de las fichas (nombre, correo, ID) se enviarían al modelo | — | Seudonimización local antes de la llamada |
| 10 | La resistencia a la inyección de instrucciones no está medida | — | Casos F03 y variantes |
| 11 | Respuesta cortada: en la consulta del cansancio la salida llega a 1000 tokens y el texto termina a medias («Cambio respecto a 2014: en a»). El texto visible es corto, así que el límite se consume antes de escribir la respuesta | `resultados/cuaderno_ejecutado_avance.ipynb`, sección 3 | Subir `max_tokens`, registrar `stop_reason` y marcar como fallo toda respuesta cortada |
| 12 | El modelo no relaciona «ataque» con «prueba con d20»: no recupera el apartado que define las pruebas con d20 y dice que no puede confirmar que el ataque esté incluido | ídem | Mejorar la recuperación (fallos 1-3); caso L01 |
| 13 | La frase de abstención aparece dentro de respuestas correctas («No está en el SRD 5.2.1 que los bandidos pierdan su primer turno. Lo que sí dice…»): un detector que solo busque la frase lo contaría como abstención | ídem, consulta de la sorpresa | Instrucción: la frase solo cuando no hay respuesta; el detector comprueba que la respuesta empieza por ella |
| 14 | La búsqueda trae mucho ruido del SRD 5.1 (6 de 10 fragmentos en la consulta de la sorpresa) | ídem | Limitar los fragmentos de 2014 a los que tengan pareja en 2024 |
