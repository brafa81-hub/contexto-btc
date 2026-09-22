"""m3.py — nulo con mascaras ligadas al precio pasado, sobre precios 'gemelos' de BTC:
misma volatilidad por fecha (sigma real 30d), mismas colas (|z| reales barajados),
misma deriva media, direccion diaria sorteada (+/-) -> el pasado no predice el futuro."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
import motor, pipeline_end_to_end as pe, nulos
from medir import gates, NH, NF
_P = pd.read_csv('btc_bitstamp_diario.csv', index_col=0, parse_dates=True).iloc[:, 0].astype(float)
lr = np.diff(np.log(_P.values)); mu = lr.mean()
sig = pd.Series(lr).rolling(30).std().bfill().values
za = np.abs((lr - mu) / sig)
za = za * np.std(lr - mu) / np.sqrt(np.mean((sig * za) ** 2))
PRE = 400
sig_ext = np.r_[sig[:PRE], sig]

def mascara(metr):
    q = metr.rolling(365, min_periods=365).quantile(0.8)
    return (metr > q).fillna(False)

RECETAS = {
    'delta20': lambda P: np.log(P).diff(20),
    'mayer':   lambda P: np.log(P / P.rolling(200).mean()),
    'vol30':   lambda P: np.log(P).diff().rolling(30).std(),
}

def gemelo(semilla):
    rng = np.random.default_rng(semilla)
    z = za[rng.integers(0, len(za), len(sig_ext))] * rng.choice([-1, 1], len(sig_ext))
    return np.exp(np.cumsum(mu + sig_ext * z)) * 100

def construir(P_arr, receta):
    n = NH + NF
    P_all = pd.Series(P_arr)
    m_all = mascara(RECETAS[receta](P_all))
    tot = len(P_all); ini = tot - (n + 30)
    f = pd.date_range('2015-01-01', periods=n + 30, freq='D')
    Pw = pd.Series(P_all.values[ini:], index=f)
    mw = pd.Series(m_all.values[ini:], index=f).astype(bool)
    fechas = f[:n]
    return {'fechas': fechas, 'precio': Pw.loc[fechas], 'mask': mw.loc[fechas],
            'ret': (Pw.shift(-30) / Pw - 1).loc[fechas].rename('retorno_N'),
            'fecha_corte_forward': fechas[NH - 1]}

def evaluar(d):
    b2 = d['fechas'][NH//2:NH]; ret = d['ret']
    try: g = gates(d, ret)
    except RuntimeError: g = (False, False, False)  # como en pipeline: gate no superado
    z = pd.DataFrame({'m': d['mask'].loc[b2], 'r': ret.reindex(b2)}).dropna()
    m = z['m'].values.astype(bool); r = z['r'].values
    eps = motor.episodios_independientes(z.index[m], 30)
    x = {'g': g, 'suf': bool(m.sum() >= 20 and len(eps) >= 8), 'act': float(d['mask'].mean())}
    if x['suf']:
        x['theta'] = float(np.median(r[m]) - np.median(r[~m]))
        x['p'] = {'epi': nulos.p_episodios(m, r), 'rot': nulos.p_rotacion(m, r)}
        x['empalme'] = nulos.empalme_artificial(m)
        x['fwd'] = bool(pe.forward_de_replica({'_d': d, 'theta_B2': x['theta']})['autoriza'])
    return x

if __name__ == '__main__':
    n = int(sys.argv[1])
    if sys.argv[1:2] and len(sys.argv) > 2 and sys.argv[2] == 'real':
        out = {}
        for rc in RECETAS:
            out[rc] = evaluar(construir(_P.values, rc))
        json.dump(out, open('m3_real_descriptivo.json', 'w'), indent=1); print(out); sys.exit()
    fn = 'm3_gemelos.jsonl'
    hechos = sum(1 for _ in open(fn)) if os.path.exists(fn) else 0
    fo = open(fn, 'a')
    for i in range(hechos, n):
        P = gemelo(700000 + i)
        fo.write(json.dumps({'i': i, **{rc: evaluar(construir(P, rc)) for rc in RECETAS}}) + '\n'); fo.flush()
