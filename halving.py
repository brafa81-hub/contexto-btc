"""
CICLO DE HALVING — el único hallazgo de los once medidos que pasó el test.

QUÉ ES Y QUÉ NO ES
-------------------
NO es una señal para el panel semanal. Es un patrón histórico con evidencia
moderada (n=4 ciclos), documentado aquí para que no se pierda, y que solo
se muestra cuando la fecha actual cae dentro o cerca de la ventana que
describe. El resto del tiempo este módulo no aporta nada al panel — ni
debe hacerlo.

EL HALLAZGO (medido el 30/08/2026)
------------------------------------
De once candidatas evaluadas para anticipar movimientos de BTC (MVRV,
funding, DXY, tipos Fed, VIX, Nasdaq, Miedo y Codicia, hashrate, M2 global,
flujos de ETF, ciclo de halving), diez fueron rechazadas. El ciclo de
halving fue la única que superó el test de significancia.

Concretamente: los 90 días que siguen a la ventana de 18-24 meses después
de cada halving muestran un retorno mediano negativo, y esto se repite en
los CUATRO ciclos existentes:

    Ciclo               Mediana retorno 90d (fase 18-24m)   % positivos
    2012-11-28                    -30%                            0%
    2016-07-09                    -16%                           13%
    2020-05-11                    -26%                           11%
    2024-04-20                    -15%                           16%

Test de permutación (se desplazó el calendario de halvings a fechas
aleatorias y se repitió la medida). El p-valor DEPENDE del rango de
desplazamiento elegido, y esto se descubrió al revisar el análisis:

    Rango de desplazamiento     p-valor
    ±180 días                     0.049
    ±350 días                     0.014
    ±700 días                     0.001
    ±1400 días                    0.014
    ±2000 días                    0.019

La primera versión de este análisis usó ±700 días y reportó el resultado
más favorable sin justificar esa elección. Como el ciclo dura ~1400 días,
desplazar 700 sitúa el grupo de control justo en la fase opuesta, que es
sistemáticamente alcista — el test estaba sesgado a favor.

El rango honesto es amplio: p entre 0.014 y 0.049. Significativo en todos
los casos, pero más frágil de lo que sugería el 0.001.

CORRECCIÓN POR PRUEBAS MÚLTIPLES: se evaluaron 6 fases del ciclo, así que
el umbral de Bonferroni es 0.05/6 = 0.0083. La fase 545-730d es la única
que lo cruza, y solo con el planteamiento más favorable del test.

VALIDACIÓN FUERA DE MUESTRA (la prueba que de verdad importa):
usando solo los ciclos anteriores para predecir cuál sería la peor fase
del siguiente, sin mirarla antes:

    Con ciclo 1     → predice ciclo 2:  ACIERTA (545-730d, -16%)
    Con ciclos 1-2  → predice ciclo 3:  ACIERTA (545-730d, -26%)
    Con ciclos 1-3  → predice ciclo 4:  FALLA   (predijo 545-730d con -15%,
                                                 la peor real fue 730-1095d
                                                 con -17%)

Dos de tres, y el fallo por margen estrecho en la fase contigua. Esto vale
más que el p-valor, porque es lo único que prueba algo sin usar información
del futuro.

CONTROL IMPORTANTE: la parte de la teoría que sí se promociona — que BTC
sube en los meses siguientes al halving — NO pasó el mismo test (p=0.135).
Lo único que se sostiene es la parte que nadie repite: la resaca de
18-24 meses después, no el rally inicial.

POR QUÉ SE ACEPTA CON RESERVAS, A DIFERENCIA DE LAS OTRAS DIEZ
-----------------------------------------------------------------
n=4 es la evidencia más débil de todo lo aceptado en este proyecto. No es
comparable en solidez a la persistencia de volatilidad a 30 días (miles de
observaciones) ni a la correlación con Nasdaq (miles de días). Se acumula
un ciclo cada ~4 años: la quinta observación llegará en 2028-2030.

Por eso este hallazgo NO entra como bloque activo del panel semanal. Entra
como nota de contexto que se activa sola solo cuando la fecha real se
acerca a la ventana descrita, y se mantiene en silencio el resto del
tiempo — que es la mayor parte de cada ciclo de cuatro años.

FECHAS DE HALVING
------------------
Los tres primeros son hechos históricos. El próximo es una estimación de
mercado (bloque 1.050.000 a ritmo de ~10 min/bloque desde el halving de
2024), no una fecha confirmada; puede desviarse semanas en cualquier
dirección según el ritmo real de minado.
"""

from datetime import date, timedelta

HALVINGS_CONFIRMADOS = [
    date(2012, 11, 28),
    date(2016, 7, 9),
    date(2020, 5, 11),
    date(2024, 4, 20),
]

