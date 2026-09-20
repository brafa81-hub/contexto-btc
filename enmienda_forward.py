#!/usr/bin/env python3
"""
enmienda_forward.py — script de un solo uso.

Anade a filtro.py la FASE 8 (confirmacion forward) con las 8 decisiones de
implementacion cerradas el 20-sep-2026, mas 3 decisiones de detalle
posteriores (M por variable aborta en vez de avisar; D8 tambien cubre el
precio; enmienda 42 no se aplica en esta fase, documentado en el informe).
NO toca v2.json ni registro.json: esto es codigo, no doctrina.
DOCTRINA_COMPATIBLE se mantiene en "2.16".

Verifica el SHA-256 del fichero de partida antes de tocar nada y el del
resultado despues. Si el de partida no coincide, aborta sin escribir.
"""
import hashlib, sys

SHA_ANTES = "54845d1d993c3a482f66b978c376de1f9800db96137233814c70bba069ad0ea9"
RUTA = sys.argv[1] if len(sys.argv) > 1 else "filtro.py"

BLOQUE = r'''# =====================================================================
# FASE 8 — CONFIRMACION FORWARD (confirmacion_forward de v2.json)
#
# Etapa posterior a la cadena de test. NO calcula p-valor, NO exige un
# minimo de episodios, NO admite descarte anticipado, NO pasa gates ni
# Benjamini-Yekutieli. Los 5 trimestres se completan siempre.
#
# Ocho decisiones de implementacion cerradas (20-sep-2026). La doctrina
# no las resuelve; se dejan anotadas aqui para que no se relean como
# criterio del motor inventado sobre la marcha:
#   D1 el forward empieza el dia siguiente a fecha_fin_ventana_test
#   D2 trimestre = bloque fijo de 91 dias; 5 bloques = 455 dias
#   D3 la exclusion de los ultimos N dias afecta a TODOS los dias del
#      borde, activos e inactivos, y se aplica ANTES de separar por
#      estado de la mascara (dias 1-61 elegibles, 62-91 excluidos)
#   D4 el signo de referencia es signo(theta_B2), nunca signo_esperado
#   D5 theta_B2 se lee anclado del registro; no se recalcula
#   D6 los tres estados de salida se validan contra estados.lista, sin
#      pasar por mapeo_salida_filtro_py, que no tiene filas para ellos
#   D7 un trimestre con theta exactamente 0 cuenta como "en contra"
#   D8 el snapshot extendido debe reproducir bit a bit el del test en el
#      tramo solapado, o el motor aborta
# =====================================================================

DIAS_BLOQUE_FORWARD = 91
N_BLOQUES_FORWARD = 5
SUELO_DEFINIDOS = 3

_ESTADOS_FORWARD = ("CONFIRMADA", "RECHAZADA_FORWARD", "PENDIENTE_REVISION")


# ---- consistencia_minima: copia literal de -----------------------------
# simulacion/calibracion-3de5/prueba_consistencia.py
# (sha256 e8a6c1f707c0eab2...). No se reimplementa ni se reescribe: la
# implementacion de referencia de la enmienda 43 y el motor deben ser el
# mismo codigo. Sus 15 casos viajan con ella y se ejecutan como prueba
# antes de emitir ningun veredicto.
def consistencia_minima(trimestres, signo_esperado):
    definidos = [t for t in trimestres if t is not None]
    n_def = len(definidos)
    n_indef = len(trimestres) - n_def
    a_favor = sum(1 for t in definidos if t == signo_esperado)

    if n_def < SUELO_DEFINIDOS:
        return "SIN_VEREDICTO", n_def, n_indef, a_favor
    if a_favor * 2 == n_def:                    # empate exacto
        return "SIN_VEREDICTO", n_def, n_indef, a_favor
    if a_favor * 2 > n_def:                     # mayoria estricta
        return "CUMPLE", n_def, n_indef, a_favor
    return "NO_CUMPLE", n_def, n_indef, a_favor


_CASOS_CONSISTENCIA = [
    ([+1, +1, +1, -1, -1], +1, "CUMPLE",        "5 definidos, 3-2 a favor"),
    ([+1, +1, -1, -1, -1], +1, "NO_CUMPLE",     "5 definidos, 2-3 en contra"),
    ([+1, +1, +1, +1, +1], +1, "CUMPLE",        "5 definidos, 5-0"),
    ([-1, -1, -1, -1, -1], +1, "NO_CUMPLE",     "5 definidos, 0-5"),
    ([+1, +1, +1, -1, None], +1, "CUMPLE",      "4 definidos, 3-1 a favor"),
    ([+1, +1, -1, -1, None], +1, "SIN_VEREDICTO", "4 definidos, empate 2-2"),
    ([+1, -1, -1, -1, None], +1, "NO_CUMPLE",   "4 definidos, 1-3 en contra"),
    ([+1, +1, -1, None, None], +1, "CUMPLE",    "3 definidos, 2-1 a favor"),
    ([+1, -1, -1, None, None], +1, "NO_CUMPLE", "3 definidos, 1-2 en contra"),
    ([+1, +1, +1, None, None], +1, "CUMPLE",    "3 definidos, 3-0"),
    ([+1, -1, None, None, None], +1, "SIN_VEREDICTO", "2 definidos (bajo el suelo)"),
    ([+1, None, None, None, None], +1, "SIN_VEREDICTO", "1 definido"),
    ([None] * 5, +1, "SIN_VEREDICTO",           "0 definidos"),
    ([-1, -1, -1, +1, +1], -1, "CUMPLE",        "signo esperado -1, 3-2 a favor"),
    ([-1, -1, +1, +1, None], -1, "SIN_VEREDICTO", "signo esperado -1, empate 2-2"),
]


def autoprueba_consistencia():
    """Los 15 casos de la enmienda 43. Si uno falla, el motor no emite."""
    fallos = []
    for tri, signo, esperado, etiqueta in _CASOS_CONSISTENCIA:
        res = consistencia_minima(tri, signo)[0]
        if res != esperado:
            fallos.append(f"{etiqueta}: esperado {esperado}, obtenido {res}")
    if fallos:
        abortar("la autoprueba de consistencia_minima falla: " + "; ".join(fallos))
    return len(_CASOS_CONSISTENCIA)


# ---- carga del snapshot extendido --------------------------------------

def cargar_metrica_extendida(path):
    """
    Igual que cargar_metrica pero SIN el corte en fecha_propuesta: aqui los
    datos posteriores son justamente el objeto de la etapa. La proteccion
    equivalente es la comprobacion bit a bit del tramo solapado (D8).
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    col_f = cols.get("fecha") or cols.get("date")
    col_v = [c for c in df.columns if c != col_f][0]
    df[col_f] = pd.to_datetime(df[col_f], utc=True).dt.tz_localize(None).dt.normalize()
    return df.set_index(col_f)[col_v].astype(float).sort_index()


def comprobar_solape_identico(serie_test, serie_ext, etiqueta):
    """
    D8: en el tramo comun, el snapshot extendido debe reproducir el del test
    valor a valor, sin tolerancia. Protege frente a revisiones retroactivas
    de la fuente (FRED revisa series hacia atras sin avisar).
    """
    comun = serie_test.index.intersection(serie_ext.index)
    faltan = serie_test.index.difference(serie_ext.index)
    if len(faltan):
        abortar(
            f"{etiqueta}: el snapshot extendido no contiene {len(faltan)} fecha(s) "
            f"que si estaban en el snapshot del test (primera {faltan.min().date()}). "
            f"No es una extension de la misma serie"
        )
    a = serie_test.loc[comun].to_numpy(dtype=float)
    b = serie_ext.loc[comun].to_numpy(dtype=float)
    if not np.array_equal(a, b, equal_nan=True):
        dif = int((~((a == b) | (np.isnan(a) & np.isnan(b)))).sum())
        i = int(np.argmax(~((a == b) | (np.isnan(a) & np.isnan(b)))))
        abortar(
            f"{etiqueta}: el snapshot extendido NO reproduce el del test en el "
            f"tramo solapado: {dif} de {len(comun)} valores difieren, el primero "
            f"el {comun[i].date()} ({a[i]} en el test, {b[i]} ahora). "
            f"Revision retroactiva de la fuente: la confirmacion forward no se "
            f"ejecuta sobre una serie que ya no es la que se testeo (D8)"
        )
    return {"dias_solapados": int(len(comun)), "identico_bit_a_bit": True}


# ---- ventana y bloques -------------------------------------------------

def bloques_forward(fecha_fin_test, N):
    """
    D1 + D2 + D3. Devuelve la lista de 5 bloques con su tramo elegible y la
    fecha de fin de la ventana completa.
    """
    inicio = pd.Timestamp(fecha_fin_test) + pd.Timedelta(days=1)
    dias_elegibles = DIAS_BLOQUE_FORWARD - N        # 91 - 30 = 61
    if dias_elegibles <= 0:
        abortar(
            f"con N={N} dias y bloques de {DIAS_BLOQUE_FORWARD} dias no queda "
            f"ningun dia elegible tras la exclusion de bordes (enmienda 4)"
        )
    bloques = []
    for k in range(N_BLOQUES_FORWARD):
        ini = inicio + pd.Timedelta(days=k * DIAS_BLOQUE_FORWARD)
        fin = ini + pd.Timedelta(days=DIAS_BLOQUE_FORWARD - 1)
        fin_eleg = ini + pd.Timedelta(days=dias_elegibles - 1)
        bloques.append({"trimestre": k + 1, "desde": ini, "hasta": fin,
                        "elegible_hasta": fin_eleg})
    fin_ventana = bloques[-1]["hasta"]
    meta = {
        "inicio_forward": str(inicio.date()),
        "fin_forward": str(fin_ventana.date()),
        "dias_por_bloque": DIAS_BLOQUE_FORWARD,
        "bloques": N_BLOQUES_FORWARD,
        "dias_totales": DIAS_BLOQUE_FORWARD * N_BLOQUES_FORWARD,
        "dias_elegibles_por_bloque": dias_elegibles,
        "dias_excluidos_por_bloque": N,
        "regla_exclusion": (
            f"dias 1-{dias_elegibles} elegibles, {dias_elegibles + 1}-"
            f"{DIAS_BLOQUE_FORWARD} excluidos. La exclusion se aplica a todos "
            f"los dias del borde, activos e inactivos, antes de separar por "
            f"estado de la mascara (enmienda 4, decision 3)"
        ),
    }
    return bloques, fin_ventana, meta


# ---- estimacion --------------------------------------------------------

def _theta(z):
    """
    Formula inmutable de definicion_de_efecto: mediana(activos) -
    mediana(inactivos). None si el tramo no tiene activos o no tiene
    inactivos (trimestre indefinido segun la enmienda 43).
    """
    a = z[z["m"]]["retorno_N"]
    b = z[~z["m"]]["retorno_N"]
    if len(a) == 0 or len(b) == 0:
        return None
    return float(a.median() - b.median())


def _signo_de_trimestre(theta, signo_b2):
    """
    D7: theta exactamente 0 cuenta como EN CONTRA, no como indefinido. La
    doctrina define indefinido de forma cerrada (sin activos o sin
    inactivos), y 0 no entra ahi.
    """
    if theta is None:
        return None
    if theta == 0.0:
        return -signo_b2
    return 1 if theta > 0 else -1


def confirmacion_forward(metrica_ext, precio_ext, ficha, theta_B2, M, doc,
                         metrica_test=None, precio_test=None):
    """
    Devuelve (veredicto, detalle). Veredicto en _ESTADOS_FORWARD.
    Sin p-valor, sin minimo de episodios, sin descarte anticipado.
    """
    n_casos = autoprueba_consistencia()
    N = ruta(doc, "definicion_de_efecto.horizonte_N.valor")

    # D5: theta_B2 anclado, no recalculado.
    if theta_B2 is None:
        abortar("theta_B2 no esta anclado en la entrada EN_CONFIRMACION del "
                "registro. La confirmacion forward no lo recalcula (decision 5)")
    theta_B2 = float(theta_B2)
    if theta_B2 == 0.0:
        abortar("theta_B2 anclado es exactamente 0: signo(theta_B2) no esta "
                "definido y los criterios 1 y 3 no son evaluables")
    # D4: el signo de referencia sale de theta_B2, NO de ficha.signo_esperado,
    # que puede valer "bilateral" y no admite comparacion de signo.
    signo_b2 = 1 if theta_B2 > 0 else -1

    fecha_fin_test = pd.Timestamp(ficha["fecha_fin_ventana_test"])
    bloques, fin_ventana, meta_ventana = bloques_forward(fecha_fin_test, N)
    ultimo_elegible = bloques[-1]["elegible_hasta"]

    # D8: el tramo solapado debe ser identico al del test.
    solape = {}
    if metrica_test is not None:
        solape["metrica"] = comprobar_solape_identico(
            metrica_test, metrica_ext, "serie de la metrica")
    if precio_test is not None:
        solape["precio"] = comprobar_solape_identico(
            precio_test, precio_ext, "serie de precio")

    # Cobertura: los 5 trimestres se completan siempre, asi que faltar datos
    # es un aborto, nunca un veredicto anticipado sobre lo que haya.
    if metrica_ext.index.max() < ultimo_elegible:
        abortar(
            f"la serie de la metrica llega a {metrica_ext.index.max().date()} y "
            f"el ultimo dia elegible del forward es {ultimo_elegible.date()}. "
            f"La ventana es fija y no se acorta (ventana.extension_permitida=false)")
    if precio_ext.index.max() < fin_ventana:
        abortar(
            f"la serie de precio llega a {precio_ext.index.max().date()} y el "
            f"retorno a {N} dias del ultimo dia elegible necesita precio hasta "
            f"{fin_ventana.date()}")

    # Mascara con la regla congelada sobre la serie COMPLETA: el percentil
    # movil necesita el pasado. Despues se recorta al forward.
    mask_total, meta_mask = construir_mascara(metrica_ext, ficha)
    ret = retorno_N(precio_ext, N)

    z = pd.DataFrame({"m": mask_total,
                      "retorno_N": ret.reindex(mask_total.index)}).dropna()
    z["m"] = z["m"].astype(bool)
    en_ventana = z[(z.index >= pd.Timestamp(meta_ventana["inicio_forward"])) &
                   (z.index <= fin_ventana)]

    # D3: el filtro temporal va ANTES de separar por estado de la mascara.
    trozos, trimestres = [], []
    for b in bloques:
        crudo = en_ventana[(en_ventana.index >= b["desde"]) &
                           (en_ventana.index <= b["hasta"])]
        elegible = crudo[crudo.index <= b["elegible_hasta"]]
        th = _theta(elegible)
        sg = _signo_de_trimestre(th, signo_b2)
        trimestres.append(sg)
        trozos.append(elegible)
        b.update({
            "dias_en_bloque": int(len(crudo)),
            "dias_retenidos": int(len(elegible)),
            "dias_excluidos_borde": int(len(crudo) - len(elegible)),
            "activos_retenidos": int(elegible["m"].sum()),
            "inactivos_retenidos": int((~elegible["m"]).sum()),
            "theta_trimestre": th,
            "signo": sg,
            "indefinido": sg is None,
            "motivo_indefinido": (
                None if sg is not None else
                ("sin dias activos" if elegible["m"].sum() == 0
                 else "sin dias inactivos")),
        })

    retenidos = pd.concat(trozos) if trozos else en_ventana.iloc[0:0]
    theta_F = _theta(retenidos)

    # Criterio 3 primero: manda sobre los otros dos. Si no hay veredicto, la
    # variable va a PENDIENTE_REVISION aunque theta_F no exista.
    res_cons, n_def, n_indef, a_favor = consistencia_minima(trimestres, signo_b2)

    c3 = {"id": "consistencia_minima", "resultado": res_cons,
          "trimestres_definidos": n_def, "trimestres_indefinidos": n_indef,
          "cuales_indefinidos": [b["trimestre"] for b in bloques if b["indefinido"]],
          "a_favor": a_favor, "en_contra": n_def - a_favor,
          "signos_por_trimestre": trimestres,
          "suelo_definidos": SUELO_DEFINIDOS,
          "autoprueba_casos": n_casos}

    detalle = {
        "ventana": meta_ventana,
        "verificacion_solape": solape or None,
        "mascara": meta_mask,
        "theta_B2_anclado": theta_B2,
        "signo_de_referencia": signo_b2,
        "origen_del_signo": "signo(theta_B2), no ficha.signo_esperado (decision 4)",
        "signo_esperado_de_la_ficha": ficha.get("signo_esperado"),
        "M_aplicado": M,
        "dias_retenidos_total": int(len(retenidos)),
        "activos_retenidos_total": int(retenidos["m"].sum()) if len(retenidos) else 0,
        "inactivos_retenidos_total": int((~retenidos["m"]).sum()) if len(retenidos) else 0,
        "theta_F": theta_F,
        "trimestres": [
            {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v)
             for k, v in b.items()} for b in bloques],
        "criterios": {},
        "sin_p_valor": "la confirmacion forward no calcula p-valor ni aplica "
                       "Benjamini-Yekutieli (confirmacion_forward.naturaleza_del_test)",
        "enmienda_42_no_aplica": "La enmienda 42 (huecos en series) es un filtro "
                                 "de ADMISION a EN_TEST. La confirmacion forward "
                                 "no tiene filtros de admision: sin gates y sin "
                                 "descarte anticipado, los 5 trimestres se "
                                 "completan siempre. Un hueco de datos se hace "
                                 "visible aqui por los dias retenidos de cada "
                                 "trimestre y por los trimestres indefinidos, "
                                 "que se registran siempre.",
    }

    if res_cons == "SIN_VEREDICTO":
        # Sin veredicto no es ni pasa ni falla: los criterios 1 y 2 no llegan a
        # evaluarse (el empate y el suelo mandan sobre los otros dos).
        c3["pasa"] = None
        detalle["criterios"]["3_consistencia_minima"] = c3
        detalle["motivo"] = (
            f"consistencia_minima sin veredicto: {n_def} trimestre(s) definido(s), "
            f"{a_favor} a favor y {n_def - a_favor} en contra"
            + (" (empate)" if n_def >= SUELO_DEFINIDOS else
               f" (bajo el suelo de {SUELO_DEFINIDOS})")
            + ". El presupuesto ya consumido no se devuelve")
        return "PENDIENTE_REVISION", detalle

    if theta_F is None:
        # Inalcanzable por construccion: >=3 trimestres definidos implica que
        # el agregado tiene activos e inactivos. Se aborta en vez de decidirlo.
        abortar("theta_F indefinido con consistencia_minima con veredicto: "
                "estado imposible, el motor no lo resuelve por su cuenta")

    signo_F = 1 if theta_F > 0 else (-1 if theta_F < 0 else 0)
    umbral = max(0.5 * abs(theta_B2), float(M))

    c1 = {"id": "signo_agregado", "regla": "signo(theta_F) == signo(theta_B2)",
          "signo_theta_F": signo_F, "signo_theta_B2": signo_b2,
          "pasa": bool(signo_F == signo_b2)}
    c2 = {"id": "magnitud",
          "regla": "abs(theta_F) >= max(0.5 * abs(theta_B2), M)",
          "abs_theta_F": abs(theta_F), "umbral_aplicado": umbral,
          "componente_relativa": 0.5 * abs(theta_B2), "componente_M": float(M),
          "linea_base": "theta_B2 (bloque 2), unica porcion no contaminada",
          "pasa": bool(abs(theta_F) >= umbral)}
    c3["pasa"] = res_cons == "CUMPLE"

    detalle["criterios"] = {"1_signo_agregado": c1, "2_magnitud": c2,
                            "3_consistencia_minima": c3}

    fallidos = [c["id"] for c in (c1, c2, c3) if not c["pasa"]]
    if fallidos:
        detalle["motivo"] = "criterio(s) no superado(s): " + ", ".join(fallidos)
        return "RECHAZADA_FORWARD", detalle
    return "CONFIRMADA", detalle


def traducir_forward(veredicto, doc):
    """
    D6: los tres estados de salida se validan contra estados.lista y NO pasan
    por estados.mapeo_salida_filtro_py.tabla, que no tiene filas para ellos.
    Asi no hace falta tocar doctrina para implementar codigo.
    """
    if veredicto not in _ESTADOS_FORWARD:
        abortar(f"veredicto forward '{veredicto}' fuera de los tres posibles")
    validos = {e["id"]: e for e in ruta(doc, "estados.lista")}
    if veredicto not in validos:
        abortar(f"filtro.py iba a emitir '{veredicto}', fuera de la lista cerrada")
    if validos[veredicto].get("emision_permitida") is False:
        abortar(f"filtro.py iba a emitir '{veredicto}', cuya emision esta prohibida")
    return veredicto


# =====================================================================
# ORQUESTACION DE LA FASE 8
# =====================================================================

def _sha_serie_metrica_anclado(v):
    """El ancla del CSV de la metrica se escribio en la transicion a EN_TEST
    (enmienda 35). Se busca hacia atras en el historial."""
    for _, e in reversed(v["historial"]):
        if e.get("sha256_serie_metrica"):
            return e["sha256_serie_metrica"]
    return None


def ejecutar_forward(args):
    doc, reg, msg_cadena = fase0_arranque(args.doctrina, args.registro)
    print(cabecera(doc))
    print(f"\n[FASE 0] {msg_cadena}")

    variables, consumo, incidencias, _ = fase1_resolver(doc, reg)
    for i in incidencias:
        print(f"[FASE 1] incidencia: {i}")

    rutas_ext = dict(x.split("=", 1) for x in (args.metrica_forward or []))
    rutas_test = dict(x.split("=", 1) for x in (args.metrica or []))

    en_conf = {vid: v for vid, v in variables.items()
               if v["estado"] == "EN_CONFIRMACION"}
    if not en_conf:
        abortar("no hay ninguna variable en EN_CONFIRMACION en el registro. "
                "La fase 8 no se ejecuta sobre estados distintos")
    sobran = sorted(set(rutas_ext) - set(en_conf))
    if sobran:
        abortar(f"--metrica-forward aporta serie para {sobran}, que no esta(n) "
                f"en EN_CONFIRMACION")

    if not args.precio:
        abortar("falta --precio: el snapshot congelado del test, necesario para "
                "comprobar el solape bit a bit (decision 8)")
    if not args.precio_forward:
        abortar("falta --precio-forward: el snapshot de precio extendido")

    precio_test, meta_precio_test = cargar_precio(args.precio, doc)
    precio_ext, meta_precio_ext = cargar_precio(args.precio_forward, doc,
                                                verificar_sha=False)
    print(f"\n[FASE 8] precio del test: {meta_precio_test['desde']} a "
          f"{meta_precio_test['hasta']} | extendido: "
          f"{meta_precio_ext['desde']} a {meta_precio_ext['hasta']}")

    M_doc = float(ruta(doc, "confirmacion_forward.umbral_absoluto_M.valor"))
    resultados = {}

    for vid, v in sorted(en_conf.items()):
        if vid not in rutas_ext:
            abortar(f"falta --metrica-forward {vid}=<csv> para la variable en "
                    f"EN_CONFIRMACION '{vid}'")
        if vid not in rutas_test:
            abortar(f"falta --metrica {vid}=<csv> (snapshot del test) para "
                    f"comprobar el solape bit a bit de '{vid}' (decision 8)")

        ficha = v["ficha_operativa"]
        ent = v["entrada_operativa"]

        fecha_fin = pd.Timestamp(ficha["fecha_fin_ventana_test"])
        metrica_test = cargar_metrica(rutas_test[vid], fecha_fin,
                                      _sha_serie_metrica_anclado(v))
        metrica_ext = cargar_metrica_extendida(rutas_ext[vid])

        M_ficha = ficha.get("M")
        if M_ficha is None:
            abortar(f"[{vid}] la ficha no declara M, campo obligatorio de "
                    f"ficha_congelada.campos_obligatorios")
        M = float(M_ficha)
        if M != M_doc:
            # umbral_absoluto_M.alcance permite un M por variable, pero solo si
            # la ficha documenta la casilla y la derivacion concretas, y la
            # doctrina no nombra el campo donde se documenta. El motor no puede
            # verificarlo, asi que no lo da por bueno ni lo deja a revision
            # manual: se para.
            abortar(
                f"[{vid}] la ficha declara M={M} y el valor por defecto del "
                f"regimen es {M_doc}. umbral_absoluto_M.alcance admite el "
                f"override solo si la ficha documenta casilla y derivacion, "
                f"pero la doctrina no nombra el campo que lo documenta y el "
                f"motor no puede comprobarlo. Se detiene en vez de decidirlo")

        veredicto, detalle = confirmacion_forward(
            metrica_ext, precio_ext, ficha,
            theta_B2=ent.get("theta_B2"), M=M, doc=doc,
            metrica_test=metrica_test, precio_test=precio_test)

        estado = traducir_forward(veredicto, doc)
        detalle["M_por_defecto_del_regimen"] = M_doc
        detalle["n_entrada_de_la_que_se_lee_theta_B2"] = v["n_entrada_operativa"]
        resultados[vid] = {"id": vid, "estado": estado, "confirmacion_forward": detalle}
        if detalle.get("motivo"):
            resultados[vid]["motivo"] = detalle["motivo"]

        w = detalle["ventana"]
        print(f"\n[FASE 8] [{vid}] ventana {w['inicio_forward']} a "
              f"{w['fin_forward']} ({w['dias_totales']} dias, "
              f"{w['dias_elegibles_por_bloque']} elegibles de "
              f"{w['dias_por_bloque']} por bloque)")
        print(f"         theta_B2 anclado {detalle['theta_B2_anclado']:+.6f} "
              f"(signo de referencia {detalle['signo_de_referencia']:+d}) | "
              f"M aplicado {detalle['M_aplicado']}")
        for t in detalle["trimestres"]:
            th = "indefinido" if t["theta_trimestre"] is None else f"{t['theta_trimestre']:+.6f}"
            print(f"         T{t['trimestre']} {t['desde']}..{t['elegible_hasta']}: "
                  f"{t['dias_retenidos']} dias retenidos "
                  f"({t['activos_retenidos']} act / {t['inactivos_retenidos']} inact), "
                  f"theta {th}"
                  + (f"  [{t['motivo_indefinido']}]" if t["indefinido"] else ""))
        tf = detalle["theta_F"]
        print(f"         theta_F {'indefinido' if tf is None else f'{tf:+.6f}'} "
              f"sobre {detalle['dias_retenidos_total']} dias retenidos")
        c = detalle["criterios"]
        for k in ("1_signo_agregado", "2_magnitud", "3_consistencia_minima"):
            if k in c:
                print(f"         criterio {k}: "
                      f"{'PASA' if c[k].get('pasa') else 'NO PASA'}")
        c3 = c["3_consistencia_minima"]
        print(f"         trimestres definidos {c3['trimestres_definidos']} "
              f"({c3['a_favor']} a favor / {c3['en_contra']} en contra), "
              f"indefinidos {c3['trimestres_indefinidos']} "
              f"{c3['cuales_indefinidos'] or ''}")
        print(f"         VEREDICTO: {estado}")

    informe = {
        "sha256_v2_json": _SHA_DOCTRINA,
        "doctrina": ruta(doc, "meta.version_esquema"),
        "fase": "8 - confirmacion forward",
        "declaracion_obligatoria": ruta(doc, "meta.declaracion_obligatoria"),
        "naturaleza_del_test": ruta(doc, "confirmacion_forward.naturaleza_del_test"),
        "incidencias_registro": incidencias,
        "precio_test": meta_precio_test,
        "precio_forward": meta_precio_ext,
        "resultados": resultados,
        "no_escribe_registro": "filtro.py no modifica registro.json. La entrada de "
                               "transicion se escribe aparte con cadena.anadir.",
    }

    print("\n" + "=" * 72)
    for vid, r in resultados.items():
        print(f"{vid}: {r['estado']}" + (f"  ({r.get('motivo')})" if r.get("motivo") else ""))
    print("=" * 72)

    if args.informe:
        with open(args.informe, "w", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=1, default=str)
        print(f"informe escrito en {args.informe}")
        print(f"\nhashes para la entrada de transicion de resultado:")
        print(f"  sha256_informe: {sha256_fichero(args.informe)}")
    print(f"  sha256_motor:   {_sha_motor()}")
    return 0


'''

