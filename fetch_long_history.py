"""
DESCARGA DE HISTÓRICO LARGO DE BTC (desde 2013-2014)

EJECUTAR EN TU ORDENADOR — este entorno no tiene acceso a estas APIs.

Binance solo tiene BTCUSDT desde agosto 2017. Para tener más historia (y por
tanto más muestra en el backtest, incluyendo el ciclo 2013-2015 con su caída
del ~85%), usamos otras fuentes.

FUENTES DISPONIBLES:

1. BITSTAMP (recomendada) — OHLC real desde 2011, gratis, sin API key.
   Es el exchange con más historia continua de BTC/USD.
   Ventaja: da velas OHLC de verdad (necesarias para calcular ATR y stops).

2. COINGECKO — desde 2013, gratis, sin API key para uso básico.
   Desventaja: el endpoint gratuito da un precio por día, NO velas OHLC.
   Eso hace que el ATR (y por tanto el stop dinámico) sea impreciso.
   Útil como comprobación cruzada, no como fuente principal.

USO:
    pip install requests
    python fetch_long_history.py --source bitstamp --out btc_long.csv
    python fetch_long_history.py --source coingecko --out btc_coingecko.csv

En Windows usa `python` (no `python3`).
"""

import argparse
import csv
import datetime as dt
import time

try:
    import requests
except ImportError:
    raise SystemExit("Falta 'requests'. Instala con: pip install requests")


def fetch_bitstamp(out="btc_long.csv", pair="btcusd"):
    """
    Bitstamp OHLC API. step=86400 (velas diarias), limit máximo 1000 por llamada.
    Paginamos hacia atrás desde hoy hasta 2011.
    """
    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/"
    step = 86400          # 1 día en segundos
    limit = 1000          # máximo permitido por llamada

    end_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())
    start_floor = int(dt.datetime(2011, 1, 1, tzinfo=dt.timezone.utc).timestamp())

    all_rows = {}
    cursor_end = end_ts

    while cursor_end > start_floor:
        cursor_start = cursor_end - (step * limit)
        params = {
            "step": step,
            "limit": limit,
            "start": max(cursor_start, start_floor),
            "end": cursor_end,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", {}).get("ohlc", [])
        except Exception as e:
            print(f"\nError en la descarga: {e}")
            break

        if not data:
            break

        for c in data:
            ts = int(c["timestamp"])
            date = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d")
            # Bitstamp a veces devuelve velas con volumen 0 y precios planos; se filtran
            if float(c["high"]) > 0 and float(c["low"]) > 0:
                all_rows[date] = [date, c["open"], c["high"], c["low"], c["close"]]

        oldest_ts = min(int(c["timestamp"]) for c in data)
        if oldest_ts >= cursor_end:
            break
        cursor_end = oldest_ts - step
        print(f"  ...descargado hasta {dt.datetime.fromtimestamp(oldest_ts, tz=dt.timezone.utc).date()}", end="\r")
        time.sleep(0.4)

    rows = [all_rows[k] for k in sorted(all_rows.keys())]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close"])
        w.writerows(rows)
    if rows:
        print(f"\nGuardado {len(rows)} filas en {out}")
        print(f"Rango: {rows[0][0]} a {rows[-1][0]}  (fuente: Bitstamp {pair.upper()})")
    else:
        print("\nNo se descargó ninguna fila. Prueba con --source coingecko.")


def fetch_coingecko(out="btc_coingecko.csv"):
    """
    CoinGecko market_chart/range. Da un precio por día (no OHLC real).
    AVISO: open=high=low=close. Sirve para medias y momentum,
    NO para ATR/stops precisos.
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
    start_ts = int(dt.datetime(2013, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    end_ts = int(dt.datetime.now(dt.timezone.utc).timestamp())

    r = requests.get(url, params={"vs_currency": "usd", "from": start_ts, "to": end_ts}, timeout=60)
    r.raise_for_status()
    prices = r.json().get("prices", [])

    daily = {}
    for ts_ms, price in prices:
        date = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d")
        daily[date] = price

    rows = [[d, p, p, p, p] for d, p in sorted(daily.items())]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close"])
        w.writerows(rows)
    print(f"Guardado {len(rows)} filas en {out}")
    if rows:
        print(f"Rango: {rows[0][0]} a {rows[-1][0]}  (fuente: CoinGecko)")
    print("AVISO: sin OHLC real (open=high=low=close). ATR y stops serán imprecisos.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["bitstamp", "coingecko"], default="bitstamp")
    p.add_argument("--out", default="btc_long.csv")
    p.add_argument("--pair", default="btcusd", help="Solo Bitstamp: btcusd, btceur")
    args = p.parse_args()

    if args.source == "bitstamp":
        fetch_bitstamp(out=args.out, pair=args.pair)
    else:
        fetch_coingecko(out=args.out)
