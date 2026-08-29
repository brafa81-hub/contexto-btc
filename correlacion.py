"""
CORRELACIÓN CON BOLSA — cuánta diversificación aporta BTC realmente.

QUÉ ES Y QUÉ NO ES
------------------
NO es una señal. No dice si comprar, ni cuándo, ni hacia dónde irá el precio.
Se midió y la macro no anticipa nada: la correlación de BTC con el Nasdaq es
0,23 el mismo día y −0,05 al día siguiente. Se mueven a la vez, no antes.

SÍ es información de dimensionamiento: si BTC se mueve con tus otras
inversiones, no diversifica, y eso cambia cuánto conviene exponer.

POR QUÉ ESTA SERIE Y NO OTRAS (medido el 29/08/2026)
-----------------------------------------------------
Se probaron cinco series macro de FRED contra 15 años de BTC. Correlación
contemporánea con retornos diarios, por épocas:

    Serie      2011-14  2015-17  2018-20  2021-23  2024-26
    nasdaq       -0.00     0.00     0.09     0.32     0.29
    dxy           0.01     0.02    -0.07    -0.18    -0.17
    vix          -0.01     0.01    -0.07    -0.26    -0.24
    bono10y      -0.02    -0.01     0.03    -0.01    -0.02
    tipo_fed     -0.03     0.04     0.05    -0.01    -0.01

Descartadas y por qué:
  - bono10y y tipo_fed: correlación nula en TODAS las épocas. No hay relación.
  - dxy: existe pero es débil (−0,17) y no anticipa nada.
  - vix: se solapa con nasdaq (−0,67 entre sí) y además, sumado a la propia
    volatilidad pasada de BTC, aporta solo +1,4 puntos de R² al predecir la
    volatilidad futura. Es doble conteo con poco valor añadido.

Se mantiene nasdaq porque es la más fuerte, la más estable desde 2018, y la
única con una consecuencia práctica clara.

EL HALLAZGO DE FONDO
--------------------
BTC se convirtió en activo macro y sigue siéndolo:

    2011-2017   correlación 180d media: -0.01
    2018-2020                            0.15
    2021-2023                            0.36
    2024-2026                            0.36

Es el patrón inverso al del Mayer Multiple (funcionaba y se rompió): aquí no
existía, apareció y lleva cinco años estable.

VALIDACIÓN DE LOS UMBRALES
--------------------------
Meses en que el Nasdaq cayó más de un 5% (2018-2026), según la correlación
vigente en ese momento:

    Correlación         n    BTC cayó también   mediana BTC
    baja  (<0.20)     123                 67%           -3%
    media (0.20-0.40) 127                 73%           -7%
    alta  (>0.40)     170                 89%          -14%

Monótono y con muestra suficiente en los tres tramos. Los cortes 0,20 y 0,40
no se eligieron a ojo: se comprobó que separan comportamientos distintos.
"""

import numpy as np
import pandas as pd

VENTANA = 180
CORTE_BAJA = 0.20
CORTE_ALTA = 0.40

# Percentiles de la distribución 2018-2026 (n=3.161 días), para situar el
# valor actual en su contexto histórico en vez de leerlo en abstracto.
PERCENTILES = {10: -0.00, 25: 0.13, 50: 0.31, 75: 0.44, 90: 0.52}

# Comportamiento observado en caídas del Nasdaq >5% en un mes, por tramo.
CAIDAS_CONJUNTAS = {
    "baja":  {"acompana": 67, "mediana": -3,  "n": 123},
    "media": {"acompana": 73, "mediana": -7,  "n": 127},
    "alta":  {"acompana": 89, "mediana": -14, "n": 170},
}


def cargar_macro(path: str) -> pd.DataFrame:
    """Carga el CSV que genera fetch_macro.py."""
    df = pd.read_csv(path)
    col = next((c for c in df.columns if c.lower() in ("date", "fecha")), df.columns[0])
    df[col] = pd.to_datetime(df[col], errors="coerce")
    df = df.set_index(col).sort_index()
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def calcular_correlacion(df_btc: pd.DataFrame, df_macro: pd.DataFrame) -> dict:
    """
    Correlación móvil de 180 días entre retornos diarios de BTC y Nasdaq.

    Los mercados cierran fines de semana y festivos, BTC no. Se rellena hacia
    adelante con un límite de 5 días: más allá de eso, el hueco es un fallo de
    datos y no un cierre de mercado, y arrastrarlo falsearía la correlación.
    """
    if "nasdaq" not in df_macro.columns:
        return {"disponible": False, "motivo": "falta la columna 'nasdaq'"}

    b = df_btc["close"]
    n = df_macro["nasdaq"].reindex(b.index).ffill(limit=5)

    rb = np.log(b / b.shift(1))
    rn = np.log(n / n.shift(1))
    corr = rb.rolling(VENTANA).corr(rn).dropna()

    if len(corr) < VENTANA:
        return {"disponible": False, "motivo": "histórico insuficiente"}

    actual = float(corr.iloc[-1])
    ref = corr.loc["2018":] if len(corr.loc["2018":]) > 200 else corr

    if actual < CORTE_BAJA:
        tramo, etiqueta = "baja", "Diversifica algo"
    elif actual < CORTE_ALTA:
        tramo, etiqueta = "media", "Diversifica poco"
    else:
        tramo, etiqueta = "alta", "Prácticamente no diversifica"

    return {
        "disponible": True,
        "correlacion": actual,
        "tramo": tramo,
        "etiqueta": etiqueta,
        "percentil": float((ref < actual).mean() * 100),
        "caidas": CAIDAS_CONJUNTAS[tramo],
        "media_1a": float(corr.iloc[-365:].mean()) if len(corr) >= 365 else np.nan,
        "fecha_dato": corr.index[-1],
    }


def texto_lectura(c: dict) -> str:
    """Frase única para mostrar en el panel, sin adornos ni alarmismo."""
    if not c.get("disponible"):
        return ""
    d = c["caidas"]
    return (
        f"Correlación con el Nasdaq (180 días): **{c['correlacion']:.2f}** — "
        f"{c['etiqueta'].lower()}. En los {d['n']} meses históricos con este "
        f"nivel de correlación en que el Nasdaq cayó más de un 5%, BTC cayó "
        f"también el {d['acompana']}% de las veces, con una mediana del "
        f"{d['mediana']}%."
    )


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    btc = load_price_csv(sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv")
    mac = cargar_macro(sys.argv[2] if len(sys.argv) > 2 else "macro.csv")
    c = calcular_correlacion(btc, mac)
    print(texto_lectura(c) if c["disponible"] else f"No disponible: {c['motivo']}")
