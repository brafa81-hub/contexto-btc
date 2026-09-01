"""
FILTRO DE VALIDACIÓN — el criterio que decide si una variable entra al panel.

Este módulo formaliza el filtro que hasta ahora se aplicaba a mano en cada
análisis. Se auditó el 29/08/2026 y se encontraron tres fallos, corregidos
aquí y documentados abajo.

LOS CUATRO PASOS
----------------
  1. ¿Existe la relación y aguanta entre épocas?
  2. ¿Anticipa o solo acompaña?
  3. ¿Aporta algo sobre lo que ya sabemos?
  4. ¿Se distingue del azar?

El orden importa: cada paso es más caro que el anterior, así que primero
descarta lo barato. Y empezar por el paso 4 daría "significancia" a cosas
que luego resultan inestables.


=======================  AUDITORÍA  =======================

FALLO 1 — El umbral de 0,05 dejaba escapar señales valiosas
-----------------------------------------------------------
Se inyectaron señales anticipatorias de fuerza conocida y se midió cuántas
detectaba el filtro:

    Correlación real   % que pasaba el paso 1
         0.02                    0%
         0.05                    3%
         0.08                   36%    <- se escapa el 64%
         0.13                   90%
         0.24                  100%

El problema: exigir |corr| > 0,05 en TODAS las épocas es muy restrictivo
cuando cada época tiene ruido propio. Basta que una caiga a 0,04 para
descartar la variable entera.

Y el coste es alto. Una señal ANTICIPATORIA de correlación 0,08 (que ahora
se escapaba dos de cada tres veces) aplicada como regla simple daría, sobre
el histórico real de BTC, un retorno acumulado varios órdenes de magnitud
por encima de comprar y mantener, con la mitad de exposición.

Ese cálculo es una simulación idealizada, no una promesa — pero establece
que el umbral estaba mal calibrado en la dirección cara.

CORRECCIÓN: se exige coherencia de SIGNO en todas las épocas y que la
mediana supere el umbral, en vez de exigir el umbral en cada una. Además
el umbral baja a 0,04, que sigue dando 0% de falsos positivos (comprobado
con 1.000 series de ruido, ver FALLO 3).


FALLO 2 — Trato injusto a variables con histórico corto
--------------------------------------------------------
Una variable con datos solo desde 2024 tiene UNA época evaluable. El filtro
la marcaba como "estable" si esa única correlación superaba el umbral, lo
cual es un falso positivo por construcción: estabilidad con n=1 no significa
nada.

Y al revés: el funding rate (2019-2026) tiene 3 épocas. Fallar 1 de 3 lo
descartaba igual que fallar 4 de 5, cuando no es la misma evidencia.

CORRECCIÓN: se exige un mínimo de 3 épocas evaluables para emitir veredicto.
Con menos, el resultado se marca como PROVISIONAL y la variable no entra al
panel, pero tampoco se descarta: queda pendiente de más datos.


FALLO 3 — El paso 1 nunca se había medido contra ruido
-------------------------------------------------------
Se probaron 1.000 series de ruido (500 puro, 500 con tendencia tipo serie
macro). Ninguna pasó el paso 1 con el umbral antiguo ni con el nuevo. El
paso es sólido en cuanto a falsos positivos: el problema era el contrario,
demasiados falsos negativos.


LO QUE NO SE CAMBIA Y POR QUÉ
------------------------------
El paso 4 (test de permutación por bloques) se mantiene tal cual. Fue el que
salvó al proyecto de meter el funding rate en el panel: los 95 días con
funding extremo eran en realidad 4 episodios, y p=0,24. Ese paso es el más
valioso del filtro y no necesita ajuste.
"""

import numpy as np
import pandas as pd

# Umbral de correlación. Bajado de 0,05 a 0,04 tras comprobar que mantiene
# 0% de falsos positivos sobre 1.000 series de ruido.
UMBRAL = 0.04

# Épocas mínimas para emitir un veredicto firme.
EPOCAS_MINIMAS = 3

EPOCAS = [("2011", "2014"), ("2015", "2017"), ("2018", "2020"),
          ("2021", "2023"), ("2024", "2026")]


