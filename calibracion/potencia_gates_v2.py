"""¿Cuánta señal REAL pierde la capa de gates a cada percentil?
Replica el metodo de FALLO 1 de filtro.py v1: inyectar señal de fuerza
conocida y medir que proporcion detecta el filtro."""
import numpy as np
from calibracion_gates_v2 import mascaras, spearman, theta

N, T, WARM, B1 = 30, 3, 200, 1387
RNG = np.random.default_rng(4242)

# umbrales derivados del nulo ya medido para esta configuracion exacta
CONFIG = {"p50": (0.089, 0.69), "p75": (0.153, 1.98), "p80": (0.172, 2.42)}


def rolling_std(x, w):
    c1 = np.concatenate([[0], np.cumsum(x)]); c2 = np.concatenate([[0], np.cumsum(x**2)])
    n = len(x); s = c1[w:]-c1[:n-w+1]; q = c2[w:]-c2[:n-w+1]
    return np.sqrt(np.maximum(q/w-(s/w)**2, 0))


def simular_con_senal(n_sims, g, sd=0.035, alpha=0.08, beta=0.90, racha=30):
    """Deriva diaria extra = g mientras la mascara esta activa (variable de regimen)."""
    n = WARM + B1 + N
    M = mascaras(n_sims, n, 0.20, racha)
    omega = sd**2 * (1-alpha-beta)
    sig2 = np.full(n_sims, sd**2)
    r = np.empty((n_sims, n))
    for t in range(n):
        e = RNG.standard_normal(n_sims)*np.sqrt(sig2)
        r[:, t] = e + g*M[:, t-1] if t > 0 else e
        sig2 = omega + alpha*e**2 + beta*sig2
    return np.exp(np.cumsum(r, axis=1)), M


def evaluar(P, M):
    ini, fin = WARM, WARM+B1
    y_f = P[:, ini+N:fin+N]/P[:, ini:fin]-1
    y_b = P[:, ini:fin]/P[:, ini-N:fin-N]-1
    m = M[:, ini:fin]
    cortes = np.array_split(np.arange(B1), T)
    corrs = np.stack([spearman(m[:, k], y_f[:, k]) for k in cortes], axis=1)
    s1 = np.abs(np.median(corrs, 1))
    g4 = np.all(corrs > 0, 1) | np.all(corrs < 0, 1)
    g2 = np.nan_to_num(np.abs(theta(m, y_f)) >= np.abs(theta(m, y_b)), nan=False).astype(bool)
    ker = np.ones(WARM)/WARM
    d = np.empty(len(P))
    for i in range(len(P)):
        p, y = P[i], y_f[i]
        sma = np.convolve(p, ker, "valid")
        X0 = np.column_stack([np.ones(B1), p[ini:fin]/sma[ini-WARM+1:fin-WARM+1],
                              rolling_std(np.diff(np.log(p)), 30)[ini-30:fin-30],
                              p[ini:fin]/p[ini-30:fin-30]-1])
        X1 = np.column_stack([X0, m[i].astype(float)])
        sst = ((y-y.mean())**2).sum()
        rr = [1-((y-X@np.linalg.lstsq(X, y, rcond=None)[0])**2).sum()/sst for X in (X0, X1)]
        d[i] = (rr[1]-rr[0])*100
    th = theta(m, y_f)
    return s1, g2, d, g4, th


print("POTENCIA DE LA CAPA DE GATES FRENTE A SEÑAL REAL INYECTADA")
print("bloque_1 = 1387 d, mascara 20% racha 30d, 800 simulaciones por fila\n")
print(f"{'deriva/dia':>10} {'theta real':>11} | {'% detectado por la capa completa':>36}")
print(f"{'':>10} {'(30d)':>11} | {'p50':>10} {'p75':>10} {'p80':>10}   {'gate2 solo':>11}")
for g in (0.0, 0.0005, 0.001, 0.002, 0.003, 0.005, 0.008):
    P, M = simular_con_senal(800, g)
    s1, g2, d, g4, th = evaluar(P, M)
    fila = []
    for k in ("p50", "p75", "p80"):
        u1, u3 = CONFIG[k]
        fila.append(100*((s1 >= u1) & g2 & (d >= u3) & g4).mean())
    print(f"{g:>10.4f} {np.nanmedian(th):>11.4f} | "
          + " ".join(f"{v:>9.1f}%" for v in fila)
          + f"   {100*g2.mean():>10.1f}%")
