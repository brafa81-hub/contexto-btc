#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aplicar_enmienda_36.py — script de un solo uso.

Aplica la enmienda 36 (repesca individual de variables del regimen v1) a v2.json.

DOCTRINA APLICADA:
  - No edita v2.json a mano. Verifica SHA-256 de origen antes de tocar nada.
  - Aborta, nunca adapta. Cualquier discrepancia detiene la ejecucion sin escribir.
  - Se commitea al repositorio como registro auditable de como se aplico el cambio.

NO TOCA registro.json. La enmienda 36 no modifica ninguna entrada del registro.

Uso:
    python3 aplicar_enmienda_36.py --v2 v2.json --registro registro.json --salida v2_nuevo.json
    python3 aplicar_enmienda_36.py ... --solo-comprobar     (verifica y no escribe)
"""

import argparse
import hashlib
import json
import sys

# ---------------------------------------------------------------------------
# CONSTANTES DE VERIFICACION — estado de origen, verificado el 2026-09-07
# ---------------------------------------------------------------------------

SHA256_V2_ORIGEN = "c12a1f0d6d9160d278483dbb2e84dba7771b2be321d4abc26a744cf07bb0f5a5"
SHA256_REGISTRO = "8257e0c369406801ddeb94c62c99902711fd76b4cc31b240ed3b6378973e403b"

VERSION_ORIGEN = "2.9.0"
VERSION_DESTINO = "2.10.0"
ENMIENDAS_ORIGEN = 35
ENMIENDA_NUEVA = 36

# Ancla de plantilla de medida, calculada sobre la ficha operativa de
# ssr_capstables. NO es una constante de doctrina: la doctrina ordena
# calcularla del registro. Se fija aqui solo para que el script aborte si el
# registro no reproduce el valor verificado el 2026-09-07.
HASH_PLANTILLA_ANCLA = (
    "35855bd55c796839d1bcaf2c7f9353955ce416ba53c675139a9b92759fc39857"
)

ID_ANCLA = "ssr_capstables"

PLANTILLA_RAIZ = [
    "horizonte_N",
    "dias_episodio",
    "M",
    "unidad_theta",
    "signo_esperado",
]
PLANTILLA_MASCARA = [
    "q_percentil",
    "tipo_ventana",
    "longitud_ventana_dias",
    "solo_informacion_anterior_a_t",
    "inclusividad",
    "warm_up_dias",
    "warm_up_excluido_del_computo_de_bloques",
]

IDS_ELEGIBLES = [
    "mvrv_z_score",
    "funding_rate",
    "dxy",
    "fed_funds_rate",
    "vix",
    "nasdaq",
    "fear_and_greed_index",
    "hashrate",
    "m2_global",
]

TEXTO_NOTA_ANTERIOR = (
    "No hay mecanismo de reapertura. Una variable descartada queda descartada "
    "de forma permanente bajo este protocolo."
)


def abortar(msg):
    print(f"\nABORTA: {msg}\n", file=sys.stderr)
    print("No se ha escrito ningun fichero.", file=sys.stderr)
    sys.exit(1)


def sha256_fichero(ruta):
    with open(ruta, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def canonizar(obj):
    """Misma canonizacion que registro.json -> meta.canonizacion."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def hash_de_plantilla(ficha):
    """Sub-hash del subconjunto de 12 campos de medida. Calculado, no almacenado."""
    sub = {k: ficha[k] for k in PLANTILLA_RAIZ if k in ficha}
    if "mascara" in ficha:
        sub["mascara"] = {
            k: ficha["mascara"][k] for k in PLANTILLA_MASCARA if k in ficha["mascara"]
        }
    n = len(sub) - (1 if "mascara" in sub else 0) + len(sub.get("mascara", {}))
    return hashlib.sha256(canonizar(sub)).hexdigest(), n, sub


def ficha_operativa(registro, vid):
    """Ultima entrada del id que no sea de tipo transicion_de_estado.

    integridad.resolucion_de_entradas.ficha_operativa
    """
    encontrada = None
    for e in registro["entradas"]:
        if e.get("id") == vid and e.get("tipo_entrada") != "transicion_de_estado":
            encontrada = e
    return encontrada


# ---------------------------------------------------------------------------
# BLOQUES DE LA ENMIENDA
# ---------------------------------------------------------------------------

