#!/usr/bin/env python3
"""
serie_active_addresses.py - Contexto-BTC

Genera la serie derivada de la candidata `active_addresses_delta20_ma7`:
direcciones activas diarias, suavizadas con media movil de 7 dias, y
variacion relativa a 20 dias sobre esa media suavizada.

FECHA DE CORTE DECLARADA COMO CONSTANTE
---------------------------------------
FECHA_CORTE se fija a 2026-09-03, que es el ultimo dia del snapshot de
precio congelado (v2.json -> fuente_de_precio.snapshot.congelacion.rango).

No se deriva de la fecha de ejecucion. Si dependiese de cuando se lanza,
el artefacto no seria reproducible y su SHA-256 cambiaria cada dia. Mismo
criterio que snapshot_precio.py (enmienda 20).

Los dias posteriores a la fecha de corte se descartan: sin precio en el
snapshot no existe retorno a 30 dias que medir contra ellos.

ORDEN DE LAS OPERACIONES
------------------------
El suavizado MA7 se aplica ANTES de la diferencia a 20 dias, no despues.
El orden inverso da una serie distinta. Queda declarado aqui.

La ventana de calentamiento (MA7 + 20 dias de desfase) consume datos
anteriores a 2015-01-01, que existen en la fuente bruta desde 2009, de
modo que no se pierde ningun dia del rango util.

FUENTE
------
bitcoin-data.com/v1/active-addresses/csv (BGeometrics). Dato bruto,
reconstruible por un auditor.
"""

import hashlib
import sys

import pandas as pd

FECHA_CORTE = "2026-09-14"   # constante declarada, no derivada de hoy
VENTANA_MA = 7
DESFASE_DELTA = 20

ENTRADA = "active_addresses_raw.csv"
SALIDA = "serie_active_addresses_delta20_ma7.csv"


def main():
    df = pd.read_csv(ENTRADA)
    df["d"] = pd.to_datetime(df["d"])
    df = df.sort_values("d").reset_index(drop=True)

    if df["d"].duplicated().any():
        sys.exit("ABORTA: fechas duplicadas en la fuente bruta")

    # Suavizado primero, diferencia despues. El orden importa.
    df["ma7"] = df["activeAddresses"].rolling(
        window=VENTANA_MA, min_periods=VENTANA_MA
    ).mean()
    df["delta20"] = (df["ma7"] / df["ma7"].shift(DESFASE_DELTA)) - 1

    # NO se recorta el inicio. El motor aplica su propio warm_up de 365 dias
    # desde el primer dato del CSV (construir_mascara). Recortar aqui a
    # 2015-01-01 haria que el motor consumiese todo 2015 y se perderia un anio
    # de rango util. Mismo criterio que la ficha de dgs2_delta20, que alimento
    # el historial completo de FRED desde 1976.
    rango = df[df["d"] <= FECHA_CORTE].dropna(subset=["delta20"]).copy()

    salida = rango[["d", "delta20"]].copy()
    salida.columns = ["fecha", "valor"]
    salida["fecha"] = salida["fecha"].dt.strftime("%Y-%m-%d")

    salida.to_csv(SALIDA, index=False, lineterminator="\n")

    with open(SALIDA, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    print(f"fichero: {SALIDA}")
    print(f"filas: {len(salida)}")
    print(f"rango: {salida['fecha'].iloc[0]} a {salida['fecha'].iloc[-1]}")
    print(f"sha256: {sha}")


if __name__ == "__main__":
    main()
