"""
motor.py — Replica exacta de las primitivas de filtro.py necesarias para
simulacion (gate1, gate3, gate4, test_permutacion, benjamini_yekutieli,
episodios_independientes). Copiado linea a linea de filtro.py del repo
(raw.githubusercontent.com/brafa81-hub/contexto-btc/main/filtro.py),
verificado contra el SHA-256 descargado en esta sesion.

NO reimplementa logica: son las mismas funciones, con las mismas firmas,
para poder alimentarlas con datos sinteticos sin tocar v2.json/registro.json.
"""

import numpy as np
import pandas as pd


# =====================================================================
# Copiado de filtro.py (FASE 4 — GATES), sin modificar
# =====================================================================

def tramos_de(indice, n_tramos):
    ini, fin = indice.min(), indice.max()
    total = (fin - ini).days
    bordes = [ini + pd.Timedelta(days=round(total * k / n_tramos)) for k in range(n_tramos + 1)]
    out = []
    for k in range(n_tramos):
        a = bordes[k]
        b = bordes[k + 1] if k == n_tramos - 1 else bordes[k + 1] - pd.Timedelta(days=1)
        out.append((a, b))
    return out


def retorno_N(precio, N):
    return (precio.shift(-N) / precio - 1).rename("retorno_N")


def _pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def spearman(x, y):
    return _pearson(pd.Series(np.asarray(x, float)).rank().values,
                    pd.Series(np.asarray(y, float)).rank().values)


def _r2_np(X, y):
    X = np.column_stack([np.ones(len(y)), X])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ beta
    sst = ((y - y.mean()) ** 2).sum()
    return float(1 - (res ** 2).sum() / sst) if sst > 0 else float("nan")


def obs_efectivas(indice, N):
    return len(indice) / N


def _preparar_tramos(indice, ret, tramos):
    r = ret.reindex(indice).values
    ok = np.isfinite(r)
    sel = [((indice >= a) & (indice <= b) & ok) for a, b in tramos]
    return r, sel


def _cors_por_tramo(mvals, rvals, selectores):
    cors = []
    for sel in selectores:
        if sel.sum() < 3:
            cors.append(float("nan"))
        else:
            cors.append(spearman(mvals[sel].astype(float), rvals[sel]))
    return cors


def umbral_por_rotacion(estadistico, mask, semilla, n_rotaciones, percentil):
    """
    Version parametrizada de filtro.py::umbral_por_rotacion (alli lee
    semilla/n_rotaciones/percentil de doc via ruta()). Misma logica exacta.
    """
    rng = np.random.default_rng(semilla)
    n = len(mask)
    offsets = rng.integers(1, max(2, n), size=n_rotaciones)
    base = np.asarray(mask.values if hasattr(mask, "values") else mask)
    vals = []
    for k in offsets:
        v = estadistico(np.roll(base, int(k)))
        if np.isfinite(v):
            vals.append(v)
    if len(vals) < n_rotaciones // 2:
        raise RuntimeError("el nulo por rotacion no produjo suficientes realizaciones finitas")
    return float(np.percentile(vals, percentil)), len(vals)


def gate1(mask_b1, ret, tramos, N, semilla, n_rotaciones, percentil, min_obs_tramo):
    insuficientes = []
    for k, (a, b) in enumerate(tramos, start=1):
        idx = mask_b1.index[(mask_b1.index >= a) & (mask_b1.index <= b)]
        if obs_efectivas(idx, N) < min_obs_tramo:
            insuficientes.append((k, round(obs_efectivas(idx, N), 1)))

    rvals, selectores = _preparar_tramos(mask_b1.index, ret, tramos)

    def stat(mvals):
        cors = [c for c in _cors_por_tramo(mvals, rvals, selectores) if np.isfinite(c)]
        return abs(float(np.median(cors))) if len(cors) == len(tramos) else float("nan")

    obs = stat(mask_b1.values)
    umbral, n_val = umbral_por_rotacion(stat, mask_b1, semilla, n_rotaciones, percentil)
    cors = _cors_por_tramo(mask_b1.values, rvals, selectores)

    if not np.isfinite(obs):
        return {"pasa": False, "insuficiencia": bool(insuficientes), "no_evaluable": True}

    return {
        "estadistico": obs, "umbral": umbral, "correlaciones_por_tramo": cors,
        "tramos_insuficientes": insuficientes,
        "pasa": bool(np.isfinite(obs) and obs >= umbral and not insuficientes),
        "insuficiencia": bool(insuficientes),
        "no_evaluable": False,
    }


