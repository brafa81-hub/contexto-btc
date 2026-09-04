"""
filtro.py v2 — Motor de validacion de Contexto-BTC.

Este archivo NO contiene reglas del protocolo. Lee la doctrina de v2.json y el
historial de registro.json, y ejecuta lo que ellos dicen. Si el codigo y la
doctrina discrepan, el codigo ABORTA; no se adapta (v2.json -> meta.precedencia).

Todo numero, umbral, minimo, lista cerrada y tabla de traduccion sale de
v2.json en tiempo de ejecucion. Las unicas constantes de este archivo son:

    DOCTRINA_COMPATIBLE   la version mayor.menor de doctrina que sabe leer
    _RAMA_BY_NEGATIVA     hueco declarado en la doctrina (ver nota abajo)

filtro.py NO escribe en registro.json. Emite la entrada propuesta por pantalla
o a un fichero aparte. La escritura es un paso separado, via cadena.anadir.

Uso:
    python filtro.py --lote 2026-Q3 --precio snapshot.csv \
        --metrica stablecoin_supply_ratio=ssr.csv [--informe informe.json]
    python filtro.py --lote 2026-Q3 --solo-comprobar
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import cadena

DOCTRINA_COMPATIBLE = "2.6"

# Hueco declarado de la doctrina: estados.mapeo_salida_filtro_py.tabla traduce
# la etiqueta interna PASA a EN_CONFIRMACION "solo si supera ademas el umbral BY
# del lote", pero no existe fila para la rama negativa. El estado RECHAZADA_PVALOR
# SI existe en estados.lista, con la descripcion exacta de ese caso. Se nombra
# aqui, se valida contra la lista cerrada en ejecucion, y se reporta como hueco
# en cada informe hasta que una enmienda anada la fila.
_RAMA_BY_NEGATIVA = "RECHAZADA_PVALOR"

_SHA_DOCTRINA = None  # se rellena al cargar; se imprime en toda salida


# =====================================================================
# UTILIDADES
# =====================================================================

class Aborto(Exception):
    """Ninguna ejecucion continua tras esto."""


def abortar(motivo):
    raise Aborto(motivo)


def ruta(obj, camino, defecto=KeyError):
    """Resuelve 'a.b.c' sobre diccionarios anidados."""
    actual = obj
    for parte in camino.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            if defecto is KeyError:
                abortar(f"la doctrina no contiene la ruta '{camino}'")
            return defecto
        actual = actual[parte]
    return actual


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _cargar_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _recorrer(obj, prefijo=""):
    """Genera (ruta, valor) para todas las hojas de una estructura anidada."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _recorrer(v, f"{prefijo}.{k}" if prefijo else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _recorrer(v, f"{prefijo}[{i}]")
    else:
        yield prefijo, obj


# =====================================================================
# FASE 0 — ARRANQUE
# =====================================================================

def fase0_arranque(ruta_doctrina, ruta_registro):
    global _SHA_DOCTRINA

    doc = _cargar_json(ruta_doctrina)
    _SHA_DOCTRINA = sha256_fichero(ruta_doctrina)

    version = ruta(doc, "meta.version_esquema")
    mayor_menor = ".".join(str(version).split(".")[:2])
    if mayor_menor != DOCTRINA_COMPATIBLE:
        abortar(
            f"incompatibilidad de doctrina: filtro.py sabe leer "
            f"{DOCTRINA_COMPATIBLE}.x y v2.json declara {version}. "
            f"No se lee nada mas."
        )

    reg = _cargar_json(ruta_registro)

    ok, msg = cadena.verificar(reg)
    if not ok:
        abortar(f"cadena de hashes rota: {msg}. No se ejecuta ningun lote.")

    # Enmienda 29 parte 2: los maximos viven solo en v2.json.
    permitidos = set(ruta(doc, "presupuesto.autoridad.que_permanece_en_registro_json"))
    for lote, cont in reg.get("presupuesto_por_trimestre", {}).items():
        for campo in cont:
            if "maxima" in campo or "maximo" in campo:
                abortar(
                    f"registro.json todavia declara un maximo de presupuesto "
                    f"('{campo}' en {lote}). La autoridad es v2.json "
                    f"(presupuesto.autoridad). Campos permitidos: {sorted(permitidos)}"
                )

    return doc, reg, msg


# =====================================================================
# FASE 1 — RESOLUCION DEL REGISTRO
# =====================================================================

def fase1_resolver(doc, reg):
    """
    Orden obligatorio (integridad.resolucion_de_entradas.lote.orden_de_resolucion):
        1) resolver ids   2) lote por la primera   3) estado por la ultima
        4) contar presupuesto
    """
    incidencias = []
    entradas = reg["entradas"]

    estados_validos = {e["id"] for e in ruta(doc, "estados.lista")}
    tipos_validos = set(ruta(doc, "integridad.resolucion_de_entradas.tipo_entrada.valores"))
    tipo_ausente = ruta(doc, "integridad.resolucion_de_entradas.tipo_entrada.ausente_equivale_a")

    # --- paso 1: resolver ids -------------------------------------------------
    texto_excepciones = ruta(doc, "integridad.resolucion_de_entradas.excepciones_documentadas.regla")
    ids_excepcion = {
        e["id"] for e in entradas
        if e["id"] in texto_excepciones and e.get("referencia_entrada_anterior")
        and e["id"] != e["referencia_entrada_anterior"]
    }

    resueltas = {}  # id_resuelto -> lista de entradas en orden de aparicion
    for i, e in enumerate(entradas, start=1):
        estado = e.get("estado")
        if estado not in estados_validos:
            abortar(f"entrada {i} ({e['id']}): estado '{estado}' fuera de la lista cerrada")

        tipo = e.get("tipo_entrada", tipo_ausente)
        if tipo not in tipos_validos:
            abortar(f"entrada {i} ({e['id']}): tipo_entrada '{tipo}' desconocido")

        ref = e.get("referencia_entrada_anterior")
        id_res = e["id"]
        if ref and ref != e["id"]:
            if e["id"] not in ids_excepcion:
                abortar(
                    f"entrada {i} ({e['id']}): aclaracion con id propio fuera de las "
                    f"dos excepciones historicas de la enmienda 28. Prohibida."
                )
            id_res = ref
            incidencias.append(
                f"entrada {i}: '{e['id']}' resuelve al id '{ref}' (excepcion enmienda 28)"
            )

        resueltas.setdefault(id_res, []).append((i, e))

    # --- pasos 2 y 3: lote por la primera, estado por la ultima ----------------
    variables = {}
    for id_res, lista in resueltas.items():
        n_primera, primera = lista[0]
        lote = primera.get("lote")

        for n, e in lista[1:]:
            if e.get("lote") and e["lote"] != lote:
                incidencias.append(
                    f"entrada {n} ({e['id']}) declara lote '{e['lote']}' pero '{id_res}' "
                    f"tiene lote '{lote}' fijado por la entrada {n_primera}. "
                    f"Se ignora y se reporta (enmienda 29 parte 4)."
                )

        n_ultima, ultima = lista[-1]
        variables[id_res] = {
            "id": id_res,
            "lote": lote,
            "estado": ultima.get("estado"),
            "familia": ultima.get("familia") or primera.get("familia"),
            "entrada_operativa": ultima,
            "n_entrada_operativa": n_ultima,
            "historial": lista,
        }

    # --- paso 4: presupuesto derivado ------------------------------------------
    der = ruta(doc, "presupuesto.derivacion")
    cuentan = set(der["estados_que_cuentan_como_consumido"])
    exentos = set(der["lotes_exentos"])

    consumo = {}
    for v in variables.values():
        if v["lote"] in exentos or not v["lote"]:
            continue
        consumo.setdefault(v["lote"], 0)
        if v["estado"] in cuentan:
            consumo[v["lote"]] += 1

    # --- enmienda 31: defectos estructurales del registro ---------------------
    # Se comprueban ANTES del presupuesto porque no son bloqueos de un lote:
    # son entradas que nunca debieron escribirse.
    estructurales = []
    for i, e in enumerate(entradas, start=1):
        estructurales += prohibicion_prospectiva(e, doc, n=i)
    estructurales += _validar_retiradas(variables, doc)
    estructurales += _colisiones_de_medida(variables, doc)
    if estructurales:
        abortar(
            "defecto estructural del registro (enmienda 31):\n  - "
            + "\n  - ".join(estructurales)
        )

    almacenado = reg.get("presupuesto_por_trimestre", {})
    for lote, derivado in consumo.items():
        guardado = almacenado.get(lote, {}).get("propuestas_usadas")
        if guardado is not None and guardado != derivado:
            abortar(
                f"presupuesto incoherente en {lote}: derivado del registro = {derivado}, "
                f"contador almacenado = {guardado}. {der['comportamiento_si_discrepan']}"
            )

    return variables, consumo, incidencias


