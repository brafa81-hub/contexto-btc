"""
FUNDING RATE — descarga el histórico de futuros perpetuos de BTC.

QUÉ ES
------
En los futuros perpetuos, cada 8 horas los que están posicionados en un lado
pagan a los del otro. Si el funding es positivo, los largos pagan a los cortos:
hay más gente apostando a la subida y está dispuesta a pagar por mantenerse.

POR QUÉ PUEDE VALER LA PENA
---------------------------
A diferencia del índice de Miedo y Codicia —que se calcula a partir de la
volatilidad, el momentum y el volumen del propio BTC, y por tanto es el precio
reetiquetado con una palabra emocional— el funding rate es dinero real
posicionado. Es un dato independiente del precio, no una transformación de él.

La hipótesis a comprobar: funding muy positivo implica mucho apalancamiento
largo, y eso históricamente precede a liquidaciones en cascada.

PERO NO SE DA POR BUENO SIN MEDIRLO
------------------------------------
Esta serie pasa por el mismo filtro que tumbó al VIX, al dólar y al bono a
10 años:

  1. ¿Existe la relación, y es estable entre épocas?
  2. ¿ANTICIPA o solo acompaña? (si se desploma en d+1, no sirve)
  3. ¿Aporta algo sobre lo que ya sabemos por el propio precio de BTC?

Si no pasa las tres, se queda fuera. El VIX parecía obviamente relevante y
aportaba +1,4 puntos de R²; la intuición no basta.

LIMITACIÓN DE LA FUENTE
-----------------------
Binance publica funding desde 2019 (BTCUSDT perpetuo). Eso son ~7 años, que
cubren 2021 y el régimen actual pero no los ciclos anteriores. Suficiente para
medir, insuficiente para afirmar que algo es estable "en todas las épocas".

Si Binance bloquea la petición desde tu red (responde 403 o 451 en algunos
países), el script lo dirá claramente en vez de guardar un CSV vacío.

EJECUTAR:
    python fetch_funding.py --out funding.csv
"""

import argparse
import time

try:
    import pandas as pd
    import requests
except ImportError:
    raise SystemExit("Faltan dependencias. Instala con: pip install pandas requests")


URL = "https://fapi.binance.com/fapi/v1/fundingRate"
SIMBOLO = "BTCUSDT"
LIMITE = 1000  # máximo por petición


def fetch_funding(out: str = "funding.csv", desde: str = "2019-09-01") -> None:
    inicio = int(pd.Timestamp(desde).timestamp() * 1000)
    filas = []

    print(f"Descargando funding de {SIMBOLO} desde {desde}...")
    while True:
        try:
            r = requests.get(
                URL,
                params={"symbol": SIMBOLO, "startTime": inicio, "limit": LIMITE},
                timeout=30,
                headers={"User-Agent": "contexto-btc/1.0"},
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            if code in (403, 451):
                raise SystemExit(
                    f"\nBinance rechaza la petición (HTTP {code}). Suele ser un "
                    f"bloqueo geográfico o de red.\nAlternativas: probar con una "
                    f"conexión distinta, o usar Bybit/OKX como fuente."
                )
            raise SystemExit(f"\nError HTTP {code} al pedir datos a Binance.")
        except Exception as e:
            raise SystemExit(f"\nError de conexión: {type(e).__name__}: {e}")

        lote = r.json()
        if not lote:
            break

        filas.extend(lote)
        ultimo = lote[-1]["fundingTime"]
        if len(lote) < LIMITE:
            break
        inicio = ultimo + 1
        print(f"  ...{len(filas)} registros, hasta "
              f"{pd.to_datetime(ultimo, unit='ms').date()}")
        time.sleep(0.4)

    if not filas:
        raise SystemExit("No se descargó ningún dato. Revisa el símbolo o la fecha.")

    df = pd.DataFrame(filas)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")

    # El funding se paga cada 8 horas. Se agrega a diario (suma) para poder
    # cruzarlo con el precio diario sin desalinear nada.
    diario = (
        df.set_index("fundingTime")["fundingRate"]
        .resample("D").sum()
        .rename("funding")
    )
    diario.index.name = "date"
    diario.to_csv(out)

    print(f"\nGuardado {len(diario)} días en {out}")
    print(f"Rango: {diario.index[0].date()} a {diario.index[-1].date()}")
    print(f"Funding diario medio: {diario.mean()*100:.4f}%  "
          f"(anualizado ≈ {diario.mean()*365*100:.1f}%)")
    print(f"Días con funding negativo: {(diario < 0).mean()*100:.0f}%")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="funding.csv")
    p.add_argument("--desde", default="2019-09-01")
    args = p.parse_args()
    fetch_funding(out=args.out, desde=args.desde)
