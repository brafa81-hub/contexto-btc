"""
RANGO ESPERADO Y DIMENSIONAMIENTO — el bloque que sí se apoya en algo medido.

QUÉ HACE Y QUÉ NO
-----------------
NO predice si BTC subirá o bajará. Eso se midió sobre 5.490 días de Bitstamp
(2011-2026) y el resultado fue R² = 0,1% en 2021-2025: la dirección del precio
es, a efectos prácticos, irreducible con estos datos.

SÍ estima CUÁNTO se moverá el precio el próximo mes, en cualquier dirección.
Eso es lo único que sobrevivió a la validación por épocas.

QUÉ SE VALIDÓ Y CÓMO (28/08/2026)
---------------------------------
Persistencia de volatilidad, ventanas NO solapadas (cada dato independiente,
sin inflar la correlación por solapamiento). Correlación de Spearman entre la
volatilidad de un periodo y la del siguiente:

    Horizonte   2011-2015   2016-2020   2021-2026   ¿Estable?
    30 días        0.53        0.45        0.49        SÍ
    60 días        0.44        0.20        0.50        NO
    90 días        0.07        0.18        0.72        NO
   180 días       -0.21        0.28        0.67        NO

POR ESO EL HORIZONTE ES 30 DÍAS Y NO 90. A 90 días la correlación reciente es
altísima (0.72) y resulta tentador usarla — pero fue 0.07 en 2011-2015. Una
relación que aparece y desaparece según la época no es una relación en la que
apoyar una decisión: es la misma trampa que rompió el motor de tendencia.

CALIBRACIÓN
-----------
Los rangos de la tabla son percentiles empíricos sobre las 5.429 observaciones
de la serie completa, agrupadas por cuartil de volatilidad. No hay ningún
parámetro ajustado: no hay nada que sobreajustar.

LIMITACIÓN QUE NO SE DEBE OLVIDAR
---------------------------------
La correlación de 0.5 significa que el orden se conserva a medias. La franja
p25-p75 es ancha a propósito: refleja la incertidumbre real, no la esconde.
El p95 existe para recordar que la cola es gorda y que el mes puede salirse
de la banda sin que nada esté "roto".
"""

import numpy as np
import pandas as pd


# Cuartiles de volatilidad 30d anualizada, calculados sobre 2011-2026 (Bitstamp).
# Se dejan fijos y explícitos para que el bloque sea reproducible: el mismo
# input da siempre el mismo output, y cualquiera puede recalcularlos.
CUARTILES_VOL = [0.42, 0.58, 0.81]

# Rango (máximo/mínimo − 1) observado en los 30 días siguientes, por cuartil.
# Percentiles empíricos, no un modelo ajustado.
RANGOS_POR_CUARTIL = {
    "muy baja": {"p25": 0.12, "p50": 0.22, "p75": 0.34, "p95": 0.71, "n": 1358},
    "baja":     {"p25": 0.14, "p50": 0.22, "p75": 0.34, "p95": 0.85, "n": 1357},
    "alta":     {"p25": 0.18, "p50": 0.25, "p75": 0.37, "p95": 0.76, "n": 1357},
    "muy alta": {"p25": 0.26, "p50": 0.39, "p75": 0.61, "p95": 1.40, "n": 1357},
}

ETIQUETAS = ["muy baja", "baja", "alta", "muy alta"]


def volatilidad_30d(df: pd.DataFrame) -> float:
    """Volatilidad anualizada de los últimos 30 días, sobre retornos logarítmicos."""
    r = np.log(df["close"] / df["close"].shift(1))
    return float(r.rolling(30).std().iloc[-1] * np.sqrt(365))


def clasificar_volatilidad(vol: float) -> str:
    """En qué cuartil histórico cae la volatilidad actual."""
    for i, corte in enumerate(CUARTILES_VOL):
        if vol < corte:
            return ETIQUETAS[i]
    return ETIQUETAS[-1]


def percentil_vol(df: pd.DataFrame, vol: float) -> float:
    """Qué porcentaje de la historia tuvo menos volatilidad que ahora."""
    r = np.log(df["close"] / df["close"].shift(1))
    serie = (r.rolling(30).std() * np.sqrt(365)).dropna()
    if len(serie) == 0:
        return float("nan")
    return float((serie < vol).mean() * 100)


