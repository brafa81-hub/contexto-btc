#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aplicar_enmienda_42.py — script de UN SOLO USO.

ENMIENDA 42: huecos en las series de las variables candidatas.

Modifica v2.json (2.13.0 -> 2.14.0) y filtro.py (DOCTRINA_COMPATIBLE
"2.13" -> "2.14"). Verifica el SHA-256 de AMBOS ficheros antes de tocar nada.
Si alguno no coincide, o si algun reemplazo de codigo no encuentra su ancla
exactamente una vez, aborta sin escribir ninguno de los dos.

Se commitea al repositorio como registro auditable de la modificacion.
"""

import hashlib
import json
import sys

RUTA_DOC = "v2.json"
RUTA_MOTOR = "filtro.py"

SHA_DOC_ESPERADO = "e89daead1165e0751ef51d728e95e4b3cae6ef9f4f4d4f2bd9f2ace5b1ed6346"
SHA_MOTOR_ESPERADO = "f6458fcb744f6d179515de1c8606c23602ff3e519fe2064aec2652022004b59b"
VERSION_ESPERADA = "2.13.0"
VERSION_NUEVA = "2.14.0"
FECHA = "2026-09-15"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def abortar(motivo):
    print("!" * 72)
    print("ABORTA aplicar_enmienda_42.py — no se ha escrito nada")
    print(f"motivo: {motivo}")
    print("!" * 72)
    sys.exit(2)


# =====================================================================
# DOCTRINA
# =====================================================================

SECCION = {
    "enmienda": 42,
    "objeto": (
        "Tratamiento de los dias sin dato en la serie de la metrica continua de "
        "una variable candidata. Hasta esta enmienda la regla de huecos solo "
        "existia para el precio (fuente_de_precio.dias_faltantes); en las series "
        "de candidatas un dia vacio se leia como mascara no activada, lo que "
        "convierte la ausencia de dato en una observacion falsa."
    ),
    "aplicacion": {
        "desde_entrada": 44,
        "regla": (
            "Se aplica a las variables cuya PRIMERA entrada en registro.json "
            "tenga indice mayor o igual que desde_entrada. Las variables con "
            "primera entrada 1 a 43 conservan exactamente el comportamiento "
            "anterior del motor, sin reevaluacion."
        ),
        "motivo_prospectivo": "Mismo criterio que las enmiendas 33, 34, 35 y 38.",
    },
    "declaracion_en_ficha": {
        "ruta_en_la_ficha": "metrica_continua.huecos",
        "campos_obligatorios": ["calendario", "ventana_dependencia_dias", "huecos_brutos"],
        "calendario": (
            "Calendario nativo de la serie. 'natural': todos los dias. "
            "'laborable_lunes_viernes': de lunes a viernes; un festivo entre "
            "semana es un dia laborable sin dato."
        ),
        "ventana_dependencia_dias": (
            "Entero >= 0, en dias del calendario declarado. El valor del dia t "
            "depende de los dias t-ventana a t. Ejemplo: media movil de 7 dias "
            "mas variacion a 20 dias sobre ella = 26."
        ),
        "huecos_brutos": (
            "Lista, posiblemente vacia, de TODOS los tramos consecutivos sin dato "
            "de la fuente bruta dentro del snapshot, cada uno con 'desde' y "
            "'hasta' (inclusive, AAAA-MM-DD, dias del calendario declarado). "
            "Ordenados y sin solaparse."
        ),
        "causa": (
            "Clave opcional 'causa' en cada hueco. Solo descriptiva: el motor no "
            "la lee y no condiciona nada."
        ),
    },
    "calendarios_permitidos": ["natural", "laborable_lunes_viernes"],
    "arrastre_maximo_dias": 2,
    "hueco_largo": "hueco de arrastre_maximo_dias + 1 dias del calendario declarado o mas",
    "regla_de_anulacion": (
        "El dia t queda anulado si algun dia entre t - ventana_dependencia_dias "
        "y t (ambos inclusive, en dias del calendario declarado) pertenece a un "
        "hueco largo. Es deliberadamente conservadora: anula tambien dias "
        "intermedios de la ventana que la transformacion concreta no usa."
    ),
    "serie_transformada": (
        "El CSV que consume el motor lista todos los dias del calendario "
        "declarado entre su primera y su ultima fecha. Los dias anulados van con "
        "valor vacio. Los huecos cortos se rellenan arrastrando el ultimo dato "
        "bruto antes de calcular la transformacion, igual que el precio."
    ),
    "verificaciones_de_filtro_py": [
        "declaracion: metrica_continua.huecos existe y tiene forma valida",
        "continuidad: el CSV no tiene fechas duplicadas, ni fechas fuera del calendario declarado, ni fechas del calendario que falten",
        "propagacion: el conjunto de dias vacios del CSV es EXACTAMENTE el conjunto de dias anulados derivado de huecos_brutos y ventana_dependencia_dias",
    ],
    "tratamiento_de_los_dias_anulados": {
        "percentil": "Un dia anulado no entra en la ventana movil del percentil.",
        "particion": (
            "La fecha de corte de bloques se deriva sobre el calendario completo, "
            "con los dias anulados incluidos, para que un hueco no desplace el corte."
        ),
        "mascara": (
            "Tras particionar, los dias anulados se excluyen de la mascara. No "
            "cuentan como activados ni como no activados."
        ),
    },
    "criterios_de_admisibilidad_adicionales": [
        {
            "id": "cobertura_por_bloque",
            "regla": "dias con valor / dias del calendario del bloque >= cobertura_minima_por_bloque, en bloque_1 y en bloque_2 por separado",
            "dias_del_calendario_del_bloque": "tras warm-up e interseccion con el precio (enmienda 39), anulados incluidos",
        },
        {
            "id": "episodios_limpios_bloque_2",
            "regla": "numero de episodios independientes del bloque_2 sin ningun dia anulado entre su primer y su ultimo dia >= protocolo.test_de_permutacion.episodios_independientes_minimos",
            "donde_se_aplica": "Solo en admisibilidad (enmienda 38). El test de permutacion y la capa de gates no cambian.",
        },
    ],
    "cobertura_minima_por_bloque": 0.90,
    "al_fallar": {
        "estado_asignado": "PENDIENTE_REVISION",
        "consume_presupuesto": False,
        "entra_en_correccion_BY": False,
        "alcance": "Cualquier verificacion o criterio de esta seccion. Mismo destino y mismo aislamiento del lote que la enmienda 38.",
        "sin_grandfathering": "Toda variable sujeta a esta seccion es posterior a ella, por lo que sus criterios bloquean siempre, tambien si la variable ya esta en EN_TEST pendiente.",
    },
    "no_modifica": "Ningun gate, umbral, estadistico, particion de variables anteriores, ni la regla de precio. El motor de gates y el test de permutacion quedan congelados.",
}

ACLARACION_ALCANCE = {
    "enmienda": 42,
    "regla": (
        "Declarar en metrica_continua.huecos los huecos brutos, el calendario y "
        "la ventana de dependencia NO es un estado de disponibilidad de datos. "
        "Describe la serie medida tal como queda congelada, con fecha y hash, y "
        "por tanto no caduca. Queda permitido y, para las variables sujetas a "
        "protocolo.huecos_en_series, es obligatorio."
    ),
}

AMPLIACION_38 = {
    "enmienda": 42,
    "criterios_anadidos": ["cobertura_por_bloque", "episodios_limpios_bloque_2"],
    "definicion": "protocolo.huecos_en_series.criterios_de_admisibilidad_adicionales",
    "aplicacion": "Solo variables sujetas a protocolo.huecos_en_series.aplicacion.",
}

META_ENMIENDA = {
    "n": 42,
    "titulo": "huecos en las series de las variables candidatas",
    "fecha": FECHA,
    "motivo": (
        "La serie de active_addresses_delta20_ma7 (entrada 43) mostro un hueco "
        "de 9 dias. El motor leia los dias vacios de una metrica como mascara no "
        "activada y no existia regla de huecos fuera del precio. Parametros "
        "aprobados por Rafa tras consulta a 5 IAs externas."
    ),
    "partes": [
        "1. Seccion protocolo.huecos_en_series: declaracion en ficha, calendario, arrastre maximo de 2 dias, regla de anulacion, cobertura minima del 90% por bloque y episodios limpios.",
        "2. Aclaracion en ficha_congelada.alcance: la declaracion de huecos no es estado de disponibilidad (enmienda 29).",
        "3. Ampliacion de protocolo.admisibilidad_estructural con dos criterios.",
        "4. Implementacion en filtro.py: verificacion de continuidad y propagacion, exclusion de dias anulados de la mascara y criterios de admisibilidad; aviso en --validar-entrada.",
    ],
    "naturaleza": "Anade verificaciones y criterios de admisibilidad. No altera ningun gate, umbral, estadistico ni el test de permutacion.",
    "momento": "Lote 2026-Q3 sin test pendiente ni resultado contaminable. Aplicacion prospectiva desde la entrada 44.",
}

# =====================================================================
# MOTOR — reemplazos exactos (cada ancla debe aparecer una sola vez)
# =====================================================================

FUNCIONES_42 = r'''

# =====================================================================
# ENMIENDA 42 — HUECOS EN SERIES DE CANDIDATAS (protocolo.huecos_en_series)
# =====================================================================

_FREQ_CALENDARIO = {"natural": "D", "laborable_lunes_viernes": "B"}


def _regimen_huecos(v, doc):
    """True si la variable esta sujeta a la enmienda 42 (primera entrada)."""
    corte = int(ruta(doc, "protocolo.huecos_en_series.aplicacion.desde_entrada"))
    return int(v["historial"][0][0]) >= corte


def _validar_declaracion_huecos(ficha, doc):
    """Devuelve (declaracion_normalizada, problemas)."""
    sec = ruta(doc, "protocolo.huecos_en_series")
    mc = ficha.get("metrica_continua")
    h = mc.get("huecos") if isinstance(mc, dict) else None
    if not isinstance(h, dict):
        return None, ["falta metrica_continua.huecos (enmienda 42)"]
    faltan = [c for c in sec["declaracion_en_ficha"]["campos_obligatorios"] if c not in h]
    if faltan:
        return None, [f"metrica_continua.huecos sin campo(s) {faltan} (enmienda 42)"]
    p = []
    cal = h["calendario"]
    if cal not in sec["calendarios_permitidos"] or cal not in _FREQ_CALENDARIO:
        p.append(f"calendario '{cal}' fuera de {sec['calendarios_permitidos']}")
        return None, p
    freq = _FREQ_CALENDARIO[cal]
    V = h["ventana_dependencia_dias"]
    if not isinstance(V, int) or isinstance(V, bool) or V < 0:
        p.append(f"ventana_dependencia_dias '{V}' no es un entero >= 0")
    brutos = h["huecos_brutos"]
    if not isinstance(brutos, list):
        return None, p + ["huecos_brutos no es una lista"]
    tramos, previo = [], None
    for k, x in enumerate(brutos, start=1):
        try:
            a = pd.Timestamp(x["desde"]).normalize()
            b = pd.Timestamp(x["hasta"]).normalize()
        except Exception:
            p.append(f"hueco {k}: 'desde'/'hasta' ausentes o no son fechas")
            continue
        if b < a:
            p.append(f"hueco {k}: hasta < desde")
            continue
        if freq == "B" and (a.weekday() > 4 or b.weekday() > 4):
            p.append(f"hueco {k}: limite en fin de semana con calendario laborable")
            continue
        if previo is not None and a <= previo:
            p.append(f"hueco {k}: desordenado o solapado con el anterior")
            continue
        previo = b
        tramos.append((a, b))
    if p:
        return None, p
    return {"calendario": cal, "freq": freq, "V": V, "tramos": tramos}, []


def verificar_huecos(metrica, ficha, doc):
    """
    Verificaciones de continuidad y propagacion. Devuelve
    (problemas, dias_anulados, meta). No mira ningun retorno ni efecto.
    """
    sec = ruta(doc, "protocolo.huecos_en_series")
    decl, p = _validar_declaracion_huecos(ficha, doc)
    if p:
        return p, pd.DatetimeIndex([]), {}
    freq, V = decl["freq"], decl["V"]
    idx = metrica.index

    if idx.has_duplicates:
        p.append(f"continuidad: {int(idx.duplicated().sum())} fecha(s) duplicada(s) en el CSV")
    esperado = pd.date_range(idx.min(), idx.max(), freq=freq)
    faltan = esperado.difference(idx)
    sobran = idx.unique().difference(esperado)
    if len(faltan):
        p.append(f"continuidad: faltan {len(faltan)} fecha(s) del calendario "
                 f"'{decl['calendario']}' (primera {faltan[0].date()})")
    if len(sobran):
        p.append(f"continuidad: {len(sobran)} fecha(s) fuera del calendario "
                 f"'{decl['calendario']}' (primera {sobran[0].date()})")
    if p:
        return p, pd.DatetimeIndex([]), {}

    largo = int(sec["arrastre_maximo_dias"]) + 1
    inicio_cal = min([idx.min()] + [a for a, _ in decl["tramos"]])
    fin_cal = max([idx.max()] + [b for _, b in decl["tramos"]])
    cal = pd.date_range(inicio_cal, fin_cal, freq=freq)
    pos = pd.Series(np.arange(len(cal)), index=cal)

    anulados, largos = set(), []
    for a, b in decl["tramos"]:
        p0, p1 = int(pos[a]), int(pos[b])
        if p1 - p0 + 1 >= largo:
            largos.append({"desde": str(a.date()), "hasta": str(b.date()),
                           "dias": p1 - p0 + 1})
            fin = min(p1 + V, len(cal) - 1)
            anulados.update(cal[p0:fin + 1])
    anulados = pd.DatetimeIndex(sorted(anulados)).intersection(esperado)

    vacios = metrica.index[metrica.isna()]
    no_explicados = vacios.difference(anulados)
    con_valor = anulados.difference(vacios)
    if len(no_explicados):
        p.append(f"propagacion: {len(no_explicados)} dia(s) vacio(s) que la "
                 f"declaracion no explica (primero {no_explicados[0].date()})")
    if len(con_valor):
        p.append(f"propagacion: {len(con_valor)} dia(s) que la declaracion anula "
                 f"y tienen valor (primero {con_valor[0].date()})")

    meta = {"calendario": decl["calendario"], "ventana_dependencia_dias": V,
            "huecos_brutos": len(decl["tramos"]), "huecos_largos": largos,
            "dias_anulados": int(len(anulados))}
    return p, anulados, meta


def criterios_huecos(mask, b2, cobertura, anulados, dias_ep, doc):
    """Criterios de admisibilidad adicionales. Devuelve (motivos, meta)."""
    minimo_cob = float(ruta(doc, "protocolo.huecos_en_series.cobertura_minima_por_bloque"))
    min_eps = int(ruta(doc, "protocolo.test_de_permutacion.episodios_independientes_minimos"))
    motivos = []
    for nombre, c in cobertura.items():
        if c < minimo_cob:
            motivos.append(f"cobertura del {nombre} {round(100 * c, 2)}% < "
                           f"{round(100 * minimo_cob, 2)}% (enmienda 42)")
    m2 = mask.loc[b2]
    eps = episodios_independientes(m2.index[m2.values], dias_ep)
    limpios = [e for e in eps
               if not ((anulados >= e[0]) & (anulados <= e[-1])).any()]
    if len(limpios) < min_eps:
        motivos.append(f"solo {len(limpios)} episodios limpios en bloque_2 de "
                       f"{len(eps)} (minimo {min_eps}, enmienda 42)")
    return motivos, {"cobertura": {k: round(v, 4) for k, v in cobertura.items()},
                     "cobertura_minima": minimo_cob,
                     "episodios_bloque_2": len(eps),
                     "episodios_limpios_bloque_2": len(limpios)}


def construir_mascara('''

REEMPLAZOS = [
    (
        'DOCTRINA_COMPATIBLE = "2.13"  # enmienda 41',
        'DOCTRINA_COMPATIBLE = "2.14"  # enmienda 42',
    ),
    (
        "\n\ndef construir_mascara(",
        FUNCIONES_42,
    ),
    # --- tras cargar la metrica: verificacion de huecos ------------------
    (
        """        mask, meta_mask = construir_mascara(metrica, ficha)
        mask = mask[mask.index <= fecha_fin]
