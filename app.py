"""
SISTEMA DE CONTEXTO BTC — App de Streamlit

Reutiliza contexto_btc.py, onchain.py y niveles.py tal cual — esta app solo
añade la capa de interfaz interactiva encima. No hay lógica de cálculo nueva.

Para correrla en local:
    pip install streamlit pandas numpy plotly requests
    streamlit run app.py

Para desplegarla, ver DEPLOY.md
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from data_loader import load_price_csv
from contexto_btc import calcular_situacion, calcular_valoracion, calcular_ciclo, calcular_riesgo, calcular_caidas_historicas
from niveles import analizar_niveles

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
def cargar_onchain(path_csv):
    from onchain import cargar_onchain as _cargar
    try:
        return _cargar(path_csv)
    except FileNotFoundError:
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
    st.caption(
        "Este panel describe la situación actual. No predice el futuro, "
        "no recomienda comprar ni vender, y no es asesoramiento financiero."
    )

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

df_onchain = cargar_onchain(archivo_onchain)

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
# 06 — Riesgo real (interactivo: cambia con el capital de la sidebar)
# ---------------------------------------------------------------
st.subheader("06 · Tu riesgo real")
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
st.caption(
    f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} · "
    "Precio: Bitstamp · On-chain: BGeometrics (bitcoin-data.com)"
)
