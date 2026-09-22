"""
pipeline_end_to_end.py — Remedicion de potencia end-to-end del pipeline
COMPLETO de 6 etapas (gates 1/3/4 -> permutacion -> Benjamini-Yekutieli ->
confirmacion forward), con el generador CORREGIDO (n_historico=4260,
calentamiento de mascara, eps_min=8 real, consistencia_minima enmienda 43).

Reutiliza sin modificar:
  - motor.py       (copia validada linea a linea + numericamente de filtro.py)
  - generador.py   (corregido, ya subido al repo en simulacion/calibracion-3de5/)
  - prueba_consistencia.py (implementacion oficial de la enmienda 43)

Anade sobre lo ya hecho en calibracion_v2.py (que mide una sola variable
aislada):
  1. Etapa test_permutacion devuelve p-valor explicito -> se agrega en LOTES
     sinteticos de tamano LOTE_N para aplicar Benjamini-Yekutieli tal como
     opera realmente en el pipeline (q_nominal=0.2, m=max(3, p-valores del
     lote), ver v2.json protocolo.correccion_multiple).
  2. Registra el THETA REALIZADO (theta_B2 medido, no el nominal inyectado)
     en cada replica que llega a bloque_2.
  3. Reporta potencia/FP por etapa individual Y end-to-end (con y sin BY),
     para escenario uniforme (la mascara Q80/365d de referencia, igual que
     en calibracion_v2.py) y escenario concentrado (mismo generador pero con
     una mascara mas persistente, phi mas alto, que concentra activaciones
     en menos episodios mas largos -> mismo theta nominal, MENOS episodios
     independientes contribuyendo).

NO se escribe nada en v2.json, filtro.py ni registro.json. Esto es
medicion, no propuesta ni implementacion.
"""
import sys, json, time
sys.path.insert(0, '.')
import numpy as np
import pandas as pd

import motor
import generador as gen
from prueba_consistencia import consistencia_minima

# ---------------------------------------------------------------------
# Parametros identicos a calibracion_v2.py (ya validado), sin modificar
# ---------------------------------------------------------------------
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
EPISODIOS_MIN_B2 = 8  # eps_min REAL de v2.json, sin relajar
N_PERMUTACIONES = 2000
SEMILLA_PERMUTACION = 0

Q_NOMINAL_BY = 0.2  # protocolo.correccion_multiple.q_nominal en v2.json

NIVELES = {
    "ruido_puro": 0.0,
    "efecto_bajo": 0.042,
    "efecto_medio": 0.084,
    "efecto_alto": 0.168,
}

# phi de la metrica AR(1): "uniforme" usa la de referencia ya validada
# (0.985, la misma de calibracion_v2.py). "concentrado" sube la persistencia
# para que las activaciones se agrupen en episodios mas largos y escasos con
# el MISMO mecanismo de mascara (Q80/365d) y el MISMO theta nominal —
# variando unicamente la estructura temporal del efecto, no su magnitud.
ESCENARIOS_PHI = {
    "uniforme": 0.985,
    "concentrado": 0.997,
}


def _theta_trimestre(mask_tr, ret_tr):
    z = pd.DataFrame({"m": mask_tr, "r": ret_tr}).dropna()
    if z["m"].sum() == 0 or (~z["m"]).sum() == 0:
        return float("nan")
    return float(z[z["m"]]["r"].median() - z[~z["m"]]["r"].median())


