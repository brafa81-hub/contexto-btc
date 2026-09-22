"""nulos.py — tres nulos para el p-valor de bloque_2 (solo medicion, no cambia el motor).
Todos usan el mismo estadistico que filtro.py: mediana(ret | mascara) - mediana(ret | no mascara),
p = fraccion de nulos >= observado (signo positivo), 2000 realizaciones, semilla 0."""
import numpy as np

def p_contiguo(m, r, n_perm=2000, semilla=0):
    # identico a motor.test_permutacion: bloque contiguo de n dias vs resto
    real = np.median(r[m]) - np.median(r[~m]); n = int(m.sum())
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm)
    for k in range(n_perm):
        i = rng.integers(0, max(1, len(r) - n))
        difs[k] = np.median(r[i:i+n]) - np.median(np.delete(r, slice(i, i+n)))
    return float((difs >= real).mean())

def _rachas(m):
    cambios = np.flatnonzero(np.diff(m.astype(np.int8))) + 1
    bordes = np.r_[0, cambios, len(m)]
    dur = np.diff(bordes); val = m[bordes[:-1]]
    return dur, val

def p_episodios(m, r, n_perm=2000, semilla=0):
    # baraja por separado duraciones de episodios (rachas activas) y de huecos; mismo patron
    # de alternancia y mismo total -> cabe exactamente en bloque_2, sin envolver
    real = np.median(r[m]) - np.median(r[~m])
    dur, val = _rachas(m); de = dur[val]; dh = dur[~val]
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm); out = dur.copy()
    for k in range(n_perm):
        out[val] = rng.permutation(de); out[~val] = rng.permutation(dh)
        mm = np.repeat(val, out)
        difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return float((difs >= real).mean())

def p_rotacion(m, r, n_perm=2000, semilla=0, excl=30):
    # rotacion circular de la mascara, desplazamiento en [excl, L-excl]
    real = np.median(r[m]) - np.median(r[~m]); L = len(m)
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm)
    for k, s in enumerate(rng.integers(excl, L - excl + 1, n_perm)):
        mm = np.roll(m, int(s)); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return float((difs >= real).mean())

def empalme_artificial(m, dias=30):
    # la rotacion une el final con el inicio: hay episodio artificial si hay dias activos
    # a ambos lados del empalme a menos de `dias` (misma regla de independencia del motor).
    # Depende de la mascara, no del desplazamiento: todas las rotaciones de esa mascara lo tienen.
    fin = np.flatnonzero(m[-dias:]); ini = np.flatnonzero(m[:dias])
    if len(fin) == 0 or len(ini) == 0: return False
    return bool((dias - 1 - fin.max()) + ini.min() + 1 <= dias)
