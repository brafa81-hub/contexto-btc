"""
Script de un solo uso — Tablero de Decision (diseno aprobado 2026-09-23/24).

Toca SOLO app.py y diario.py. Verifica SHA-256 antes de tocar nada y aborta
si algun fichero no es el esperado o si algun reemplazo no encaja exactamente
una vez. No toca v2.json, registro.json, filtro.py ni cadena.py.

Uso:  python tablero_decision.py   (desde la raiz del repo)
"""

import hashlib
import sys

ESPERADO = {
    "app.py": "c203f1b449609766ea5eaecc12bf57ca40ebebbdd43cb0a96a659410f98a90c5",
    "diario.py": "355ddc0b98fc91c759ecb2244bb9ba47f2cf31c21adb08bf70609e82238c3022",
}


def sha(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def reemplazar(texto, viejo, nuevo, nombre):
    n = texto.count(viejo)
    if n != 1:
        sys.exit(f"ABORTADO: '{nombre}' aparece {n} veces (se esperaba 1).")
    return texto.replace(viejo, nuevo)


for f, h in ESPERADO.items():
    if sha(f) != h:
        sys.exit(f"ABORTADO: {f} no coincide con el hash esperado.")

# ------------------------------------------------------------------ app.py
with open("app.py", encoding="utf-8") as fh:
    app = fh.read()

VIEJO_CAL = '''# ---------------------------------------------------------------
# Calendario — lo único del panel que no necesita demostrar poder
# predictivo, porque no predice: solo dice qué está programado.
# BTC correlaciona 0,33 con el Nasdaq, así que lo que mueve la bolsa
# estadounidense lo mueve con ella.
# ---------------------------------------------------------------
_cal = estado_calendario()
if not _cal["ok"]:
    st.warning(_cal["mensaje"], icon="📅")

_ev = eventos_proximos(dias=45, limite=4)
if _ev:
    _lineas = []
    for _e in _ev:
        _cuando = ("hoy" if _e["dias"] == 0 else
                   "mañana" if _e["dias"] == 1 else f"en {_e['dias']} días")
        _marca = "**" if _e["relevancia"] == "alta" else ""
        _lineas.append(f"{_marca}{_e['nombre']}{_marca} · {_cuando} ({_e['fecha']:%d/%m})")
    st.info("📅 " + "  ·  ".join(_lineas), icon=None)
    st.caption(
        "Eventos programados que mueven la bolsa estadounidense, y con ella a BTC "
        "(correlación 0,33). No indica dirección ni magnitud: solo que ese día "
        "suele haber más movimiento del habitual."
    )
'''

NUEVO_CAL = '''# ---------------------------------------------------------------
# Tablero de decisión (diseño aprobado 2026-09-23/24).
# Dos semáforos independientes + una línea descriptiva. NO hay semáforo de
# dirección: las mediciones P1-P4 concluyeron que "la dirección a 30 días
# no es estimable con estos datos". Ninguna lógica combina los dos
# semáforos en una recomendación: cada uno se lee por separado.
# Iconos neutros a propósito (sin verde/rojo, que se leen como compra/venta).
# ---------------------------------------------------------------
_cal = estado_calendario()
if not _cal["ok"]:
    st.warning(_cal["mensaje"], icon="📅")

# N días del semáforo de Ruido. Supuesto de diseño, no medido (no hay
# histórico de fechas de eventos): coincide con la revisión semanal.
TABLERO_N_DIAS_RUIDO = 7
_ICONO_NIVEL = {"Bajo": "○", "Normal": "◐", "Elevado": "●"}

st.markdown("### Tablero")
_col_r, _col_n = st.columns(2)
with _col_r:
    if _r6a["disponible"]:
        st.metric("Riesgo · volatilidad frente a 6 años",
                  f"{_ICONO_NIVEL.get(_r6a['etiqueta'], '')} {_r6a['etiqueta']}")
    else:
        st.metric("Riesgo · volatilidad frente a 6 años", "Sin datos")
    st.caption("Cuánto se agita el precio comparado con los últimos 6 años. "
               "No indica dirección.")
with _col_n:
    _ev_alta = [e for e in eventos_proximos(dias=TABLERO_N_DIAS_RUIDO, limite=10)
                if e["relevancia"] == "alta"]
    if _ev_alta and _ev_alta[0]["dias"] <= 2:
        _ruido = "● Evento inminente"
    elif _ev_alta:
        _ruido = "◐ Evento esta semana"
    else:
        _ruido = "○ Sin eventos"
    st.metric(f"Ruido · agenda próximos {TABLERO_N_DIAS_RUIDO} días", _ruido)
    st.caption("Dato de inflación de EEUU y reuniones de la Fed con proyecciones. "
               "Esos días suele haber más movimiento. No indica dirección.")

_sigma_mes = rg["vol"] * np.sqrt(30 / 365) * 100
st.markdown(
    f"**Movimiento reciente:** últimos 30 días {c['ret_30d']:+.1f}%. "
    f"Oscilación típica de un mes con la volatilidad actual: ±{_sigma_mes:.0f}%."
)
st.caption("Solo describe lo que ya pasó. Comparar el último mes con la "
           "oscilación típica no anticipa el mes siguiente.")

_ev = eventos_proximos(dias=45, limite=4)
if _ev:
    _lineas = []
    for _e in _ev:
        _cuando = ("hoy" if _e["dias"] == 0 else
                   "mañana" if _e["dias"] == 1 else f"en {_e['dias']} días")
        _marca = "**" if _e["relevancia"] == "alta" else ""
        _lineas.append(f"{_marca}{_e['nombre']}{_marca} · {_cuando} ({_e['fecha']:%d/%m})")
    st.caption("📅 Próximos eventos: " + "  ·  ".join(_lineas))
'''

app = reemplazar(app, VIEJO_CAL, NUEVO_CAL, "bloque calendario")

VIEJO_INVAL = '''    col1, col2 = st.columns(2)
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
'''

NUEVO_INVAL = '''    # Referencia de salida (diseño aprobado 2026-09-24, consulta externa 6/6):
    # media de 200 días del día de la decisión, CONGELADA al guardar. No
    # validada como salida. Si el precio ya está por debajo, no aplica.
    # El campo de precio va vacío por defecto (se elimina el antiguo ×0,75).
    _ref_salida = int(round(s["sma200"])) if s["precio"] > s["sma200"] else None

    col1, col2 = st.columns(2)
    with col1:
        inval_precio = st.number_input(
            "Por debajo de este precio ($)", min_value=0,
            value=None, step=500, placeholder="Vacío si no quieres fijarlo",
        )
        if _ref_salida:
            st.caption(
                f"Referencia **no validada**: media de 200 días hoy, "
                f"${_ref_salida:,.0f}. Valor congelado; la media real seguirá moviéndose."
            )
        else:
            st.caption("Referencia no aplica: el precio ya está por debajo "
                       "de la media de 200 días.")
    with col2:
        inval_cond = st.text_input(
            "O si ocurre esto",
            placeholder="ej. cierre diario por debajo de la media de 200 días",
        )

    if st.button("Guardar en el diario", type="primary"):
        # Se considera "usada" si el precio escrito coincide con la
        # referencia redondeada al paso del campo (500 $).
        _usada = (None if _ref_salida is None else
                  bool(inval_precio) and abs(inval_precio - _ref_salida) <= 250)
        st.session_state.diario = dj.anadir(d, {
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "tipo": tipo,
            "precio": s["precio"],
            "importe": importe if tipo != "No hacer nada" else 0,
            "hipotesis": hipotesis.strip() or None,
            "invalidacion_precio": inval_precio or None,
            "invalidacion_condicion": inval_cond.strip() or None,
            "estado_animo": estado,
            "confianza": confianza,
            "salida_referencia": _ref_salida,
            "salida_referencia_usada": _usada,
            **ctx,
        })
        st.success("Guardado. Descarga el CSV en la pestaña Historial para no perderlo.")
        st.rerun()
'''

app = reemplazar(app, VIEJO_INVAL, NUEVO_INVAL, "formulario invalidacion")

VIEJO_HIP = '''        "Por qué haces esto",
        placeholder="La razón concreta, hoy. Sin adornos — nadie más lo va a leer.",'''
NUEVO_HIP = '''        "Por qué haces esto (opcional)",
        placeholder="La razón concreta, hoy. Sin adornos — nadie más lo va a leer.",'''
app = reemplazar(app, VIEJO_HIP, NUEVO_HIP, "etiqueta hipotesis")

VIEJO_REV = '''with tab_revision:
    rev = dj.revisar(d, precio_actual=s["precio"])
'''
NUEVO_REV = '''with tab_revision:
    rev = dj.revisar(d, precio_actual=s["precio"])

    # La hipótesis es opcional desde 2026-09-24: se avisa aquí si falta.
    _sin_hip = int(d["hipotesis"].fillna("").astype(str).str.strip().eq("").sum()) if len(d) else 0
    if _sin_hip:
        st.warning(
            f"{_sin_hip} de {len(d)} registros sin el porqué. Sin él, la revisión "
            "no puede distinguir una buena decisión con mala suerte de una mala decisión.",
            icon="✍️",
        )
'''
app = reemplazar(app, VIEJO_REV, NUEVO_REV, "aviso revision")

with open("app.py", "w", encoding="utf-8") as fh:
    fh.write(app)

# ---------------------------------------------------------------- diario.py
with open("diario.py", encoding="utf-8") as fh:
    dia = fh.read()

VIEJO_COL = '''    "revisada", "resultado", "notas_revision",
]'''
NUEVO_COL = '''    "revisada", "resultado", "notas_revision",
    # 2026-09-24: referencia de salida mostrada (media de 200 días congelada)
    # y si el usuario la usó. Los diarios antiguos cargan igual: cargar()
    # rellena las columnas que falten.
    "salida_referencia", "salida_referencia_usada",
]'''
dia = reemplazar(dia, VIEJO_COL, NUEVO_COL, "COLUMNAS diario")

with open("diario.py", "w", encoding="utf-8") as fh:
    fh.write(dia)

print("OK")
for f in ESPERADO:
    print(f, sha(f))
