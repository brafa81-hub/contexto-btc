#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aplicar_enmienda_37.py — script de UN SOLO USO.

ENMIENDA 37: implementacion en el motor de las verificaciones de la repesca v1
(enmienda 36) y resolucion doctrinal del campo 'regimen'.

Verifica el SHA-256 de v2.json ANTES de tocar nada. Si no coincide con el
estado esperado, aborta y no escribe.

Se commitea al repositorio como registro auditable de la modificacion.
"""

import hashlib
import json
import sys

RUTA = "v2.json"

SHA_ESPERADO = "0004ef64e44eb5d9efd823887b5b6bc6bdfca3e253b0b52f97c2416b3ebf848e"
VERSION_ESPERADA = "2.10.0"
VERSION_NUEVA = "2.11.0"
FECHA = "2026-09-07"


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def abortar(motivo):
    print("!" * 72)
    print("ABORTA aplicar_enmienda_37.py — no se ha escrito nada")
    print(f"motivo: {motivo}")
    print("!" * 72)
    sys.exit(2)


def main():
    sha = sha256_fichero(RUTA)
    if sha != SHA_ESPERADO:
        abortar(
            f"{RUTA} no esta en el estado esperado.\n"
            f"        esperado: {SHA_ESPERADO}\n"
            f"        leido:    {sha}"
        )

    with open(RUTA, encoding="utf-8") as f:
        doc = json.load(f)

    if doc["meta"]["version_esquema"] != VERSION_ESPERADA:
        abortar(f"version_esquema es {doc['meta']['version_esquema']}, "
                f"se esperaba {VERSION_ESPERADA}")

    if any(e["n"] == 37 for e in doc["meta"]["enmiendas"]):
        abortar("la enmienda 37 ya figura en meta.enmiendas")

    rep = doc["repesca_v1"]
    vfp = rep["verificaciones_de_filtro_py"]
    if "superado_por_la_enmienda_37" in vfp:
        abortar("verificaciones_de_filtro_py ya lleva superado_por_la_enmienda_37")

    res = doc["integridad"]["resolucion_de_entradas"]
    if "regimen" in res:
        abortar("integridad.resolucion_de_entradas ya tiene una clave 'regimen'")

    # -----------------------------------------------------------------
    # PARTE 1 — resolucion del campo 'regimen'
    # -----------------------------------------------------------------
    res["regimen"] = {
        "enmienda": 37,
        "regla": (
            "regimen es una propiedad de la VARIABLE, no de la entrada. Lo fija "
            "la PRIMERA entrada de un id y ninguna entrada posterior puede "
            "cambiarlo. Identica a la regla de 'lote' de la enmienda 29."
        ),
        "comportamiento_ante_discrepancia": (
            "Si una entrada posterior declara un regimen distinto, filtro.py "
            "IGNORA ese valor y hace constar la incoherencia en el informe, "
            "nombrando la entrada. No aborta: el registro es append-only y estas "
            "entradas no se pueden editar."
        ),
        "motivo": (
            "Detectado al implementar la verificacion (b) de la enmienda 36. La "
            "entrada 13 (nasdaq_aclaracion_panel) declara regimen 'v2' sobre una "
            "variable del regimen v1, exactamente el mismo defecto que ya tiene "
            "en el campo lote y que la enmienda 29 resolvio. Sin esta regla, "
            "'nasdaq' resolvia a regimen v2 y la verificacion (b) lo declaraba "
            "no elegible, contradiciendo a ids_elegibles.lista, que lo incluye. "
            "Dos clausulas de la misma enmienda daban respuestas opuestas sobre "
            "la misma variable."
        ),
        "por_que_no_se_resolvio_en_el_codigo": (
            "El motor no puede decidir de que entrada lee un campo cuando la "
            "doctrina no lo dice: seria una regla viviendo en el codigo, que es "
            "lo que meta.precedencia prohibe y lo que "
            "repesca_v1.verificaciones_de_filtro_py.regla exige evitar."
        ),
        "alcance": (
            "No modifica ninguna entrada del registro ni ningun resultado. La "
            "entrada 13 conserva su valor 'v2' y pasa a reportarse como "
            "incoherencia de regimen en cada ejecucion, ademas de la de lote que "
            "ya se reportaba."
        ),
        "no_es_una_categoria_nueva": (
            "No se define que valores puede tomar regimen ni se crea lista "
            "cerrada. Solo se dice de que entrada se lee. Cerrar la lista de "
            "valores exigiria decidir sobre regimenes futuros sin caso."
        ),
        "orden_de_resolucion": (
            "Se fija en el mismo paso que lote: 1) resolver ids; 2) fijar lote y "
            "regimen por la primera entrada de cada id resuelto; 3) fijar estado "
            "por la ultima; 4) contar presupuesto."
        ),
    }

    # -----------------------------------------------------------------
    # PARTE 2 — criterios verificables de ids_elegibles
    # -----------------------------------------------------------------
    rep["ids_elegibles"]["criterios_verificables"] = {
        "enmienda": 37,
        "naturaleza": (
            "TRANSCRIPCION a forma legible por maquina de los tres criterios que "
            "verificacion_viva ya enuncia en prosa. No anade ninguna condicion "
            "nueva, no relaja ninguna existente y no altera la lista de ids."
        ),
        "motivo": (
            "verificacion_viva exige comprobar regimen, lote y estado del id "
            "apuntado, pero sus tres valores solo existian dentro de una frase. "
            "Extraerlos del texto por coincidencia de cadena habria sido una "
            "regla de interpretacion escondida en el motor; escribirlos en el "
            "codigo habria violado verificaciones_de_filtro_py.regla."
        ),
        "regimen": "v1",
        "lote": "v1-historico",
        "estado_operativo": "RECHAZADA_PVALOR",
        "como_se_resuelve_cada_uno": (
            "regimen y lote por la primera entrada del id resuelto "
            "(integridad.resolucion_de_entradas.regimen y .lote); estado por la "
            "ultima."
        ),
    }

    # -----------------------------------------------------------------
    # PARTE 3 — estado de implementacion de las verificaciones
    # -----------------------------------------------------------------
    vfp["superado_por_la_enmienda_37"] = {
        "hecho": (
            "La enmienda 37 implementa en filtro.py las verificaciones (a) a (f) "
            "y el inventario_de_reincidencia. El texto de "
            "estado_de_implementacion describe el estado del motor entre las "
            "enmiendas 36 y 37 y no se reescribe."
        ),
        "controles_que_pasan_a_ejecutarse": [
            "a. pertenencia de repesca_de_id_v1 a ids_elegibles.lista.",
            "b. existencia del id apuntado y coincidencia con los tres criterios "
            "de ids_elegibles.criterios_verificables.",
            "c. presencia y contenido no vacio de declaracion_de_antecedente.",
            "d. unicidad del antecedente entre ids resueltos distintos.",
            "e. una sola repesca por lote.",
            "f. coincidencia del hash de plantilla con el ancla calculada sobre "
            "la ficha operativa de ssr_capstables, nombrando los campos que "
            "difieren.",
            "inventario_de_reincidencia, sin severidad y sin capacidad de "
            "abortar.",
        ],
        "momento_de_ejecucion": (
            "En la fase 1, sobre el registro completo, despues de los defectos "
            "estructurales de la enmienda 31 y antes de la fase de admision. "
            "Ninguna repesca puede llegar a ejecutar un gate sin haberlas "
            "superado, y se comprueban tambien bajo --solo-comprobar."
        ),
        "verificacion_g_no_automatizada": {
            "hecho": (
                "La verificacion (g) no pasa a ejecutarse: la propia lista la "
                "define como invariante de codigo, no como comprobacion en "
                "tiempo de ejecucion."
            ),
            "constatacion": (
                "Verificada por revision del codigo el 2026-09-07: "
                "repesca_de_id_v1 se lee unicamente dentro de las verificaciones "
                "de esta seccion y del inventario, y no aparece en ninguna ruta "
                "de resolucion ni de plegado de ids. Queda constatada en "
                "comentario dentro de filtro.py."
            ),
            "por_que_no_se_imprime_en_cada_ejecucion": (
                "Imprimirla presentaria como comprobada en ejecucion una "
                "propiedad que solo se verifica en revision. Mismo criterio que "
                "ficha_congelada.alcance.aislamiento_del_resolver, que se declara "
                "verificada por revision con fecha y no se comprueba sola."
            ),
        },
        "prohibicion_de_forma_ya_cubierta": (
            "campos.repesca_de_id_v1.prohibicion_de_forma no necesita control "
            "propio: fase1 ya aborta ante cualquier entrada con "
            "referencia_entrada_anterior a un id distinto fuera de las dos "
            "excepciones historicas de la enmienda 28. Una ficha de repesca que "
            "intentase plegarse sobre su antecedente no llega a resolverse."
        ),
        "garantia_de_que_no_se_declara_en_vano": (
            "Esta enmienda cambia mayor.menor y filtro.py aborta antes de leer "
            "nada si DOCTRINA_COMPATIBLE no coincide con version_esquema. Entre "
            "las enmiendas 36 y 37 el motor estaba efectivamente detenido: la 36 "
            "llevo la doctrina a 2.10.0 con un motor que declaraba 2.9. El "
            "desfase se manifesto como aborto, no como control declarado e "
            "incumplido en silencio."
        ),
        "huecos_que_permanecen": [
            "El inventario_de_reincidencia sigue siendo un control detectivo por "
            "coincidencia de cadena. Un id renombrado lo evade por completo. No "
            "cierra elusion_conocida.",
            "Ninguno de estos controles alcanza al entorno de ejecucion.",
        ],
    }

    rep["inventario_de_reincidencia"]["forma_de_la_salida"] = {
        "enmienda": 37,
        "regla": (
            "Cada fila distingue si el id coincide exactamente con un id "
            "elegible o si lo contiene como subcadena estricta."
        ),
        "no_es_un_filtro": (
            "Los nueve ids elegibles se contienen a si mismos y por tanto "
            "figuran siempre en el inventario. No se excluyen: excluirlos seria "
            "un criterio que esta seccion no escribe. La distincion es "
            "descripcion de un hecho, no severidad ni diagnostico."
        ),
    }

    # -----------------------------------------------------------------
    # PARTE 4 — version y registro de la enmienda
    # -----------------------------------------------------------------
    doc["meta"]["version_esquema"] = VERSION_NUEVA
    doc["meta"]["enmiendas"].append({
        "n": 37,
        "titulo": "implementacion de las verificaciones de la repesca v1 y "
                  "resolucion del campo regimen",
        "fecha": FECHA,
        "motivo": (
            "La enmienda 36 dejo sus siete verificaciones DECLARADAS NO "
            "AUTOMATIZADAS y prohibio escribir ninguna repesca hasta "
            "implementarlas. Al implementarlas aparecio que la doctrina no decia "
            "de que entrada se lee el campo regimen, y que segun la respuesta "
            "'nasdaq' era o no elegible: dos clausulas de la enmienda 36 en "
            "contradiccion. Se resuelve por analogia explicita con la regla de "
            "lote de la enmienda 29, escrita en la doctrina y no en el motor."
        ),
    })

    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print("=" * 72)
    print("ENMIENDA 37 APLICADA")
    print(f"  version_esquema: {VERSION_ESPERADA} -> {VERSION_NUEVA}")
    print(f"  sha256 anterior: {SHA_ESPERADO}")
    print(f"  sha256 nuevo:    {sha256_fichero(RUTA)}")
    print("=" * 72)
    print("Recordatorio: filtro.py debe declarar DOCTRINA_COMPATIBLE = \"2.11\".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
