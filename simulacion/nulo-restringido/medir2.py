"""medir2.py — M1/M2 del nulo de rotacion restringida, mismo esquema que medir.py (precio real, mascaras sinteticas).
Uso: python3 medir2.py <escenario> <n>   -> r2_real_<escenario>.jsonl"""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
import motor, pipeline_end_to_end as pe, nulos2
from medir import replica, con_efecto, gates, NH
NIVELES = ['ruido_puro', 'efecto_medio', 'efecto_alto']

if __name__ == '__main__':
    esc, n = sys.argv[1], int(sys.argv[2])
    phi = pe.ESCENARIOS_PHI[esc]; base = 50000 + (0 if esc == 'uniforme' else 1_000_000)
    fn = f'r2_real_{esc}.jsonl'
    hechos = sum(1 for _ in open(fn)) if os.path.exists(fn) else 0
    fo = open(fn, 'a')
    for i in range(hechos, n):
        d = replica(base + i, phi, 'real'); f = d['fechas']; b2 = f[NH//2:NH]
        T_all = nulos2.tramos_vol(d['precio'])
        fila = {'i': i}
        for nv in NIVELES:
            ret = con_efecto(d, pe.NIVELES[nv], False)
            g = gates(d, ret)
            z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': ret.reindex(b2), 'T': T_all.reindex(b2)}).dropna()
            m = z['m'].values.astype(bool); r = z['r'].values; T = z['T'].values.astype(int)
            eps = motor.episodios_independientes(z.index[m], 30)
            x = {'g': g, 'suf': bool(m.sum() >= 20 and len(eps) >= 8)}
            if x['suf']:
                x['theta'] = float(np.median(r[m]) - np.median(r[~m]))
                x['pr'] = nulos2.p_restringida(m, r, T)
                d2 = dict(d); d2['ret'] = ret
                x['fwd'] = bool(pe.forward_de_replica({'_d': d2, 'theta_B2': x['theta']})['autoriza'])
            fila[nv] = x
        fo.write(json.dumps(fila) + '\n'); fo.flush()
