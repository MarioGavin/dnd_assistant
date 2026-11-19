"""Evaluación sobre casos/casos_prueba.json.

Modo «solo recuperación» (sin modelo de lenguaje, sin coste): para cada consulta con
fuentes esperadas, en qué puesto aparece cada fuente (búsqueda por significado, por
palabras y combinada), el recall@5 y @10, y si todas las fuentes llegan al contexto que
recibiría el modelo (después de seleccionar() y emparejar()).

Modo completo (llama al modelo): cada consulta se puntúa con requiere, prohibidos (fuera
del párrafo «Cambio respecto a 2014:»), aviso de 2014, abstención (la respuesta empieza por
la frase), cita, recuperación, respuesta cortada, tokens, coste y segundos. Las fichas las
valida el código (veredicto y motivos) y el modelo explica el resultado.

Una fuente se da por recuperada si un fragmento es del mismo documento, su ruta contiene
el apartado esperado y su rango de páginas incluye la página. Para la cita no se exige la
página (es informativa en el plan). Cada caso tiene grupos de fuentes: hace falta al menos
una alternativa de cada grupo.

Uso:
    python -m asistente.evaluar --solo-recuperacion --sin-vectores
    python -m asistente.evaluar --solo-recuperacion --sin-vectores --sin-raices --sin-sinonimos   # BM25 sin más
    python -m asistente.evaluar --modelo claude-haiku-5-5 --repeticiones 3
    python -m asistente.evaluar --modelo claude-sonnet-5-5 --repeticiones 3
    python -m asistente.evaluar --modelo claude-haiku-5-5 --reformular --repeticiones 3
    python -m asistente.evaluar --modelo claude-haiku-5-5 --enrutar --repeticiones 3
    python -m asistente.evaluar --tabla                  # compara todo lo que hay en resultados/
"""
import argparse
import glob
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from asistente.corpus import RAIZ

CASOS = RAIZ / "casos" / "casos_prueba.json"
RESULTADOS = RAIZ / "resultados"
FUERA = 99               # puesto que se anota cuando la fuente no aparece
ETIQUETAS = {"claude-haiku-5-5": "haiku-5.5", "claude-sonnet-5-5": "sonnet-5.5"}


def etiqueta_modelo(modelo):
    """Nombre corto para los ficheros: «Qwen/Qwen3-4B» → «qwen3-4b» (sin «/»)."""
    return ETIQUETAS.get(modelo, modelo.split("/")[-1].lower())


# ---------------------------------------------------------------- utilidades de puntuación

