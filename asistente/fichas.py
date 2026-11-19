"""Validador de fichas de personaje (niveles 1-5) con las tablas del SRD 5.2.1.

Es la herramienta externa: las cuentas (coste en puntos, PG, competencia) las hace el
código con datos/tablas_srd.json, no el modelo. Cada comprobación devuelve si se cumple,
el cálculo y la fuente (apartado y página).

Veredicto: «ilegal» si falla alguna comprobación; si no, «no_verificable» si algo queda
fuera del SRD o del alcance (nivel > 5, multiclase, puntuaciones tiradas…); si no, «legal».

Uso:  python -m asistente.fichas casos/casos_prueba.json      (valida las fichas del fichero)
"""
import copy
import hashlib
import json

from asistente.corpus import RAIZ

TABLAS = json.load(open(RAIZ / "datos" / "tablas_srd.json", encoding="utf-8"))
DOC = TABLAS["documento"]
CARS = TABLAS["caracteristicas"]


def _fuente(bloque):
    return {"documento": DOC, **bloque}


def modificador(puntuacion):
    return (puntuacion - 10) // 2


def _resultado(id_, ok, detalle, fuente, *otras):
    """«fuente» es la regla principal; «fuentes» incluye además las tablas o rasgos usados."""
    fuentes = [_fuente(f) for f in (fuente, *otras)]
    return {"id": id_, "ok": ok, "detalle": detalle, "fuente": fuentes[0], "fuentes": fuentes}


# ---------------------------------------------------------------- comprobaciones

def _base_y_finales(ficha):
    """Puntuaciones base (antes de aumentos) y finales. Si la ficha trae las finales,
    la base se obtiene restando los aumentos de trasfondo, especie y nivel."""
    aumentos = {c: 0 for c in CARS}
    for clave in ("aumentos_trasfondo", "aumentos_especie", "aumentos_nivel"):
        for c, v in (ficha.get(clave) or {}).items():
            aumentos[c] += v
    if "puntuaciones_base" in ficha:
        base = dict(ficha["puntuaciones_base"])
        finales = {c: base[c] + aumentos[c] for c in CARS}
    else:
        finales = dict(ficha["puntuaciones_finales"])
        base = {c: finales[c] - aumentos[c] for c in CARS}
    return base, finales


def comprobar_metodo(ficha, base):
    metodo = ficha.get("metodo")
    if metodo == "coste_en_puntos":
        t = TABLAS["coste_en_puntos"]
        fuera = [f"{c} {v}" for c, v in base.items() if str(v) not in t["costes"]]
        if fuera:
            return _resultado(metodo, False, f"Puntuación base fuera de la tabla de costes (8-15): {', '.join(fuera)}", t["fuente"])
        costes = [t["costes"][str(base[c])] for c in CARS]
        total = sum(costes)
        suma = " + ".join(map(str, costes)) + f" = {total}"
        ok = total <= t["presupuesto"]
        return _resultado(metodo, ok, f"{suma} puntos; el máximo es {t['presupuesto']}", t["fuente"])
    if metodo == "conjunto_estandar":
        t = TABLAS["conjunto_estandar"]
        valores = sorted(base.values(), reverse=True)
        ok = valores == t["valores"]
        return _resultado(metodo, ok, f"Base {valores}; el conjunto estándar es {t['valores']}", t["fuente"])
    return None   # tiradas u otro método: no se puede comprobar


