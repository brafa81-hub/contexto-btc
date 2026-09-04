"""
Aplica la enmienda 30 a v2.json.

Enmienda 30: la prohibicion de referencias pasa de sintactica a funcional.
No toca registro.json. No toca ninguna ficha. No toca ningun campo de medida.

Uso: python aplicar_enmienda_30.py v2.json
"""
import hashlib
import json
import sys

SHA_ESPERADO_ANTES = "73778260efb635d351c63c51a4440c10c53f0d7bae7bd9a5f0e1b98b7a04ca1e"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main(path):
    antes = sha256(path)
    if antes != SHA_ESPERADO_ANTES:
        sys.exit(f"ABORTA: v2.json no es el esperado.\n  esperado {SHA_ESPERADO_ANTES}\n  leido    {antes}")

    d = json.loads(open(path, encoding="utf-8").read())

    # --- 1. version de esquema ---------------------------------------
    assert d["meta"]["version_esquema"] == "2.3.0"
    d["meta"]["version_esquema"] = "2.4.0"

    # --- 2. registro de la enmienda ----------------------------------
    assert d["meta"]["enmiendas"][-1]["n"] == 29
    d["meta"]["enmiendas"].append({
        "n": 30,
        "titulo": "la prohibicion de referencias pasa de sintactica a funcional",
        "fecha": "2026-09-04",
        "motivo": (
            "La enmienda 29 quiso impedir que una ficha DEPENDA de la estructura de v2.json, "
            "pero escribio la prueba como 'ninguna ficha puede nombrar una ruta', que es una "
            "prueba sobre el texto y no sobre la dependencia. La entrada 18 la incumple en cuatro "
            "citas, una de ellas a una ruta eliminada por la enmienda 24 que se cita precisamente "
            "para dejar constancia de que murio. Un registro de auditoria de cambios doctrinales "
            "necesita poder nombrar lo que cambio. Ademas la via de sustituir la ficha esta cerrada "
            "por migracion_de_fichas.limite_de_la_sustitucion, que exige identidad en "
            "naturaleza_de_la_hipotesis. La garantia real ya estaba escrita en la ultima frase de "
            "la propia regla 29 y se eleva aqui a clausula principal."
        ),
    })

    alcance = d["ficha_congelada"]["alcance"]

    # --- 3. regla de alcance: retirar la mencion sintactica -----------
    viejo = (
        "Prohibido incluir condiciones operativas, estados de disponibilidad de datos "
        "o referencias a rutas concretas de v2.json."
    )
    nuevo = "Prohibido incluir condiciones operativas y estados de disponibilidad de datos."
    assert viejo in alcance["regla"], "no se encuentra la frase a sustituir en alcance.regla"
    alcance["regla"] = alcance["regla"].replace(viejo, nuevo)

    # --- 4. prohibicion_de_referencias: sintactica -> funcional -------
    # La clave conserva su nombre a proposito: renombrarla activaria
    # ficha_congelada.migracion_de_fichas.regla.
    assert isinstance(alcance["prohibicion_de_referencias"], str)
    alcance["prohibicion_de_referencias"] = {
        "enmienda": 30,
        "sustituye_a": "la redaccion sintactica de la enmienda 29",
        "texto_sustituido": (
            "Ninguna ficha puede nombrar una ruta de v2.json. Si una ficha contiene una ruta, "
            "filtro.py aborta y la nombra. No se resuelve, no se traduce, no se sigue renombrado_desde."
        ),
        "regla": (
            "Ninguna ficha puede DEPENDER de la estructura de v2.json. Toda cadena contenida en una "
            "ficha que coincida con la sintaxis de una ruta doctrinal es texto inerte: filtro.py no la "
            "resuelve, no la traduce, no la interpreta como selector, puntero o alias, y no sigue "
            "renombrado_desde. La presencia, ausencia o modificacion de una ruta citada textualmente "
            "no altera en nada la ejecucion de la ficha."
        ),
        "no_es_causa_de_aborto": (
            "La mera aparicion de una ruta en un campo de ficha NO hace abortar a filtro.py, en ningun "
            "campo y a ninguna profundidad. La enmienda 29 abortaba por aparicion textual; esta "
            "enmienda aborta por dependencia."
        ),
        "causa_de_aborto": (
            "filtro.py aborta si alguna cadena procedente de registro.json se utiliza como camino para "
            "resolver contenido de v2.json."
        ),
        "justificacion": (
            "La independencia estructural es una propiedad del comportamiento del motor, no del texto "
            "de la ficha. Si el motor es incapaz de usar esas cadenas, la ficha no puede depender de "
            "ellas por construccion. Una prohibicion sintactica protege contra un peligro que el motor "
            "ya no puede materializar y a cambio impide al registro documentar la eliminacion de una "
            "ruta, que es una funcion legitima y necesaria de la auditoria."
        ),
        "sin_clasificacion_de_campos": (
            "Esta regla no distingue campos narrativos de campos de medida. Se aplica igual a todos. "
            "Clasificar campos para darles trato distinto queda expresamente descartado: fue la via "
            "rechazada en el analisis previo por abrir deriva de clasificacion."
        ),
    }

    # --- 5. inventario_de_referencias (clave nueva) -------------------
    alcance["inventario_de_referencias"] = {
        "enmienda": 30,
        "regla": (
            "filtro.py lista en cada informe toda cadena de una ficha que coincida con la sintaxis de "
            "una ruta doctrinal, junto a si esa ruta existe o no en la v2.json del pin de version. Es "
            "un inventario, no un diagnostico."
        ),
        "sin_severidad": (
            "Las entradas del inventario no son errores ni advertencias y no llevan nivel de severidad. "
            "Una ruta que no resuelve no es una anomalia: puede ser una referencia historica correcta. "
            "Se declara asi para evitar que un informe con alertas permanentes deje de leerse."
        ),
        "no_bloquea": (
            "El inventario nunca hace abortar a filtro.py ni condiciona ninguna transicion de estado."
        ),
        "precedente_interno": (
            "Mismo patron que integridad.resolucion_de_entradas.lote.comportamiento_ante_discrepancia "
            "(hace constar sin abortar) y que la enmienda 19 (gate 2 descriptivo no vinculante)."
        ),
    }

    # --- 6. aislamiento_del_resolver (clave nueva) --------------------
    alcance["aislamiento_del_resolver"] = {
        "enmienda": 30,
        "regla": (
            "El resolver de rutas de filtro.py solo admite caminos literales del codigo o caminos "
            "leidos de la propia v2.json. Ninguna cadena procedente de registro.json puede llegar a el "
            "como camino sobre la doctrina."
        ),
        "direccion_permitida": (
            "doctrina -> ficha. La comprobacion de campos obligatorios resuelve caminos definidos en la "
            "doctrina SOBRE una entrada del registro. Es legitima y no crea dependencia."
        ),
        "direccion_prohibida": (
            "ficha -> doctrina. Resolver sobre v2.json un camino tomado de una entrada del registro "
            "convierte la cita textual en dependencia real."
        ),
        "funcion_del_inventario": (
            "El inventario comprueba EXISTENCIA, nunca obtiene el valor. La funcion que lo implementa "
            "devuelve un booleano y no puede devolver contenido de la doctrina."
        ),
        "motivo": (
            "Sin esta clausula la garantia de no-resolucion es solo una promesa escrita. Con ella es "
            "una propiedad del codigo, verificable en revision. Riesgo senalado de forma independiente "
            "por las cuatro revisiones externas del 04/09/2026."
        ),
        "estado_verificado_2026_09_04": (
            "filtro.py v2 ya cumple esta invariante: todas las llamadas al resolver sobre la doctrina "
            "usan literales del codigo, y la unica llamada sobre una entrada del registro usa un camino "
            "procedente de la doctrina."
        ),
    }

    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

    print("enmienda 30 aplicada")
    print("  SHA-256 antes  :", antes)
    print("  SHA-256 despues:", sha256(path))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v2.json")
