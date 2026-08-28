"""
Indicadores técnicos — Sistema de Exposición a BTC V1.0

Fórmulas EXACTAS según la especificación:
- SMA200 / SMA50: media móvil simple
- Pendiente SMA200: variación relativa de la SMA200 vs. hace N días (default 20)
- Momentum 6 meses: variación relativa del precio vs. hace 126 días (calculado
  para reporting, la especificación V1.0 NO lo usa en las reglas de entrada/salida)
- ATR(14): True Range de Wilder, diario y semanal
"""

import pandas as pd
import numpy as np


def sma(series: pd.Series, window: int) -> pd.Series:
    """Media móvil simple."""
    return series.rolling(window=window, min_periods=window).mean()


def sma_slope(sma_series: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Pendiente de una SMA: (SMA_hoy - SMA_hace_N_dias) / SMA_hace_N_dias.
    Positiva si > 0.
    """
    return (sma_series - sma_series.shift(lookback)) / sma_series.shift(lookback)


def momentum(close: pd.Series, lookback: int = 126) -> pd.Series:
    """
    Momentum: (precio_hoy / precio_hace_N_dias) - 1.
    Calculado para reporting/futuras versiones; V1.0 no lo usa en las reglas
    de entrada/salida (ver Especificación V1.0, sección 2 vs. secciones 3-4).
    """
    return (close / close.shift(lookback)) - 1.0


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """
    True Range de Wilder:
    max(high-low, |high-close_prev|, |low-close_prev|)
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    ATR de Wilder: media móvil simple del True Range para los primeros `window`
    valores, y después suavizado exponencial de Wilder:
    ATR_t = (ATR_{t-1} * (window-1) + TR_t) / window
    Este es el método estándar de Wilder (equivalente a un EMA con alpha=1/window).
    """
    tr = true_range(high, low, close)
    atr = tr.copy() * np.nan
    # Semilla: SMA de los primeros `window` TR válidos
    first_valid_idx = tr.first_valid_index()
    if first_valid_idx is None:
        return atr
    pos = tr.index.get_loc(first_valid_idx)
    if pos + window > len(tr):
        return atr
    seed = tr.iloc[pos:pos + window].mean()
    atr.iloc[pos + window - 1] = seed
    for i in range(pos + window, len(tr)):
        prev = atr.iloc[i - 1]
        atr.iloc[i] = (prev * (window - 1) + tr.iloc[i]) / window
    return atr


def resample_weekly_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte OHLC diario a semanal, cerrando semana en domingo (W-SUN).
    Requiere columnas: open, high, low, close (index = fecha diaria).
    """
    weekly = pd.DataFrame({
        "open": df["open"].resample("W-SUN").first(),
        "high": df["high"].resample("W-SUN").max(),
        "low": df["low"].resample("W-SUN").min(),
        "close": df["close"].resample("W-SUN").last(),
    })
    weekly = weekly.dropna(subset=["close"])
    return weekly


def compute_all_indicators(
    df: pd.DataFrame,
    sma_long: int = 200,
    sma_short: int = 50,
    slope_window: int = 20,
    atr_window: int = 14,
    momentum_window: int = 126,
) -> pd.DataFrame:
    """
    Calcula todos los indicadores diarios definidos en la Especificación V1.0
    y añade el ATR semanal (reindexado a diario, forward-filled dentro de cada
    semana) para el cálculo del stop dinámico.

    df debe tener columnas: open, high, low, close (index = fecha diaria, orden ascendente).
    """
    out = df.copy()
    out["sma200"] = sma(out["close"], sma_long)
    out["sma50"] = sma(out["close"], sma_short)
    out["sma200_slope"] = sma_slope(out["sma200"], slope_window)
    out["momentum_6m"] = momentum(out["close"], momentum_window)
    out["atr14_daily"] = atr_wilder(out["high"], out["low"], out["close"], atr_window)

    weekly = resample_weekly_ohlc(out)
    weekly["atr14_weekly"] = atr_wilder(weekly["high"], weekly["low"], weekly["close"], atr_window)

    # Reindexar el ATR semanal a diario: cada día "ve" el ATR semanal calculado
    # con el ÚLTIMO cierre semanal ya confirmado (evita look-ahead bias).
    atr_w_shifted = weekly["atr14_weekly"].shift(1)  # ATR de la semana anterior, disponible desde el lunes
    atr_w_current_week = weekly["atr14_weekly"]      # ATR de la semana en curso, solo disponible el domingo de cierre

    out["atr14_weekly"] = np.nan
    out["is_week_close"] = False
    week_end_dates = weekly.index
    for i, week_end in enumerate(week_end_dates):
        week_start = week_end - pd.Timedelta(days=6)
        mask = (out.index >= week_start) & (out.index <= week_end)
        if i > 0:
            out.loc[mask, "atr14_weekly"] = atr_w_shifted.iloc[i]
        if week_end in out.index:
            out.loc[week_end, "atr14_weekly"] = atr_w_current_week.iloc[i]
            out.loc[week_end, "is_week_close"] = True

    return out
