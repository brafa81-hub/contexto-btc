# Genera serie_liveliness_delta20.csv a partir del CSV bruto de BGeometrics.
# Uso: python serie_liveliness.py liveliness_raw.csv
# Fuente: https://bitcoin-data.com/v1/liveliness/csv (descargado 2026-09-21)
import sys, hashlib, pandas as pd
RAW_SHA = "ab4f61247a371822c6a965c57e375601031db0d378811cb4a2a45a2156f35e32"
raw = sys.argv[1] if len(sys.argv) > 1 else "liveliness_raw.csv"
if hashlib.sha256(open(raw, "rb").read()).hexdigest() != RAW_SHA:
    sys.exit("ABORTA: el CSV bruto no coincide con el anclado")
s = pd.read_csv(raw, encoding="latin-1").set_index("d")["liveliness"].astype(float)
dl = (s - s.shift(20)).dropna()   # calendario natural, sin huecos en origen
pd.DataFrame({"fecha": dl.index, "liveliness_delta20": dl.values}).to_csv(
    "serie_liveliness_delta20.csv", index=False, lineterminator="\n", float_format="%.8f")
print(hashlib.sha256(open("serie_liveliness_delta20.csv", "rb").read()).hexdigest())