# Estimación, no confirmada. Ver docstring.
PROXIMO_HALVING_ESTIMADO = date(2028, 4, 20)

# La ventana con evidencia (18-24 meses = 545-730 días tras el halving).
VENTANA_INICIO_DIAS = 545
VENTANA_FIN_DIAS = 730

# Cuánto antes de la ventana empieza a avisar, para dar margen de reflexión
# sin que el aviso lleve activo la mayor parte del ciclo.
MARGEN_PREVIO_DIAS = 90


def dias_desde_ultimo_halving(hoy: date = None) -> tuple:
    """Días transcurridos desde el halving más reciente, y cuál fue."""
    hoy = hoy or date.today()
    todos = HALVINGS_CONFIRMADOS + [PROXIMO_HALVING_ESTIMADO]
    pasados = [h for h in todos if h <= hoy]
    if not pasados:
        return None, None
    ultimo = pasados[-1]
    return (hoy - ultimo).days, ultimo


def evaluar_ventana(hoy: date = None) -> dict:
    """
    ¿La fecha actual cae dentro, cerca, o lejos de la ventana de riesgo?

    Devuelve 'silencio' la inmensa mayoría del tiempo, que es el
    comportamiento correcto: este hallazgo solo importa una vez cada
    varios años.
    """
    hoy = hoy or date.today()
    dias, ultimo = dias_desde_ultimo_halving(hoy)
    if dias is None:
        return {"estado": "silencio"}

    fin_ventana_actual = ultimo + timedelta(days=VENTANA_FIN_DIAS)
    inicio_ventana_actual = ultimo + timedelta(days=VENTANA_INICIO_DIAS)
    inicio_aviso = inicio_ventana_actual - timedelta(days=MARGEN_PREVIO_DIAS)

    if hoy < inicio_aviso or hoy > fin_ventana_actual:
        return {"estado": "silencio", "dias_desde_halving": dias}

    estado = "en_ventana" if inicio_ventana_actual <= hoy <= fin_ventana_actual else "aproximandose"

    dias_hasta = (inicio_ventana_actual - hoy).days
    dias_restantes = (fin_ventana_actual - hoy).days

    return {
        "estado": estado,
        "halving_referencia": ultimo,
        "es_estimado": ultimo == PROXIMO_HALVING_ESTIMADO,
        "dias_desde_halving": dias,
        "inicio_ventana": inicio_ventana_actual,
        "fin_ventana": fin_ventana_actual,
        "dias_hasta_ventana": max(dias_hasta, 0),
        "dias_restantes_ventana": max(dias_restantes, 0),
    }


def texto_aviso(hoy: date = None) -> str:
    """
    Texto para el panel. Cadena vacía si no hay nada que decir — que es el
    caso casi siempre, y así debe ser: no se narra un hallazgo de n=4 cada
    semana solo porque el módulo existe.
    """
    v = evaluar_ventana(hoy)
    if v["estado"] == "silencio":
        return ""

    nota_estimado = " (fecha de halving estimada, no confirmada)" if v.get("es_estimado") else ""

    if v["estado"] == "aproximandose":
        return (
            f"📅 En {v['dias_hasta_ventana']} días entra la ventana histórica de "
            f"18-24 meses post-halving{nota_estimado}. En los cuatro ciclos "
            f"anteriores, esa fase precedió una caída mediana del 22% a 90 días "
            f"(p entre 0,014 y 0,049 según el test; acierta 2 de 3 fuera de muestra), con solo 4 observaciones — evidencia débil, no "
            f"una predicción. Detalle completo en `halving.py`."
        )

    return (
        f"📅 Estás dentro de la ventana histórica de 18-24 meses post-halving"
        f"{nota_estimado} (quedan {v['dias_restantes_ventana']} días). En los "
        f"cuatro ciclos anteriores esta fase precedió una caída mediana del 22% "
        f"a 90 días (p entre 0,014 y 0,049; acierta 2 de 3 fuera de muestra) — evidencia con solo 4 observaciones, no una "
        f"predicción. Detalle completo en `halving.py`."
    )


if __name__ == "__main__":
    v = evaluar_ventana()
    print("┌─ CICLO DE HALVING " + "─" * 47)
    if v["estado"] == "silencio":
        d = v.get("dias_desde_halving")
        print(f"│  Sin aviso activo. Día {d} desde el último halving." if d
              else "│  Sin aviso activo.")
    else:
        print(f"│  {texto_aviso()}")
    print("│")
    print("│  Próxima ventana de riesgo estimada: "
          f"{PROXIMO_HALVING_ESTIMADO + timedelta(days=VENTANA_INICIO_DIAS)} "
          f"a {PROXIMO_HALVING_ESTIMADO + timedelta(days=VENTANA_FIN_DIAS)}")
    print("└" + "─" * 66)
