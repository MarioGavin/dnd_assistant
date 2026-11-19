"""Opciones de la búsqueda por palabras: raíces y sinónimos de la guía de conversión."""
import json

from asistente.busqueda import RAIZ, expandir, palabras


def test_raices():
    assert palabras("Atacar, ataca", raices=True) == ["atac", "atac"]
    assert palabras("Caídas") == ["caidas"]


def test_sinonimos_de_la_guia():
    assert "prueba con d20" in expandir("¿Tengo desventaja en las tiradas de ataque?")
    assert "especie" in expandir("¿Qué raza elijo?")
    assert expandir("¿Cuánto daño hace una caída?") == "¿Cuánto daño hace una caída?"


def test_cada_sinonimo_cita_la_guia():
    tabla = json.load(open(RAIZ / "datos" / "sinonimos.json", encoding="utf-8"))["sinonimos"]
    assert tabla and all(s["guia"] and s["de"] and s["a"] for s in tabla)
