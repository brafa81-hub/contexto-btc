"""
generador.py — Generador de datos sinteticos para calibracion.

Replica el mecanismo usado en la sesion de calibracion de 6a (bitacora-
sesiones-3.md): block bootstrap con reemplazo, bloques de 20 dias, mascara
percentil movil 365d Q80 sobre una metrica AR(1), inyeccion de efecto por
MAXIMO sobre el retorno. Extension: continuacion forward de 5 trimestres
sinteticos tras el "hoy" de cada replica, mismo mecanismo de remuestreo.

Verificado sin el bug de acumulacion de sesiones anteriores: cada bloque de
bootstrap se toma de un INDICE ALEATORIO INDEPENDIENTE sobre la serie base
(sin arrastrar offset acumulado entre bloques sucesivos).

CORREGIDO (sesion Sonnet, 19/20-sep-2026): n_historico por defecto pasa de
1200 a 4260 dias. Con 1200 (bloques de ~1,6 anios cada uno) el generador
incumplia protocolo.particion_datos.minimo_por_bloque_anios=3 de la propia
doctrina: toda replica seria NO ADMISIBLE por el motor real antes de contar
episodios. 4260 = 2 bloques de 2130 dias (5,83 anios cada uno), el tamano
real medido en las variables del registro (dgs10_delta20, dgs2_delta20,
vix_repesca). Detectado y corregido en sesion Opus previa (ver bitacora).
"""

import numpy as np
import pandas as pd


def _serie_ar1(n, phi, semilla, sigma=1.0):
    rng = np.random.default_rng(semilla)
    x = np.zeros(n)
    ruido = rng.normal(0, sigma, n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + ruido[t]
    return x


def _precio_gbm(n, semilla, mu=0.0002, sigma=0.02):
    rng = np.random.default_rng(semilla + 1_000_000)
    retornos = rng.normal(mu, sigma, n)
    precio = 100 * np.exp(np.cumsum(retornos))
    return precio


def _block_bootstrap_indices(n_total, n_salida, bloque, rng):
    """
    Genera indices (sobre 0..n_total-1) para construir una serie de longitud
    n_salida mediante bloques contiguos de tamano `bloque`, cada uno tomado
    de un punto de inicio aleatorio INDEPENDIENTE (con reemplazo). Sin
    acumulacion de offset entre bloques (ese fue el bug de la reconstruccion
    anterior: alli el punto de inicio del bloque k+1 se calculaba sumando al
    offset del bloque k en vez de sortear de nuevo).
    """
    idx = []
    max_inicio = n_total - bloque
    while len(idx) < n_salida:
        inicio = rng.integers(0, max_inicio + 1)  # sorteo independiente, sin memoria del bloque anterior
        idx.extend(range(inicio, inicio + bloque))
    return np.array(idx[:n_salida])


def generar_replica(semilla, n_historico=4260, n_forward_dias=455,
                     bloque=20, phi=0.985, theta_nominal=0.0,
                     percentil_mascara=80, ventana_mascara=365):
    """
    Genera UNA replica completa: historico (para gates+permutacion, bloque_1
    + bloque_2) mas continuacion forward de 5 trimestres sinteticos (para
    confirmacion_forward).

    theta_nominal: efecto inyectado por MAXIMO sobre el retorno a 30 dias
    cuando la mascara esta activa. theta_nominal=0.0 => ruido puro.

    Se genera un CALENTAMIENTO previo de `ventana_mascara` dias (no incluido
    en el resultado) para que la mascara movil Q80/365d tenga historia
    completa desde el primer dia de bloque_1: sin esto, los primeros 365
    dias de cada replica quedan con mascara forzada a False (NaN del
    rolling), lo que en la practica vaciaba bloque_1 de activaciones y
    hacia fallar gate1 de forma sistematica y espuria (detectado y corregido
    en esta sesion, antes de calibrar nada).

    Devuelve un dict con: indice completo, precio, metrica, mask, ret,
    fecha_corte_forward (separa historico de continuacion), y los parametros
    usados (para trazabilidad).
    """
    rng = np.random.default_rng(semilla)
    n_calentamiento = ventana_mascara
    n_total = n_calentamiento + n_historico + n_forward_dias

    # Metrica base AR(1) sobre una serie mas larga, luego remuestreada por
    # bloques (asi la mascara conserva autocorrelacion realista tanto en el
    # tramo historico como en el forward, sin discontinuidad artificial en el corte).
    n_fuente = max(4000, n_total * 3)
    metrica_fuente = _serie_ar1(n_fuente, phi, semilla)
    precio_fuente = _precio_gbm(n_fuente, semilla)

    idx_bootstrap = _block_bootstrap_indices(n_fuente, n_total, bloque, rng)
    metrica = metrica_fuente[idx_bootstrap]
    precio = precio_fuente[idx_bootstrap]
    # Renormalizar precio para que sea una trayectoria continua propia (no
    # saltos entre bloques): reconstruir como paseo con los retornos log del
    # bloque re-muestreado.
    log_ret_fuente = np.diff(np.log(precio_fuente), prepend=np.log(precio_fuente[0]))
    log_ret = log_ret_fuente[idx_bootstrap]
    precio = 100 * np.exp(np.cumsum(log_ret))

    fechas_totales = pd.date_range("2015-01-01", periods=n_total, freq="D")
    metrica_s_full = pd.Series(metrica, index=fechas_totales)
    precio_s_full = pd.Series(precio, index=fechas_totales)

    # Mascara: percentil movil Q80 sobre ventana de 365d (variable de referencia),
    # calculada sobre la serie CON calentamiento para que tenga historia completa
    # desde el primer dia util (n_calentamiento).
    umbral_movil = metrica_s_full.rolling(ventana_mascara, min_periods=ventana_mascara).quantile(percentil_mascara / 100)
    mask_full = (metrica_s_full > umbral_movil).fillna(False)

    # Retorno a 30 dias, CON inyeccion de efecto por maximo cuando mask=True
    ret_base_full = (precio_s_full.shift(-30) / precio_s_full - 1)
    if theta_nominal != 0.0:
        ret_efecto = ret_base_full.copy()
        ret_efecto[mask_full] = np.maximum(ret_base_full[mask_full], ret_base_full[mask_full] + theta_nominal)
        # inyeccion por MAXIMO: el efecto empuja el retorno hacia arriba,
        # tomando el mayor entre el retorno base y el retorno base + theta
        ret_full = ret_efecto
    else:
        ret_full = ret_base_full
    ret_full = ret_full.rename("retorno_N")

    # Se descarta el calentamiento: el resultado empieza en el primer dia con
    # mascara ya valida (n_calentamiento dias despues del origen sintetico).
    fechas = fechas_totales[n_calentamiento:]
    metrica_s = metrica_s_full.loc[fechas]
    precio_s = precio_s_full.loc[fechas]
    mask = mask_full.loc[fechas]
    ret = ret_full.loc[fechas]

    fecha_corte = fechas[n_historico - 1]

    return {
        "fechas": fechas, "precio": precio_s, "metrica": metrica_s,
        "mask": mask, "ret": ret, "fecha_corte_forward": fecha_corte,
        "n_historico": n_historico, "n_forward_dias": n_forward_dias,
        "theta_nominal": theta_nominal, "semilla": semilla,
    }
