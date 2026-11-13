"""Muestra aleatoria de fragmentos para revisar el troceado a mano contra el PDF.

Genera corpus/muestra_revision.md: cada fragmento con casillas para anotar si el
título, el texto y la página coinciden con el original.
"""
import random
from asistente.corpus import RAIZ, cabecera, cargar

def muestra(n_vigente=15, n_obsoleto=5, semilla=13):
    fr = cargar()
    rnd = random.Random(semilla)
    elegidos = (rnd.sample([f for f in fr if f["vigente"]], n_vigente)
                + rnd.sample([f for f in fr if not f["vigente"]], n_obsoleto))
    lineas = ["# Revisión manual del troceado", "",
              f"Semilla {semilla}. Cada fragmento se compara con el PDF en la página indicada:",
              "T = título y ruta correctos · C = texto completo y en orden · P = página correcta", ""]
    for i, f in enumerate(elegidos, 1):
        lineas += [f"## {i}. {f['id']} — {cabecera(f)}", "", "- [ ] T  - [ ] C  - [ ] P  · Nota: ", "",
                   "```text", f["texto"], "```", ""]
    (RAIZ / "corpus" / "muestra_revision.md").write_text("\n".join(lineas), encoding="utf-8")
    print(f"{len(elegidos)} fragmentos en corpus/muestra_revision.md")

if __name__ == "__main__":
    muestra()
