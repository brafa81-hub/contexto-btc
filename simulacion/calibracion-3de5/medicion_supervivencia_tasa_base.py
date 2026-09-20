"""
medicion_supervivencia_tasa_base.py — Remide P(CONFIRMADA | theta_B2) con
una tasa base REALISTA, y la expresa como funcion continua en vez de
terciles.

PROBLEMA QUE CORRIGE
--------------------
La medicion anterior (medicion_supervivencia.py) uso una mezcla sintetica
de 400 replicas por nivel, es decir una proporcion ~1/3-1/3-1/3 entre los
tres niveles con efecto. Consulta externa a 6 IAs (unanime): esas cifras
(91-94% en el tercio alto, cortes en theta_B2 = 0,098 y 0,161) NO son
transportables a variables reales, porque en produccion la inmensa mayoria
de las candidatas son ruido y las de efecto alto son rarisimas. La relacion
direccional (mas theta_B2 -> mas probabilidad de confirmar) sigue valiendo;
lo que no vale es la cifra exacta ni los puntos de corte.

METODO
------
1. NO se regeneran replicas por mezcla. La composicion de la mezcla no
   cambia como se genera cada replica: cada nivel se simula independiente.
   La mezcla solo cambia el PESO con el que cada replica entra en el ajuste
   final. Por eso se reutilizan las replicas ya medidas y se reponderan.
   Esto es exacto, no una aproximacion, y evita simular millones de
   replicas de ruido que por definicion nunca llegan a EN_CONFIRMACION.

2. Peso de cada replica del nivel L bajo la mezcla M:
       w_L = prevalencia_M(L) / n_replicas_medidas(L)
   Todas las replicas de un mismo nivel pesan igual entre si. El peso
   relativo entre niveles reproduce exactamente la composicion que tendria
   la muestra de EN_CONFIRMACION bajo esa tasa base, porque la tasa de
   llegada de cada nivel ya esta incorporada de forma natural: de cada
   nivel solo entran en el ajuste las replicas que de hecho llegaron.

3. Ajuste de una funcion continua P(CONFIRMADA | theta_B2) por REGRESION
   LOGISTICA PONDERADA. Se elige logistica y no isotonica porque:
     - la muestra util es de orden 10^2, no 10^4: la isotonica sobreajusta
       con pocos datos y produce escalones planos que reintroducen
       exactamente el problema de "acantilado" que se queria evitar;
     - la logistica impone monotonia suave, que es justo la forma que la
       teoria predice y que la medicion previa ya mostro direccionalmente;
     - permite calcular un limite inferior de confianza continuo.
   Se reporta tambien un ajuste isotonico como contraste visual/numerico,
   no como resultado principal.

4. Limite inferior de confianza al 95% de la curva, por bootstrap de
   replicas ponderado (varias IAs externas recomendaron no operar con el
   punto central estimado sino con un limite conservador).

5. Todo para los dos escenarios ya usados: uniforme (phi=0,985) y
   concentrado (phi=0,997).

QUE ES DATO Y QUE ES SUPUESTO
-----------------------------
- DATO MEDIDO: la tasa de llegada a EN_CONFIRMACION de cada nivel, el
  theta_B2 realizado de cada replica, y su veredicto CONFIRMADA /
  RECHAZADA_FORWARD / PENDIENTE_REVISION.
- SUPUESTO (NO medido): la prevalencia de cada nivel entre las variables
  candidatas reales, es decir la tasa base. Es una ELECCION doctrinal.
  Por eso se miden TRES mezclas (pesimista / central / optimista) y se
  reporta la sensibilidad del resultado a esa eleccion, en vez de
  comprometerse con una sola cifra inventada.

NO escribe en v2.json, filtro.py ni registro.json. Medicion, no propuesta.
"""
import sys, json, argparse
sys.path.insert(0, '.')
import numpy as np

