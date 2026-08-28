"""
SISTEMA DE CONTEXTO BTC — v1

NO predice. NO dice comprar ni vender.
Su trabajo es responder: "¿dónde estoy y qué riesgo estoy asumiendo?"

Cuatro bloques:
  1. SITUACIÓN — precio vs medias, volatilidad, posición en el rango histórico
  2. VALORACIÓN — dónde está BTC respecto a su propio historial (caro/normal/barato)
  3. RIESGO REAL — qué pasa con tu dinero si cae un 50%, 70%, 85%
  4. CONTEXTO DE CICLO — cuánto lleva subiendo/bajando, drawdown actual

Todo se calcula a partir del histórico de precios. Los datos on-chain
(MVRV, flujos ETF) se pueden introducir a mano si se tienen.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


# Caídas históricas de BTC.
# ORIGEN: se calculan directamente desde los datos cargados (ver
# calcular_caidas_historicas). NO están escritas a mano.
# Los periodos sí son elección nuestra (marcan los grandes ciclos bajistas).
PERIODOS_BAJISTAS = [
    ("2011-2012", "2011-01-01", "2012-12-31"),
    ("2013-2015", "2013-01-01", "2015-12-31"),
    ("2017-2018", "2017-01-01", "2019-06-30"),
    ("2021-2022", "2021-01-01", "2023-06-30"),
]


def calcular_caidas_historicas(df: pd.DataFrame) -> list:
    """
    Calcula la caída máxima real en cada ciclo bajista, a partir de los datos.
    Devuelve [(etiqueta, caida_pct), ...].

    NOTA: la caída depende de dónde empiece el histórico. Si el CSV empieza en
    agosto de 2011, el ciclo de 2011 aparecerá recortado (la caída real de ese
    año llegó a superar el -90% contando desde el máximo de junio).
    """
    close = df["close"]
    resultado = []
    for etiqueta, ini, fin in PERIODOS_BAJISTAS:
        sub = close.loc[ini:fin]
        if len(sub) < 30:
            continue
        dd = (sub / sub.cummax() - 1).min() * 100
        resultado.append((etiqueta, round(dd)))
    return resultado


def calcular_situacion(df: pd.DataFrame) -> dict:
    """Bloque 1: dónde está el precio respecto a sus referencias."""
    close = df["close"]
    precio = close.iloc[-1]

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    sma1000 = close.rolling(1000).mean().iloc[-1] if len(close) >= 1000 else np.nan

    # Volatilidad anualizada de los últimos 90 días vs histórica
    ret = close.pct_change()
    vol_actual = ret.tail(90).std() * np.sqrt(365) * 100
    vol_historica = ret.std() * np.sqrt(365) * 100

    # Máximo histórico y distancia a él
    ath = close.max()
    fecha_ath = close.idxmax()
    dist_ath = (precio / ath - 1) * 100

    return {
        "precio": precio,
        "sma50": sma50,
        "sma200": sma200,
        "sma1000": sma1000,
        "vs_sma50": (precio / sma50 - 1) * 100,
        "vs_sma200": (precio / sma200 - 1) * 100,
        "vs_sma1000": (precio / sma1000 - 1) * 100 if pd.notna(sma1000) else np.nan,
        "vol_actual": vol_actual,
        "vol_historica": vol_historica,
        "ath": ath,
        "fecha_ath": fecha_ath,
        "dist_ath": dist_ath,
    }


def calcular_valoracion(df: pd.DataFrame) -> dict:
    """
    Bloque 2: ¿está caro o barato respecto a su propia historia?
    Usa el "Mayer Multiple" (precio / SMA200), una métrica clásica y simple
    de BTC, y lo compara con su distribución histórica completa.

    ORIGEN DE LOS NÚMEROS:
    - El percentil SÍ se calcula sobre los datos reales cargados. Es un hecho
      aritmético, no una opinión: "en el X% de su historia estuvo más barato".
    - Los CORTES para las etiquetas (85/65/35/15) son elección nuestra, no
      derivada de ningún análisis. Poner "caro" en el percentil 85 en vez del
      80 o el 90 es arbitrario. Las etiquetas son una ayuda de lectura, no un
      veredicto: el número del percentil es lo que tiene valor informativo.
    """
    close = df["close"]
    sma200_serie = close.rolling(200).mean()
    mayer = (close / sma200_serie).dropna()
    mayer_actual = mayer.iloc[-1]

    percentil = (mayer < mayer_actual).mean() * 100

    if percentil >= 85:
        etiqueta = "HISTÓRICAMENTE CARO"
        nota = "Zona donde históricamente el riesgo de corrección ha sido mayor"
    elif percentil >= 65:
        etiqueta = "POR ENCIMA DE LA MEDIA"
        nota = "Más caro que la mayoría de su historia"
    elif percentil >= 35:
        etiqueta = "ZONA NORMAL"
        nota = "En línea con su comportamiento histórico habitual"
    elif percentil >= 15:
        etiqueta = "POR DEBAJO DE LA MEDIA"
        nota = "Más barato que la mayoría de su historia"
    else:
        etiqueta = "HISTÓRICAMENTE BARATO"
        nota = "Zona donde históricamente ha habido menos riesgo de caída adicional"

    return {
        "mayer_multiple": mayer_actual,
        "percentil": percentil,
        "etiqueta": etiqueta,
        "nota": nota,
    }


def calcular_ciclo(df: pd.DataFrame) -> dict:
    """Bloque 4: en qué momento del ciclo estamos."""
    close = df["close"]
    precio = close.iloc[-1]

    # Drawdown actual desde el máximo histórico
    running_max = close.cummax()
    dd_actual = (precio / running_max.iloc[-1] - 1) * 100

    # Cuánto lleva desde el último máximo histórico
    fecha_ath = close.idxmax()
    dias_desde_ath = (close.index[-1] - fecha_ath).days

    # Rentabilidad en distintos plazos
    def ret_dias(n):
        if len(close) > n:
            return (precio / close.iloc[-n - 1] - 1) * 100
        return np.nan

    return {
        "drawdown_actual": dd_actual,
        "dias_desde_ath": dias_desde_ath,
        "ret_30d": ret_dias(30),
        "ret_90d": ret_dias(90),
        "ret_365d": ret_dias(365),
    }


def calcular_riesgo(capital: float, precio_actual: float) -> dict:
    """
    Bloque 3: el más importante.
    Traduce "BTC es volátil" en números concretos sobre TU dinero.
    """
    escenarios = []
    for pct in [-30, -50, -70, -85]:
        valor_restante = capital * (1 + pct / 100)
        perdida = capital - valor_restante
        precio_implicito = precio_actual * (1 + pct / 100)
        # Cuánto tendría que subir después para recuperar
        subida_necesaria = (capital / valor_restante - 1) * 100
        escenarios.append({
            "caida_pct": pct,
            "precio_btc": precio_implicito,
            "valor_restante": valor_restante,
            "perdida": perdida,
            "subida_para_recuperar": subida_necesaria,
        })
    return {"capital": capital, "escenarios": escenarios}


def generar_informe(df: pd.DataFrame, capital: Optional[float] = None) -> str:
    """Genera el informe de contexto completo, legible."""
    s = calcular_situacion(df)
    v = calcular_valoracion(df)
    c = calcular_ciclo(df)

    L = []
    L.append("=" * 68)
    L.append(f"  CONTEXTO BTC — {df.index[-1].strftime('%d/%m/%Y')}")
    L.append("=" * 68)
    L.append("")

    # --- BLOQUE 1: SITUACIÓN ---
    L.append("┌─ 1. DÓNDE ESTÁ EL PRECIO " + "─" * 40)
    L.append(f"│  Precio actual:        ${s['precio']:>12,.0f}")
    L.append(f"│  Media 50 días:        ${s['sma50']:>12,.0f}   ({s['vs_sma50']:+.1f}%)")
    L.append(f"│  Media 200 días:       ${s['sma200']:>12,.0f}   ({s['vs_sma200']:+.1f}%)")
    if pd.notna(s["sma1000"]):
        L.append(f"│  Media 1000 días:      ${s['sma1000']:>12,.0f}   ({s['vs_sma1000']:+.1f}%)")
    L.append(f"│  Máximo histórico:     ${s['ath']:>12,.0f}   ({s['dist_ath']:+.1f}%)")
    L.append(f"│  Fecha del máximo:      {s['fecha_ath'].strftime('%d/%m/%Y'):>12}")
    L.append("│")
    L.append(f"│  Volatilidad (90d):    {s['vol_actual']:>6.0f}%  anualizada")
    L.append(f"│  Volatilidad histórica:{s['vol_historica']:>6.0f}%")
    L.append("└" + "─" * 66)
    L.append("")

    # --- BLOQUE 2: VALORACIÓN ---
    L.append("┌─ 2. ¿CARO O BARATO? (vs. su propia historia) " + "─" * 20)
    L.append(f"│  Precio / Media 200d:  {v['mayer_multiple']:.2f}")
    L.append(f"│  Percentil histórico:  {v['percentil']:.0f}%")
    L.append("│")
    L.append(f"│  → {v['etiqueta']}")
    L.append(f"│    {v['nota']}")
    L.append("│")
    L.append(f"│  Lectura: en el {v['percentil']:.0f}% de su historia, BTC estuvo más barato")
    L.append("│  que ahora en relación a su media de 200 días.")
    L.append("└" + "─" * 66)
    L.append("")

    # --- BLOQUE 4: CICLO ---
    L.append("┌─ 3. MOMENTO DEL CICLO " + "─" * 43)
    L.append(f"│  Caída desde máximos:  {c['drawdown_actual']:>+7.1f}%")
    L.append(f"│  Días desde el máximo: {c['dias_desde_ath']:>7.0f}")
    L.append("│")
    L.append(f"│  Rentabilidad 30 días: {c['ret_30d']:>+7.1f}%")
    L.append(f"│  Rentabilidad 90 días: {c['ret_90d']:>+7.1f}%")
    L.append(f"│  Rentabilidad 1 año:   {c['ret_365d']:>+7.1f}%")
    L.append("└" + "─" * 66)
    L.append("")

    # --- BLOQUE 3: RIESGO REAL ---
    if capital:
        r = calcular_riesgo(capital, s["precio"])
        L.append("┌─ 4. TU RIESGO REAL " + "─" * 46)
        L.append(f"│  Si inviertes {capital:,.0f}€ hoy:")
        L.append("│")
        L.append("│   Caída    BTC llegaría a    Te quedarían      Pierdes")
        L.append("│  " + "─" * 60)
        for e in r["escenarios"]:
            L.append(f"│   {e['caida_pct']:>4.0f}%    ${e['precio_btc']:>12,.0f}    "
                      f"{e['valor_restante']:>10,.0f}€   {e['perdida']:>10,.0f}€")
        L.append("│")
        L.append("│  Caídas REALES que ha tenido BTC en su historia:")
        for periodo, pct in calcular_caidas_historicas(df):
            valor = capital * (1 + pct / 100)
            L.append(f"│    {periodo:<12} {pct:>4}%  →  te quedarían {valor:>9,.0f}€")
        L.append("│")
        L.append("│  Pregunta honesta: ¿podrías ver esos números sin vender?")
        L.append("│  Si la respuesta es no, la cantidad es demasiado alta.")
        L.append("└" + "─" * 66)
        L.append("")

    L.append("─" * 68)
    L.append("Este informe describe la situación actual. NO predice el futuro")
    L.append("ni recomienda comprar o vender. Las decisiones son tuyas.")
    L.append("─" * 68)

    return "\n".join(L)


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    capital = float(sys.argv[2]) if len(sys.argv) > 2 else None

    df = load_price_csv(csv_path)
    print(generar_informe(df, capital))
