"""nulos2.py — rotacion restringida por tramos de volatilidad (parametros aprobados 22-sep-2026).
Mismo estadistico que nulos.py. Devuelve ambas colas: 'sup' = frac(nulo >= obs), 'inf' = frac(nulo <= obs).
Parametros congelados: vol30 = std de log-retornos de los 30 dias hasta t; 3 tramos por terciles de vol30
frente a los 365 dias ANTERIORES (solo pasado); admisible si ningun tramo difiere > 10 puntos en el reparto
de dias activos; desplazamientos candidatos [30, L-30]; minimo 200 admisibles, si no -> no evaluable."""
import numpy as np, pandas as pd
import nulos

EXCL, TOL, MIN_ADM, N_PERM, SEMILLA = 30, 0.10, 200, 2000, 0

def tramos_vol(precio):
    """precio: pd.Series. Devuelve Serie con tramo 0/1/2 (NaN si falta historia)."""
    v = np.log(precio).diff().rolling(30).std()
    past = v.shift(1).rolling(365, min_periods=365)
    q1, q2 = past.quantile(1/3), past.quantile(2/3)
    t = pd.Series(np.where(v > q2, 2, np.where(v > q1, 1, 0)), index=precio.index, dtype=float)
    t[q1.isna() | v.isna()] = np.nan
    return t

def _reparto(m, T):
    n = m.sum()
    return np.array([(m & (T == k)).sum() / n for k in range(3)])

def admisibles(m, T, excl=EXCL, tol=TOL):
    L = len(m); base = _reparto(m, T)
    ind = [(T == k) for k in range(3)]
    ss = np.arange(excl, L - excl + 1); n = m.sum(); out = []
    for s in ss:
        mm = np.roll(m, int(s))
        rep = np.array([(mm & ind[k]).sum() for k in range(3)]) / n
        if np.max(np.abs(rep - base)) <= tol: out.append(s)
    return np.array(out, dtype=int)

def _colas(real, difs):
    return {'sup': float((difs >= real).mean()), 'inf': float((difs <= real).mean())}

def p_restringida(m, r, T):
    real = np.median(r[m]) - np.median(r[~m])
    adm = admisibles(m, T)
    if len(adm) < MIN_ADM:
        return {'evaluable': False, 'n_adm': int(len(adm))}
    rng = np.random.default_rng(SEMILLA); difs = np.empty(N_PERM)
    for k, s in enumerate(rng.choice(adm, N_PERM, replace=True)):
        mm = np.roll(m, int(s)); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return {'evaluable': True, 'n_adm': int(len(adm)), **_colas(real, difs)}

# --- ambas colas para los nulos ya medidos (solo para recalcular M3 con el criterio nuevo) ---
def p_rotacion2(m, r, n_perm=N_PERM, semilla=SEMILLA, excl=EXCL):
    real = np.median(r[m]) - np.median(r[~m]); L = len(m)
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm)
    for k, s in enumerate(rng.integers(excl, L - excl + 1, n_perm)):
        mm = np.roll(m, int(s)); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return _colas(real, difs)

def p_episodios2(m, r, n_perm=N_PERM, semilla=SEMILLA):
    real = np.median(r[m]) - np.median(r[~m])
    dur, val = nulos._rachas(m); de = dur[val]; dh = dur[~val]
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm); out = dur.copy()
    for k in range(n_perm):
        out[val] = rng.permutation(de); out[~val] = rng.permutation(dh)
        mm = np.repeat(val, out); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return _colas(real, difs)
