"""
ANÁLISIS ON-CHAIN — calcula e interpreta métricas fundamentales de BTC.

Trabaja sobre el CSV que genera fetch_onchain.py (CoinMetrics Community API).

FILOSOFÍA: igual que el resto del sistema, esto NO predice. Sitúa las métricas
actuales en su contexto histórico (percentiles) para responder:
"¿esto es normal, alto o bajo comparado con la historia de BTC?"
"""

import pandas as pd
import numpy as np


def cargar_onchain(path: str) -> pd.DataFrame:
    """Carga y prepara el CSV de datos on-chain."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Convertir a numérico (la API puede devolver strings o vacíos)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def calcular_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara las métricas para su uso.

    NOTA (28/08/2026): con la fuente anterior (CoinMetrics) calculábamos MVRV
    y Z-Score nosotros mismos a partir de Market Cap y Realized Cap. Con la
    fuente actual (BGeometrics/bitcoin-data.com) estas métricas ya vienen
    calculadas directamente por ellos — tienen su propio nodo Bitcoin y
    calculan MVRV desde datos on-chain crudos. Aquí solo las preparamos
    (tipos numéricos, medias móviles de salud de red).
    """
    out = df.copy()

    # Si por lo que sea faltan mvrv o mvrv_zscore pero SÍ tenemos market_cap
    # y realized_cap (columnas antiguas, por si se vuelve a otra fuente),
    # se calculan como fallback.
    if "mvrv" not in out.columns and "CapMrktCurUSD" in out.columns and "CapRealUSD" in out.columns:
        out["mvrv"] = out["CapMrktCurUSD"] / out["CapRealUSD"]
    if "mvrv_zscore" not in out.columns and "mvrv" in out.columns:
        diff = out.get("CapMrktCurUSD", pd.Series(dtype=float)) - out.get("CapRealUSD", pd.Series(dtype=float))
        std_expanding = out.get("CapMrktCurUSD", pd.Series(dtype=float)).expanding(min_periods=365).std()
        if not diff.empty:
            out["mvrv_zscore"] = diff / std_expanding

    # Hashrate: media de 30 días y su variación (si está disponible)
    if "hashrate" in out.columns:
        out["hashrate_ma30"] = out["hashrate"].rolling(30).mean()
        out["hashrate_change_60d"] = out["hashrate_ma30"].pct_change(60) * 100

    # Direcciones activas: media 30d y variación (si está disponible)
    if "active_addresses" in out.columns:
        out["adr_ma30"] = out["active_addresses"].rolling(30).mean()
        out["adr_change_60d"] = out["adr_ma30"].pct_change(60) * 100

    return out


def percentil_historico(serie: pd.Series, valor_actual: float) -> float:
    """Qué porcentaje de la historia estuvo por debajo del valor actual."""
    s = serie.dropna()
    if len(s) == 0 or pd.isna(valor_actual):
        return np.nan
    return (s < valor_actual).mean() * 100


def interpretar_mvrv_por_percentil(pct: float) -> tuple[str, str]:
    """
    Etiqueta del MVRV basada en SU PROPIO percentil histórico, calculado
    sobre la serie real de CoinMetrics — no en umbrales fijos copiados de
    un proveedor externo.

    POR QUÉ ESTE CAMBIO (agosto 2026):
    Al contrastar con fuentes citables se vio que Glassnode y CryptoQuant NO
    comparten una única tabla de umbrales:
      - Glassnode (bandas por frecuencia histórica): <0.8 / <1.0 / >2.4 / >3.2
      - Glassnode (guía general, otra métrica): >3.5 como señal de ciclo tardío
      - CryptoQuant: <1.0 posible fondo / >3.7 posible techo
    Mezclar 3.5 de una página con umbrales de otra metodología (que es lo que
    hacía la versión anterior de esta función) no es correcto.

    La propia Glassnode resuelve esto calibrando SUS bandas por frecuencia
    histórica (percentiles), no por un número fijo memorizado. Aplicamos el
    mismo principio aquí: usamos el percentil sobre NUESTRA serie (CoinMetrics),
    que es coherente con cómo ya tratamos el Mayer Multiple en contexto_btc.py.

    Los umbrales de Glassnode/CryptoQuant se muestran aparte, como referencia
    citada, en vez de fundirlos en esta etiqueta.
    """
    if pd.isna(pct):
        return "SIN DATOS", ""
    if pct >= 94:
        return "EUFORIA", "Entre el 6% de valores más altos de toda la historia de BTC"
    elif pct >= 80:
        return "OPTIMISMO ALTO", "Ganancias no realizadas elevadas para el estándar histórico"
    elif pct >= 35:
        return "ZONA MEDIA", "Dentro del rango habitual de su historia"
    elif pct >= 15:
        return "ZONA BAJA", "Más barato que la mayoría de su historia"
    else:
        return "CAPITULACIÓN", "Entre el 15% de valores más bajos de toda la historia de BTC"


