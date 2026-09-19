"""
correr_calibracion.py — Ejecuta la calibracion del criterio "3 de 5" a varios
niveles de efecto (ruido puro + 3 niveles), y con dos minimos de episodios
independientes en bloque_2 (2 relajado / 8 real de v2.json), para poder
atribuir si la escasez de muestra viene de bloque_2 o es propia del forward.
"""
import sys, json, time
sys.path.insert(0, '.')
import numpy as np
import simulacion_3de5 as sim3

NIVELES = {
    "ruido_puro": 0.0,
    "efecto_bajo": 0.042,
    "efecto_medio": 0.084,
    "efecto_alto": 0.168,
}

N_REPLICAS = 300  # por nivel; reducido respecto a 6a (600) por coste de tiempo
                   # de la ejecucion combinada (2 escenarios de eps_min x 4 niveles)

def correr(eps_min_b2, n_replicas, semilla_base):
    resultados = {}
    for nombre, theta in NIVELES.items():
        supervivientes = []
        n_insuficientes = 0
        t0 = time.time()
        for i in range(n_replicas):
            semilla = semilla_base + i
            # monkeypatch del eps_min de bloque_2 dentro del modulo de simulacion
            r = sim3.procesar_replica.__wrapped__(semilla, theta) if hasattr(sim3.procesar_replica, '__wrapped__') else None
            # (no hay wrapper; se llama a una version parametrizada mas abajo)
            r = _procesar_con_eps_min(semilla, theta, eps_min_b2)
            if r is None:
                n_insuficientes += 1
            else:
                supervivientes.append(r)
        dt = time.time() - t0
        resultados[nombre] = {
            "theta_nominal": theta,
            "n_replicas": n_replicas,
            "n_supervivientes": len(supervivientes),
            "n_insuficientes_o_rechazados": n_insuficientes,
            "tasa_supervivencia": len(supervivientes) / n_replicas,
            "detalle": supervivientes,
            "tiempo_seg": round(dt, 1),
        }
        print(f"  [eps_min={eps_min_b2}] {nombre}: {len(supervivientes)}/{n_replicas} sobreviven "
              f"({100*len(supervivientes)/n_replicas:.1f}%) — {dt:.1f}s")
    return resultados


