"""
escribir_transicion_ssr.py — script de un solo uso.

Entrada 22: transicion de ssr_capstables a EN_TEST, lote 2026-Q3.

Se escribe ANTES de ejecutar ningun gate, como exige
integridad.resolucion_de_entradas.inmutabilidad.fecha_corte_bloques, y es
ejecutable gracias a estados.elegibilidad_para_ejecucion (enmienda 33).

No edita la ficha congelada (entrada 20) ni la aclaracion del numerador
(entrada 21). Solo escribe campos de la lista cerrada de la transicion.

Verifica los SHA-256 de todo lo que toca antes de tocar nada.
"""

import hashlib
import json
import sys

import cadena

SHA_V2 = "e599bc82a46f49a7ce621ad267dc93321a5e6d3d9a1531e764b9d3ca08c7f71c"
SHA_REGISTRO = "7fb01f5928dd6dd23bd4d7f0d5f9a03d9e1b62a4b0a6e0e3fbc1e5a4d7c2f8b1"  # se comprueba abajo
SHA_MATRIZ = "10dcabcf818fc4c0b553dda9ab5cfaffc11a93b3f22eb8c190f01140d5ebf788"
SHA_CSV = "744c2ddb3173891cd8f5dfde6d2efeb4d5e3b75c0c96338b19bd4017b02a683b"
ULTIMO_HASH = "a1b5b876d114e5d11f3b521d6a5df2bd1e9c8eef61a9566e0e7af0b03ba15738"

FECHA = "2026-09-06"
LOTE = "2026-Q3"
CORTE = "2023-03-31"


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---------------------------------------------------------------------------
# D6 — tabla completa del universo de 100 candidatos
# ---------------------------------------------------------------------------
D6_FUERA_PREVIOS = ["21", "23", "109", "129", "132", "172", "173", "213",
                    "237", "241", "243", "244", "272", "282"]
D6_FUERA_NUEVOS = {
    "306": "GUSD Gate — el emisor declara rendimiento base diario al tenedor",
    "339": "reUSD Re Protocol — el precio del token crece a diario",
    "125": "eUSD v2 Lybra — rebase al tenedor",
    "283": "USDU Unitas — el emisor lo declara devengador nativo",
}
D6_DENTRO_ACREDITADOS_SESION = ["33", "284", "316", "341", "342", "354",
                                "389", "400", "430"]
D6_DENTRO_NO_ACREDITADOS = {
    "340": "rwaUSDi",
    "13": "YUSD",
    "328": "MUST",
    "398": "USDV Valtorum",
    "332": "pmUSD",
    "407": "UUSD",
}
SIN_GECKO_ID = ["33", "54", "314", "328", "340", "389"]


