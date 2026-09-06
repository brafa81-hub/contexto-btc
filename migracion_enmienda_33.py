"""
migracion_enmienda_33.py — script de un solo uso.

ENMIENDA 33: elegibilidad de EN_TEST para ejecucion, campos estructurados en
la entrada de transicion, y los controles que la doctrina prometia y el motor
no ejecutaba.

Origen: contradiccion detectada el 2026-09-06 al preparar la ejecucion del
lote 2026-Q3, y consulta a cinco modelos externos sobre como resolverla.

Naturaleza del cambio: SOLO ANADE. No reescribe ningun texto existente, no
altera ningun gate, umbral, mascara, particion ni criterio estadistico. La
unica modificacion de un valor previo es meta.version_esquema y la extension
de una lista de campos permitidos.

Verifica el SHA-256 de v2.json antes de tocar nada.
"""

import hashlib
import json
import sys

SHA_ESPERADO = "024cab9cf4f3c38de579aa279c4928f587aa5202865b290effa207c35dbb8cd5"
RUTA = "v2.json"
FECHA = "2026-09-06"


def sha256_fichero(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    real = sha256_fichero(RUTA)
    if real != SHA_ESPERADO:
        print(f"ABORTA: {RUTA} no coincide.\n  esperado {SHA_ESPERADO}\n  leido    {real}")
        return 1

    with open(RUTA, encoding="utf-8") as f:
        d = json.load(f)

    if d["meta"]["version_esquema"] != "2.6.0":
        print("ABORTA: version_esquema no es 2.6.0")
        return 1

    # ---------------------------------------------------------------- parte 1
    # Indice de enmiendas incompleto. Las enmiendas 31 y 32 estan aplicadas en
    # el cuerpo del fichero pero no figuran en meta.enmiendas, que termina en la
    # 30. Se dan de alta con titulo derivado de las clausulas que las citan.
    ns = [e["n"] for e in d["meta"]["enmiendas"]]
    if ns[-1] != 30 or 31 in ns or 32 in ns:
        print("ABORTA: el indice de enmiendas no esta en el estado esperado")
        return 1

    d["meta"]["enmiendas"] += [
        {
            "n": 31,
            "titulo": "retirada en propuesta, prohibicion prospectiva de marcadores "
                      "PENDIENTE_ y lista literal de campos de definicion de medida",
            "fecha": "2026-09-05",
            "alta_en_el_indice": "enmienda 33",
            "nota_indice": "La enmienda se aplico en el cuerpo del fichero "
                           "(estados.lista RETIRADA_EN_PROPUESTA, "
                           "ficha_congelada.marcadores_pendientes.prohibicion_prospectiva, "
                           "ficha_congelada.campos_de_definicion_de_medida y "
                           "ficha_congelada.retirada_en_propuesta) pero no se anadio a "
                           "este indice. Se da de alta ahora sin reescribir ninguna de "
                           "esas clausulas. El titulo se deriva de ellas, no se inventa.",
        },
        {
            "n": 32,
            "titulo": "hash de medida calculado y no almacenado, alcance real de la "
                      "unicidad y declaracion de la retirada estrategica",
            "fecha": "2026-09-05",
            "alta_en_el_indice": "enmienda 33",
            "nota_indice": "Mismo caso que la 31. Clausulas afectadas: "
                           "ficha_congelada.hash_de_medida, "
                           "ficha_congelada.retirada_en_propuesta.reproposicion."
                           "una_sola_vez.alcance_real y "
                           "ficha_congelada.retirada_en_propuesta.retirada_estrategica.",
        },
        {
            "n": 33,
            "titulo": "elegibilidad de EN_TEST para ejecucion, campos estructurados "
                      "en la entrada de transicion y controles prometidos no ejecutados",
            "fecha": FECHA,
            "motivo": "Al preparar la primera ejecucion real del lote 2026-Q3 se "
                      "midio que el orden que la doctrina prescribe era inejecutable. "
                      "La doctrina exige escribir la transicion a EN_TEST antes de "
                      "ejecutar ningun gate, pero filtro.py solo admitia a ejecucion "
                      "variables en estado PROPUESTA: escrita la transicion, el motor "
                      "reportaba cero candidatas y terminaba sin ejecutar nada y sin "
                      "abortar. Ademas, la ficha de ssr_capstables declara que el "
                      "sha256 del snapshot se registra en la entrada de transicion, "
                      "pero la lista cerrada de esa entrada no contenia ningun campo "
                      "donde escribirlo.",
            "origen_externo": "Cinco revisiones externas independientes el 2026-09-06. "
                              "Unanimidad en dos puntos: no usar el campo motivo como "
                              "contenedor de datos estructurados, y enmendar antes de "
                              "ejecutar en lugar de elegir entre parches. Cuatro de "
                              "cinco rechazaron ejecutar contra una copia previa del "
                              "registro. Cuatro de cinco senalaron que fijar "
                              "fecha_corte_bloques en una entrada de aclaracion es "
                              "reinterpretacion mientras la doctrina lo asigne a la "
                              "transicion.",
            "naturaleza": "Solo anade. No reescribe ningun texto previo. No altera "
                          "ningun gate, umbral, mascara, particion ni criterio "
                          "estadistico. Una enmienda escrita antes del test que "
                          "relajase cualquiera de esas cosas no seria una enmienda "
                          "sino una propuesta nueva.",
            "momento": "Encadenada antes de que exista ningun resultado del test de "
                       "ssr_capstables. Escrita despues, no valdria nada.",
            "partes": [
                "1. Alta en el indice de las enmiendas 31 y 32, aplicadas en el "
                "cuerpo y ausentes de meta.enmiendas.",
                "2. estados.elegibilidad_para_ejecucion: el motor admite PROPUESTA o "
                "EN_TEST sin gate_alcanzado, y aborta si termina sin ejecutar una "
                "variable que estaba en ese segundo caso.",
                "3. integridad.resolucion_de_entradas.ficha_operativa: la ficha es la "
                "ultima entrada que no sea de tipo transicion_de_estado. El estado lo "
                "sigue fijando la ultima entrada.",
                "4. Dos campos nuevos en la lista cerrada de la entrada de transicion, "
                "y prohibicion expresa de usar motivo como contenedor de datos.",
                "5. Implementacion de dos controles que la doctrina afirmaba y el "
                "motor no ejecutaba: campos extra en una transicion, y coincidencia "
                "entre la fecha de corte derivada y la registrada. El primero se "
                "aplica de forma prospectiva y destapo un defecto preexistente en la "
                "entrada 19, que queda declarado y no se puede corregir.",
            ],
        },
    ]

    # ---------------------------------------------------------------- parte 2
    if "elegibilidad_para_ejecucion" in d["estados"]:
        print("ABORTA: estados.elegibilidad_para_ejecucion ya existe")
        return 1

    d["estados"]["elegibilidad_para_ejecucion"] = {
        "enmienda": 33,
        "regla": "El motor admite a ejecucion de gates una variable cuyo estado sea "
                 "PROPUESTA, o EN_TEST con gate_alcanzado ausente o nulo. El segundo "
                 "caso es exactamente la variable cuya entrada de transicion ya esta "
                 "escrita y cuyo test todavia no se ha ejecutado.",
        "motivo": "integridad.resolucion_de_entradas.inmutabilidad.fecha_corte_bloques "
                  "exige escribir la transicion antes de ejecutar ningun gate. Con la "
                  "regla anterior de elegibilidad ese orden era inejecutable.",
        "comportamiento_si_no_se_ejecuta": "Si un lote contiene una variable en EN_TEST "
                                           "sin gate_alcanzado y el motor termina sin "
                                           "haberla ejecutado, aborta. Un fallo de "
                                           "gobernanza que termina en silencio es peor "
                                           "que uno que bloquea: puede confundirse con "
                                           "una ejecucion correcta sin senal.",
        "no_relaja_nada": "Esta clausula no toca ningun gate, umbral, mascara, "
                          "particion ni criterio estadistico. Solo hace ejecutable el "
                          "orden que la doctrina ya prescribia.",
        "presupuesto": "El consumo sigue rigiendose por presupuesto.nota_consumo: se "
                       "consume al asignar EN_TEST, es decir al escribir la transicion, "
                       "que ahora es anterior a la ejecucion. Cierra de paso la via de "
                       "ejecutar sin consumir cuota.",
    }

    # ---------------------------------------------------------------- parte 3
    re_ = d["integridad"]["resolucion_de_entradas"]
    if "ficha_operativa" in re_:
        print("ABORTA: ficha_operativa ya existe")
        return 1

    re_["ficha_operativa"] = {
        "enmienda": 33,
        "regla": "La ficha operativa de una variable es la ultima entrada de su id que "
                 "NO sea de tipo transicion_de_estado. El estado lo sigue fijando la "
                 "ultima entrada, sea del tipo que sea.",
        "motivo": "El motor tomaba la ultima entrada como ficha. Escrita una transicion "
                  "a EN_TEST, que por su lista cerrada no lleva ningun campo de ficha, "
                  "la variable se quedaba sin mascara, sin horizonte y sin fecha de fin "
                  "de ventana. La doctrina ya distinguia las dos cosas: el estado gana "
                  "la ultima, la ficha es inmutable.",
        "alcance": "No cambia cual es la ficha en ninguna variable ya registrada: a "
                   "fecha de esta enmienda no existe ninguna entrada de tipo "
                   "transicion_de_estado en el registro.",
        "no_debilita_la_inmutabilidad": "Sigue vigente que la ficha solo puede "
                                        "sustituirse en estado PROPUESTA y que queda "
                                        "inmutable al alcanzar EN_TEST. Esta clausula "
                                        "dice cual es la ficha, no permite cambiarla.",
    }

    # ---------------------------------------------------------------- parte 4
    tr = re_["tipo_entrada"]["alta_transicion_de_estado"]
    if "sha256_snapshot_metrica" in tr["campos_permitidos"]:
        print("ABORTA: los campos nuevos ya estan en la lista")
        return 1

    tr["campos_permitidos"] = [
        "id",
        "tipo_entrada",
        "estado",
        "fecha_registro",
        "gate_alcanzado",
        "fecha_corte_bloques",
        "sha256_snapshot_metrica",
        "declaraciones_de_ejecucion",
        "motivo",
        "hash_anterior",
        "hash",
    ]
    tr["ampliacion_enmienda_33"] = {
        "campos_anadidos": ["sha256_snapshot_metrica", "declaraciones_de_ejecucion"],
        "motivo": "La ficha de ssr_capstables declara que el sha256 del snapshot se "
                  "registra en la entrada de transicion, pero no habia campo donde "
                  "escribirlo. La unica alternativa era esconderlo dentro de motivo.",
        "prohibicion_expresa_del_campo_motivo": "motivo es texto libre para explicar "
            "una decision. Queda prohibido usarlo como contenedor de datos "
            "estructurados: hashes, fechas, listas, tablas o declaraciones que otro "
            "campo deberia albergar. Si un dato necesita quedar registrado y no tiene "
            "campo, se amplia la lista cerrada por enmienda. Esconderlo en un campo de "
            "texto preserva la forma de la lista y vacia su funcion, que es que una "
            "entrada sea verificable por maquina y no por lectura humana.",
        "declaraciones_de_ejecucion": {
            "naturaleza": "Objeto documental. Recoge lo que hubo que decidir o medir "
                          "para poder ejecutar, y que no pertenece a la definicion de "
                          "la medida.",
            "no_es_campo_de_medida": "No figura en "
                                     "ficha_congelada.campos_de_definicion_de_medida.lista, "
                                     "no participa en hash_de_medida y no condiciona "
                                     "ninguna transicion de estado.",
            "prohibicion": "No puede contener ninguna clave que coincida con un campo "
                           "de la ficha congelada. No es una via para redefinir la "
                           "medida ni para anadirle nada.",
        },
    }
    tr["control_de_campos_implementado"] = {
        "enmienda": 33,
        "regla": "filtro.py comprueba la lista cerrada en toda entrada de tipo "
                 "transicion_de_estado y aborta como defecto estructural si aparece "
                 "cualquier campo fuera de ella.",
        "nota": "Hasta esta enmienda la doctrina afirmaba este control y el motor no lo "
                "ejecutaba. La ausencia de comprobacion en el codigo nunca autorizo a "
                "omitir el requisito doctrinal, pero tampoco lo garantizaba.",
        "aplicacion_prospectiva": {
            "regla": "El control bloquea solo las entradas de transicion escritas a "
                     "partir de esta enmienda. El registro tenia 21 entradas cuando se "
                     "escribio; las entradas 1 a 21 quedan fuera del bloqueo y se "
                     "reportan como incidencia en cada ejecucion.",
            "entradas_previas_a_la_enmienda": 21,
            "motivo": "El registro es append-only: una entrada anterior no se puede "
                      "corregir. Aplicar el control hacia atras dejaria el registro "
                      "permanentemente inejecutable por un defecto que nadie puede "
                      "reparar. Es el mismo criterio de "
                      "ficha_congelada.marcadores_pendientes.prohibicion_prospectiva.",
            "defecto_preexistente_declarado": {
                "entrada": 19,
                "id": "stablecoin_supply_ratio",
                "campo_fuera_de_la_lista": "declaracion",
                "hallazgo": "Detectado por el propio control nada mas implementarlo, el "
                            "2026-09-06. Nadie lo habia visto porque nadie lo "
                            "comprobaba.",
                "alcance": "Es la retirada en propuesta de la entrada 18. Su contenido "
                           "es documental: no define ninguna medida, no participa en "
                           "hash_de_medida y no condiciona ningun test. El defecto es "
                           "de forma, no de fondo.",
                "consecuencia": "Queda declarado aqui y visible en cada ejecucion. No "
                                "se corrige porque no se puede corregir.",
            },
        },
    }

    # ---------------------------------------------------------------- parte 5
    inm = re_["inmutabilidad"]
    if "fecha_corte_bloques_control" in inm:
        print("ABORTA: fecha_corte_bloques_control ya existe")
        return 1

    inm["fecha_corte_bloques_control"] = {
        "enmienda": 33,
        "regla": "filtro.py deriva la particion de los datos y de sus propios "
                 "parametros. Debe comparar la fecha de corte que deriva con la "
                 "registrada en la entrada de transicion y abortar si difieren.",
        "motivo": "El campo estaba escrito en el registro y no lo leia nadie. Un campo "
                  "de precompromiso que ningun control consume es decorativo: podria "
                  "divergir del valor realmente usado sin que nada lo detectase.",
        "no_invierte_la_autoridad": "El valor registrado no sustituye a la derivacion. "
                                    "El motor sigue derivando la particion; el campo "
                                    "actua como comprobacion de que lo derivado coincide "
                                    "con lo comprometido de antemano.",
    }

    # ---------------------------------------------------------------- cierre
    d["meta"]["version_esquema"] = "2.7.0"

    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("OK  enmienda 33 aplicada")
    print(f"    version_esquema: 2.6.0 -> {d['meta']['version_esquema']}")
    print(f"    SHA-256 anterior: {SHA_ESPERADO}")
    print(f"    SHA-256 nuevo:    {sha256_fichero(RUTA)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
