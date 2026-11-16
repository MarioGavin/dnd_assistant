r"""Corpus: del PDF del SRD a fragmentos citables.

Dos pasos:
  1. pdf_a_markdown(): lee el PDF con PyMuPDF y reconoce los títulos por su letra
     (fuente y tamaño), las dos columnas y las tablas. Cada página deja una marca
     <!-- p. N --> para poder citar la página.
  2. trocear(): corta el markdown por apartados (títulos r"^#{1,4}\s"). Los apartados
     largos se parten por párrafos repitiendo el título, y una tabla nunca se parte.

trocear() adapta trocear_apartados() del ejemplo de la asignatura Herramientas de
IA Generativa (USJ, curso 2026-27).

Uso:  python -m asistente.corpus [--srd carpeta_con_los_pdf]
"""
import argparse
import json
import re
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parents[1]
MAXIMO = 2500          # caracteres por fragmento

# Fuente y tamaño de letra de cada nivel de título, medidos en los propios PDF.
FUENTES = {
    "srd521": {
        "pdf": "SP_SRD_CC_v5.2.1.pdf", "documento": "SRD 5.2.1 ES", "edicion": "2024",
        "vigente": True,
        # Cómo jugar (p. 5) … Herramientas del juego (hasta p. 222). Sin objetos mágicos
        # ni monstruos: los monstruos se consultan con la herramienta (dnd5eapi).
        "paginas": [(5, 222)],
        "titulos": {("GillSans-SemiBold", 26.0): 1, ("GillSans-SemiBold", 18.0): 2,
                    ("GillSans-SemiBold", 14.0): 3,
                    ("GillSans-SemiBold", 12.0): 4},
        # 14,8 pt es el título de un perfil dentro de un conjuro («Objeto animado»): no abre apartado.
        "titulo_tabla": {("GillSans-SemiBold", 10.5), ("GillSans-SemiBold", 14.8)},
        "es_tabla": lambda f, s: f.startswith("GillSans") and 9.1 < s <= 10.0,
    },
    "srd51": {
        "pdf": "SRD_CC_v5.1_ES.pdf", "documento": "SRD 5.1 ES", "edicion": "2014",
        "vigente": False,
        # Razas … conjuros (pp. 2-220), la introducción de «Monstruos» (pp. 274-281),
        # que nombra criaturas sin dar su perfil, y los estados (pp. 389-390).
        "paginas": [(2, 220), (274, 281), (389, 390)],
        "titulos": {("Calibri", 26.0): 1, ("Calibri", 18.0): 2, ("Calibri", 14.0): 3,
                    ("Calibri", 12.0): 4, ("Calibri-Bold", 12.0): 4, ("Calibri", 11.0): 4},
        "titulo_tabla": set(),
        "es_tabla": lambda f, s: f.startswith("Calibri") and s <= 10.0,
    },
}


# ---------------------------------------------------------------- 1. PDF → markdown

def _lineas(pagina, cfg):
    """Las líneas de una página, con su clase: titulo, tabla, titulo_tabla o texto."""
    salida = []
    for bloque in pagina.get_text("dict")["blocks"]:
        for linea in bloque.get("lines", []):
            spans = [s for s in linea["spans"] if s["text"].strip()]
            if not spans:
                continue
            y = spans[0]["origin"][1]            # línea base: la caja de algunas fuentes viene desplazada
            if y > 738:                          # cabecera de página y aviso de reventa
                continue
            fuente, tam = spans[0]["font"], round(spans[0]["size"], 1)
            partes = []
            for s in linea["spans"]:
                t = s["text"].replace("\xa0", " ")
                if "BoldItalic" in s["font"] and t.strip():
                    t = f"**{t.strip()}** "
                partes.append(t)
            texto = re.sub(r"[ \t]+", " ", "".join(partes)).strip()
            if (fuente, tam) in cfg["titulos"]:
                clase = "titulo"
            elif (fuente, tam) in cfg["titulo_tabla"]:
                clase = "titulo_tabla"
            elif cfg["es_tabla"](fuente, tam):
                clase = "tabla"
            else:
                clase = "texto"
            salida.append({"x0": linea["bbox"][0], "x1": linea["bbox"][2], "y": y,
                           "texto": texto, "clase": clase, "fuente": fuente, "tam": tam,
                           "nivel": cfg["titulos"].get((fuente, tam))})
    return salida


def _filas(lineas, tolerancia=2.5):
    """Agrupa líneas en filas por su línea base."""
    filas = []
    for ln in sorted(lineas, key=lambda l: (l["y"], l["x0"])):
        if filas and abs(filas[-1][0]["y"] - ln["y"]) <= tolerancia:
            filas[-1].append(ln)
        else:
            filas.append([ln])
    return [sorted(f, key=lambda l: l["x0"]) for f in filas]


