"""
M2 GLOBAL — masa monetaria, la única macro sin probar.

POR QUÉ ESTA Y NO OTRA
----------------------
Ya se midió el tipo efectivo de los fondos federales y salió correlación
±0,03 con BTC en todas las épocas: nula. Pero el M2 es otra cosa. El tipo
de interés es el precio del dinero; el M2 es la cantidad. Son variables
distintas con mecanismos distintos, y el M2 es mucho más lento.

Esa lentitud importa: las variables lentas tienen más posibilidades de
anticipar que las rápidas. Todo lo que hemos rechazado hasta ahora fallaba
por lo mismo — correlación alta el mismo día, cero al día siguiente. Una
serie que se mueve en escala de meses no puede fallar de esa forma.

LA HIPÓTESIS CONCRETA A PROBAR
------------------------------
De las propuestas recibidas, una afirma que el M2 global adelanta a BTC
entre 10 y 12 semanas (70-84 días). Es una afirmación específica, con
número, y por tanto comprobable — a diferencia de "la liquidez importa",
que es cierto siempre y no se puede refutar.

Se probarán desfases de 0 a 180 días para ver si existe un pico alrededor
de esas 10-12 semanas o si el número está elegido a posteriori.

QUÉ SE DESCARGA
---------------
  M2SL            M2 de EEUU, mensual, desde 1959. La serie principal.
  WM2NS           M2 de EEUU, semanal. Más granular, empieza más tarde.
  M2REAL          M2 ajustado por inflación. Descuenta el efecto precios.
  WALCL           Balance de la Reserva Federal, semanal. Liquidez directa.

Se incluye el balance de la Fed porque es la parte de la liquidez que se
mueve más rápido y de forma más discrecional. Si algo del bloque "liquidez"
anticipa a BTC, es un candidato tan bueno como el M2.

LIMITACIÓN IMPORTANTE
---------------------
El M2 es mensual. Eso significa que en 15 años hay ~180 observaciones
reales, no 5.400. Al pasarlo a diario se está repitiendo el mismo valor
30 veces, y eso infla artificialmente cualquier correlación.

El análisis tendrá que usar ventanas no solapadas y contar observaciones
independientes de verdad — exactamente el error que casi se cuela con la
volatilidad a 90 días y que sí tumbó al funding rate.

FUENTE: FRED (Reserva Federal de St. Louis). Gratis, sin clave.

EJECUTAR:
    python fetch_m2.py --out m2.csv
"""

import argparse
import io
import time

try:
    import pandas as pd
    import requests
except ImportError:
    raise SystemExit("Faltan dependencias. Instala con: pip install pandas requests")


BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

SERIES = {
    "M2SL": "m2_eeuu",
    "WM2NS": "m2_semanal",
    "M2REAL": "m2_real",
    "WALCL": "balance_fed",
}


def fetch_serie(codigo: str, desde: str = "2010-01-01") -> pd.Series:
    """Descarga una serie de FRED. Misma lógica que fetch_macro.py."""
    r = requests.get(
        f"{BASE}?id={codigo}&cosd={desde}",
        timeout=45,
        headers={"User-Agent": "contexto-btc/1.0"},
    )
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))

    # FRED alterna entre "DATE" y "observation_date" según la versión.
    col_fecha = next(
        (c for c in df.columns if c.lower() in ("date", "observation_date")),
        df.columns[0],
    )
    col_valor = next((c for c in df.columns if c != col_fecha), None)
    if col_valor is None:
        raise ValueError(f"{codigo}: no se encontró columna de valores")

    return pd.Series(
        pd.to_numeric(df[col_valor], errors="coerce").values,
        index=pd.to_datetime(df[col_fecha], errors="coerce"),
        name=SERIES[codigo],
    ).dropna()


def fetch_m2(out: str = "m2.csv", desde: str = "2010-01-01") -> None:
    series = {}
    for codigo, nombre in SERIES.items():
        print(f"Descargando {codigo} ({nombre})...", end=" ", flush=True)
        try:
            s = fetch_serie(codigo, desde)
            series[nombre] = s
            print(f"{len(s)} obs, {s.index[0].date()} a {s.index[-1].date()}")
        except Exception as e:
            print(f"AVISO: falló ({type(e).__name__})")
        time.sleep(1)

    if not series:
        raise SystemExit(
            "\nNo se descargó ninguna serie. Comprueba la conexión o si FRED "
            "sigue sirviendo CSV en:\n  "
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL"
        )

    df = pd.DataFrame(series).sort_index()
    df.index.name = "date"
    df.to_csv(out)

    print(f"\nGuardado en {out}: {len(df)} filas, {len(df.columns)} series")

    # El dato clave no es cuántas filas hay, sino cuántas observaciones
    # INDEPENDIENTES. Con datos mensuales, 15 años son ~180, no 5.400.
    print("\nObservaciones reales por serie (esto es lo que limita el análisis):")
    for c in df.columns:
        s = df[c].dropna()
        if len(s) > 1:
            dias = (s.index[-1] - s.index[0]).days / max(len(s) - 1, 1)
            frec = ("mensual" if dias > 20 else
                    "semanal" if dias > 5 else "diaria")
            print(f"  {c:<14} {len(s):>5} obs · frecuencia {frec}")
    print("\nCon datos mensuales no hay miles de datos independientes, hay")
    print("unos cientos. El análisis lo tendrá en cuenta.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="m2.csv")
    p.add_argument("--desde", default="2010-01-01")
    args = p.parse_args()
    fetch_m2(out=args.out, desde=args.desde)
