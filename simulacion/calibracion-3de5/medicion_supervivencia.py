"""
medicion_supervivencia.py — Mide, para las replicas que llegan a
EN_CONFIRMACION (superan gates + permutacion + Benjamini-Yekutieli),
que fraccion acaba CONFIRMADA / RECHAZADA_FORWARD / PENDIENTE_REVISION
en el forward de 5 trimestres.

NO reimplementa logica de pipeline_end_to_end.py: reutiliza sus mismas
funciones procesar_replica(), aplicar_by() y forward_de_replica() tal
cual estan en el motor ya validado (sha256 04e5a9cc606d35957ea01dc1d47
35cb93fba0c17f77a4ec6d1679bebbabd66d), solo cambia que registra
'veredicto_consistencia' ademas de 'autoriza' para poder separar
RECHAZADA_FORWARD de PENDIENTE_REVISION (pipeline_end_to_end.py solo
mira el booleano final 'autoriza').

NO escribe nada en v2.json, filtro.py ni registro.json.
"""
import sys, json, time
sys.path.insert(0, '.')
import numpy as np

import pipeline_end_to_end as pe

NIVELES = pe.NIVELES
ESCENARIOS_PHI = pe.ESCENARIOS_PHI


def wilson_ic95(k, n):
    """IC95% de Wilson para una proporcion k/n."""
    if n == 0:
        return (None, None)
    from scipy.stats import norm
    z = norm.ppf(0.975)
    phat = k / n
    denom = 1 + z**2 / n
    centro = phat + z**2 / (2 * n)
    margen = z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    return ((centro - margen) / denom, (centro + margen) / denom)


def correr_nivel_con_desglose(nombre_nivel, theta, n_replicas, semilla_base, phi, lote_n=12):
    """
    Identico en generacion de datos a pe.correr_un_nivel, pero clasifica
    cada EN_CONFIRMACION en 3 categorias en vez de solo autoriza/no.
    """
    t0 = time.time()
    crudos = []
    for i in range(n_replicas):
        semilla = semilla_base + i
        r = pe.procesar_replica(semilla, theta, phi)
        crudos.append(r)

    con_pvalor = [r for r in crudos if r["etapa_alcanzada"] == "con_pvalor"]

    en_confirmacion = []  # las que superan BY -> llegan a EN_CONFIRMACION
    for ini in range(0, len(con_pvalor), lote_n):
        lote = con_pvalor[ini:ini + lote_n]
        if not lote:
            continue
        idx_aceptados = pe.aplicar_by(lote)
        for idx in idx_aceptados:
            en_confirmacion.append(lote[idx])

    n_en_confirmacion = len(en_confirmacion)
    n_confirmada = 0
    n_rechazada = 0
    n_pendiente = 0
    detalle = []

    theta_b2_confirmada = []
    theta_b2_rechazada = []
    theta_b2_pendiente = []

    for r in en_confirmacion:
        fwd = pe.forward_de_replica(r)
        veredicto_cons = fwd["veredicto_consistencia"]  # CUMPLE | NO_CUMPLE | SIN_VEREDICTO
        autoriza = fwd["autoriza"]

        if veredicto_cons == "SIN_VEREDICTO":
            categoria = "PENDIENTE_REVISION"
            n_pendiente += 1
            theta_b2_pendiente.append(r["theta_B2"])
        elif autoriza:
            categoria = "CONFIRMADA"
            n_confirmada += 1
            theta_b2_confirmada.append(r["theta_B2"])
        else:
            categoria = "RECHAZADA_FORWARD"
            n_rechazada += 1
            theta_b2_rechazada.append(r["theta_B2"])

        detalle.append({
            "semilla": r["semilla"], "theta_B2": r["theta_B2"], "p_valor": r["p_valor"],
            "episodios_b2": r["episodios_b2"], "theta_F": fwd["theta_F"],
            "c_signo": fwd["c_signo"], "c_magnitud": fwd["c_magnitud"],
            "veredicto_consistencia": veredicto_cons, "categoria": categoria,
        })

    ic_confirmada = wilson_ic95(n_confirmada, n_en_confirmacion) if n_en_confirmacion else (None, None)
    ic_rechazada = wilson_ic95(n_rechazada, n_en_confirmacion) if n_en_confirmacion else (None, None)
    ic_pendiente = wilson_ic95(n_pendiente, n_en_confirmacion) if n_en_confirmacion else (None, None)

    dt = time.time() - t0
    resultado = {
        "theta_nominal": theta,
        "n_replicas_totales": n_replicas,
        "n_en_confirmacion": n_en_confirmacion,
        "n_confirmada": n_confirmada,
        "n_rechazada_forward": n_rechazada,
        "n_pendiente_revision": n_pendiente,
        "tasa_confirmada": (n_confirmada / n_en_confirmacion) if n_en_confirmacion else None,
        "ic95_confirmada": ic_confirmada,
        "tasa_rechazada_forward": (n_rechazada / n_en_confirmacion) if n_en_confirmacion else None,
        "ic95_rechazada_forward": ic_rechazada,
        "tasa_pendiente_revision": (n_pendiente / n_en_confirmacion) if n_en_confirmacion else None,
        "ic95_pendiente_revision": ic_pendiente,
        "theta_b2_mediana_confirmada": float(np.median(theta_b2_confirmada)) if theta_b2_confirmada else None,
        "theta_b2_mediana_rechazada": float(np.median(theta_b2_rechazada)) if theta_b2_rechazada else None,
        "theta_b2_mediana_pendiente": float(np.median(theta_b2_pendiente)) if theta_b2_pendiente else None,
        "tiempo_seg": round(dt, 1),
        "detalle": detalle,
    }
    print(f"  [{nombre_nivel}, phi={phi}] EN_CONFIRMACION={n_en_confirmacion} de {n_replicas} replicas | "
          f"CONFIRMADA={n_confirmada} RECHAZADA={n_rechazada} PENDIENTE={n_pendiente} — {dt:.1f}s")
    return pe.limpiar(resultado)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--semilla_base", type=int, default=70000)
    ap.add_argument("--out", type=str, default="resultado_supervivencia.json")
    ap.add_argument("--escenario", type=str, default=None, help="uniforme|concentrado; None=ambos")
    ap.add_argument("--nivel", type=str, default=None, help="ruido_puro|efecto_bajo|efecto_medio|efecto_alto; None=todos")
    args = ap.parse_args()

    print(f"n_historico usado: {pe.gen.generar_replica.__defaults__[0]}")
    print(f"eps_min_b2 = {pe.EPISODIOS_MIN_B2} (real de v2.json)")
    print(f"q_nominal BY = {pe.Q_NOMINAL_BY}, lote_n=12")
    print()

    escenarios = {args.escenario: ESCENARIOS_PHI[args.escenario]} if args.escenario else ESCENARIOS_PHI
    niveles = {args.nivel: NIVELES[args.nivel]} if args.nivel else NIVELES

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
            todo[escenario][nombre_nivel] = correr_nivel_con_desglose(
                nombre_nivel, theta, n_replicas=args.n,
                semilla_base=semilla_base_esc, phi=phi,
            )
        print()

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(todo, f, indent=2, ensure_ascii=False, default=str)
    print(f"Guardado en {args.out}")