# ---------------------------------------------------------------------
# Tasas de llegada a EN_CONFIRMACION medidas (resultado_supervivencia.json)
# Se usan solo para documentar la composicion; el reponderado no las
# necesita porque ya estan implicitas en cuantas replicas de cada nivel
# llegaron efectivamente.
# ---------------------------------------------------------------------
TASAS_LLEGADA_MEDIDAS = {
    "uniforme":    {"ruido_puro": 0.0000, "efecto_bajo": 0.0850,
                    "efecto_medio": 0.7950, "efecto_alto": 1.0000},
    "concentrado": {"ruido_puro": 0.0000, "efecto_bajo": 0.0975,
                    "efecto_medio": 0.7400, "efecto_alto": 0.9975},
}

# ---------------------------------------------------------------------
# MEZCLAS DE TASA BASE — SUPUESTO DOCTRINAL, NO DATO MEDIDO
# ---------------------------------------------------------------------
MEZCLAS = {
    # Lo unico que influye en la curva es la composicion RELATIVA de las que
    # LLEGAN a EN_CONFIRMACION, no la prevalencia absoluta de ruido (el ruido
    # puro nunca llega: 0 de 400 medidas). Las tres mezclas se han elegido
    # para que esa composicion relativa sea claramente distinta entre ellas;
    # de lo contrario la "sensibilidad a la mezcla" seria ficticia.
    "pesimista": {"ruido_puro": 0.9700, "efecto_bajo": 0.0280,
                  "efecto_medio": 0.0018, "efecto_alto": 0.0002},
    "central":   {"ruido_puro": 0.9000, "efecto_bajo": 0.0750,
                  "efecto_medio": 0.0210, "efecto_alto": 0.0040},
    "optimista": {"ruido_puro": 0.8000, "efecto_bajo": 0.1200,
                  "efecto_medio": 0.0550, "efecto_alto": 0.0250},
}


def cargar_casos(ruta_base, ruta_ampliacion_unif, ruta_ampliacion_conc):
    """
    Devuelve, por escenario y nivel, la lista de casos que LLEGARON a
    EN_CONFIRMACION, con su theta_B2 y si acabaron CONFIRMADA, mas el
    numero de replicas generadas de ese nivel (denominador del peso).
    """
    with open(ruta_base, "r", encoding="utf-8") as f:
        base = json.load(f)

    ampliaciones = {}
    for ruta in (ruta_ampliacion_unif, ruta_ampliacion_conc):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                ampliaciones.update(json.load(f))
        except FileNotFoundError:
            pass

    datos = {}
    for esc in base:
        datos[esc] = {}
        for niv in base[esc]:
            r = base[esc][niv]
            casos = [{"theta_B2": d["theta_B2"],
                      "confirmada": 1 if d["categoria"] == "CONFIRMADA" else 0,
                      "categoria": d["categoria"]}
                     for d in r.get("detalle", [])]
            n_gen = r["n_replicas_totales"]

            # fusionar ampliacion de efecto_bajo si existe para este escenario
            if niv == "efecto_bajo" and esc in ampliaciones:
                a = ampliaciones[esc]
                casos += [{"theta_B2": d["theta_B2"],
                           "confirmada": 1 if d["categoria"] == "CONFIRMADA" else 0,
                           "categoria": d["categoria"]}
                          for d in a.get("detalle", [])]
                n_gen += a["n_replicas_totales"]

            datos[esc][niv] = {"casos": casos, "n_generadas": n_gen}
    return datos


def pesos_de_mezcla(datos_esc, mezcla):
    """
    Peso de cada replica del nivel L = prevalencia(L) / n_generadas(L).
    Devuelve arrays x (theta_B2), y (confirmada 0/1), w (peso), y la
    composicion resultante de la muestra que llega.
    """
    xs, ys, ws, nivs = [], [], [], []
    for niv, prev in mezcla.items():
        d = datos_esc.get(niv)
        if d is None or not d["casos"] or prev <= 0:
            continue
        w = prev / d["n_generadas"]
        for c in d["casos"]:
            xs.append(c["theta_B2"]); ys.append(c["confirmada"])
            ws.append(w); nivs.append(niv)
    x = np.asarray(xs, float); y = np.asarray(ys, float)
    w = np.asarray(ws, float); nivs = np.asarray(nivs)

    composicion = {}
    if w.sum() > 0:
        for niv in set(nivs.tolist()):
            composicion[niv] = float(w[nivs == niv].sum() / w.sum())
    return x, y, w, nivs, composicion