def paso1_estabilidad(x: pd.Series, y: pd.Series, epocas=None,
                      min_obs: int = 100) -> dict:
    """
    ¿Existe la relación y mantiene el mismo signo entre épocas?

    Criterio corregido: coherencia de signo en todas las épocas evaluables
    Y mediana por encima del umbral. Antes se exigía el umbral en cada
    época, lo que descartaba señales reales por una sola época floja.
    """
    epocas = epocas or EPOCAS
    vals, detalle = [], {}
    for a, b in epocas:
        z = pd.concat([x.rename("x"), y.rename("y")], axis=1).loc[a:b].dropna()
        if len(z) >= min_obs:
            c = z["x"].rank().corr(z["y"].rank())
            vals.append(c)
            detalle[f"{a}-{b}"] = round(float(c), 3)

    if len(vals) < EPOCAS_MINIMAS:
        return {
            "pasa": False,
            "provisional": True,
            "motivo": f"solo {len(vals)} épocas evaluables (mínimo {EPOCAS_MINIMAS}). "
                      f"Sin datos suficientes para juzgar estabilidad.",
            "detalle": detalle,
        }

    mismo_signo = all(v > 0 for v in vals) or all(v < 0 for v in vals)
    mediana = float(np.median(vals))
    pasa = mismo_signo and abs(mediana) >= UMBRAL

    return {
        "pasa": pasa,
        "provisional": False,
        "mediana": round(mediana, 3),
        "min": round(min(vals, key=abs), 3),
        "mismo_signo": mismo_signo,
        "n_epocas": len(vals),
        "detalle": detalle,
        "motivo": "" if pasa else (
            "el signo cambia entre épocas" if not mismo_signo
            else f"mediana {mediana:.3f} por debajo del umbral {UMBRAL}"),
    }


def paso2_anticipacion(x: pd.Series, y: pd.Series, desfases=(0, 1, 2, 3, 5),
                       desde: str = "2018") -> dict:
    """
    ¿Anticipa o solo acompaña?

    Compara la correlación contemporánea con la desfasada. Si cae más de un
    60% al día siguiente, la variable se mueve a la vez que BTC y no da
    ventaja de tiempo.
    """
    res = {}
    for k in desfases:
        z = pd.concat([x.shift(k).rename("x"), y.rename("y")],
                      axis=1).loc[desde:].dropna()
        res[k] = round(float(z["x"].rank().corr(z["y"].rank())), 3) if len(z) > 100 else np.nan

    c0 = abs(res.get(0, 0) or 0)
    c1 = abs(res.get(1, 0) or 0)
    retiene = (c1 / c0) if c0 > 0.01 else 0.0

    return {
        "pasa": retiene >= 0.4 and c1 >= UMBRAL,
        "correlaciones": res,
        "retencion": round(retiene, 2),
        "motivo": "" if (retiene >= 0.4 and c1 >= UMBRAL) else
                  f"la correlación cae de {c0:.2f} a {c1:.2f} en un día: acompaña, no anticipa",
    }


def paso3_valor_incremental(base: pd.Series, nueva: pd.Series, y: pd.Series,
                            minimo_pp: float = 3.0) -> dict:
    """
    ¿Aporta algo sobre lo que ya sabemos?

    Compara el R² usando solo las variables que ya tenemos frente a añadir
    la nueva. Si aporta menos de 3 puntos, no compensa la complejidad.
    """
    d = pd.concat([base.rename("b"), nueva.rename("n"), y.rename("y")],
                  axis=1).dropna()
    if len(d) < 50:
        return {"pasa": False, "motivo": "muestra insuficiente"}

    def r2(cols):
        X = np.column_stack([np.ones(len(d))] + [d[c].values for c in cols])
        yy = d["y"].values
        beta = np.linalg.lstsq(X, yy, rcond=None)[0]
        p = X @ beta
        return (1 - ((yy - p) ** 2).sum() / ((yy - yy.mean()) ** 2).sum()) * 100

    solo_base, con_nueva = r2(["b"]), r2(["b", "n"])
    aporta = con_nueva - solo_base

    return {
        "pasa": aporta >= minimo_pp,
        "r2_base": round(solo_base, 1),
        "r2_con_nueva": round(con_nueva, 1),
        "aporta_pp": round(aporta, 1),
        "motivo": "" if aporta >= minimo_pp else
                  f"aporta solo {aporta:.1f} puntos de R² (mínimo {minimo_pp})",
    }


