"""
MIGRACION — enmienda 29. Doctrina 2.2.0 -> 2.3.0 y entrada 18 del registro.

Script auditable de un solo uso. Hace exactamente tres cosas en v2.json y
dos en registro.json, y nada mas. Verifica la cadena antes y despues.

Se ejecuta desde la raiz del repositorio:  python migracion_enmienda_29.py
"""

import json
import hashlib
import sys

import cadena

ESPERADO_ANTES = "2.2.0"
NUEVA_VERSION = "2.3.0"
ULTIMO_HASH_ESPERADO = (
    "0aea02d54ce6cecac95fa14a1b6c8d97d7b9ef0e6947a1139b8eaebfcf10748c"
)


def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar(ruta, obj):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sha256_fichero(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# =====================================================================
# 1. DOCTRINA
# =====================================================================

def migrar_doctrina(d):
    if d["meta"]["version_esquema"] != ESPERADO_ANTES:
        raise SystemExit(
            f"v2.json no esta en {ESPERADO_ANTES}: "
            f"encontrado {d['meta']['version_esquema']}. Abortado."
        )

    d["meta"]["version_esquema"] = NUEVA_VERSION

    d["meta"]["enmiendas"].append({
        "n": 29,
        "titulo": "alcance de la ficha congelada, autoridad del presupuesto y limpieza de vocabulario",
        "fecha": "2026-09-04",
        "motivo": (
            "La ficha de SSR contenia una clausula operativa (bloqueo_ejecucion) que "
            "referenciaba una ruta de la doctrina eliminada por la enmienda 24. El "
            "sintoma era una ruta rota; la causa es que la ficha congelada mezclaba "
            "definicion de medida, que no caduca, con condiciones operativas "
            "transitorias, que si caducan. Se separan ambas cosas y la condicion pasa "
            "a la doctrina en forma que no puede quedar desactualizada."
        ),
        "descartado": (
            "Resolver rutas obsoletas desde el codigo siguiendo renombrado_desde. "
            "Rechazado por cuatro revisiones externas independientes: renombrado_desde "
            "prueba genealogia documental, no equivalencia semantica, y el renombrado "
            "de la enmienda 24 tambien cambio la definicion de los sub-periodos. "
            "Ademas contradice meta.precedencia: el codigo aborta, no se adapta."
        ),
        "partes": [
            "alcance de ficha_congelada y regla de marcadores PENDIENTE",
            "autoridad unica del presupuesto",
            "limpieza de vocabulario de la enmienda 24",
            "lote inmutable, fijado por la primera entrada del id",
        ],
        "hallazgo_durante_la_migracion": (
            "La parte 4 no estaba prevista. Aparecio al comprobar que el presupuesto "
            "derivado seguia cuadrando tras la migracion: no cuadraba, y ya no cuadraba "
            "en 2.2.0 antes de tocar nada. filtro.py v2 habria abortado en el arranque."
        ),
    })

    # --- parte 1: alcance de la ficha ---------------------------------
    d["ficha_congelada"]["alcance"] = {
        "enmienda": 29,
        "regla": (
            "La ficha congelada contiene UNICAMENTE definicion de medida: como se "
            "mide la variable y como se juzgara el efecto. Prohibido incluir "
            "condiciones operativas, estados de disponibilidad de datos o "
            "referencias a rutas concretas de v2.json."
        ),
        "justificacion": (
            "Una definicion de medida no caduca. Una condicion operativa si, y al "
            "vivir dentro de un documento inmutable no hay donde actualizarla. Una "
            "referencia a una ruta de la doctrina hace que la ficha dependa de la "
            "estructura de otro archivo que puede cambiar."
        ),
        "prohibicion_de_referencias": (
            "Ninguna ficha puede nombrar una ruta de v2.json. Si una ficha contiene "
            "una ruta, filtro.py aborta y la nombra. No se resuelve, no se traduce, "
            "no se sigue renombrado_desde."
        ),
        "campos_que_no_pertenecen_a_la_ficha": ["bloqueo_ejecucion"],
        "sustituido_por": "ficha_congelada.marcadores_pendientes",
    }

    d["ficha_congelada"]["marcadores_pendientes"] = {
        "enmienda": 29,
        "regla": (
            "Ningun campo de la entrada operativa de una variable puede contener un "
            "marcador que empiece por PENDIENTE_ en el momento de transitar a "
            "EN_TEST. filtro.py aborta y nombra el campo exacto."
        ),
        "ambito": "recursivo sobre todos los campos de la entrada operativa, a cualquier profundidad",
        "prefijo": "PENDIENTE_",
        "justificacion": (
            "Sustituye a las clausulas bloqueo_ejecucion escritas a mano dentro de "
            "cada ficha. Es mas fuerte: se aplica a toda variable presente y futura, "
            "no solo a la que se acordo de escribirla, y no nombra ninguna ruta, por "
            "lo que no puede quedar desactualizada por un renombrado."
        ),
        "cobertura_verificada_ssr": (
            "metrica_continua.fuente = PENDIENTE_DEFINICION sigue bloqueando la "
            "transicion de SSR a EN_TEST por esta regla, sin necesidad de clausula "
            "propia en la ficha."
        ),
        "no_cubre": (
            "Los bloqueos de alcance global no viven en las fichas. "
            "fuente_de_precio.snapshot.estado = PENDIENTE_PRIMER_LOTE afecta a todo "
            "lote y lo comprueba filtro.py sobre la doctrina, no sobre la ficha."
        ),
    }

    d["ficha_congelada"]["migracion_de_fichas"] = {
        "enmienda": 29,
        "regla": (
            "Cuando una enmienda renombre o elimine una clave de la doctrina, toda "
            "ficha en estado PROPUESTA que la referencie debe sustituirse antes de "
            "cualquier evaluacion. La sustitucion se registra como entrada nueva."
        ),
        "limite_de_la_sustitucion": (
            "Una ficha sustitutiva solo puede diferir de la anterior en los campos "
            "que la enmienda obliga a tocar, en motivo_sustitucion y en los hashes. "
            "Todo campo de definicion de medida (metrica_continua, mascara, "
            "horizonte_N, M, unidad_theta, signo_esperado, casilla_dashboard, "
            "naturaleza_de_la_hipotesis, dias_episodio) debe ser identico. filtro.py "
            "compara ambas entradas y aborta si difiere alguno."
        ),
        "justificacion_del_limite": (
            "La mutabilidad en PROPUESTA es necesaria, pero sin limite medible se "
            "convierte en la puerta de atras que permite retocar una ficha alegando "
            "cambio doctrinal. El limite es verificable por codigo."
        ),
        "prohibido_tras_en_test": (
            "Si la variable ya alcanzo EN_TEST no hay sustitucion posible. filtro.py "
            "aborta de forma permanente. Es el coste asumido en "
            "integridad.resolucion_de_entradas.inmutabilidad."
        ),
    }

    # --- parte 2: autoridad del presupuesto ---------------------------
    d["presupuesto"]["autoridad"] = {
        "enmienda": 29,
        "regla": (
            "Los maximos (propuestas_maximas_por_trimestre y "
            "familias_nuevas_maximas_por_trimestre) viven exclusivamente en v2.json. "
            "Se retiran de registro.json."
        ),
        "motivo": (
            "presupuesto_por_trimestre vive fuera del array entradas, luego fuera de "
            "la cadena de hashes. Un valor duplicado ahi no es un snapshot forense: "
            "es un segundo parametro editable sin romper nada. Conservarlo como "
            "'prueba historica' era falso, porque no esta firmado."
        ),
        "que_permanece_en_registro_json": [
            "propuestas_usadas",
            "familias_nuevas_usadas",
        ],
        "por_que_permanecen": (
            "presupuesto.derivacion los necesita: filtro.py deriva el consumo del "
            "array entradas y aborta si no coincide con el contador almacenado. Ese "
            "contraste es el mecanismo de la enmienda 10 y se conserva intacto."
        ),
        "comportamiento_filtro_py": (
            "Si registro.json contiene todavia un campo de maximos, filtro.py aborta: "
            "indica que la migracion de la enmienda 29 no se aplico."
        ),
    }

    # --- parte 4: lote inmutable --------------------------------------
    d["integridad"]["resolucion_de_entradas"]["lote"] = {
        "enmienda": 29,
        "regla": (
            "lote es una propiedad de la VARIABLE, no de la entrada. Lo fija la "
            "PRIMERA entrada de un id y ninguna entrada posterior puede cambiarlo."
        ),
        "comportamiento_ante_discrepancia": (
            "Si una entrada posterior declara un lote distinto, filtro.py IGNORA ese "
            "valor y hace constar la incoherencia en el informe, nombrando la entrada. "
            "No aborta: el registro es append-only y estas entradas no se pueden editar."
        ),
        "relacion_con_gana_la_ultima": (
            "No la contradice. La doctrina ya distingue entre lo que transiciona y lo "
            "que queda fijado: el estado gana la ultima, la ficha es inmutable. lote "
            "pertenece al segundo grupo y hasta ahora no estaba dicho."
        ),
        "motivo": (
            "Detectado durante la migracion de la enmienda 29. La entrada 13 "
            "(nasdaq_aclaracion_panel) archivo una aclaracion sobre una variable de "
            "v1 bajo el lote 2026-Q3, mientras que la entrada 17 "
            "(halving_ciclo_aclaracion_pvalor), misma operacion, uso correctamente "
            "v1-historico. Dos convenciones distintas para el mismo acto. Al resolver "
            "ids, la entrada 13 ganaba como operativa de 'nasdaq' y arrastraba su lote "
            "equivocado, lo que hacia que nasdaq (RECHAZADA_PVALOR) contase como "
            "presupuesto consumido de 2026-Q3."
        ),
        "agujero_cerrado": (
            "Sin esta regla, una entrada posterior puede mover cualquier variable de "
            "trimestre a posteriori, y con ella su consumo de presupuesto. El caso de "
            "la entrada 13 es el sintoma; el agujero es general."
        ),
        "descartado": (
            "Excluir del conteo los ids cuyas entradas sean aclaraciones con "
            "referencia_entrada_anterior a un id distinto. Rechazado: infiere una "
            "categoria semantica ('esto no es una variable') de la forma documental de "
            "dos entradas, que es el mismo error que la enmienda 29 rechaza en el caso "
            "de renombrado_desde. Ademas habria ocultado la incoherencia de la entrada "
            "13 en vez de dejarla visible, y no habria cerrado el agujero general."
        ),
        "orden_de_resolucion": (
            "1) resolver ids (enmienda 28: las aclaraciones con id propio se pliegan "
            "sobre el id referenciado); 2) fijar lote por la primera entrada de cada id "
            "resuelto; 3) fijar estado por la ultima; 4) contar presupuesto."
        ),
    }

    d["presupuesto"]["derivacion"]["orden_de_resolucion"] = (
        "El conteo opera sobre ids RESUELTOS, no sobre entradas crudas, y toma el lote "
        "segun integridad.resolucion_de_entradas.lote. Ver el orden de los cuatro pasos "
        "alli. Sin ese orden, el consumo derivado de 2026-Q3 da 1 en lugar de 0."
    )
    d["presupuesto"]["derivacion"]["verificacion_2026Q3"] = (
        "Con la formula de la enmienda 27 y el orden de resolucion de la enmienda 29, "
        "el consumo derivado de 2026-Q3 es 0: la entrada operativa de SSR esta en "
        "PROPUESTA, y nasdaq resuelve al lote v1-historico, que es exento. Coincide con "
        "el contador almacenado. Verificado por script el 2026-09-04."
    )

    # --- parte 3: limpieza de vocabulario -----------------------------
    gates = d["protocolo"]["gates_cualitativos"]

    if gates["lista"] != [
        "estabilidad_entre_epocas",
        "anticipacion_no_contemporaneidad",
        "contribucion_incremental_R2",
        "coherencia_de_signo",
    ]:
        raise SystemExit("gates_cualitativos.lista no tiene el contenido esperado. Abortado.")

    gates["lista"] = [
        "magnitud_en_tramos",
        "anticipacion",
        "contribucion_incremental_R2",
        "coherencia_de_signo_en_tramos",
    ]
    gates["nota_lista"] = (
        "Nombres alineados con gates_cualitativos.parametros por la enmienda 29. "
        "Los nombres anteriores (estabilidad_entre_epocas, "
        "anticipacion_no_contemporaneidad, coherencia_de_signo) quedan en "
        "renombrado_desde de cada bloque de parametros, solo como trazabilidad "
        "documental. No son alias resolubles por codigo."
    )

    for e in d["estados"]["lista"]:
        if e["id"] == "DESCARTADA_GATE_1":
            if e["descripcion"] != "Fallo estabilidad entre epocas":
                raise SystemExit("descripcion de DESCARTADA_GATE_1 inesperada. Abortado.")
            e["descripcion"] = "Fallo el gate 1: magnitud en tramos"
            e["nota_enmienda_29"] = (
                "Descripcion actualizada. Las epocas de calendario desaparecieron con "
                "la enmienda 24 y el gate 1 dejo de exigir signo con la enmienda 25. "
                "El identificador del estado no cambia: el registro es append-only."
            )

    tabla = d["estados"]["mapeo_salida_filtro_py"]["tabla"]
    if "RECHAZADA_paso_2" not in tabla:
        raise SystemExit("la fila RECHAZADA_paso_2 no esta donde se esperaba. Abortado.")
    del tabla["RECHAZADA_paso_2"]

    d["estados"]["mapeo_salida_filtro_py"]["fila_retirada_enmienda_29"] = {
        "fila": "RECHAZADA_paso_2 -> DESCARTADA_GATE_2",
        "motivo": (
            "Contradecia a la enmienda 19, que retira el estado DESCARTADA_GATE_2 y "
            "ordena a filtro.py abortar si lo emite. El gate 2 no es vinculante: no "
            "existe ninguna salida que deba mapearse a ese estado."
        ),
        "el_estado_no_se_borra": (
            "DESCARTADA_GATE_2 permanece en estados.lista con emision_permitida false. "
            "Lo referencia presupuesto.derivacion y el registro es append-only."
        ),
    }

    d["estados"]["mapeo_salida_filtro_py"]["nota_claves"] = (
        "Las claves de la tabla son etiquetas internas de filtro.py, no estados del "
        "protocolo. Solo los valores pertenecen a la lista cerrada."
    )

    return d


# =====================================================================
# 2. REGISTRO
# =====================================================================

CAMPOS_DE_MEDIDA = [
    "metrica_continua", "mascara", "horizonte_N", "unidad_theta", "M",
    "estado_M", "derivacion_M", "casilla_dashboard",
    "naturaleza_de_la_hipotesis", "dias_episodio", "signo_esperado",
    "justificacion_signo",
]


def construir_entrada_18(operativa_16):
    nueva = {
        k: v for k, v in operativa_16.items()
        if k not in ("hash", "hash_anterior", "bloqueo_ejecucion",
                     "motivo_sustitucion", "nota", "fecha_registro")
    }
    nueva["fecha_registro"] = "2026-09-04"
    nueva["motivo_sustitucion"] = (
        "Sustituye a la entrada 16 para retirar el campo bloqueo_ejecucion, que la "
        "enmienda 29 declara ajeno al alcance de la ficha congelada. Aquella "
        "clausula referenciaba la ruta "
        "gates_cualitativos.parametros.estabilidad_entre_epocas.definicion_de_epocas, "
        "eliminada por la enmienda 24. La condicion que protegia no se pierde: la "
        "regla ficha_congelada.marcadores_pendientes impide la transicion a EN_TEST "
        "mientras metrica_continua.fuente sea PENDIENTE_DEFINICION, y lo hace para "
        "toda variable, no solo para esta. Permitido porque SSR sigue en PROPUESTA."
    )
    nueva["nota_cambio_de_tramos"] = (
        "Se hace constar que el cambio de epocas de calendario a tramos "
        "proporcionales (enmienda 24) es FAVORABLE a esta variable: bajo las epocas "
        "de calendario de v1, una variable cuyo bloque_1 no abarcase tres epocas "
        "fallaba el gate 1 por construccion, que es exactamente el caso de SSR con "
        "3,8 anios por bloque. No se oculta que la sustitucion de ficha ocurre en un "
        "contexto que beneficia a la variable. Ningun campo de medida se modifica."
    )
    nueva["nota"] = (
        "Entrada operativa de SSR desde esta fecha. Las entradas 12, 15 y 16 se "
        "conservan como historial y no se evaluan."
    )
    return nueva


def migrar_registro(r):
    if r["meta"]["ultimo_hash"] != ULTIMO_HASH_ESPERADO:
        raise SystemExit("el ultimo hash del registro no es el esperado. Abortado.")

    ok, msg = cadena.verificar(r)
    if not ok:
        raise SystemExit(f"cadena rota ANTES de migrar: {msg}")
    print(f"  cadena antes: {msg}")

    # 2a. retirar los maximos de presupuesto_por_trimestre
    for trimestre, datos in r["presupuesto_por_trimestre"].items():
        for campo in ("propuestas_maximas", "familias_nuevas_maximas"):
            if campo in datos:
                del datos[campo]
                print(f"  retirado {trimestre}.{campo}")
        datos["nota_enmienda_29"] = (
            "Los maximos viven solo en v2.json (presupuesto.autoridad). Aqui quedan "
            "unicamente los contadores de uso, que filtro.py contrasta contra el "
            "valor derivado del array entradas."
        )

    # 2b. entrada 18
    operativa = [e for e in r["entradas"] if e["id"] == "stablecoin_supply_ratio"][-1]
    nueva = construir_entrada_18(operativa)

    for campo in CAMPOS_DE_MEDIDA:
        if operativa.get(campo) != nueva.get(campo):
            raise SystemExit(
                f"campo de medida '{campo}' difiere entre la entrada 16 y la 18. "
                f"Prohibido por ficha_congelada.migracion_de_fichas. Abortado."
            )
    print(f"  {len(CAMPOS_DE_MEDIDA)} campos de medida verificados identicos")

    if "bloqueo_ejecucion" in nueva:
        raise SystemExit("bloqueo_ejecucion sigue presente. Abortado.")

    return cadena.anadir(r, nueva)


# =====================================================================

def main():
    print("Doctrina:")
    d = migrar_doctrina(cargar("v2.json"))
    guardar("v2.json", d)
    print(f"  v2.json -> {NUEVA_VERSION}, {len(d['meta']['enmiendas'])} enmiendas")
    print(f"  SHA-256 nuevo: {sha256_fichero('v2.json')}")

    print("Registro:")
    r = migrar_registro(cargar("registro.json"))
    guardar("registro.json", r)

    ok, msg = cadena.verificar(cargar("registro.json"))
    if not ok:
        raise SystemExit(f"CADENA ROTA DESPUES DE MIGRAR: {msg}")
    print(f"  cadena despues: {msg}")
    print(f"  ultimo hash: {r['meta']['ultimo_hash']}")

    # comprobacion final: presupuesto derivado con el orden de resolucion
    dd = cargar("v2.json")
    consumidos = set(dd["presupuesto"]["derivacion"]["estados_que_cuentan_como_consumido"])
    exentos = set(dd["presupuesto"]["derivacion"]["lotes_exentos"])

    def resolver(e):
        ref = e.get("referencia_entrada_anterior")
        if e.get("tipo_entrada") == "aclaracion" and ref and ref != e["id"]:
            return ref
        return e["id"]

    lote_de, estado_de, incoherencias = {}, {}, []
    for e in r["entradas"]:
        rid = resolver(e)
        if rid not in lote_de:
            lote_de[rid] = e.get("lote")          # lote: gana la PRIMERA
        elif e.get("lote") != lote_de[rid]:
            incoherencias.append(f"entrada '{e['id']}' declara lote "
                                 f"{e.get('lote')} pero '{rid}' es {lote_de[rid]}")
        estado_de[rid] = e["estado"]              # estado: gana la ULTIMA

    derivado = sum(1 for rid, est in estado_de.items()
                   if lote_de[rid] not in exentos and est in consumidos)
    almacenado = r["presupuesto_por_trimestre"]["2026-Q3"]["propuestas_usadas"]
    print(f"  presupuesto 2026-Q3: derivado={derivado} almacenado={almacenado}")
    for msg_i in incoherencias:
        print(f"  INCOHERENCIA DE LOTE (se ignora, se reporta): {msg_i}")
    if derivado != almacenado:
        raise SystemExit("discrepancia de presupuesto. Abortado.")

    print("\nOK.")


if __name__ == "__main__":
    sys.exit(main())