""",
        """        # ---- Enmienda 42: verificacion de huecos antes de la mascara ----
        regimen_42 = _regimen_huecos(v, doc)
        anulados, meta_42 = pd.DatetimeIndex([]), None
        if regimen_42:
            prob_42, anulados, meta_42 = verificar_huecos(metrica, ficha, doc)
            if prob_42:
                r = {"id": vid, "estado": traducir("PROVISIONAL", doc),
                     "motivo": "; ".join(prob_42),
                     "huecos_enmienda_42": {"verificacion": "FALLA",
                                            "problemas": prob_42}}
                if args.solo_comprobar:
                    print(f"\\n[--solo-comprobar] [{vid}] NO ADMISIBLE (enmienda 42)")
                    for x in prob_42:
                        print(f"    BLOQUEO: {x}")
                resultados[vid] = r
                continue
        # ---- fin enmienda 42 --------------------------------------------

        mask, meta_mask = construir_mascara(metrica, ficha)
        mask = mask[mask.index <= fecha_fin]
""",
    ),
    # --- tras particionar: excluir anulados y medir cobertura ------------
    (
        """        r = {"id": vid, "mascara": meta_mask, "particion": meta_part,
             "racha_media_mascara": round(racha_media(mask), 1)}
""",
        """        # ---- Enmienda 42: corte sobre calendario completo; despues se ----
        # excluyen los dias anulados de la mascara y se mide la cobertura.
        cobertura_42 = None
        if regimen_42:
            validos = metrica.reindex(mask.index).notna()
            cobertura_42 = {
                "bloque_1": float(validos.loc[b1].mean()) if len(b1) else 0.0,
                "bloque_2": float(validos.loc[b2].mean()) if len(b2) else 0.0,
            }
            mask = mask[validos.values]
            b1 = b1[b1.isin(mask.index)]
            b2 = b2[b2.isin(mask.index)]
            meta_42["dias_anulados_excluidos_de_la_mascara"] = int((~validos).sum())
        # ---- fin enmienda 42 --------------------------------------------

        r = {"id": vid, "mascara": meta_mask, "particion": meta_part,
             "racha_media_mascara": round(racha_media(mask), 1)}
        if regimen_42:
            r["huecos_enmienda_42"] = meta_42