def procesar_replica(semilla, theta_nominal, phi, signo_esperado="positivo"):
    """
    Ejecuta gates 1/3/4 -> permutacion sobre UNA replica sintetica.
    Devuelve un dict con el resultado de cada etapa (para poder reportar
    potencia por etapa), independientemente de si sobrevive o no.
    etapa alcanzada: 'gate1' | 'gate3' | 'gate4' | 'permutacion' | 'con_pvalor'
    """
    n_historico = gen.generar_replica.__defaults__[0]  # 4260
    d = gen.generar_replica(
        semilla=semilla, n_historico=n_historico,
        n_forward_dias=N_TRIMESTRES * DIAS_TRIMESTRE,
        theta_nominal=theta_nominal, phi=phi,
    )
    idx_hist = d["fechas"][:n_historico]
    mitad = n_historico // 2
    b1 = idx_hist[:mitad]
    b2 = idx_hist[mitad:]
    mask = d["mask"]; ret = d["ret"]; precio = d["precio"]

    resultado = {"semilla": semilla, "theta_nominal": theta_nominal, "phi": phi,
                 "etapa_alcanzada": None, "theta_B2": None, "p_valor": None,
                 "episodios_b2": None}

    m1 = mask.loc[b1]
    tramos = motor.tramos_de(b1, N_TRAMOS_GATE1)
    try:
        g1 = motor.gate1(m1, ret, tramos, N=N, semilla=SEMILLA_ROTACION,
                          n_rotaciones=N_ROTACIONES, percentil=PERCENTIL_ROTACION,
                          min_obs_tramo=MIN_OBS_TRAMO)
    except RuntimeError:
        resultado["etapa_alcanzada"] = "gate1_error_rotacion"
        return resultado
    if g1.get("no_evaluable") or g1["insuficiencia"] or not g1["pasa"]:
        resultado["etapa_alcanzada"] = "gate1"
        return resultado

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
        resultado["etapa_alcanzada"] = "gate3_error_rotacion"
        return resultado
    if g3["insuficiencia"] or not g3["pasa"]:
        resultado["etapa_alcanzada"] = "gate3"
        return resultado

    g4 = motor.gate4(g1["correlaciones_por_tramo"])
    if not g4["pasa"]:
        resultado["etapa_alcanzada"] = "gate4"
        return resultado

    m2 = mask.loc[b2]
    perm = motor.test_permutacion(
        m2, ret, signo_esperado, dias_ep=DIAS_EPISODIO,
        obs_min=OBS_MASCARADAS_MIN, eps_min=EPISODIOS_MIN_B2,
        n_permutaciones=N_PERMUTACIONES, semilla=SEMILLA_PERMUTACION,
    )
    if perm["insuficiencia"]:
        resultado["etapa_alcanzada"] = "permutacion_insuficiencia"
        return resultado

    resultado["etapa_alcanzada"] = "con_pvalor"
    resultado["theta_B2"] = perm["theta_B2"]
    resultado["p_valor"] = perm["p_valor"]
    resultado["episodios_b2"] = perm["episodios"]
    resultado["_d"] = d  # se guarda para forward solo si hace falta luego
    resultado["_idx_hist_n"] = n_historico
    resultado["_signo_esperado"] = signo_esperado
    return resultado


def forward_de_replica(resultado):
    """
    Dado un resultado con 'con_pvalor' y que ademas sobrevivio a BY, calcula
    la confirmacion forward completa (signo, magnitud, consistencia_minima).
    """
    d = resultado["_d"]
    mask = d["mask"]; ret = d["ret"]
    theta_B2 = resultado["theta_B2"]

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
    trimestres_signo = [
        (None if not np.isfinite(t) else (1 if t > 0 else (-1 if t < 0 else 0)))
        for t in thetas_trimestre
    ]
    veredicto_cons, n_def, n_indef, a_favor = consistencia_minima(trimestres_signo, signo_esperado_q)
    c_consistencia = (veredicto_cons == "CUMPLE")

    autoriza = c_signo and c_magnitud and c_consistencia
    return {
        "theta_F": theta_F, "c_signo": c_signo, "c_magnitud": c_magnitud,
        "veredicto_consistencia": veredicto_cons, "c_consistencia": c_consistencia,
        "autoriza": autoriza,
    }


