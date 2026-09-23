"""Prueba prerregistrada bandas bloque 06 (2026-09-23). Datos: bitstamp_api.csv sha256 a5ebd75a..."""
import numpy as np, pandas as pd, hashlib, json
assert hashlib.sha256(open("bitstamp_api.csv","rb").read()).hexdigest().startswith("a5ebd75a96e9859a")
df=pd.read_csv("bitstamp_api.csv",parse_dates=["date"]).set_index("date")
c=df.close.values; n=len(c); H=30
lr=np.log(df.close/df.close.shift(1))
vol=(lr.rolling(30).std()*np.sqrt(365)).values          # igual que rango.py
amp=np.full(n,np.nan); caida=np.full(n,np.nan)
for i in range(n-H):
    w=c[i:i+H+1]; amp[i]=w.max()/w.min()-1; caida[i]=1-w.min()/c[i]   # igual que regimen.py
S=np.sqrt(H/365)
R=np.log1p(amp)/(vol*S)                                  # movimiento log / volatilidad
fechas=df.index
ok=~np.isnan(R)

# ---------- PASO 1 ----------
rng=np.random.default_rng(20260923)
def boot_q(x,qs,B=2000,blk=90):
    m=len(x); out=np.empty((B,len(qs)))
    for b in range(B):
        k=int(np.ceil(m/blk)); st=rng.integers(0,m,k)
        idx=(st[:,None]+np.arange(blk)[None,:]).ravel()[:m]%m
        out[b]=np.quantile(x[idx],qs)
    return np.quantile(out,[0.025,0.975],axis=0)
epocas={"2011-15":("2011-01-01","2015-12-31"),"2016-20":("2016-01-01","2020-12-31"),"2021-26":("2021-01-01","2026-12-31")}
p1={}
for e,(a,b) in epocas.items():
    m=ok&(fechas>=a)&(fechas<=b); x=R[m]
    pt=np.quantile(x,[.75,.95]); ci=boot_q(x,[.75,.95])
    p1[e]={"n":int(m.sum()),"p75":pt[0],"p95":pt[1],"ci75":ci[:,0].tolist(),"ci95":ci[:,1].tolist()}
estable=True
for j,q in enumerate(["75","95"]):
    pts=[p1[e]["p"+q] for e in epocas]; cis=[p1[e]["ci"+q] for e in epocas]
    solape=max(ci[0] for ci in cis)<=min(ci[1] for ci in cis)
    ratio=max(pts)/min(pts)
    p1["crit_"+q]={"solapan":bool(solape),"max_min":ratio}
    estable&= solape and ratio<=1.25
p1["estable"]=bool(estable)

# ---------- PASO 2 (point-in-time, embargo 30d) ----------
tramos={"2016-18":("2016-01-01","2018-12-31"),"2019-20":("2019-01-01","2020-12-31"),
        "2021-23":("2021-01-01","2023-12-31"),"2024-26":("2024-01-01","2026-12-31")}
eval_idx=[t for t in range(n) if ok[t] and fechas[t]>=pd.Timestamp("2016-01-01")]
pred={k:np.full((n,2),np.nan) for k in "ABC"}
def wq(x,w,q):
    o=np.argsort(x); x,w=x[o],w[o]; cw=np.cumsum(w)/w.sum()
    return np.interp(q,cw,x)
for t in eval_idx:
    tr=np.arange(0,t-H+1); tr=tr[ok[tr]]          # origenes con rango ya conocido en t
    v=vol[tr]; a_=amp[tr]; r_=R[tr]
    cuts=np.quantile(v,[.25,.5,.75]); g=np.searchsorted(cuts,v,side="right"); gt=np.searchsorted(cuts,vol[t],side="right")
    pred["A"][t]=np.quantile(a_[g==gt],[.75,.95])
    pred["B"][t]=np.expm1(np.quantile(r_,[.75,.95])*vol[t]*S)
    w=0.5**((t-tr)/(3*365))
    pred["C"][t]=np.expm1(np.array([wq(r_,w,.75),wq(r_,w,.95)])*vol[t]*S)
def pin(y,q,tau): return np.where(y<=q,(1-tau)*(q-y),tau*(y-q))
res={}
for tn,(a,b) in tramos.items():
    m=np.array([ok[t] and a<=str(fechas[t].date())<=b for t in range(n)])
    y=amp[m]; cd=caida[m]; res[tn]={"n":int(m.sum())}
    for k in "ABC":
        q=pred[k][m]
        res[tn][k]={"cob75":float((y<=q[:,0]).mean()),"cob95":float((y<=q[:,1]).mean()),
                    "ancho75":float(q[:,0].mean()),"ancho95":float(q[:,1].mean()),
                    "perdida":float(pin(y,q[:,0],.75).mean()+pin(y,q[:,1],.95).mean()),
                    "cob_caida07":float((cd<=q[:,1]/2).mean())}
json.dump({"paso1":p1,"paso2":res},open("resultado_bandas.json","w"),indent=1,default=float)
print(json.dumps(p1,indent=1,default=lambda x:round(float(x),3)))
for tn in res:
    print(tn,res[tn]["n"])
    for k in "ABC":
        r=res[tn][k]; print(f"  {k} cob75 {r['cob75']:.3f} cob95 {r['cob95']:.3f} ancho75 {r['ancho75']:.3f} ancho95 {r['ancho95']:.3f} perdida {r['perdida']:.4f} cob_caida07 {r['cob_caida07']:.3f}")