def gate3(mask_b1, ret, base, N, semilla, n_rotaciones, percentil, minimo):
    datos = base.reindex(mask_b1.index).join(ret.reindex(mask_b1.index)).dropna()
    efectivas = obs_efectivas(datos.index, N)

    cols = list(base.columns)
    X0 = datos[cols].values
    y = datos["retorno_N"].values
    pos = mask_b1.index.get_indexer(datos.index)
    r2_base = _r2_np(X0, y)

    def stat(mvals):
        m = np.asarray(mvals, float)[pos]
        if m.std() == 0:
            return float("nan")
        return (_r2_np(np.column_stack([X0, m]), y) - r2_base) * 100

    obs = stat(mask_b1.values)
    umbral, n_val = umbral_por_rotacion(stat, mask_b1, semilla, n_rotaciones, percentil)

    return {"delta_r2_pp": obs, "umbral_pp": umbral,
            "observaciones_efectivas": round(efectivas, 1), "minimo": minimo,
            "insuficiencia": bool(efectivas < minimo),
            "pasa": bool(np.isfinite(obs) and obs >= umbral and efectivas >= minimo)}


def gate4(cors):
    validos = [c for c in cors if np.isfinite(c) and c != 0]
    pasa = len(validos) == len(cors) and len({np.sign(c) for c in validos}) == 1
    return {"pasa": bool(pasa)}


# =====================================================================
# Copiado de filtro.py (FASE 5 — P-VALOR SOBRE BLOQUE_2), sin modificar
# =====================================================================

def _media_recortada(x, prop):
    x = np.sort(np.asarray(x, float))
    k = int(len(x) * prop)
    return float(x[k:len(x) - k].mean()) if len(x) - 2 * k > 0 else float("nan")


def _hodges_lehmann(a, b, semilla, tope=400):
    rng = np.random.default_rng(semilla)
    if len(a) > tope:
        a = rng.choice(a, tope, replace=False)
    if len(b) > tope:
        b = rng.choice(b, tope, replace=False)
    return float(np.median(np.subtract.outer(a, b)))


def episodios_independientes(fechas, dias_episodio):
    eps = []
    for d in fechas:
        if not eps or (d - eps[-1][-1]).days > dias_episodio:
            eps.append([d])
        else:
            eps[-1].append(d)
    return eps


def test_permutacion(mask_b2, ret, signo_esperado, dias_ep, obs_min, eps_min,
                      n_permutaciones, semilla):
    z = pd.DataFrame({"m": mask_b2, "retorno_N": ret.reindex(mask_b2.index)}).dropna()
    sel = z[z["m"]]

    if len(sel) < obs_min:
        return {"insuficiencia": True, "motivo": f"solo {len(sel)} observaciones enmascaradas"}

    eps = episodios_independientes(sel.index, dias_ep)
    if len(eps) < eps_min:
        return {"insuficiencia": True, "episodios": len(eps),
                "motivo": f"solo {len(eps)} episodios independientes"}

    real = float(z[z["m"]]["retorno_N"].median() - z[~z["m"]]["retorno_N"].median())
    vals = z["retorno_N"].values
    n = len(sel)
    rng = np.random.default_rng(semilla)

    difs = []
    for _ in range(n_permutaciones):
        i = rng.integers(0, max(1, len(vals) - n))
        bloque = vals[i:i + n]
        resto = np.delete(vals, slice(i, i + n))
        difs.append(np.median(bloque) - np.median(resto))
    difs = np.array(difs)

    if signo_esperado == "positivo":
        p = float((difs >= real).mean())
    elif signo_esperado == "negativo":
        p = float((difs <= real).mean())
    elif signo_esperado == "bilateral":
        p = float((np.abs(difs) >= abs(real)).mean())
    else:
        raise ValueError(f"signo_esperado '{signo_esperado}' invalido")

    a = z[z["m"]]["retorno_N"].values
    b = z[~z["m"]]["retorno_N"].values
    hl = _hodges_lehmann(a, b, semilla=semilla)
    recortada = _media_recortada(a, 0.10) - _media_recortada(b, 0.10)

    return {"insuficiencia": False, "p_valor": p, "theta_B2": real,
            "episodios": len(eps), "observaciones_enmascaradas": int(n),
            "robustez": {"hodges_lehmann": hl, "media_recortada_10pct": recortada}}


def benjamini_yekutieli(pvalores, q_nominal):
    m = max(3, len(pvalores))
    H = sum(1.0 / j for j in range(1, m + 1))
    orden = sorted(pvalores.items(), key=lambda kv: kv[1])
    k = 0
    for rango, (_, p) in enumerate(orden, start=1):
        if p <= (rango / m) * q_nominal / H:
            k = rango
    aceptados = {id_ for id_, _ in orden[:k]}
    return aceptados