def _ordenar(lineas, ancho):
    """Orden de lectura: columna izquierda y luego derecha, salvo las tablas que
    ocupan las dos columnas, que se leen como una franja entera."""
    medio = ancho / 2
    col = lambda l: 0 if l["x0"] < medio - 5 else 1
    otras = [l for l in lineas if l["clase"] != "tabla"]
    margen_dcha = min((l["x0"] for l in otras if col(l) == 1), default=medio + 16)
    # Una fila de tabla es «de página entera» si tiene celdas a los dos lados y no hay
    # texto a su altura en ninguna columna.
    candidatas = []
    for fila in _filas([l for l in lineas if l["clase"] == "tabla"]):
        y = fila[0]["y"]
        if {col(l) for l in fila} == {0, 1} and not any(abs(o["y"] - y) < 7 for o in otras):
            hueco = any(medio - 12 <= l["x0"] < margen_dcha - 2 for l in fila)   # celda en el canal central
            candidatas.append((y, hueco))
    franjas = []
    for y, hueco in candidatas:
        if franjas and y - franjas[-1][1] < 25:
            franjas[-1][1] = y
            franjas[-1][2] += 1
            franjas[-1][3] |= hueco
        else:
            franjas.append([y, y, 1, hueco])
    # Dos tablas de columna a la misma altura no son una tabla ancha: se exige una celda
    # en el canal central o al menos tres filas seguidas.
    franjas = [[a, b] for a, b, n, hueco in franjas if hueco or n >= 3]
    franjas = [(a - 32, b + 2) for a, b in franjas]     # sube hasta el título de la tabla

    def en_franja(l):
        return l["clase"] in ("tabla", "titulo_tabla") and any(a <= l["y"] <= b for a, b in franjas)

    cortes = [-1.0] + [a for a, _ in franjas] + [1e9]
    orden = []
    for i in range(len(cortes) - 1):
        tramo = [l for l in lineas if cortes[i] <= l["y"] < cortes[i + 1] and not en_franja(l)]
        for c in (0, 1):
            orden += sorted((l for l in tramo if col(l) == c), key=lambda l: (l["y"], l["x0"]))
        if i < len(franjas):
            a, b = franjas[i]
            orden += [dict(l, ancha=True) for l in lineas if en_franja(l) and a <= l["y"] <= b]
    return orden


def _unir(previo, siguiente):
    """Une dos líneas de un párrafo quitando el guion de partición."""
    if previo.endswith("\xad"):
        return previo[:-1] + siguiente
    if re.search(r"[a-záéíóúñ]-$", previo) and siguiente[:1].islower():
        return previo[:-1] + siguiente
    return previo + " " + siguiente


def _pagina_a_markdown(lineas):
    md, parrafo, tabla = [], "", []
    ultimo_titulo = None

    def cerrar():
        nonlocal parrafo, tabla
        if parrafo:
            md.append(parrafo.replace("\xad", "").strip())
            parrafo = ""
        if tabla:
            suelto, previa = "", None
            for fila in _filas(tabla):
                celdas = [l["texto"].replace("\xad", "") for l in fila]
                if len(celdas) == 1 and len(celdas[0]) > 40:     # recuadro de texto, no tabla
                    suelto = _unir(suelto, celdas[0]) if suelto else celdas[0]
                    continue
                if suelto:
                    md.append(suelto.replace("\xad", ""))
                    suelto = ""
                # Celda partida en dos líneas: la segunda línea queda debajo de una celda
                # de la fila anterior, a menos distancia que entre filas.
                if previa and len(fila) <= len(previa[1]) and fila[0]["y"] - previa[0] < 13.5 and all(
                        any(abs(l["x0"] - p["x0"]) <= 5 for p in previa[1]) for l in fila):
                    for l in fila:
                        j = next(i for i, p in enumerate(previa[1]) if abs(l["x0"] - p["x0"]) <= 5)
                        previa[2][j] = _unir(previa[2][j], l["texto"])
                    md[-1] = "| " + " | ".join(c.replace("\xad", "") for c in previa[2]) + " |"
                    previa[0] = fila[0]["y"]
                    continue
                md.append("| " + " | ".join(celdas) + " |")
                previa = [fila[0]["y"], fila, [l["texto"] for l in fila]]
            if suelto:
                md.append(suelto.replace("\xad", ""))
            md.append("")
            tabla = []

    for ln in lineas:
        t = ln["texto"]
        if ln["clase"] == "titulo":
            # Un título partido en dos líneas («Paso 3: puntuaciones» / «de característica»).
            if ultimo_titulo is not None and md and md[-1].startswith("#") and ultimo_titulo["tam"] == ln["tam"] \
                    and 0 < ln["y"] - ultimo_titulo["y"] < ln["tam"] * 1.6 and not parrafo and not tabla:
                md[-1] += " " + t
            else:
                cerrar()
                md.append("#" * ln["nivel"] + " " + t)
            ultimo_titulo = ln
            continue
        ultimo_titulo = None
        if ln["clase"] == "titulo_tabla":
            if md and md[-1].startswith("**Tabla: ") and not parrafo and not tabla:
                md[-1] = md[-1][:-2] + " " + t + "**"
            else:
                cerrar()
                md.append(f"**Tabla: {t}**")
        elif ln["clase"] == "tabla":
            if parrafo:
                cerrar()
            tabla.append(ln)
        else:
            if tabla:
                cerrar()
            nuevo = (not parrafo or t.startswith(("•", "**")) or re.match(r"^\d+:\s", t))
            if nuevo:
                cerrar()
                parrafo = re.sub(r"^•\s*", "- ", t)
            else:
                parrafo = _unir(parrafo, t)
    cerrar()
    return "\n".join(md)


