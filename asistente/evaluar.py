"""Evaluación sobre casos/casos_prueba.json.

Modo «solo recuperación» (no llama a ningún modelo de lenguaje, no cuesta nada):
para cada consulta con fuentes esperadas, en qué puesto aparece cada fuente en la
búsqueda por significado, por palabras y combinada, y el recall@5 y @10.

Una fuente se da por recuperada si un fragmento recuperado es del mismo documento,
su ruta contiene el apartado esperado y su rango de páginas incluye la página
esperada. Cada caso tiene grupos de fuentes: el caso se recupera si cada grupo tiene
al menos una de sus alternativas entre los k primeros (recall por apartado, no por
documento).

Uso:
    python -m asistente.evaluar --solo-recuperacion                 # combinada
    python -m asistente.evaluar --solo-recuperacion --sin-vectores  # solo BM25
    python -m asistente.evaluar --solo-recuperacion --modelo-emb BAAI/bge-m3
"""
import argparse
import json
import unicodedata
from datetime import datetime
from pathlib import Path

from asistente.corpus import RAIZ

CASOS = RAIZ / "casos" / "casos_prueba.json"
RESULTADOS = RAIZ / "resultados"
FUERA = 99               # puesto que se anota cuando la fuente no aparece


# ---------------------------------------------------------------- utilidades de puntuación

def normalizar(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def contiene(texto, grupos):
    """Cada grupo es una lista de alternativas: tiene que aparecer al menos una de cada grupo."""
    return all(any(normalizar(alt) in normalizar(texto) for alt in grupo) for grupo in grupos or [])


def coincide(fragmento, fuente):
    return (fragmento["documento"] == fuente["documento"]
            and fuente["apartado"].lower() in fragmento["ruta"].lower()
            and fragmento["pagina"] <= fuente["pagina"] <= fragmento["pagina_fin"])


def puesto(orden, fragmentos, grupo):
    """Primer puesto (1, 2, …) de la lista en que aparece alguna fuente del grupo."""
    for p, i in enumerate(orden, 1):
        if any(coincide(fragmentos[i], fuente) for fuente in grupo):
            return p
    return FUERA


def cargar_casos(ruta=CASOS):
    return json.load(open(ruta, encoding="utf-8"))


# ---------------------------------------------------------------- recuperación

def evaluar_recuperacion(buscador, casos, candidatos=50):
    filas = []
    for caso in casos:
        if caso.get("modo") != "consulta" or not caso.get("fuentes"):
            continue
        sig, pal = buscador.listas(caso["pregunta"], candidatos)
        comb = buscador.ordenar(caso["pregunta"], "combinada", candidatos) if sig else None
        fila = {"id": caso["id"], "tipo": caso["tipo"], "grupos": []}
        for grupo in caso["fuentes"]:
            fila["grupos"].append({
                "fuente": " | ".join(f"{f['apartado']} p. {f['pagina']}" for f in grupo),
                "vectorial": puesto(sig, buscador.fragmentos, grupo) if sig else None,
                "lexica": puesto(pal, buscador.fragmentos, grupo),
                "combinada": puesto(comb, buscador.fragmentos, grupo) if comb else None,
            })
        obsoletas = caso.get("fuentes_obsoletas", [])
        fila["obsoleta_en_10"] = bool(obsoletas) and puesto(comb or pal, buscador.fragmentos, obsoletas) <= 10
        filas.append(fila)
    return filas


def resumen(filas, modos=("vectorial", "lexica", "combinada")):
    out = {}
    for modo in modos:
        if any(g[modo] is None for f in filas for g in f["grupos"]):
            continue
        for k in (5, 10):
            ok = [f["id"] for f in filas if all(g[modo] <= k for g in f["grupos"])]
            out[f"{modo}@{k}"] = f"{len(ok)}/{len(filas)}"
    return out


def imprimir(filas, res):
    print(f"{'caso':5} {'fuente':58} {'vect':>5} {'léx':>5} {'comb':>5}")
    for f in filas:
        for g in f["grupos"]:
            fmt = lambda x: "-" if x is None else ("fuera" if x == FUERA else x)
            print(f"{f['id']:5} {g['fuente'][:58]:58} {fmt(g['vectorial']):>5} {fmt(g['lexica']):>5} {fmt(g['combinada']):>5}")
    print("\nRecall por caso (todas las fuentes del caso entre los k primeros):")
    for clave, valor in res.items():
        print(f"  {clave:14} {valor}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-recuperacion", action="store_true")
    ap.add_argument("--sin-vectores", action="store_true", help="solo BM25 (sin modelo de embeddings)")
    ap.add_argument("--modelo-emb", default=None)
    ap.add_argument("--casos", default=str(CASOS))
    args = ap.parse_args()

    from asistente.busqueda import MODELO_EMB, Buscador
    modelo = args.modelo_emb or MODELO_EMB
    buscador = Buscador(vectorial=not args.sin_vectores, modelo=modelo)
    casos = cargar_casos(args.casos)

    if not args.solo_recuperacion:
        raise SystemExit("La evaluación completa (con modelo de lenguaje) todavía no está implementada.")

    filas = evaluar_recuperacion(buscador, casos)
    res = resumen(filas)
    imprimir(filas, res)
    config = {"modo": "solo_recuperacion", "embeddings": None if args.sin_vectores else modelo,
              "candidatos_por_lista": 20, "rrf": 60, "fecha": datetime.now().isoformat(timespec="seconds"),
              "casos": Path(args.casos).name}
    RESULTADOS.mkdir(exist_ok=True)
    nombre = "recuperacion-bm25" if args.sin_vectores else f"recuperacion-{modelo.split('/')[-1]}"
    with open(RESULTADOS / f"{nombre}.json", "w", encoding="utf-8") as fh:
        json.dump({"config": config, "resumen": res, "casos": filas}, fh, ensure_ascii=False, indent=1)
    print(f"\nGuardado en resultados/{nombre}.json")


if __name__ == "__main__":
    main()
