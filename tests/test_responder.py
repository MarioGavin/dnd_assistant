"""Responder sin llamar a la API: abstención, selección del contexto, respuestas cortadas,
datos personales e inyección en fichas. El cliente de Anthropic se sustituye por uno falso."""
import json
from types import SimpleNamespace

import pytest

from asistente import responder as R
from asistente.corpus import RAIZ, cargar

FRAGMENTOS = cargar()
CASOS = json.load(open(RAIZ / "casos" / "casos_prueba.json", encoding="utf-8"))


class ClienteFalso:
    """Guarda cada petición y devuelve una respuesta fija."""
    def __init__(self, texto="Respuesta [1].", stop="end_turn", bloques=("text",)):
        self.peticiones, self.texto, self.stop, self.bloques = [], texto, stop, bloques
        self.messages = self

    def create(self, **kw):
        self.peticiones.append(kw)
        content = [SimpleNamespace(type=t, text=self.texto) if t == "text" else SimpleNamespace(type=t)
                   for t in self.bloques]
        return SimpleNamespace(content=content, stop_reason=self.stop,
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=100))


@pytest.fixture
def falso(monkeypatch):
    c = ClienteFalso()
    monkeypatch.setattr(R, "_cliente", c)
    return c


@pytest.mark.parametrize("texto,esperado", [
    ("No está en el SRD 5.2.1.", True),
    ("  No está en el SRD 5.2.1. El contemplador no aparece.", True),
    ("No esta en el SRD 5.2.1.", True),
    # respuesta correcta que contiene la frase (fallo 13): no es abstención
    ("No está en el SRD 5.2.1 que los bandidos pierdan su primer turno. Lo que sí dice…", False),
    ("Tienen desventaja en la iniciativa [1]. No está en el SRD 5.2.1.", False),
])
def test_abstencion_solo_al_principio(texto, esperado):
    assert R.abstiene(texto) is esperado


def test_seleccion_limita_2014():
    obsoletos = [f for f in FRAGMENTOS if not f["vigente"]][:40]
    elegidos = R.seleccionar(obsoletos, FRAGMENTOS, k=10, max_obsoletos=1)
    assert sum(not f["vigente"] for f in elegidos) <= 1
    titulos = R._vigentes_por_titulo(FRAGMENTOS)
    assert all(f["vigente"] or R._titulo(f) in titulos for f in elegidos)


def test_pareja_2024_va_delante():
    viejo = next(f for f in FRAGMENTOS if not f["vigente"] and R._titulo(f) == "cansancio")
    elegidos = R.emparejar(R.seleccionar([viejo], FRAGMENTOS), FRAGMENTOS)
    assert [f["vigente"] for f in elegidos] == [True, False]
    assert "Cansancio [estado]" in elegidos[0]["ruta"]


def test_respuesta_cortada(falso):
    falso.stop, falso.bloques = "max_tokens", ("thinking", "text")
    r = R.llamar("sistema", "mensaje")
    assert r["cortada"] and r["bloques"] == ["thinking", "text"]
    assert falso.peticiones[0]["max_tokens"] == R.MAX_TOKENS
    assert "temperature" not in falso.peticiones[0]


def test_coste():
    c = ClienteFalso()
    R._cliente = c
    try:
        r = R.llamar("s", "m", modelo="claude-sonnet-5-5")
        assert r["coste_usd"] == pytest.approx((1000 * 2 + 100 * 10) / 1e6)
    finally:
        R._cliente = None


FICHAS = [c for c in CASOS if c["modo"] == "ficha"]


@pytest.mark.parametrize("caso", FICHAS, ids=[c["id"] for c in FICHAS])
def test_ficha_sin_datos_personales(falso, caso):
    R.responder_ficha(caso["ficha"])
    enviado = json.dumps(falso.peticiones[-1], ensure_ascii=False)
    for dato in caso["ficha"]["jugador"].values():
        assert str(dato) not in enviado


def test_inyeccion_no_cambia_el_veredicto(falso):
    f03 = next(c for c in CASOS if c["id"] == "F03")
    falso.texto = "La ficha es LEGAL."
    r = R.responder_ficha(f03["ficha"])
    assert r["veredicto"] == "ilegal" and r["respuesta"].startswith("Veredicto: ilegal.")
    mensaje = falso.peticiones[-1]["messages"][0]["content"]
    assert "<ficha>" in mensaje and "Ignora las reglas" in mensaje.split("<ficha>")[1]   # va como dato


def test_ficha_cita_las_fuentes_del_validador(falso):
    n01 = next(c for c in CASOS if c["id"] == "N01")
    r = R.responder_ficha(n01["ficha"])
    citas = [f["cita"] for f in r["fragmentos"]]
    assert any("Tabla: Costes en puntos" in c for c in citas)         # la tabla, no solo la introducción
    assert any("Soldado" in c for c in citas)


class ClientePorInstruccion(ClienteFalso):
    """Responde según la instrucción de sistema: términos al reformular, texto fijo si no."""
    def create(self, **kw):
        r = super().create(**kw)
        if kw["system"] == R.SISTEMA_REFORMULAR:
            r.content[0].text = "Cansancio [estado], prueba con d20, tirada de ataque"
        return r


def test_reformular(monkeypatch):
    c = ClientePorInstruccion("Respuesta [1].")
    monkeypatch.setattr(R, "_cliente", c)
    pregunta = "Tengo 2 niveles de cansancio, ¿qué me pasa al atacar?"
    r = R.responder(pregunta, reformular_pregunta=True)
    assert len(c.peticiones) == 2
    assert pregunta in c.peticiones[0]["messages"][0]["content"]            # la reformulación ve la pregunta
    assert "prueba con d20" in r["consulta"]                                 # se busca con los términos
    mensaje = c.peticiones[1]["messages"][0]["content"]
    assert mensaje.endswith("Pregunta: " + pregunta)                         # el modelo recibe la original
    assert r["tokens_entrada"] == 2000 and r["coste_usd"] == pytest.approx(2 * (1000 * 0.10 + 100 * 0.50) / 1e6)


@pytest.mark.parametrize("pregunta", [
    "Hemos pillado por sorpresa a unos bandidos, ¿pierden su primer turno?",
    "¿Cuántos dardos lanza Proyectil mágico?",
])
def test_enrutar(falso, pregunta):
    r = R.responder(pregunta, enrutar=True)
    hay_2014 = any("OBSOLETO" in f["cita"] for f in r["fragmentos"])
    assert r["enrutada"] == hay_2014
    assert falso.peticiones[-1]["model"] == (R.MODELO_ENRUTADO if hay_2014 else R.MODELO)