# Umbrales fijos publicados por Glassnode y CryptoQuant, mostrados como
# referencia externa citada — NO se usan para calcular la etiqueta anterior.
# Fuentes: docs.glassnode.com/guides-and-tutorials/metric-guides/mvrv,
#          userguide.cryptoquant.com/es/market-data-indicators/mvrv-ratio
REFERENCIA_EXTERNA_MVRV = {
    "glassnode_bandas_frecuencia": {
        "extreme_lows": 0.8, "getting_low": 1.0, "getting_high": 2.4, "extremely_high": 3.2,
        "nota": "Calibradas para que ~5% de días históricos estén bajo 0.8, ~20% sobre 2.4",
    },
    "cryptoquant": {
        "posible_fondo": 1.0, "posible_techo": 3.7,
    },
}


def interpretar_mvrv(mvrv: float) -> tuple[str, str]:
    """
    ⚠ FUNCIÓN ANTIGUA, mantenida solo por compatibilidad.
    Usa umbrales fijos mezclados de distintas fuentes (ver aviso histórico
    abajo). Se recomienda usar interpretar_mvrv_por_percentil() en su lugar,
    que es la que usa ya generar_bloque_onchain().
    """
    if pd.isna(mvrv):
        return "SIN DATOS", ""
    if mvrv >= 3.5:
        return "EUFORIA", "Zona donde históricamente se han formado techos de ciclo"
    elif mvrv >= 2.5:
        return "OPTIMISMO ALTO", "Ganancias no realizadas elevadas, riesgo creciente"
    elif mvrv >= 1.5:
        return "ZONA MEDIA-ALTA", "Mercado en beneficio, sin extremos"
    elif mvrv >= 1.0:
        return "ZONA MEDIA-BAJA", "Beneficio moderado, cerca del coste medio del mercado"
    else:
        return "CAPITULACIÓN", "El mercado en agregado está en pérdidas — históricamente zona de suelo"


def interpretar_zscore(z: float) -> tuple[str, str]:
    """
    ⚠ Mismo aviso que interpretar_mvrv: umbrales (5/3/1/0) tomados de la
    literatura habitual, NO verificados contra la serie histórica en este
    proyecto. El percentil que se muestra junto al valor es más fiable.
    """
    if pd.isna(z):
        return "SIN DATOS", ""
    if z >= 5:
        return "EXTREMO ALTO", "Históricamente asociado a techos de ciclo"
    elif z >= 3:
        return "ALTO", "Valoración estirada respecto al coste base del mercado"
    elif z >= 1:
        return "NORMAL-ALTO", "Por encima de la media histórica"
    elif z >= 0:
        return "NORMAL-BAJO", "Por debajo de la media histórica"
    else:
        return "EXTREMO BAJO", "Históricamente asociado a suelos de ciclo"