def calcular_rango_esperado(df: pd.DataFrame) -> dict:
    """
    Rango de oscilación esperado para los próximos 30 días.

    Devuelve el precio actual, la volatilidad, su cuartil, y las bandas de
    oscilación traducidas a precio. Las bandas son simétricas en amplitud
    porque el método NO tiene opinión sobre la dirección — solo sobre cuánto
    terreno es probable que cubra el precio.
    """
    precio = float(df["close"].iloc[-1])
    vol = volatilidad_30d(df)
    cuartil = clasificar_volatilidad(vol)
    tabla = RANGOS_POR_CUARTIL[cuartil]

    bandas = {}
    for k in ("p25", "p50", "p75", "p95"):
        amplitud = tabla[k]
        # Reparto de la amplitud alrededor del precio actual. No es una
        # predicción de máximo y mínimo: es el ancho típico del recorrido.
        bandas[k] = {
            "amplitud": amplitud,
            "suelo": precio / (1 + amplitud / 2),
            "techo": precio * (1 + amplitud / 2),
        }

    return {
        "precio": precio,
        "vol": vol,
        "vol_pct": percentil_vol(df, vol),
        "cuartil": cuartil,
        "n_historico": tabla["n"],
        "bandas": bandas,
    }


def dimensionar(capital_disponible: float, perdida_tolerable: float,
                rango: dict) -> dict:
    """
    Traduce una pérdida tolerable en euros a un tamaño de posición.

    La lógica va al revés de lo habitual: no parte de cuánto quieres invertir,
    sino de cuánto estás dispuesto a perder sin que te afecte al sueño. El
    escenario 'prudente' usa el percentil 75 de oscilación; el 'adverso' usa
    el 95, que es la cola que de verdad hace daño.

    IMPORTANTE: esto dimensiona, no recomienda entrar. Que el cálculo diga
    "puedes exponer 3.000 €" no significa que debas hacerlo.
    """
    escenarios = {}
    for nombre, clave in [("típico", "p50"), ("prudente", "p75"), ("adverso", "p95")]:
        # Caída potencial ~ la mitad de la amplitud del rango (movimiento
        # adverso desde el precio actual hasta el extremo bajo de la banda).
        caida = rango["bandas"][clave]["amplitud"] / 2
        capital = perdida_tolerable / caida if caida > 0 else float("nan")
        escenarios[nombre] = {
            "caida_pct": caida * 100,
            "capital_max": min(capital, capital_disponible),
            "supera_disponible": capital > capital_disponible,
        }
    return escenarios


def generar_bloque(df: pd.DataFrame, capital: float = None,
                   perdida_tolerable: float = None) -> str:
    """Bloque de texto para consola, en el mismo formato que el resto."""
    r = calcular_rango_esperado(df)
    L = []
    L.append("┌─ RANGO ESPERADO (30 DÍAS) " + "─" * 39)
    L.append(f"│  Volatilidad 30d: {r['vol']*100:.0f}%  ({r['cuartil']}, "
             f"percentil {r['vol_pct']:.0f} de su historia)")
    L.append("│")
    L.append(f"│  Con volatilidad {r['cuartil']}, el precio osciló en un mes:")
    for k, nom in [("p50", "la mitad de las veces"), ("p75", "3 de cada 4 veces"),
                   ("p95", "1 de cada 20 veces")]:
        b = r["bandas"][k]
        L.append(f"│    {nom:<24} menos de {b['amplitud']*100:>3.0f}%  "
                 f"(${b['suelo']:,.0f} – ${b['techo']:,.0f})")
    L.append("│")
    L.append(f"│  Basado en {r['n_historico']} meses históricos con volatilidad similar.")
    L.append("│  No indica dirección: solo cuánto terreno suele cubrir el precio.")

    if capital and perdida_tolerable:
        L.append("│")
        d = dimensionar(capital, perdida_tolerable, r)
        L.append(f"│  Para no perder más de {perdida_tolerable:,.0f} € :")
        for nom, e in d.items():
            aviso = "  (más de tu capital)" if e["supera_disponible"] else ""
            L.append(f"│    escenario {nom:<9} (−{e['caida_pct']:.0f}%): "
                     f"hasta {e['capital_max']:,.0f} €{aviso}")

    L.append("└" + "─" * 66)
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    print(generar_bloque(load_price_csv(path), capital=10000, perdida_tolerable=1000))
