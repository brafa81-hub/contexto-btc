"""
ETIQUETA DE RÉGIMEN DE VOLATILIDAD (Bajo / Normal / Elevado) — ventana móvil 6 años.

QUÉ ES Y QUÉ NO
----------------
Es una etiqueta DESCRIPTIVA: sitúa la volatilidad de hoy frente a los
últimos 6 años, nada más. NO determina las bandas de precio del bloque 06
(rango.py) — esas siguen usando el histórico completo 2011-2026 con la
tabla de 4 grupos fija. Las dos cosas conviven porque responden a
preguntas distintas: "¿es esto normal ÚLTIMAMENTE?" (esta etiqueta) frente
a "¿cuánto suele moverse el precio en un mes con esta volatilidad, en
toda la historia disponible?" (rango.py).

POR QUÉ SUSTITUYE A LA ETIQUETA DE 4 GRUPOS DE rango.py
---------------------------------------------------------
regimen.py (auditoría del bloque 06) ya documentó que los 4 grupos fijos
de rango.py, calibrados sobre 2011-2026, han dejado de repartir bien los
días recientes: en 2025-2026 el 57% de los días cae en "muy baja". Una
etiqueta que sale casi siempre igual no informa. Esta etiqueta nueva NO
sustituye los grupos de rango.py (que siguen existiendo para elegir la
fila de bandas de precio) — sustituye SOLO lo que el usuario ve.

POR QUÉ VENTANA MÓVIL DE 6 AÑOS Y NO OTRA
-------------------------------------------
Decisión explícita de Rafa (2026-09-23), tras descartar: todo el histórico
(sesga por 2011-2014, volatilidad estructuralmente alta), 2 ciclos de
halving cerrados (ignora 2024-2026) y ventana anclada a halving (salto
brusco cada ~4 años). 6 años (~1,5 ciclos de halving) se recalcula cada
día como [hoy − 6 años, hoy], ambos extremos incluidos.

REPRODUCIBILIDAD: POR QUÉ SE GUARDAN LOS UMBRALES DIARIOS
-------------------------------------------------------------
Una ventana móvil pierde reproducibilidad exacta si solo se guarda el
valor de vol30 del día: para reconstruir la etiqueta de una fecha pasada
hace falta saber también los dos umbrales (terciles) vigentes ESE día,
que dependen de qué 6 años de historia había disponibles entonces. Por
eso cada ejecución debe registrar una fila en el CSV de histórico de
umbrales (ver `registrar_umbrales_dia`). Este módulo no escribe ese CSV
por sí solo desde el panel (Streamlit Cloud no persiste ficheros): lo
hace un paso dedicado en el workflow diario de GitHub Actions.
"""

import numpy as np
import pandas as pd

VENTANA_ANOS = 6
ETIQUETAS = ["Bajo", "Normal", "Elevado"]

COLUMNAS_HISTORICO = ["fecha", "vol30", "umbral_bajo_normal",
                      "umbral_normal_elevado", "n_ventana", "etiqueta"]


def volatilidad_30d(df: pd.DataFrame) -> pd.Series:
    """Serie completa de volatilidad anualizada a 30 días (no solo el último dato)."""
    r = np.log(df["close"] / df["close"].shift(1))
    return r.rolling(30).std() * np.sqrt(365)


def calcular_umbrales(serie_vol: pd.Series, fecha: pd.Timestamp) -> dict:
    """
    Terciles de la ventana [fecha - 6 años, fecha], ambos extremos incluidos,
    sobre la serie de volatilidad ya calculada. Determinista: mismo input,
    mismo output.
    """
    corte = fecha - pd.DateOffset(years=VENTANA_ANOS)
    ventana = serie_vol[(serie_vol.index >= corte) & (serie_vol.index <= fecha)].dropna()
    if len(ventana) < 252:  # menos de ~1 año de datos: ventana insuficiente
        return {"suficiente": False, "n_ventana": len(ventana)}

    q1, q2 = np.quantile(ventana, [1 / 3, 2 / 3])
    return {
        "suficiente": True,
        "n_ventana": len(ventana),
        "umbral_bajo_normal": float(q1),
        "umbral_normal_elevado": float(q2),
    }


