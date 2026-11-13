"""Comprueba que frases conocidas del SRD caen en la página y el apartado correctos.
Cada frase y su página se verificaron a mano en los PDF oficiales."""
import pytest
from asistente.corpus import cargar

FRAGMENTOS = cargar()

CASOS = [  # (documento, frase literal, página, palabra que debe estar en la ruta)
    ("SRD 5.2.1 ES", "Tienes 27 puntos", 23, "Paso 3"),
    ("SRD 5.2.1 ES", "| 14 | 7 |", 23, "Paso 3"),
    ("SRD 5.2.1 ES", "Explorador, guerrero o paladín | 6", 26, "Subir de nivel"),
    ("SRD 5.2.1 ES", "solo puedes gastar un espacio de conjuro", 115, "Un conjuro por cada espacio"),
    ("SRD 5.2.1 ES", "2 × tu nivel de cansancio", 197, "Cansancio [estado]"),
    ("SRD 5.2.1 ES", "| 3 | 150 | 225 | 400 |", 221, "presupuesto de PX"),
    ("SRD 5.2.1 ES", "Evocación de nivel 3 (hechicero, mago)", 125, "Bola de fuego"),
    ("SRD 5.2.1 ES", "desventaja en su tirada de iniciativa", 14, "Iniciativa"),
    ("SRD 5.1 ES", "Velocidad reducida a la mitad", 389, "Cansancio"),
    ("SRD 5.1 ES", "contempladores", 274, "Monstruos"),
    ("SRD 5.1 ES", "excepto si se trata de un truco", 107, "Acción adicional"),
]


@pytest.mark.parametrize("documento,frase,pagina,en_ruta", CASOS)
def test_pagina_y_apartado(documento, frase, pagina, en_ruta):
    hallados = [f for f in FRAGMENTOS if f["documento"] == documento and frase in f["texto"]]
    assert hallados, f"no aparece «{frase}»"
    f = hallados[0]
    assert f["pagina"] <= pagina <= f["pagina_fin"], (f["pagina"], f["pagina_fin"])
    assert en_ruta.lower() in f["ruta"].lower(), f["ruta"]


def test_contemplador_no_esta_en_el_vigente():
    vigente = " ".join(f["texto"].lower() for f in FRAGMENTOS if f["vigente"])
    for nombre in ("contemplador", "beholder", "azotamentes", "illithid"):
        assert nombre not in vigente