ENTRADA_META = {
    "n": 36,
    "titulo": "repesca individual de variables del regimen v1",
    "fecha": "2026-09-07",
    "motivo": (
        "Mantener intocable un veredicto producido por un metodo que el propio "
        "protocolo declara defectuoso le daba autoridad permanente a algo a lo que "
        "se le niega valor probatorio en todas las demas clausulas. Los defectos "
        "de v1 (cola elegida tras ver el signo, error tipo I 0.095 a nominal 0.05, "
        "desfases sin correccion) hacian el filtro MAS LAXO: una variable que no lo "
        "supero no fue victima de un filtro estricto, pero tampoco fue evaluada por "
        "uno valido."
    ),
    "origen_externo": (
        "Cinco revisiones externas el 2026-09-06 sobre la naturaleza de "
        "unicidad_del_test (unanimidad 5/5: es multiplicidad, un test defectuoso "
        "consume el intento). Cuatro revisiones externas el 2026-09-07 sobre las dos "
        "decisiones de diseno de esta enmienda."
    ),
    "partes": [
        "1. Seccion nueva de primer nivel: repesca_v1.",
        "2. Primera entrada en protocolo.unicidad_del_test.excepciones, hasta hoy "
        "lista vacia, y sustitucion del texto de su nota.",
        "3. Campo nuevo de ficha repesca_de_id_v1, trazabilidad no resolutiva, con "
        "el precedente del campo sustituye_a_id_retirado.",
        "4. hash_de_plantilla: anclaje verificable por codigo a la plantilla de "
        "medida congelada de ssr_capstables, calculado y no almacenado.",
        "5. Declaracion del defecto de la consulta externa de potencia y del cabo "
        "suelto de rango probatorio en el panel.",
    ],
    "naturaleza": (
        "Anade una excepcion acotada y cerrada. No altera ningun gate, umbral, "
        "mascara, particion ni criterio estadistico. No modifica ninguna entrada del "
        "registro. No reescribe ningun texto previo salvo "
        "protocolo.unicidad_del_test.nota, cuyo texto anterior se conserva."
    ),
    "momento": (
        "Lote 2026-Q3 cerrado, sin test pendiente ni resultado contaminable. "
        "Ninguna variable en CONFIRMADA."
    ),
}

EXCEPCION_UNICIDAD = {
    "id": "repesca_v1",
    "enmienda": 36,
    "fecha_alta": "2026-09-07",
    "resumen": (
        "Una variable rechazada bajo el regimen v1 puede volver a presentarse UNA "
        "SOLA VEZ, con identificador nuevo, declarando su antecedente, consumiendo "
        "plaza ordinaria del trimestre y adoptando sin retoques la plantilla de "
        "medida congelada de ssr_capstables. Condiciones completas en la seccion "
        "repesca_v1."
    ),
    "cerrada": True,
    "alcance_finito": (
        "Exclusivamente los nueve ids enumerados en repesca_v1.ids_elegibles. No "
        "aplicable a descartes bajo v2 ni posterior."
    ),
    "por_que_se_declara_excepcion": (
        "Existe un argumento tecnico para no declararla: un id nuevo es, para el "
        "motor, una variable nueva. Ese argumento es exactamente el que "
        "ficha_congelada.retirada_en_propuesta.reproposicion.una_sola_vez."
        "elusion_conocida describe como via de elusion. No se usa. Una repesca con "
        "antecedente declarado ES una segunda oportunidad sobre el mismo constructo, "
        "y la propia obligacion de declarar el antecedente lo demuestra: si no lo "
        "fuera, no habria nada que declarar."
    ),
    "funcion_de_control": (
        "Esta lista es ademas el punto de control automatico. Una via de reapertura "
        "documentada fuera de aqui no pasaria por ninguna comprobacion verificable y "
        "la clausula de unicidad dejaria de ser comprobable por codigo para pasar a "
        "ser de confianza."
    ),
}

NOTA_NUEVA = (
    "No hay mecanismo general de reapertura. Una variable descartada queda "
    "descartada de forma permanente bajo este protocolo, con la unica salvedad de "
    "la excepcion cerrada repesca_v1, cuyo alcance es una lista finita y enumerada "
    "de nueve ids del regimen v1 y que no admite ampliacion a resultados de v2 ni "
    "posteriores."
)

MOTIVO_SUSTITUCION = (
    "El texto anterior pasaba a ser falso al abrirse la repesca. Un documento que "
    "afirma no tener fugas en el campo que un auditor consulta primero, mientras la "
    "fuga existe documentada en otra seccion, convierte su clausula central de "
    "integridad en decorativa."
)

NOTA_RE_TEST = (
    "Permanece en false. Sigue rigiendo sobre ids formales: ninguna entrada puede "
    "re-testear el id que ya fue testeado. La repesca no lo contradice porque usa id "
    "nuevo, pero eso NO es la razon por la que se admite: ver "
    "excepciones[0].por_que_se_declara_excepcion."
)

