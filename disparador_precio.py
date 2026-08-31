"""
DISPARADOR DE MOVIMIENTO EXTREMO — el primero de los vigilantes de eventos.

QUÉ ES Y QUÉ NO ES
-------------------
No decide si algo es importante. Comprueba un hecho objetivo — el precio
se movió más de lo habitual — y deja que el análisis (vía API) decida qué
lo causó, solo cuando ese hecho ocurre. La mayor parte del tiempo este
módulo no hace nada, y así debe ser.

POR QUÉ UMBRAL RELATIVO Y NO FIJO
-----------------------------------
Se midió la volatilidad diaria de BTC por época:

    Época          >8% en un día      p95 diario
    2018-2020         23.6 veces/año     8.9%
    2021-2023         14.7 veces/año     7.5%
    2024-2026          4.5 veces/año     5.1%

Un umbral fijo del 8% habría disparado 23 veces al año en 2018-2020 y solo
4-5 en el régimen actual. Fijar un número significa recalibrarlo cada pocos
años a mano, o vivir con una sensibilidad que ya no encaja.

Se usa en su lugar el mismo enfoque que ya está validado en rango.py: un
múltiplo de la volatilidad reciente (30 días), no un porcentaje fijo. Así
el disparador se adapta solo al régimen de mercado, igual que ya hace el
resto del sistema.

CALIBRACIÓN
-----------
Umbral: retorno diario absoluto > 3× la volatilidad diaria de los últimos
30 días. Con la volatilidad actual (~40% anualizada ≈ 2,1% diario), eso
dispara en torno al 6,3% de movimiento en un día — similar al umbral fijo
que daría ~5 avisos/año en el régimen actual, pero se ajusta solo si la
volatilidad cambia.

Se exige además que el movimiento sea el mayor de los últimos 5 días, para
no disparar en cada día de una racha ya conocida — el objetivo es detectar
el inicio de algo, no repetir el aviso mientras dura.

QUÉ HACE ESTE MÓDULO Y QUÉ HACE EL WORKFLOW
----------------------------------------------
Este módulo solo evalúa la condición sobre precio ya disponible en
btc_long.csv. No llama a ninguna API. El workflow de GitHub Actions es
quien, si `hay_disparo()` devuelve True, decide llamar al análisis
completo — manteniendo el coste en cero el resto del tiempo.
"""

import numpy as np
import pandas as pd

MULTIPLO_VOLATILIDAD = 3.0
VENTANA_VOL = 30
VENTANA_MAXIMO_RECIENTE = 5


def evaluar(df: pd.DataFrame) -> dict:
    """
    Comprueba si el movimiento del último día disponible es extremo
    respecto a la volatilidad reciente, y si es el mayor de los últimos
    días (para no repetir aviso en una racha ya detectada).
    """
    c = df["close"]
    ret = c.pct_change()
    vol_diaria = ret.rolling(VENTANA_VOL).std()

    if len(ret.dropna()) < VENTANA_VOL + VENTANA_MAXIMO_RECIENTE:
        return {"disparo": False, "motivo": "histórico insuficiente"}

    umbral = vol_diaria.iloc[-1] * MULTIPLO_VOLATILIDAD
    ultimo = ret.iloc[-1]
    es_extremo = abs(ultimo) > umbral

    recientes = ret.abs().iloc[-VENTANA_MAXIMO_RECIENTE:]
    es_el_mayor = abs(ultimo) >= recientes.max()

    disparo = bool(es_extremo and es_el_mayor)

    return {
        "disparo": disparo,
        "fecha": c.index[-1],
        "retorno": float(ultimo * 100),
        "umbral_pct": float(umbral * 100),
        "vol_30d_diaria_pct": float(vol_diaria.iloc[-1] * 100),
        "direccion": "subida" if ultimo > 0 else "bajada",
        "es_maximo_reciente": bool(es_el_mayor),
    }


def texto_disparo(r: dict) -> str:
    """Mensaje para el workflow o para logging. Vacío si no hay disparo."""
    if not r.get("disparo"):
        return ""
    return (
        f"Movimiento extremo detectado: {r['retorno']:+.1f}% en un día "
        f"({r['direccion']}), frente a un umbral de ±{r['umbral_pct']:.1f}% "
        f"(3× la volatilidad diaria reciente de {r['vol_30d_diaria_pct']:.1f}%). "
        f"Fecha: {r['fecha']:%d/%m/%Y}."
    )


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    r = evaluar(load_price_csv(path))
    if r["disparo"]:
        print("DISPARO:", texto_disparo(r))
        sys.exit(0)  # código 0 = "hay algo que analizar", para el workflow
    else:
        motivo = r.get("motivo", "sin movimiento extremo")
        print(f"Sin disparo. {motivo}")
        sys.exit(1)  # código 1 = "nada que hacer"
