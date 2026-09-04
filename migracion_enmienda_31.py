"""
migracion_enmienda_31.py — Script de UN SOLO USO.

Aplica la enmienda 31 a v2.json. No toca registro.json.

Verificaciones previas obligatorias:
  - SHA-256 de v2.json de partida
  - version_esquema 2.4.0
  - la lista literal campos_de_definicion_de_medida coincide EXACTAMENTE con
    la que filtro.py deriva hoy parseando el texto en prosa

Uso:
    python migracion_enmienda_31.py v2.json
"""

import hashlib
import json
import sys

SHA_ESPERADO = "ca49c1b93ce6c5e2586e34a176f00fc1bb29c8c6c86df84c4b4aca5842d7e1be"
VERSION_ORIGEN = "2.4.0"
VERSION_DESTINO = "2.5.0"
FECHA_EFECTO = "2026-09-05"

CAMPOS_MEDIDA = [
    "metrica_continua",
    "mascara",
    "horizonte_N",
    "M",
    "unidad_theta",
    "signo_esperado",
    "casilla_dashboard",
    "naturaleza_de_la_hipotesis",
    "dias_episodio",
]


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ruta = argv[1]

    sha_ini = sha256_fichero(ruta)
    if sha_ini != SHA_ESPERADO:
        print(f"ABORTA: SHA-256 de partida {sha_ini} != {SHA_ESPERADO}")
        return 1

    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)

    if doc["meta"]["version_esquema"] != VERSION_ORIGEN:
        print("ABORTA: version_esquema de partida inesperada")
        return 1

    # --- Comprobacion critica: la codificacion no cambia contenido ---------
    texto = doc["ficha_congelada"]["migracion_de_fichas"]["limite_de_la_sustitucion"]
    derivada = [c.strip() for c in texto.split("(")[1].split(")")[0].split(",")]
    if derivada != CAMPOS_MEDIDA:
        print("ABORTA: la lista literal NO coincide con la derivada del texto")
        print(f"  derivada: {derivada}")
        print(f"  literal : {CAMPOS_MEDIDA}")
        return 1
    print("OK  la lista literal coincide con la derivada del parseo actual")

    fc = doc["ficha_congelada"]

    # --- A) Lista canonica de campos de definicion de medida ---------------
    if "campos_de_definicion_de_medida" in fc:
        print("ABORTA: campos_de_definicion_de_medida ya existe")
        return 1
    fc["campos_de_definicion_de_medida"] = {
        "enmienda": 31,
        "naturaleza": "codificacion, no cambio de contenido",
        "lista": CAMPOS_MEDIDA,
        "regla": (
            "Esta lista es la unica fuente de verdad sobre que campos de una ficha "
            "son de definicion de medida. La usan migracion_de_fichas."
            "limite_de_la_sustitucion y marcadores_pendientes.prohibicion_prospectiva."
        ),
        "motivo": (
            "filtro.py derivaba la lista partiendo el texto en prosa de "
            "limite_de_la_sustitucion por el primer parentesis. Una reescritura "
            "del parrafo cambiaba en silencio el alcance de una prohibicion. "
            "Verificado por el script de migracion: la lista literal es identica "
            "a la que ese parseo produce."
        ),
        "comportamiento_filtro_py": (
            "Se lee esta lista. Queda prohibido derivar la lista de ningun texto "
            "en prosa."
        ),
        "no_cambia_el_limite_de_la_sustitucion": (
            "El texto de limite_de_la_sustitucion se conserva intacto como "
            "justificacion. Deja de ser la fuente de la que el codigo extrae la "
            "lista."
        ),
    }

    # --- B) Prohibicion prospectiva de marcadores en campos de medida ------
    mp = fc["marcadores_pendientes"]
    if "prohibicion_prospectiva" in mp:
        print("ABORTA: prohibicion_prospectiva ya existe")
        return 1
    mp["prohibicion_prospectiva"] = {
        "enmienda": 31,
        "fecha_efecto": FECHA_EFECTO,
        "prospectiva": True,
        "regla": (
            "Ninguna entrada con tipo_entrada propuesta, ficha_congelada o "
            "alta_retroactiva y fecha_registro igual o posterior a fecha_efecto "
            "puede contener una cadena que empiece por el prefijo dentro de un "
            "campo de campos_de_definicion_de_medida, a cualquier profundidad."
        ),
        "momento_de_la_comprobacion": (
            "antes de escribir la entrada en el registro, no en la transicion a "
            "EN_TEST"
        ),
        "implementacion": {
            "validacion_previa": (
                "filtro.py --validar-entrada FICHERO.json comprueba una entrada "
                "candidata contra esta regla y devuelve codigo de salida distinto "
                "de cero si la incumple. Debe ejecutarse antes de cadena.anadir."
            ),
            "red_de_seguridad": (
                "Si una entrada infractora llegase al registro, filtro.py ABORTA "
                "en fase 1 nombrando entrada y campo. No es un bloqueo por "
                "variable: es un defecto estructural del registro y ningun lote "
                "puede ejecutarse."
            ),
            "por_que_no_en_cadena_py": (
                "cadena.py declara en su cabecera que no contiene ninguna regla "
                "del protocolo, solo la aritmetica de hashes. Meter aqui una "
                "regla doctrinal rompe esa separacion y crea un segundo lugar "
                "donde vive la doctrina. La combinacion de validacion previa mas "
                "aborto global tiene la misma fuerza practica sin ese coste."
            ),
        },
        "diferencia_con_la_regla_general": (
            "marcadores_pendientes sigue vigente sin cambios: cubre todos los "
            "campos a cualquier profundidad y bloquea la transicion a EN_TEST. "
            "Esta clausula es mas estrecha en alcance de campos y mas dura en "
            "consecuencia."
        ),
        "no_retroactiva": (
            "Las entradas anteriores a fecha_efecto no se reevaluan ni se editan. "
            "El registro es append-only. La entrada 18 (fecha_registro "
            "2026-09-04) queda expresamente fuera."
        ),
        "justificacion": (
            "Una fuente de datos no es un metadato: es parte de la definicion de "
            "la medida. Firmar una ficha con la fuente sin definir crea una "
            "variable que nace sin salida dentro de la doctrina, porque "
            "limite_de_la_sustitucion prohibe despues corregir ese mismo campo. "
            "El caso SSR es el sintoma; el agujero es general. Consenso unanime "
            "de las cuatro revisiones externas del 2026-09-04."
        ),
    }

    # --- C) Estado terminal nuevo -----------------------------------------
    lista = doc["estados"]["lista"]
    if any(e["id"] == "RETIRADA_EN_PROPUESTA" for e in lista):
        print("ABORTA: el estado ya existe")
        return 1
    lista.append({
        "id": "RETIRADA_EN_PROPUESTA",
        "descripcion": (
            "Variable retirada antes de testearse, por decision documentada. "
            "No es un resultado de test."
        ),
        "alta": FECHA_EFECTO,
        "enmienda": 31,
        "terminal": True,
        "consume_presupuesto": False,
        "admisible_a_EN_TEST": False,
        "declaracion_obligatoria": (
            "Este estado NO expresa ningun juicio sobre la variable. No es "
            "evidencia de ausencia de efecto, no es un resultado de test y no "
            "puede citarse como tal en ningun informe. No abre ninguna excepcion "
            "a protocolo.unicidad_del_test: ese protocolo gobierna tests "
            "ejecutados, y aqui no se ejecuto ninguno."
        ),
        "nota_excepcion_a_estados_cerrado": (
            "Segunda excepcion documentada a estados.cerrado, tras NULO_V1 "
            "(enmienda 9). Se anade antes de ejecutar ningun lote v2."
        ),
    })

    # --- D) Reglas de la retirada -----------------------------------------
    if "retirada_en_propuesta" in fc:
        print("ABORTA: retirada_en_propuesta ya existe")
        return 1
    fc["retirada_en_propuesta"] = {
        "enmienda": 31,
        "condiciones_estrictas": {
            "nunca_alcanzo_EN_TEST": (
                "Ninguna entrada del id puede haber tenido estado EN_TEST ni "
                "ningun estado de presupuesto.derivacion."
                "estados_que_cuentan_como_consumido. filtro.py aborta si lo "
                "encuentra."
            ),
            "sin_datos_adquiridos": (
                "No puede existir ningun snapshot de datos asociado al id, ni "
                "hash de snapshot, ni theta_B2 distinto de null. filtro.py "
                "aborta si theta_B2 no es null."
            ),
            "estado_actual_PROPUESTA": (
                "La entrada operativa del id debe estar en PROPUESTA en el "
                "momento de la retirada."
            ),
        },
        "forma": {
            "tipo_entrada": "transicion_de_estado",
            "campos_obligatorios_adicionales": ["motivo", "declaracion"],
            "prohibido": (
                "No puede modificar ningun campo de la ficha. Rigen los "
                "campos_permitidos de integridad.resolucion_de_entradas."
                "tipo_entrada.alta_transicion_de_estado mas los dos anteriores."
            ),
        },
        "terminalidad": (
            "Ninguna entrada posterior con el mismo id puede cambiar el estado. "
            "filtro.py aborta. El id queda muerto de forma permanente."
        ),
        "reproposicion": {
            "permitida": True,
            "condicion": (
                "Solo mediante una ficha NUEVA con id distinto, que no resuelva "
                "al id retirado por el mecanismo de excepciones de la "
                "enmienda 28."
            ),
            "campo_obligatorio": "sustituye_a_id_retirado",
            "prohibicion_de_forma": (
                "La ficha nueva NO puede usar referencia_entrada_anterior "
                "apuntando al id retirado: eso la plegaria sobre el id muerto al "
                "resolver ids. sustituye_a_id_retirado es trazabilidad, no "
                "resolucion, y filtro.py nunca lo usa para plegar ids."
            ),
            "verificacion": (
                "filtro.py aborta si sustituye_a_id_retirado apunta a un id que "
                "no esta en RETIRADA_EN_PROPUESTA."
            ),
            "declaracion_de_sesgo_obligatoria": (
                "La ficha nueva debe declarar en declaracion_de_sesgo que campos "
                "de medida difieren de la retirada y por que. Sin ese campo "
                "filtro.py aborta."
            ),
            "una_sola_vez": {
                "regla": (
                    "Una ficha que lleve sustituye_a_id_retirado no puede a su "
                    "vez ser retirada. filtro.py aborta si una transicion a "
                    "RETIRADA_EN_PROPUESTA apunta a un id cuya ficha contiene "
                    "ese campo."
                ),
                "efecto": (
                    "Cada variable subyacente dispone de una sola correccion. "
                    "Cierra el bucle retirar-reproponer-retirar sin castigar el "
                    "error honesto de una vez."
                ),
                "descartado": (
                    "Hacer que la retirada consuma presupuesto del trimestre. "
                    "Rechazado: castiga corregir un error, que es el incentivo "
                    "contrario al que persigue el protocolo."
                ),
            },
        },
        "coste_asumido_declarado": (
            "Retirar y reproponer es la unica via legitima de corregir un campo "
            "de medida en PROPUESTA, y por tanto tambien una puerta trasera "
            "potencial a limite_de_la_sustitucion. No se cierra con una "
            "prohibicion sino con dos frenos verificables: visibilidad "
            "obligatoria (retirada, motivo, id sucesor y declaracion de sesgo en "
            "la cadena de hashes y en cada informe) y el limite de una sola vez."
        ),
    }

    # --- E) Nota en unicidad_del_test -------------------------------------
    u = doc["protocolo"]["unicidad_del_test"]
    if "nota_retirada_en_propuesta" in u:
        print("ABORTA: la nota ya existe")
        return 1
    if u["excepciones"] != []:
        print("ABORTA: unicidad_del_test.excepciones ya no esta vacia")
        return 1
    u["nota_retirada_en_propuesta"] = (
        "RETIRADA_EN_PROPUESTA no es una excepcion a esta regla. Una variable "
        "retirada antes de EN_TEST no fue testeada, luego reproponerla no es un "
        "re-test. La lista excepciones permanece vacia."
    )

    # --- F) Version --------------------------------------------------------
    doc["meta"]["version_esquema"] = VERSION_DESTINO

    salida = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(salida)

    print(f"OK  enmienda 31 aplicada. version_esquema {VERSION_DESTINO}")
    print(f"OK  SHA-256 nuevo: {sha256_fichero(ruta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