def normalizar(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("−", "-")


def aparece(alt, texto):
    """Números y palabras cortas, como palabra entera: «6» no cuenta dentro de «16» ni de
    «1d6», ni «+2» dentro de «+20». El resto, como subcadena."""
    alt, texto = normalizar(alt), normalizar(texto)
    if re.fullmatch(r"[+-]?\d+|\w{1,3}", alt):
        return re.search(rf"(?<![\w]){re.escape(alt)}(?![\w])", texto) is not None
    return alt in texto


def contiene(texto, grupos):
    """Cada grupo es una lista de alternativas: tiene que aparecer al menos una de cada grupo."""
    return all(any(aparece(alt, texto) for alt in grupo) for grupo in grupos or [])


def coincide(fragmento, fuente, con_pagina=True):
    return (fragmento["documento"] == fuente["documento"]
            and fuente["apartado"].lower() in fragmento["ruta"].lower()
            and (not con_pagina or fragmento["pagina"] <= fuente["pagina"] <= fragmento["pagina_fin"]))


def puesto(orden, fragmentos, grupo):
    """Primer puesto (1, 2, …) de la lista en que aparece alguna fuente del grupo."""
    for p, i in enumerate(orden, 1):
        if any(coincide(fragmentos[i], fuente) for fuente in grupo):
            return p
    return FUERA


def cargar_casos(ruta=CASOS):
    return json.load(open(ruta, encoding="utf-8"))


def citas(texto):
    """Números citados entre corchetes: [3], [4][10], [1, 2]."""
    return {int(n) for grupo in re.findall(r"\[([\d,\s]+)\]", texto) for n in re.findall(r"\d+", grupo)}


# ---------------------------------------------------------------- recuperación

def evaluar_recuperacion(buscador, casos, candidatos=50, tablas_padre=False, amplio=False):
    from asistente.responder import AMPLIO, CANDIDATOS, K, MAX_OBSOLETOS, contexto as montar
    n, k, mo = (AMPLIO["candidatos"], AMPLIO["k"], AMPLIO["max_obsoletos"]) if amplio else (CANDIDATOS, K, MAX_OBSOLETOS)
    tablas_padre = tablas_padre or (amplio and AMPLIO["tablas_padre"])
    filas = []
    for caso in casos:
        if caso.get("modo") != "consulta" or not caso.get("fuentes"):
            continue
        sig, pal = buscador.listas(caso["pregunta"], candidatos)
        comb = buscador.ordenar(caso["pregunta"], "combinada", candidatos) if sig else None
        orden = comb or pal
        contexto = montar(buscador.buscar(caso["pregunta"], k=n), buscador.fragmentos, k, mo,
                          tablas_padre=tablas_padre)
        fila = {"id": caso["id"], "tipo": caso["tipo"], "grupos": []}
        for grupo in caso["fuentes"]:
            fila["grupos"].append({
                "fuente": " | ".join(f"{f['apartado']} p. {f['pagina']}" for f in grupo),
                "vectorial": puesto(sig, buscador.fragmentos, grupo) if sig else None,
                "lexica": puesto(pal, buscador.fragmentos, grupo),
                "combinada": puesto(comb, buscador.fragmentos, grupo) if comb else None,
                "contexto": any(coincide(f, fu) for f in contexto for fu in grupo),
            })
        obsoletas = caso.get("fuentes_obsoletas", [])
        fila["obsoleta_en_10"] = bool(obsoletas) and puesto(orden, buscador.fragmentos, obsoletas) <= 10
        fila["obsoleta_en_contexto"] = bool(obsoletas) and any(coincide(f, fu) for f in contexto for fu in obsoletas)
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
    out["contexto"] = f"{sum(all(g['contexto'] for g in f['grupos']) for f in filas)}/{len(filas)}"
    return out


def imprimir(filas, res):
    print(f"{'caso':5} {'fuente':58} {'vect':>5} {'léx':>5} {'comb':>5} {'ctx':>4}")
    for f in filas:
        for g in f["grupos"]:
            fmt = lambda x: "-" if x is None else ("fuera" if x == FUERA else x)
            print(f"{f['id']:5} {g['fuente'][:58]:58} {fmt(g['vectorial']):>5} {fmt(g['lexica']):>5} "
                  f"{fmt(g['combinada']):>5} {'sí' if g['contexto'] else 'no':>4}")
    print("\nRecall por caso (todas las fuentes del caso entre los k primeros; «contexto»: lo que recibe el modelo):")
    for clave, valor in res.items():
        print(f"  {clave:14} {valor}")


# ---------------------------------------------------------------- evaluación completa

def puntuar_consulta(caso, r, por_id):
    from asistente.responder import AVISO_2014
    texto = r.get("respuesta", "")
    principal = re.split(re.escape(AVISO_2014), texto, flags=re.I)[0]   # sin el párrafo de 2014
    recibidos = [por_id[f["id"]] for f in r.get("fragmentos", [])]
    citados = [recibidos[n - 1] for n in citas(texto) if 0 < n <= len(recibidos)]
    grupos = caso.get("fuentes") or []

    prohibido = [p for p in caso.get("prohibidos", []) if aparece(p, principal)]
    prohibido += [p for p in caso.get("prohibidos_regex", []) if re.search(p, principal)]
    p = {
        "abstiene": r.get("abstiene", False),
        "cortada": r.get("cortada", False),
        "error": r.get("error"),
        "requiere": contiene(principal, caso.get("requiere")),
        "prohibidos": prohibido,
        "aviso": (normalizar(AVISO_2014) in normalizar(texto)) if caso.get("aviso") else None,
        "recuperacion": all(any(coincide(f, fu) for f in recibidos for fu in g) for g in grupos) if grupos else None,
        "cita": all(any(coincide(f, fu, con_pagina=False) for f in citados for fu in g) for g in grupos) if grupos else None,
        "cita_obsoleta_sola": bool(citados) and all(not f["vigente"] for f in citados),
    }
    return veredicto(p, caso["tipo"])


def veredicto(p, tipo):
    """correcto y correcto_con_cita a partir de las comprobaciones de puntuar_consulta()."""
    if tipo == "debe_fallar":
        p["correcto"] = bool(p["abstiene"] and not p["prohibidos"] and not p["cortada"] and not p["error"])
    else:
        p["correcto"] = bool(not p["abstiene"] and not p["cortada"] and not p["error"] and p["requiere"]
                             and not p["prohibidos"] and p["aviso"] is not False)
    p["correcto_con_cita"] = p["correcto"] and p["cita"] is not False
    return p


def repuntuar(motivo="abstención con punto o dos puntos (fallo 31)"):
    """Vuelve a calcular la abstención y el veredicto de las consultas ya guardadas en
    resultados/ con el detector actual, sin llamar al modelo. Las demás comprobaciones
    (requiere, prohibidos, aviso, cita) se conservan tal como se guardaron."""
    from asistente.responder import abstiene
    for ruta in sorted(glob.glob(str(RESULTADOS / "*-r[0-9]*.json"))):
        datos = json.load(open(ruta, encoding="utf-8"))
        if "repeticion" not in datos.get("resumen", {}):
            continue
        cambios = []
        for f in datos["casos"]:
            if f["modo"] != "consulta":
                continue
            antes = (f["abstiene"], f["correcto"])
            f["abstiene"] = abstiene(f.get("respuesta", ""))
            veredicto(f, f["tipo"])
            if (f["abstiene"], f["correcto"]) != antes:
                cambios.append(f["id"])
        if cambios:
            datos["resumen"].update(resumir(datos["casos"]))
            datos["resumen"]["repuntuado"] = f"{datetime.now().isoformat(timespec='seconds')}: {motivo}; cambian {cambios}"
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump(datos, fh, ensure_ascii=False, indent=1)
            print(f"{Path(ruta).name}: {cambios}")


def puntuar_ficha(caso, r):
    texto = r.get("respuesta", "").split("\n\n", 1)[-1]          # sin la línea del veredicto que pone el código
    p = {
        "veredicto": r.get("veredicto"),
        "veredicto_ok": r.get("veredicto") == caso["veredicto"],
        "motivos_ok": sorted(r.get("motivos", [])) == sorted(caso.get("motivos", [])),
        "falso_legal": r.get("veredicto") == "legal" and caso["veredicto"] != "legal",
        "explicacion_ok": contiene(texto, caso.get("requiere")) and not r.get("cortada") and not r.get("error"),
        "cortada": r.get("cortada", False),
        "error": r.get("error"),
        # «legal» suelto en la explicación: puede ser obediencia o una cita de la orden para negarse.
        "revisar_a_mano": bool(re.search(r"(?<![a-z])legal", normalizar(texto))) and caso["veredicto"] != "legal",
    }
    p["correcto"] = p["veredicto_ok"] and p["motivos_ok"] and p["explicacion_ok"]
    return p


def una_ejecucion(casos, modelo, max_obsoletos, por_id, fichas_con_modelo=True, reformular=False, enrutar=False,
                  tablas=True, tablas_padre=False, contexto_amplio=False):
    from asistente import responder as R
    from asistente.fichas import validar
    filas = []
    for caso in casos:
        try:
            if caso["modo"] == "consulta":
                r = R.responder(caso["pregunta"], modelo=modelo, max_obsoletos=max_obsoletos,
                                reformular_pregunta=reformular, enrutar=enrutar, tablas=tablas,
                                tablas_padre=tablas_padre, contexto_amplio=contexto_amplio)
            elif fichas_con_modelo:
                r = R.responder_ficha(caso["ficha"], modelo=modelo)
            else:
                inf = validar(caso["ficha"])
                r = {"respuesta": f"Veredicto: {inf['veredicto']}.", "veredicto": inf["veredicto"],
                     "motivos": inf["motivos"], "tokens_entrada": 0, "tokens_salida": 0, "coste_usd": 0, "segundos": 0}
        except Exception as e:                                  # un error no para la evaluación
            r = {"respuesta": "", "error": f"{type(e).__name__}: {e}"[:300], "fragmentos": []}
            if caso["modo"] == "ficha":
                inf = validar(caso["ficha"])
                r.update(veredicto=inf["veredicto"], motivos=inf["motivos"])
        p = puntuar_consulta(caso, r, por_id) if caso["modo"] == "consulta" else puntuar_ficha(caso, r)
        fila = {"id": caso["id"], "tipo": caso["tipo"], "modo": caso["modo"], "subtipo": caso.get("subtipo"),
                **p, "respuesta": r.get("respuesta", ""), "fragmentos": [f["cita"] for f in r.get("fragmentos", [])],
                "stop_reason": r.get("stop_reason"), "bloques": r.get("bloques"),
                "modelo_usado": r.get("modelo"), "enrutada": r.get("enrutada", False), "consulta": r.get("consulta"),
                "tokens_entrada": r.get("tokens_entrada", 0), "tokens_salida": r.get("tokens_salida", 0),
                "coste_usd": r.get("coste_usd", 0), "segundos": r.get("segundos", 0)}
        filas.append(fila)
        marca = "ok " if fila["correcto"] else "MAL"
        print(f"  {marca} {caso['id']:4} {fila['segundos']:>5} s  {fila['respuesta'][:90]!r}")
    return filas


def _frac(filas, clave="correcto"):
    return f"{sum(bool(f[clave]) for f in filas)}/{len(filas)}"


def resumir(filas):
    cons = [f for f in filas if f["modo"] == "consulta"]
    fichas = [f for f in filas if f["modo"] == "ficha"]
    con_resp = [f for f in cons if f["tipo"] != "debe_fallar"]
    llamadas = [f for f in filas if f["tokens_entrada"]]
    res = {}
    for tipo in ("normal", "limite", "debe_fallar"):
        grupo = [f for f in cons if f["tipo"] == tipo]
        if grupo:
            res[f"consultas_{tipo}"] = _frac(grupo)
    for tipo in ("normal", "limite"):
        grupo = [f for f in cons if f["tipo"] == tipo]
        if grupo:
            res[f"consultas_{tipo}_con_cita"] = _frac(grupo, "correcto_con_cita")
    res.update({
        "abstenciones_indebidas": f"{sum(f['abstiene'] for f in con_resp)}/{len(con_resp)}",
        "recuperacion": f"{sum(bool(f['recuperacion']) for f in con_resp)}/{len(con_resp)}",
        "fichas_veredicto": _frac(fichas, "veredicto_ok"),
        "fichas_motivos": _frac(fichas, "motivos_ok"),
        "fichas_explicacion": _frac(fichas, "explicacion_ok"),
        "falsos_legal": sum(f["falso_legal"] for f in fichas),
        "revisar_a_mano": [f["id"] for f in fichas if f["revisar_a_mano"]],
        "cortadas": [f["id"] for f in filas if f["cortada"]],
        "enrutadas": [f["id"] for f in filas if f.get("enrutada")],
        "errores": [f["id"] for f in filas if f.get("error")],
        "tokens_entrada": sum(f["tokens_entrada"] for f in filas),
        "tokens_salida": sum(f["tokens_salida"] for f in filas),
        "coste_usd": round(sum(f["coste_usd"] for f in filas), 4),
        "coste_medio_consulta_usd": round(sum(f["coste_usd"] for f in cons) / max(len(cons), 1), 5),
        "segundos_medios": round(sum(f["segundos"] for f in llamadas) / max(len(llamadas), 1), 2),
        "segundos_max": max((f["segundos"] for f in llamadas), default=0),
    })
    return res


def evaluar_completo(args, casos):
    from asistente import responder as R
    from asistente.corpus import cargar
    from asistente.fichas import TABLAS

    import anthropic
    por_id = {f["id"]: f for f in cargar()}
    etiqueta = args.etiqueta or (etiqueta_modelo(args.modelo)
                                 + "-reformular" * args.reformular + "-enrutar" * args.enrutar
                                 + "-sin-tablas" * args.sin_tablas + "-tablas-padre" * args.tablas_padre
                                 + "-contexto-amplio" * args.contexto_amplio)
    config = {
        "etiqueta": etiqueta, "modelo": args.modelo, "k": R.K, "candidatos": R.CANDIDATOS,
        "max_obsoletos": args.max_obsoletos, "busqueda": "BM25 + raíces + sinónimos" if (R.buscador().raices and R.buscador().sinonimos) else "BM25", "max_tokens": R.MAX_TOKENS,
        "temperature": "no se envía", "version_prompt": R.VERSION_PROMPT,
        "huella_prompt": hashlib.sha1((R.SISTEMA + R.SISTEMA_FICHA).encode("utf-8")).hexdigest()[:10],
        "tablas_srd": hashlib.sha1(json.dumps(TABLAS, sort_keys=True).encode("utf-8")).hexdigest()[:10],
        "fichas_con_modelo": not args.fichas_sin_modelo, "sdk_anthropic": anthropic.__version__,
        "reformular": args.reformular, "enrutar": R.MODELO_ENRUTADO if args.enrutar else None,
        "tablas": not args.sin_tablas, "tablas_padre": args.tablas_padre,
        "contexto_amplio": R.AMPLIO if args.contexto_amplio else None,
        "casos": Path(args.casos).name,
        "generacion_local": {**R.GENERACION_LOCAL, "max_new_tokens": R.MAX_TOKENS_LOCAL, "dtype": "float16",
                             "razonamiento": False} if args.modelo.startswith("Qwen/") else None,
    }
    RESULTADOS.mkdir(exist_ok=True)
    resumenes = []
    for rep in range(1, args.repeticiones + 1):
        print(f"\n=== {etiqueta} · ejecución {rep} de {args.repeticiones}")
        filas = una_ejecucion(casos, args.modelo, args.max_obsoletos, por_id, not args.fichas_sin_modelo,
                              args.reformular, args.enrutar, not args.sin_tablas, args.tablas_padre,
                              args.contexto_amplio)
        res = {**config, "repeticion": rep, "fecha": datetime.now().isoformat(timespec="seconds"), **resumir(filas)}
        resumenes.append(res)
        nombre = RESULTADOS / f"{etiqueta}-r{rep}.json"
        with open(nombre, "w", encoding="utf-8") as fh:
            json.dump({"resumen": res, "casos": filas}, fh, ensure_ascii=False, indent=1)
        print(f"Guardado en resultados/{nombre.name}")
    imprimir_tabla(resumenes)


# ---------------------------------------------------------------- tabla comparativa

COLUMNAS = [("normal", "consultas_normal"), ("límite", "consultas_limite"), ("deben fallar", "consultas_debe_fallar"),
            ("normal+cita", "consultas_normal_con_cita"), ("límite+cita", "consultas_limite_con_cita"),
            ("abst. indebidas", "abstenciones_indebidas"), ("recup.", "recuperacion"),
            ("fichas", "fichas_veredicto"), ("explic.", "fichas_explicacion"), ("falsos legal", "falsos_legal"),
            ("cortadas", "cortadas"), ("enrutadas", "enrutadas"), ("tokens ent./sal.", None), ("coste $", "coste_usd"), ("s medios", "segundos_medios")]


def imprimir_tabla(resumenes, salida=None):
    cab = ["config", "rep"] + [c for c, _ in COLUMNAS]
    lineas = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for r in resumenes:
        celdas = [r.get("etiqueta", "?"), str(r.get("repeticion", ""))]
        for _, clave in COLUMNAS:
            if clave is None:
                celdas.append(f"{r.get('tokens_entrada', 0)} / {r.get('tokens_salida', 0)}")
            else:
                v = r.get(clave, "")
                celdas.append(str(len(v)) if isinstance(v, list) else str(v))
        lineas.append("| " + " | ".join(celdas) + " |")
    texto = "\n".join(lineas)
    print("\n" + texto)
    if salida:
        Path(salida).write_text(texto + "\n", encoding="utf-8")
        print(f"\nGuardado en resultados/{Path(salida).name}")


def tabla():
    resumenes = []
    for ruta in sorted(glob.glob(str(RESULTADOS / "*-r[0-9]*.json"))):
        r = json.load(open(ruta, encoding="utf-8")).get("resumen", {})
        if "modelo" in r and "repeticion" in r:
            resumenes.append(r)
    if not resumenes:
        raise SystemExit("No hay ejecuciones completas en resultados/.")
    imprimir_tabla(resumenes, RESULTADOS / "comparacion.md")


# ---------------------------------------------------------------- main

def main():
    from asistente.responder import MAX_OBSOLETOS, MODELO
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-recuperacion", action="store_true")
    ap.add_argument("--sin-vectores", action="store_true", help="solo BM25 (sin modelo de embeddings)")
    ap.add_argument("--modelo-emb", default=None)
    ap.add_argument("--sin-raices", action="store_true", help="BM25 sin raíces (alternativa medida)")
    ap.add_argument("--sin-sinonimos", action="store_true", help="BM25 sin sinónimos (alternativa medida)")
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--modelo", default=MODELO, help="modelo de lenguaje para la evaluación completa")
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--max-obsoletos", type=int, default=MAX_OBSOLETOS)
    ap.add_argument("--etiqueta", default=None, help="nombre de los ficheros de resultados")
    ap.add_argument("--fichas-sin-modelo", action="store_true", help="solo el validador, sin explicación del modelo")
    ap.add_argument("--tabla", action="store_true", help="tabla comparativa de resultados/ (sin llamadas)")
    ap.add_argument("--repuntuar", action="store_true",
                    help="volver a puntuar las consultas guardadas con el detector actual (sin llamadas)")
    ap.add_argument("--reformular", action="store_true", help="añadir términos del SRD a la pregunta antes de buscar")
    ap.add_argument("--enrutar", action="store_true", help="Sonnet solo para las consultas con un fragmento de 2014")
    ap.add_argument("--sin-tablas", action="store_true", help="sin añadir tablas al contexto (alternativa medida)")
    ap.add_argument("--tablas-padre", action="store_true", help="añadir también las tablas del apartado padre")
    ap.add_argument("--contexto-amplio", action="store_true", help="60 candidatos, 20 fragmentos, 2 de 2014 y tablas del padre")
    args = ap.parse_args()

    if args.repuntuar:
        repuntuar()
        return tabla()
    if args.tabla:
        return tabla()
    casos = cargar_casos(args.casos)
    if not args.solo_recuperacion:
        return evaluar_completo(args, casos)

    from asistente.busqueda import MODELO_EMB, Buscador
    modelo = args.modelo_emb or MODELO_EMB
    buscador = Buscador(vectorial=not args.sin_vectores, modelo=modelo, raices=not args.sin_raices, sinonimos=not args.sin_sinonimos)
    filas = evaluar_recuperacion(buscador, casos, tablas_padre=args.tablas_padre, amplio=args.contexto_amplio)
    res = resumen(filas)
    imprimir(filas, res)
    config = {"modo": "solo_recuperacion", "embeddings": None if args.sin_vectores else modelo,
              "candidatos_por_lista": 20, "rrf": 60, "fecha": datetime.now().isoformat(timespec="seconds"),
              "raices": not args.sin_raices, "sinonimos": not args.sin_sinonimos, "tablas_padre": args.tablas_padre,
              "contexto_amplio": args.contexto_amplio, "casos": Path(args.casos).name}
    RESULTADOS.mkdir(exist_ok=True)
    nombre = "recuperacion-bm25" if args.sin_vectores else f"recuperacion-{modelo.split('/')[-1]}"
    nombre += "-sin-raices" * args.sin_raices + "-sin-sinonimos" * args.sin_sinonimos + "-tablas-padre" * args.tablas_padre + "-contexto-amplio" * args.contexto_amplio
    if Path(args.casos).name != CASOS.name:
        nombre += f"-{Path(args.casos).stem}"
    with open(RESULTADOS / f"{nombre}.json", "w", encoding="utf-8") as fh:
        json.dump({"config": config, "resumen": res, "casos": filas}, fh, ensure_ascii=False, indent=1)
    print(f"\nGuardado en resultados/{nombre}.json")


if __name__ == "__main__":
    main()
