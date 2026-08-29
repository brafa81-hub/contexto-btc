"""
DIARIO DE DECISIONES — registra el porqué ANTES de saber el resultado.

POR QUÉ EXISTE
--------------
Del análisis de 15 años de datos salió que la dirección del precio de BTC es
esencialmente impredecible (R² ≈ 0,1% fuera de muestra). Si no hay ventaja en
la señal, la única fuente de mejora que queda es no cometer errores evitables.
Y los errores evitables solo se pueden detectar si quedan registrados antes de
conocer el desenlace.

EL PROBLEMA QUE RESUELVE
------------------------
La memoria humana reescribe. Después de una operación que sale mal, el recuerdo
es "ya sospechaba que era mala idea". Después de una que sale bien, es "lo tenía
claro". Ninguna de las dos versiones sirve para aprender, porque ambas se
escribieron después de conocer el resultado.

Este módulo obliga a escribir tres cosas ANTES:
  1. La hipótesis (por qué haces esto)
  2. Qué la invalidaría (a qué precio o en qué condición admites que fallaste)
  3. Tu estado al decidir (calma, prisa, FOMO, miedo)

Y captura automáticamente el estado del panel en ese momento, para que no
dependa de lo que recuerdes haber mirado.

QUÉ DETECTA LA REVISIÓN
-----------------------
Patrones que el propio sujeto no ve en sí mismo:
  - Incumplir tu propio criterio de invalidación (el error más caro)
  - Aumentar tamaño después de acertar (exceso de confianza)
  - Comprar tras subidas fuertes (perseguir precio)
  - Decidir en estados emocionales que históricamente te salen mal
  - Aumentar frecuencia de decisiones (sobreoperar)

LIMITACIÓN HONESTA
------------------
Con menos de ~10 registros no hay nada que analizar y el módulo lo dirá en vez
de inventar un patrón. Detectar tendencias en 3 operaciones es exactamente el
mismo error de sobreajuste que rompió el motor de tendencia.

PERSISTENCIA
------------
En Streamlit Cloud el disco es efímero: lo que se escribe se pierde al
redesplegar. Por eso el diario vive en un CSV que descargas y vuelves a subir.
En local sí se puede guardar directamente en disco.
"""

import numpy as np
import pandas as pd

COLUMNAS = [
    "fecha", "tipo", "precio", "importe", "hipotesis",
    "invalidacion_precio", "invalidacion_condicion", "estado_animo",
    "confianza", "vol_30d", "percentil_valoracion", "drawdown", "vs_sma200",
    "revisada", "resultado", "notas_revision",
]

TIPOS = ["Entrar", "Ampliar", "Reducir", "Salir", "No hacer nada"]

ESTADOS = [
    "Tranquilo, sin prisa",
    "Con prisa / miedo a perderlo",
    "Preocupado por perder dinero",
    "Confiado tras un acierto",
    "Frustrado tras un error",
]

# Estados que la literatura y el sentido común asocian a peores decisiones.
# No se usan para bloquear nada — solo para contarlos en la revisión.
ESTADOS_RIESGO = [
    "Con prisa / miedo a perderlo",
    "Confiado tras un acierto",
    "Frustrado tras un error",
]


def diario_vacio() -> pd.DataFrame:
    """DataFrame vacío con el esquema correcto."""
    return pd.DataFrame(columns=COLUMNAS)


def cargar(path_o_buffer) -> pd.DataFrame:
    """Carga un diario existente, tolerando columnas que falten."""
    df = pd.read_csv(path_o_buffer)
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = np.nan
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df[COLUMNAS].sort_values("fecha").reset_index(drop=True)


def capturar_contexto(situacion: dict, valoracion: dict, ciclo: dict,
                      rango: dict) -> dict:
    """
    Fotografía objetiva del panel en el momento de decidir.

    Se guarda automáticamente para que la revisión posterior no dependa de lo
    que el usuario recuerde haber visto, que es justo lo que la memoria falsea.
    """
    return {
        "vol_30d": round(rango.get("vol", np.nan) * 100, 1),
        "percentil_valoracion": round(valoracion.get("percentil", np.nan), 0),
        "drawdown": round(ciclo.get("drawdown_actual", np.nan), 1),
        "vs_sma200": round(situacion.get("vs_sma200", np.nan), 1),
    }