def clasificar(vol_hoy: float, umbrales: dict) -> str:
    """A qué tercio de los últimos 6 años pertenece la volatilidad de hoy."""
    if vol_hoy < umbrales["umbral_bajo_normal"]:
        return ETIQUETAS[0]
    elif vol_hoy < umbrales["umbral_normal_elevado"]:
        return ETIQUETAS[1]
    return ETIQUETAS[2]


def calcular_regimen_6a(df: pd.DataFrame) -> dict:
    """
    Punto de entrada del bloque 06 para la etiqueta. Devuelve la etiqueta
    de hoy, los umbrales vigentes y el tamaño de la ventana usada — todo
    lo necesario para mostrarla y para registrarla en el histórico.
    """
    serie_vol = volatilidad_30d(df)
    fecha_hoy = df.index[-1]
    vol_hoy = float(serie_vol.iloc[-1])

    umbrales = calcular_umbrales(serie_vol, fecha_hoy)
    if not umbrales["suficiente"]:
        return {
            "disponible": False,
            "fecha": fecha_hoy,
            "vol30": vol_hoy,
            "n_ventana": umbrales["n_ventana"],
        }

    etiqueta = clasificar(vol_hoy, umbrales)
    return {
        "disponible": True,
        "fecha": fecha_hoy,
        "vol30": vol_hoy,
        "etiqueta": etiqueta,
        "umbral_bajo_normal": umbrales["umbral_bajo_normal"],
        "umbral_normal_elevado": umbrales["umbral_normal_elevado"],
        "n_ventana": umbrales["n_ventana"],
    }


def registrar_umbrales_dia(df: pd.DataFrame, path_csv: str = "umbrales_vol.csv") -> dict:
    """
    Añade (o actualiza si ya existe) la fila del día en el histórico de
    umbrales. Append-only por fecha: si la fecha ya está, se sobreescribe
    esa fila (permite relanzar el workflow el mismo día sin duplicar),
    nunca se reescriben fechas anteriores.

    Pensado para ejecutarse UNA vez al día desde un paso dedicado del
    workflow de GitHub Actions (no desde el panel Streamlit, que no
    persiste ficheros entre ejecuciones).
    """
    r = calcular_regimen_6a(df)
    fecha_str = r["fecha"].strftime("%Y-%m-%d")

    try:
        historico = pd.read_csv(path_csv, dtype={"fecha": str})
    except FileNotFoundError:
        historico = pd.DataFrame(columns=COLUMNAS_HISTORICO)

    fila = {
        "fecha": fecha_str,
        "vol30": round(r["vol30"], 6),
        "umbral_bajo_normal": round(r["umbral_bajo_normal"], 6) if r["disponible"] else "",
        "umbral_normal_elevado": round(r["umbral_normal_elevado"], 6) if r["disponible"] else "",
        "n_ventana": r["n_ventana"],
        "etiqueta": r.get("etiqueta", ""),
    }

    historico = historico[historico["fecha"] != fecha_str]
    historico = pd.concat([historico, pd.DataFrame([fila])], ignore_index=True)
    historico = historico.sort_values("fecha").reset_index(drop=True)
    historico.to_csv(path_csv, index=False)
    return fila


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    df = load_price_csv(path)
    r = calcular_regimen_6a(df)
    if r["disponible"]:
        print(f"{r['fecha'].date()}  vol30={r['vol30']*100:.1f}%  "
              f"régimen={r['etiqueta']}  "
              f"(umbrales {r['umbral_bajo_normal']*100:.1f}% / "
              f"{r['umbral_normal_elevado']*100:.1f}%, n={r['n_ventana']})")
    else:
        print(f"{r['fecha'].date()}  vol30={r['vol30']*100:.1f}%  "
              f"ventana insuficiente (n={r['n_ventana']} < 252)")