def _procesar_con_eps_min(semilla, theta_nominal, eps_min_b2, signo_esperado="positivo"):
    """Copia de procesar_replica pero con eps_min de bloque_2 parametrizable."""
    import pandas as pd
    import motor
    import generador as gen

    n_historico = 800
    d = gen.generar_replica(
        semilla=semilla, n_historico=n_historico,
        n_forward_dias=sim3.N_TRIMESTRES * sim3.DIAS_TRIMESTRE,
        theta_nominal=theta_nominal,
    )
    idx_hist = d["fechas"][:n_historico]
    mitad = n_historico // 2
    b1 = idx_hist[:mitad]
    b2 = idx_hist[mitad:]
    mask = d["mask"]; ret = d["ret"]; precio = d["precio"]

    m1 = mask.loc[b1]
    tramos = motor.tramos_de(b1, sim3.N_TRAMOS_GATE1)
    try:
        g1 = motor.gate1(m1, ret, tramos, N=sim3.N, semilla=sim3.SEMILLA_ROTACION,
                          n_rotaciones=sim3.N_ROTACIONES, percentil=sim3.PERCENTIL_ROTACION,
                          min_obs_tramo=sim3.MIN_OBS_TRAMO)
    except RuntimeError:
        # mismo caso que filtro.py aborta (nulo por rotacion no evaluable,
        # tipicamente mascara sin variacion en algun tramo): se cuenta como
        # no superviviente, no como error de la simulacion.
        return None
    if g1.get("no_evaluable") or g1["insuficiencia"] or not g1["pasa"]:
        return None

    base = pd.DataFrame({
        "mayer": precio / precio.rolling(200).mean(),
        "vol30": precio.pct_change().rolling(30).std(),
        "mom30": precio / precio.shift(30) - 1,
    })
    try:
        g3 = motor.gate3(m1, ret, base, N=sim3.N, semilla=sim3.SEMILLA_ROTACION,
                          n_rotaciones=sim3.N_ROTACIONES, percentil=sim3.PERCENTIL_ROTACION,
                          minimo=sim3.MIN_OBS_GATE3)
    except RuntimeError:
        return None
    if g3["insuficiencia"] or not g3["pasa"]:
        return None

    g4 = motor.gate4(g1["correlaciones_por_tramo"])
    if not g4["pasa"]:
        return None

    m2 = mask.loc[b2]
    perm = motor.test_permutacion(
        m2, ret, signo_esperado, dias_ep=sim3.DIAS_EPISODIO,
        obs_min=sim3.OBS_MASCARADAS_MIN, eps_min=eps_min_b2,
        n_permutaciones=sim3.N_PERMUTACIONES, semilla=sim3.SEMILLA_PERMUTACION,
    )
    if perm["insuficiencia"]:
        return None

    theta_B2 = perm["theta_B2"]

    fecha_inicio_fwd = d["fecha_corte_forward"]
    fechas_fwd = d["fechas"][d["fechas"] > fecha_inicio_fwd]
    fechas_fwd = fechas_fwd[:sim3.N_TRIMESTRES * sim3.DIAS_TRIMESTRE]

    thetas_trimestre = []
    for q in range(sim3.N_TRIMESTRES):
        ini = q * sim3.DIAS_TRIMESTRE
        fin = ini + sim3.DIAS_TRIMESTRE
        idx_q = fechas_fwd[ini:fin]
        if len(idx_q) == 0:
            thetas_trimestre.append(float("nan"))
            continue
        thetas_trimestre.append(sim3._theta_trimestre(mask.loc[idx_q], ret.loc[idx_q]))

    theta_F = sim3._theta_trimestre(mask.loc[fechas_fwd], ret.loc[fechas_fwd])

    signo_B2 = np.sign(theta_B2)
    signo_F = np.sign(theta_F) if np.isfinite(theta_F) else 0
    c_signo = bool(np.isfinite(theta_F) and signo_F == signo_B2 and signo_F != 0)
    c_magnitud = bool(np.isfinite(theta_F) and abs(theta_F) >= max(0.5 * abs(theta_B2), sim3.M_ABSOLUTO))
    signo_esperado_q = np.sign(theta_B2)
    aciertos = sum(1 for t in thetas_trimestre if np.isfinite(t) and np.sign(t) == signo_esperado_q and np.sign(t) != 0)
    c_consistencia = aciertos >= 3
    autoriza = c_signo and c_magnitud and c_consistencia

    return {
        "theta_B2": theta_B2, "theta_F": theta_F, "thetas_trimestre": thetas_trimestre,
        "aciertos_trimestre": aciertos,
        "c_signo": c_signo, "c_magnitud": c_magnitud, "c_consistencia": c_consistencia,
        "autoriza": autoriza,
    }


if __name__ == "__main__":
    print("=== CALIBRACION eps_min_b2 = 2 (relajado) ===")
    res_relajado = correr(eps_min_b2=2, n_replicas=N_REPLICAS, semilla_base=10000)
    print()
    print("=== CALIBRACION eps_min_b2 = 8 (real de v2.json) ===")
    res_real = correr(eps_min_b2=8, n_replicas=N_REPLICAS, semilla_base=10000)

    def resumen(res):
        out = {}
        for nombre, r in res.items():
            det = r["detalle"]
            if det:
                autoriza_pct = 100 * sum(d["autoriza"] for d in det) / len(det)
                c_signo_pct = 100 * sum(d["c_signo"] for d in det) / len(det)
                c_mag_pct = 100 * sum(d["c_magnitud"] for d in det) / len(det)
                c_cons_pct = 100 * sum(d["c_consistencia"] for d in det) / len(det)
            else:
                autoriza_pct = c_signo_pct = c_mag_pct = c_cons_pct = None
            out[nombre] = {
                "n_supervivientes_a_forward": len(det),
                "tasa_supervivencia_bloque2": r["tasa_supervivencia"],
                "P_autoriza_los_3_criterios": autoriza_pct,
                "P_pasa_signo_agregado": c_signo_pct,
                "P_pasa_magnitud": c_mag_pct,
                "P_pasa_consistencia_minima_3de5": c_cons_pct,
            }
        return out

    resumen_relajado = resumen(res_relajado)
    resumen_real = resumen(res_real)

    with open("resultado_calibracion.json", "w", encoding="utf-8") as f:
        json.dump({"eps_min_2": resumen_relajado, "eps_min_8": resumen_real}, f, indent=2, ensure_ascii=False)

    print()
    print("=== RESUMEN eps_min=2 ===")
    print(json.dumps(resumen_relajado, indent=2, ensure_ascii=False))
    print()
    print("=== RESUMEN eps_min=8 ===")
    print(json.dumps(resumen_real, indent=2, ensure_ascii=False))
