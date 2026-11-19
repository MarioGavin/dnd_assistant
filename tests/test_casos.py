"""Coherencia del conjunto de prueba: formato y que cada fuente esperada exista en el corpus."""
import json

import pytest

from asistente.corpus import RAIZ, cargar

CASOS = json.load(open(RAIZ / "casos" / "casos_prueba.json", encoding="utf-8"))
FRAGMENTOS = cargar()


def coincide(f, fuente):
    return (f["documento"] == fuente["documento"]
            and fuente["apartado"].lower() in f["ruta"].lower()
            and f["pagina"] <= fuente["pagina"] <= f["pagina_fin"])


def test_ids_unicos_y_tipos():
    assert len({c["id"] for c in CASOS}) == len(CASOS)
    assert {c["tipo"] for c in CASOS} <= {"normal", "limite", "debe_fallar"}
    assert all(("pregunta" in c) != ("ficha" in c) for c in CASOS)


@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_fuentes_existen(caso):
    fuentes = [f for grupo in caso.get("fuentes", []) for f in grupo] + caso.get("fuentes_obsoletas", [])
    for fuente in fuentes:
        assert any(coincide(f, fuente) for f in FRAGMENTOS), fuente


CONTRASTE = json.load(open(RAIZ / "casos" / "consultas_contraste.json", encoding="utf-8"))


@pytest.mark.parametrize("caso", CONTRASTE, ids=[c["id"] for c in CONTRASTE])
def test_fuentes_de_contraste_existen(caso):
    assert caso["id"] not in {c["id"] for c in CASOS}
    for fuente in [f for grupo in caso["fuentes"] for f in grupo]:
        assert any(coincide(f, fuente) for f in FRAGMENTOS), fuente
