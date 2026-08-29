"""
SISTEMA DE CONTEXTO BTC — App de Streamlit

Reutiliza contexto_btc.py, onchain.py y niveles.py tal cual — esta app solo
añade la capa de interfaz interactiva encima. No hay lógica de cálculo nueva.

Para correrla en local:
    pip install streamlit pandas numpy plotly requests
    streamlit run app.py

Para desplegarla, ver DEPLOY.md
"""

import os

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from data_loader import load_price_csv
from contexto_btc import calcular_situacion, calcular_valoracion, calcular_ciclo, calcular_riesgo, calcular_caidas_historicas
from niveles import analizar_niveles
from rango import calcular_rango_esperado, dimensionar
import diario as dj

st.set_page_config(
    page_title="Contexto BTC",
    page_icon="◆",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# Estilo — mismo lenguaje visual que el dashboard HTML (papel + tinta)
# ---------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --ink: #14150f;
        --paper: #e8e4d9;
        --dim: #6a6558;
    }

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; color: var(--ink); }

    /* Fondo general y del contenedor principal */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: var(--paper);
        color: var(--ink);
    }

    /* Texto de cabeceras */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Fraunces', serif !important;
        letter-spacing: -0.01em;
        color: var(--ink) !important;
    }

    /* Párrafos, listas, spans y texto general (cubre st.caption, st.markdown, etc.) */
    p, span, li, label, .stMarkdown, [data-testid="stMarkdownContainer"] {
        color: var(--ink) !important;
    }

    .eyebrow {
        font-family: 'IBM Plex Mono', monospace; font-size: 11px;
        letter-spacing: .18em; text-transform: uppercase; color: var(--dim) !important;
    }

    /* Métricas (st.metric): valor, etiqueta y delta */
    div[data-testid="stMetricValue"] {
        font-family: 'Fraunces', serif;
        color: var(--ink) !important;
    }
    div[data-testid="stMetricLabel"] { color: var(--dim) !important; }
    div[data-testid="stMetricDelta"] { color: var(--ink) !important; }

    /* Barra lateral: fondo oscuro propio, así que su texto se queda claro a propósito */
    [data-testid="stSidebar"] { background-color: #1c1d17; }
    [data-testid="stSidebar"] * { color: #e8e4d9 !important; }
    [data-testid="stSidebar"] .eyebrow { color: #9a9488 !important; }

    /* Tablas (st.table) */
    [data-testid="stTable"] * { color: var(--ink) !important; }
    table { color: var(--ink) !important; }

    /* Inputs de texto y number_input dentro del área principal (no aplica, están en sidebar) */
    input { color: var(--ink); }

    /* Los mensajes de alerta (info/warning) ya traen su propio contraste, no se tocan */
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------
# Carga de datos (cacheada para no recalcular en cada interacción)
# ---------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="Cargando histórico de precio...")
def cargar_datos(path_csv):
    return load_price_csv(path_csv)


@st.cache_data(ttl=3600, show_spinner="Cargando datos on-chain...")
def cargar_onchain(path_csv, _firma):
    """
    _firma: (tamaño, fecha de modificación) del archivo. No se usa dentro,
    pero al formar parte de la clave de caché hace que Streamlit recargue
    solo cuando el archivo cambia de verdad.

    POR QUÉ (28/08/2026): antes, si se abría la app sin el CSV, se cacheaba
    None durante una hora. Al generar luego el archivo, la app seguía diciendo
    "no se encontró" hasta reiniciar el servidor. Con la firma, en cuanto el
    CSV aparece o cambia, la caché se invalida sola.
    """
    from onchain import cargar_onchain as _cargar
    try:
        return _cargar(path_csv)
    except FileNotFoundError:
        return None
    except Exception as e:
        # El archivo existe pero no se puede leer: eso es un error real,
        # no un "aún no lo has descargado". Se muestra tal cual.
        st.error(f"**{path_csv}** existe pero no se pudo leer: {type(e).__name__} — {e}")
        return None


def _firma_archivo(path):
    """(tamaño, mtime) del archivo, o None si no existe."""
    try:
        st_info = os.stat(path)
        return (st_info.st_size, st_info.st_mtime)
    except OSError:
        return None


# ---------------------------------------------------------------
# Sidebar — controles
# ---------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="eyebrow">Configuración</div>', unsafe_allow_html=True)
    st.markdown("### Tu situación")

    capital = st.number_input(
        "Capital que consideras invertir (€)",
        min_value=0, value=1000, step=100,
        help="Se usa solo para calcular tu riesgo real en euros. No se guarda en ningún sitio.",
    )

    st.markdown("---")
    st.markdown("### Datos")
    archivo_precio = st.text_input("Archivo de precio", value="btc_long.csv")
    archivo_onchain = st.text_input("Archivo on-chain (opcional)", value="btc_onchain.csv")

    st.markdown("---")
    st.markdown("### Diario")
    subido = st.file_uploader(
        "Cargar diario.csv", type="csv",
        help="Sube tu diario para continuarlo. Sin esto, empiezas uno nuevo.",
    )

    st.markdown("---")
    st.caption(
        "Este panel describe la situación actual. No predice el futuro, "
        "no recomienda comprar ni vender, y no es asesoramiento financiero."
    )

# El diario vive en la sesión. En Streamlit Cloud el disco es efímero, así que
# la persistencia real es el CSV que el usuario descarga y vuelve a subir.
if "diario" not in st.session_state:
    st.session_state.diario = dj.diario_vacio()
if subido is not None and not st.session_state.get("_diario_cargado"):
    try:
        st.session_state.diario = dj.cargar(subido)
        st.session_state._diario_cargado = True
    except Exception as e:
        st.sidebar.error(f"No se pudo leer el diario: {e}")

# ---------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------
try:
    df = cargar_datos(archivo_precio)
except FileNotFoundError:
    st.error(
        f"No se encuentra **{archivo_precio}**. Descárgalo primero con "
        f"`python fetch_long_history.py --source bitstamp --out {archivo_precio}` "
        f"y colócalo en esta misma carpeta."
    )
    st.stop()
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.stop()

df_onchain = cargar_onchain(archivo_onchain, _firma_archivo(archivo_onchain))

s = calcular_situacion(df)
v = calcular_valoracion(df)
c = calcular_ciclo(df)

# ---------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------
st.markdown('<div class="eyebrow">Sistema de contexto · no es una recomendación</div>', unsafe_allow_html=True)
st.title("¿Dónde está Bitcoin?")

_MESES_ES = {
    "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
    "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
    "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre",
}
_fecha_en = df.index[-1].strftime("%d de %B de %Y")
_fecha_es = _fecha_en
for _en, _es in _MESES_ES.items():
    _fecha_es = _fecha_es.replace(_en, _es)
st.caption(f"Datos a {_fecha_es}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Precio", f"${s['precio']:,.0f}")
col2.metric("Desde máximos", f"{s['dist_ath']:+.1f}%")
col3.metric("30 días", f"{c['ret_30d']:+.1f}%")
col4.metric("1 año", f"{c['ret_365d']:+.1f}%")

# Gráfico de precio interactivo (esto es lo que gana mucho respecto al HTML estático)
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df.index, y=df["close"], mode="lines",
    line=dict(color="#14150f", width=1.3), name="Precio",
    hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=df.index, y=df["close"].rolling(200).mean(), mode="lines",
    line=dict(color="#c98a4f", width=1, dash="dot"), name="SMA 200",
    hovertemplate="SMA200: $%{y:,.0f}<extra></extra>",
))
fig.update_layout(
    height=320, margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="#e8e4d9", paper_bgcolor="#e8e4d9",
    font=dict(color="#14150f"),
    xaxis=dict(showgrid=False, color="#14150f"),
    yaxis=dict(showgrid=True, gridcolor="#d5d0c2", type="log", color="#14150f"),
    hovermode="x unified", showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------
# 01 — Medias
# ---------------------------------------------------------------
st.subheader("01 · Respecto a sus medias")
col1, col2, col3 = st.columns(3)
col1.metric("Media 50 días", f"{s['vs_sma50']:+.1f}%", f"${s['sma50']:,.0f}")
col2.metric("Media 200 días", f"{s['vs_sma200']:+.1f}%", f"${s['sma200']:,.0f}")
if pd.notna(s["vs_sma1000"]):
    col3.metric("Media 1000 días", f"{s['vs_sma1000']:+.1f}%", f"${s['sma1000']:,.0f}")

st.divider()

# ---------------------------------------------------------------
# 02 — Valoración
# ---------------------------------------------------------------
st.subheader("02 · ¿Caro o barato?")
pct = v["percentil"]
col1, col2 = st.columns([1, 2])
with col1:
    st.metric(v["etiqueta"].title(), f"Percentil {pct:.0f}")
    st.caption(f"Ratio precio/SMA200: {v['mayer_multiple']:.2f}")
with col2:
    st.progress(int(pct))
    st.caption(f"En el {pct:.0f}% de su historia, BTC estuvo más barato que ahora en términos relativos.")
st.info(v["nota"], icon="ℹ️")
st.caption(
    "⚠ Medido sobre 2011-2026: este percentil ordenaba bien el retorno del año "
    "siguiente hasta 2020, pero ese orden se rompió a partir de 2021 (la franja "
    "20-40 pasó a rendir peor que la 0-20 y que la 60-80). Lo único que ha "
    "mantenido el mismo signo en ambas épocas es que el 20% más caro va seguido "
    "de peores retornos. Léelo como contexto histórico, no como señal actual."
)

st.divider()

# ---------------------------------------------------------------
# 03 — Momento del ciclo
# ---------------------------------------------------------------
st.subheader("03 · Momento del ciclo")
col1, col2, col3 = st.columns(3)
col1.metric("Caída desde máximos", f"{c['drawdown_actual']:+.1f}%", f"hace {c['dias_desde_ath']:.0f} días", delta_color="off")
col2.metric("Volatilidad 90 días", f"{s['vol_actual']:.0f}%", f"histórica: {s['vol_historica']:.0f}%", delta_color="off")
col3.metric("Rentabilidad 90 días", f"{c['ret_90d']:+.1f}%")

st.divider()

# ---------------------------------------------------------------
# 04 — Niveles clave
# ---------------------------------------------------------------
st.subheader("04 · Dónde ha reaccionado el precio")
niv = analizar_niveles(df, meses=12)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Zonas por encima**")
    if niv["resistencias"]:
        for z in niv["resistencias"]:
            dist = (z["centro"] / s["precio"] - 1) * 100
            st.markdown(f"`${z['minimo']:,.0f} – ${z['maximo']:,.0f}`  {dist:+.1f}% · {z['toques']} toques")
    else:
        st.caption("Sin zonas con 2+ toques por encima")
with col2:
    st.markdown("**Zonas por debajo**")
    if niv["soportes"]:
        for z in niv["soportes"]:
            dist = (z["centro"] / s["precio"] - 1) * 100
            st.markdown(f"`${z['minimo']:,.0f} – ${z['maximo']:,.0f}`  {dist:+.1f}% · {z['toques']} toques")
    else:
        st.caption("Sin zonas con 2+ toques por debajo")

st.caption(
    "Cada zona agrupa máximos o mínimos donde el precio ya giró antes. "
    "El ancho sale del ATR real, no de un porcentaje elegido a mano. "
    "Que haya reaccionado ahí antes no significa que vuelva a hacerlo."
)

st.divider()

# ---------------------------------------------------------------
# 05 — On-chain (si hay datos)
# ---------------------------------------------------------------
if df_onchain is not None:
    from onchain import calcular_metricas, interpretar_mvrv_por_percentil, percentil_historico, REFERENCIA_EXTERNA_MVRV

    st.subheader("05 · Fundamental de la red")
    dfo = calcular_metricas(df_onchain)
    u = dfo.iloc[-1]
    mvrv, z, rp = u["mvrv"], u["mvrv_zscore"], u["realized_price"]
    pct_mvrv = percentil_historico(dfo["mvrv"], mvrv)
    etiq, nota = interpretar_mvrv_por_percentil(pct_mvrv)

    col1, col2, col3 = st.columns(3)
    col1.metric("MVRV", f"{mvrv:.2f}", f"percentil {pct_mvrv:.0f}%", delta_color="off")
    col2.metric("MVRV Z-Score", f"{z:.2f}")
    col3.metric("Precio realizado", f"${rp:,.0f}")

    st.info(f"**{etiq}** — {nota}", icon="🔗")

    g = REFERENCIA_EXTERNA_MVRV["glassnode_bandas_frecuencia"]
    cq = REFERENCIA_EXTERNA_MVRV["cryptoquant"]
    st.caption(
        f"La etiqueta sale del percentil sobre nuestra serie (BGeometrics), no de umbrales "
        f"fijos de un proveedor. Referencia externa citada: Glassnode marca extremos en "
        f"<{g['extreme_lows']} y >{g['extremely_high']}; CryptoQuant en <{cq['posible_fondo']} y >{cq['posible_techo']}."
    )
    st.divider()
else:
    st.info(
        f"No se encontró **{archivo_onchain}**. Este bloque se activa descargando datos con "
        f"`python fetch_onchain.py --out {archivo_onchain}`.",
        icon="ℹ️",
    )
    st.divider()

# ---------------------------------------------------------------
# 06 — Rango esperado y dimensionamiento
#
# Este bloque es el único que se apoya en una relación validada por épocas
# (persistencia de volatilidad a 30 días: Spearman 0.53 / 0.45 / 0.49 en
# 2011-2015, 2016-2020 y 2021-2026, con ventanas no solapadas). Ver rango.py
# para el detalle de por qué el horizonte es 30 días y no 90.
# ---------------------------------------------------------------
st.subheader("06 · Cuánto puede moverse")

rg = calcular_rango_esperado(df)

col1, col2 = st.columns([1, 2])
with col1:
    st.metric(
        f"Volatilidad {rg['cuartil']}",
        f"{rg['vol']*100:.0f}%",
        f"percentil {rg['vol_pct']:.0f}",
        delta_color="off",
    )
with col2:
    st.caption(
        f"Con volatilidad **{rg['cuartil']}**, esto es cuánto osciló el precio "
        f"en un mes a lo largo de {rg['n_historico']} meses históricos comparables. "
        "No indica dirección — solo cuánto terreno suele cubrir el precio."
    )

tabla_rango = pd.DataFrame([
    {
        "Frecuencia": nombre,
        "Oscilación": f"menos de {rg['bandas'][k]['amplitud']*100:.0f}%",
        "Banda de precio": f"${rg['bandas'][k]['suelo']:,.0f} – ${rg['bandas'][k]['techo']:,.0f}",
    }
    for k, nombre in [
        ("p50", "La mitad de los meses"),
        ("p75", "3 de cada 4 meses"),
        ("p95", "1 de cada 20 meses"),
    ]
])
st.table(tabla_rango.set_index("Frecuencia"))

st.caption(
    "Por qué 30 días y no 90: la volatilidad se predice a sí misma de forma "
    "estable a un mes en las tres épocas medidas. A 90 días la relación es muy "
    "fuerte desde 2021 pero era casi nula antes de 2016 — aparece y desaparece "
    "según la época, así que no se usa."
)

st.divider()

# ---------------------------------------------------------------
# 07 — Dimensionamiento (parte de la pérdida tolerable, no del capital)
# ---------------------------------------------------------------
st.subheader("07 · Cuánto exponer")
st.markdown(
    "En vez de partir de cuánto quieres invertir, esto parte de **cuánto puedes "
    "perder sin que te cambie los planes** — y calcula hacia atrás."
)

perdida_tol = st.slider(
    "Pérdida que podrías asumir sin que te afecte (€)",
    min_value=50, max_value=int(max(capital, 100)),
    value=int(max(capital * 0.15, 50)), step=50,
)

dim = dimensionar(capital, perdida_tol, rg)
tabla_dim = pd.DataFrame([
    {
        "Escenario": nombre.capitalize(),
        "Caída asumida": f"−{e['caida_pct']:.0f}%",
        "Capital a exponer": (
            f"{e['capital_max']:,.0f} €" +
            (" (todo el disponible)" if e["supera_disponible"] else "")
        ),
    }
    for nombre, e in dim.items()
])
st.table(tabla_dim.set_index("Escenario"))

st.caption(
    "El escenario adverso usa el percentil 95 de oscilación histórica: no es el "
    "peor caso imaginable, es el peor caso *habitual*. Que el cálculo permita "
    "exponer una cantidad no significa que debas hacerlo."
)

st.divider()

# ---------------------------------------------------------------
# 08 — Riesgo real (interactivo: cambia con el capital de la sidebar)
# ---------------------------------------------------------------
st.subheader("08 · Tu riesgo real")
st.markdown(f"Si inviertes **{capital:,.0f} €** hoy, esto es lo que verías en pantalla:")

r = calcular_riesgo(capital, s["precio"])
tabla_riesgo = pd.DataFrame([
    {"Si BTC cae": f"{e['caida_pct']}%", "Precio": f"${e['precio_btc']:,.0f}",
     "Te quedan": f"{e['valor_restante']:,.0f} €", "Pierdes": f"−{e['perdida']:,.0f} €"}
    for e in r["escenarios"]
])
st.table(tabla_riesgo.set_index("Si BTC cae"))

st.markdown("**Caídas que BTC ya ha tenido:**")
caidas = calcular_caidas_historicas(df)
tabla_hist = pd.DataFrame([
    {"Periodo": periodo, "Caída": f"{pct}%", "Te habrían quedado": f"{capital * (1 + pct/100):,.0f} €"}
    for periodo, pct in caidas
])
st.table(tabla_hist.set_index("Periodo"))

st.warning("¿Podrías ver esos números durante uno o dos años sin vender? Si la respuesta es no, la cantidad es demasiado alta.", icon="⚠️")

st.divider()

# ---------------------------------------------------------------
# 09 — Diario de decisiones
#
# Razón de existir: el análisis sobre 15 años concluyó que la dirección del
# precio es impredecible (R² ≈ 0,1%). Si no hay ventaja en la señal, lo único
# que queda es no cometer errores evitables — y eso exige registrar el porqué
# ANTES de conocer el resultado, porque la memoria lo reescribe después.
# ---------------------------------------------------------------
st.subheader("09 · Diario de decisiones")

d = st.session_state.diario
ctx = dj.capturar_contexto(s, v, c, rg)

tab_nueva, tab_revision, tab_historial = st.tabs(
    ["Registrar decisión", "Revisión", f"Historial ({len(d)})"]
)

with tab_nueva:
    st.caption(
        "Se guarda automáticamente el estado del panel de hoy, para que la "
        "revisión no dependa de lo que recuerdes haber mirado."
    )

    col1, col2 = st.columns(2)
    with col1:
        tipo = st.selectbox("Qué haces", dj.TIPOS)
        importe = st.number_input("Importe (€)", min_value=0, value=0, step=50,
                                  disabled=(tipo == "No hacer nada"))
    with col2:
        estado = st.selectbox("Cómo estás al decidir", dj.ESTADOS)
        confianza = st.slider("Confianza en la decisión", 1, 5, 3)

    hipotesis = st.text_area(
        "Por qué haces esto",
        placeholder="La razón concreta, hoy. Sin adornos — nadie más lo va a leer.",
        height=80,
    )

    st.markdown("**Qué te haría admitir que te equivocaste**")
    st.caption(
        "Escribirlo ahora es lo que después distingue «me equivoqué» de "
        "«todavía no ha pasado». Sin esto, una pérdida no tiene final."
    )
    col1, col2 = st.columns(2)
    with col1:
        inval_precio = st.number_input(
            "Por debajo de este precio ($)", min_value=0,
            value=int(s["precio"] * 0.75), step=500,
        )
    with col2:
        inval_cond = st.text_input(
            "O si ocurre esto",
            placeholder="ej. seis meses sin recuperar la media de 200 días",
        )

    if st.button("Guardar en el diario", type="primary"):
        if not hipotesis.strip():
            st.error("Falta el porqué. Es el campo que da sentido al registro.")
        else:
            st.session_state.diario = dj.anadir(d, {
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "tipo": tipo,
                "precio": s["precio"],
                "importe": importe if tipo != "No hacer nada" else 0,
                "hipotesis": hipotesis.strip(),
                "invalidacion_precio": inval_precio or None,
                "invalidacion_condicion": inval_cond.strip() or None,
                "estado_animo": estado,
                "confianza": confianza,
                **ctx,
            })
            st.success("Guardado. Descarga el CSV en la pestaña Historial para no perderlo.")
            st.rerun()

with tab_revision:
    rev = dj.revisar(d, precio_actual=s["precio"])

    if not rev["suficientes"]:
        st.info(
            f"Llevas {rev['n']} registros. La revisión se activa a partir de "
            f"{dj.MINIMO_PARA_ANALIZAR} — faltan {rev['faltan']}.\n\n"
            "No es una restricción arbitraria: buscar patrones en 3 decisiones "
            "es el mismo error de sobreajuste que rompió el motor de tendencia.",
            icon="ℹ️",
        )
    elif not rev["avisos"]:
        st.success(
            f"{rev['n']} registros revisados y ningún patrón problemático detectado. "
            "Eso no significa que las decisiones fueran acertadas — significa que "
            "fueron consistentes con tus propias reglas.",
            icon="✅",
        )
    else:
        st.markdown(f"**{len(rev['avisos'])} patrones detectados en {rev['n']} registros:**")
        for a in rev["avisos"]:
            st.warning(a, icon="⚠️")

    if rev["stats"]:
        st.markdown("**Resumen**")
        stt = rev["stats"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Decisiones", stt.get("total", 0))
        col2.metric("Con criterio de error", stt.get("con_invalidacion", 0))
        if "acierto" in stt:
            col3.metric("Acierto", f"{stt['acierto']:.0f}%",
                        f"{stt.get('revisadas', 0)} revisadas", delta_color="off")

with tab_historial:
    if len(d) == 0:
        st.caption("Todavía no hay registros.")
    else:
        st.dataframe(
            d[["fecha", "tipo", "precio", "importe", "hipotesis",
               "invalidacion_precio", "estado_animo"]],
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            "Descargar diario.csv", d.to_csv(index=False).encode("utf-8"),
            "diario.csv", "text/csv", type="primary",
        )
        st.caption(
            "Descárgalo cada vez que añadas algo. La app no guarda nada entre "
            "sesiones: el archivo es tuyo y solo tuyo."
        )

st.divider()
st.caption(
    f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} · "
    "Precio: Bitstamp · On-chain: BGeometrics (bitcoin-data.com)"
)
