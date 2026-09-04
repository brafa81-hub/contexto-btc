"""
CALIBRACION DE LOS GATES — Contexto-BTC, migracion v1 -> v2 (Tanda 0, Paso 1)
Fecha: 2026-09-04.  Semilla fija: reproducible byte a byte.

QUE MIDE
--------
Que proporcion de RUIDO PURO atraviesa cada gate del protocolo v2 rediseñado,
para fijar tres umbrales sin elegirlos a ojo:

  (a) umbral de correlacion del gate 1, con entrada BINARIA (la mascara)
  (b) umbral de Delta-R2 del gate 3
  (c) minimo de observaciones por tramo del gate 1

Y de paso verifica empiricamente las dos tasas que las enmiendas B y G
afirman sin haberlas medido: ~50% para el gate 2 y ~25% para el gate 4.

METODO
------
Mismo montaje que fijo el 0.04 de v1 (FALLO 3 de filtro.py): series
sinteticas de precio con volatilidad agrupada tipo BTC, y una mascara
binaria con rachas generada de forma INDEPENDIENTE del precio. Por
construccion NO existe relacion. Todo lo que pasa un gate es falso positivo.

El liston se pone en el percentil 70-80, no en el 95: el control real de
falsos positivos vive en la confirmacion forward, no en estos gates. El
coste de un falso negativo aqui es irreversible (unicidad_del_test).

SUPUESTOS DECLARADOS (no son datos confirmados; se someten a sensibilidad)
-------------------------------------------------------------------------
  - precio: GARCH(1,1) alpha=0.08, beta=0.90, sd diaria 3.5%
  - mascara: cadena de Markov de 2 estados, activa 20%, racha media 30 dias
  - bloque_1 de referencia: 1387 dias (~3.8 anios, el de SSR)
  - horizonte N = 30 dias (definicion_de_efecto, INMUTABLE)

No se uso ninguna serie real de BTC: la calibracion mide la distribucion
NULA, que depende de la estructura de solapamiento (N=30) y de las rachas
de la mascara, no del historico concreto. La sensibilidad lo confirma.
"""
import numpy as np
from scipy.stats import rankdata

RNG = np.random.default_rng(20260904)

N = 30              # horizonte del retorno (inmutable)
WARM = 200          # warm-up para SMA200 de la base del gate 3
N_TRAMOS = 3        # enmienda G, opcion B


# ------------------------------------------------------------------ generadores
def precios(n_sims, n_dias, sd=0.035, alpha=0.08, beta=0.90):
    """Log-precios con volatilidad agrupada. Deriva cero (irrelevante en el nulo)."""
    omega = (sd ** 2) * (1 - alpha - beta)
    sig2 = np.full(n_sims, sd ** 2)
    r = np.empty((n_sims, n_dias))
    for t in range(n_dias):
        e = RNG.standard_normal(n_sims) * np.sqrt(sig2)
        r[:, t] = e
        sig2 = omega + alpha * e ** 2 + beta * sig2
    return np.exp(np.cumsum(r, axis=1))


def mascaras(n_sims, n_dias, activa=0.20, racha=30):
    """Markov de 2 estados. Independiente del precio: este es el nulo."""
    b = 1.0 / racha
    a = activa * b / (1 - activa)
    m = np.empty((n_sims, n_dias), dtype=bool)
    est = RNG.random(n_sims) < activa
    for t in range(n_dias):
        m[:, t] = est
        u = RNG.random(n_sims)
        est = np.where(est, u >= b, u < a)
    return m


# ----------------------------------------------------------------- estadisticos
def spearman(x, y):
    """Spearman por filas. Con x binaria ES la correlacion rank-biserial."""
    rx = np.apply_along_axis(rankdata, 1, x.astype(float))
    ry = np.apply_along_axis(rankdata, 1, y)
    rx -= rx.mean(1, keepdims=True)
    ry -= ry.mean(1, keepdims=True)
    den = np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))
    return np.divide((rx * ry).sum(1), den, out=np.zeros(len(x)), where=den > 0)


