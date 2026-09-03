"""
cadena.py — Integridad de registro.json para Contexto-BTC.

Modulo compartido. Sustituye la capacidad de escritura de build_registro.py.

Este modulo NO contiene ninguna regla del protocolo. Solo implementa la
aritmetica de hashes descrita en v2.json -> integridad y en
registro.json -> meta.canonizacion.

Tres operaciones:
    verificar(registro)               -> (ok, mensaje)
    anadir(registro, entrada)         -> registro nuevo, con hash calculado
    es_extension(viejo, nuevo)        -> (ok, mensaje)   # anti-truncamiento

CLI:
    python cadena.py verificar registro.json
    python cadena.py extension registro_anterior.json registro.json

Deliberadamente NO existe una funcion que reconstruya el registro desde cero.
Esa capacidad era la que convertia a build_registro.py en un riesgo.
"""

import hashlib
import json
import sys

GENESIS = "0" * 64


def _canonico(obj):
    """Serializacion canonica declarada en registro.json -> meta.canonizacion."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash_entrada(entrada):
    """SHA-256 de la entrada excluyendo su propio campo hash."""
    cuerpo = {k: v for k, v in entrada.items() if k != "hash"}
    return hashlib.sha256(_canonico(cuerpo)).hexdigest()


def verificar(registro):
    """Recorre la cadena completa. Devuelve (ok, mensaje)."""
    meta = registro.get("meta", {})
    entradas = registro.get("entradas", [])

    if meta.get("algoritmo_hash") != "sha256":
        return False, "meta.algoritmo_hash no es sha256"

    genesis = meta.get("genesis", GENESIS)
    previo = genesis

    for i, entrada in enumerate(entradas, start=1):
        if entrada.get("hash_anterior") != previo:
            return False, (
                f"entrada {i} ({entrada.get('id')}): hash_anterior no encadena. "
                f"esperado {previo[:16]}..., encontrado "
                f"{str(entrada.get('hash_anterior'))[:16]}..."
            )
        calculado = _hash_entrada(entrada)
        if calculado != entrada.get("hash"):
            return False, (
                f"entrada {i} ({entrada.get('id')}): hash no coincide. "
                f"contenido modificado despues de firmarse"
            )
        previo = entrada["hash"]

    n_declarado = meta.get("n_entradas")
    if n_declarado is not None and n_declarado != len(entradas):
        return False, (
            f"meta.n_entradas dice {n_declarado} pero hay {len(entradas)} entradas"
        )

    ultimo_declarado = meta.get("ultimo_hash")
    if ultimo_declarado is not None and ultimo_declarado != previo:
        return False, "meta.ultimo_hash no coincide con el ultimo eslabon"

    return True, f"cadena valida: {len(entradas)} entradas, ultimo {previo[:16]}..."


def anadir(registro, entrada):
    """
    Devuelve un registro NUEVO con la entrada anadida al final.

    No muta el registro recibido. Calcula hash_anterior y hash, y actualiza
    meta.n_entradas y meta.ultimo_hash. Verifica la cadena antes de anadir:
    sobre una cadena rota no se anade nada.
    """
    ok, msg = verificar(registro)
    if not ok:
        raise ValueError(f"no se anade sobre una cadena rota: {msg}")

    if "hash" in entrada or "hash_anterior" in entrada:
        raise ValueError(
            "la entrada no debe traer hash ni hash_anterior: los calcula este modulo"
        )

    entradas = list(registro.get("entradas", []))
    previo = entradas[-1]["hash"] if entradas else registro["meta"].get("genesis", GENESIS)

    nueva = dict(entrada)
    nueva["hash_anterior"] = previo
    nueva["hash"] = _hash_entrada(nueva)

    salida = json.loads(json.dumps(registro, ensure_ascii=False))
    salida["entradas"] = entradas + [nueva]
    salida["meta"]["n_entradas"] = len(salida["entradas"])
    salida["meta"]["ultimo_hash"] = nueva["hash"]
    return salida


def es_extension(viejo, nuevo):
    """
    Comprueba que 'nuevo' extiende a 'viejo' sin borrar ni alterar nada.

    La cadena de hashes por si sola detecta modificaciones, pero NO detecta
    que se hayan borrado entradas del final: una cadena truncada sigue
    verificando. Esta funcion cubre ese hueco comparando contra el estado
    anterior (por ejemplo, el commit previo en un GitHub Action).
    """
    ev, en = viejo.get("entradas", []), nuevo.get("entradas", [])

    if len(en) < len(ev):
        return False, (
            f"truncamiento: el registro paso de {len(ev)} a {len(en)} entradas"
        )

    for i, (a, b) in enumerate(zip(ev, en), start=1):
        if a.get("hash") != b.get("hash"):
            return False, f"entrada {i} ({a.get('id')}) fue modificada"

    ok, msg = verificar(nuevo)
    if not ok:
        return False, msg

    return True, f"extension valida: +{len(en) - len(ev)} entradas nuevas"


def _cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    if len(argv) >= 3 and argv[1] == "verificar":
        ok, msg = verificar(_cargar(argv[2]))
        print(("OK  " if ok else "FALLO  ") + msg)
        return 0 if ok else 1

    if len(argv) >= 4 and argv[1] == "extension":
        ok, msg = es_extension(_cargar(argv[2]), _cargar(argv[3]))
        print(("OK  " if ok else "FALLO  ") + msg)
        return 0 if ok else 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