REPESCA_V1 = {
    "enmienda": 36,
    "fecha": "2026-09-07",
    "regla": (
        "Una variable rechazada bajo el regimen v1 puede volver a presentarse UNA "
        "SOLA VEZ, con identificador nuevo, declarando su antecedente v1 y su "
        "resultado, consumiendo plaza ordinaria del trimestre y adoptando sin "
        "retoques la plantilla de medida congelada de ssr_capstables."
    ),
    "por_que_se_abre": {
        "asimetria_corregida": (
            "Mantener intocable un veredicto producido por un metodo que el propio "
            "protocolo declara defectuoso le da autoridad permanente a algo a lo que "
            "se le niega valor probatorio en todas las demas clausulas."
        ),
        "direccion_del_defecto_v1": (
            "Los defectos conocidos de v1 hacian el filtro MAS LAXO, no mas "
            "estricto. Cola elegida tras ver el signo (error tipo I medido 0.095 a "
            "nominal 0.05, ver protocolo.test_de_permutacion."
            "evidencia_de_calibracion), desfases multiples sin correccion. Una "
            "variable que no supero un filtro sesgado a su favor no fue victima de "
            "un filtro estricto; tampoco fue evaluada por uno valido."
        ),
        "donde_esta_la_garantia": (
            "La contaminacion afecta a la fase de cribado, no a la de confirmacion. "
            "Los cinco trimestres de confirmacion_forward son datos que no existen "
            "hoy. El conocimiento previo del autor puede ayudar a una variable a "
            "ENTRAR en la fase forward; no puede ayudarla a superarla."
        ),
        "lo_que_esto_NO_afirma": (
            "No afirma que la fase 1 quede limpia. Afirma que su contaminacion es un "
            "coste de oportunidad (plazas gastadas, tasa de confirmacion mas baja) y "
            "no un defecto de inferencia final. La fase 1 de una repesca debe leerse "
            "como filtro de viabilidad, no como evidencia."
        ),
    },
    "ids_elegibles": {
        "regla": (
            "Un id es elegible como antecedente si y solo si figura en esta lista. "
            "filtro.py aborta si repesca_de_id_v1 apunta fuera de ella."
        ),
        "lista": IDS_ELEGIBLES,
        "criterio_de_la_lista": (
            "Los nueve ids con estado operativo RECHAZADA_PVALOR y lote v1-historico "
            "en el registro de 23 entradas del 2026-09-07."
        ),
        "verificacion_viva": (
            "Ademas de la pertenencia a esta lista, filtro.py comprueba contra el "
            "registro que el id apuntado existe, es de regimen v1, tiene lote "
            "v1-historico y su estado operativo es RECHAZADA_PVALOR. Las dos "
            "comprobaciones son redundantes a proposito: fallan de forma distinta y "
            "detectan errores distintos."
        ),
        "lista_cerrada": (
            "No ampliable. Anadir un id a esta lista exigiria una enmienda nueva que "
            "justificase por que ese id fue evaluado por un metodo declarado "
            "defectuoso."
        ),
    },
    "no_elegibles": {
        "regla": (
            "Los estados de resultado del regimen v2 NO son elegibles: "
            "DESCARTADA_GATE_1, DESCARTADA_GATE_3, DESCARTADA_GATE_4, "
            "RECHAZADA_PVALOR bajo lote v2, RECHAZADA_FORWARD."
        ),
        "motivo": (
            "El argumento que abre esta via es que el metodo v1 era mas laxo de lo "
            "que declaraba. Ese argumento no existe para v2. Sin esta clausula, la "
            "repesca deja de ser una excepcion acotada y pasa a ser un mecanismo "
            "general de reapertura."
        ),
        "una_sola_repesca_por_id_para_siempre": (
            "El limite es una repesca por id, no una por version del protocolo. Una "
            "variable ya repescada y descartada bajo v2 NO recupera elegibilidad si "
            "en el futuro se escribe un protocolo v3, por muy superior que sea. "
            "Permitir una repesca por cada mejora del sistema convertiria la "
            "excepcion acotada en reevaluacion permanente y destruiria el valor del "
            "veredicto negativo, que es el nucleo de unicidad_del_test. Reabrir esa "
            "via exigiria una enmienda nueva, explicita y con sus propias "
            "condiciones: queda prohibida por defecto, no prohibida para siempre."
        ),
        "casos_expresamente_fuera": {
            "etf_flows": (
                "PENDIENTE_REVISION. No se cerro ningun test: 'Historia "
                "insuficiente. No consume presupuesto ni entra en BY'. Puede entrar "
                "como propuesta ordinaria cuando haya historia suficiente. No "
                "necesita esta via."
            ),
            "probabilidad_contexto": (
                "NULO_V1. 'El test no llego a abrirse'. Misma via ordinaria."
            ),
            "halving_ciclo": (
                "SELLADA_V1, con sellados[0].re_test_permitido = false. Ver "
                "asimetria_halving_ciclo en esta misma seccion."
            ),
        },
    },
    "campos_obligatorios": {
        "ancla_estructural": (
            "La presencia del campo repesca_de_id_v1 en la ficha. No se crea ningun "
            "discriminante nuevo ni se toca la lista global "
            "ficha_congelada.campos_obligatorios, que rige para toda ficha."
        ),
        "campos": {
            "repesca_de_id_v1": {
                "definicion": (
                    "Id del antecedente del regimen v1 cuyo resultado se vuelve a "
                    "someter al protocolo con identificador nuevo."
                ),
                "naturaleza": (
                    "Trazabilidad, NUNCA resolucion. filtro.py no lo usa jamas para "
                    "plegar ids, exactamente igual que el campo de ficha "
                    "sustituye_a_id_retirado (enmienda 31, precedente vivo en la "
                    "ficha operativa de ssr_capstables, registro.json)."
                ),
                "prohibicion_de_forma": (
                    "La ficha de repesca NO puede usar referencia_entrada_anterior "
                    "apuntando al id v1: eso la plegaria sobre el id antiguo al "
                    "resolver ids y la haria heredar su estado terminal."
                ),
            },
            "declaracion_de_antecedente": {
                "definicion": (
                    "Texto obligatorio en la propia ficha. filtro.py aborta si "
                    "repesca_de_id_v1 esta presente y este campo falta."
                ),
                "debe_contener": [
                    "1. El id del antecedente v1 y su resultado literal.",
                    "2. Que el cribado de esta variable se ejecuta con el "
                    "antecedente CONOCIDO por el autor.",
                    "3. Que la garantia frente a esa contaminacion no la aporta la "
                    "fase de cribado sino la confirmacion forward sobre datos que no "
                    "existian al congelar la ficha.",
                    "4. Que la fase 1 de esta variable no debe leerse como filtro "
                    "ciego dentro de tres anios.",
                ],
                "prohibicion": (
                    "No puede omitirse alegando que el id es nuevo. Presentar una "
                    "repesca como variable sin historia es exactamente la "
                    "elusion_conocida de la enmienda 32."
                ),
            },
        },
        "compatibilidad_con_sustituye_a_id_retirado": (
            "Una ficha puede llevar ambos campos. En ese caso rige tambien "
            "una_sola_vez: una ficha que lleve sustituye_a_id_retirado no puede a su "
            "vez ser retirada, y la cadena de sucesion queda cerrada igual."
        ),
    },
    "hash_de_plantilla": {
        "proposito": (
            "Verificar por codigo que la ficha de repesca adopta sin retoques la "
            "plantilla de medida congelada de ssr_capstables."
        ),
        "por_que_no_sirve_hash_de_medida": (
            "ficha_congelada.hash_de_medida aborta ante colision entre ids resueltos "
            "distintos. Aqui la colision PARCIAL es deseada y buscada. Son dos "
            "controles con proposito opuesto sobre el mismo material."
        ),
        "definicion": (
            "SHA-256 de la serializacion canonica del subconjunto de doce campos "
            "listados en subconjunto, extraidos de una ficha."
        ),
        "canonizacion": (
            "La MISMA que registro.json -> meta.canonizacion: claves ordenadas, "
            "separadores compactos, UTF-8. No se define ninguna convencion nueva ni "
            "se aplica normalizacion previa del contenido."
        ),
        "subconjunto": {
            "raiz": PLANTILLA_RAIZ,
            "mascara": PLANTILLA_MASCARA,
            "total_campos": 12,
            "criterio_de_inclusion": (
                "Los siete parametros son exactamente "
                "ficha_congelada.mascara.campos_obligatorios. Los cinco de raiz son "
                "los campos de medida que definen la geometria del test y no la "
                "identidad de la variable."
            ),
            "criterio_de_exclusion": (
                "Quedan fuera metrica_continua (es lo que cambia, es el proposito de "
                "la repesca), casilla_dashboard (variable distinta, casilla "
                "distinta), naturaleza_de_la_hipotesis, y todas las justificaciones "
                "en prosa de mascara, que son texto sobre SSR y no parametros."
            ),
        },
        "calculado_no_almacenado": {
            "regla": (
                "El hash NO se escribe en la ficha. filtro.py lo calcula en cada "
                "ejecucion a partir del contenido."
            ),
            "motivo": (
                "Mismo criterio que "
                "ficha_congelada.hash_de_medida.calculado_no_almacenado: un hash "
                "derivado no puede mentir."
            ),
        },
        "ancla": {
            "regla": (
                "El valor de referencia se calcula sobre la ficha operativa del id "
                "ssr_capstables en el propio registro. NO se escribe como constante "
                "en la doctrina."
            ),
            "motivo": (
                "Una constante copiada puede derivar del contenido que dice resumir. "
                "La ficha de ssr_capstables esta dentro de la cadena de hashes y es "
                "inmutable."
            ),
            "valor_verificado_2026_09_07": HASH_PLANTILLA_ANCLA,
            "estabilidad_verificada": (
                "Las entradas 18, 20 y 21 producen el mismo hash de plantilla. El "
                "ancla es por tanto estable con independencia de la regla de "
                "resolucion aplicada, y confirma por hash la identidad de medida que "
                "la declaracion_de_sesgo de la entrada 20 afirmaba en prosa."
            ),
        },
        "comportamiento_filtro_py": (
            "Si el hash de plantilla de una ficha con repesca_de_id_v1 no coincide "
            "con el ancla, filtro.py ABORTA y nombra el campo concreto que difiere, "
            "no solo el hash."
        ),
        "no_activa_la_regla_de_colision": (
            "Este sub-hash NO participa en "
            "ficha_congelada.hash_de_medida.regla_de_colision. El hash_de_medida "
            "completo de una repesca siempre diferira del de ssr_capstables porque "
            "metrica_continua y casilla_dashboard difieren. Se declara expresamente "
            "para que las dos reglas no se lean como contradictorias."
        ),
        "consecuencia_asumida": (
            "La plantilla encajara mal en algunas variables. Encajar mal solo RESTA "
            "potencia, nunca la regala, y esa asimetria es lo que hace valida la "
            "eleccion de un ancla unica congelada sin conocer estos resultados."
        ),
    },
    "signo_esperado_bilateral": {
        "regla": "Toda ficha de repesca queda con signo_esperado = bilateral.",
        "naturaleza": (
            "No es una regla anadida. CAE de hash_de_plantilla: signo_esperado forma "
            "parte del subconjunto y la ficha de ssr_capstables es bilateral. Se "
            "hace constar por separado porque es la consecuencia con mas efecto y no "
            "debe descubrirse por accidente."
        ),
        "motivo_1_calibracion": (
            "Es la unica formula con calibracion medida en este proyecto. "
            "protocolo.test_de_permutacion.evidencia_de_calibracion: valor absoluto "
            "0.043 a nominal 0.05; cola segun signo observado 0.095; dos por cola "
            "menor 0.068. Las formulas unilaterales estan permitidas pero su tasa de "
            "error tipo I nunca se ha medido aqui."
        ),
        "motivo_2_texto_libre": (
            "ficha_congelada.signo_esperado.regla_unilateral exige rellenar "
            "justificacion_signo para declarar direccion. Bilateral no exige "
            "justificacion. Es unilateral, y no bilateral, el valor que abre un campo "
            "de texto libre contaminable por el conocimiento del signo v1."
        ),
        "motivo_3_sin_clase_penalizada": (
            "ssr_capstables, la unica variable jamas testeada bajo v2, es bilateral. "
            "Las repescas no reciben un trato mas duro que la unica variable "
            "ordinaria del registro: reciben el mismo."
        ),
        "coste_real_declarado": {
            "donde_cuesta": (
                "En el test de permutacion sobre bloque_2, unico punto del motor "
                "donde se lee signo_esperado (filtro.py, test_permutacion, invocada "
                "en la fase 5)."
            ),
            "donde_NO_cuesta": (
                "En la capa de gates. Ninguno de los cuatro gates lee "
                "signo_esperado. gates_cualitativos.parametros.magnitud_en_tramos."
                "exige_signo es false y coherencia_de_signo_en_tramos evalua "
                "consistencia entre tramos del bloque_1, no direccion declarada."
            ),
            "magnitud": (
                "NO MEDIDA. Se declara como hueco conocido, no se estima."
            ),
        },
    },
    "limites": {
        "una_por_id_v1": {
            "regla": (
                "filtro.py ABORTA si dos ids resueltos distintos apuntan al mismo "
                "valor de repesca_de_id_v1, y nombra ambos."
            ),
            "efecto": (
                "Cada negativo de v1 dispone de una oportunidad, no de una serie. Es "
                "el analogo verificable de unicidad_del_test dentro de esta via."
            ),
        },
        "una_por_lote": {
            "regla": (
                "filtro.py ABORTA si dos ids resueltos distintos del mismo lote "
                "llevan repesca_de_id_v1, y nombra ambos."
            ),
            "motivo": (
                "Con doce propuestas maximas por trimestre, sin este limite un lote "
                "entero podria ser una cohorte de repesca. La repesca se acordo "
                "individual, no por cohorte."
            ),
        },
        "sin_tope_numerico_arbitrario": {
            "regla": "No se fija un numero maximo total de repescas.",
            "motivo": (
                "El producto de los dos limites anteriores sobre una lista finita de "
                "nueve ids ya da un techo natural de nueve repescas a ritmo maximo "
                "de una por trimestre. Un numero inventado (tres, cinco) seria una "
                "constante sin justificacion, que es justo lo que el resto del "
                "protocolo evita."
            ),
            "descartado": (
                "Se evaluo un tercer limite, una repesca abierta a la vez. Rechazado "
                "por redundante con los dos anteriores y porque penalizaria la fase "
                "forward, que es la fase limpia."
            ),
        },
        "sin_presupuesto_paralelo": (
            "Una repesca consume plaza ordinaria del trimestre por el mecanismo "
            "normal de presupuesto.derivacion. No se crea contador propio, ni cuota "
            "reservada, ni clase privilegiada."
        ),
    },
    "verificaciones_de_filtro_py": {
        "regla": (
            "Todas se ejecutan cuando la ficha operativa de un id contiene "
            "repesca_de_id_v1. Ninguna constante nueva vive en el codigo: la lista de "
            "ids elegibles, el subconjunto de campos del hash de plantilla y el id "
            "del ancla se leen de esta seccion."
        ),
        "lista": [
            "a. repesca_de_id_v1 pertenece a ids_elegibles.lista. Si no, ABORTA.",
            "b. El id apuntado existe en el registro, es regimen v1, lote "
            "v1-historico y su estado operativo es RECHAZADA_PVALOR. Si no, ABORTA.",
            "c. declaracion_de_antecedente esta presente y no vacia. Si no, ABORTA.",
            "d. Ningun otro id resuelto apunta al mismo repesca_de_id_v1. Si lo hay, "
            "ABORTA nombrando ambos.",
            "e. Ningun otro id resuelto del mismo lote lleva repesca_de_id_v1. Si lo "
            "hay, ABORTA nombrando ambos.",
            "f. El hash de plantilla de la ficha coincide con el ancla calculado "
            "sobre la ficha operativa de ssr_capstables. Si no, ABORTA nombrando el "
            "campo que difiere.",
            "g. repesca_de_id_v1 no se usa en ningun punto para resolver ni plegar "
            "ids. Invariante de codigo, verificable en revision, mismo criterio que "
            "ficha_congelada.alcance.aislamiento_del_resolver.",
        ],
        "estado_de_implementacion": (
            "DECLARADO NO AUTOMATIZADO en el momento de esta enmienda. filtro.py no "
            "implementa todavia ninguna de las siete. Se anota junto a los huecos ya "
            "declarados del motor, con el mismo criterio que la enmienda 34 uso para "
            "su obligatoriedad condicional: se declara el hueco antes que suponerlo "
            "cerrado. Ninguna repesca puede escribirse hasta que esten "
            "implementadas."
        ),
    },
    "inventario_de_reincidencia": {
        "regla": (
            "filtro.py lista en cada informe todo id de ficha cuyo texto contenga "
            "como subcadena alguno de los nueve ids de ids_elegibles.lista y que NO "
            "declare repesca_de_id_v1."
        ),
        "sin_severidad": (
            "No es un error ni una advertencia y no lleva nivel de severidad. Es un "
            "inventario, no un diagnostico. Una coincidencia de subcadena puede ser "
            "casual."
        ),
        "no_bloquea": (
            "Nunca hace abortar a filtro.py ni condiciona ninguna transicion de "
            "estado."
        ),
        "debilidad_declarada": (
            "Es un control detectivo por coincidencia de cadena. Un id renombrado lo "
            "evade por completo. NO cierra elusion_conocida y no debe leerse como si "
            "lo hiciera: la deteccion de equivalencia conceptual sigue fuera del "
            "enforcement automatico, segun ficha_congelada.retirada_en_propuesta."
            "reproposicion.una_sola_vez.alcance_real."
        ),
        "precedente_interno": (
            "Mismo patron y mismo alcance parcial que ficha_congelada.alcance."
            "prohibicion_de_referencias.inventario_de_referencias."
        ),
    },
    "declaracion_obligatoria": {
        "estado": "OBLIGATORIO_EN_INFORME",
        "regla": (
            "Todo informe que mencione una repesca imprime literalmente este texto, "
            "ademas de meta.declaracion_obligatoria y de potencia_medida."
            "texto_literal, que siguen siendo obligatorios por meta.regla_de_impresion."
        ),
        "texto_literal": (
            "Esta variable es una repesca del regimen v1. Su cribado se ejecuto con "
            "el antecedente v1 CONOCIDO por el autor, por lo que la fase de gates no "
            "debe leerse como un filtro ciego. La garantia frente a esa contaminacion "
            "no la aporta el cribado sino la confirmacion forward sobre cinco "
            "trimestres de datos que no existian cuando la ficha fue congelada. "
            "Ademas, la capa de gates detecta aproximadamente el 39 por ciento de un "
            "efecto real de theta=0.084 y deja pasar el 15 por ciento del ruido puro: "
            "una repesca sera probablemente descartada aunque tuviera senal real. Eso "
            "no es injusticia ni evidencia de ausencia de efecto, es el limite del "
            "sistema, y afecta igual a las variables nuevas."
        ),
    },
    "asimetria_halving_ciclo": {
        "que_se_resuelve": (
            "Desaparece el privilegio de que un resultado v1 negativo fuera "
            "definitivo mientras un resultado v1 positivo se conservaba con valor "
            "operativo. Ya no hay una clase congelada y otra viva."
        ),
        "que_NO_se_resuelve": (
            "halving_ciclo sigue sin ruta, ni hacia CONFIRMADA ni hacia la "
            "invalidacion. Los negativos ganan una ruta que el positivo no tiene."
        ),
        "por_que_debe_seguir_asi": (
            "El argumento que abre la repesca es que el filtro v1 era MAS LAXO. Ese "
            "argumento justifica reexaminar a quien no supero un filtro sesgado a su "
            "favor. NO justifica re-testear al que lo supero: re-testear un positivo "
            "hasta que falle es el mismo abuso en espejo. Mantener "
            "sellados[0].re_test_permitido = false es coherencia, no privilegio."
        ),
        "cabo_suelto_cerrado": (
            "La advertencia de que halving_ciclo es valor operativo y no evidencia "
            "validada bajo v2 ya vive en sellados[0].nota_de_sesgo. halving.py fue "
            "corregido el 2026-09-07 para cumplir la regla_derivada de la enmienda 17 "
            "al citar el rango de p."
        ),
    },
    "cabo_suelto_declarado": {
        "descripcion": (
            "Si una repesca alcanzase CONFIRMADA, el panel mostraria dos hallazgos de "
            "RANGO PROBATORIO distinto: uno confirmado bajo v2 sobre datos futuros y "
            "otro sellado bajo v1. Ninguna clausula obliga hoy al panel a mostrar esa "
            "diferencia."
        ),
        "no_cubierto_por": (
            "notas_de_migracion.theta_v1_no_comparable prohibe comparar MAGNITUDES "
            "entre regimenes. No dice nada sobre el rango probatorio en la interfaz."
        ),
        "se_declara_no_se_resuelve": (
            "Legislar aqui sobre un caso que aun no existe seria escribir la regla "
            "mientras un caso la espera, que es lo que la enmienda 35 parte 5 decidio "
            "expresamente no hacer. Se deja constancia para que no se descubra como "
            "sorpresa."
        ),
    },
    "consulta_externa": {
        "fecha": "2026-09-07",
        "modelos": 4,
        "resultado_gobernanza": (
            "Cuatro de cinco lecturas limpias a favor de declarar la excepcion en la "
            "lista en lugar de documentarla aparte. La discrepancia unica era "
            "internamente contradictoria: argumentaba que la via alternativa es una "
            "trampa semantica real y a continuacion la recomendaba."
        ),
        "defecto_de_la_consulta_de_potencia": {
            "hecho": (
                "Las cuatro respuestas calcularon la penalizacion de potencia de "
                "unilateral a bilateral SOBRE la cifra del 39 por ciento de "
                "potencia_medida."
            ),
            "por_que_es_erroneo": (
                "El 39 por ciento es una cifra de la capa de gates sobre bloque_1, y "
                "ninguno de los cuatro gates lee signo_esperado. La convencion de "
                "cola solo interviene en el test de permutacion sobre bloque_2. "
                "Verificado en filtro.py el 2026-09-07."
            ),
            "responsabilidad": (
                "El error es del prompt, no de los modelos: presentaba ambas cosas en "
                "el mismo bloque sin distinguir la capa a la que pertenece cada una."
            ),
            "consecuencia": (
                "Los argumentos de gobernanza de esa consulta son validos. Las cifras "
                "de potencia son inservibles y no pueden citarse como si hubieran "
                "validado nada."
            ),
            "propuestas_rechazadas": {
                "endurecer_fase_2_para_repescas": (
                    "Propuesta por tres de los cuatro modelos (4 de 5 trimestres, "
                    "magnitud 70 por ciento). Rechazada: confirmacion_forward es "
                    "inmutable, crearia una clase con trato diferenciado que es justo "
                    "lo excluido, y confirmacion_forward._motivo_modificacion "
                    "documenta que la evaluacion endurecida por trimestre se rechazo "
                    "tras medir tasas de falso descarte del 41 al 94 por ciento."
                ),
                "anclaje_documental_anterior_a_v1": (
                    "Propuesta por dos modelos para permitir unilateral. Innecesaria "
                    "al caer bilateral de la plantilla, y no verificable por codigo."
                ),
                "cegamiento_con_tercero": (
                    "Propuesta por un modelo, que admite en la misma respuesta que ya "
                    "es tarde: el resultado v1 esta en la memoria del autor."
                ),
            },
        },
    },
    "naturaleza": (
        "Anade una excepcion acotada y cerrada. No altera ningun gate, umbral, "
        "mascara, particion ni criterio estadistico. No modifica ninguna entrada del "
        "registro. Aplicacion prospectiva."
    ),
    "momento": (
        "Escrita con el lote 2026-Q3 cerrado, sin ningun test pendiente ni ningun "
        "resultado que se pueda contaminar, y sin ninguna variable en CONFIRMADA. Es "
        "la unica ventana en que abrir esta via no admite sospecha de haberla "
        "ajustado a un caso concreto."
    ),
    "prohibicion_de_caso_a_medida": (
        "Ninguna variable estaba elegida cuando se escribio esta enmienda. La primera "
        "repesca la elige Rafa DESPUES de que este texto quede encadenado. Escribir la "
        "regla con un caso esperando la habria convertido en una autorizacion a "
        "medida, que es el defecto que la enmienda 35 parte 5 evito expresamente."
    ),
}


