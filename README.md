# Asistente de reglas del SRD 5.2.1 para el máster de D&D

Responde consultas de reglas de Dungeons & Dragons citando el documento de referencia del sistema (SRD 5.2.1, reglas de 2024) y avisa cuando la regla de 2014 (SRD 5.1) era distinta. Si la respuesta no está en el SRD, lo dice. También valida fichas de personaje de nivel 1 a 5: las cuentas las hace el código con las tablas del SRD y el modelo solo explica el resultado.

Proyecto final de Herramientas de IA Generativa (Máster en IA Aplicada, USJ, 2026-27). **Estado: entrega final** (ver `FALLOS_CONOCIDOS.md`).

## Ejecutar

En Colab: abrir `cuaderno_colab.ipynb` y crear el secreto `ANTHROPIC_API_KEY`.

En local (Python 3.10+):

```
pip install pymupdf rank-bm25 snowballstemmer anthropic pytest
python -m pytest -q
python -m asistente.responder "Tengo 2 niveles de cansancio, ¿qué me pasa al atacar?"   # Haiku, reformulando y con contexto ampliado
python -m asistente.responder "..." --sin-reformular --sin-contexto-amplio               # búsqueda y contexto básicos
python -m asistente.fichas                                   # valida las fichas de los casos, sin modelo
python -m asistente.evaluar --solo-recuperacion --sin-vectores
python -m asistente.evaluar --modelo claude-haiku-5-5 --repeticiones 3
python -m asistente.evaluar --modelo claude-haiku-5-5 --reformular --contexto-amplio --repeticiones 3   # configuración entregada
python -m asistente.evaluar --modelo claude-haiku-5-5 --reformular --repeticiones 3
python -m asistente.evaluar --modelo claude-haiku-5-5 --tablas-padre --repeticiones 3 # opción medida (fallo 24)
python -m asistente.evaluar --modelo Qwen/Qwen3-4B --repeticiones 1   # modelo local: necesita GPU, torch, transformers y accelerate
python -m asistente.evaluar --modelo Qwen/Qwen3-8B --repeticiones 1   # en 16 bits si cabe en la GPU (medido en bf16 en una L4); si no, en 4 bits con bitsandbytes
python -m asistente.evaluar --repuntuar                      # vuelve a puntuar lo guardado con el detector actual
python -m asistente.evaluar --wilson                         # aciertos con intervalo de Wilson al 95 % (resultados/wilson.md)
python -m asistente.evaluar --tabla                          # compara las ejecuciones de resultados/
```

La clave se toma de la variable de entorno `ANTHROPIC_API_KEY` o de un fichero `.env` (no se sube al repositorio).

En las fichas, el nombre, el correo y el ID del jugador se sustituyen por un seudónimo antes de llamar al modelo (`fichas.seudonimizar`).

## Estructura

| Ruta | Contenido |
|---|---|
| `asistente/corpus.py` | PDF del SRD → markdown → fragmentos por apartado con su página |
| `asistente/busqueda.py` | Búsqueda por palabras (BM25 con raíces y sinónimos), por significado (embeddings) o combinada |
| `asistente/responder.py` | Contexto (2024 primero, 2014 emparejado, cada apartado con sus tablas) y llamada a Claude |
| `asistente/fichas.py` | Validador de fichas (coste en puntos, bonificadores, PG, competencia) y seudonimización |
| `asistente/evaluar.py` | Evaluación sobre `casos/casos_prueba.json`: recuperación, o completa con el modelo |
| `datos/tablas_srd.json` | Tablas del SRD que usa el validador, con apartado y página |
| `datos/sinonimos.json` | Términos de 2014 → 2024 de la guía oficial de conversión, para la búsqueda |
| `DECISIONES.md` | Decisiones de diseño, con la alternativa descartada y el dato |
| `corpus/` | Corpus generado (`fragmentos.jsonl`) y su versión en markdown |
| `casos/` | Conjunto de prueba (`casos_prueba.json`) y consultas de contraste para la búsqueda (`consultas_contraste.json`) |
| `resultados/` | Resultados de cada ejecución (`<modelo>-r<n>.json`) y `comparacion.md` |
| `tests/` | Tests del corpus, la búsqueda, los casos, las fichas, `responder` y `evaluar` |

Para regenerar el corpus, descargar en `srd/` `SP_SRD_CC_v5.2.1.pdf` y `SRD_CC_v5.1_ES.pdf` desde https://www.dndbeyond.com/srd y ejecutar `python -m asistente.corpus`.

## Licencia y atribución

Esta obra incluye material procedente del documento de referencia del sistema 5.2.1 ("SRD 5.2.1") y del documento de referencia del sistema 5.1 ("SRD 5.1") de Wizards of the Coast LLC, disponibles en https://www.dndbeyond.com/srd. Ambos se publican con la licencia Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/legalcode).
