"""control_emparejado.py — M3 control emparejado con Mayer (parametros aprobados 22-sep-2026).
Por gemelo i (semilla 700000+i, mismos 1000 de M3): mascara Mayer en bloque evaluado; mascara de control =
rachas activas y huecos de ESA mascara barajados por separado (misma alternancia, mismo total), semilla 900000+i.
Nulo A sin cambios: nulos2.p_rotacion2 (2000 rotaciones, excl 30, semilla 0). Filtro: >=20 activos y >=8 episodios.
Uso: python3 control_emparejado.py <n> [procesos] -> control_emparejado.jsonl"""
import sys, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from multiprocessing import Pool
import motor, nulos, nulos2
from m3 import gemelo, construir
from medir import NH

def suf(idx, m):
    return bool(m.sum() >= 20 and len(motor.episodios_independientes(idx[m], 30)) >= 8)

def control(m, semilla):
    dur, val = nulos._rachas(m); out = dur.copy(); rng = np.random.default_rng(semilla)
    out[val] = rng.permutation(dur[val]); out[~val] = rng.permutation(dur[~val])
    return np.repeat(val, out)

def uno(i):
    d = construir(gemelo(700000 + i), 'mayer'); b2 = d['fechas'][NH//2:NH]
    z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': d['ret'].reindex(b2)}).dropna()
    m = z['m'].values.astype(bool); r = z['r'].values
    mc = control(m, 900000 + i)
    x = {'i': i, 'mayer': {'suf': suf(z.index, m)}, 'ctrl': {'suf': suf(z.index, mc)},
         'act': int(m.sum()), 'act_c': int(mc.sum())}
    if x['mayer']['suf']: x['mayer']['rot'] = nulos2.p_rotacion2(m, r)
    if x['ctrl']['suf']:  x['ctrl']['rot'] = nulos2.p_rotacion2(mc, r)
    return x

if __name__ == '__main__':
    n = int(sys.argv[1]); k = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    with Pool(k) as p, open('control_emparejado.jsonl', 'w') as fo:
        for x in p.imap(uno, range(n)): fo.write(json.dumps(x) + '\n'); fo.flush()
