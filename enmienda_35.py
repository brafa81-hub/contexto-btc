"""
enmienda_35.py — script de un solo uso. Contexto-BTC.

Aplica la enmienda 35 sobre v2.json:

  1. Campo nuevo en la lista cerrada de la entrada de transicion:
     sha256_serie_metrica, con obligatoriedad condicional en EN_TEST.
  2. Regimen expreso de sha256_snapshot_metrica: opcional, pero verificado
     y exigible si la entrada lo declara.
  3. Declaracion de que la enmienda 35 implementa en el motor los controles
     que la enmienda 34 declaro no automatizados.
  4. Actualizacion del estado de requirements.txt, sin reescribir el texto
     de la enmienda 34.
  5. Constancia de la decision de NO escribir la regla general que distinga
     cambios de compatibilidad de cambios de comportamiento.

Solo anade. No reescribe ningun texto previo. El unico valor que se sustituye
es meta.version_esquema, que toda enmienda mayor.menor obliga a cambiar.

Verifica el SHA-256 de v2.json antes de tocar nada y aborta si no coincide.
"""

import hashlib
import json
import sys

ENTRADA = "v2.json"
SALIDA = "v2_nuevo.json"

SHA_ESPERADO = "c24117ea0def853d7396013822e8eafff75bff7db57097fdf3c07f0fa907a382"
VERSION_ANTERIOR = "2.8.0"
VERSION_NUEVA = "2.9.0"
FECHA = "2026-09-06"
ENTRADAS_AL_ESCRIBIR = 23


def abortar(motivo):
    print("ABORTA: " + motivo)
    sys.exit(1)


