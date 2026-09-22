import json, numpy as np, motor
from scipy.stats import beta
SIG = {'delta20': 'sup', 'mayer': 'inf', 'vol30': 'inf'}
def cp(k, n):
    return (0.0 if k == 0 else beta.ppf(.025, k, n-k+1), 1.0 if k == n else beta.ppf(.975, k+1, n-k))
def pct(a): return f'{100*a:.1f}%'

print('== M3 (gemelos) — rechazo p<=0,05; no evaluable cuenta como no rechazo ==')
L = [json.loads(l) for l in open('m3b_gemelos.jsonl')]
print('replicas:', len(L))
for rc, cola in SIG.items():
    xs = [x[rc] for x in L if x[rc]['suf']]; n = len(xs)
    otra = 'inf' if cola == 'sup' else 'sup'
    ev = [x for x in xs if x['pr']['evaluable']]
    ne = n - len(ev)
    r_pr = sum(x['pr'][cola] <= .05 for x in ev) / n
    r_pr_ev = sum(x['pr'][cola] <= .05 for x in ev) / max(1, len(ev))
    r_pr_o = sum(x['pr'][otra] <= .05 for x in ev) / n
    print(f"{rc:8s} n_suf={n} | RESTR: esperada({cola})={pct(r_pr)} [solo evaluables {pct(r_pr_ev)}, n_ev={len(ev)}] contraria={pct(r_pr_o)} no_eval={pct(ne/n)} n_adm_mediana={np.median([x['pr']['n_adm'] for x in xs]):.0f}")
    for nul in ('rot', 'epi'):
        e = sum(x[nul][cola] <= .05 for x in xs) / n; o = sum(x[nul][otra] <= .05 for x in xs) / n
        print(f"{'':8s} {nul.upper()}: esperada({cola})={pct(e)} contraria={pct(o)} | cola sup={pct(sum(x[nul]['sup']<=.05 for x in xs)/n)}")

for esc in ('uniforme', 'concentrado'):
    try: R = [json.loads(l) for l in open(f'r2_real_{esc}.jsonl')]
    except FileNotFoundError: continue
    print(f'\n== {esc}: {len(R)} replicas ==')
    for nv in ('ruido_puro', 'efecto_medio', 'efecto_alto'):
        xs = [r[nv] for r in R]; n = len(xs)
        suf = [x for x in xs if x['suf']]
        ev = [x for x in suf if x['pr']['evaluable']]
        rej = sum(x['pr']['sup'] <= .05 for x in ev)
        # pipeline completo
        con = [x for x in ev if all(x['g'])]
        conf = 0
        for i in range(0, len(con), 12):
            lote = con[i:i+12]; acc = motor.benjamini_yekutieli({j: x['pr']['sup'] for j, x in enumerate(lote)}, 0.2)
            conf += sum(lote[j]['fwd'] for j in acc)
        lo, hi = cp(conf, n)
        print(f"{nv:13s} sin gates: rechazo={pct(rej/len(suf))} (k={rej}/{len(suf)}) no_eval={pct((len(suf)-len(ev))/len(suf))} | "
              f"pasan gates={len(con)} | CONFIRMADA={conf}/{n}={pct(conf/n)} IC95=[{pct(lo)},{pct(hi)}]")
