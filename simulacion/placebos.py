
"""
placebos.py — Carril de placebos de Contexto-BTC (diseno aprobado 21-sep-2026).

QUE MIDE: la tasa de falsos positivos del pipeline COMPLETO (admision ->
gates 1/3/4 -> permutacion -> Benjamini-Yekutieli -> confirmacion forward)
ante variables reales barajadas (sin relacion con el precio, con su forma
real). NO mide la tasa base (consulta externa 6/6, 21-sep-2026).

Carril propio: no consume presupuesto_por_trimestre, no escribe en
registro.json, v2.json ni filtro.py. Importa filtro.py SIN modificarlo y usa
sus funciones tal cual (mismas etapas, mismos parametros de doctrina).

Uso:
  (desde la raiz del repo)
  python simulacion/placebos/placebos.py congelar            # escribe config congelada + hash
  python simulacion/placebos/placebos.py ejecutar --escala 1 --replicas 25 --salida r.json
"""
import sys, json, hashlib, argparse, time, copy
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import filtro

# ---------------------------------------------------------------------
# Huellas de entrada exigidas (verificadas antes de calcular nada)
# ---------------------------------------------------------------------
SHA_ENTRADA = {
    "v2.json":        "8f92a305cb8fd493",
    "registro.json":  "571c04c6d5fa7d79",
    "filtro.py":      "657961a762cef7f0",
    "snapshot_precio_btcusd.csv": "32c0b8ea8a66f011",
}
import os
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_placebos.json")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verificar_entradas(extra=None):
    todo = dict(SHA_ENTRADA, **(extra or {}))
    for p, pref in todo.items():
        real = sha(p)
        if not real.startswith(pref):
            sys.exit(f"ABORTO: {p} sha256 {real[:16]} != esperado {pref}")


# ---------------------------------------------------------------------
# Variables del lote de humo. Ventana de dependencia DEDUCIDA de la
# formula de la metrica (aprobado 21-sep, hueco 1), no leida de la ficha.
# ---------------------------------------------------------------------
LOTE_HUMO = [
    {"id": "vix_repesca", "csv": "serie_vix.csv", "sha": "476f91733659d841",
     "ventana_formula": "nivel diario del VIX; el valor de t no depende de dias previos",
     "V_obs": 0},
    {"id": "baa_credit_spread", "csv": "baa10y_serie_2026-09-08.csv", "sha": "7a90bd8777b70392",
     "ventana_formula": "nivel diario BAA10Y publicado por FRED; sin dependencia de dias previos",
     "V_obs": 0},
    {"id": "dgs10_delta20", "csv": "serie_dgs10_delta20.csv", "sha": "a9a7a2c79b81f920",
     "ventana_formula": "DGS10(t) - DGS10(t-20 observaciones no ausentes)",
     "V_obs": 20},
    {"id": "dgs2_delta20", "csv": "serie_dgs2_delta20.csv", "sha": "9715e58e5e771f8c",
     "ventana_formula": "DGS2(t) - DGS2(t-20 observaciones no ausentes)",
     "V_obs": 20},
]
EXCLUIDAS = [
    {"id": "ssr_capstables", "motivo":
     "historia desde 2018-10-27: no cubre el tramo comun de barajado (desde "
     "2013), requisito para aplicar la MISMA permutacion a todo el lote "
     "(punto 4 del diseno). No se fuerza."},
]

SUELO_BLOQUE = 30          # dias naturales (punto 2)
MIN_BLOQUES = 20           # bloques independientes minimos (punto 2)
FACTOR_SENSIBILIDAD = 2    # punto 3, fijado antes de ver resultados
SEMILLA = 20260921
DIAS_FORWARD = 455         # 5 x 91 (decision D2 de la fase 8)
M_REGIMEN = 0.03


def cargar_serie(path):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    f = df.columns[0]
    df[f] = pd.to_datetime(df[f]).dt.normalize()
    return df.set_index(f)[df.columns[1]].astype(float).sort_index()


def ventana_dias_naturales(serie, V_obs):
    """Maximo tramo en dias naturales que abarcan V_obs observaciones."""
    if V_obs == 0:
        return 0
    idx = serie.dropna().index
    return int((idx[V_obs:] - idx[:-V_obs]).days.max())


def ficha_de(reg, vid):
    fichas = [e for e in reg["entradas"] if e["id"] == vid and e.get("mascara")]
    if not fichas:
        sys.exit(f"ABORTO: sin ficha con mascara para {vid}")
    return fichas[-1]


