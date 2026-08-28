"""
NIVELES CLAVE — zonas donde el precio ha reaccionado históricamente.

FILOSOFÍA (importante):
Este módulo NO dice "compra en el soporte". Dice "el precio ha reaccionado
varias veces en esta zona". Es información de contexto, igual que las medias.

Tres métodos independientes, cada uno mostrado por separado. NO se combinan
en un score ponderado, porque cualquier ponderación sería inventada y no
tenemos forma de validarla. Si tres métodos coinciden en una zona, lo verás
tú mirando; eso es más honesto que un número que finge precisión.

MÉTODO 1 — Pivotes de swing
  Un máximo de swing es un día cuyo precio es el más alto de una ventana
  centrada en él. Igual para mínimos. Es mecánico y objetivo: no hay
  parámetros de opinión, solo el tamaño de la ventana.

MÉTODO 2 — Volume Profile
  Divide el rango de precios en tramos y suma cuánto volumen se negoció en
  cada uno. Los tramos con más volumen son zonas donde mucha gente tiene
  posiciones — históricamente actúan como imán o como barrera.

  ⚠ LIMITACIÓN REAL: usamos volumen de UN solo exchange (Bitstamp). El
  volumen real de BTC está repartido entre decenas de exchanges y derivados.
  Esto es una aproximación, no el mapa completo del mercado.

MÉTODO 3 — Niveles de marcos temporales altos
  Máximos y mínimos de los últimos meses/años. Son los niveles que más
  observa el conjunto del mercado, precisamente por ser los más visibles.

TODOS LOS NIVELES SE EXPRESAN COMO ZONAS, NO COMO LÍNEAS.
Un soporte no es "74.312$", es "73.500-75.100$". El ancho de la zona se
deriva del ATR (volatilidad real del activo), no de un porcentaje inventado.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List


@dataclass
class Nivel:
    """Una zona de precio relevante."""
    centro: float
    minimo: float
    maximo: float
    tipo: str           # "soporte" o "resistencia"
    metodo: str         # de qué método salió
    toques: int         # cuántas veces el precio ha visitado la zona
    detalle: str

    def contiene(self, precio: float) -> bool:
        return self.minimo <= precio <= self.maximo

    def distancia_pct(self, precio: float) -> float:
        return (self.centro / precio - 1) * 100


def _atr_actual(df: pd.DataFrame, ventana: int = 14) -> float:
    """ATR reciente, usado para dimensionar el ancho de las zonas."""
    high, low, close = df["high"], df["low"], df["close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.tail(ventana * 3).rolling(ventana).mean().iloc[-1]


def pivotes_swing(df: pd.DataFrame, ventana: int = 10, meses: int = 12) -> List[dict]:
    """
    MÉTODO 1: encuentra máximos y mínimos de swing.

    Un pivote alto = el máximo del día es el mayor de los `ventana` días
    anteriores y posteriores. Objetivo y mecánico.
    """
    corte = df.index[-1] - pd.DateOffset(months=meses)
    sub = df.loc[corte:]
    if len(sub) < ventana * 2 + 1:
        return []

    pivotes = []
    highs, lows = sub["high"].values, sub["low"].values
    fechas = sub.index

    for i in range(ventana, len(sub) - ventana):
        ventana_h = highs[i - ventana:i + ventana + 1]
        ventana_l = lows[i - ventana:i + ventana + 1]
        if highs[i] == ventana_h.max():
            pivotes.append({"precio": highs[i], "fecha": fechas[i], "tipo": "resistencia"})
        if lows[i] == ventana_l.min():
            pivotes.append({"precio": lows[i], "fecha": fechas[i], "tipo": "soporte"})

    return pivotes


def agrupar_en_zonas(pivotes: List[dict], ancho: float, ancho_max: float = None) -> List[dict]:
    """
    Agrupa pivotes cercanos en zonas. Si tres máximos están a 74.100, 74.500
    y 74.900, no son tres resistencias: es una zona de resistencia.

    `ancho`     = distancia máxima entre dos pivotes consecutivos para unirlos.
    `ancho_max` = ancho total máximo de una zona. Sin este límite, una cadena
                  de pivotes escalonados se fusiona en una zona gigante e
                  inútil (encadenamiento). Por defecto, el doble de `ancho`.
    """
    if not pivotes:
        return []
    if ancho_max is None:
        ancho_max = ancho * 2

    ordenados = sorted(pivotes, key=lambda p: p["precio"])
    grupos = []
    grupo_actual = [ordenados[0]]

    for p in ordenados[1:]:
        cerca_del_anterior = p["precio"] - grupo_actual[-1]["precio"] <= ancho
        cabe_en_la_zona = p["precio"] - grupo_actual[0]["precio"] <= ancho_max
        if cerca_del_anterior and cabe_en_la_zona:
            grupo_actual.append(p)
        else:
            grupos.append(grupo_actual)
            grupo_actual = [p]
    grupos.append(grupo_actual)

    zonas = []
    for g in grupos:
        precios = [p["precio"] for p in g]
        tipos = [p["tipo"] for p in g]
        # El tipo dominante del grupo
        tipo = max(set(tipos), key=tipos.count)
        zonas.append({
            "centro": float(np.mean(precios)),
            "minimo": float(min(precios)),
            "maximo": float(max(precios)),
            "toques": len(g),
            "tipo": tipo,
            "ultima_fecha": max(p["fecha"] for p in g),
        })
    return zonas


def volume_profile(df: pd.DataFrame, meses: int = 12, n_tramos: int = 40) -> List[dict]:
    """
    MÉTODO 2: reparte el volumen entre tramos de precio.

    Si el CSV no tiene columna de volumen, devuelve lista vacía (no inventa
    datos). Bitstamp sí lo proporciona, pero nuestro fetch actual no lo guarda,
    así que esto se activará cuando se añada esa columna.
    """
    if "volume" not in df.columns:
        return []

    corte = df.index[-1] - pd.DateOffset(months=meses)
    sub = df.loc[corte:].dropna(subset=["volume"])
    if len(sub) < 30:
        return []

    lo, hi = sub["low"].min(), sub["high"].max()
    bordes = np.linspace(lo, hi, n_tramos + 1)
    volumen_por_tramo = np.zeros(n_tramos)

    # Reparte el volumen de cada día entre los tramos que cubre su rango
    for _, fila in sub.iterrows():
        idx_lo = np.searchsorted(bordes, fila["low"], side="right") - 1
        idx_hi = np.searchsorted(bordes, fila["high"], side="right") - 1
        idx_lo = max(0, min(idx_lo, n_tramos - 1))
        idx_hi = max(0, min(idx_hi, n_tramos - 1))
        n = idx_hi - idx_lo + 1
        volumen_por_tramo[idx_lo:idx_hi + 1] += fila["volume"] / n

    total = volumen_por_tramo.sum()
    if total == 0:
        return []

    resultado = []
    for i in range(n_tramos):
        resultado.append({
            "minimo": float(bordes[i]),
            "maximo": float(bordes[i + 1]),
            "centro": float((bordes[i] + bordes[i + 1]) / 2),
            "volumen_pct": float(volumen_por_tramo[i] / total * 100),
        })
    return sorted(resultado, key=lambda x: -x["volumen_pct"])


def niveles_marcos_altos(df: pd.DataFrame) -> dict:
    """
    MÉTODO 3: máximos y mínimos de periodos largos. Los niveles más visibles
    del mercado, y por eso mismo los más observados.
    """
    close, high, low = df["close"], df["high"], df["low"]
    hoy = df.index[-1]

    def rango(meses):
        corte = hoy - pd.DateOffset(months=meses)
        sub = df.loc[corte:]
        if len(sub) < 5:
            return None
        return {"maximo": float(sub["high"].max()), "minimo": float(sub["low"].min())}

    return {
        "3_meses": rango(3),
        "6_meses": rango(6),
        "1_año": rango(12),
        "2_años": rango(24),
        "historico": {"maximo": float(high.max()), "minimo": float(low.min())},
    }


def analizar_niveles(df: pd.DataFrame, meses: int = 12) -> dict:
    """Ejecuta los tres métodos y devuelve todo por separado, sin combinar."""
    precio = float(df["close"].iloc[-1])
    atr = _atr_actual(df)
    ancho_zona = atr * 1.5  # ancho derivado de la volatilidad real, no inventado

    # Método 1
    pivotes = pivotes_swing(df, ventana=10, meses=meses)
    zonas = agrupar_en_zonas(pivotes, ancho_zona, ancho_max=ancho_zona * 2)
    # Solo zonas con al menos 2 toques (una sola visita no hace un nivel)
    zonas_relevantes = [z for z in zonas if z["toques"] >= 2]

    # Una zona que engloba el precio actual no es soporte ni resistencia:
    # el precio ya está dentro. Se descarta para no confundir.
    zonas_relevantes = [z for z in zonas_relevantes
                         if not (z["minimo"] <= precio <= z["maximo"])]

    soportes = sorted([z for z in zonas_relevantes if z["maximo"] < precio],
                       key=lambda z: -z["centro"])[:4]
    resistencias = sorted([z for z in zonas_relevantes if z["minimo"] > precio],
                           key=lambda z: z["centro"])[:4]

    # Método 2
    vp = volume_profile(df, meses=meses)
    vp_top = vp[:5] if vp else []

    # Método 3
    marcos = niveles_marcos_altos(df)

    return {
        "precio": precio,
        "atr": float(atr),
        "ancho_zona": float(ancho_zona),
        "soportes": soportes,
        "resistencias": resistencias,
        "volume_profile": vp_top,
        "marcos_altos": marcos,
        "n_pivotes": len(pivotes),
    }


def informe_texto(df: pd.DataFrame, meses: int = 12) -> str:
    """Informe legible en texto de los niveles encontrados."""
    a = analizar_niveles(df, meses)
    precio = a["precio"]

    L = []
    L.append("┌─ NIVELES CLAVE " + "─" * 50)
    L.append(f"│  Precio actual: ${precio:,.0f}")
    L.append(f"│  Ancho de zona: ±${a['ancho_zona']/2:,.0f} (derivado del ATR, no inventado)")
    L.append("│")

    L.append("│  RESISTENCIAS (zonas por encima):")
    if a["resistencias"]:
        for z in a["resistencias"]:
            dist = (z["centro"] / precio - 1) * 100
            L.append(f"│    ${z['minimo']:>9,.0f} – ${z['maximo']:<9,.0f}  "
                      f"{dist:>+6.1f}%   {z['toques']} toques")
    else:
        L.append("│    (ninguna zona con 2+ toques por encima del precio)")
    L.append("│")

    L.append("│  SOPORTES (zonas por debajo):")
    if a["soportes"]:
        for z in a["soportes"]:
            dist = (z["centro"] / precio - 1) * 100
            L.append(f"│    ${z['minimo']:>9,.0f} – ${z['maximo']:<9,.0f}  "
                      f"{dist:>+6.1f}%   {z['toques']} toques")
    else:
        L.append("│    (ninguna zona con 2+ toques por debajo del precio)")
    L.append("│")

    m = a["marcos_altos"]
    L.append("│  RANGOS DE REFERENCIA:")
    for etiqueta, clave in [("3 meses", "3_meses"), ("1 año", "1_año"),
                             ("2 años", "2_años"), ("histórico", "historico")]:
        r = m.get(clave)
        if r:
            L.append(f"│    {etiqueta:<10} ${r['minimo']:>10,.0f}  –  ${r['maximo']:>10,.0f}")

    if a["volume_profile"]:
        L.append("│")
        L.append("│  ZONAS DE MÁS VOLUMEN (Bitstamp, aproximación):")
        for v in a["volume_profile"][:3]:
            L.append(f"│    ${v['minimo']:>9,.0f} – ${v['maximo']:<9,.0f}  {v['volumen_pct']:.1f}% del volumen")

    L.append("│")
    L.append("│  Estas zonas describen dónde ha reaccionado el precio antes.")
    L.append("│  No predicen que vaya a volver a reaccionar ahí.")
    L.append("└" + "─" * 66)
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    df = load_price_csv(path)
    print(informe_texto(df))
