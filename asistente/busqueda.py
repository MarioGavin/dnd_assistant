"""Búsqueda sobre el corpus: por palabras (BM25), por significado (embeddings) o
combinada, fusionando las dos listas por posición: 1 / (60 + puesto).

Adapta indice(), listas() y buscar() del ejemplo de la asignatura Herramientas de
IA Generativa (USJ, curso 2026-27). Cambios: modelo de embeddings configurable (por
defecto Qwen3-Embedding-0.6B), 20 candidatos por lista y vectores guardados en disco
para no recalcularlos en cada ejecución.

Uso:
    from asistente.busqueda import Buscador
    b = Buscador()                       # combinada (necesita sentence-transformers)
    b = Buscador(vectorial=False)        # solo BM25, sin modelo de embeddings
    b.buscar("¿Qué pasa con 2 niveles de cansancio?", k=10)

Por defecto, BM25 con raíces (snowballstemmer: «caer» y «caídas» coinciden) y con los
sinónimos de 2014 → 2024 de datos/sinonimos.json (guía oficial de conversión). Ver DECISIONES.md.
"""
import json
import hashlib
import re
import unicodedata
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from asistente.corpus import RAIZ, cabecera, cargar

MODELO_EMB = "Qwen/Qwen3-Embedding-0.6B"
CANDIDATOS = 20          # puestos de cada lista que entran en la fusión
RRF = 60                 # constante de la fusión por posición
RAICES = True            # BM25 sobre raíces de las palabras
SINONIMOS = True         # añadir a la pregunta los términos de 2024 (datos/sinonimos.json)

# Cómo espera cada modelo las preguntas y los documentos.
#   Qwen3-Embedding: instrucción en la pregunta (prompt_name="query"), documento tal cual.
#   bge-m3: sin prefijos.   e5: "query: " y "passage: ".
FORMATO = {
    "Qwen/Qwen3-Embedding-0.6B": {"pregunta": {"prompt_name": "query"}, "doc": ""},
    "BAAI/bge-m3": {"pregunta": {}, "doc": ""},
    "intfloat/multilingual-e5-small": {"pregunta": {"prompt": "query: "}, "doc": "passage: "},
    "intfloat/multilingual-e5-large": {"pregunta": {"prompt": "query: "}, "doc": "passage: "},
}


def palabras(texto, raices=False):
    """Minúsculas, sin tildes, solo letras y números; con raices=True, cada palabra reducida
    a su raíz («ataque», «atacar» → «ataqu», «atac»)."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    lista = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", texto)
    if raices:
        import snowballstemmer
        lista = snowballstemmer.stemmer("spanish").stemWords(lista)
    return lista


def expandir(pregunta):
    """Añade a la pregunta el término de 2024 de cada término de 2014 que contenga."""
    n = " ".join(palabras(pregunta))
    tabla = json.load(open(RAIZ / "datos" / "sinonimos.json", encoding="utf-8"))["sinonimos"]
    extra = [s["a"] for s in tabla if any(re.search(rf"\b{d}\b", n) for d in s["de"])]
    return " ".join([pregunta] + extra)


def texto_indexado(f):
    return f"{cabecera(f)}\n{f['texto']}"


class Buscador:
    def __init__(self, fragmentos=None, vectorial=True, modelo=MODELO_EMB, dispositivo=None,
                 raices=RAICES, sinonimos=SINONIMOS):
        self.fragmentos = fragmentos if fragmentos is not None else cargar()
        self.raices, self.sinonimos = raices, sinonimos
        self.bm25 = BM25Okapi([palabras(texto_indexado(f), raices) for f in self.fragmentos])
        self.modelo = modelo if vectorial else None
        self.codificador, self.vectores = None, None
        if vectorial:
            from sentence_transformers import SentenceTransformer
            self.codificador = SentenceTransformer(modelo, device=dispositivo)
            self.codificador.max_seq_length = 512      # los fragmentos rara vez pasan de 512 tokens
            self.vectores = self._vectores()

    # ---------------------------------------------------------------- índice vectorial
    def _vectores(self):
        """Calcula los vectores de los fragmentos, o los lee de disco si el corpus y el
        modelo no han cambiado (la huella cubre ids, textos y nombre del modelo)."""
        huella = hashlib.sha1((self.modelo + "".join(f["id"] + f["texto"] for f in self.fragmentos))
                              .encode("utf-8")).hexdigest()[:12]
        ruta = RAIZ / "corpus" / "indices" / f"{self.modelo.replace('/', '__')}-{huella}.npy"
        if ruta.exists():
            return np.load(ruta)
        prefijo = FORMATO.get(self.modelo, {"doc": ""})["doc"]
        v = self.codificador.encode([prefijo + texto_indexado(f) for f in self.fragmentos],
                                    normalize_embeddings=True, batch_size=16, show_progress_bar=True)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        np.save(ruta, v.astype(np.float32))
        return v

    # ---------------------------------------------------------------- búsquedas
    def listas(self, pregunta, candidatos=CANDIDATOS):
        """Índices de los fragmentos en cada búsqueda por separado:
        (por significado, por palabras). Sin modelo vectorial, la primera va vacía."""
        consulta = expandir(pregunta) if self.sinonimos else pregunta
        por_palabras = list(np.argsort(-self.bm25.get_scores(palabras(consulta, self.raices)))[:candidatos])
        if self.codificador is None:
            return [], por_palabras
        opciones = FORMATO.get(self.modelo, {"pregunta": {}})["pregunta"]
        q = self.codificador.encode([pregunta], normalize_embeddings=True, **opciones)[0]
        por_significado = list(np.argsort(-(self.vectores @ q))[:candidatos])
        return por_significado, por_palabras

    def ordenar(self, pregunta, busqueda="combinada", candidatos=CANDIDATOS):
        """Lista ordenada de índices según el modo de búsqueda."""
        por_significado, por_palabras = self.listas(pregunta, candidatos)
        if busqueda == "vectorial":
            return por_significado
        if busqueda == "lexica" or not por_significado:
            return por_palabras
        puntos = {}
        for lista in (por_significado, por_palabras):
            for puesto, i in enumerate(lista):
                puntos[i] = puntos.get(i, 0) + 1 / (RRF + puesto)
        return sorted(puntos, key=puntos.get, reverse=True)

    def buscar(self, pregunta, busqueda="combinada", k=10):
        """Los k primeros. Con k > CANDIDATOS, cada lista aporta k candidatos (antes se
        cortaba en CANDIDATOS aunque se pidieran más)."""
        return [self.fragmentos[i] for i in self.ordenar(pregunta, busqueda, max(k, CANDIDATOS))[:k]]