# ---------------------------------------------------------------------
# CONGELAR (punto 9): todo el procedimiento queda fijado antes de ejecutar
# ---------------------------------------------------------------------
def congelar():
    verificar_entradas({v["csv"]: v["sha"] for v in LOTE_HUMO})
    doc = json.load(open("v2.json"))
    precio, _ = filtro.cargar_precio("snapshot_precio_btcusd.csv", doc)
    fin_precio = precio.index.max()
    fin_test = fin_precio - pd.Timedelta(days=DIAS_FORWARD)
    ventanas_mascara = []
    reg = json.load(open("registro.json"))
    vars_cfg = []
    for v in LOTE_HUMO:
        s = cargar_serie(v["csv"])
        f = ficha_de(reg, v["id"])
        ventanas_mascara.append(int(f["mascara"]["longitud_ventana_dias"]))
        V = ventana_dias_naturales(s, v["V_obs"])
        vars_cfg.append({**v, "V_dias_naturales": V,
                         "bloque_minimo_propio": max(SUELO_BLOQUE, V),
                         "signo_esperado": f["signo_esperado"]})
    inicio = precio.index.min() - pd.Timedelta(days=max(ventanas_mascara))
    span = (fin_precio - inicio).days + 1
    L = max(x["bloque_minimo_propio"] for x in vars_cfg)
    for x in vars_cfg:
        s = cargar_serie(x["csv"])
        x["cubre_tramo_comun"] = bool(s.index.min() <= inicio and s.index.max() >= fin_precio)
        x["bloques_esperados_base"] = round(span / L, 1)
        x["cumple_min_bloques_base"] = span / L >= MIN_BLOQUES
        x["cumple_min_bloques_sensibilidad"] = span / (L * FACTOR_SENSIBILIDAD) >= MIN_BLOQUES
    cfg = {
        "naturaleza": "carril de placebos; NO consume presupuesto; NO es candidata",
        "mide": "tasa de falsos positivos del pipeline completo bajo nula realista; NO la tasa base",
        "algoritmo": "stationary bootstrap (Politis-Romano 1994) sobre calendario diario "
                     "comun, bloques de longitud geometrica, circular; MISMA secuencia de "
                     "indices para todas las variables del lote (punto 4); cada variable "
                     "conserva su propio calendario de observacion",
        "tramo_comun": [str(inicio.date()), str(fin_precio.date())],
        "dias_tramo": span,
        "bloque_medio_base": L,
        "bloque_medio_sensibilidad": L * FACTOR_SENSIBILIDAD,
        "regla_bloque": f"max({SUELO_BLOQUE}, ventana de cada variable); comun = maximo del lote; "
                        f">= {MIN_BLOQUES} bloques o la variable se excluye",
        "calendario_placebo": {"fecha_fin_test": str(fin_test.date()),
                               "forward": f"{DIAS_FORWARD} dias hasta {fin_precio.date()}"},
        "M": M_REGIMEN,
        "semilla": SEMILLA,
        "lote_BY": "las variables del lote en la misma replica forman un lote; "
                   "m = max(3, n con p-valor), igual que filtro.py",
        "enmienda_42": "no se aplica al placebo: el barajado mueve valores, no el "
                       "calendario de observacion; los dias sin dato siguen donde estaban",
        "contaje_independencia": "la cota de falsos positivos se calcula con el numero "
                                 "de REPLICAS (barajados distintos), no con variables x replicas",
        "variables": vars_cfg,
        "excluidas": EXCLUIDAS,
        "sha_entradas": {**SHA_ENTRADA, **{v["csv"]: v["sha"] for v in LOTE_HUMO}},
        "sha_script": sha(__file__),
    }
    for x in vars_cfg:
        if not (x["cubre_tramo_comun"] and x["cumple_min_bloques_base"]):
            sys.exit(f"ABORTO: {x['id']} no cumple requisitos; excluir antes de congelar")
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: cfg[k] for k in ("tramo_comun", "bloque_medio_base",
                      "bloque_medio_sensibilidad", "calendario_placebo")}, ensure_ascii=False))
    for x in vars_cfg:
        print(f"  {x['id']}: V={x['V_dias_naturales']}d, bloque propio {x['bloque_minimo_propio']}, "
              f"~{x['bloques_esperados_base']} bloques")
    print(f"config congelada: {CONFIG} sha256 {sha(CONFIG)}")