def aplicar_by(items_con_pvalor):
    """
    items_con_pvalor: lista de dicts con 'p_valor' (todas las candidatas del
    LOTE que llegaron a producir p-valor en bloque_2; las que murieron antes
    en gates NO cuentan para m, segun v2.json m_efectivo.no_cuentan).
    Devuelve el subconjunto (por indice de la lista) que sobrevive BY.
    """
    pvals = {i: it["p_valor"] for i, it in enumerate(items_con_pvalor)}
    aceptados = motor.benjamini_yekutieli(pvals, Q_NOMINAL_BY)
    return aceptados


def correr_escenario(n_replicas, semilla_base, phi, lote_n=12):
    """
    Genera n_replicas POR NIVEL de theta_nominal, agrupadas en lotes
    sinteticos de tamano lote_n para poder aplicar BY tal como opera en el
    pipeline real (BY actua sobre el lote, no variable a variable).
    Cada replica del lote tiene el MISMO theta_nominal (todas las variables
    de un lote comparten el escenario que se esta midiendo); esto es una
    simplificacion declarada: en la practica un lote real mezcla variables
    con distinta señal real, pero medir potencia/FP requiere escenarios
    homogeneos por theta para poder atribuir el resultado.
    """
    resultados_nivel = {}
    for nombre, theta in NIVELES.items():
        t0 = time.time()
        crudos = []
        for i in range(n_replicas):
            semilla = semilla_base + i
            r = procesar_replica(semilla, theta, phi)
            crudos.append(r)

        # --- potencia/FP por etapa individual (sobre TODAS las replicas) ---
        n_total = len(crudos)
        etapas_alcanzadas = [r["etapa_alcanzada"] for r in crudos]
        n_pasa_gate1 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion"))
        n_pasa_gate3 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion", "gate3", "gate3_error_rotacion"))
        n_pasa_gate4 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion", "gate3", "gate3_error_rotacion", "gate4"))
        n_con_pvalor = sum(1 for e in etapas_alcanzadas if e == "con_pvalor")

        # --- agrupar en lotes sinteticos para BY ---
        con_pvalor = [r for r in crudos if r["etapa_alcanzada"] == "con_pvalor"]
        aceptados_by_total = 0
        forward_autoriza = 0
        forward_evaluados = 0
        thetas_b2_realizados = []
        thetas_f_realizados = []
        detalle_forward = []

        for ini in range(0, len(con_pvalor), lote_n):
            lote = con_pvalor[ini:ini + lote_n]
            if not lote:
                continue
            idx_aceptados = aplicar_by(lote)
            aceptados_by_total += len(idx_aceptados)
            for idx in idx_aceptados:
                r = lote[idx]
                thetas_b2_realizados.append(r["theta_B2"])
                fwd = forward_de_replica(r)
                thetas_f_realizados.append(fwd["theta_F"])
                forward_evaluados += 1
                if fwd["autoriza"]:
                    forward_autoriza += 1
                detalle_forward.append({
                    "semilla": r["semilla"], "theta_B2": r["theta_B2"],
                    "p_valor": r["p_valor"], "episodios_b2": r["episodios_b2"],
                    **fwd,
                })

        dt = time.time() - t0
        resultados_nivel[nombre] = {
            "theta_nominal": theta,
            "n_replicas": n_total,
            "n_pasa_gate1": n_pasa_gate1,
            "n_pasa_gate3": n_pasa_gate3,
            "n_pasa_gate4": n_pasa_gate4,
            "n_con_pvalor": n_con_pvalor,
            "n_aceptados_by": aceptados_by_total,
            "n_autoriza_forward": forward_autoriza,
            "tasa_pasa_gate1": n_pasa_gate1 / n_total,
            "tasa_pasa_gate3_dado_gate1": (n_pasa_gate3 / n_pasa_gate1) if n_pasa_gate1 else None,
            "tasa_pasa_gate4_dado_gate3": (n_pasa_gate4 / n_pasa_gate3) if n_pasa_gate3 else None,
            "tasa_con_pvalor_dado_gate4": (n_con_pvalor / n_pasa_gate4) if n_pasa_gate4 else None,
            "tasa_by_dado_pvalor": (aceptados_by_total / n_con_pvalor) if n_con_pvalor else None,
            "tasa_forward_dado_by": (forward_autoriza / aceptados_by_total) if aceptados_by_total else None,
            "end_to_end_gates_perm": n_con_pvalor / n_total,
            "end_to_end_con_by": aceptados_by_total / n_total,
            "end_to_end_completo": forward_autoriza / n_total,
            "theta_b2_realizado_mediana": float(np.median(thetas_b2_realizados)) if thetas_b2_realizados else None,
            "theta_b2_realizado_media": float(np.mean(thetas_b2_realizados)) if thetas_b2_realizados else None,
            "theta_f_realizado_mediana": float(np.nanmedian(thetas_f_realizados)) if thetas_f_realizados else None,
            "tiempo_seg": round(dt, 1),
            "detalle_forward": detalle_forward,
        }
        print(f"  [{nombre}, phi={phi}] n={n_total} | gate1={n_pasa_gate1} gate3={n_pasa_gate3} "
              f"gate4={n_pasa_gate4} p-valor={n_con_pvalor} BY={aceptados_by_total} "
              f"forward_OK={forward_autoriza} | e2e_completo={100*forward_autoriza/n_total:.2f}% "
              f"e2e_gates+perm={100*n_con_pvalor/n_total:.2f}% — {dt:.1f}s")
    return resultados_nivel


