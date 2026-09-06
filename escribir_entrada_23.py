"""
escribir_entrada_23.py — SCRIPT DE UN SOLO USO.

Escribe la entrada 23: transicion de ssr_capstables a DESCARTADA_GATE_3.
Usa cadena.anadir(). No edita registro.json a mano.

Verifica antes de tocar nada:
  - SHA-256 de v2.json (el NUEVO, tras la enmienda 34)
  - SHA-256 de registro.json
  - SHA-256 del informe y del snapshot de metrica que se van a citar
  - que sha256_motor citado NO es el del filtro.py vigente, sino el del
    fichero que ejecuto el test (comprobacion explicita, no accidental)
  - que todos los campos estan en la lista cerrada vigente
"""

import hashlib
import json
import sys

import cadena

SHA_V2 = "c24117ea0def853d7396013822e8eafff75bff7db57097fdf3c07f0fa907a382"
SHA_REGISTRO = "b7dae020f2ffebde32bea448f733deef661edb71a163c3a3ebd9a6a4faaaa3fb"
SHA_INFORME = "eaff81e22ebbe8ecc1c5b7381134206549c9a999a1e70fc1114d54d5801f0e88"
SHA_SNAPSHOT_METRICA = "10dcabcf818fc4c0b553dda9ab5cfaffc11a93b3f22eb8c190f01140d5ebf788"

# Motor que EJECUTO el test, anterior al cambio de la constante de
# compatibilidad de la enmienda 34. No es el filtro.py vigente.
SHA_MOTOR_EJECUTOR = "936eda7034ec04dbadfc3f03b0530bd1c52e1b3ef5f99a0208185220f097966f"


def sha256_fichero(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def abortar(msg):
    print(f"ABORTA: {msg}")
    sys.exit(1)


def main():
    for ruta, esperado in (
        ("v2.json", SHA_V2),
        ("registro.json", SHA_REGISTRO),
        ("informe_2026Q3_ssr_capstables.json", SHA_INFORME),
        ("snapshot_matriz_ssr_capstables.json", SHA_SNAPSHOT_METRICA),
    ):
        real = sha256_fichero(ruta)
        if real != esperado:
            abortar(f"{ruta}: {real} != {esperado}")
        print(f"[ok] {ruta}: {real[:16]}...")

    vigente = sha256_fichero("filtro.py")
    if vigente == SHA_MOTOR_EJECUTOR:
        abortar(
            "filtro.py vigente coincide con el motor ejecutor: la enmienda 34 "
            "no se ha aplicado a la constante de compatibilidad"
        )
    print(f"[ok] filtro.py vigente {vigente[:16]}... != motor ejecutor "
          f"{SHA_MOTOR_EJECUTOR[:16]}... (discrepancia esperada y declarada)")

    doc = json.load(open("v2.json", encoding="utf-8"))
    if doc["meta"]["version_esquema"] != "2.8.0":
        abortar("v2.json no declara 2.8.0")

    permitidos = set(
        doc["integridad"]["resolucion_de_entradas"]["tipo_entrada"][
            "alta_transicion_de_estado"
        ]["campos_permitidos"]
    )

    entrada = {
        "id": "ssr_capstables",
        "tipo_entrada": "transicion_de_estado",
        "estado": "DESCARTADA_GATE_3",
        "fecha_registro": "2026-09-06",
        "gate_alcanzado": 3,
        "fecha_corte_bloques": "2023-03-31",
        "sha256_snapshot_metrica": SHA_SNAPSHOT_METRICA,
        "sha256_motor": SHA_MOTOR_EJECUTOR,
        "sha256_informe": SHA_INFORME,
        "motivo": (
            "Resultado del test del lote 2026-Q3. La variable no supera el gate 3: "
            "su contribucion incremental de R2 queda por debajo del umbral del lote, "
            "sin insuficiencia de observaciones efectivas. Los gates 1 y 4 se superan y "
            "el gate 2, descriptivo desde la enmienda 19, no condiciona el veredicto. "
            "La particion coincide con la fecha de corte comprometida en la entrada 22, "
            "escrita antes de ejecutar. Las cifras estan en el informe anclado en "
            "sha256_informe; no se reproducen aqui, porque la enmienda 33 prohibe usar "
            "este campo como contenedor de datos estructurados. sha256_motor identifica "
            "el fichero filtro.py que produjo el resultado, anterior al cambio de la "
            "constante de compatibilidad de la enmienda 34; difiere del fichero vigente "
            "y esa diferencia es procedencia historica, no defecto. El rechazo cierra la "
            "variable: no otorga derecho a re-proponerla ni a proponer variantes, "
            "conforme a protocolo.unicidad_del_test. No se reabren la ficha congelada "
            "(entrada 20), la aclaracion del numerador (entrada 21) ni la incidencia de "
            "cobertura Omni declarada en la entrada 22."
        ),
    }

    fuera = [k for k in entrada if k not in permitidos]
    if fuera:
        abortar(f"campos fuera de la lista cerrada: {fuera}")
    print(f"[ok] {len(entrada)} campos, todos en la lista cerrada vigente")

    reg = json.load(open("registro.json", encoding="utf-8"))
    ok, msg = cadena.verificar(reg)
    if not ok:
        abortar(f"cadena rota antes de anadir: {msg}")
    print(f"[ok] {msg}")

    nuevo = cadena.anadir(reg, entrada)

    ok, msg = cadena.verificar(nuevo)
    if not ok:
        abortar(f"cadena rota despues de anadir: {msg}")
    ok, msg2 = cadena.es_extension(reg, nuevo)
    if not ok:
        abortar(f"no es extension: {msg2}")
    print(f"[ok] {msg}")
    print(f"[ok] extension verificada: {msg2}")

    with open("registro.json", "w", encoding="utf-8") as f:
        json.dump(nuevo, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"[ok] registro.json escrito. {nuevo['meta']['n_entradas']} entradas")
    print(f"[ok] ultimo hash: {nuevo['meta']['ultimo_hash']}")
    print(f"[ok] SHA-256 registro.json: {sha256_fichero('registro.json')}")


if __name__ == "__main__":
    main()