# ---------------------------------------------------------------------
# STATIONARY BOOTSTRAP (punto 1)
# ---------------------------------------------------------------------
def stationary_bootstrap(n, L, rng):
    """Indices 0..n-1: bloques de longitud geometrica media L, inicio
    uniforme, circular."""
    p = 1.0 / L
    out = np.empty(n, dtype=np.int64)
    i = 0
    while i < n:
        ini = rng.integers(0, n)
        largo = rng.geometric(p)
        k = min(largo, n - i)
        out[i:i + k] = (ini + np.arange(k)) % n
        i += k
    return out


def placebo_de(serie, cal, idx):
    """Valor en t = ultimo dato disponible en la fecha origen cal[idx[t]];
    se conservan solo las fechas en que la serie original tiene dato."""
    asof = serie.dropna().reindex(cal, method="ffill")
    vals = asof.values[idx]
    s = pd.Series(vals, index=cal)
    obs = serie.dropna().index
    return s[s.index.isin(obs)].dropna()


# ---------------------------------------------------------------------
# PIPELINE: replica exacta de filtro.ejecutar para una variable
# ---------------------------------------------------------------------
def etapa_test(met_test, ficha, precio, ret, base, doc, n_tramos):
    """Devuelve dict con etapa alcanzada y, si llega, p-valor y theta_B2."""
    fecha_fin = pd.Timestamp(ficha["fecha_fin_ventana_test"])
    mask, _ = filtro.construir_mascara(met_test, ficha)
    mask = mask[mask.index <= fecha_fin]
    mask = mask[mask.index.isin(precio.index)]
    b1, b2, part = filtro.particionar(mask.index, doc)
    if not part["suficiente"]:
        return {"etapa": "particion"}
    diag = filtro.diagnostico_estructural(mask, b1, b2, ret, base, doc)
    if not diag["admisible"]:
        return {"etapa": "admision_38", "motivos": diag["motivos"]}
    m1, m2 = mask.loc[b1], mask.loc[b2]
    tr = filtro.tramos_de(b1, n_tramos)
    g1 = filtro.gate1(m1, ret, tr, doc)
    g3 = filtro.gate3(m1, ret, base, doc)
    g4 = filtro.gate4(g1["correlaciones_por_tramo"], doc)
    if g1["insuficiencia"] or g3["insuficiencia"]:
        return {"etapa": "insuficiencia_gates"}
    if not g1["pasa"]:
        return {"etapa": "gate1"}
    if not g3["pasa"]:
        return {"etapa": "gate3"}
    if not g4["pasa"]:
        return {"etapa": "gate4"}
    perm = filtro.test_permutacion(m2, ret, doc, ficha["signo_esperado"])
    if perm["insuficiencia"]:
        return {"etapa": "permutacion_insuficiencia"}
    return {"etapa": "con_pvalor", "p_valor": perm["p_valor"],
            "theta_B2": perm["theta_B2"], "episodios": perm["episodios"]}


def protegido(fn, *a):
    try:
        return fn(*a)
    except SystemExit as e:
        return {"etapa": "aborto_motor", "motivo": str(e)[:200]}
    except RuntimeError as e:
        return {"etapa": "error_rotacion", "motivo": str(e)[:200]}


