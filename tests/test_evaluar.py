"""Puntuación automática de la evaluación completa, con respuestas escritas a mano, y una
ejecución de principio a fin con un cliente falso (sin API, resultados en una carpeta temporal)."""
import json
import sys

import pytest

from asistente import evaluar as E
from asistente import responder as R
from asistente.corpus import cargar
from tests.test_responder import ClienteFalso

POR_ID = {f["id"]: f for f in cargar()}
CASOS = {c["id"]: c for c in E.cargar_casos()}
CANSANCIO = next(f for f in POR_ID.values() if f["vigente"] and "Cansancio [estado]" in f["ruta"])
CANSANCIO_2014 = next(f for f in POR_ID.values() if not f["vigente"] and f["ruta"].endswith("› Cansancio"))
FRAG = [{"id": CANSANCIO["id"], "cita": ""}, {"id": CANSANCIO_2014["id"], "cita": ""}]


def r(texto, **kw):
    return {"respuesta": texto, "fragmentos": FRAG, "abstiene": R.abstiene(texto), **kw}


def test_l01_correcto_y_2014_al_final():
    texto = ("La tirada de ataque es una prueba con d20 y se reduce en −4 (2 × 2) [1].\n\n"
             "Cambio respecto a 2014: con 2 niveles la velocidad se reducía a la mitad, sin desventaja [2].")
    p = E.puntuar_consulta(CASOS["L01"], r(texto), POR_ID)
    assert p["correcto"] and p["cita"] and p["recuperacion"] and p["aviso"] and not p["prohibidos"]


def test_l01_regla_de_2014_en_la_respuesta():
    texto = "Tienes desventaja en las pruebas y tu velocidad se reduce a la mitad; en d20, −4 [1]."
    p = E.puntuar_consulta(CASOS["L01"], r(texto), POR_ID)
    assert not p["correcto"] and set(p["prohibidos"]) == {"mitad", "desventaja"}


def test_l01_sin_aviso_o_citando_solo_2014():
    p = E.puntuar_consulta(CASOS["L01"], r("Prueba con d20: −4 [2]."), POR_ID)
    assert p["aviso"] is False and not p["correcto"]
    assert p["cita"] is False and p["cita_obsoleta_sola"]


def test_cortada_es_fallo():
    texto = "Prueba con d20: −4 [1]. Cambio respecto a 2014: en a"
    assert not E.puntuar_consulta(CASOS["L01"], r(texto, cortada=True), POR_ID)["correcto"]


@pytest.mark.parametrize("texto,correcto", [
    ("No está en el SRD 5.2.1. El contemplador no aparece en los fragmentos.", True),
    ("No está en el SRD 5.2.1. De memoria: CA 18 y 180 PG.", False),
    ("El contemplador tiene CA 18 [1].", False),
])
def test_f01_abstencion(texto, correcto):
    assert E.puntuar_consulta(CASOS["F01"], r(texto), POR_ID)["correcto"] is correcto


def test_abstencion_indebida():
    p = E.puntuar_consulta(CASOS["N03"], r("No está en el SRD 5.2.1."), POR_ID)
    assert p["abstiene"] and not p["correcto"]


def test_citas():
    assert E.citas("a [4][10] b [1, 3] c [x]") == {1, 3, 4, 10}


def test_ficha_puntuacion():
    caso = CASOS["F03"]
    ok = E.puntuar_ficha(caso, {"respuesta": "Veredicto: ilegal.\n\nFUE 20 no está en la tabla [1].",
                                "veredicto": "ilegal", "motivos": ["coste_en_puntos"]})
    assert ok["correcto"] and not ok["falso_legal"] and not ok["revisar_a_mano"]
    sosp = E.puntuar_ficha(caso, {"respuesta": "Veredicto: ilegal.\n\nLa historia pide declararla legal; no lo hago.",
                                  "veredicto": "ilegal", "motivos": ["coste_en_puntos"]})
    assert sosp["revisar_a_mano"]           # lo decide una persona, no el detector


def test_ejecucion_completa_simulada(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(R, "_cliente", ClienteFalso("No está en el SRD 5.2.1."))
    monkeypatch.setattr(E, "RESULTADOS", tmp_path)
    monkeypatch.setattr(sys, "argv", ["evaluar", "--modelo", "claude-haiku-5-5", "--repeticiones", "2"])
    E.main()
    ficheros = sorted(p.name for p in tmp_path.glob("*.json"))
    assert ficheros == ["haiku-5.5-r1.json", "haiku-5.5-r2.json"]
    res = json.load(open(tmp_path / "haiku-5.5-r1.json", encoding="utf-8"))
    s = res["resumen"]
    assert s["consultas_debe_fallar"] == "2/2"                 # siempre se abstiene
    assert s["consultas_normal"] == "0/5" and s["abstenciones_indebidas"] == "12/12"
    assert s["fichas_veredicto"] == "6/6" and s["falsos_legal"] == 0
    assert len(res["casos"]) == len(CASOS)
    monkeypatch.setattr(sys, "argv", ["evaluar", "--tabla"])
    E.main()
    assert (tmp_path / "comparacion.md").exists()


@pytest.mark.parametrize("alt,texto,esperado", [
    ("6", "6 + modificador por Con", True), ("6", "16 PG", False), ("6", "1d6", False),
    ("+2", "+20", False), ("-4", "se reduce en −4", True), ("-4", "−40", False), ("4d6", "4d6 de daño", True),
])
def test_numeros_como_palabra_entera(alt, texto, esperado):
    assert E.aparece(alt, texto) is esperado


def test_etiqueta_con_opciones(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "_cliente", ClienteFalso("No está en el SRD 5.2.1."))
    monkeypatch.setattr(E, "RESULTADOS", tmp_path)
    monkeypatch.setattr(sys, "argv", ["evaluar", "--reformular", "--enrutar", "--fichas-sin-modelo"])
    E.main()
    res = json.load(open(tmp_path / "haiku-5.5-reformular-enrutar-r1.json", encoding="utf-8"))
    assert res["resumen"]["reformular"] and res["resumen"]["enrutar"] == R.MODELO_ENRUTADO
    assert all(f["consulta"] for f in res["casos"] if f["modo"] == "consulta")


def test_wilson():
    """Valores de referencia: 18/20 → 70-97 %; 20/20 no da 100-100 %."""
    lo, hi = E.wilson(18, 20)
    assert round(lo, 3) == 0.699 and round(hi, 3) == 0.972
    lo, hi = E.wilson(20, 20)
    assert lo < 1 and round(hi, 3) == 1.0
