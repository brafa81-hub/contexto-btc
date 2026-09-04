"""
migracion_enmienda_32.py — Script de UN SOLO USO.

Aplica la enmienda 32 a v2.json. No toca registro.json.

Origen: consulta a cuatro modelos externos el 2026-09-05 sobre la solidez del
freno "una_sola_vez" de la enmienda 31. Consenso unanime (4/4): la visibilidad
en la cadena de hashes es un control detectivo, no preventivo, y no constituye
un freno real cuando el unico auditor probable es el autor de las fichas.

Tres partes:
  1. Reformula la afirmacion normativa de una_sola_vez. El protocolo garantiza
     unicidad de identidad FORMAL declarada, no de concepto. Deja de prometer
     una propiedad que el sistema no puede demostrar.
  2. Declara la retirada estrategica como limitacion conocida no prevenible
     por codigo.
  3. Anade hash_de_medida: identidad formal calculada (no almacenada) sobre los
     campos de definicion de medida, con su cobertura real declarada.

Uso:
    python migracion_enmienda_32.py v2.json
"""

import hashlib
import json
import sys

SHA_ESPERADO = "8e4e8e1fe6300af7e4573d3169255e817a92ce82c04065bce4210eeb0fe18e65"
VERSION_ORIGEN = "2.5.0"
VERSION_DESTINO = "2.6.0"


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ruta = argv[1]

    sha_ini = sha256_fichero(ruta)
    if sha_ini != SHA_ESPERADO:
        print(f"ABORTA: SHA-256 de partida {sha_ini}")
        print(f"        esperado           {SHA_ESPERADO}")
        return 1

    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)

    if doc["meta"]["version_esquema"] != VERSION_ORIGEN:
        print("ABORTA: version_esquema de partida inesperada")
        return 1

    fc = doc["ficha_congelada"]
    rp = fc["retirada_en_propuesta"]

    # === PARTE 1: reformular la afirmacion normativa ======================
    usv = rp["reproposicion"]["una_sola_vez"]
    if "alcance_real" in usv:
        print("ABORTA: la parte 1 ya esta aplicada")
        return 1

    usv["_texto_sustituido_enmienda_31"] = usv["efecto"]
    usv["efecto"] = (
        "Cada CADENA DE SUCESION DECLARADA dispone de una sola correccion. "
        "Cierra el bucle retirar-reproponer-retirar dentro de esa cadena."
    )
    usv["alcance_real"] = {
        "enmienda": 32,
        "garantia": (
            "El protocolo garantiza unicidad de IDENTIDAD FORMAL DECLARADA. No "
            "garantiza unicidad de concepto ni de constructo."
        ),
        "no_garantia": (
            "Dos fichas con ids distintos que midan lo mismo en espiritu son, "
            "para el motor, dos variables distintas. La deteccion de "
            "equivalencia conceptual queda FUERA del enforcement automatico: es "
            "un control de auditoria, no una propiedad del sistema."
        ),
        "motivo_de_la_reformulacion": (
            "La redaccion de la enmienda 31 afirmaba que cada variable "
            "subyacente dispone de una sola correccion. El mecanismo no "
            "implementa eso: implementa una sola sucesion por cadena declarada. "
            "Afirmar la propiedad mas fuerte era prometer algo que el sistema no "
            "puede demostrar, que es justo el defecto que el resto del protocolo "
            "evita."
        ),
    }
    usv["elusion_conocida"] = {
        "descripcion": (
            "El freno se ata a la PRESENCIA del campo sustituye_a_id_retirado. "
            "Nada impide reproponer la misma medida con un id nuevo omitiendo "
            "ese campo y presentandola como variable nueva."
        ),
        "detectable_por_codigo": False,
        "no_se_cierra_porque": (
            "Identidad por significado, cero intervencion humana y cero "
            "clasificacion semantica son tres propiedades incompatibles entre "
            "si. Cualquier regla que decida cuando dos medidas son 'la misma' es "
            "clasificacion semantica, que es la via ya descartada expresamente "
            "en ficha_congelada.alcance.prohibicion_de_referencias."
            "sin_clasificacion_de_campos por abrir deriva de clasificacion."
        ),
        "descartado_concept_key": (
            "Se evaluo exigir una clave canonica de concepto declarada por el "
            "autor. Rechazado: es una etiqueta declarada, luego tiene "
            "exactamente la misma debilidad que sustituye_a_id_retirado, y "
            "ademas introduce la clasificacion semantica ya descartada."
        ),
        "descartada_normalizacion_previa": (
            "Se evaluo normalizar los campos de medida (recortar espacios, "
            "unificar mayusculas, ordenar listas) antes de calcular su hash. "
            "Rechazado: decidir que diferencias 'no son sustanciales' es "
            "clasificacion semantica por la puerta de atras, y haria el hash "
            "menos verificable, no mas."
        ),
        "revision_externa": (
            "Consenso unanime de cuatro modelos externos el 2026-09-05: la "
            "visibilidad en la cadena de hashes es un control detectivo, no "
            "preventivo, y no frena a un autor que sea tambien su unico auditor."
        ),
    }

    # === PARTE 2: retirada estrategica ====================================
    if "retirada_estrategica" in rp:
        print("ABORTA: la parte 2 ya esta aplicada")
        return 1
    rp["retirada_estrategica"] = {
        "enmienda": 32,
        "problema": (
            "Como la retirada no consume presupuesto, funciona como una opcion "
            "de abandono gratuita: mirar los datos de forma informal, intuir que "
            "la variable va a fallar, retirarla y reproponer una version "
            "retocada."
        ),
        "por_que_no_lo_impide_sin_datos_adquiridos": (
            "La condicion sin_datos_adquiridos solo comprueba que no exista "
            "theta_B2 ni snapshot asociado. Mirar una serie sin registrar nada "
            "no deja rastro en el registro."
        ),
        "prevenible_por_codigo": False,
        "mitigacion_real": (
            "No esta en esta capa. La garantia del sistema frente a este riesgo "
            "es la misma que frente al resto de la seleccion: la confirmacion "
            "forward sobre datos que no existian cuando la variable fue "
            "propuesta. Una retirada estrategica no compra nada alli, porque la "
            "ventana forward se juzga sobre datos futuros que el autor no puede "
            "haber mirado. Ver meta.declaracion_obligatoria."
        ),
        "se_declara_no_se_resuelve": (
            "Se hace constar en el mismo registro que potencia_medida y que "
            "notas_de_migracion.theta_v1_no_comparable: son limitaciones "
            "conocidas del sistema, declaradas para que ningun informe futuro "
            "pueda presentarlas como si no existieran."
        ),
    }

    # === PARTE 3: hash de medida ==========================================
    if "hash_de_medida" in fc:
        print("ABORTA: la parte 3 ya esta aplicada")
        return 1
    fc["hash_de_medida"] = {
        "enmienda": 32,
        "definicion": (
            "SHA-256 de la serializacion canonica del subconjunto de campos de "
            "campos_de_definicion_de_medida.lista presentes en una ficha."
        ),
        "canonizacion": (
            "La MISMA que registro.json -> meta.canonizacion: claves ordenadas, "
            "separadores compactos, UTF-8. No se define ninguna convencion "
            "nueva. No se aplica ninguna normalizacion previa del contenido."
        ),
        "calculado_no_almacenado": {
            "regla": (
                "El hash NO se escribe en la ficha. filtro.py lo calcula en cada "
                "ejecucion a partir del contenido."
            ),
            "motivo": (
                "Un hash almacenado puede divergir del contenido que dice "
                "resumir, y obliga a una comprobacion adicional que puede "
                "fallar. Un hash derivado no puede mentir."
            ),
        },
        "solo_fichas_completas": {
            "regla": (
                "Solo se calcula sobre entradas que contengan TODOS los campos "
                "de la lista. Las fichas incompletas no producen hash y no "
                "entran en la comparacion."
            ),
            "motivo": (
                "Una ficha se construye por etapas. Comparar hashes de "
                "subconjuntos distintos de campos no significa nada."
            ),
        },
        "regla_de_colision": {
            "entre_ids_distintos": (
                "Si dos ids RESUELTOS distintos producen el mismo hash de "
                "medida, filtro.py ABORTA y nombra ambos. Es una reproposicion "
                "exacta de una medida ya registrada."
            ),
            "dentro_del_mismo_id": (
                "Esperado y correcto: limite_de_la_sustitucion exige que una "
                "ficha sustitutiva tenga los campos de medida identicos a la "
                "anterior. No es colision."
            ),
        },
        "que_protege": (
            "La reproposicion EXACTA de una medida ya registrada, con o sin "
            "sustituye_a_id_retirado. Refuerza protocolo.unicidad_del_test."
        ),
        "que_NO_protege": (
            "NO implementa una_sola_vez. El proposito legitimo de retirar y "
            "reproponer es cambiar campos de medida, luego el hash nuevo nunca "
            "colisiona con el retirado. Y una reproposicion abusiva con un "
            "retoque minimo tampoco colisiona. Se declara para que nadie lea "
            "esta regla como si cerrase la elusion_conocida."
        ),
        "cobertura_medida_2026_09_05": (
            "0 de las 11 variables ya testeadas. Las entradas 1 a 11, 13, 14 y "
            "17 son de regimen v1 y no contienen ningun campo de definicion de "
            "medida, por lo que no producen hash. La cobertura es "
            "exclusivamente prospectiva y arranca desde una base vacia. Medido "
            "por script sobre el registro de 18 entradas."
        ),
    }

    doc["meta"]["version_esquema"] = VERSION_DESTINO

    salida = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(salida)

    print(f"OK  enmienda 32 aplicada. version_esquema {VERSION_DESTINO}")
    print(f"OK  SHA-256 nuevo: {sha256_fichero(ruta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
