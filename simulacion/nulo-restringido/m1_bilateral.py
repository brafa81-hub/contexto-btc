"""m1_bilateral.py — M1 bilateral del nulo A (regla fijada 22-sep-2026 antes de medir: 3-7% en ambos escenarios).
Mismas replicas de ruido que M1 (medir.replica, fuente real, theta=0, semillas 50000+i / 1050000+i).
Nulo A identico a nulos.p_rotacion (2000 rotaciones, excl 30, semilla 0). Devuelve sup, inf y bil=|difs|>=|real|.
Uso: python3 m1_bilateral.py <escenario> <n> [procesos] -> m1bil_<escenario>.jsonl"""
import sys, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from multiprocessing import Pool
import motor, pipeline_end_to_end as pe
from medir import replica, NH

def colas(m, r, n_perm=2000, semilla=0, excl=30):
    real = np.median(r[m]) - np.median(r[~m]); L = len(m)
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm)
    for k, s in enumerate(rng.integers(excl, L - excl + 1, n_perm)):
        mm = np.roll(m, int(s)); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return {'sup': float((difs >= real).mean()), 'inf': float((difs <= real).mean()),
            'bil': float((np.abs(difs) >= abs(real)).mean())}

ESC = sys.argv[1]

def uno(i):
    d = replica(50000 + (0 if ESC == 'uniforme' else 1_000_000) + i, pe.ESCENARIOS_PHI[ESC], 'real')
    b2 = d['fechas'][NH//2:NH]
    z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': d['ret'].reindex(b2)}).dropna()
    m = z['m'].values.astype(bool); r = z['r'].values
    suf = bool(m.sum() >= 20 and len(motor.episodios_independientes(z.index[m], 30)) >= 8)
    x = {'i': i, 'suf': suf}
    if suf: x.update(colas(m, r))
    return x

if __name__ == '__main__':
    n = int(sys.argv[2]); k = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    with Pool(k) as p, open(f'm1bil_{ESC}.jsonl', 'w') as fo:
        for x in p.imap(uno, range(n)): fo.write(json.dumps(x) + '\n'); fo.flush()