def anadir(df: pd.DataFrame, registro: dict) -> pd.DataFrame:
    """Añade una decisión al diario."""
    fila = {c: registro.get(c, np.nan) for c in COLUMNAS}
    fila["revisada"] = False
    return pd.concat([df, pd.DataFrame([fila])], ignore_index=True)


# ---------------------------------------------------------------
# Revisión — detección de patrones
# ---------------------------------------------------------------

MINIMO_PARA_ANALIZAR = 10


def _incumplimientos(df: pd.DataFrame, precio_actual: float) -> list:
    """
    Decisiones donde se cruzó el precio de invalidación y no se registró salida.

    Este es el patrón más caro de todos: definir un criterio de error y luego
    no aplicarlo. Se detecta comparando el precio de invalidación declarado
    con el mínimo alcanzado después, no con el precio de hoy.
    """
    avisos = []
    abiertas = df[(df["tipo"].isin(["Entrar", "Ampliar"])) &
                  (df["invalidacion_precio"].notna())]
    for _, r in abiertas.iterrows():
        inval = r["invalidacion_precio"]
        if pd.isna(inval) or inval <= 0:
            continue
        # ¿hubo una salida registrada después de esta entrada?
        posteriores = df[(df["fecha"] > r["fecha"]) &
                         (df["tipo"].isin(["Reducir", "Salir"]))]
        if precio_actual < inval and len(posteriores) == 0:
            avisos.append(
                f"Decisión del {r['fecha']:%d/%m/%Y}: dijiste que te equivocabas "
                f"por debajo de ${inval:,.0f}. El precio está en ${precio_actual:,.0f} "
                f"y no hay ninguna salida registrada."
            )
    return avisos


def _tamano_tras_acierto(df: pd.DataFrame) -> list:
    """¿Sube el importe después de una operación que salió bien?"""
    avisos = []
    ops = df[df["tipo"].isin(["Entrar", "Ampliar"])].dropna(subset=["importe"])
    if len(ops) < 4:
        return avisos
    con_res = df.dropna(subset=["resultado"])
    if len(con_res) < 3:
        return avisos
    tras_bien, tras_mal = [], []
    for i in range(1, len(ops)):
        previa = con_res[con_res["fecha"] < ops.iloc[i]["fecha"]]
        if len(previa) == 0:
            continue
        ult = previa.iloc[-1]["resultado"]
        (tras_bien if str(ult).lower().startswith("g") else tras_mal).append(
            ops.iloc[i]["importe"])
    if len(tras_bien) >= 2 and len(tras_mal) >= 2:
        mb, mm = np.mean(tras_bien), np.mean(tras_mal)
        if mb > mm * 1.3:
            avisos.append(
                f"Tras una operación ganadora inviertes de media {mb:,.0f} €; "
                f"tras una perdedora, {mm:,.0f} €. Una diferencia del "
                f"{(mb/mm-1)*100:.0f}% sugiere que el resultado anterior te "
                f"está moviendo el tamaño, no el análisis."
            )
    return avisos


def _perseguir_precio(df: pd.DataFrame) -> list:
    """¿Las compras llegan después de subidas fuertes?"""
    avisos = []
    compras = df[df["tipo"].isin(["Entrar", "Ampliar"])].dropna(subset=["vs_sma200"])
    if len(compras) < 4:
        return avisos
    extendidas = (compras["vs_sma200"] > 20).sum()
    if extendidas / len(compras) > 0.5:
        avisos.append(
            f"{extendidas} de tus {len(compras)} compras se hicieron con el precio "
            f"más de un 20% por encima de su media de 200 días. Puede ser "
            f"deliberado, pero conviene comprobar que no es reacción a la subida."
        )
    return avisos


