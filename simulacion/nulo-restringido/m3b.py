"""m3b.py — M3 (criterio modificado): mismos gemelos y recetas que m3.py; calibracion sin gates.
Calcula ambas colas para rotacion restringida (nueva), rotacion circular y episodios (recalculo).
Uso: python3 m3b.py <n>  -> m3b_gemelos.jsonl"""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
import motor, nulos2
from m3 import gemelo, construir, RECETAS
from medir import NH

def evaluar(d):
    b2 = d['fechas'][NH//2:NH]
    T_all = nulos2.tramos_vol(d['precio'])
    z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': d['ret'].reindex(b2), 'T': T_all.reindex(b2)}).dropna()
    m = z['m'].values.astype(bool); r = z['r'].values; T = z['T'].values.astype(int)
    eps = motor.episodios_independientes(z.index[m], 30)
    x = {'suf': bool(m.sum() >= 20 and len(eps) >= 8)}
    if x['suf']:
        x['pr'] = nulos2.p_restringida(m, r, T)
        x['rot'] = nulos2.p_rotacion2(m, r)
        x['epi'] = nulos2.p_episodios2(m, r)
    return x

if __name__ == '__main__':
    n = int(sys.argv[1]); fn = 'm3b_gemelos.jsonl'
    hechos = sum(1 for _ in open(fn)) if os.path.exists(fn) else 0
    fo = open(fn, 'a')
    for i in range(hechos, n):
        P = gemelo(700000 + i)
        fo.write(json.dumps({'i': i, **{rc: evaluar(construir(P, rc)) for rc in RECETAS}}) + '\n'); fo.flush()
