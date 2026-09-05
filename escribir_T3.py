"""
escribir_T3.py — Script de UN SOLO USO.

Escribe DOS entradas en registro.json usando cadena.py (nunca a mano):

  1. transicion_de_estado: retira 'stablecoin_supply_ratio' (entrada 18) a
     RETIRADA_EN_PROPUESTA. D1 del plan del 2026-09-05.
  2. ficha_congelada nueva: 'ssr_capmarket_ptit', sucesora declarada via
     sustituye_a_id_retirado. Campos de medida IDENTICOS a la entrada 18 salvo
     los que D3 y D4 obligan a cambiar (metrica_continua.fuente y
     metrica_continua.definicion).

Verificaciones antes de escribir nada:
  - SHA-256 de v2.json y de registro.json de partida
  - version_esquema 2.6.0
  - comparacion campo a campo de la ficha nueva contra la entrada 18 para los
    9 campos de campos_de_definicion_de_medida.lista

Uso:
    python escribir_T3.py registro.json v2.json
"""

import hashlib
import json
import sys

import cadena

SHA_V2_ESPERADO = "024cab9cf4f3c38de579aa279c4928f587aa5202865b290effa207c35dbb8cd5"
SHA_REG_ESPERADO_ULTIMO = "3f5ca58f36d903c5ce560cefe55f3aab375701421c1991fb0073136a28f0ea57"
VERSION_ESPERADA = "2.6.0"

ID_RETIRADO = "stablecoin_supply_ratio"
ID_NUEVO = "ssr_capmarket_ptit"
FECHA = "2026-09-05"