def limpiar(obj):
    if isinstance(obj, dict):
        return {k: limpiar(v) for k, v in obj.items() if k not in ("_d",)}
    if isinstance(obj, list):
        return [limpiar(x) for x in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def correr_un_nivel(nombre_nivel, theta, n_replicas, semilla_base, phi, lote_n=12):
    """Version de correr_escenario para UN SOLO nivel, para poder trocear
    la ejecucion en llamadas cortas independientes."""
    t0 = time.time()
    crudos = []
    for i in range(n_replicas):
        semilla = semilla_base + i
        r = procesar_replica(semilla, theta, phi)
        crudos.append(r)

    n_total = len(crudos)
    etapas_alcanzadas = [r["etapa_alcanzada"] for r in crudos]
    n_pasa_gate1 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion"))
    n_pasa_gate3 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion", "gate3", "gate3_error_rotacion"))
    n_pasa_gate4 = sum(1 for e in etapas_alcanzadas if e not in ("gate1", "gate1_error_rotacion", "gate3", "gate3_error_rotacion", "gate4"))
    n_con_pvalor = sum(1 for e in etapas_alcanzadas if e == "con_pvalor")

    con_pvalor = [r for r in crudos if r["etapa_alcanzada"] == "con_pvalor"]
    aceptados_by_total = 0
    forward_autoriza = 0
    forward_evaluados = 0
    thetas_b2_realizados = []
    thetas_f_realizados = []
    detalle_forward = []

    for ini in range(0, len(con_pvalor), lote_n):
        lote = con_pvalor[ini:ini + lote_n]
        if not lote:
            continue
        idx_aceptados = aplicar_by(lote)
        aceptados_by_total += len(idx_aceptados)
        for idx in idx_aceptados:
            r = lote[idx]
            thetas_b2_realizados.append(r["theta_B2"])
            fwd = forward_de_replica(r)
            thetas_f_realizados.append(fwd["theta_F"])
            forward_evaluados += 1
            if fwd["autoriza"]:
                forward_autoriza += 1
            detalle_forward.append({
                "semilla": r["semilla"], "theta_B2": r["theta_B2"],
                "p_valor": r["p_valor"], "episodios_b2": r["episodios_b2"],
                **fwd,
            })

    dt = time.time() - t0
    resultado = {
        "theta_nominal": theta,
        "n_replicas": n_total,
        "n_pasa_gate1": n_pasa_gate1,
        "n_pasa_gate3": n_pasa_gate3,
        "n_pasa_gate4": n_pasa_gate4,
        "n_con_pvalor": n_con_pvalor,
        "n_aceptados_by": aceptados_by_total,
        "n_autoriza_forward": forward_autoriza,
        "tasa_pasa_gate1": n_pasa_gate1 / n_total,
        "tasa_pasa_gate3_dado_gate1": (n_pasa_gate3 / n_pasa_gate1) if n_pasa_gate1 else None,
        "tasa_pasa_gate4_dado_gate3": (n_pasa_gate4 / n_pasa_gate3) if n_pasa_gate3 else None,
        "tasa_con_pvalor_dado_gate4": (n_con_pvalor / n_pasa_gate4) if n_pasa_gate4 else None,
        "tasa_by_dado_pvalor": (aceptados_by_total / n_con_pvalor) if n_con_pvalor else None,
        "tasa_forward_dado_by": (forward_autoriza / aceptados_by_total) if aceptados_by_total else None,
        "end_to_end_gates_perm": n_con_pvalor / n_total,
        "end_to_end_con_by": aceptados_by_total / n_total,
        "end_to_end_completo": forward_autoriza / n_total,
        "theta_b2_realizado_mediana": float(np.median(thetas_b2_realizados)) if thetas_b2_realizados else None,
        "theta_b2_realizado_media": float(np.mean(thetas_b2_realizados)) if thetas_b2_realizados else None,
        "theta_f_realizado_mediana": float(np.nanmedian(thetas_f_realizados)) if thetas_f_realizados else None,
        "tiempo_seg": round(dt, 1),
        "detalle_forward": detalle_forward,
    }
    print(f"  [{nombre_nivel}, phi={phi}] n={n_total} | gate1={n_pasa_gate1} gate3={n_pasa_gate3} "
          f"gate4={n_pasa_gate4} p-valor={n_con_pvalor} BY={aceptados_by_total} "
          f"forward_OK={forward_autoriza} | e2e_completo={100*forward_autoriza/n_total:.2f}% "
          f"e2e_gates+perm={100*n_con_pvalor/n_total:.2f}% — {dt:.1f}s")
    return limpiar(resultado)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--semilla_base", type=int, default=50000)
    ap.add_argument("--out", type=str, default="resultado_end_to_end.json")
    ap.add_argument("--escenario", type=str, default=None, help="uniforme|concentrado; None=ambos")
    ap.add_argument("--nivel", type=str, default=None, help="ruido_puro|efecto_bajo|efecto_medio|efecto_alto; None=todos")
    args = ap.parse_args()

    print(f"n_historico usado: {gen.generar_replica.__defaults__[0]}")
    print(f"eps_min_b2 = {EPISODIOS_MIN_B2} (real de v2.json)")
    print(f"q_nominal BY = {Q_NOMINAL_BY}, lote_n=12")
    print()

    escenarios = {args.escenario: ESCENARIOS_PHI[args.escenario]} if args.escenario else ESCENARIOS_PHI
    niveles = {args.nivel: NIVELES[args.nivel]} if args.nivel else NIVELES

    # cargar resultado previo si existe, para ir acumulando por trozos
    try:
        with open(args.out, "r", encoding="utf-8") as f:
            todo = json.load(f)
    except FileNotFoundError:
        todo = {}

    for escenario, phi in escenarios.items():
        print(f"=== ESCENARIO {escenario.upper()} (phi={phi}) ===")
        todo.setdefault(escenario, {})
        semilla_base_esc = args.semilla_base + (0 if escenario == "uniforme" else 1_000_000)
        for nombre_nivel, theta in niveles.items():
            todo[escenario][nombre_nivel] = correr_un_nivel(
                nombre_nivel, theta, n_replicas=args.n,
                semilla_base=semilla_base_esc, phi=phi,
            )
        print()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(todo, f, indent=2, ensure_ascii=False, default=str)
    print(f"Guardado en {args.out}")
