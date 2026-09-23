import requests, pandas as pd, time, hashlib
rows=[]; start=int(pd.Timestamp("2011-08-01",tz="UTC").timestamp())
while True:
    r=requests.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/",params={"step":86400,"limit":1000,"start":start},timeout=30).json()
    d=r["data"]["ohlc"]
    if not d: break
    rows+=d
    last=int(d[-1]["timestamp"])
    if last>=int(pd.Timestamp('2026-09-22',tz='UTC').timestamp()): break
    start=last+86400; time.sleep(0.5)
df=pd.DataFrame(rows).astype(float).drop_duplicates("timestamp").sort_values("timestamp")
df["date"]=pd.to_datetime(df.timestamp,unit="s").dt.strftime("%Y-%m-%d")
df=df[df.date<"2026-09-23"]  # excluir vela incompleta de hoy
df[["date","open","high","low","close"]].to_csv("bitstamp_api.csv",index=False)
print(len(df),df.date.iloc[0],df.date.iloc[-1])
print(hashlib.sha256(open("bitstamp_api.csv","rb").read()).hexdigest())