def comprobar_bonificadores(ficha, finales):
    errores = []
    tras = TABLAS["trasfondos"]["valores"].get(ficha.get("trasfondo"), [])
    aum = {c: v for c, v in (ficha.get("aumentos_trasfondo") or {}).items() if v}
    if sorted(aum.values()) not in ([1, 2], [1, 1, 1]):
        errores.append(f"aumentos de trasfondo {aum}: deben ser +2/+1 o +1/+1/+1")
    fuera = [c for c in aum if c not in tras]
    if fuera:
        errores.append(f"{', '.join(fuera)} no es característica del trasfondo {ficha.get('trasfondo')} ({', '.join(tras)})")
    if ficha.get("aumentos_especie"):
        errores.append(f"la especie no aumenta características en 2024 (la ficha suma {ficha['aumentos_especie']}, regla de 2014)")
    mejora = TABLAS["mejora_caracteristica"]
    nivel_aum = {c: v for c, v in (ficha.get("aumentos_nivel") or {}).items() if v}
    if nivel_aum:
        if ficha["nivel"] < mejora["nivel_minimo"]:
            errores.append(f"Mejora de característica antes del nivel {mejora['nivel_minimo']}")
        elif sum(nivel_aum.values()) != mejora["total"]:
            errores.append(f"Mejora de característica suma {sum(nivel_aum.values())}, debe sumar {mejora['total']}")
    altas = [f"{c} {v}" for c, v in finales.items() if v > TABLAS["aumentos_trasfondo"]["maximo"]]
    if altas:
        errores.append(f"puntuación final por encima de 20: {', '.join(altas)}")
    detalle = "; ".join(errores) if errores else "Aumentos de trasfondo correctos y sin aumentos de especie"
    otras = [{"apartado": f"Descripciones de trasfondos › {ficha.get('trasfondo')}", "pagina": TABLAS["trasfondos"]["fuente"]["pagina"]}]
    if nivel_aum:
        otras.append(mejora["fuente"])
    return _resultado("bonificadores_caracteristica", not errores, detalle, TABLAS["aumentos_trasfondo"]["fuente"], *otras)


def rasgos_pg(nivel, especie=None, subclase=None):
    """Rasgos del SRD que suben los PG máximos y se aplican a esta ficha."""
    return {nombre: r for nombre, r in TABLAS["rasgos_pg"].items()
            if ((especie and r.get("especie") == especie) or (subclase and r.get("subclase") == subclase))
            and nivel >= r["desde_nivel"]}


def pg_esperados(clase, nivel, mod_con, especie=None, subclase=None):
    """PG máximos con el valor establecido por nivel (sin tirar dados)."""
    c = TABLAS["clases"]["valores"][clase]
    pg = c["pg_nivel_1"] + mod_con + (nivel - 1) * (c["pg_por_nivel"] + mod_con)
    partes = [f"{c['pg_nivel_1']} + {mod_con}"]
    if nivel > 1:
        partes.append(f"{nivel - 1} × ({c['pg_por_nivel']} + {mod_con})")
    for nombre, r in rasgos_pg(nivel, especie, subclase).items():
        pg += r["por_nivel"] * nivel
        partes.append(f"{r['por_nivel'] * nivel} ({nombre})")
    return pg, " + ".join(partes)


def comprobar_pg(ficha, finales):
    mod = modificador(finales["CON"])
    pg, cuenta = pg_esperados(ficha["clase"], ficha["nivel"], mod, ficha.get("especie"), ficha.get("subclase"))
    ok = ficha.get("pg_max") == pg
    t = TABLAS["clases"]
    fuentes = [t["fuente_pg_nivel_1"]] + ([t["fuente_pg_por_nivel"]] if ficha["nivel"] > 1 else [])
    fuentes += [r["fuente"] for r in rasgos_pg(ficha["nivel"], ficha.get("especie"), ficha.get("subclase")).values()]
    fuentes.append(TABLAS["modificador"]["fuente"])
    return _resultado("pg", ok, f"PG = {cuenta} = {pg} (Con {finales['CON']}, mod. {mod:+d}); la ficha dice {ficha.get('pg_max')}", *fuentes)


def comprobar_competencia(ficha):
    t = TABLAS["competencia"]
    esperado = t["por_nivel"][str(ficha["nivel"])]
    ok = ficha.get("bonificador_competencia") == esperado
    return _resultado("competencia", ok, f"Nivel {ficha['nivel']}: +{esperado}; la ficha dice +{ficha.get('bonificador_competencia')}", t["fuente"])


# ---------------------------------------------------------------- validación