def pdf_a_markdown(nombre, carpeta_srd):
    cfg = FUENTES[nombre]
    doc = pymupdf.open(Path(carpeta_srd) / cfg["pdf"])
    trozos = []
    for ini, fin in cfg["paginas"]:
        for n in range(ini, fin + 1):
            pagina = doc[n - 1]
            lineas = _ordenar(_lineas(pagina, cfg), pagina.rect.width)
            trozos.append(f"<!-- p. {n} -->\n" + _pagina_a_markdown(lineas))
    return "\n\n".join(trozos)


# ---------------------------------------------------------------- 2. Trocear

TITULO = re.compile(r"^(#{1,4})\s+(.*)$")
PAGINA = re.compile(r"^<!-- p\. (\d+) -->$")


def _partir(titulo, cuerpo, maximo=MAXIMO):
    """Parte un apartado largo por párrafos, repitiendo el título. Una tabla va entera."""
    bloques, actual = [], ""
    for parrafo in re.split(r"\n(?=\S)(?!\|)", cuerpo):      # no corta entre filas de tabla
        if actual and len(actual) + len(parrafo) > maximo:
            bloques.append(actual)
            actual = ""
        actual += ("\n" if actual else "") + parrafo
    if actual:
        bloques.append(actual)
    return [(titulo if i == 0 else f"{titulo} (cont.)", b) for i, b in enumerate(bloques)]


TABLA = re.compile(r"^\*\*Tabla: (.*)\*\*$")


def trocear(markdown, nombre):
    """Un fragmento por apartado. Una tabla con título es un fragmento propio, con el
    título de la tabla como apartado: así se cita bien aunque en el PDF quede lejos
    del título de su sección (las tablas de clase ocupan la página entera)."""
    cfg = FUENTES[nombre]
    ruta = [None] * 5                     # 4 niveles de título + la tabla
    fragmentos, cuerpo, pagina, pag_ini = [], [], None, None
    en_tabla = False

    def guardar():
        texto = "\n".join(l for l in cuerpo if not PAGINA.match(l)).strip()
        if not texto or not any(ruta):
            return
        titulo = next(t for t in reversed(ruta) if t)
        for apartado, bloque in _partir(titulo, texto):
            fragmentos.append({
                "id": f"{nombre}-{len(fragmentos):04d}",
                "documento": cfg["documento"], "edicion": cfg["edicion"],
                "vigente": cfg["vigente"],
                "ruta": " › ".join(t for t in ruta if t),
                "apartado": apartado,
                "pagina": pag_ini, "pagina_fin": pagina,
                "texto": bloque,
            })

    for linea in markdown.split("\n"):
        m = PAGINA.match(linea)
        if m:
            pagina = int(m.group(1))
            if not "".join(l for l in cuerpo if not PAGINA.match(l)).strip():
                pag_ini = pagina
            cuerpo.append(linea)
            continue
        m = TITULO.match(linea)
        t = TABLA.match(linea)
        if m:
            guardar()
            nivel = len(m.group(1))
            ruta[nivel - 1] = m.group(2).strip()
            for i in range(nivel, 5):
                ruta[i] = None
            cuerpo, pag_ini, en_tabla = [], pagina, False
        elif t:
            guardar()
            ruta[4] = "Tabla: " + t.group(1).strip()
            cuerpo, pag_ini, en_tabla = [linea], pagina, True
        elif en_tabla and linea.strip() and not linea.startswith("|"):
            # Fin de la tabla: el texto que sigue vuelve a su apartado.
            guardar()
            ruta[4] = None
            cuerpo, pag_ini, en_tabla = [linea], pagina, False
        else:
            cuerpo.append(linea)
    guardar()
    return fragmentos


def cabecera(f):
    """Cómo se cita un fragmento (y lo que se indexa con su texto)."""
    obsoleto = "" if f["vigente"] else " · OBSOLETO (reglas de 2014)"
    return f"{f['documento']} · {f['ruta']} · p. {f['pagina']}{obsoleto}"


def cargar(ruta=RAIZ / "corpus" / "fragmentos.jsonl"):
    with open(ruta, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh]


def construir(carpeta_srd):
    todos = []
    for nombre in FUENTES:
        md = pdf_a_markdown(nombre, carpeta_srd)
        (RAIZ / "corpus" / f"{nombre}.md").write_text(md, encoding="utf-8")
        fr = trocear(md, nombre)
        largos = max(len(f["texto"]) for f in fr)
        print(f"{nombre}: {len(fr)} fragmentos, el más largo de {largos} caracteres")
        todos += fr
    with open(RAIZ / "corpus" / "fragmentos.jsonl", "w", encoding="utf-8") as fh:
        for f in todos:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    return todos


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--srd", default=str(RAIZ / "srd"), help="carpeta con los PDF del SRD")
    construir(ap.parse_args().srd)