EDICIONES = [
    # (viejo, nuevo, descripcion)
    (
        'def cargar_precio(path, doc):\n    fp = ruta(doc, "fuente_de_precio")\n\n    sha_declarado = fp["snapshot"].get("sha256")\n    sha_real = sha256_fichero(path)\n    if sha_declarado and sha_real != sha_declarado:',
        'def cargar_precio(path, doc, verificar_sha=True):\n    fp = ruta(doc, "fuente_de_precio")\n\n    sha_declarado = fp["snapshot"].get("sha256")\n    sha_real = sha256_fichero(path)\n    # verificar_sha=False solo lo usa la fase 8 con el snapshot de precio\n    # EXTENDIDO, que por definicion no puede coincidir con el congelado en\n    # doctrina. Su proteccion equivalente es el solape bit a bit (decision 8).\n    if verificar_sha and sha_declarado and sha_real != sha_declarado:',
        "cargar_precio acepta verificar_sha (por defecto True: sin cambio)",
    ),
]

def main():
    bruto = open(RUTA, "rb").read()
    sha = hashlib.sha256(bruto).hexdigest()
    print(f"fichero de partida: {RUTA}  {len(bruto)} bytes  sha256 {sha}")
    if sha != SHA_ANTES:
        print(f"ABORTA: se esperaba {SHA_ANTES}")
        return 2
    s = bruto.decode("utf-8")

    for viejo, nuevo, desc in EDICIONES:
        if s.count(viejo) != 1:
            print(f"ABORTA: la edicion '{desc}' no encaja exactamente una vez")
            return 2
        s = s.replace(viejo, nuevo)
        print(f"  ok  {desc}")

    ancla = "def main(argv=None):"
    if s.count(ancla) != 1:
        print("ABORTA: no hay un unico 'def main(argv=None):'")
        return 2
    s = s.replace(ancla, BLOQUE + ancla)
    print("  ok  FASE 8 insertada antes de main()")

    viejo_cli = '    ap.add_argument("--informe")\n    ap.add_argument("--solo-comprobar", action="store_true")'
    nuevo_cli = viejo_cli + '''
    ap.add_argument("--confirmacion-forward", action="store_true",
                    help="Fase 8: ejecuta la confirmacion forward sobre las "
                         "variables en EN_CONFIRMACION. No pasa gates, no "
                         "calcula p-valor y no aplica Benjamini-Yekutieli.")
    ap.add_argument("--metrica-forward", action="append",
                    help="id=ruta.csv (repetible). Serie de la metrica "
                         "EXTENDIDA hasta cubrir la ventana forward.")
    ap.add_argument("--precio-forward",
                    help="Snapshot de precio extendido hasta el fin de la "
                         "ventana forward.")'''
    if s.count(viejo_cli) != 1:
        print("ABORTA: el bloque de argumentos no encaja")
        return 2
    s = s.replace(viejo_cli, nuevo_cli)
    print("  ok  tres argumentos nuevos en main()")

    viejo_rt = '    if not args.lote:\n        ap.error("--lote es obligatorio salvo con --validar-entrada")\n\n    try:\n        return ejecutar(args)'
    nuevo_rt = '''    if args.confirmacion_forward:
        try:
            return ejecutar_forward(args)
        except Aborto as e:
            print("\\n" + "!" * 72)
            print("ABORTA filtro.py (fase 8)")
            print(f"motivo: {e}")
            print(f"SHA-256 v2.json: {_SHA_DOCTRINA}")
            print("!" * 72)
            return 2

''' + viejo_rt
    if s.count(viejo_rt) != 1:
        print("ABORTA: el enrutado de main() no encaja")
        return 2
    s = s.replace(viejo_rt, nuevo_rt)
    print("  ok  enrutado de --confirmacion-forward")

    salida = s.encode("utf-8")
    compile(s, RUTA, "exec")
    open(RUTA, "wb").write(salida)
    print(f"\nfichero resultante: {len(salida)} bytes  "
          f"sha256 {hashlib.sha256(salida).hexdigest()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
