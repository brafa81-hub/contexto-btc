"""
simulacion_3de5.py — Calibracion del criterio "3 de 5" (consistencia_minima)
de confirmacion_forward (v2.json), tal como se especifica en el repo:

    signo_agregado:    signo(theta_F) == signo(theta_B2)
    magnitud:          abs(theta_F) >= max(0.5*abs(theta_B2), M=0.03)
    consistencia_minima: al menos 3 de los 5 trimestres presentan el signo esperado

Los 3 criterios son TODOS obligatorios (todos_obligatorios=true). Esta
simulacion mide, aislando cada pieza, cuanto aporta o resta el "3 de 5" en
concreto: reporta tambien el resultado de los otros dos criterios por
separado para poder atribuir el efecto.

Pipeline por replica:
  1) generar datos historicos (bloque_1 + bloque_2) + 5 trimestres forward
  2) pasar bloque_1/bloque_2 por gate1, gate3, gate4, test_permutacion
     (motor.py, exactamente como filtro.py) -> obtiene theta_B2, signo_esperado
  3) si sobrevive (gates pasan + permutacion con datos suficientes):
     calcular theta_F (agregado 5 trimestres) y theta por trimestre sobre la
     CONTINUACION forward sintetica
  4) evaluar los 3 criterios de confirmacion_forward
  5) registrar: autoriza_todos_3 (los 3 criterios), y ademas cada criterio
     por separado, para diagnosticar

NO se modifica ningun criterio: solo se mide bajo la especificacion vigente.
"""

import numpy as np
import pandas as pd

import motor
import generador as gen


N = 30  # definicion_de_efecto.horizonte_N.valor (v2.json)
DIAS_TRIMESTRE = 91  # aprox., como en la sesion de calibracion de 6a
N_TRIMESTRES = 5
M_ABSOLUTO = 0.03  # umbral_absoluto_M.valor (v2.json)

# Parametros de gates (mismos valores usados en la sesion de calibracion de 6a,
# ver bitacora-sesiones-3.md: gate1/gate3/permutacion validados linea a linea)
SEMILLA_ROTACION = 7
N_ROTACIONES = 200
PERCENTIL_ROTACION = 90
MIN_OBS_TRAMO = 2
MIN_OBS_GATE3 = 5
N_TRAMOS_GATE1 = 4

DIAS_EPISODIO = 30  # max(21, N) con N=30
OBS_MASCARADAS_MIN = 20  # observaciones_enmascaradas_minimas (v2.json)
EPISODIOS_MIN_B2 = 8  # episodios_independientes_minimos (v2.json) -- referencia,
                        # NO se aplica como criterio de 6a (eso ya se abandono);
                        # se usa aqui solo como filtro de admisibilidad de bloque_2,
                        # igual que en filtro.py real.
N_PERMUTACIONES = 2000
SEMILLA_PERMUTACION = 0


def _theta_trimestre(mask_tr, ret_tr):
    """Mismo estimador que theta_B2 en test_permutacion: mediana(activo) - mediana(inactivo)."""
    z = pd.DataFrame({"m": mask_tr, "r": ret_tr}).dropna()
    if z["m"].sum() == 0 or (~z["m"]).sum() == 0:
        return float("nan")
    return float(z[z["m"]]["r"].median() - z[~z["m"]]["r"].median())