def ejecutar(escala, n_replicas, salida, identidad=False):
    cfg = json.load(open(CONFIG))
    if cfg["sha_script"] != sha(__file__):
        sys.exit("ABORTO: el script cambio despues de congelar la config")
    verificar_entradas({v["csv"]: v["sha"] for v in cfg["variables"]})
    doc = json.load(open("v2.json"))
    reg = json.load(open("registro.json"))
    precio, _ = filtro.cargar_precio("snapshot_precio_btcusd.csv", doc)
    N = filtro.ruta(doc, "definicion_de_efecto.horizonte_N.valor")
    n_tramos = filtro.ruta(doc, "protocolo.gates_cualitativos.parametros.definicion_de_tramos.n_tramos")
    fin_test = pd.Timestamp(cfg["calendario_placebo"]["fecha_fin_test"])
    precio_test = precio[precio.index <= fin_test + pd.Timedelta(days=N)]
    ret = filtro.retorno_N(precio_test, N)
    base = filtro.base_gate3(precio_test, doc)
    ini, fin = map(pd.Timestamp, cfg["tramo_comun"])
    cal = pd.date_range(ini, fin, freq="D")
    L = cfg["bloque_medio_base"] * escala
    series, fichas = {}, {}
    for v in cfg["variables"]:
        s = cargar_serie(v["csv"])
        series[v["id"]] = s[(s.index >= ini) & (s.index <= fin)]
        f = copy.deepcopy(ficha_de(reg, v["id"]))
        f["fecha_fin_ventana_test"] = str(fin_test.date())
        fichas[v["id"]] = f
    rng = np.random.default_rng(SEMILLA + 1000 * escala)
    replicas = []
    t0 = time.time()
    for r in range(n_replicas):
        idx = np.arange(len(cal)) if identidad else stationary_bootstrap(len(cal), L, rng)
        res = {}
        pl_ext = {}
        for vid in series:
            pl = placebo_de(series[vid], cal, idx)
            pl_ext[vid] = pl
            res[vid] = protegido(etapa_test, pl[pl.index <= fin_test], fichas[vid],
                                 precio_test, ret, base, doc, n_tramos)
        pv = {vid: x["p_valor"] for vid, x in res.items() if x["etapa"] == "con_pvalor"}
        if pv:
            acept, by = filtro.benjamini_yekutieli(pv, doc)
            for vid in pv:
                res[vid]["pasa_BY"] = vid in acept
                res[vid]["m_BY"] = by["m_efectivo"]
                if vid in acept:
                    try:
                        ver, det = filtro.confirmacion_forward(
                            pl_ext[vid], precio, fichas[vid], res[vid]["theta_B2"],
                            M_REGIMEN, doc,
                            metrica_test=pl_ext[vid][pl_ext[vid].index <= fin_test],
                            precio_test=precio_test)
                        res[vid]["forward"] = ver
                        res[vid]["theta_F"] = det.get("theta_F")
                    except SystemExit as e:
                        res[vid]["forward"] = "aborto_motor"
                        res[vid]["motivo_forward"] = str(e)[:200]
        replicas.append({"replica": r, "resultados": res})
        print(f"  replica {r + 1}/{n_replicas} ({time.time() - t0:.0f}s): "
              + " | ".join(f"{k}:{v['etapa']}{'+BY' if v.get('pasa_BY') else ''}"
                           f"{'+' + v['forward'] if v.get('forward') else ''}"
                           for k, v in res.items()), flush=True)
    out = {"config_sha256": sha(CONFIG), "escala_bloque": escala, "bloque_medio": L,
           "identidad": identidad, "n_replicas": n_replicas,
           "embudo": embudo(replicas), "replicas": replicas}
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(out["embudo"], ensure_ascii=False, indent=1))
    print(f"resultado: {salida} sha256 {sha(salida)}")


ORDEN = ["particion", "admision_38", "insuficiencia_gates", "error_rotacion",
         "aborto_motor", "gate1", "gate3", "gate4", "permutacion_insuficiencia", "con_pvalor"]


def embudo(replicas):
    por_var, total = {}, {"llega_pvalor": 0, "pasa_BY": 0, "CONFIRMADA": 0}
    rep_con_confirmada = 0
    for rp in replicas:
        alguna = False
        for vid, x in rp["resultados"].items():
            d = por_var.setdefault(vid, {k: 0 for k in ORDEN + ["pasa_BY", "CONFIRMADA",
                                                                "RECHAZADA_FORWARD", "PENDIENTE_REVISION"]})
            d[x["etapa"]] += 1
            if x.get("pasa_BY"):
                d["pasa_BY"] += 1
            if x.get("forward") in d:
                d[x["forward"]] += 1
            if x["etapa"] == "con_pvalor":
                total["llega_pvalor"] += 1
            total["pasa_BY"] += int(bool(x.get("pasa_BY")))
            if x.get("forward") == "CONFIRMADA":
                total["CONFIRMADA"] += 1
                alguna = True
        rep_con_confirmada += int(alguna)
    n = len(replicas)
    return {"por_variable": por_var, "totales": total,
            "replicas": n, "replicas_con_alguna_CONFIRMADA": rep_con_confirmada,
            "cota_sup_95_por_replica_si_0": round(3.0 / n, 4) if n else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["congelar", "ejecutar"])
    ap.add_argument("--escala", type=int, default=1)
    ap.add_argument("--replicas", type=int, default=25)
    ap.add_argument("--salida", default="resultado_placebos.json")
    ap.add_argument("--identidad", action="store_true",
                    help="sin barajar: comprobacion de fontaneria")
    a = ap.parse_args()
    congelar() if a.accion == "congelar" else ejecutar(a.escala, a.replicas, a.salida, a.identidad)
