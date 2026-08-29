"""
DETECTOR DE CAMBIO DE RÉGIMEN — vigila si el panel sigue midiendo bien.

POR QUÉ EXISTE
--------------
El motor de tendencia de este proyecto funcionó durante años y dejó de
funcionar en 2021. El problema no fue que fallara: fue que nadie se enteró
de que había dejado de aplicar. Un sistema calibrado sobre un mundo que ya
cambió no da error — da respuestas plausibles y equivocadas.

Este módulo hace dos trabajos distintos:

  1. AVISAR de que el comportamiento del activo ha cambiado de forma sostenida
  2. AUDITAR si la calibración del propio panel sigue discriminando

El segundo es el más importante y el que casi nadie implementa.

CALIBRACIÓN DEL DETECTOR (28/08/2026)
--------------------------------------
Se probaron cuatro reglas sobre 15 años de Bitstamp, contando cuántas alarmas
habría dado cada una:

    Regla              Alarmas en 15 años
    p10 / 30 días            5
    p10 / 60 días            4      <- elegida
    p10 / 90 días            2
    p5  / 60 días            1

Se eligió p10/60d: cuatro avisos en quince años es un ritmo que se puede
atender sin desensibilizarse. Con p10/30d aparecen alarmas que se deshacen
solas; con p5/60d se detecta casi nada.

De las tres alarmas históricas completas (2016-11, 2023-08, 2025-09), dos
señalaron cambios que persistieron un año o más. La de 2016 avisó de un
cambio real, pero la volatilidad se movió en dirección contraria a la
sugerida por la alarma. Por eso el detector NO predice dirección: solo dice
"algo cambió, revisa tus supuestos".

EL HALLAZGO QUE MOTIVÓ LA AUDITORÍA
------------------------------------
Los cuartiles de volatilidad de rango.py se calibraron sobre 2011-2026 y
reparten los días así:

    Periodo      muy baja   baja   alta   muy alta
    2011-2026        25%     26%    24%      25%     <- equilibrado
    2021-2026        32%     32%    25%      11%
    2024-2026        44%     39%    14%       2%
    2025-2026        57%     33%     8%       2%     <- degenerado

En los últimos dos años, el 57% de los días caen en "muy baja". Un cuartil
que concentra más de la mitad de las observaciones ha dejado de discriminar:
la etiqueta sale casi siempre igual y por tanto no informa de nada.

Impacto medido: el p95 de oscilación que usa rango.py para el escenario
adverso (85%) procede en buena parte de meses de 2011-2015 con volatilidad
nominalmente parecida pero comportamiento muy distinto. Desde 2023, meses con
la misma volatilidad tuvieron un p95 real del 37%, no del 85%.

El error va en la dirección segura — dimensiona más conservador de lo
necesario, no menos. Pero sigue siendo un error, y conviene saberlo.
"""

import numpy as np
import pandas as pd

VENTANA_REFERENCIA = 1095   # 3 años
UMBRAL = 0.10
DIAS_PERSISTENCIA = 60
CORTES_FIJOS = [0.42, 0.58, 0.81]
ETIQUETAS = ["muy baja", "baja", "alta", "muy alta"]


def _vol(df: pd.DataFrame, ventana: int) -> pd.Series:
    r = np.log(df["close"] / df["close"].shift(1))
    return r.rolling(ventana).std() * np.sqrt(365)


def detectar_cambio_regimen(df: pd.DataFrame) -> dict:
    """
    ¿La volatilidad reciente lleva tiempo fuera de su rango histórico?

    No dice si eso es bueno o malo, ni hacia dónde irá el precio. Dice que
    el activo lleva sesenta días comportándose de forma que antes era rara.
    """
    vol = _vol(df, 90).dropna()
    if len(vol) < VENTANA_REFERENCIA:
        return {"activa": False, "motivo": "histórico insuficiente"}

    actual = float(vol.iloc[-1])
    hist = vol.iloc[:-1]
    p_bajo, p_alto = hist.quantile(UMBRAL), hist.quantile(1 - UMBRAL)

    fuera = (vol < p_bajo) | (vol > p_alto)
    dias_seguidos = int(fuera.iloc[-DIAS_PERSISTENCIA:].sum())
    activa = dias_seguidos >= DIAS_PERSISTENCIA

    return {
        "activa": activa,
        "vol_actual": actual * 100,
        "banda_baja": float(p_bajo) * 100,
        "banda_alta": float(p_alto) * 100,
        "direccion": "por debajo" if actual < p_bajo else ("por encima" if actual > p_alto else "dentro"),
        "dias_fuera": dias_seguidos,
        "percentil": float((hist < actual).mean() * 100),
    }


def auditar_calibracion(df: pd.DataFrame, meses: int = 24) -> dict:
    """
    ¿Los cuartiles fijos de rango.py siguen repartiendo los días?

    Si un cuartil concentra más del 50% de las observaciones recientes, la
    etiqueta ha dejado de informar: sale siempre la misma. Esto se detecta
    sin necesidad de que nada "falle" visiblemente.
    """
    vol30 = _vol(df, 30).dropna()
    corte = df.index[-1] - pd.Timedelta(days=meses * 30)
    reciente = vol30.loc[corte:]
    if len(reciente) < 90:
        return {"suficiente": False}

    def clasificar(v):
        for i, x in enumerate(CORTES_FIJOS):
            if v < x:
                return ETIQUETAS[i]
        return ETIQUETAS[-1]

    reparto = reciente.apply(clasificar).value_counts(normalize=True) * 100
    reparto = {e: float(reparto.get(e, 0.0)) for e in ETIQUETAS}
    dominante = max(reparto, key=reparto.get)

    # Cortes que resultarían de recalibrar solo con los últimos 3 años
    ref = vol30.iloc[-VENTANA_REFERENCIA:]
    cortes_actuales = [float(ref.quantile(q)) for q in (0.25, 0.50, 0.75)]

    return {
        "suficiente": True,
        "reparto": reparto,
        "dominante": dominante,
        "concentracion": reparto[dominante],
        "degenerado": reparto[dominante] > 50,
        "desequilibrado": reparto[dominante] > 40,
        "cortes_fijos": [x * 100 for x in CORTES_FIJOS],
        "cortes_recientes": [x * 100 for x in cortes_actuales],
        "meses": meses,
    }


