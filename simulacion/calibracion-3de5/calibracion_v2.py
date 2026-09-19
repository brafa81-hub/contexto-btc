"""
calibracion_v2.py — Repeticion de la calibracion del "3 de 5" (consistencia_minima)
de confirmacion_forward, LIMPIA de los dos artefactos identificados en la sesion
Opus del 19-sep-2026:

  1) generador.py corregido: n_historico=4260 (2 bloques de 5,83 anios cada uno,
     el tamano real que usan las variables del registro), no 1200 (bloques de
     ~1,6 anios, que violaba protocolo.particion_datos.minimo_por_bloque_anios=3).
  2) eps_min=8 REAL de v2.json en el filtro de admisibilidad de bloque_2 (episodios
     independientes), SIN relajar a 2 como en la sesion anterior.

Ademas usa la consistencia_minima YA CORREGIDA (enmienda 43, version_esquema
2.15.0): exclusion de trimestres indefinidos del recuento, suelo de 3 definidos,
mayoria estricta, empate/insuficientes -> SIN_VEREDICTO (equivalente de
simulacion a PENDIENTE_REVISION). Usa prueba_consistencia.consistencia_minima()
tal cual esta en el repo (implementacion de referencia oficial, ya validada
contra los 15 casos de la enmienda), no una reimplementacion propia.

NO se modifica ningun criterio de v2.json. Esto es medicion, no propuesta.
"""
import sys, json, time
sys.path.insert(0, '.')
import numpy as np
import pandas as pd

import motor
import generador as gen
from prueba_consistencia import consistencia_minima

N = 30
DIAS_TRIMESTRE = 91
N_TRIMESTRES = 5
M_ABSOLUTO = 0.03

SEMILLA_ROTACION = 7
N_ROTACIONES = 200
PERCENTIL_ROTACION = 90
MIN_OBS_TRAMO = 2
MIN_OBS_GATE3 = 5
N_TRAMOS_GATE1 = 4

DIAS_EPISODIO = 30
OBS_MASCARADAS_MIN = 20
EPISODIOS_MIN_B2 = 8  # eps_min REAL de v2.json, SIN relajar
N_PERMUTACIONES = 2000
SEMILLA_PERMUTACION = 0

NIVELES = {
    "ruido_puro": 0.0,
    "efecto_bajo": 0.042,
    "efecto_medio": 0.084,
    "efecto_alto": 0.168,
}


def _theta_trimestre(mask_tr, ret_tr):
    z = pd.DataFrame({"m": mask_tr, "r": ret_tr}).dropna()
    if z["m"].sum() == 0 or (~z["m"]).sum() == 0:
        return float("nan")
    return float(z[z["m"]]["r"].median() - z[~z["m"]]["r"].median())


