"""medir.py — M1/M2/M4. Por replica (una mascara): gates por separado, p-valor con 3 nulos,
theta_B2 realizado, forward. Todo sin tocar filtro.py/v2.json/registro.json."""
import sys, os, json, time; sys.path.insert(0, '.')
import numpy as np, pandas as pd
import generador as gen, motor, pipeline_end_to_end as pe, nulos
_ORIG = gen.generar_replica
_P = pd.read_csv('btc_bitstamp_diario.csv', index_col=0, parse_dates=True).iloc[:, 0].astype(float)
NH, NF = 4260, 455

def replica(semilla, phi, fuente):
    d = _ORIG(semilla=semilla, n_historico=NH, n_forward_dias=NF, phi=phi, theta_nominal=0.0)
    f = d['fechas']; n = len(f)
    if fuente == 'real':
        pe_ = pd.Series(_P.values[-(n+30):], index=pd.date_range(f[0], periods=n+30, freq='D'))
        d['precio'] = pe_.loc[f]; d['ret'] = (pe_.shift(-30)/pe_ - 1).loc[f].rename('retorno_N')
    return d

def con_efecto(d, theta, norm):
    ret = d['ret'].copy(); m = d['mask']
    if theta: ret[m] = ret[m] + theta
    if norm:  # normalizado por volatilidad conocida en t (30d, escalada a 30 dias)
        sig = d['precio'].pct_change().rolling(30).std() * np.sqrt(30)
        ret = ret / sig
    return ret.rename('retorno_N')

def gates(d, ret):
    idx = d['fechas'][:NH]; b1 = idx[:NH//2]; m1 = d['mask'].loc[b1]; P = d['precio']
    g1 = motor.gate1(m1, ret, motor.tramos_de(b1, 4), N=30, semilla=7, n_rotaciones=200, percentil=90, min_obs_tramo=2)
    base = pd.DataFrame({'mayer': P/P.rolling(200).mean(), 'vol30': P.pct_change().rolling(30).std(), 'mom30': P/P.shift(30)-1})
    g3 = motor.gate3(m1, ret, base, N=30, semilla=7, n_rotaciones=200, percentil=90, minimo=5)
    ok1 = bool(g1['pasa'] and not g1.get('no_evaluable') and not g1['insuficiencia'])
    ok4 = bool(motor.gate4(g1['correlaciones_por_tramo'])['pasa']) if not g1.get('no_evaluable') else False
    ok3 = bool(g3['pasa'] and not g3['insuficiencia'])
    return ok1, ok3, ok4

if __name__ == '__main__':
    modo, fuente, esc, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    niveles = sys.argv[5].split(',')
    phi = pe.ESCENARIOS_PHI[esc]; base = 50000 + (0 if esc == 'uniforme' else 1_000_000)
    fn = f'{modo}_{fuente}_{esc}.jsonl'
    hechos = sum(1 for _ in open(fn)) if os.path.exists(fn) else 0
    fo = open(fn, 'a')
    for i in range(hechos, n):
        d = replica(base+i, phi, fuente); f = d['fechas']; b2 = f[NH//2:NH]
        fila = {'i': i}
        for nv in niveles:
            th = pe.NIVELES[nv]
            if modo == 'm4':   # gates por separado, crudo y normalizado
                fila[nv] = {'crudo': gates(d, con_efecto(d, th, False)), 'norm': gates(d, con_efecto(d, th, True))}
                continue
            ret = con_efecto(d, th, False)
            g = gates(d, ret)
            z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': ret.reindex(b2)}).dropna()
            m = z['m'].values.astype(bool); r = z['r'].values
            eps = motor.episodios_independientes(z.index[m], 30)
            suf = bool(m.sum() >= 20 and len(eps) >= 8)
            x = {'g': g, 'suf': suf, 'eps': len(eps)}
            if suf:
                x['theta'] = float(np.median(r[m]) - np.median(r[~m]))
                x['p'] = {'cont': nulos.p_contiguo(m, r), 'epi': nulos.p_episodios(m, r), 'rot': nulos.p_rotacion(m, r)}
                x['empalme'] = nulos.empalme_artificial(m)
                d2 = dict(d); d2['ret'] = ret
                x['fwd'] = bool(pe.forward_de_replica({'_d': d2, 'theta_B2': x['theta']})['autoriza'])
            fila[nv] = x
        fo.write(json.dumps(fila) + '\n'); fo.flush()
