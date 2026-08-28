"""
DATOS ON-CHAIN DE BITCOIN — CoinMetrics Community API

API pública y gratuita, sin API key, con historial desde 2010-2014 según métrica.
Documentación: https://docs.coinmetrics.io/api/v4

MÉTRICAS QUE USAMOS:
  CapMrktCurUSD  → Market Cap (valor de mercado actual)
  CapRealUSD     → Realized Cap (valor "realizado": cada BTC valorado al precio
                   de su última transacción, no al precio actual)
  SplyCur        → Supply circulante
  HashRate       → Hashrate de la red
  AdrActCnt      → Direcciones activas

DE AHÍ CALCULAMOS:
  MVRV = Market Cap / Realized Cap
     > 3.5  históricamente zona de euforia/techo
     < 1.0  históricamente zona de suelo/capitulación

  MVRV Z-Score = (Market Cap - Realized Cap) / desviación estándar del Market Cap
     Versión normalizada, mejor para comparar entre ciclos.

  Realized Price = Realized Cap / Supply
     "Precio medio al que el mercado compró sus BTC". Actúa como soporte
     psicológico importante en mercados bajistas.

EJECUTAR EN TU ORDENADOR:
    python fetch_onchain.py --out btc_onchain.csv
"""

import argparse
import csv
import datetime as dt

try:
    import requests
except ImportError:
    raise SystemExit("Falta 'requests'. Instala con: pip install requests")


BASE_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"

METRICAS = [
    "CapMrktCurUSD",   # Market cap
    "CapRealUSD",      # Realized cap
    "SplyCur",         # Supply circulante
    "HashRate",        # Hashrate
    "AdrActCnt",       # Direcciones activas
    "PriceUSD",        # Precio de referencia de CoinMetrics
]


def fetch_onchain(out="btc_onchain.csv", start="2011-01-01"):
    """Descarga métricas on-chain de BTC paginando hasta el presente."""
    all_rows = []
    next_page_token = None
    page = 0

    while True:
        params = {
            "assets": "btc",
            "metrics": ",".join(METRICAS),
            "frequency": "1d",
            "start_time": start,
            "page_size": 10000,
        }
        if next_page_token:
            params["next_page_token"] = next_page_token

        try:
            r = requests.get(BASE_URL, params=params, timeout=60)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            print(f"\nError descargando datos: {e}")
            break

        data = payload.get("data", [])
        if not data:
            break

        all_rows.extend(data)
        page += 1
        print(f"  ...página {page}, {len(all_rows)} registros acumulados", end="\r")

        next_page_token = payload.get("next_page_token")
        if not next_page_token:
            break

    if not all_rows:
        print("\nNo se descargó ningún dato.")
        return

    # Escribir CSV
    campos = ["date"] + METRICAS
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(campos)
        for row in all_rows:
            fecha = row.get("time", "")[:10]
            valores = [row.get(m, "") for m in METRICAS]
            w.writerow([fecha] + valores)

    print(f"\nGuardado {len(all_rows)} filas en {out}")
    print(f"Rango: {all_rows[0].get('time','')[:10]} a {all_rows[-1].get('time','')[:10]}")
    print("Fuente: CoinMetrics Community API (gratuita)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="btc_onchain.csv")
    p.add_argument("--start", default="2011-01-01")
    args = p.parse_args()
    fetch_onchain(out=args.out, start=args.start)