def _estados_emocionales(df: pd.DataFrame) -> list:
    """¿En qué estado se decide, y ese estado correlaciona con peor resultado?"""
    avisos = []
    con_estado = df.dropna(subset=["estado_animo"])
    if len(con_estado) < 6:
        return avisos
    riesgo = con_estado[con_estado["estado_animo"].isin(ESTADOS_RIESGO)]
    frac = len(riesgo) / len(con_estado)
    if frac > 0.4:
        top = riesgo["estado_animo"].value_counts().idxmax()
        avisos.append(
            f"El {frac*100:.0f}% de tus decisiones se tomaron en un estado de "
            f"riesgo, sobre todo «{top}». Es el dato más accionable del diario: "
            f"puedes imponerte esperar 24 h cuando lo detectes."
        )
    # ¿el estado predice el resultado?
    con_res = con_estado.dropna(subset=["resultado"])
    if len(con_res) >= 8:
        en_riesgo = con_res["estado_animo"].isin(ESTADOS_RIESGO)
        gana = con_res["resultado"].astype(str).str.lower().str.startswith("g")
        if en_riesgo.sum() >= 3 and (~en_riesgo).sum() >= 3:
            tasa_r, tasa_c = gana[en_riesgo].mean(), gana[~en_riesgo].mean()
            if tasa_c - tasa_r > 0.2:
                avisos.append(
                    f"Decidiendo en calma aciertas el {tasa_c*100:.0f}% de las veces; "
                    f"en estado de riesgo, el {tasa_r*100:.0f}%. Muestra pequeña, "
                    f"pero apunta en una dirección clara."
                )
    return avisos


def _frecuencia(df: pd.DataFrame) -> list:
    """¿Está aumentando el ritmo de decisiones?"""
    avisos = []
    activas = df[df["tipo"] != "No hacer nada"].dropna(subset=["fecha"])
    if len(activas) < 8:
        return avisos
    mitad = len(activas) // 2
    p1, p2 = activas.iloc[:mitad], activas.iloc[mitad:]
    d1 = (p1["fecha"].max() - p1["fecha"].min()).days or 1
    d2 = (p2["fecha"].max() - p2["fecha"].min()).days or 1
    r1, r2 = len(p1) / d1 * 30, len(p2) / d2 * 30
    if r2 > r1 * 1.5:
        avisos.append(
            f"Tu ritmo pasó de {r1:.1f} a {r2:.1f} decisiones al mes. "
            f"El sistema está diseñado para revisión semanal; un ritmo creciente "
            f"suele preceder a operar por aburrimiento o por ansiedad."
        )
    return avisos


def _sin_invalidacion(df: pd.DataFrame) -> list:
    """¿Cuántas decisiones se tomaron sin definir qué las invalidaría?"""
    avisos = []
    entradas = df[df["tipo"].isin(["Entrar", "Ampliar"])]
    if len(entradas) < 3:
        return avisos
    sin = entradas["invalidacion_precio"].isna() & entradas["invalidacion_condicion"].isna()
    if sin.sum() / len(entradas) > 0.3:
        avisos.append(
            f"{sin.sum()} de {len(entradas)} entradas no tienen criterio de "
            f"invalidación. Sin él no hay forma de distinguir «me equivoqué» "
            f"de «todavía no ha pasado», que es como se sostienen las pérdidas."
        )
    return avisos


def revisar(df: pd.DataFrame, precio_actual: float = None) -> dict:
    """
    Revisión completa del diario.

    Devuelve avisos y estadísticas. Si no hay registros suficientes lo dice
    claramente en vez de fabricar conclusiones sobre 3 datos.
    """
    n = len(df)
    if n < MINIMO_PARA_ANALIZAR:
        return {
            "suficientes": False,
            "n": n,
            "faltan": MINIMO_PARA_ANALIZAR - n,
            "avisos": [],
            "stats": _estadisticas(df),
        }

    avisos = []
    if precio_actual:
        avisos += _incumplimientos(df, precio_actual)
    avisos += _sin_invalidacion(df)
    avisos += _tamano_tras_acierto(df)
    avisos += _perseguir_precio(df)
    avisos += _estados_emocionales(df)
    avisos += _frecuencia(df)

    return {
        "suficientes": True,
        "n": n,
        "avisos": avisos,
        "stats": _estadisticas(df),
    }


def _estadisticas(df: pd.DataFrame) -> dict:
    """Resumen numérico, útil aunque no haya registros para detectar patrones."""
    if len(df) == 0:
        return {}
    activas = df[df["tipo"] != "No hacer nada"]
    con_res = df.dropna(subset=["resultado"])
    st = {
        "total": len(df),
        "activas": len(activas),
        "no_hacer_nada": len(df) - len(activas),
        "con_invalidacion": int(df["invalidacion_precio"].notna().sum()),
    }
    if len(con_res) > 0:
        gana = con_res["resultado"].astype(str).str.lower().str.startswith("g")
        st["revisadas"] = len(con_res)
        st["acierto"] = gana.mean() * 100
    if df["estado_animo"].notna().any():
        st["estado_frecuente"] = df["estado_animo"].value_counts().idxmax()
    return st