# =====================================================================
# FASE 2 — ADMISION A EN_TEST
# =====================================================================

def _bloqueos_globales(doc):
    problemas = []
    snap = ruta(doc, "fuente_de_precio.snapshot")
    if snap.get("obligatorio") and not snap.get("sha256"):
        problemas.append(
            f"fuente_de_precio.snapshot.sha256 = null "
            f"(estado {snap.get('estado')}). Bloqueo de alcance global: "
            f"ningun lote puede ejecutarse sin el snapshot congelado."
        )
    return problemas


def _validar_ficha(entrada, doc):
    """Devuelve lista de problemas. No lanza: el llamador decide."""
    problemas = []
    fc = ruta(doc, "ficha_congelada")

    for campo in fc["campos_obligatorios"]:
        if ruta(entrada, campo, defecto=None) is None:
            problemas.append(f"falta el campo obligatorio de ficha '{campo}'")

    for campo in ruta(doc, "ficha_congelada.mascara.campos_obligatorios"):
        if entrada.get("mascara", {}).get(campo) is None:
            problemas.append(f"falta el campo obligatorio de mascara '{campo}'")

    # Alcance de la ficha (enmienda 29 parte 1): campos prohibidos.
    for campo in ruta(doc, "ficha_congelada.alcance.campos_que_no_pertenecen_a_la_ficha"):
        if campo in entrada:
            problemas.append(
                f"la ficha contiene el campo prohibido '{campo}' "
                f"(ficha_congelada.alcance)"
            )

    # Referencias a rutas de v2.json dentro de la ficha (enmienda 30).
    # La aparicion textual de una ruta NO es causa de aborto. La prohibicion es
    # de DEPENDENCIA, no de mencion: filtro.py nunca resuelve estas cadenas
    # contra la doctrina. Se recogen en un inventario descriptivo sin severidad
    # (ficha_congelada.alcance.inventario_de_referencias), que se imprime en el
    # informe y no condiciona ninguna transicion de estado.

    # Marcadores PENDIENTE_ (enmienda 29): recursivo, a cualquier profundidad.
    prefijo = ruta(doc, "ficha_congelada.marcadores_pendientes.prefijo")
    for camino, valor in _recorrer(entrada):
        if isinstance(valor, str) and valor.startswith(prefijo):
            problemas.append(
                f"el campo '{camino}' contiene el marcador '{valor}'. "
                f"No puede transitar a EN_TEST"
            )

    return problemas


def prohibicion_prospectiva(entrada, doc, n=None):
    """
    ficha_congelada.marcadores_pendientes.prohibicion_prospectiva (enmienda 31).

    Ninguna entrada de ficha con fecha_registro >= fecha_efecto puede llevar un
    marcador PENDIENTE_ dentro de un campo de definicion de medida.

    Devuelve lista de problemas. NO es un bloqueo por variable: el llamador de
    fase 1 aborta, porque una entrada asi es un defecto estructural del
    registro. Esta misma funcion es la que usa --validar-entrada antes de
    escribir nada con cadena.py.
    """
    pp = ruta(doc, "ficha_congelada.marcadores_pendientes.prohibicion_prospectiva")
    prefijo = ruta(doc, "ficha_congelada.marcadores_pendientes.prefijo")
    campos = ruta(doc, "ficha_congelada.campos_de_definicion_de_medida.lista")
    tipos = ("propuesta", "ficha_congelada", "alta_retroactiva")

    tipo = entrada.get("tipo_entrada", ruta(
        doc, "integridad.resolucion_de_entradas.tipo_entrada.ausente_equivale_a"))
    if tipo not in tipos:
        return []

    fecha = entrada.get("fecha_registro") or entrada.get("fecha_propuesta")
    if not fecha or str(fecha) < pp["fecha_efecto"]:
        return []

    etiqueta = f"entrada {n}: " if n else ""
    problemas = []
    for campo in campos:
        if campo not in entrada:
            continue
        for camino, valor in _recorrer({campo: entrada[campo]}):
            if isinstance(valor, str) and valor.startswith(prefijo):
                problemas.append(
                    f"{etiqueta}[{entrada.get('id')}] el campo de definicion de "
                    f"medida '{camino}' contiene el marcador '{valor}'. "
                    f"Prohibido desde {pp['fecha_efecto']} (enmienda 31)"
                )
    return problemas


