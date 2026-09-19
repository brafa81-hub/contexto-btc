#!/usr/bin/env python3
"""
Implementacion de referencia de consistencia_minima segun la enmienda 43,
y su bateria de casos sinteticos. NO forma parte de filtro.py (la etapa de
confirmacion forward aun no esta implementada alli).

Entrada: lista de 5 trimestres. Cada uno es +1 / -1 (signo de theta del
trimestre) o None (trimestre indefinido: sin dias activos o sin dias
inactivos). Mas el signo esperado, +1 o -1.

Salida: "CUMPLE" | "NO_CUMPLE" | "SIN_VEREDICTO"
  CUMPLE        -> el criterio pasa
  NO_CUMPLE     -> el criterio falla (camino a RECHAZADA_FORWARD)
  SIN_VEREDICTO -> la variable pasa a PENDIENTE_REVISION
"""

SUELO_DEFINIDOS = 3


def consistencia_minima(trimestres, signo_esperado):
    definidos = [t for t in trimestres if t is not None]
    n_def = len(definidos)
    n_indef = len(trimestres) - n_def
    a_favor = sum(1 for t in definidos if t == signo_esperado)

    if n_def < SUELO_DEFINIDOS:
        return "SIN_VEREDICTO", n_def, n_indef, a_favor
    if a_favor * 2 == n_def:                    # empate exacto
        return "SIN_VEREDICTO", n_def, n_indef, a_favor
    if a_favor * 2 > n_def:                     # mayoria estricta
        return "CUMPLE", n_def, n_indef, a_favor
    return "NO_CUMPLE", n_def, n_indef, a_favor


CASOS = [
    # (trimestres, signo_esperado, resultado_esperado, etiqueta)
    ([+1, +1, +1, -1, -1], +1, "CUMPLE",        "5 definidos, 3-2 a favor"),
    ([+1, +1, -1, -1, -1], +1, "NO_CUMPLE",     "5 definidos, 2-3 en contra"),
    ([+1, +1, +1, +1, +1], +1, "CUMPLE",        "5 definidos, 5-0"),
    ([-1, -1, -1, -1, -1], +1, "NO_CUMPLE",     "5 definidos, 0-5"),
    ([+1, +1, +1, -1, None], +1, "CUMPLE",      "4 definidos, 3-1 a favor"),
    ([+1, +1, -1, -1, None], +1, "SIN_VEREDICTO", "4 definidos, empate 2-2"),
    ([+1, -1, -1, -1, None], +1, "NO_CUMPLE",   "4 definidos, 1-3 en contra"),
    ([+1, +1, -1, None, None], +1, "CUMPLE",    "3 definidos, 2-1 a favor"),
    ([+1, -1, -1, None, None], +1, "NO_CUMPLE", "3 definidos, 1-2 en contra"),
    ([+1, +1, +1, None, None], +1, "CUMPLE",    "3 definidos, 3-0"),
    ([+1, -1, None, None, None], +1, "SIN_VEREDICTO", "2 definidos (bajo el suelo)"),
    ([+1, None, None, None, None], +1, "SIN_VEREDICTO", "1 definido"),
    ([None] * 5, +1, "SIN_VEREDICTO",           "0 definidos"),
    # signo esperado negativo: misma mecanica, espejo
    ([-1, -1, -1, +1, +1], -1, "CUMPLE",        "signo esperado -1, 3-2 a favor"),
    ([-1, -1, +1, +1, None], -1, "SIN_VEREDICTO", "signo esperado -1, empate 2-2"),
]

if __name__ == "__main__":
    fallos = 0
    print(f"{'caso':<38} {'def':>3} {'ind':>3} {'fav':>3}  {'obtenido':<14} ok")
    for tri, signo, esperado, etiqueta in CASOS:
        res, n_def, n_ind, fav = consistencia_minima(tri, signo)
        ok = res == esperado
        fallos += not ok
        print(f"{etiqueta:<38} {n_def:>3} {n_ind:>3} {fav:>3}  {res:<14} {'OK' if ok else 'FALLA'}")
    print()
    print("TODOS LOS CASOS OK" if not fallos else f"{fallos} CASOS FALLIDOS")
