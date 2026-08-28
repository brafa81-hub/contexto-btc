"""
Carga de datos de precio diario desde CSV.

Formato esperado del CSV (nombres de columna flexibles, ver COLUMN_ALIASES):
  date, open, high, low, close

Ejemplo mínimo:
  date,open,high,low,close
  2015-01-01,320.5,325.0,318.2,321.4
  ...

Fuentes recomendadas para obtener el CSV (a exportar/descargar por el usuario,
ya que este entorno no tiene acceso de red a exchanges):
  - Binance (spot klines diarias, BTCUSDT) vía script fetch_binance_data.py incluido
  - CoinGecko (histórico diario)
  - Yahoo Finance (BTC-USD) vía yfinance, ejecutado localmente
"""

import pandas as pd

COLUMN_ALIASES = {
    "date": ["date", "fecha", "timestamp", "time", "open_time"],
    "open": ["open", "apertura"],
    "high": ["high", "maximo", "máximo"],
    "low": ["low", "minimo", "mínimo"],
    "close": ["close", "cierre", "adj close", "adj_close"],
}


def _find_column(columns, aliases):
    lower_map = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def load_price_csv(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    resolved = {}
    for key, aliases in COLUMN_ALIASES.items():
        col = _find_column(raw.columns, aliases)
        if col is None:
            raise ValueError(
                f"No se encontró columna para '{key}' en el CSV. "
                f"Columnas disponibles: {list(raw.columns)}. "
                f"Nombres aceptados para '{key}': {aliases}"
            )
        resolved[key] = col

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[resolved["date"]]),
        "open": raw[resolved["open"]].astype(float),
        "high": raw[resolved["high"]].astype(float),
        "low": raw[resolved["low"]].astype(float),
        "close": raw[resolved["close"]].astype(float),
    })
    df = df.dropna(subset=["close"]).sort_values("date").drop_duplicates(subset="date")
    df = df.set_index("date")

    if len(df) < 250:
        raise ValueError(
            f"Solo hay {len(df)} filas de datos. Se necesitan al menos ~250 días "
            f"para que la SMA200 empiece a calcularse, y varios años para un backtest fiable."
        )
    return df