# ---------------------------------------------------------------------------
# EJECUCION
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", required=True)
    ap.add_argument("--registro", required=True)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--solo-comprobar", action="store_true")
    args = ap.parse_args()

    print("=" * 70)
    print("ENMIENDA 36 — repesca individual de variables del regimen v1")
    print("=" * 70)

    # --- 1. Verificacion de hashes de origen -------------------------------
    h_v2 = sha256_fichero(args.v2)
    h_reg = sha256_fichero(args.registro)
    print(f"\n[1] SHA-256 de origen")
    print(f"    v2.json       {h_v2}")
    print(f"    registro.json {h_reg}")
    if h_v2 != SHA256_V2_ORIGEN:
        abortar(f"v2.json no coincide. Esperado {SHA256_V2_ORIGEN}")
    if h_reg != SHA256_REGISTRO:
        abortar(f"registro.json no coincide. Esperado {SHA256_REGISTRO}")
    print("    OK — ambos coinciden con el estado verificado 2026-09-07")

    with open(args.v2, encoding="utf-8") as fh:
        v2 = json.load(fh)
    with open(args.registro, encoding="utf-8") as fh:
        registro = json.load(fh)

    # --- 2. Estado esperado de la doctrina ---------------------------------
    print(f"\n[2] Estado de la doctrina")
    ver = v2["meta"]["version_esquema"]
    n_enm = len(v2["meta"]["enmiendas"])
    print(f"    version_esquema {ver}   enmiendas {n_enm}")
    if ver != VERSION_ORIGEN:
        abortar(f"version_esquema es {ver}, se esperaba {VERSION_ORIGEN}")
    if n_enm != ENMIENDAS_ORIGEN:
        abortar(f"hay {n_enm} enmiendas, se esperaban {ENMIENDAS_ORIGEN}")
    if any(e.get("n") == ENMIENDA_NUEVA for e in v2["meta"]["enmiendas"]):
        abortar("la enmienda 36 ya figura en meta.enmiendas")
    if "repesca_v1" in v2:
        abortar("la clave repesca_v1 ya existe en v2.json")

    unicidad = v2["protocolo"]["unicidad_del_test"]
    if unicidad.get("excepciones") != []:
        abortar(
            "unicidad_del_test.excepciones no esta vacia. La enmienda 36 escribe la "
            f"PRIMERA entrada. Contenido actual: {unicidad.get('excepciones')}"
        )
    if unicidad.get("nota") != TEXTO_NOTA_ANTERIOR:
        abortar(
            "unicidad_del_test.nota no tiene el texto esperado. No se sustituye un "
            "texto que no es el que se creia estar sustituyendo."
        )
    if unicidad.get("re_test_permitido") is not False:
        abortar("unicidad_del_test.re_test_permitido no es false")
    print("    OK — excepciones vacia, nota literal coincide, re_test_permitido false")

    # --- 3. Ancla de plantilla, calculada del registro ---------------------
    print(f"\n[3] Ancla de plantilla de medida ({ID_ANCLA})")
    ficha = ficha_operativa(registro, ID_ANCLA)
    if ficha is None:
        abortar(f"no se encuentra ficha operativa de {ID_ANCLA} en el registro")
    h_plant, n_campos, sub = hash_de_plantilla(ficha)
    print(f"    tipo_entrada usada: {ficha.get('tipo_entrada')}")
    print(f"    campos en el subconjunto: {n_campos}")
    print(f"    hash calculado: {h_plant}")
    if n_campos != 12:
        abortar(f"el subconjunto tiene {n_campos} campos, se esperaban 12")
    if h_plant != HASH_PLANTILLA_ANCLA:
        abortar(
            f"el ancla calculada no coincide con la verificada.\n"
            f"  calculada: {h_plant}\n  esperada:  {HASH_PLANTILLA_ANCLA}"
        )
    if sub.get("signo_esperado") != "bilateral":
        abortar(
            f"la ficha ancla declara signo_esperado='{sub.get('signo_esperado')}'. "
            "La enmienda afirma que bilateral CAE de la plantilla; si el ancla no es "
            "bilateral esa afirmacion es falsa."
        )
    print("    OK — coincide con el valor verificado, y el ancla es bilateral")

    # --- 4. Ids elegibles verificados contra el registro -------------------
    print(f"\n[4] Ids elegibles ({len(IDS_ELEGIBLES)})")
    estados = {}
    for e in registro["entradas"]:
        vid = e.get("id")
        if vid:
            estados[vid] = e
    for vid in IDS_ELEGIBLES:
        e = estados.get(vid)
        if e is None:
            abortar(f"el id elegible '{vid}' no existe en el registro")
        if e.get("estado") != "RECHAZADA_PVALOR":
            abortar(f"'{vid}' tiene estado {e.get('estado')}, se esperaba RECHAZADA_PVALOR")
        if e.get("lote") != "v1-historico":
            abortar(f"'{vid}' tiene lote {e.get('lote')}, se esperaba v1-historico")
    print("    OK — los nueve existen, RECHAZADA_PVALOR, lote v1-historico")

    if args.solo_comprobar:
        print("\n--solo-comprobar: verificaciones superadas. No se escribe nada.\n")
        return

    if not args.salida:
        abortar("falta --salida (o usa --solo-comprobar)")

    # --- 5. Aplicacion -----------------------------------------------------
    print(f"\n[5] Aplicando la enmienda")

    v2["meta"]["version_esquema"] = VERSION_DESTINO
    v2["meta"]["enmiendas"].append(ENTRADA_META)
    print(f"    meta.version_esquema  {VERSION_ORIGEN} -> {VERSION_DESTINO}")
    print(f"    meta.enmiendas        {ENMIENDAS_ORIGEN} -> {len(v2['meta']['enmiendas'])}")

    unicidad["excepciones"] = [EXCEPCION_UNICIDAD]
    unicidad["_texto_sustituido_enmienda_36"] = TEXTO_NOTA_ANTERIOR
    unicidad["_motivo_de_la_sustitucion_enmienda_36"] = MOTIVO_SUSTITUCION
    unicidad["nota"] = NOTA_NUEVA
    unicidad["_nota_re_test_permitido_enmienda_36"] = NOTA_RE_TEST
    print("    unicidad_del_test.excepciones  [] -> 1 entrada (repesca_v1)")
    print("    unicidad_del_test.nota         sustituida, texto anterior conservado")

    v2["repesca_v1"] = REPESCA_V1
    print("    repesca_v1  seccion nueva de primer nivel")

    salida = json.dumps(v2, indent=1, ensure_ascii=False) + "\n"
    with open(args.salida, "w", encoding="utf-8") as fh:
        fh.write(salida)

    h_nuevo = hashlib.sha256(salida.encode("utf-8")).hexdigest()
    print(f"\n[6] Escrito: {args.salida}")
    print(f"    SHA-256 nuevo: {h_nuevo}")
    print("\n" + "=" * 70)
    print("ENMIENDA 36 APLICADA. registro.json NO se ha tocado.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
