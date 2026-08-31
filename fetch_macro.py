"""
DATOS MACRO — descarga las series con las que medir si afectan a BTC.

POR QUÉ ESTE SCRIPT
-------------------
Antes de añadir ninguna fuente macro al panel hay que comprobar si su
relación con BTC existe y si es estable. Igual que se hizo con el Mayer
Multiple (funcionaba hasta 2020, se rompió en 2021) y con la persistencia
de volatilidad (estable a 30 días, inestable a 90).

Este script solo trae los datos. El análisis viene después, y si una serie
no demuestra relación medible con BTC, no entra en el panel.

FUENTE: FRED (Reserva Federal de St. Louis)
  - Gratis, sin registro, sin clave de API
  - Endpoint CSV directo, series diarias
  - Es fuente primaria: publica los datos oficiales, no los reinterpreta

SERIES ELEGIDAS Y POR QUÉ
-------------------------
  NASDAQCOM   Nasdaq Composite. BTC lleva años correlacionando con tecnología;
              esta serie permite comprobar si sigue siendo cierto.
  DTWEXBGS    Índice del dólar (amplio). Relación históricamente inversa.
  DGS10       Bono EEUU a 10 años. Termómetro del apetito por riesgo.
  VIXCLS      VIX. Miedo en renta variable — sirve para ver si el estrés
              se contagia a BTC o si BTC tiene su propio ciclo de miedo.
  DFF         Tipo efectivo de los fondos federales. El precio del dinero.

QUÉ NO ESTÁ AQUÍ Y POR QUÉ
--------------------------
No hay ninguna serie de "geopolítica" en FRED con actualización diaria
fiable. El índice más citado (Geopolitical Risk Index de Caldara e
Iacoviello, policyuncertainty.com) se publica con retraso y su versión
diaria es más ruido que señal para un sistema de revisión semanal.

Sí hay un sustituto medible: el VIX ya recoge buena parte del estrés
geopolítico en el momento en que el mercado lo descuenta, que es lo único
que importa aquí. Un conflicto que no mueve el VIX tampoco mueve a BTC.

EJECUTAR:
    python fetch_macro.py --out macro.csv
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
    "NASDAQCOM": "nasdaq",
    "DTWEXBGS": "dxy",
    "DGS10": "bono10y",
    "VIXCLS": "vix",
    "DFF": "tipo_fed",
}


def fetch_serie(codigo: str, desde: str = "2011-01-01") -> pd.Series:
    """Descarga una serie diaria de FRED en formato CSV."""
    url = f"{BASE}?id={codigo}&cosd={desde}"
    r = requests.get(url, timeout=45, headers={"User-Agent": "contexto-btc/1.0"})
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text))

    # FRED cambió el nombre de la columna de fecha entre versiones:
    # antes "DATE", ahora "observation_date". Se acepta cualquiera de las dos
    # en vez de asumir una, que es como se rompen los scripts en silencio.
    col_fecha = next(
        (c for c in df.columns if c.lower() in ("date", "observation_date")),
        df.columns[0],
    )
    col_valor = next((c for c in df.columns if c != col_fecha), None)
    if col_valor is None:
        raise ValueError(f"{codigo}: no se encontró columna de valores")

    s = pd.Series(
        pd.to_numeric(df[col_valor], errors="coerce").values,
        index=pd.to_datetime(df[col_fecha], errors="coerce"),
        name=SERIES[codigo],
    )
    return s.dropna()


def fetch_macro(out: str = "macro.csv", desde: str = "2011-01-01") -> None:
    series = {}
    for codigo, nombre in SERIES.items():
        print(f"Descargando {codigo} ({nombre})...", end=" ", flush=True)
        try:
            s = fetch_serie(codigo, desde)
            series[nombre] = s
            print(f"{len(s)} filas, {s.index[0].date()} a {s.index[-1].date()}")
        except Exception as e:
            print(f"AVISO: falló ({type(e).__name__}: {e})")
        time.sleep(1)

    if not series:
        raise SystemExit(
            "\nNo se descargó ninguna serie. Comprueba tu conexión o si FRED "
            "sigue sirviendo CSV en:\n  "
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NASDAQCOM"
        )

    df = pd.DataFrame(series).sort_index()
    df.index.name = "date"
    df.to_csv(out)

    print(f"\nGuardado en {out}: {len(df)} filas, {len(df.columns)} series")
    print(f"Rango: {df.index[0].date()} a {df.index[-1].date()}")

    # Comprobación de cobertura: una serie que llega mayormente vacía es
    # peor que una que falta, porque pasa desapercibida.
    print("\nCobertura por serie:")
    for c in df.columns:
        pct = df[c].notna().mean() * 100
        marca = "ok " if pct >= 60 else "AVISO"
        print(f"  [{marca}] {c}: {df[c].notna().sum()} valores ({pct:.0f}% de las filas)")
    print("\nLos huecos son normales: los mercados cierran fines de semana y "
          "festivos, BTC no. El análisis los alinea.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="macro.csv")
    p.add_argument("--desde", default="2011-01-01")
    args = p.parse_args()
    fetch_macro(out=args.out, desde=args.desde)