def sha256_fichero(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def insertar_despues(d, clave_ancla, clave_nueva, valor):
    """Reconstruye el dict conservando el orden e insertando tras el ancla."""
    if clave_ancla not in d:
        abortar(f"no existe la clave ancla '{clave_ancla}'")
    if clave_nueva in d:
        abortar(f"la clave '{clave_nueva}' ya existe: el script no se repite")
    nuevo = {}
    for k, v in d.items():
        nuevo[k] = v
        if k == clave_ancla:
            nuevo[clave_nueva] = valor
    d.clear()
    d.update(nuevo)


# =====================================================================
# FASE 0 — VERIFICACION
# =====================================================================

sha_real = sha256_fichero(ENTRADA)
if sha_real != SHA_ESPERADO:
    abortar(
        f"{ENTRADA} no es el fichero esperado.\n"
        f"  esperado: {SHA_ESPERADO}\n"
        f"  leido:    {sha_real}"
    )
print(f"[0] {ENTRADA} verificado: {sha_real[:16]}...")

with open(ENTRADA, "rb") as f:
    doc = json.loads(f.read())

if doc["meta"]["version_esquema"] != VERSION_ANTERIOR:
    abortar(f"version_esquema no es {VERSION_ANTERIOR}")
if [e["n"] for e in doc["meta"]["enmiendas"]][-1] != 34:
    abortar("la ultima enmienda del indice no es la 34")

atr = doc["integridad"]["resolucion_de_entradas"]["tipo_entrada"]["alta_transicion_de_estado"]
e34 = atr["ampliacion_enmienda_34"]
print("[0] estructura previa correcta")


# =====================================================================
# PARTE 1 — CAMPO NUEVO EN LA LISTA CERRADA
# =====================================================================

permitidos = atr["campos_permitidos"]
if "sha256_serie_metrica" in permitidos:
    abortar("sha256_serie_metrica ya esta en la lista cerrada")
i = permitidos.index("sha256_snapshot_metrica")
permitidos.insert(i + 1, "sha256_serie_metrica")
print(f"[1] campos_permitidos: {len(permitidos)} campos")


# =====================================================================
# PARTE 2 — AMPLIACION ENMIENDA 35
# =====================================================================

e35 = {
    "campos_anadidos": ["sha256_serie_metrica"],
    "definiciones": {
        "sha256_serie_metrica": (
            "SHA-256 del fichero CSV de la serie de la metrica continua que "
            "filtro.py consume por --metrica para esta variable. Es el fichero "
            "que entra al motor, no el artefacto bruto del que se derivo."
        ),
        "distincion_con_sha256_snapshot_metrica": (
            "sha256_snapshot_metrica ancla el artefacto bruto que la ficha de la "
            "variable declare como snapshot; para ssr_capstables, la matriz fecha "
            "por token. sha256_serie_metrica ancla la serie derivada que el motor "
            "lee. Pueden coincidir si la ficha no define un snapshot bruto aparte: "
            "en ese caso ambos campos llevan el mismo hash y no se duplica nada, "
            "porque cada uno responde a una pregunta distinta."
        ),
    },
    "motivo": (
        "Entre el artefacto anclado y el resultado registrado quedaba un eslabon "
        "sin verificar: el CSV que el motor lee de verdad. Un cambio en ese "
        "fichero no rompia ningun hash y no lo detectaba nadie. La entrada 22 "
        "registro su SHA-256 dentro de declaraciones_de_ejecucion, que es objeto "
        "documental y no condiciona ninguna transicion. Usarlo como ancla "
        "vinculante habria repetido con declaraciones_de_ejecucion la maniobra "
        "que la enmienda 33 prohibio con el campo motivo."
    ),
    "obligatoriedad_condicional": {
        "regla": (
            "sha256_serie_metrica es exigido cuando el campo estado de la "
            "transicion es EN_TEST."
        ),
        "estados_que_lo_exigen": ["EN_TEST"],
        "ancla_estructural": (
            "El propio campo estado, igual que en la enmienda 34. No se crea "
            "ningun discriminante nuevo."
        ),
        "momento": (
            "Es un precompromiso, no un registro de resultado: se escribe antes "
            "de ejecutar ningun gate, como fecha_corte_bloques. Exigirlo en la "
            "transicion de resultado llegaria tarde, porque para entonces el "
            "fichero ya habria producido el veredicto."
        ),
        "fuera_de_ese_estado": "Opcional.",
    },
    "regimen_de_sha256_snapshot_metrica": {
        "obligatoriedad": (
            "Sigue siendo opcional. No toda variable futura tendra un artefacto "
            "bruto distinto de la serie que el motor lee."
        ),
        "consecuencia_de_declararlo": (
            "Si una entrada de transicion a EN_TEST lo trae, filtro.py exige el "
            "fichero correspondiente en la ejecucion y aborta si no se aporta o "
            "si el hash no coincide. Declarar un ancla y no poder comprobarla es "
            "peor que no declararla."
        ),
        "motivo_de_no_hacerlo_obligatorio": (
            "Exigirlo siempre obligaria a una variable de fuente unica a escribir "
            "dos veces el hash del mismo fichero para satisfacer la forma de la "
            "lista. La lista cerrada se amplia para registrar lo que existe, no "
            "para obligar a inventar artefactos."
        ),
    },
    "implementacion_en_el_motor": {
        "argumento_nuevo": (
            "filtro.py recibe el artefacto bruto por un argumento propio. El "
            "motor no asume que sea una matriz fecha por token: verifica lo que "
            "la ficha de esa variable declare como snapshot."
        ),
        "cero_reglas_en_el_codigo": (
            "La lista de estados que exige cada campo y el corte de aplicacion "
            "prospectiva se leen de este objeto y del de la enmienda 34. El motor "
            "no incorpora ninguna constante nueva."
        ),
        "utilidad_anadida": (
            "Al terminar, filtro.py imprime el SHA-256 del informe que acaba de "
            "escribir y el suyo propio. No es una regla: exigir dos hashes y no "
            "ofrecerlos deja abierta la via de error mas probable, que es "
            "calcularlos a mano."
        ),
    },
    "aplicacion_prospectiva": {
        "regla": (
            "El campo y su obligatoriedad condicional rigen para las entradas de "
            "transicion escritas a partir de esta enmienda. El registro tenia 23 "
            "entradas cuando se escribio; las entradas 1 a 23 quedan fuera."
        ),
        "entradas_previas_a_la_enmienda": ENTRADAS_AL_ESCRIBIR,
        "motivo": (
            "El registro es append-only: una entrada anterior no se puede "
            "corregir. Mismo criterio que las enmiendas 33 y 34."
        ),
    },
    "momento": (
        "Escrita con el lote 2026-Q3 cerrado, sin ningun test pendiente ni "
        "ningun resultado que se pueda contaminar. Es la unica ventana en que "
        "tocar los controles del motor no admite sospecha de haberlos ajustado "
        "a un resultado."
    ),
    "naturaleza": (
        "Solo anade. No reescribe ningun texto previo. No altera ningun gate, "
        "umbral, mascara, particion ni criterio estadistico. No modifica ninguna "
        "entrada del registro. Aplicacion prospectiva."
    ),
}
atr["ampliacion_enmienda_35"] = e35
print("[2] ampliacion_enmienda_35 anadida")


# =====================================================================
# PARTE 3 — LOS CONTROLES DE LA 34 PASAN A EJECUTARSE
# =====================================================================

insertar_despues(
    e34["no_automatizada"],
    "leccion",
    "superado_por_la_enmienda_35",
    {
        "hecho": (
            "La enmienda 35 implementa esta obligatoriedad condicional en "
            "filtro.py, junto con la verificacion de los hashes de la metrica. "
            "El texto de este objeto describe el estado del motor entre las "
            "enmiendas 34 y 35 y no se reescribe."
        ),
        "controles_que_pasan_a_ejecutarse": [
            "Obligatoriedad de sha256_motor y sha256_informe en los estados de resultado de test.",
            "Verificacion de sha256_serie_metrica contra el CSV que el motor consume.",
            "Verificacion de sha256_snapshot_metrica contra su fichero cuando la entrada lo declara.",
        ],
        "garantia_de_que_no_se_declara_en_vano": (
            "Esta enmienda cambia mayor.menor, y filtro.py aborta antes de leer "
            "nada si DOCTRINA_COMPATIBLE no coincide con version_esquema. Una "
            "doctrina 2.9.0 con un motor que aun no ejecute estos controles no "
            "puede ejecutarse en absoluto: el desfase se manifiesta como aborto, "
            "no como control declarado e incumplido en silencio."
        ),
        "hueco_que_permanece": (
            "Ninguno de estos controles alcanza al entorno de ejecucion. Ver "
            "alcance_de_sha256_motor."
        ),
    },
)
print("[3] no_automatizada: superado_por_la_enmienda_35")


# =====================================================================
# PARTE 4 — REQUIREMENTS.TXT
# =====================================================================

insertar_despues(
    e34["alcance_de_sha256_motor"],
    "naturaleza",
    "actualizacion_enmienda_35",
    {
        "hecho": (
            f"El {FECHA} se fijan versiones exactas de pandas y numpy en "
            "requirements.txt. El texto de no_cubre describe el estado del "
            "repositorio en la fecha de la enmienda 34, era cierto entonces y no "
            "se reescribe."
        ),
        "alcance_de_la_fijacion": (
            "Solo pandas y numpy, que son las bibliotecas que intervienen en el "
            "calculo del resultado. streamlit, plotly y requests quedan en rango: "
            "afectan al dashboard o a una descarga ya congelada por hash, y "
            "clavarlos anadiria riesgo de despliegue sin ganar reproducibilidad."
        ),
        "lo_que_no_queda_fijado": (
            "La version del interprete de Python y las dependencias transitivas. "
            "requirements.txt no las gobierna. La limitacion se reduce, no "
            "desaparece."
        ),
        "no_es_retroactivo": (
            "Las versiones con que se ejecuto el informe anclado en la entrada 23 "
            "son DESCONOCIDAS. Fijar hoy las de un contenedor de verificacion y "
            "presentarlas como aquellas registraria un supuesto como confirmado. "
            "No se reconstruyen."
        ),
        "alcance_de_sha256_motor_sin_cambios": (
            "sha256_motor sigue cubriendo el fichero unicamente. Fijar "
            "dependencias reduce la deriva futura del entorno; no amplia lo que "
            "ese hash cubre."
        ),
    },
)
print("[4] alcance_de_sha256_motor: actualizacion_enmienda_35")


# =====================================================================
# PARTE 5 — DECISION SOBRE LA REGLA GENERAL
# =====================================================================

insertar_despues(
    e34["cambio_de_compatibilidad_posterior_al_resultado"],
    "alcance",
    "evaluacion_enmienda_35",
    {
        "decision": (
            "No se escribe la regla general que distinga cambios de "
            f"compatibilidad de cambios de comportamiento. Evaluada el {FECHA}, "
            "con el lote 2026-Q3 cerrado y sin ningun caso pendiente que la "
            "reclame, que es la condicion que este parrafo exigia."
        ),
        "motivos": [
            "meta.compatibilidad.consecuencia_asumida declara deliberada la friccion de que toda enmienda mayor.menor obligue a tocar filtro.py. Una regla que exima a los cambios de compatibilidad ablanda exactamente esa friccion.",
            "meta.compatibilidad.cierre_del_hueco_de_parche reconoce que la granularidad deja abierto quien decide que es un parche, y lo cierra con la traza, no con una categoria. Clasificar los cambios en compatibilidad y comportamiento reintroduce esa decision un nivel mas arriba y con poder de autorizacion en lugar de deteccion.",
            "El problema que la regla resolveria ya esta resuelto por anclaje: sha256_motor registra en cada entrada el fichero que ejecuto. El coste de no tener regla general es una declaracion por caso; el de tenerla, una autorizacion generica invocable por quien necesite que su cambio sea de compatibilidad.",
            "Existe un unico precedente. Generalizar de una observacion es lo contrario del criterio con que se escribio el resto del protocolo.",
        ],
        "alcance_de_la_decision": (
            "No prohibe escribir esa regla en el futuro. Deja constancia de que "
            "se evaluo y se decidio no escribirla, para que la ausencia no se lea "
            "como olvido. Reabrir requiere un segundo caso real."
        ),
        "nota": (
            "La enmienda 35 no pertenece a esta categoria: cambia el "
            "comportamiento del motor, no solo su constante de compatibilidad."
        ),
    },
)
print("[5] cambio_de_compatibilidad: evaluacion_enmienda_35")


# =====================================================================
# PARTE 6 — INDICE Y VERSION
# =====================================================================

doc["meta"]["enmiendas"].append({
    "n": 35,
    "titulo": "verificacion de los hashes de la metrica y cierre de los controles declarados no automatizados",
    "fecha": FECHA,
    "motivo": (
        "La enmienda 34 dejo declarados dos huecos del motor: no comprobaba la "
        "obligatoriedad de sha256_motor y sha256_informe, ni verificaba los "
        "hashes del artefacto bruto y del CSV de la metrica. El CSV, ademas, no "
        "tenia campo en la lista cerrada donde anclarse."
    ),
    "partes": [
        "1. Campo nuevo en la lista cerrada de la entrada de transicion: sha256_serie_metrica, exigido en EN_TEST como precompromiso.",
        "2. Regimen expreso de sha256_snapshot_metrica: opcional, pero exigible y verificado si la entrada lo declara.",
        "3. Implementacion en filtro.py de los tres controles, con la lista de estados y el corte prospectivo leidos de la doctrina.",
        "4. Actualizacion del estado de requirements.txt, con declaracion expresa de que las versiones de la ejecucion de la entrada 23 son desconocidas y no se reconstruyen.",
        "5. Constancia de la decision de no escribir la regla general que distinga cambios de compatibilidad de cambios de comportamiento.",
    ],
    "momento": (
        "Lote 2026-Q3 cerrado, sin test pendiente ni resultado contaminable."
    ),
    "naturaleza": "Solo anade. Aplicacion prospectiva.",
})

doc["meta"]["version_esquema"] = VERSION_NUEVA
print(f"[6] indice: 35 enmiendas · version_esquema {VERSION_NUEVA}")


# =====================================================================
# ESCRITURA
# =====================================================================

texto = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
with open(SALIDA, "w", encoding="utf-8") as f:
    f.write(texto)

print(f"\nescrito {SALIDA}")
print(f"SHA-256: {sha256_fichero(SALIDA)}")