def _validar_retiradas(variables, doc):
    """
    ficha_congelada.retirada_en_propuesta (enmienda 31).

    Comprueba las condiciones estrictas del estado terminal
    RETIRADA_EN_PROPUESTA. Devuelve lista de problemas; el llamador aborta.
    """
    rp = ruta(doc, "ficha_congelada.retirada_en_propuesta")
    cuentan = set(ruta(doc, "presupuesto.derivacion.estados_que_cuentan_como_consumido"))
    campo_suc = rp["reproposicion"]["campo_obligatorio"]
    problemas = []

    retirados = set()
    for v in variables.values():
        historial = v["historial"]
        estados = [e.get("estado") for _, e in historial]

        if "RETIRADA_EN_PROPUESTA" in estados:
            i = estados.index("RETIRADA_EN_PROPUESTA")
            n_ret, ret = historial[i]
            retirados.add(v["id"])

            # terminalidad
            if i != len(historial) - 1:
                problemas.append(
                    f"[{v['id']}] RETIRADA_EN_PROPUESTA (entrada {n_ret}) es "
                    f"terminal, pero existen entradas posteriores con el mismo id"
                )
            # nunca alcanzo EN_TEST ni ningun estado que consuma
            previos = [s for s in estados[:i] if s in cuentan or s == "EN_TEST"]
            if previos:
                problemas.append(
                    f"[{v['id']}] no puede retirarse: su historial contiene "
                    f"{sorted(set(previos))}"
                )
            # sin datos adquiridos
            for _, e in historial[:i]:
                if e.get("theta_B2") is not None:
                    problemas.append(
                        f"[{v['id']}] no puede retirarse: theta_B2 no es null"
                    )
                    break
            # forma
            if ret.get("tipo_entrada") != rp["forma"]["tipo_entrada"]:
                problemas.append(
                    f"[{v['id']}] la entrada {n_ret} de retirada debe ser de tipo "
                    f"'{rp['forma']['tipo_entrada']}'"
                )
            for campo in rp["forma"]["campos_obligatorios_adicionales"]:
                if not ret.get(campo):
                    problemas.append(
                        f"[{v['id']}] la entrada {n_ret} de retirada carece del "
                        f"campo obligatorio '{campo}'"
                    )
            # una sola vez: una ficha sucesora no puede a su vez retirarse
            if any(e.get(campo_suc) for _, e in historial[:i]):
                problemas.append(
                    f"[{v['id']}] es una ficha sucesora ({campo_suc}) y no puede "
                    f"retirarse a su vez: {rp['reproposicion']['una_sola_vez']['regla']}"
                )

    # verificacion de las sucesoras
    for v in variables.values():
        destino = v["entrada_operativa"].get(campo_suc)
        if not destino:
            continue
        if destino not in retirados:
            problemas.append(
                f"[{v['id']}] {campo_suc} = '{destino}', que no esta en "
                f"RETIRADA_EN_PROPUESTA"
            )
        if v["entrada_operativa"].get("referencia_entrada_anterior") == destino:
            problemas.append(
                f"[{v['id']}] usa referencia_entrada_anterior hacia el id "
                f"retirado '{destino}'. {rp['reproposicion']['prohibicion_de_forma']}"
            )
        if not v["entrada_operativa"].get("declaracion_de_sesgo"):
            problemas.append(
                f"[{v['id']}] ficha sucesora sin declaracion_de_sesgo. "
                f"{rp['reproposicion']['declaracion_de_sesgo_obligatoria']}"
            )

    return problemas