""",
    ),
    # --- sin grandfathering para variables sujetas a la 42 -----------------
    (
        """        es_admision_nueva = v.get("admision_nueva_enmienda_38", True)
""",
        """        es_admision_nueva = v.get("admision_nueva_enmienda_38", True)
        if regimen_42:
            # protocolo.huecos_en_series.al_fallar.sin_grandfathering
            es_admision_nueva = True
""",
    ),
    # --- criterios adicionales dentro del diagnostico ----------------------
    (
        """        diag = diagnostico_estructural(mask, b1, b2, ret, base, doc)
        r["diagnostico_estructural"] = diag
""",
        """        diag = diagnostico_estructural(mask, b1, b2, ret, base, doc)
        if regimen_42:
            mot_42, crit_42 = criterios_huecos(mask, b2, cobertura_42, anulados,
                                               diag["dias_episodio"], doc)
            diag["enmienda_42"] = crit_42
            diag["motivos"] += mot_42
            diag["admisible"] = not diag["motivos"]
        r["diagnostico_estructural"] = diag
""",
    ),
    # --- impresion en --solo-comprobar -------------------------------------
    (
        """            for m in diag["motivos"]:
                print(f"    {'BLOQUEO' if es_admision_nueva else 'aviso (no bloquea)'}: {m}")