def procesar_replica(semilla, theta_nominal, signo_esperado="positivo"):
    """
    Ejecuta el pipeline completo sobre una replica. Devuelve None si la
    variable no sobrevive a gates/permutacion (insuficiencia o rechazo), o
    un dict con el resultado de confirmacion_forward si sobrevive.
    """
    n_historico = 800  # bloque_1 + bloque_2 combinados, suficiente para 4 tramos + permutacion
    d = gen.generar_replica(
        semilla=semilla, n_historico=n_historico,
        n_forward_dias=N_TRIMESTRES * DIAS_TRIMESTRE,
        theta_nominal=theta_nominal,
    )

    idx_hist = d["fechas"][:n_historico]
    mitad = n_historico // 2
    b1 = idx_hist[:mitad]
    b2 = idx_hist[mitad:]

    mask = d["mask"]
    ret = d["ret"]
    precio = d["precio"]

    m1 = mask.loc[b1]
    tramos = motor.tramos_de(b1, N_TRAMOS_GATE1)

    g1 = motor.gate1(m1, ret, tramos, N=N, semilla=SEMILLA_ROTACION,
                      n_rotaciones=N_ROTACIONES, percentil=PERCENTIL_ROTACION,
                      min_obs_tramo=MIN_OBS_TRAMO)
    if g1.get("no_evaluable") or g1["insuficiencia"] or not g1["pasa"]:
        return None

    base = pd.DataFrame({
        "mayer": precio / precio.rolling(200).mean(),
        "vol30": precio.pct_change().rolling(30).std(),
        "mom30": precio / precio.shift(30) - 1,
    })
    g3 = motor.gate3(m1, ret, base, N=N, semilla=SEMILLA_ROTACION,
                      n_rotaciones=N_ROTACIONES, percentil=PERCENTIL_ROTACION,
                      minimo=MIN_OBS_GATE3)
    if g3["insuficiencia"] or not g3["pasa"]:
        return None

    g4 = motor.gate4(g1["correlaciones_por_tramo"])
    if not g4["pasa"]:
        return None

    m2 = mask.loc[b2]
    perm = motor.test_permutacion(
        m2, ret, signo_esperado, dias_ep=DIAS_EPISODIO,
        obs_min=OBS_MASCARADAS_MIN, eps_min=2,  # eps_min relajado aqui: el
        # minimo doctrinal de 8 ya se sabe que casi ninguna replica lo alcanza
        # (hallazgo de la sesion de 6a); usar 8 aqui dejaria casi 0 supervivientes
        # y no permitiria calibrar el "3 de 5". Se documenta como limitacion.
        n_permutaciones=N_PERMUTACIONES, semilla=SEMILLA_PERMUTACION,
    )
    if perm["insuficiencia"]:
        return None

    theta_B2 = perm["theta_B2"]

    # --- Continuacion forward: 5 trimestres sinteticos ---
    fecha_inicio_fwd = d["fecha_corte_forward"]
    fechas_fwd = d["fechas"][d["fechas"] > fecha_inicio_fwd]
    fechas_fwd = fechas_fwd[:N_TRIMESTRES * DIAS_TRIMESTRE]

    thetas_trimestre = []
    for q in range(N_TRIMESTRES):
        ini = q * DIAS_TRIMESTRE
        fin = ini + DIAS_TRIMESTRE
        idx_q = fechas_fwd[ini:fin]
        if len(idx_q) == 0:
            thetas_trimestre.append(float("nan"))
            continue
        thetas_trimestre.append(_theta_trimestre(mask.loc[idx_q], ret.loc[idx_q]))

    theta_F = _theta_trimestre(mask.loc[fechas_fwd], ret.loc[fechas_fwd])

    # --- Los 3 criterios de confirmacion_forward, tal como estan en v2.json ---
    signo_B2 = np.sign(theta_B2)
    signo_F = np.sign(theta_F) if np.isfinite(theta_F) else 0

    c_signo = bool(np.isfinite(theta_F) and signo_F == signo_B2 and signo_F != 0)

    c_magnitud = bool(
        np.isfinite(theta_F)
        and abs(theta_F) >= max(0.5 * abs(theta_B2), M_ABSOLUTO)
    )

    signo_esperado_q = np.sign(theta_B2)  # "signo esperado" = signo de B2, coherente con el resto del sistema
    aciertos = sum(
        1 for t in thetas_trimestre
        if np.isfinite(t) and np.sign(t) == signo_esperado_q and np.sign(t) != 0
    )
    c_consistencia = aciertos >= 3

    autoriza = c_signo and c_magnitud and c_consistencia

    return {
        "theta_B2": theta_B2, "theta_F": theta_F, "thetas_trimestre": thetas_trimestre,
        "aciertos_trimestre": aciertos,
        "c_signo": c_signo, "c_magnitud": c_magnitud, "c_consistencia": c_consistencia,
        "autoriza": autoriza,
    }