def theta(mask, y):
    """theta = mediana(y|m=1) - mediana(y|m=0)."""
    out = np.full(len(y), np.nan)
    for i in range(len(y)):
        m = mask[i]
        if m.sum() >= 2 and (~m).sum() >= 2:
            out[i] = np.median(y[i][m]) - np.median(y[i][~m])
    return out


def rolling_std(x, w):
    c1 = np.concatenate([[0], np.cumsum(x)])
    c2 = np.concatenate([[0], np.cumsum(x ** 2)])
    n = len(x)
    s, q = c1[w:] - c1[:n - w + 1], c2[w:] - c2[:n - w + 1]
    return np.sqrt(np.maximum(q / w - (s / w) ** 2, 0))


# ---------------------------------------------------------------------- gate 1
def gate1(n_sims, dias_tramo, activa=0.20, racha=30, sd=0.035,
          alpha=0.08, beta=0.90):
    """Devuelve (estadistico |mediana corr tramos|, pasa gate 4, activos/tramo)."""
    b1 = dias_tramo * N_TRAMOS
    P = precios(n_sims, b1 + N, sd, alpha, beta)
    M = mascaras(n_sims, b1 + N, activa, racha)
    y = P[:, N:] / P[:, :b1] - 1
    m = M[:, :b1]
    cortes = np.array_split(np.arange(b1), N_TRAMOS)
    corrs = np.stack([spearman(m[:, c], y[:, c]) for c in cortes], axis=1)
    act = np.stack([m[:, c].sum(1) for c in cortes], axis=1)
    signo = np.all(corrs > 0, 1) | np.all(corrs < 0, 1)
    return np.abs(np.median(corrs, axis=1)), signo, act


# ---------------------------------------------------------------------- gate 2
def gate2(n_sims, dias_b1=1387, activa=0.20, racha=30):
    """|theta_fwd| >= |theta_bwd|, ambos sobre la mascara (enmienda B)."""
    P = precios(n_sims, N + dias_b1 + N)
    M = mascaras(n_sims, N + dias_b1 + N, activa, racha)
    ini, fin = N, N + dias_b1
    y_f = P[:, ini + N:fin + N] / P[:, ini:fin] - 1
    y_b = P[:, ini:fin] / P[:, ini - N:fin - N] - 1
    m = M[:, ini:fin]
    return np.abs(theta(m, y_f)) >= np.abs(theta(m, y_b))


# ---------------------------------------------------------------------- gate 3
def gate3(n_sims, dias_b1, activa=0.20, racha=30, sd=0.035,
          alpha=0.08, beta=0.90, regresor="mascara"):
    """Delta-R2 en pp, en muestra, base fija [mayer, vol30, mom30] (enmienda D)."""
    P = precios(n_sims, WARM + dias_b1 + N, sd, alpha, beta)
    M = mascaras(n_sims, WARM + dias_b1 + N, activa, racha)
    ini, fin = WARM, WARM + dias_b1
    ker = np.ones(WARM) / WARM
    out = np.empty(n_sims)
    for i in range(n_sims):
        p = P[i]
        y = p[ini + N:fin + N] / p[ini:fin] - 1
        sma = np.convolve(p, ker, "valid")
        mayer = p[ini:fin] / sma[ini - WARM + 1: fin - WARM + 1]
        vol30 = rolling_std(np.diff(np.log(p)), 30)[ini - 30: fin - 30]
        mom30 = p[ini:fin] / p[ini - 30:fin - 30] - 1
        X0 = np.column_stack([np.ones(dias_b1), mayer, vol30, mom30])
        nueva = (M[i, ini:fin].astype(float) if regresor == "mascara"
                 else np.log(p[ini:fin]) - np.log(p[ini - 5:fin - 5]))
        X1 = np.column_stack([X0, nueva])
        sst = ((y - y.mean()) ** 2).sum()
        r = [1 - ((y - X @ np.linalg.lstsq(X, y, rcond=None)[0]) ** 2).sum() / sst
             for X in (X0, X1)]
        out[i] = (r[1] - r[0]) * 100
    return out