def logistica_ponderada(x, y, w, iters=200, tol=1e-10, ridge=1e-6):
    """
    Regresion logistica ponderada por IRLS (Newton-Raphson). Sin scikit:
    solo numpy, para no anadir dependencias al proyecto.
    Modelo: P(CONFIRMADA) = 1 / (1 + exp(-(b0 + b1 * theta_B2)))
    ridge minimo para estabilidad numerica si hay separacion casi perfecta.
    """
    X = np.column_stack([np.ones_like(x), x])
    beta = np.zeros(2)
    for _ in range(iters):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(eta, -35, 35)))
        W = w * p * (1 - p)
        W = np.maximum(W, 1e-12)
        z = eta + (y - p) / np.maximum(p * (1 - p), 1e-12)
        XtW = X.T * W
        H = XtW @ X + ridge * np.eye(2)
        b_new = np.linalg.solve(H, XtW @ z)
        if np.max(np.abs(b_new - beta)) < tol:
            beta = b_new
            break
        beta = b_new
    return beta


def predecir(beta, grid):
    eta = beta[0] + beta[1] * grid
    return 1.0 / (1.0 + np.exp(-np.clip(eta, -35, 35)))


def bootstrap_curva(x, y, w, nivs, grid, n_boot=2000, semilla=12345):
    """
    Bootstrap ESTRATIFICADO POR NIVEL: se remuestrea con reemplazo dentro
    de cada nivel, conservando el numero de casos de ese nivel. Asi la
    incertidumbre refleja la del muestreo real, y no se mezcla con la
    incertidumbre sobre la mezcla (que se trata aparte, con 3 escenarios).
    Devuelve percentiles 2.5 / 50 / 97.5 de la curva en cada punto del grid.
    """
    rng = np.random.default_rng(semilla)
    niveles_unicos = sorted(set(nivs.tolist()))
    idx_por_nivel = {nv: np.where(nivs == nv)[0] for nv in niveles_unicos}

    curvas = np.empty((n_boot, len(grid)))
    validas = 0
    for b in range(n_boot):
        sel = []
        for nv in niveles_unicos:
            idx = idx_por_nivel[nv]
            sel.append(rng.choice(idx, size=len(idx), replace=True))
        sel = np.concatenate(sel)
        xb, yb, wb = x[sel], y[sel], w[sel]
        if len(set(yb.tolist())) < 2:
            continue
        try:
            bb = logistica_ponderada(xb, yb, wb)
            curvas[validas] = predecir(bb, grid)
            validas += 1
        except np.linalg.LinAlgError:
            continue
    curvas = curvas[:validas]
    return {
        "n_boot_validas": validas,
        "p025": np.percentile(curvas, 2.5, axis=0),
        "p500": np.percentile(curvas, 50.0, axis=0),
        "p975": np.percentile(curvas, 97.5, axis=0),
    }


def isotonica_ponderada(x, y, w):
    """
    Regresion isotonica ponderada (PAVA), SOLO como contraste. No es el
    resultado principal: con muestra de orden 10^2 produce escalones que
    reintroducen el problema de acantilado.
    """
    orden = np.argsort(x)
    xs, ys, ws = x[orden], y[orden], w[orden]
    val = list(ys.astype(float)); pes = list(ws.astype(float))
    i = 0
    while i < len(val) - 1:
        if val[i] <= val[i + 1] + 1e-15:
            i += 1
            continue
        nw = pes[i] + pes[i + 1]
        nv = (val[i] * pes[i] + val[i + 1] * pes[i + 1]) / nw
        val[i:i + 2] = [nv]; pes[i:i + 2] = [nw]
        i = max(i - 1, 0)
    # reexpandir
    out_x, out_y = [], []
    k = 0
    for v, p in zip(val, pes):
        out_x.append(xs[k]); out_y.append(v)
        k += 1
    return np.asarray(out_x), np.asarray(out_y)


