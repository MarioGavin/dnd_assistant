# Asistente de reglas del SRD 5.2.1 para el máster de D&D

Responde consultas de reglas de Dungeons & Dragons citando el documento de referencia del sistema (SRD 5.2.1, reglas de 2024) y avisa cuando la regla de 2014 (SRD 5.1) era distinta. Si la respuesta no está en el SRD, lo dice.

Proyecto final de Herramientas de IA Generativa (Máster en IA Aplicada, USJ, 2026-27). **Estado: avance** (ver `FALLOS_CONOCIDOS.md`).

## Ejecutar

En Colab: abrir `cuaderno_colab.ipynb` y crear el secreto `ANTHROPIC_API_KEY`.

En local (Python 3.10+):

```
pip install pymupdf rank-bm25 anthropic pytest
python -m pytest -q
python -m asistente.responder "Tengo 2 niveles de cansancio, ¿qué me pasa al atacar?"
python -m asistente.evaluar --solo-recuperacion --sin-vectores
```

La clave se toma de la variable de entorno `ANTHROPIC_API_KEY` o de un fichero `.env` (no se sube al repositorio).

## Estructura

| Ruta | Contenido |
|---|---|
| `asistente/corpus.py` | PDF del SRD → markdown → fragmentos por apartado con su página |
| `asistente/busqueda.py` | Búsqueda por palabras (BM25), por significado (embeddings) o combinada |
| `asistente/responder.py` | Contexto con las dos ediciones emparejadas y llamada a Claude |
| `asistente/evaluar.py` | Evaluación sobre `casos/casos_prueba.json` |
| `corpus/` | Corpus generado (`fragmentos.jsonl`) y su versión en markdown |
| `casos/` | Conjunto de prueba |
| `tests/` | Tests del corpus y de los casos |

Para regenerar el corpus, descargar en `srd/` `SP_SRD_CC_v5.2.1.pdf` y `SRD_CC_v5.1_ES.pdf` desde https://www.dndbeyond.com/srd y ejecutar `python -m asistente.corpus`.

## Licencia y atribución

Esta obra incluye material procedente del documento de referencia del sistema 5.2.1 ("SRD 5.2.1") y del documento de referencia del sistema 5.1 ("SRD 5.1") de Wizards of the Coast LLC, disponibles en https://www.dndbeyond.com/srd. Ambos se publican con la licencia Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/legalcode).