def hash_de_medida(entrada, doc):
    """
    ficha_congelada.hash_de_medida (enmienda 32).

    Identidad FORMAL de una medida. Se CALCULA, nunca se almacena: un hash
    guardado puede divergir del contenido que dice resumir.

    Devuelve None si la ficha no contiene todos los campos de medida. Una ficha
    se construye por etapas y comparar hashes de subconjuntos distintos de
    campos no significa nada.

    Canonizacion identica a la de cadena.py, que es la declarada en
    registro.json -> meta.canonizacion. No se define convencion nueva y no se
    normaliza el contenido: decidir que diferencias "no son sustanciales" seria
    clasificacion semantica.
    """
    campos = ruta(doc, "ficha_congelada.campos_de_definicion_de_medida.lista")
    if any(c not in entrada for c in campos):
        return None
    cuerpo = {c: entrada[c] for c in campos}
    canon = json.dumps(
        cuerpo, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _colisiones_de_medida(variables, doc):
    """
    ficha_congelada.hash_de_medida.regla_de_colision.

    Colision entre ids RESUELTOS distintos: aborto (reproposicion exacta de una
    medida ya registrada). Colision dentro del mismo id: esperada y correcta,
    la impone limite_de_la_sustitucion.

    ALCANCE DECLARADO: esto NO implementa una_sola_vez. Solo bloquea la
    reproposicion exacta. Ver hash_de_medida.que_NO_protege.
    """
    por_hash = {}
    for v in variables.values():
        for n, e in v["historial"]:
            h = hash_de_medida(e, doc)
            if h:
                por_hash.setdefault(h, {}).setdefault(v["id"], []).append(n)

    problemas = []
    for h, ids in por_hash.items():
        if len(ids) > 1:
            detalle = ", ".join(f"'{i}' (entrada(s) {ns})" for i, ns in sorted(ids.items()))
            problemas.append(
                f"hash de medida {h[:16]}... compartido por ids distintos: "
                f"{detalle}. Reproposicion exacta de una medida ya registrada"
            )
    return problemas


def _existe_ruta(doc, camino):
    """
    ficha_congelada.alcance.aislamiento_del_resolver.

    Comprueba EXISTENCIA y devuelve un booleano. Nunca devuelve contenido de la
    doctrina. Es la unica funcion a la que se le permite recibir una cadena
    procedente de registro.json, y por construccion no puede convertirla en un
    valor utilizable por el motor. No usar ruta() aqui: ruta() devuelve valor.
    """
    actual = doc
    for parte in camino.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return False
        actual = actual[parte]
    return True


def _inventario_de_referencias(entrada, doc):
    """
    ficha_congelada.alcance.inventario_de_referencias (enmienda 30).

    Lista las cadenas de la ficha que coinciden con la sintaxis de una ruta
    doctrinal, junto a si esa ruta existe hoy. Es un inventario, NO un
    diagnostico: no lleva severidad, no distingue tipos de campo y no bloquea.
    Una ruta que no resuelve puede ser una referencia historica correcta.
    """
    claves = sorted(doc.keys())
    filas = []
    for camino, valor in _recorrer(entrada):
        if not isinstance(valor, str):
            continue
        for raiz in claves:
            marca = f"{raiz}."
            if marca not in valor:
                continue
            resto = valor.split(marca, 1)[1]
            token = marca + "".join(
                c for c in resto.split()[0] if c.isalnum() or c in "._"
            )
            token = token.rstrip(".")
            filas.append({
                "campo": camino,
                "referencia": token,
                "resuelve_en_doctrina_vigente": _existe_ruta(doc, token),
            })
            break
    return filas


def _comparar_ficha_sustitutiva(variable, doc):
    """
    ficha_congelada.migracion_de_fichas.

    DECISION DE IMPLEMENTACION DECLARADA (2026-09-04, validada por el usuario):
    la doctrina dice dos cosas en el mismo parrafo. La primera frase describe una
    lista blanca estricta; la segunda dice literalmente que "filtro.py compara
    ambas entradas y aborta si difiere alguno" refiriendose a los campos de
    medida. Se implementa la segunda: aborta solo por campos de medida. Las
    demas diferencias se reportan sin abortar. La lista blanca estricta abortaria
    contra la entrada 18 del propio registro (difiere en nota y fecha_registro).
    """
    problemas, avisos = [], []
    mig = ruta(doc, "ficha_congelada.migracion_de_fichas")

    lista = variable["historial"]
    n_ult, ultima = lista[-1]
    if ultima.get("tipo_entrada") != "ficha_congelada" or len(lista) < 2:
        return problemas, avisos

    fichas_previas = [(n, e) for n, e in lista[:-1] if e.get("mascara")]
    if not fichas_previas:
        return problemas, avisos
    n_ant, anterior = fichas_previas[-1]

    if any(e.get("estado") == "EN_TEST" for _, e in lista[:-1]):
        problemas.append(mig["prohibido_tras_en_test"])
        return problemas, avisos

    # Enmienda 31 parte A: la lista se lee de ficha_congelada.
    # campos_de_definicion_de_medida.lista. Queda PROHIBIDO derivarla parseando
    # el texto en prosa de limite_de_la_sustitucion, como hacia la version
    # anterior: una reescritura del parrafo cambiaba en silencio el alcance de
    # esta prohibicion.
    campos_medida = ruta(doc, "ficha_congelada.campos_de_definicion_de_medida.lista")

    for c in campos_medida:
        if anterior.get(c) != ultima.get(c):
            problemas.append(
                f"ficha sustitutiva (entrada {n_ult}) difiere de la entrada {n_ant} "
                f"en el campo de medida '{c}'. Prohibido"
            )

    otros = sorted(
        k for k in set(anterior) | set(ultima)
        if k not in campos_medida
        and k not in ("hash", "hash_anterior", "motivo_sustitucion")
        and anterior.get(k) != ultima.get(k)
    )
    if otros:
        avisos.append(
            f"ficha sustitutiva (entrada {n_ult} sobre {n_ant}): campos NO de medida "
            f"que difieren: {otros}. Se reporta, no aborta (decision declarada)"
        )

    return problemas, avisos


def fase2_admision(doc, variables, consumo, lote, inventario=None):
    candidatas, problemas, avisos = [], [], []
    if inventario is None:
        inventario = []

    problemas += _bloqueos_globales(doc)

    max_prop = ruta(doc, "presupuesto.propuestas_maximas_por_trimestre")
    max_fam = ruta(doc, "presupuesto.familias_nuevas_maximas_por_trimestre")
    familias_catalogo = {f["id"] for f in ruta(doc, "catalogo_familias.familias")}

    del_lote = [v for v in variables.values() if v["lote"] == lote]
    if not del_lote:
        abortar(f"el lote '{lote}' no contiene ninguna variable en el registro")

    en_propuesta = [v for v in del_lote if v["estado"] == "PROPUESTA"]
    if not en_propuesta:
        avisos.append(f"el lote {lote} no tiene ninguna variable en PROPUESTA")

    consumido = consumo.get(lote, 0)
    if consumido + len(en_propuesta) > max_prop:
        problemas.append(
            f"presupuesto excedido en {lote}: {consumido} consumidas + "
            f"{len(en_propuesta)} a transitar > maximo {max_prop}"
        )

    familias_nuevas = {v["familia"] for v in en_propuesta} - familias_catalogo
    if len(familias_nuevas) > max_fam:
        problemas.append(
            f"familias nuevas excedidas en {lote}: {sorted(familias_nuevas)} "
            f"> maximo {max_fam}"
        )

    for v in en_propuesta:
        e = v["entrada_operativa"]
        for fila in _inventario_de_referencias(e, doc):
            fila["variable"] = v["id"]
            inventario.append(fila)
        p = _validar_ficha(e, doc)
        ps, av = _comparar_ficha_sustitutiva(v, doc)
        p += ps
        avisos += av
        if p:
            problemas += [f"[{v['id']}] {x}" for x in p]
        else:
            candidatas.append(v)

    return candidatas, problemas, avisos


# =====================================================================
# FASE 3 — DATOS, MASCARA Y PARTICION
# =====================================================================

def cargar_precio(path, doc):
    fp = ruta(doc, "fuente_de_precio")

    sha_declarado = fp["snapshot"].get("sha256")
    sha_real = sha256_fichero(path)
    if sha_declarado and sha_real != sha_declarado:
        abortar(
            f"el snapshot de precio no coincide con la doctrina: "
            f"declarado {sha_declarado[:16]}..., leido {sha_real[:16]}..."
        )

    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    col_f = cols.get("fecha") or cols.get("date") or cols.get("time")
    col_p = cols.get("cierre") or cols.get("close") or cols.get("precio")
    if not col_f or not col_p:
        abortar(f"el snapshot {path} no tiene columnas de fecha y cierre reconocibles")

    df[col_f] = pd.to_datetime(df[col_f], utc=True).dt.tz_localize(None).dt.normalize()

    dup = df[col_f].duplicated(keep="last").sum()
    if dup:
        df = df.drop_duplicates(subset=[col_f], keep="last")

    s = df.set_index(col_f)[col_p].astype(float).sort_index()

    # Huecos: se arrastra el ultimo cierre un maximo de 2 dias consecutivos.
    completo = pd.date_range(s.index.min(), s.index.max(), freq="D")
    huecos = completo.difference(s.index)
    if len(huecos):
        rachas, actual = [], []
        for d in huecos:
            if actual and (d - actual[-1]).days == 1:
                actual.append(d)
            else:
                if actual:
                    rachas.append(actual)
                actual = [d]
        rachas.append(actual)
        peor = max(len(r) for r in rachas)
        if peor >= 3:
            mala = [r for r in rachas if len(r) >= 3][0]
            abortar(
                f"hueco de {peor} dias consecutivos en la serie de precio desde "
                f"{mala[0].date()}. La serie se parte (fuente_de_precio.dias_faltantes)"
            )
        s = s.reindex(completo).ffill(limit=2)

    return s, {"duplicados_resueltos": int(dup), "sha256_snapshot": sha_real,
               "dias": int(len(s)), "desde": str(s.index.min().date()),
               "hasta": str(s.index.max().date())}


def cargar_metrica(path, fecha_fin):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    col_f = cols.get("fecha") or cols.get("date")
    col_v = [c for c in df.columns if c != col_f][0]
    df[col_f] = pd.to_datetime(df[col_f], utc=True).dt.tz_localize(None).dt.normalize()
    s = df.set_index(col_f)[col_v].astype(float).sort_index()

    posteriores = s.index[s.index > fecha_fin]
    if len(posteriores):
        abortar(
            f"la serie de la metrica contiene {len(posteriores)} observaciones "
            f"posteriores a fecha_propuesta ({fecha_fin.date()}). "
            f"filtro.py aborta, no trunca en silencio (protocolo.ventana_temporal)"
        )
    return s


def _operador_mascara(ficha):
    """
    La direccion de la mascara solo es recuperable del campo 'inclusividad'.
    ficha_congelada.mascara.campos_obligatorios no incluye un campo 'operador'
    explicito. Se reporta como cabo suelto; no se inventa.
    """
    txt = str(ficha["mascara"]["inclusividad"])
    for op in ("<=", ">=", "<", ">"):
        if op in txt:
            return op
    abortar(
        f"no se puede determinar el operador de la mascara desde "
        f"inclusividad='{txt}'. La ficha no declara la direccion de forma legible"
    )


def construir_mascara(metrica, ficha):
    m = ficha["mascara"]
    if m["tipo_ventana"] != "movil":
        abortar(f"tipo_ventana '{m['tipo_ventana']}' no implementado")
    if not m["solo_informacion_anterior_a_t"]:
        abortar("la ficha permite look-ahead en el calculo del percentil")

    ventana = int(m["longitud_ventana_dias"])
    q = float(m["q_percentil"]) / 100.0
    op = _operador_mascara(ficha)

    # closed='left' => la ventana termina en t-1: solo informacion anterior a t.
    umbral = metrica.rolling(f"{ventana}D", closed="left").quantile(q)

    if op == "<":
        mask = metrica < umbral
    elif op == "<=":
        mask = metrica <= umbral
    elif op == ">":
        mask = metrica > umbral
    else:
        mask = metrica >= umbral

    warm = int(m["warm_up_dias"])
    inicio = metrica.index.min() + pd.Timedelta(days=warm)
    mask = mask[mask.index >= inicio]
    mask = mask[umbral.reindex(mask.index).notna()]
    return mask.astype(bool), {"operador": op, "q": m["q_percentil"],
                               "ventana_dias": ventana, "warm_up_dias": warm,
                               "primer_dia_valido": str(mask.index.min().date())}


def particionar(indice, doc):
    minimo_anios = ruta(doc, "protocolo.particion_datos.minimo_por_bloque_anios")
    ini, fin = indice.min(), indice.max()
    total = (fin - ini).days
    corte = ini + pd.Timedelta(days=total // 2)

    b1 = indice[(indice >= ini) & (indice <= corte)]
    b2 = indice[indice > corte]

    anios1 = (b1.max() - b1.min()).days / 365.25 if len(b1) else 0
    anios2 = (b2.max() - b2.min()).days / 365.25 if len(b2) else 0
    suficiente = anios1 >= minimo_anios and anios2 >= minimo_anios

    return b1, b2, {
        "fecha_corte_bloques": str(corte.date()),
        "anios_bloque_1": round(anios1, 2),
        "anios_bloque_2": round(anios2, 2),
        "minimo_por_bloque_anios": minimo_anios,
        "suficiente": bool(suficiente),
    }


def tramos_de(indice, n_tramos):
    ini, fin = indice.min(), indice.max()
    total = (fin - ini).days
    bordes = [ini + pd.Timedelta(days=round(total * k / n_tramos)) for k in range(n_tramos + 1)]
    out = []
    for k in range(n_tramos):
        a = bordes[k]
        b = bordes[k + 1] if k == n_tramos - 1 else bordes[k + 1] - pd.Timedelta(days=1)
        out.append((a, b))
    return out


def retorno_N(precio, N):
    return (precio.shift(-N) / precio - 1).rename("retorno_N")


def base_gate3(precio, doc):
    series = ruta(doc, "protocolo.gates_cualitativos.parametros."
                       "contribucion_incremental_R2.base.series")
    out = {}
    for nombre in series:
        if nombre == "mayer":
            out[nombre] = precio / precio.rolling(200).mean()
        elif nombre == "vol30":
            out[nombre] = precio.pct_change().rolling(30).std()
        elif nombre == "mom30":
            out[nombre] = precio / precio.shift(30) - 1
        else:
            abortar(f"la base fija del gate 3 declara la serie '{nombre}', no implementada")
    return pd.DataFrame(out)


# =====================================================================
# FASE 4 — GATES
# =====================================================================

def _pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def spearman(x, y):
    return _pearson(pd.Series(np.asarray(x, float)).rank().values,
                    pd.Series(np.asarray(y, float)).rank().values)


def _r2_np(X, y):
    X = np.column_stack([np.ones(len(y)), X])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ beta
    sst = ((y - y.mean()) ** 2).sum()
    return float(1 - (res ** 2).sum() / sst) if sst > 0 else float("nan")


def obs_efectivas(indice, N):
    """Unidad declarada: dias con dato dividido por N. NO dias activos."""
    return len(indice) / N


def _preparar_tramos(indice, ret, tramos):
    """Alinea el retorno con el indice de la mascara una sola vez."""
    r = ret.reindex(indice).values
    ok = np.isfinite(r)
    sel = [((indice >= a) & (indice <= b) & ok) for a, b in tramos]
    return r, sel


def _cors_por_tramo(mvals, rvals, selectores):
    cors = []
    for sel in selectores:
        if sel.sum() < 3:
            cors.append(float("nan"))
        else:
            cors.append(spearman(mvals[sel].astype(float), rvals[sel]))
    return cors


def umbral_por_rotacion(estadistico, mask, doc):
    p = ruta(doc, "protocolo.gates_cualitativos.parametros.metodo_de_umbral")
    rng = np.random.default_rng(p["semilla"])
    n = len(mask)
    # La doctrina fija percentil, n_rotaciones y semilla, pero no el sorteo de
    # los desplazamientos. Se declara: enteros uniformes en [1, n-1] con esa semilla.
    offsets = rng.integers(1, max(2, n), size=p["n_rotaciones"])
    base = np.asarray(mask.values if hasattr(mask, "values") else mask)
    vals = []
    for k in offsets:
        v = estadistico(np.roll(base, int(k)))
        if np.isfinite(v):
            vals.append(v)
    if len(vals) < p["n_rotaciones"] // 2:
        abortar("el nulo por rotacion no produjo suficientes realizaciones finitas")
    return float(np.percentile(vals, p["percentil"])), len(vals)


def racha_media(mask):
    v = mask.astype(int).values
    rachas, actual = [], 0
    for x in v:
        if x:
            actual += 1
        elif actual:
            rachas.append(actual)
            actual = 0
    if actual:
        rachas.append(actual)
    return float(np.mean(rachas)) if rachas else 0.0


def gate1(mask_b1, ret, tramos, doc):
    par = ruta(doc, "protocolo.gates_cualitativos.parametros.magnitud_en_tramos")
    N = ruta(doc, "definicion_de_efecto.horizonte_N.valor")
    minimo = par["observaciones_efectivas_minimas_por_tramo"]

    insuficientes = []
    for k, (a, b) in enumerate(tramos, start=1):
        idx = mask_b1.index[(mask_b1.index >= a) & (mask_b1.index <= b)]
        if obs_efectivas(idx, N) < minimo:
            insuficientes.append((k, round(obs_efectivas(idx, N), 1)))

    rvals, selectores = _preparar_tramos(mask_b1.index, ret, tramos)

    def stat(mvals):
        cors = [c for c in _cors_por_tramo(mvals, rvals, selectores) if np.isfinite(c)]
        return abs(float(np.median(cors))) if len(cors) == len(tramos) else float("nan")

    obs = stat(mask_b1.values)
    umbral, n_val = umbral_por_rotacion(stat, mask_b1, doc)
    cors = _cors_por_tramo(mask_b1.values, rvals, selectores)

    if not np.isfinite(obs):
        vacios = [k for k, c in enumerate(cors, start=1) if not np.isfinite(c)]
        abortar(
            f"gate 1 no evaluable: la correlacion es indefinida en el/los tramo(s) "
            f"{vacios} (la mascara no varia dentro de ese tramo). La doctrina no "
            f"define este caso; no se decide por codigo."
        )

    return {
        "gate": 1, "vinculante": True, "estadistico": obs, "umbral": umbral,
        "n_realizaciones_nulo": n_val, "correlaciones_por_tramo": cors,
        "tramos_insuficientes": insuficientes,
        "pasa": bool(np.isfinite(obs) and obs >= umbral and not insuficientes),
        "insuficiencia": bool(insuficientes),
        "criterio": par["criterio"], "exige_signo": par["exige_signo"],
    }


def gate2(mask_b1, precio, N, doc):
    par = ruta(doc, "protocolo.gates_cualitativos.parametros.anticipacion")
    fwd = (precio.shift(-N) / precio - 1).reindex(mask_b1.index)
    bwd = (precio / precio.shift(N) - 1).reindex(mask_b1.index)

    def theta(serie):
        d = pd.DataFrame({"m": mask_b1, "r": serie.reindex(mask_b1.index)}).dropna()
        if d["m"].sum() == 0 or (~d["m"]).sum() == 0:
            return float("nan")
        return float(d[d["m"]]["r"].median() - d[~d["m"]]["r"].median())

    tf, tb = theta(fwd), theta(bwd)
    cociente = abs(tf) / abs(tb) if tb and np.isfinite(tb) and abs(tb) > 0 else float("nan")
    lectura = ("no evaluable" if not np.isfinite(cociente) else
               "el efecto hacia adelante domina al de hacia atras" if cociente > 1.2 else
               "el efecto hacia atras domina: parece contemporaneo, no anticipatorio"
               if cociente < 0.8 else "empate: no distingue anticipacion de regimen")

    return {"gate": 2, "vinculante": False, "afecta_a_veredicto": False,
            "theta_fwd": tf, "theta_bwd": tb, "cociente": cociente,
            "lectura": lectura, "ambito": par["ambito"]}


def gate3(mask_b1, ret, base, doc):
    par = ruta(doc, "protocolo.gates_cualitativos.parametros.contribucion_incremental_R2")
    N = ruta(doc, "definicion_de_efecto.horizonte_N.valor")

    datos = base.reindex(mask_b1.index).join(ret.reindex(mask_b1.index)).dropna()
    efectivas = obs_efectivas(datos.index, N)
    minimo = par["observaciones_efectivas_minimas"]

    cols = list(base.columns)
    X0 = datos[cols].values
    y = datos["retorno_N"].values
    pos = mask_b1.index.get_indexer(datos.index)   # alineacion mascara -> filas usadas
    r2_base = _r2_np(X0, y)

    def stat(mvals):
        m = np.asarray(mvals, float)[pos]
        if m.std() == 0:
            return float("nan")
        return (_r2_np(np.column_stack([X0, m]), y) - r2_base) * 100

    obs = stat(mask_b1.values)
    umbral, n_val = umbral_por_rotacion(stat, mask_b1, doc)

    return {"gate": 3, "vinculante": True, "delta_r2_pp": obs, "umbral_pp": umbral,
            "n_realizaciones_nulo": n_val, "observaciones_efectivas": round(efectivas, 1),
            "minimo": minimo, "base": cols,
            "insuficiencia": bool(efectivas < minimo),
            "pasa": bool(np.isfinite(obs) and obs >= umbral and efectivas >= minimo)}


def gate4(cors, doc):
    par = ruta(doc, "protocolo.gates_cualitativos.parametros.coherencia_de_signo_en_tramos")
    validos = [c for c in cors if np.isfinite(c) and c != 0]
    pasa = len(validos) == len(cors) and len({np.sign(c) for c in validos}) == 1
    return {"gate": 4, "vinculante": True, "signos": [int(np.sign(c)) if np.isfinite(c) else None
                                                      for c in cors],
            "pasa": bool(pasa), "advertencia": par["advertencia_obligatoria"],
            "tasa_bajo_ruido_medida": par["tasa_bajo_ruido_medida"]}


# =====================================================================
# FASE 5 — P-VALOR SOBRE BLOQUE_2
# =====================================================================

def _media_recortada(x, prop):
    x = np.sort(np.asarray(x, float))
    k = int(len(x) * prop)
    return float(x[k:len(x) - k].mean()) if len(x) - 2 * k > 0 else float("nan")


def _hodges_lehmann(a, b, semilla, tope=400):
    """Desplazamiento de Hodges-Lehmann: mediana de las diferencias por pares."""
    rng = np.random.default_rng(semilla)
    if len(a) > tope:
        a = rng.choice(a, tope, replace=False)
    if len(b) > tope:
        b = rng.choice(b, tope, replace=False)
    return float(np.median(np.subtract.outer(a, b)))


def episodios_independientes(fechas, dias_episodio):
    eps = []
    for d in fechas:
        if not eps or (d - eps[-1][-1]).days > dias_episodio:
            eps.append([d])
        else:
            eps[-1].append(d)
    return eps


def test_permutacion(mask_b2, ret, doc, signo_esperado):
    tp = ruta(doc, "protocolo.test_de_permutacion")
    formulas = tp["capa_de_interpretacion"]["formulas"]
    dias_ep = tp["dias_episodio"]["valor_bajo_N_30"]
    N = ruta(doc, "definicion_de_efecto.horizonte_N.valor")
    if tp["dias_episodio"]["regla"].startswith("dias_episodio = max(21, N)"):
        dias_ep = max(21, N)

    z = pd.DataFrame({"m": mask_b2, "retorno_N": ret.reindex(mask_b2.index)}).dropna()
    sel = z[z["m"]]

    if len(sel) < tp["observaciones_enmascaradas_minimas"]:
        return {"insuficiencia": True,
                "motivo": f"solo {len(sel)} observaciones enmascaradas "
                          f"(minimo {tp['observaciones_enmascaradas_minimas']})"}

    eps = episodios_independientes(sel.index, dias_ep)
    if len(eps) < tp["episodios_independientes_minimos"]:
        return {"insuficiencia": True, "episodios": len(eps),
                "motivo": f"solo {len(eps)} episodios independientes "
                          f"(minimo {tp['episodios_independientes_minimos']}, "
                          f"dias_episodio={dias_ep})"}

    real = float(z[z["m"]]["retorno_N"].median() - z[~z["m"]]["retorno_N"].median())
    vals = z["retorno_N"].values
    n = len(sel)
    rng = np.random.default_rng(tp["semilla"])

    difs = []
    for _ in range(tp["n_permutaciones"]):
        i = rng.integers(0, max(1, len(vals) - n))
        bloque = vals[i:i + n]
        resto = np.delete(vals, slice(i, i + n))
        difs.append(np.median(bloque) - np.median(resto))
    difs = np.array(difs)

    if signo_esperado == "positivo":
        p = float((difs >= real).mean())
    elif signo_esperado == "negativo":
        p = float((difs <= real).mean())
    elif signo_esperado == "bilateral":
        p = float((np.abs(difs) >= abs(real)).mean())
    else:
        abortar(f"signo_esperado '{signo_esperado}' fuera de los valores permitidos")

    a = z[z["m"]]["retorno_N"].values
    b = z[~z["m"]]["retorno_N"].values
    hl = _hodges_lehmann(a, b, semilla=tp["semilla"])
    recortada = _media_recortada(a, 0.10) - _media_recortada(b, 0.10)

    return {"insuficiencia": False, "p_valor": p, "theta_B2": real,
            "formula_usada": formulas[signo_esperado], "signo_esperado": signo_esperado,
            "episodios": len(eps), "dias_episodio": dias_ep,
            "observaciones_enmascaradas": int(n),
            "robustez": {"hodges_lehmann": hl, "media_recortada_10pct": recortada}}


# =====================================================================
# FASE 6 — BENJAMINI-YEKUTIELI
# =====================================================================

def benjamini_yekutieli(pvalores, doc):
    cm = ruta(doc, "protocolo.correccion_multiple")
    q = cm["q_nominal"]
    m = max(3, len(pvalores))
    H = sum(1.0 / j for j in range(1, m + 1))

    orden = sorted(pvalores.items(), key=lambda kv: kv[1])
    k = 0
    for rango, (_, p) in enumerate(orden, start=1):
        if p <= (rango / m) * q / H:
            k = rango
    aceptados = {id_ for id_, _ in orden[:k]}
    umbral = (max(k, 1) / m) * q / H
    return aceptados, {"q_nominal": q, "m_efectivo": m, "H_m": round(H, 4),
                       "umbral_aplicado": umbral, "metodo": cm["metodo"]}


# =====================================================================
# FASE 7 — TRADUCCION Y SALIDA
# =====================================================================

def traducir(etiqueta_interna, doc, pasa_by=None):
    tabla = ruta(doc, "estados.mapeo_salida_filtro_py.tabla")
    validos = {e["id"]: e for e in ruta(doc, "estados.lista")}

    if etiqueta_interna == "PASA":
        estado = "EN_CONFIRMACION" if pasa_by else _RAMA_BY_NEGATIVA
    else:
        if etiqueta_interna not in tabla:
            abortar(f"etiqueta interna '{etiqueta_interna}' sin fila en el mapeo de salida")
        estado = tabla[etiqueta_interna].split(" ")[0]

    if estado not in validos:
        abortar(f"filtro.py iba a emitir '{estado}', fuera de la lista cerrada")
    if validos[estado].get("emision_permitida") is False:
        abortar(f"filtro.py iba a emitir '{estado}', cuya emision esta prohibida "
                f"({validos[estado].get('nota', '')})")
    return estado


def cabecera(doc):
    return "\n".join([
        "=" * 72,
        f"CONTEXTO-BTC · filtro.py v2 · doctrina {ruta(doc, 'meta.version_esquema')}",
        f"SHA-256 v2.json: {_SHA_DOCTRINA}",
        f"ejecucion: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "=" * 72,
        "",
        "DECLARACION OBLIGATORIA",
        ruta(doc, "meta.declaracion_obligatoria"),
        "",
        "POTENCIA MEDIDA",
        ruta(doc, "potencia_medida.texto_literal"),
        "=" * 72,
    ])


# =====================================================================
# ORQUESTACION
# =====================================================================

def ejecutar(args):
    doc, reg, msg_cadena = fase0_arranque(args.doctrina, args.registro)
    print(cabecera(doc))
    print(f"\n[FASE 0] {msg_cadena}")
    print("[FASE 0] registro.json sin maximos de presupuesto: correcto")

    variables, consumo, incidencias = fase1_resolver(doc, reg)
    print(f"\n[FASE 1] {len(variables)} variables resueltas desde "
          f"{len(reg['entradas'])} entradas")
    print(f"[FASE 1] consumo derivado por lote: {consumo or '{}'} (coincide con los contadores)")
    for i in incidencias:
        print(f"[FASE 1] incidencia: {i}")

    inventario = []
    candidatas, problemas, avisos = fase2_admision(
        doc, variables, consumo, args.lote, inventario
    )
    print(f"\n[FASE 2] lote {args.lote}: {len(candidatas)} candidatas admisibles a EN_TEST")
    for a in avisos:
        print(f"[FASE 2] aviso: {a}")

    # Inventario de referencias (enmienda 30). Sin severidad, no bloquea.
    if inventario:
        print("\n[FASE 2] inventario de referencias doctrinales citadas en fichas")
        print("         (descriptivo, sin severidad; no condiciona ninguna transicion)")
        for f in inventario:
            estado = "vigente" if f["resuelve_en_doctrina_vigente"] else "no resuelve hoy"
            print(f"  - [{f['variable']}] {f['campo']}: {f['referencia']}  ->  {estado}")

    if problemas:
        print("\n[FASE 2] BLOQUEOS:")
        for p in problemas:
            print(f"  - {p}")
        abortar(f"{len(problemas)} bloqueo(s) impiden ejecutar el lote {args.lote}")

    if args.solo_comprobar:
        print("\n[--solo-comprobar] fases 0-2 superadas. No se ejecuta ningun test.")
        return 0

    if not args.precio:
        abortar("falta --precio: el snapshot congelado de la serie de precio")

    precio, meta_precio = cargar_precio(args.precio, doc)
    print(f"\n[FASE 3] precio: {meta_precio['dias']} dias, "
          f"{meta_precio['desde']} a {meta_precio['hasta']}")

    N = ruta(doc, "definicion_de_efecto.horizonte_N.valor")
    n_tramos = ruta(doc, "protocolo.gates_cualitativos.parametros.definicion_de_tramos.n_tramos")
    base = base_gate3(precio, doc)
    ret = retorno_N(precio, N)

    rutas_metrica = dict(x.split("=", 1) for x in (args.metrica or []))
    resultados, pvalores = {}, {}

    for v in candidatas:
        ficha = v["entrada_operativa"]
        vid = v["id"]
        if vid not in rutas_metrica:
            abortar(f"falta --metrica {vid}=<csv> para la variable admitida '{vid}'")

        fecha_fin = pd.Timestamp(ficha["fecha_fin_ventana_test"])
        metrica = cargar_metrica(rutas_metrica[vid], fecha_fin)
        mask, meta_mask = construir_mascara(metrica, ficha)
        mask = mask[mask.index <= fecha_fin]

        b1, b2, meta_part = particionar(mask.index, doc)
        r = {"id": vid, "mascara": meta_mask, "particion": meta_part,
             "racha_media_mascara": round(racha_media(mask), 1)}

        if r["racha_media_mascara"] > 60:
            r["aviso_racha"] = ruta(doc, "protocolo.gates_cualitativos.parametros."
                                        "metodo_de_umbral.limitacion_declarada")

        if not meta_part["suficiente"]:
            r["estado"] = traducir("PROVISIONAL", doc)
            r["motivo"] = (f"bloques de {meta_part['anios_bloque_1']} y "
                           f"{meta_part['anios_bloque_2']} anios, minimo "
                           f"{meta_part['minimo_por_bloque_anios']}")
            resultados[vid] = r
            continue

        m1, m2 = mask.loc[b1], mask.loc[b2]
        tr = tramos_de(b1, n_tramos)
        r["tramos"] = [[str(a.date()), str(b.date())] for a, b in tr]

        g1 = gate1(m1, ret, tr, doc)
        g2 = gate2(m1, precio, N, doc)
        g3 = gate3(m1, ret, base, doc)
        g4 = gate4(g1["correlaciones_por_tramo"], doc)
        r["gates"] = {"1": g1, "2": g2, "3": g3, "4": g4}

        # Diagnostico: observaciones de bloque_1 cuyo retorno usa precios de bloque_2.
        r["diagnostico_solape_bloques"] = int(
            (b1 > b1.max() - pd.Timedelta(days=N)).sum())

        if g1["insuficiencia"] or g3["insuficiencia"]:
            r["estado"] = traducir("PROVISIONAL", doc)
            r["motivo"] = "observaciones efectivas por debajo del minimo en la capa de gates"
        elif not g1["pasa"]:
            r["estado"] = traducir("RECHAZADA_paso_1", doc)
        elif not g3["pasa"]:
            r["estado"] = traducir("RECHAZADA_paso_3", doc)
        elif not g4["pasa"]:
            r["estado"] = traducir("RECHAZADA_coherencia_signo", doc)
        else:
            perm = test_permutacion(m2, ret, doc, ficha["signo_esperado"])
            r["permutacion"] = perm
            if perm["insuficiencia"]:
                r["estado"] = traducir("PROVISIONAL", doc)
                r["motivo"] = perm["motivo"]
            else:
                pvalores[vid] = perm["p_valor"]
                r["estado"] = "PENDIENTE_BY"

        resultados[vid] = r

    by_meta = None
    if pvalores:
        aceptados, by_meta = benjamini_yekutieli(pvalores, doc)
        for vid in pvalores:
            resultados[vid]["estado"] = traducir("PASA", doc, pasa_by=vid in aceptados)
        print(f"\n[FASE 6] BY: m={by_meta['m_efectivo']}, q={by_meta['q_nominal']}, "
              f"umbral aplicado {by_meta['umbral_aplicado']:.4f}")

    informe = {
        "sha256_v2_json": _SHA_DOCTRINA,
        "doctrina": ruta(doc, "meta.version_esquema"),
        "lote": args.lote,
        "declaracion_obligatoria": ruta(doc, "meta.declaracion_obligatoria"),
        "potencia_medida": ruta(doc, "potencia_medida.texto_literal"),
        "incidencias_registro": incidencias,
        "avisos": avisos,
        "presupuesto_derivado": consumo,
        "precio": meta_precio,
        "correccion_multiple": by_meta,
        "resultados": resultados,
        "huecos_de_doctrina_detectados": [
            "estados.mapeo_salida_filtro_py.tabla no tiene fila para la rama negativa "
            "del umbral BY. filtro.py usa RECHAZADA_PVALOR de la lista cerrada.",
            "ficha_congelada.mascara.campos_obligatorios no incluye un campo 'operador': "
            "la direccion de la mascara se deduce de 'inclusividad'.",
            "protocolo.gates_cualitativos.parametros.metodo_de_umbral no especifica el "
            "sorteo de desplazamientos del nulo por rotacion, ni que hacer con las "
            "rotaciones cuya realizacion es indefinida (se descartan y se cuenta cuantas "
            "quedan).",
            "La doctrina no define que ocurre si un tramo del bloque_1 no tiene ninguna "
            "observacion con la mascara activa: la correlacion queda indefinida. "
            "filtro.py aborta en vez de decidirlo por su cuenta.",
        ],
        "no_escribe_registro": "filtro.py no modifica registro.json. La entrada de "
                               "transicion se escribe aparte con cadena.anadir.",
    }

    print("\n" + "=" * 72)
    for vid, r in resultados.items():
        print(f"{vid}: {r['estado']}" + (f"  ({r.get('motivo')})" if r.get("motivo") else ""))
    print("=" * 72)

    if args.informe:
        with open(args.informe, "w", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=1, default=str)
        print(f"informe escrito en {args.informe}")

    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Motor de validacion v2 de Contexto-BTC")
    ap.add_argument("--lote")
    ap.add_argument("--doctrina", default="v2.json")
    ap.add_argument("--registro", default="registro.json")
    ap.add_argument("--precio")
    ap.add_argument("--metrica", action="append",
                    help="id=ruta.csv (repetible)")
    ap.add_argument("--informe")
    ap.add_argument("--solo-comprobar", action="store_true")
    ap.add_argument(
        "--validar-entrada",
        help="Valida un fichero JSON con una entrada candidata contra la "
             "enmienda 31 ANTES de escribirla con cadena.py. No toca el registro."
    )
    args = ap.parse_args(argv)

    if args.validar_entrada:
        doc = _cargar_json(args.doctrina)
        entrada = _cargar_json(args.validar_entrada)
        problemas = prohibicion_prospectiva(entrada, doc)
        if problemas:
            print("RECHAZADA. No escribir esta entrada:")
            for p in problemas:
                print("  - " + p)
            return 1
        print("OK  la entrada no incumple la enmienda 31. "
              "Puede escribirse con cadena.py")
        return 0

    if not args.lote:
        ap.error("--lote es obligatorio salvo con --validar-entrada")

    try:
        return ejecutar(args)
    except Aborto as e:
        print("\n" + "!" * 72)
        print("ABORTA filtro.py")
        print(f"motivo: {e}")
        print(f"SHA-256 v2.json: {_SHA_DOCTRINA}")
        print("!" * 72)
        return 2


if __name__ == "__main__":
    sys.exit(main())