# ------------------------------------------------------------------------ main
if __name__ == "__main__":
    P = (70, 75, 80)

    print("=" * 78)
    print("(a) GATE 1 — |mediana de las correlaciones por tramo|, entrada BINARIA")
    print("=" * 78)
    print(f"{'dias/tramo':>10} {'anios b1':>9} {'obs_ef':>7} "
          f"{'p70':>8} {'p75':>8} {'p80':>8} {'% pasa 0.04':>12}")
    for d in (120, 180, 250, 365, 462, 600, 900):
        s, _, _ = gate1(3000, d)
        print(f"{d:>10} {3*d/365:>9.1f} {d/N:>7.1f} "
              + " ".join(f"{np.percentile(s,p):>8.4f}" for p in P)
              + f" {100*(s>=0.04).mean():>11.1f}%")

    print("\n" + "=" * 78)
    print("(b) GATE 3 — Delta-R2 bajo ruido puro, base fija del precio")
    print("=" * 78)
    print(f"{'escenario':<38} {'p70':>7} {'p75':>7} {'p80':>7} {'%pasa 3.0':>10}")
    for nombre, kw in [
        ("bloque_1 1095 d (minimo doctrinal)", dict(dias_b1=1095)),
        ("bloque_1 1387 d (SSR)", dict(dias_b1=1387)),
        ("bloque_1 1825 d (5 anios)", dict(dias_b1=1825)),
        ("SSR, regresor CONTINUO (control)", dict(dias_b1=1387, regresor="continuo")),
    ]:
        d = gate3(1200, **kw)
        d = d[np.isfinite(d)]
        print(f"{nombre:<38} " + " ".join(f"{np.percentile(d,p):>7.3f}" for p in P)
              + f" {100*(d>=3.0).mean():>9.1f}%")

    print("\n" + "=" * 78)
    print("(c) DIAS ACTIVOS POR TRAMO DE 365 DIAS, segun velocidad de la mascara")
    print("=" * 78)
    for racha in (15, 30, 60, 90):
        m = mascaras(4000, 365, 0.20, racha).sum(1)
        print(f"racha {racha:>2}d: media={m.mean():>3.0f} activos  "
              f"p5={np.percentile(m,5):>3.0f}  "
              f"% tramos con <30 activos = {100*(m<30).mean():>4.1f}%")

    print("\n" + "=" * 78)
    print("VERIFICACION DE LOS GATES SIN PARAMETRO LIBRE")
    print("=" * 78)
    print(f"GATE 2 (|theta_fwd| >= |theta_bwd|) pasa el "
          f"{100*np.nanmean(gate2(3000)):.1f}% del ruido puro")
    _, sg, _ = gate1(3000, 462)
    print(f"GATE 4 (signo identico en 3 tramos)  pasa el "
          f"{100*sg.mean():.1f}% del ruido puro")

    print("\n" + "=" * 78)
    print("SENSIBILIDAD DE (a) A LOS SUPUESTOS  [tramo = 365 d]")
    print("=" * 78)
    for nombre, kw in [
        ("caso base", {}), ("racha 15d", {"racha": 15}),
        ("racha 60d", {"racha": 60}), ("racha 90d", {"racha": 90}),
        ("mascara 15%", {"activa": 0.15}), ("mascara 25%", {"activa": 0.25}),
        ("vol diaria 2.5%", {"sd": 0.025}), ("vol diaria 5.0%", {"sd": 0.050}),
        ("sin agrupamiento vol", {"alpha": 0.0, "beta": 0.0}),
    ]:
        s, _, _ = gate1(3000, 365, **kw)
        print(f"{nombre:<24} " + "  ".join(f"p{p}={np.percentile(s,p):.4f}" for p in P))
