"""
aplicar_enmienda_34.py — SCRIPT DE UN SOLO USO.

Aplica la enmienda 34 a v2.json:
  - version_esquema 2.7.0 -> 2.8.0
  - dos campos nuevos en la lista cerrada de alta_transicion_de_estado
  - bloque ampliacion_enmienda_34 con las declaraciones obligatorias
  - alta en meta.enmiendas

Verifica el SHA-256 de partida antes de tocar nada. Aborta si no coincide.
No edita ningun otro fichero.
"""

import hashlib
import json
import sys

SHA_ESPERADO = "e599bc82a46f49a7ce621ad267dc93321a5e6d3d9a1531e764b9d3ca08c7f71c"
VERSION_ANTERIOR = "2.7.0"
VERSION_NUEVA = "2.8.0"

RUTA = "v2.json"


def sha256_fichero(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def abortar(msg):
    print(f"ABORTA: {msg}")
    sys.exit(1)


def main():
    sha = sha256_fichero(RUTA)
    if sha != SHA_ESPERADO:
        abortar(f"v2.json no es el esperado. {sha} != {SHA_ESPERADO}")
    print(f"[ok] v2.json verificado: {sha[:16]}...")

    with open(RUTA, "r", encoding="utf-8") as f:
        doc = json.load(f)

    if doc["meta"]["version_esquema"] != VERSION_ANTERIOR:
        abortar(f"version_esquema no es {VERSION_ANTERIOR}")

    base = doc["integridad"]["resolucion_de_entradas"]["tipo_entrada"][
        "alta_transicion_de_estado"
    ]

    if "ampliacion_enmienda_34" in base:
        abortar("la enmienda 34 ya esta aplicada")

    campos = base["campos_permitidos"]
    for c in ("sha256_motor", "sha256_informe"):
        if c in campos:
            abortar(f"el campo {c} ya figura en la lista cerrada")

    # Los dos campos nuevos se insertan junto a sha256_snapshot_metrica,
    # antes de declaraciones_de_ejecucion. hash_anterior y hash cierran
    # la lista, como hasta ahora.
    i = campos.index("sha256_snapshot_metrica") + 1
    campos[i:i] = ["sha256_motor", "sha256_informe"]

    base["ampliacion_enmienda_34"] = {
        "campos_anadidos": ["sha256_motor", "sha256_informe"],
        "definiciones": {
            "sha256_motor": "SHA-256 del fichero filtro.py que produjo el resultado registrado en esta entrada.",
            "sha256_informe": "SHA-256 del fichero de informe de lote archivado en el repositorio que contiene ese resultado.",
        },
        "motivo": "El resultado de un test quedaba registrado sin anclaje al artefacto que lo produjo ni al informe que lo documenta. Sin esos dos hashes, la entrada afirma un veredicto que solo puede comprobarse por lectura humana del historial de Git.",
        "alcance_de_sha256_motor": {
            "cubre": "El fichero del motor, unicamente.",
            "no_cubre": "El entorno de ejecucion ni las dependencias. requirements.txt no fija versiones (pandas>=2.0, numpy>=1.24), de modo que dos ejecuciones del mismo fichero pueden correr sobre bibliotecas distintas.",
            "naturaleza": "Limitacion declarada, no resuelta. Fijar versiones es tarea aparte y posterior: no se sabe con que versiones se ejecuto el informe ya archivado, y fijar hoy las de un contenedor de verificacion registraria como confirmado un dato que es supuesto sobre una ejecucion pasada.",
        },
        "obligatoriedad_condicional": {
            "regla": "Ambos campos son exigidos cuando el campo estado de la transicion pertenece a los estados de resultado de test.",
            "estados_de_resultado_de_test": [
                "DESCARTADA_GATE_1",
                "DESCARTADA_GATE_3",
                "DESCARTADA_GATE_4",
                "RECHAZADA_PVALOR",
                "EN_CONFIRMACION",
            ],
            "ancla_estructural": "El propio campo estado. No se crea ningun campo tipo_transicion: anadir un discriminante nuevo para distinguir lo que estado ya distingue duplicaria la fuente de verdad.",
            "nota_gate_2": "DESCARTADA_GATE_2 no figura porque su emision esta prohibida desde la enmienda 19. Un estado que no puede emitirse no puede exigir campos.",
            "fuera_de_esos_estados": "Los campos son opcionales. Una transicion a EN_TEST se escribe antes de ejecutar y no puede conocer el hash de un informe que aun no existe.",
        },
        "no_automatizada": {
            "hecho": "filtro.py no comprueba hoy esta obligatoriedad condicional. La doctrina la afirma y el motor no la ejecuta.",
            "consecuencia": "Queda declarada como hueco conocido del motor, junto al de la enmienda 33: filtro.py verifica el SHA-256 del snapshot de precio contra la doctrina, pero no el del snapshot de matriz ni el del CSV de la metrica.",
            "leccion": "Misma que la enmienda 33: la doctrina no afirma controles que el motor ejecuta sin decirlo, ni finge que ejecuta los que no ejecuta. La ausencia de comprobacion en el codigo no autoriza a omitir el requisito doctrinal, pero tampoco lo garantiza.",
        },
        "cambio_de_compatibilidad_posterior_al_resultado": {
            "hecho": "Esta enmienda cambia mayor.menor, por lo que meta.compatibilidad.consecuencia_asumida obliga a tocar filtro.py. La edicion se limita a la constante DOCTRINA_COMPATIBLE, de 2.7 a 2.8. Se realiza despues de conocer el resultado del test de ssr_capstables del lote 2026-Q3.",
            "por_que_no_afecta_al_resultado": "La constante gobierna unicamente si el motor acepta leer esta doctrina. No interviene en extraccion de datos, calculo, umbrales, mascara, particion, gates ni decision. No tiene capacidad causal sobre un resultado ya emitido, que ademas no se regenera.",
            "consecuencia_registrada": "El SHA-256 de filtro.py cambia. El campo sha256_motor de la entrada que registre ese resultado debe llevar el hash del fichero que EJECUTO, no el del fichero vigente tras esta enmienda. La discrepancia entre ambos es procedencia historica correcta, no un defecto.",
            "reproducibilidad": "El informe archivado es regenerable byte a byte contra el estado del repositorio anterior a esta enmienda, no contra el vigente. La reproducibilidad se define contra el artefacto historico que produjo el resultado.",
            "alcance": "Declaracion de hecho sobre esta enmienda. No crea ninguna regla general ni ninguna excepcion invocable en el futuro. Si se quiere una regla que distinga cambios de compatibilidad de cambios de comportamiento, debe escribirse como enmienda propia y decidirse sin un caso pendiente que la reclame.",
        },
        "aplicacion_prospectiva": {
            "regla": "Los dos campos y su obligatoriedad condicional rigen para las entradas de transicion escritas a partir de esta enmienda. El registro tenia 22 entradas cuando se escribio; las entradas 1 a 22 quedan fuera.",
            "entradas_previas_a_la_enmienda": 22,
            "motivo": "El registro es append-only: una entrada anterior no se puede corregir. Mismo criterio que la aplicacion prospectiva de la enmienda 33.",
        },
        "origen_externo": "Dos rondas de revision externa independiente el 2026-09-06. La segunda, sobre la forma del versionado, con cinco revisores: unanimidad en que ampliar una lista cerrada leida desde la doctrina es un cambio semantico y exige mayor.menor; unanimidad en que meta.compatibilidad.cierre_del_hueco_de_parche es una regla de deteccion y no de autorizacion; unanimidad en que alojar estos hashes en declaraciones_de_ejecucion repetiria la maniobra que la enmienda 33 prohibio con el campo motivo.",
        "naturaleza": "Solo anade. No reescribe ningun texto previo. No altera ningun gate, umbral, mascara, particion ni criterio estadistico. No modifica ninguna entrada del registro.",
    }

    doc["meta"]["version_esquema"] = VERSION_NUEVA

    ns = [e["n"] for e in doc["meta"]["enmiendas"]]
    if 34 in ns:
        abortar("la enmienda 34 ya figura en el indice")
    if max(ns) != 33:
        abortar(f"la ultima enmienda del indice no es la 33, sino la {max(ns)}")

    doc["meta"]["enmiendas"].append(
        {
            "n": 34,
            "titulo": "anclaje del resultado al motor y al informe que lo produjeron",
            "fecha": "2026-09-06",
            "motivo": "La entrada que registra el resultado de un test no tenia donde anclar ni el fichero del motor que lo calculo ni el informe que lo documenta. La lista cerrada de la entrada de transicion carecia de ambos campos y la enmienda 33 prohibe expresamente usar motivo como contenedor de datos estructurados.",
            "partes": [
                "1. Dos campos nuevos en la lista cerrada de la entrada de transicion: sha256_motor y sha256_informe.",
                "2. Obligatoriedad condicional anclada en el campo estado, para los estados de resultado de test.",
                "3. Declaracion del alcance real de sha256_motor: cubre el fichero, no el entorno ni las dependencias.",
                "4. Declaracion de que filtro.py no automatiza esa obligatoriedad, y alta del hueco junto al de los hashes de snapshot no verificados.",
                "5. Declaracion del cambio de la constante de compatibilidad de filtro.py posterior al resultado, con su alcance limitado a esta enmienda.",
            ],
            "naturaleza": "Solo anade. Aplicacion prospectiva.",
        }
    )

    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"[ok] v2.json escrito. version_esquema {VERSION_NUEVA}")
    print(f"[ok] SHA-256 nuevo: {sha256_fichero(RUTA)}")


if __name__ == "__main__":
    main()