def resumen_composicion(datos_esc, mezcla):
    """Composicion teorica de la muestra que llega, con las tasas medidas."""
    pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="resultado_supervivencia.json")
    ap.add_argument("--amp_unif", default="ampliacion_efecto_bajo.json")
    ap.add_argument("--amp_conc", default="ampliacion_efecto_bajo_conc.json")
    ap.add_argument("--out", default="resultado_tasa_base.json")
    ap.add_argument("--n_boot", type=int, default=2000)
    args = ap.parse_args()

    datos = cargar_casos(args.base, args.amp_unif, args.amp_conc)

    grid = np.round(np.arange(0.00, 0.3001, 0.005), 4)
    salida = {
        "_supuesto_declarado": (
            "Las prevalencias de MEZCLAS son una ELECCION doctrinal, no un dato "
            "medido. No existe medicion de la tasa base real de variables "
            "candidatas en BTC. Los resultados deben leerse como sensibilidad a "
            "esa eleccion, nunca como probabilidad calibrada de una variable real."
        ),
        "_dato_medido": (
            "theta_B2 realizado, veredicto forward por replica, y tasa de llegada "
            "a EN_CONFIRMACION por nivel. Generador AR(1) corregido n_historico=4260, "
            "mascara Q80/365d, motor sha256 04e5a9cc606d35957ea01dc1d4d735cb93fba0c17f77a4ec6d1679bebbabd66d."
        ),
        "mezclas_usadas": MEZCLAS,
        "tasas_llegada_medidas": TASAS_LLEGADA_MEDIDAS,
        "grid_theta_B2": grid.tolist(),
        "escenarios": {},
    }

    for esc in datos:
        salida["escenarios"][esc] = {"mezclas": {}, "n_casos_por_nivel": {
            niv: {"llegaron": len(datos[esc][niv]["casos"]),
                  "generadas": datos[esc][niv]["n_generadas"]}
            for niv in datos[esc]}}

        print(f"\n=== ESCENARIO {esc.upper()} ===")
        for niv in datos[esc]:
            d = datos[esc][niv]
            print(f"  {niv}: {len(d['casos'])} llegaron de {d['n_generadas']} generadas")

        for nombre_mezcla, mezcla in MEZCLAS.items():
            x, y, w, nivs, comp = pesos_de_mezcla(datos[esc], mezcla)
            if len(x) == 0 or len(set(y.tolist())) < 2:
                print(f"  [{nombre_mezcla}] sin datos suficientes")
                continue

            beta = logistica_ponderada(x, y, w)
            curva = predecir(beta, grid)
            boot = bootstrap_curva(x, y, w, nivs, grid, n_boot=args.n_boot)

            # tasa global ponderada (el equivalente al "68-94%" anterior, ya corregido)
            tasa_global = float(np.sum(w * y) / np.sum(w))

            iso_x, iso_y = isotonica_ponderada(x, y, w)

            salida["escenarios"][esc]["mezclas"][nombre_mezcla] = {
                "composicion_de_los_que_llegan": comp,
                "n_casos_efectivos": int(len(x)),
                "tasa_global_confirmada_ponderada": tasa_global,
                "beta0": float(beta[0]), "beta1": float(beta[1]),
                "curva_central": curva.tolist(),
                "curva_limite_inferior95": boot["p025"].tolist(),
                "curva_limite_superior95": boot["p975"].tolist(),
                "curva_mediana_boot": boot["p500"].tolist(),
                "n_boot_validas": int(boot["n_boot_validas"]),
                "isotonica_contraste": {"x": iso_x.tolist(), "y": iso_y.tolist()},
            }

            print(f"  [{nombre_mezcla}] n={len(x)} | tasa global ponderada="
                  f"{100*tasa_global:.1f}% | beta1={beta[1]:.2f} | boot ok={boot['n_boot_validas']}")
            for t in (0.05, 0.08, 0.10, 0.15, 0.20):
                j = int(np.argmin(np.abs(grid - t)))
                print(f"       theta_B2={t:.2f} -> central={100*curva[j]:.1f}%  "
                      f"lim.inf95={100*boot['p025'][j]:.1f}%")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    print(f"\nGuardado en {args.out}")