def procesar_replica(semilla, theta_nominal, signo_esperado="positivo"):
    """
    Devuelve None si la variable no sobrevive gates+permutacion (con eps_min=8
    real). Si sobrevive, devuelve el resultado de los 3 criterios de
    confirmacion_forward, incluida la consistencia_minima corregida.
    """
    n_historico = gen.generar_replica.__defaults__[0]  # 4260, tomado del generador corregido
    d = gen.generar_replica(
        semilla=semilla, n_historico=n_historico,
        n_forward_dias=N_TRIMESTRES * DIAS_TRIMESTRE,
        theta_nominal=theta_nominal,
    )
    idx_hist = d["fechas"][:n_historico]
    mitad = n_historico // 2
    b1 = idx_hist[:mitad]
    b2 = idx_hist[mitad:]
    mask = d["mask"]; ret = d["ret"]; precio = d["precio"]

    m1 = mask.loc[b1]
    tramos = motor.tramos_de(b1, N_TRAMOS_GATE1)
    try:
        g1 = motor.gate1(m1, ret, tramos, N=N, semilla=SEMILLA_ROTACION,
                          n_rotaciones=N_ROTACIONES, percentil=PERCENTIL_ROTACION,
                          min_obs_tramo=MIN_OBS_TRAMO)
    except RuntimeError:
        return None
    if g1.get("no_evaluable") or g1["insuficiencia"] or not g1["pasa"]:
        return None

    base = pd.DataFrame({
        "mayer": precio / precio.rolling(200).mean(),
        "vol30": precio.pct_change().rolling(30).std(),
        "mom30": precio / precio.shift(30) - 1,
    })
    try:
        g3 = motor.gate3(m1, ret, base, N=N, semilla=SEMILLA_ROTACION,
                          n_rotaciones=N_ROTACIONES, percentil=PERCENTIL_ROTACION,
                          minimo=MIN_OBS_GATE3)
    except RuntimeError:
        return None
    if g3["insuficiencia"] or not g3["pasa"]:
        return None

    g4 = motor.gate4(g1["correlaciones_por_tramo"])
    if not g4["pasa"]:
        return None

    m2 = mask.loc[b2]
    perm = motor.test_permutacion(
        m2, ret, signo_esperado, dias_ep=DIAS_EPISODIO,
        obs_min=OBS_MASCARADAS_MIN, eps_min=EPISODIOS_MIN_B2,
        n_permutaciones=N_PERMUTACIONES, semilla=SEMILLA_PERMUTACION,
    )
    if perm["insuficiencia"]:
        return None

    theta_B2 = perm["theta_B2"]

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

    signo_B2 = np.sign(theta_B2)
    signo_F = np.sign(theta_F) if np.isfinite(theta_F) else 0

    c_signo = bool(np.isfinite(theta_F) and signo_F == signo_B2 and signo_F != 0)
    c_magnitud = bool(np.isfinite(theta_F) and abs(theta_F) >= max(0.5 * abs(theta_B2), M_ABSOLUTO))

    signo_esperado_q = int(signo_B2)
    # convertir cada theta de trimestre a +1/-1/None segun la definicion doctrinal
    # (indefinido = sin dias activos o sin dias inactivos = theta NaN, ya calculado asi arriba)
    trimestres_signo = [
        (None if not np.isfinite(t) else (1 if t > 0 else (-1 if t < 0 else 0)))
        for t in thetas_trimestre
    ]
    veredicto_cons, n_def, n_indef, a_favor = consistencia_minima(trimestres_signo, signo_esperado_q)
    c_consistencia = (veredicto_cons == "CUMPLE")
    sin_veredicto = (veredicto_cons == "SIN_VEREDICTO")

    autoriza = c_signo and c_magnitud and c_consistencia

    return {
        "theta_B2": theta_B2, "theta_F": theta_F, "thetas_trimestre": thetas_trimestre,
        "trimestres_signo": trimestres_signo, "n_definidos": n_def, "n_indefinidos": n_indef,
        "a_favor": a_favor, "veredicto_consistencia": veredicto_cons,
        "c_signo": c_signo, "c_magnitud": c_magnitud, "c_consistencia": c_consistencia,
        "sin_veredicto": sin_veredicto,
        "autoriza": autoriza,
    }


def correr(n_replicas, semilla_base):
    resultados = {}
    for nombre, theta in NIVELES.items():
        supervivientes = []
        n_no_llega_forward = 0
        t0 = time.time()
        for i in range(n_replicas):
            semilla = semilla_base + i
            r = procesar_replica(semilla, theta)
            if r is None:
                n_no_llega_forward += 1
            else:
                supervivientes.append(r)
        dt = time.time() - t0
        resultados[nombre] = {
            "theta_nominal": theta,
            "n_replicas": n_replicas,
            "n_llega_a_forward": len(supervivientes),
            "n_no_llega_a_forward": n_no_llega_forward,
            "tasa_llega_a_forward": len(supervivientes) / n_replicas,
            "detalle": supervivientes,
            "tiempo_seg": round(dt, 1),
        }
        print(f"  {nombre}: {len(supervivientes)}/{n_replicas} llegan a forward "
              f"({100*len(supervivientes)/n_replicas:.1f}%) — {dt:.1f}s")
    return resultados


if __name__ == "__main__":
    N_REPLICAS = 300
    print(f"n_historico usado: {gen.generar_replica.__defaults__[0]}")
    print(f"eps_min_b2 = {EPISODIOS_MIN_B2} (real de v2.json, sin relajar)")
    print()
    print("=== CALIBRACION CORREGIDA (generador 4260 dias + eps_min=8 + consistencia_minima enmienda 43) ===")
    res = correr(n_replicas=N_REPLICAS, semilla_base=20000)

    with open("resultado_calibracion_v2.json", "w", encoding="utf-8") as f:
        # el detalle completo (con arrays numpy/theta) no es serializable directo; guardamos resumen + detalle limpio
        def limpio(d):
            return {k: (list(v) if isinstance(v, (list,)) else v) for k, v in d.items()}
        serializable = {
            nombre: {
                **{k: v for k, v in r.items() if k != "detalle"},
                "detalle": [
                    {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                     for k, v in d.items()}
                    for d in r["detalle"]
                ]
            }
            for nombre, r in res.items()
        }
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

    print()
    print("Guardado en resultado_calibracion_v2.json")