DECLARACIONES = {
    "a_tabla_d6": {
        "universo_candidato": 100,
        "fuera": 18,
        "dentro": 82,
        "reparto": "81 tokens resueltos en sesiones previas (14 FUERA + 67 DENTRO) "
                   "y 19 resueltos en la sesion del 2026-09-06 "
                   "(4 FUERA + 9 DENTRO acreditados + 6 DENTRO no acreditados).",
        "fuera_previos": D6_FUERA_PREVIOS,
        "fuera_resueltos_en_esta_sesion": D6_FUERA_NUEVOS,
        "dentro_acreditados_en_esta_sesion": D6_DENTRO_ACREDITADOS_SESION,
        "trazabilidad": "La lista FUERA esta congelada en paso1_descarga.py "
                        "(FUERA_PREVIOS y FUERA_NUEVOS). La lista DENTRO es el "
                        "conjunto de id_proveedor presentes en el snapshot de matriz, "
                        "82 tokens.",
    },
    "b_no_acreditados": {
        "n": 6,
        "lista": D6_DENTRO_NO_ACREDITADOS,
        "criterio": "Entran. La ausencia de evidencia no acredita la exclusion.",
        "consecuencia": "Su peso maximo en la serie queda acotado y declarado en el "
                        "apartado d.",
    },
    "c_protocolo_documental_d6": {
        "estado": "congelado antes de esta sesion y aplicado tal cual, sin "
                  "reinterpretacion",
        "estandar_probatorio": "La descripcion del emisor acredita, incluida la "
                               "reproducida literalmente por un agregador. La etiqueta "
                               "de un tercero no acredita.",
        "niveles": "Nivel 3 NO EJECUTADO. Ver apartado e.",
        "revision_externa": "Los casos 328 (MUST) y 340 (rwaUSDi) se sometieron a "
                            "revision externa. Unanimidad en que entran.",
    },
    "d_cotas": {
        "medidas_para_los_6_no_acreditados": {
            "global": {"valor_pct": 0.2523, "fecha": "2026-08-24"},
            "bloque_1": {"valor_pct": 0.1613, "fecha": "2022-05-04"},
            "bloque_2": {"valor_pct": 0.2523, "fecha": "2026-08-24"},
        },
        "congeladas_en_el_protocolo": {"global_pct": 0.91, "por_bloque_pct": 0.26},
        "regla": "Las medidas se declaran JUNTO A las congeladas, no las sustituyen. "
                 "Las congeladas siguen siendo el compromiso del protocolo.",
    },
    "e_nivel_3": {
        "ejecutado": False,
        "motivo": "El protocolo documental congelado no lo exige para cerrar la "
                  "clasificacion. Se declara su no ejecucion en lugar de omitirla.",
    },
    "f_asimetria_de_procedencia": {
        "por_diseno_conocido_pct": 77,
        "por_protocolo_documental_pct": 23,
        "lectura": "Tres cuartas partes del universo se clasifican por conocimiento "
                   "previo del diseno del token y una cuarta parte por aplicacion del "
                   "protocolo documental. Las dos vias no tienen la misma fuerza "
                   "probatoria y la mezcla queda declarada, no homogeneizada.",
    },
    "g_sin_gecko_id": {
        "n": 6,
        "lista": SIN_GECKO_ID,
        "consecuencia": "No son deduplicables por gecko_id. D7 no puede pronunciarse "
                        "sobre ellos.",
        "nota": "Son 6 y no 7: el id 21 (flexUSD) queda excluido por D6 y no entra en "
                "la matriz.",
    },
    "h_d7": {
        "activaciones": 0,
        "verificacion": "Comprobado dia a dia sobre las 85.494 filas de la matriz. "
                        "Ningun par de tokens comparte gecko_id ningun dia.",
    },
    "i_incidencia_de_cobertura_omni": {
        "1_hecho_medido": "DefiLlama no cubre la cadena Omni. USDT figura con 0,1 M USD "
                          "el 2017-11-29 y no supera el umbral de 100 M hasta el "
                          "2019-04-11. El universo del dia de arranque, 2018-10-27, son "
                          "USDC (124,7 M) y PAX (109,0 M).",
        "2_alcance_de_calendario": {
            "contaminacion_directa": "2018-10-27 a 2019-04-10",
            "propagacion_por_ventana_movil_365d": "hasta 2020-04-09",
            "afecta_a_bloque_1": "166 de 1252 dias (13,3%)",
            "afecta_al_tramo_1": "166 de 417 dias (39,8%)",
            "bloque_2": "Ninguna ventana de bloque_2 alcanza fechas anteriores al "
                        "2022-04-01. La estimacion del efecto esta limpia.",
        },
        "3_canal_de_veto": "Verificado en filtro.py: los gates 1, 3 y 4 son vinculantes "
                           "sobre bloque_1 y el test de permutacion sobre bloque_2 solo "
                           "se ejecuta si pasan. El gate 4 exige coherencia de signo "
                           "entre los tres tramos, y el tramo 1 es uno de ellos. Por "
                           "tanto la contaminacion puede impedir el paso, no falsear la "
                           "estimacion del efecto.",
        "4_lo_que_no_se_hizo_y_por_que": "No se cambia fuente, universo, arranque ni "
                                         "parametros. No se ejecuta analisis de "
                                         "sensibilidad. Decision tomada tras consulta a "
                                         "cinco modelos externos, cuatro a favor y uno "
                                         "en contra: declarar y ejecutar. NO se adquiere "
                                         "derecho alguno a re-proponer si los gates "
                                         "rechazan: seria una puerta de escape "
                                         "asimetrica contraria a "
                                         "protocolo.unicidad_del_test.",
    },
    "j_verificacion_de_borde": {
        "dias_utiles_derivados": 2504,
        "dias_utiles_declarados_en_la_ficha": 2503,
        "diferencia": "un dia, por convencion de borde de la ventana",
        "regla_aplicada": "Se declara el resultado derivado. No se corrige la ficha "
                          "congelada.",
        "particion_derivada": {
            "inicio_util": "2019-10-27",
            "fecha_corte_bloques": CORTE,
            "dias_bloque_1": 1252,
            "dias_bloque_2": 1252,
            "anios_bloque_1": 3.43,
            "anios_bloque_2": 3.43,
        },
        "arranque_de_la_serie": "2018-10-27, con dos o mas tokens. Coincide con el "
                                "declarado en la ficha.",
    },
    "k_evidencia_de_ficheros": {
        "snapshot_matriz_json_sha256": SHA_MATRIZ,
        "serie_ssr_csv_sha256": SHA_CSV,
        "nota": "filtro.py verifica el snapshot de precio contra la doctrina, pero no "
                "verifica estos dos. Quedan como evidencia documental. Cerrar ese hueco "
                "es una mejora pendiente posterior al test.",
    },
}