def comparar_colas(df: pd.DataFrame, vol_actual: float, margen: float = 0.05) -> dict:
    """
    El escenario adverso del bloque 07 usa el p95 histórico completo.
    Aquí se compara con el p95 observado solo en los últimos 3 años, con
    volatilidad comparable, para ver cuánto difieren.
    """
    vol30 = _vol(df, 30)
    c = df["close"].values
    rng = pd.Series(index=df.index, dtype=float)
    for i in range(len(c) - 30):
        w = c[i:i + 31]
        rng.iloc[i] = w.max() / w.min() - 1

    z = pd.concat([vol30.rename("v"), rng.rename("r")], axis=1).dropna()
    sim = z[(z["v"] >= vol_actual - margen) & (z["v"] <= vol_actual + margen)]
    if len(sim) < 60:
        return {"suficiente": False}

    corte = df.index[-1] - pd.Timedelta(days=VENTANA_REFERENCIA)
    reciente = sim.loc[corte:]
    if len(reciente) < 60:
        return {"suficiente": False}

    return {
        "suficiente": True,
        "n_total": len(sim),
        "n_reciente": len(reciente),
        "p95_total": float(sim["r"].quantile(0.95)) * 100,
        "p95_reciente": float(reciente["r"].quantile(0.95)) * 100,
        "p50_total": float(sim["r"].median()) * 100,
        "p50_reciente": float(reciente["r"].median()) * 100,
    }


def informe(df: pd.DataFrame) -> dict:
    """Ejecuta las tres comprobaciones y devuelve avisos en lenguaje llano."""
    reg = detectar_cambio_regimen(df)
    cal = auditar_calibracion(df)
    vol_act = _vol(df, 30).iloc[-1]
    colas = comparar_colas(df, float(vol_act))

    avisos = []

    if reg.get("activa"):
        avisos.append({
            "nivel": "alto",
            "texto": (
                f"La volatilidad lleva {reg['dias_fuera']} días seguidos "
                f"{reg['direccion']} de su rango habitual "
                f"({reg['banda_baja']:.0f}–{reg['banda_alta']:.0f}%). "
                f"Está en {reg['vol_actual']:.0f}%, percentil {reg['percentil']:.0f} "
                f"de toda su historia. Esto no dice hacia dónde irá el precio: "
                f"dice que el activo se está comportando de una forma que antes "
                f"era rara, y que conviene revisar si los supuestos del panel "
                f"siguen aplicando."
            ),
        })

    if cal.get("suficiente"):
        if cal["degenerado"]:
            avisos.append({
                "nivel": "alto",
                "texto": (
                    f"La calibración del bloque 06 ha dejado de discriminar: el "
                    f"{cal['concentracion']:.0f}% de los últimos {cal['meses']} meses "
                    f"caen en la categoría «{cal['dominante']}». Cuando un cuartil "
                    f"concentra más de la mitad de los días, la etiqueta sale casi "
                    f"siempre igual y por tanto no informa. Los cortes fijos son "
                    f"{cal['cortes_fijos'][0]:.0f}/{cal['cortes_fijos'][1]:.0f}/"
                    f"{cal['cortes_fijos'][2]:.0f}%; con los últimos 3 años serían "
                    f"{cal['cortes_recientes'][0]:.0f}/{cal['cortes_recientes'][1]:.0f}/"
                    f"{cal['cortes_recientes'][2]:.0f}%."
                ),
            })
        elif cal["desequilibrado"]:
            avisos.append({
                "nivel": "medio",
                "texto": (
                    f"El {cal['concentracion']:.0f}% de los últimos {cal['meses']} meses "
                    f"caen en «{cal['dominante']}». Todavía discrimina, pero se está "
                    f"desequilibrando. Merece la pena vigilarlo."
                ),
            })

    if colas.get("suficiente"):
        dif = colas["p95_total"] - colas["p95_reciente"]
        if abs(dif) > 15:
            direccion = "sobreestima" if dif > 0 else "subestima"
            gravedad = "medio" if dif > 0 else "alto"
            avisos.append({
                "nivel": gravedad,
                "texto": (
                    f"El escenario adverso del bloque 07 {direccion} la cola. Usa el "
                    f"p95 de toda la historia ({colas['p95_total']:.0f}%), pero en los "
                    f"últimos 3 años con volatilidad similar el p95 real fue "
                    f"{colas['p95_reciente']:.0f}%. "
                    + ("El error va en la dirección segura (dimensiona más "
                       "conservador de lo necesario), pero conviene saberlo."
                       if dif > 0 else
                       "ATENCIÓN: el error va en la dirección peligrosa — el "
                       "escenario adverso real es peor que el que muestra el panel.")
                ),
            })

    return {"regimen": reg, "calibracion": cal, "colas": colas, "avisos": avisos}


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    inf = informe(load_price_csv(path))
    print("┌─ AUDITORÍA DEL PANEL " + "─" * 44)
    if not inf["avisos"]:
        print("│  Sin avisos: régimen y calibración dentro de lo normal.")
    for a in inf["avisos"]:
        print(f"│  [{a['nivel'].upper()}] {a['texto']}")
        print("│")
    print("└" + "─" * 66)