def generar_bloque_onchain(df_onchain: pd.DataFrame, precio_actual: float = None) -> str:
    """
    Genera el bloque de texto con el análisis on-chain actual.
    precio_actual: si se pasa (recomendado), se usa el precio de Bitstamp del
    resto del sistema en vez de depender de una columna de precio propia del
    CSV on-chain, que la fuente actual (BGeometrics) no siempre incluye igual.
    """
    df = calcular_metricas(df_onchain)
    ultimo = df.iloc[-1]
    fecha = df.index[-1]

    mvrv = ultimo.get("mvrv", np.nan)
    z = ultimo.get("mvrv_zscore", np.nan)
    rp = ultimo.get("realized_price", np.nan)
    precio = precio_actual if precio_actual is not None else ultimo.get("PriceUSD", np.nan)

    _vacia = pd.Series(dtype=float)
    pct_mvrv = percentil_historico(df["mvrv"] if "mvrv" in df.columns else _vacia, mvrv)
    pct_z = percentil_historico(df["mvrv_zscore"] if "mvrv_zscore" in df.columns else _vacia, z)

    # Etiqueta basada en NUESTRO percentil (método principal, ver docstring)
    etiq_mvrv, nota_mvrv = interpretar_mvrv_por_percentil(pct_mvrv)

    L = []
    L.append("┌─ FUNDAMENTAL ON-CHAIN " + "─" * 43)
    L.append(f"│  (datos a {fecha.strftime('%d/%m/%Y')} — BGeometrics/bitcoin-data.com)")
    L.append("│")
    L.append(f"│  MVRV:                 {mvrv:>8.2f}   percentil {pct_mvrv:>3.0f}%")
    L.append(f"│    → {etiq_mvrv}")
    L.append(f"│      {nota_mvrv}")
    L.append("│")
    L.append(f"│  MVRV Z-Score:         {z:>8.2f}   percentil {pct_z:>3.0f}%")
    L.append("│")
    L.append(f"│  Precio realizado:     ${rp:>11,.0f}")
    L.append(f"│    (precio medio al que el mercado compró sus BTC)")
    if pd.notna(precio) and pd.notna(rp):
        dist = (precio / rp - 1) * 100
        L.append(f"│    Precio actual está {dist:+.0f}% sobre el precio realizado")
    L.append("│")
    L.append("│  Para comparar — umbrales fijos publicados (no usados en la")
    L.append("│  etiqueta de arriba, solo como referencia externa citada):")
    g = REFERENCIA_EXTERNA_MVRV["glassnode_bandas_frecuencia"]
    cq = REFERENCIA_EXTERNA_MVRV["cryptoquant"]
    L.append(f"│    Glassnode: <{g['extreme_lows']} extremo bajo · >{g['extremely_high']} extremo alto")
    L.append(f"│    CryptoQuant: <{cq['posible_fondo']} posible fondo · >{cq['posible_techo']} posible techo")
    L.append("│")

    # Salud de la red
    #
    # CORREGIDO (28/08/2026): antes se accedía con ultimo["adr_change_60d"],
    # que revienta con KeyError si el CSV no trae 'active_addresses' — que es
    # justo el caso con la fuente actual (BGeometrics no expone ese endpoint
    # con nombre confirmado, ver nota en fetch_onchain.py). Con .get() el
    # bloque simplemente omite esa línea en vez de tumbar el script.
    hr_chg = ultimo.get("hashrate_change_60d", np.nan)
    adr_chg = ultimo.get("adr_change_60d", np.nan)
    if pd.notna(hr_chg):
        estado_hr = "creciendo" if hr_chg > 2 else ("estable" if hr_chg > -2 else "cayendo")
        L.append(f"│  Hashrate (60d):       {hr_chg:>+7.1f}%   ({estado_hr})")
    if pd.notna(adr_chg):
        estado_adr = "creciendo" if adr_chg > 5 else ("estable" if adr_chg > -5 else "cayendo")
        L.append(f"│  Direcciones activas:  {adr_chg:>+7.1f}%   ({estado_adr})")

    L.append("└" + "─" * 66)
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_onchain.csv"
    df = cargar_onchain(path)
    print(generar_bloque_onchain(df))