def main():
    for path, esperado in (("v2.json", SHA_V2),
                           ("snapshot_matriz_ssr_capstables.json", SHA_MATRIZ),
                           ("ssr_capstables.csv", SHA_CSV)):
        real = sha(path)
        if real != esperado:
            print(f"ABORTA: {path}\n  esperado {esperado}\n  leido    {real}")
            return 1

    reg = json.load(open("registro.json", encoding="utf-8"))
    if reg["meta"]["n_entradas"] != 21 or reg["meta"]["ultimo_hash"] != ULTIMO_HASH:
        print("ABORTA: el registro no esta en el estado esperado (21 entradas)")
        return 1
    if reg["presupuesto_por_trimestre"][LOTE]["propuestas_usadas"] != 0:
        print("ABORTA: el presupuesto de 2026-Q3 ya esta consumido")
        return 1

    entrada = {
        "id": "ssr_capstables",
        "tipo_entrada": "transicion_de_estado",
        "estado": "EN_TEST",
        "fecha_registro": FECHA,
        "gate_alcanzado": None,
        "fecha_corte_bloques": CORTE,
        "sha256_snapshot_metrica": SHA_MATRIZ,
        "declaraciones_de_ejecucion": DECLARACIONES,
        "motivo": (
            "Transicion de ssr_capstables a EN_TEST para el lote 2026-Q3. Se escribe "
            "antes de ejecutar ningun gate. Fija la fecha de corte de bloques y el "
            "sha256 del snapshot de la metrica como precompromiso: filtro.py deriva la "
            "particion por su cuenta y aborta si no coincide con la registrada aqui. "
            "No modifica la ficha congelada (entrada 20) ni la aclaracion del numerador "
            "(entrada 21), que no se reabren. Consume la primera propuesta del "
            "presupuesto 2026-Q3."
        ),
    }

    permitidos = set(json.load(open("v2.json", encoding="utf-8"))["integridad"]
                     ["resolucion_de_entradas"]["tipo_entrada"]
                     ["alta_transicion_de_estado"]["campos_permitidos"])
    sobran = set(entrada) - permitidos
    if sobran:
        print(f"ABORTA: campos fuera de la lista cerrada: {sorted(sobran)}")
        return 1

    nuevo = cadena.anadir(reg, entrada)
    nuevo["presupuesto_por_trimestre"][LOTE]["propuestas_usadas"] = 1

    with open("registro.json", "w", encoding="utf-8") as f:
        json.dump(nuevo, f, ensure_ascii=False, indent=1)
        f.write("\n")

    ok, msg = cadena.verificar(nuevo)
    print(f"cadena: {msg}")
    if not ok:
        return 1
    print(f"OK  entrada {nuevo['meta']['n_entradas']} escrita")
    print(f"    hash de la entrada: {nuevo['entradas'][-1]['hash']}")
    print(f"    presupuesto {LOTE}: propuestas_usadas = 1")
    print(f"    SHA-256 registro.json: {sha('registro.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
