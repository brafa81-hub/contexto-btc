"""equivalencia_46.py — test de equivalencia obligatorio de la enmienda 46.
Compara filtro.test_permutacion (salida_46/filtro.py + salida_46/v2.json) con nulos.p_rotacion
(simulacion/nulo-restringido/nulos.py): positivo vs p_rotacion(m, r); negativo vs p_rotacion(m, -r);
bilateral vs calculo independiente. Exige igualdad exacta. Casos: 60 mascaras AR(1) sinteticas
+ 4 mascaras de precio (Mayer, delta20, vol30, con huecos) sobre precio real, varios tamanos de bloque."""
import hashlib, importlib.util, json, sys
import numpy as np, pandas as pd

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
assert sha('nulos.py').startswith('fe957ced765e1a9f'), 'nulos.py distinto'
assert sha('btc_bitstamp_diario.csv').startswith('afcc5312b8922206'), 'precio distinto'
spec = importlib.util.spec_from_file_location('filtro46', 'salida_46/filtro.py')
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
import nulos
doc = json.load(open('salida_46/v2.json'))
P = pd.read_csv('btc_bitstamp_diario.csv', index_col=0, parse_dates=True).iloc[:, 0].astype(float)
ret = (P.shift(-30) / P - 1).rename('retorno_N')

def bil(m, r, n_perm=2000, semilla=0, excl=30):
    real = np.median(r[m]) - np.median(r[~m]); L = len(m)
    rng = np.random.default_rng(semilla); difs = np.empty(n_perm)
    for k, s in enumerate(rng.integers(excl, L - excl + 1, n_perm)):
        mm = np.roll(m, int(s)); difs[k] = np.median(r[mm]) - np.median(r[~mm])
    return float((np.abs(difs) >= abs(real)).mean())

casos = []
rng = np.random.default_rng(46)
for i in range(60):
    L = int(rng.integers(900, 2200)); ini = int(rng.integers(400, len(P) - L - 40))
    idx = P.index[ini:ini + L]; phi = rng.choice([0.9, 0.97, 0.99]); x = np.zeros(L)
    e = rng.standard_normal(L)
    for t in range(1, L): x[t] = phi * x[t-1] + e[t]
    casos.append((f'ar1_{i}', pd.Series(x > np.quantile(x, rng.uniform(0.7, 0.9)), index=idx)))
b2 = P.index[len(P) - 2200:len(P) - 60]
mayer = P / P.rolling(200).mean(); d20 = P / P.shift(20) - 1; v30 = np.log(P).diff().rolling(30).std()
for nom, s in [('mayer', mayer > mayer.rolling(365).quantile(0.8)), ('delta20', d20 > d20.rolling(365).quantile(0.8)),
               ('vol30', v30 < v30.rolling(365).quantile(0.2))]:
    casos.append((nom, s.loc[b2]))
h = casos[0][1].drop(casos[0][1].index[100:130])  # mascara con huecos de fechas
casos.append(('ar1_huecos', h))

res, fallos, evaluados = [], 0, 0
for nom, mask in casos:
    z = pd.DataFrame({'m': mask, 'r': ret.reindex(mask.index)}).dropna()
    m = z['m'].values.astype(bool); r = z['r'].values
    fila = {'caso': nom, 'L': len(m)}
    for signo in ('positivo', 'negativo', 'bilateral'):
        out = F.test_permutacion(mask, ret, doc, signo)
        if out.get('insuficiencia'): fila[signo] = 'insuficiente'; continue
        ref = {'positivo': lambda: nulos.p_rotacion(m, r), 'negativo': lambda: nulos.p_rotacion(m, -r),
               'bilateral': lambda: bil(m, r)}[signo]()
        ok = out['p_valor'] == ref; evaluados += 1; fallos += (not ok)
        fila[signo] = [out['p_valor'], ref, ok]
    res.append(fila)
open('equivalencia_46.json', 'w').write(json.dumps(res, sort_keys=True) + '\n')
print(f'{evaluados} comparaciones, {fallos} discrepancias, {sum(1 for f in res if f.get("positivo") == "insuficiente")} casos insuficientes')
sys.exit(1 if fallos or evaluados < 100 else 0)