def paso4_significancia(mascara: pd.Series, resultado: pd.Series,
                        n_perm: int = 2000, dias_episodio: int = 21,
                        semilla: int = 0) -> dict:
    """
    ¿Se distingue del azar?

    Test de permutación por BLOQUES, no por observaciones sueltas. Las
    condiciones de mercado vienen en rachas: el funding alto dura semanas.
    Permutar día a día rompería esa estructura e inflaría la significancia.

    Este es el paso que evitó meter el funding rate en el panel.
    """
    z = pd.concat([mascara.rename("m"), resultado.rename("r")], axis=1).dropna()
    sel = z[z["m"]]
    if len(sel) < 20:
        return {"pasa": False, "motivo": "menos de 20 observaciones seleccionadas"}

    # Contar episodios independientes: días separados por más de dias_episodio
    eps, fechas = [], sel.index
    for d in fechas:
        if not eps or (d - eps[-1][-1]).days > dias_episodio:
            eps.append([d])
        else:
            eps[-1].append(d)

    real = float(z[z["m"]]["r"].median() - z[~z["m"]]["r"].median())
    vals = z["r"].values
    n = len(sel)
    rng = np.random.default_rng(semilla)

    difs = []
    for _ in range(n_perm):
        i = rng.integers(0, max(1, len(vals) - n))
        bloque = vals[i:i + n]
        resto = np.delete(vals, slice(i, i + n))
        difs.append(np.median(bloque) - np.median(resto))
    difs = np.array(difs)

    p = float((difs <= real).mean() if real < 0 else (difs >= real).mean())

    return {
        "pasa": p < 0.05 and len(eps) >= 8,
        "p_valor": round(p, 3),
        "episodios": len(eps),
        "dias": len(sel),
        "diferencia": round(real, 4),
        "motivo": "" if (p < 0.05 and len(eps) >= 8) else (
            f"solo {len(eps)} episodios independientes (mínimo 8)" if len(eps) < 8
            else f"p={p:.3f}, no se distingue del azar"),
    }


def evaluar(nombre: str, x: pd.Series, y: pd.Series,
            base: pd.Series = None) -> dict:
    """Aplica los pasos 1-3 en orden y para en el primero que falle."""
    r1 = paso1_estabilidad(x, y)
    if not r1["pasa"]:
        estado = "PROVISIONAL" if r1.get("provisional") else "RECHAZADA"
        return {"variable": nombre, "estado": estado, "paso": 1,
                "motivo": r1["motivo"], "detalle": r1}

    r2 = paso2_anticipacion(x, y)
    if not r2["pasa"]:
        return {"variable": nombre, "estado": "RECHAZADA", "paso": 2,
                "motivo": r2["motivo"], "detalle": r2}

    if base is not None:
        r3 = paso3_valor_incremental(base, x, y)
        if not r3["pasa"]:
            return {"variable": nombre, "estado": "RECHAZADA", "paso": 3,
                    "motivo": r3["motivo"], "detalle": r3}

    return {"variable": nombre, "estado": "PASA", "paso": None,
            "motivo": "supera los pasos aplicados", "detalle": r1}


# =====================================================================
# REGISTRO DE CANDIDATAS EVALUADAS
# =====================================================================
# Cada variable que se ha medido para intentar anticipar el precio de BTC,
# con su veredicto y el motivo. Se mantiene aquí, y no en el historial del
# chat, para que dentro de un año nadie tenga que volver a medir algo que
# ya se probó — ni fiarse de la memoria de quién construyó esto.
#
# "RECHAZADA": se midió con datos suficientes y no pasó el filtro.
# "PENDIENTE_REVISION": indicio real pero sin datos suficientes para
#   concluir. No entra al panel. Se revisa cuando haya más historia.