# Campos de medida que D3/D4 obligan a cambiar. Todo lo que NO este aqui debe
# copiarse IDENTICO de la entrada 18.
CAMBIA_METRICA_CONTINUA = True   # fuente y definicion, por D3 y D4
CAMBIA_OTROS = []                # mascara, horizonte_N, M, unidad_theta,
                                  # signo_esperado, casilla_dashboard,
                                  # naturaleza_de_la_hipotesis, dias_episodio:
                                  # NINGUNO cambia


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    ruta_reg, ruta_v2 = argv[1], argv[2]

    sha_v2 = sha256_fichero(ruta_v2)
    if sha_v2 != SHA_V2_ESPERADO:
        print(f"ABORTA: SHA-256 de v2.json {sha_v2} != {SHA_V2_ESPERADO}")
        return 1

    with open(ruta_v2, encoding="utf-8") as f:
        doc = json.load(f)
    if doc["meta"]["version_esquema"] != VERSION_ESPERADA:
        print("ABORTA: version_esquema inesperada")
        return 1

    with open(ruta_reg, encoding="utf-8") as f:
        reg = json.load(f)

    ok, msg = cadena.verificar(reg)
    if not ok:
        print(f"ABORTA: cadena rota antes de empezar: {msg}")
        return 1

    entrada18 = reg["entradas"][17]
    if entrada18["id"] != ID_RETIRADO or entrada18.get("hash") != SHA_REG_ESPERADO_ULTIMO:
        print("ABORTA: la entrada 18 no es la esperada")
        return 1
    if entrada18.get("estado") != "PROPUESTA":
        print(f"ABORTA: SSR no esta en PROPUESTA, esta en {entrada18.get('estado')}")
        return 1
    if entrada18.get("theta_B2") is not None:
        print("ABORTA: theta_B2 no es null, no se puede retirar")
        return 1

    campos_medida = doc["ficha_congelada"]["campos_de_definicion_de_medida"]["lista"]

    # ======================================================================
    # ENTRADA A: retirada de la 18 (transicion_de_estado)
    # ======================================================================
    retirada = {
        "id": ID_RETIRADO,
        "tipo_entrada": "transicion_de_estado",
        "estado": "RETIRADA_EN_PROPUESTA",
        "fecha_registro": FECHA,
        "motivo": (
            "D1 del plan cerrado 2026-09-05. La entrada 18 no tiene salida "
            "dentro de la doctrina: ficha_congelada.marcadores_pendientes "
            "exige que metrica_continua.fuente deje de ser PENDIENTE_DEFINICION "
            "antes de EN_TEST, y ficha_congelada.migracion_de_fichas."
            "limite_de_la_sustitucion prohibe que metrica_continua difiera "
            "entre una ficha y su sustitutiva. Ninguna excepcion monotonica "
            "podria ademas corregir la ambiguedad de 'oferta agregada' en "
            "metrica_continua.definicion, que no lleva marcador propio."
        ),
        "declaracion": (
            "Esta retirada NO es un resultado de test. SSR nunca alcanzo "
            "EN_TEST, no tiene theta_B2, no tiene snapshot de datos asociado y "
            "no ha consumido presupuesto (propuestas_usadas 2026-Q3 = 0 antes y "
            "despues de esta entrada). No reabre protocolo.unicidad_del_test."
        ),
    }

    reg = cadena.anadir(reg, retirada)
    print(f"OK  entrada {len(reg['entradas'])}: retirada de '{ID_RETIRADO}' anadida")

    # ======================================================================
    # ENTRADA B: ficha nueva, sucesora declarada
    # ======================================================================
    e18 = entrada18  # atajo de lectura

    ficha = {
        "id": ID_NUEVO,
        "alias": "SSR",
        "tipo_entrada": "ficha_congelada",
        "familia": e18["familia"],
        "regimen": "v2",
        "lote": "2026-Q3",
        "fecha_propuesta": FECHA,
        "fecha_fin_ventana_test": FECHA,
        "fecha_corte_bloques": None,
        "estado": "PROPUESTA",
        "gate_alcanzado": None,

        # --- metrica_continua: UNICO campo de medida que D3/D4 obligan a
        # cambiar. fuente pasa de PENDIENTE_DEFINICION a objeto completo
        # (T4, pendiente). definicion se corrige (D1: 'oferta agregada' era
        # ambigua) y ahora fija el denominador en capitalizacion (D3).
        "metrica_continua": {
            "definicion": (
                "Stablecoin Supply Ratio: capitalizacion de mercado de BTC "
                "dividida entre la capitalizacion de mercado agregada del "
                "universo de stablecoins en t (oferta circulante x precio de "
                "mercado del token en t), no oferta nominal. Ver D3."
            ),
            "fuente": "PENDIENTE_DEFINICION",
            "nota_fuente": (
                "PENDIENTE a proposito, tarea T4 de este mismo plan. Como "
                "fecha_registro de ESTA ficha es 2026-09-05, la prohibicion "
                "prospectiva de la enmienda 31 se aplica en pleno: esta ficha "
                "NO puede escribirse en el registro definitivo mientras este "
                "campo siga PENDIENTE. Se deja aqui unicamente para completar "
                "la comparacion campo a campo de T3; T4 debe rellenarlo antes "
                "de que esta entrada se anada de verdad con cadena.py."
            ),
        },

        # --- resto de campos de medida: IDENTICOS a la entrada 18, verificado
        # campo a campo mas abajo por el propio script.
        "mascara": e18["mascara"],
        "horizonte_N": e18["horizonte_N"],
        "unidad_theta": e18["unidad_theta"],
        "theta_B2": None,
        "M": e18["M"],
        "estado_M": e18["estado_M"],
        "derivacion_M": e18["derivacion_M"],
        "casilla_dashboard": e18["casilla_dashboard"],
        "naturaleza_de_la_hipotesis": e18["naturaleza_de_la_hipotesis"],
        "dias_episodio": e18["dias_episodio"],
        "signo_esperado": e18["signo_esperado"],
        "justificacion_signo": e18["justificacion_signo"],

        "pronostico_registrado": e18["pronostico_registrado"],
        "consume_presupuesto_v2": False,
        "nota_presupuesto": "Consumira presupuesto al transitar a EN_TEST.",

        "fecha_registro": FECHA,
        "sustituye_a_id_retirado": ID_RETIRADO,
        "declaracion_de_sesgo": (
            "Campos de definicion de medida que difieren respecto a la ficha "
            "retirada (id 'stablecoin_supply_ratio', entrada 18) y por que:\n"
            "- metrica_continua.definicion: se sustituye 'oferta agregada de "
            "stablecoins' (ambigua, sin marcador propio, senalada por "
            "revisores externos) por 'capitalizacion de mercado agregada del "
            "universo de stablecoins' (D3). El cambio esta motivado por que el "
            "tratamiento del depeg de UST altera el resultado segun se use "
            "oferta nominal o capitalizacion, y revisores externos senalaron "
            "esa sensibilidad antes de fijar la eleccion.\n"
            "- metrica_continua.fuente: sigue PENDIENTE_DEFINICION en este "
            "borrador de comparacion; se completa en T4 antes de escribir esta "
            "entrada de verdad.\n"
            "Ningun otro campo de definicion de medida cambia: mascara, "
            "horizonte_N, M, unidad_theta, signo_esperado, casilla_dashboard, "
            "naturaleza_de_la_hipotesis y dias_episodio son identicos, "
            "verificados campo a campo contra la entrada 18."
        ),
        "nota": (
            f"Ficha sucesora de '{ID_RETIRADO}' (RETIRADA_EN_PROPUESTA, "
            f"entrada {len(reg['entradas'])}). Registrada bajo la enmienda 31 "
            f"y sujeta en pleno a su prohibicion prospectiva por llevar "
            f"fecha_registro {FECHA}."
        ),
    }

    # --- Comparacion campo a campo, tal como pide T3 explicitamente --------
    print("\n=== COMPARACION CAMPO A CAMPO CONTRA LA ENTRADA 18 ===")
    idénticos, distintos = [], []
    for c in campos_medida:
        if c == "metrica_continua":
            distintos.append(c)
            continue
        if ficha.get(c) == e18.get(c):
            idénticos.append(c)
        else:
            distintos.append(c)
            print(f"  DIFERENTE (inesperado): {c}")

    print(f"  identicos a la entrada 18: {idénticos}")
    print(f"  distintos (D3/D4 obligan): {distintos}")

    if set(distintos) != {"metrica_continua"}:
        print("\nABORTA: cambian mas campos de medida de los que D3/D4 autorizan.")
        return 1
    if len(idénticos) != len(campos_medida) - 1:
        print("\nABORTA: no todos los campos esperados quedaron identicos.")
        return 1

    print("\nOK  verificacion campo a campo superada: solo metrica_continua "
          "difiere, exactamente lo que D3 y D4 exigen.")

    # NOTA IMPORTANTE: esta ficha NO se escribe todavia con cadena.anadir(),
    # porque metrica_continua.fuente sigue PENDIENTE. filtro.py --validar-entrada
    # la rechazaria (correctamente) por la enmienda 31. Se deja preparada en
    # ficha_ssr_borrador.json para que T4 solo tenga que rellenar el campo
    # fuente y ejecutar este mismo bloque.

    with open("ficha_ssr_borrador.json", "w", encoding="utf-8") as f:
        json.dump(ficha, f, ensure_ascii=False, indent=2)
    print("\nOK  borrador de la ficha escrito en ficha_ssr_borrador.json "
          "(NO anadido al registro: fuente sigue pendiente, ver T4)")

    # Se escribe SOLO la retirada, que si esta completa y valida por si sola.
    with open(ruta_reg, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    ok, msg = cadena.verificar(reg)
    print(f"\n{'OK' if ok else 'FALLO'}  {msg}")
    print(f"OK  registro.json escrito con la retirada de '{ID_RETIRADO}' "
          f"({len(reg['entradas'])} entradas)")
    print(f"OK  SHA-256 nuevo de registro.json: {sha256_fichero(ruta_reg)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
