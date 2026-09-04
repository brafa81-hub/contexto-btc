"""
congelar_snapshot.py — Script de UN SOLO USO.

Escribe en v2.json el SHA-256 del snapshot de precio y cambia su estado.

Esto NO es una enmienda. fuente_de_precio.snapshot.regla ordena literalmente
registrar el SHA-256 en la doctrina antes de ejecutar ningun test: rellenar el
hueco es la operacion prevista, no una modificacion de la regla.

Verificaciones previas obligatorias:
  - SHA-256 de v2.json de partida (doctrina 2.5.0, tras la enmienda 31)
  - snapshot.sha256 sigue a null y el estado sigue en PENDIENTE_PRIMER_LOTE
  - si el CSV esta presente en la carpeta, se recalcula su hash y se compara

Uso:
    python congelar_snapshot.py v2.json
"""

import hashlib
import json
import os
import sys

SHA_V2_ESPERADO = "862975383f72ed45900f24d4a8578639305faf68f8c4846ff6366ce078547015"
SHA_SNAPSHOT = "32c0b8ea8a66f01181032c3cb5b66c10ede867b12f6779d7bea8b19258627e49"
CSV = "snapshot_precio_btcusd.csv"
VERSION_ESPERADA = "2.5.0"


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
    if sha_ini != SHA_V2_ESPERADO:
        print(f"ABORTA: SHA-256 de v2.json {sha_ini}")
        print(f"        esperado          {SHA_V2_ESPERADO}")
        return 1

    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)

    if doc["meta"]["version_esquema"] != VERSION_ESPERADA:
        print("ABORTA: version_esquema inesperada")
        return 1

    snap = doc["fuente_de_precio"]["snapshot"]
    if snap.get("sha256") is not None:
        print("ABORTA: snapshot.sha256 ya tiene valor. No se sobrescribe.")
        return 1
    if snap.get("estado") != "PENDIENTE_PRIMER_LOTE":
        print(f"ABORTA: estado inesperado '{snap.get('estado')}'")
        return 1

    # Si el CSV esta al lado, se comprueba. Si no, se confia en la constante.
    if os.path.exists(CSV):
        real = sha256_fichero(CSV)
        if real != SHA_SNAPSHOT:
            print(f"ABORTA: el CSV presente tiene hash {real},")
            print(f"        pero se iba a congelar     {SHA_SNAPSHOT}")
            return 1
        print(f"OK  {CSV} verificado contra la constante")
    else:
        print(f"AVISO: {CSV} no esta en esta carpeta. No se pudo re-verificar.")

    snap["sha256"] = SHA_SNAPSHOT
    snap["estado"] = "CONGELADO"
    snap["congelacion"] = {
        "fecha": "2026-09-05",
        "fichero": CSV,
        "rango": "2015-01-01 a 2026-09-03",
        "filas": 4264,
        "dias_sin_dato": 0,
        "duplicados_resueltos": 0,
        "columnas": "fecha,cierre",
        "final_de_linea": "LF",
        "script": "snapshot_precio.py",
        "vela_incompleta_descartada": (
            "La API devolvio ademas la vela del 2026-09-04, que a la hora de la "
            "descarga aun no habia cerrado (cierra a las 00:00 UTC del "
            "2026-09-05). Se descarto por la fecha de corte declarada en el "
            "script, no a mano."
        ),
        "eleccion_de_la_fecha_de_corte": (
            "2026-09-03 es la ultima vela diaria UTC completa en el momento de "
            "fijar la constante. Se declara como constante en el script y no se "
            "deriva de la fecha de ejecucion: si dependiese de cuando se lanza, "
            "el snapshot no seria reproducible."
        ),
        "limitacion_declarada": (
            "snapshot.sha256 es un campo escalar, pero la regla dice que cada "
            "lote congela su propio snapshot. Mientras solo exista un lote v2 "
            "activo no hay conflicto. Un segundo lote exigira convertir este "
            "bloque en una estructura por lote, y eso si sera una enmienda."
        ),
    }

    salida = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(salida)

    print("OK  snapshot congelado en v2.json")
    print(f"OK  SHA-256 nuevo de v2.json: {sha256_fichero(ruta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