""",
        """            if "enmienda_42" in diag:
                c42 = diag["enmienda_42"]
                print(f"    enmienda 42: cobertura b1 "
                      f"{round(100 * c42['cobertura']['bloque_1'], 2)}% / b2 "
                      f"{round(100 * c42['cobertura']['bloque_2'], 2)}% (minimo "
                      f"{round(100 * c42['cobertura_minima'], 2)}%) | episodios "
                      f"limpios b2 {c42['episodios_limpios_bloque_2']} de "
                      f"{c42['episodios_bloque_2']} | dias anulados "
                      f"{meta_42['dias_anulados']}")
            for m in diag["motivos"]:
                print(f"    {'BLOQUEO' if es_admision_nueva else 'aviso (no bloquea)'}: {m}")
""",
    ),
    # --- --validar-entrada: declaracion de huecos --------------------------
    (
        """        problemas = prohibicion_prospectiva(entrada, doc)
        if problemas:""",
        """        problemas = prohibicion_prospectiva(entrada, doc)
        # Enmienda 42: una ficha nueva debe declarar sus huecos. La entrada
        # candidata ocuparia el indice len(registro)+1.
        try:
            n_cand = len(_cargar_json(args.registro)["entradas"]) + 1
        except Exception:
            n_cand = None
        corte_42 = int(ruta(doc, "protocolo.huecos_en_series.aplicacion.desde_entrada"))
        if "metrica_continua" in entrada and (n_cand is None or n_cand >= corte_42):
            _, p42 = _validar_declaracion_huecos(entrada, doc)
            problemas += p42
        if problemas:""",
    ),
    (
        'print("OK  la entrada no incumple la enmienda 31. "',
        'print("OK  la entrada no incumple las enmiendas 31 ni 42. "',
    ),
]


def main():
    with open(RUTA_DOC, "rb") as f:
        raw_doc = f.read()
    with open(RUTA_MOTOR, "rb") as f:
        raw_motor = f.read()

    if sha256_bytes(raw_doc) != SHA_DOC_ESPERADO:
        abortar(f"{RUTA_DOC} no esta en el estado esperado (leido {sha256_bytes(raw_doc)})")
    if sha256_bytes(raw_motor) != SHA_MOTOR_ESPERADO:
        abortar(f"{RUTA_MOTOR} no esta en el estado esperado (leido {sha256_bytes(raw_motor)})")

    doc = json.loads(raw_doc.decode("utf-8"))
    if doc["meta"]["version_esquema"] != VERSION_ESPERADA:
        abortar(f"version_esquema {doc['meta']['version_esquema']}, se esperaba {VERSION_ESPERADA}")
    if any(e["n"] == 42 for e in doc["meta"]["enmiendas"]):
        abortar("la enmienda 42 ya figura en meta.enmiendas")
    if "huecos_en_series" in doc["protocolo"]:
        abortar("protocolo.huecos_en_series ya existe")

    # La serializacion debe reproducir el fichero original byte a byte.
    def volcar(d):
        return (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if volcar(doc) != raw_doc:
        abortar("la serializacion de v2.json no reproduce el original; no se reescribe")

    doc["meta"]["version_esquema"] = VERSION_NUEVA
    doc["meta"]["enmiendas"].append(META_ENMIENDA)
    doc["protocolo"]["huecos_en_series"] = SECCION
    doc["ficha_congelada"]["alcance"]["aclaracion_enmienda_42"] = ACLARACION_ALCANCE
    doc["protocolo"]["admisibilidad_estructural"]["ampliacion_enmienda_42"] = AMPLIACION_38

    motor = raw_motor.decode("utf-8")
    for viejo, nuevo in REEMPLAZOS:
        n = motor.count(viejo)
        if n != 1:
            abortar(f"ancla de codigo encontrada {n} veces (se exige 1): {viejo[:60]!r}")
        motor = motor.replace(viejo, nuevo)

    nuevo_doc = volcar(doc)
    nuevo_motor = motor.encode("utf-8")
    with open(RUTA_DOC, "wb") as f:
        f.write(nuevo_doc)
    with open(RUTA_MOTOR, "wb") as f:
        f.write(nuevo_motor)

    print("OK  enmienda 42 aplicada")
    print(f"  v2.json   {VERSION_ESPERADA} -> {VERSION_NUEVA}  sha256 {sha256_bytes(nuevo_doc)}")
    print(f"  filtro.py 2.13 -> 2.14  sha256 {sha256_bytes(nuevo_motor)}")


if __name__ == "__main__":
    main()