CANDIDATAS_EVALUADAS = {
    "probabilidad_contexto": {
        "estado": "SIN_EVIDENCIA",
        "motivo": "experimento formal con protocolo congelado antes de "
                  "ejecutar (ver probabilidad_contexto_v1.1.md). Contexto de "
                  "3 dimensiones ya validadas (tendencia SMA200, valoración "
                  "Mayer, volatilidad), 8 celdas, ventanas de 28d no "
                  "solapadas, benchmark por periodo, selección automática "
                  "con penalización por muestra pequeña (Wilson). Con 103 "
                  "observaciones de train repartidas en 8 celdas (2 vacías "
                  "por construcción), ninguna alcanzó simultáneamente n≥20 y "
                  "diferencia ≥10pp frente al benchmark. Paso 4: no hay "
                  "candidata, el test no se abrió. Mejor resultado no "
                  "cualificado: celda [precio>SMA200, valoración alta, vol "
                  "alta], n=27, 63% positivo, +7pp — registrado como señal "
                  "exploratoria no validada, no como indicador. Conclusión "
                  "metodológica: el espacio de 8 celdas es demasiado grande "
                  "para la muestra que 15 años de datos permiten; seguir "
                  "subdividiendo el contexto agravaría el problema. Una "
                  "investigación futura con variables continuas sería un "
                  "experimento nuevo, no una revisión de este.",
    },
    "mvrv": {
        "estado": "RECHAZADA",
        "motivo": "ordenaba bien el retorno a 1 año hasta 2020; se rompió "
                  "desde 2021 (la franja 20-40% pasó a rendir peor que la "
                  "0-20% y la 60-80%)",
    },
    "funding_rate": {
        "estado": "RECHAZADA",
        "motivo": "los extremos parecían preceder caídas mayores, pero solo "
                  "hay 4 episodios independientes desde 2019; p=0.21, no se "
                  "distingue del azar",
    },
    "dxy": {"estado": "RECHAZADA", "motivo": "correlación débil (-0.17) y no anticipa: cae a 0.03 al día siguiente"},
    "tipo_fed": {"estado": "RECHAZADA", "motivo": "correlación nula (±0.03) en las 5 épocas medidas"},
    "vix": {
        "estado": "RECHAZADA",
        "motivo": "no anticipa (se solapa -0.67 con nasdaq); sumado a la "
                  "volatilidad pasada de BTC aporta solo +1.4 puntos de R²",
    },
    "nasdaq": {
        "estado": "ACEPTADA_COMO_CONTEXTO",
        "motivo": "no anticipa (0.23 mismo día, -0.05 al siguiente), pero la "
                  "correlación de 180d es información válida de diversificación. "
                  "En el panel como contexto, no como señal",
    },
    "fear_greed_index": {"estado": "RECHAZADA", "motivo": "se calcula con volatilidad y momentum de BTC; es el precio reetiquetado, no un dato independiente"},
    "hashrate": {
        "estado": "RECHAZADA",
        "motivo": "con 4 años parecía coherente (2 épocas positivas); con 17.7 "
                  "años el signo cambia en 4 de 5 épocas en las 8 formulaciones "
                  "probadas (variación 30d/60d, vs media 200d, hash ribbon)",
    },
    "m2_global": {
        "estado": "RECHAZADA",
        "motivo": "la hipótesis de un adelanto de 70-84 días no se sostiene "
                  "(los valores en esa ventana están entre los más bajos "
                  "medidos); el único desfase con correlación notable (14d, "
                  "+0.20) no es estable entre épocas (-0.04 a +0.39)",
    },
    "flujos_etf": {
        "estado": "PENDIENTE_REVISION",
        "motivo": "3 formulaciones básicas (diario, acum 5d, acum 20d) no "
                  "anticiparon nada. Al ampliar a 8 formulaciones, el acumulado "
                  "a 60 días (corr -0.29) y la aceleración 5d-vs-20d (corr "
                  "+0.15) mantienen el signo fuera de muestra (train "
                  "2024-2025, test 2026). Pero solo hay ~19-21 observaciones "
                  "independientes tras corregir el solapamiento, y probar 16 "
                  "combinaciones exige Bonferroni 0.05/16=0.003, que ninguna "
                  "alcanza. El test de permutación por episodios no es "
                  "ejecutable: solo 2-3 episodios extremos independientes "
                  "desde 2024 (mínimo 8). Revisar de nuevo cuando haya más "
                  "historia — hacia 2028-2029 debería haber episodios "
                  "suficientes. El signo negativo del acumulado a 60 días es "
                  "el dato más intrigante: más entrada institucional "
                  "precediendo peor retorno, lo contrario de la narrativa "
                  "habitual — motivo de más, no de menos, para revisarlo con "
                  "más datos en vez de descartarlo sin más",
    },
    "ciclo_halving": {
        "estado": "ACEPTADA_CON_RESERVAS",
        "motivo": "única candidata que superó el test de significancia. La "
                  "fase 18-24 meses post-halving precede retornos negativos "
                  "en los 4 ciclos existentes (p entre 0.014 y 0.049 según el "
                  "test; acierta 2 de 3 fuera de muestra). n=4 es la "
                  "evidencia más débil de todo lo aceptado en este proyecto. "
                  "No entra como bloque activo del panel — ver halving.py, "
                  "que solo se activa cuando la fecha real se acerca a esa "
                  "ventana. Próxima ventana estimada: 2029-2030",
    },
}