def fuera_de_alcance(ficha):
    """Lo que impide comprobar la ficha entera."""
    motivos = []
    lo, hi = TABLAS["niveles"]
    if ficha.get("multiclase") or isinstance(ficha.get("clase"), list):
        motivos.append("multiclase: fuera del alcance")
    elif ficha.get("clase") not in TABLAS["clases"]["valores"]:
        motivos.append(f"clase «{ficha.get('clase')}» no está en el SRD 5.2.1")
    if not lo <= ficha.get("nivel", 0) <= hi:
        motivos.append(f"nivel {ficha.get('nivel')}: solo se comprueban los niveles {lo}-{hi}")
    if ficha.get("especie") not in TABLAS["especies"]["valores"]:
        motivos.append(f"especie «{ficha.get('especie')}» no está en el SRD 5.2.1")
    if ficha.get("trasfondo") not in TABLAS["trasfondos"]["valores"]:
        motivos.append(f"trasfondo «{ficha.get('trasfondo')}» no está en el SRD 5.2.1")
    sub = ficha.get("subclase")
    if sub and ficha.get("clase") in TABLAS["clases"]["valores"] and sub != TABLAS["clases"]["valores"][ficha["clase"]]["subclase"]:
        motivos.append(f"subclase «{sub}» no está en el SRD 5.2.1")
    if ficha.get("metodo") not in ("coste_en_puntos", "conjunto_estandar"):
        motivos.append(f"método «{ficha.get('metodo')}»: las puntuaciones tiradas no se pueden comprobar")
    return motivos


def validar(ficha):
    """Devuelve {veredicto, motivos, no_verificable, comprobaciones}. No lee la historia
    ni ningún texto libre de la ficha: solo los campos numéricos y los nombres."""
    no_verif = fuera_de_alcance(ficha)
    comprobaciones = []
    try:
        base, finales = _base_y_finales(ficha)
    except (KeyError, TypeError):
        no_verif.append("faltan las puntuaciones de característica")
        base = finales = None
    if base:
        m = comprobar_metodo(ficha, base)
        if m:
            comprobaciones.append(m)
        if ficha.get("trasfondo") in TABLAS["trasfondos"]["valores"]:
            comprobaciones.append(comprobar_bonificadores(ficha, finales))
        if ficha.get("clase") in TABLAS["clases"]["valores"] and TABLAS["niveles"][0] <= ficha.get("nivel", 0) <= TABLAS["niveles"][1]:
            comprobaciones.append(comprobar_pg(ficha, finales))
            comprobaciones.append(comprobar_competencia(ficha))
    motivos = [c["id"] for c in comprobaciones if not c["ok"]]
    veredicto = "ilegal" if motivos else ("no_verificable" if no_verif else "legal")
    return {"veredicto": veredicto, "motivos": motivos, "no_verificable": no_verif,
            "comprobaciones": comprobaciones}


# ---------------------------------------------------------------- datos personales

CAMPOS_PERSONALES = ("nombre", "correo", "id_jugador")


def seudonimo(jugador):
    clave = "|".join(str(jugador.get(c, "")) for c in CAMPOS_PERSONALES)
    return "jugador-" + hashlib.sha256(clave.encode("utf-8")).hexdigest()[:8]


def seudonimizar(ficha):
    """Copia de la ficha sin nombre, correo ni ID del jugador (no hacen falta para validar).
    Devuelve (ficha_sin_datos, seudónimo). La correspondencia no sale del equipo local."""
    f = copy.deepcopy(ficha)
    jugador = f.pop("jugador", None) or {}
    alias = seudonimo(jugador)
    f["jugador"] = alias
    return f, alias


if __name__ == "__main__":
    import sys
    casos = json.load(open(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "casos" / "casos_prueba.json", encoding="utf-8"))
    for caso in casos:
        if caso.get("modo") != "ficha":
            continue
        r = validar(caso["ficha"])
        ok = "✓" if r["veredicto"] == caso.get("veredicto") else "✗"
        print(f"{ok} {caso['id']}: {r['veredicto']} (esperado {caso.get('veredicto')}) {r['motivos']} {r['no_verificable']}")
        for c in r["comprobaciones"]:
            print(f"     {'ok ' if c['ok'] else 'MAL'} {c['id']}: {c['detalle']} [{c['fuente']['apartado']}, p. {c['fuente']['pagina']}]")
