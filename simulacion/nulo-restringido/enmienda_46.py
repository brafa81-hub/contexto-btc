"""enmienda_46.py — script de un solo uso. Protocolo v3: nulo por rotacion circular.
Aprobado por Rafa el 2026-09-22 (nulo A, opcion v3, regimen 'v3', reanalisis solo informativo).
Lee ./v2.json y ./filtro.py, verifica SHA-256 de entrada, escribe ./salida_46/{v2.json,filtro.py}.
No toca registro.json. Determinista: dos ejecuciones dan salida identica byte a byte."""
import hashlib, json, os, sys, copy, py_compile

SHA_V2_IN = "fe9c9a8f1fc8f04e43dcbbed63f6cb91748d47d6a7550c728012016d14c414f8"
SHA_FI_IN = "9c11c1243bdf091bf672e65ad6ccebdae7545b7fde4d931bbfff5b1c42052480"

def sha(b): return hashlib.sha256(b).hexdigest()
def fallo(m): print("ABORTA:", m); sys.exit(2)

v2b = open("v2.json", "rb").read(); fib = open("filtro.py", "rb").read()
if sha(v2b) != SHA_V2_IN: fallo(f"v2.json SHA distinto: {sha(v2b)}")
if sha(fib) != SHA_FI_IN: fallo(f"filtro.py SHA distinto: {sha(fib)}")
d = json.loads(v2b); orig = copy.deepcopy(d)
if json.dumps(d, ensure_ascii=False, indent=2).encode() + b"\n" != v2b: fallo("formato de v2.json no reproducible")
if d["meta"]["version_esquema"] != "2.17.0" or len(d["meta"]["enmiendas"]) != 45: fallo("estado de doctrina inesperado")

# ---------------- v2.json ----------------
d["meta"]["version_esquema"] = "3.0.0"

motor_ant = d["motor"]
d["motor"] = {
    "identificador": "batch_prds_rotacion",
    "estado": "CONGELADO",
    "protocolo": "v3",
    "origen_decision": "Enmienda 46 (2026-09-22). El cambio de nulo es un cambio de motor y, por la nota del motor anterior, exige version nueva de protocolo: se formaliza como protocolo v3.",
    "cambio_respecto_al_anterior": "Unico cambio: la distribucion nula del test de permutacion sobre bloque_2 pasa de bloque contiguo de n dias a rotacion circular de la mascara (protocolo.test_de_permutacion.rotacion_circular). Sin cambios: estadistico (diferencia de medianas), semilla, n_permutaciones, formulas de p-valor por signo_esperado, minimos del test, gates, Benjamini-Yekutieli y confirmacion forward.",
    "nota": "No se sustituye ni se reparametriza el motor. Cualquier cambio de motor exige una version nueva de protocolo (v4) y no se aplica retroactivamente a variables ya testeadas.",
    "nombres_de_fichero": "Se conservan los nombres v2.json, registro.json y filtro.py para no romper filtro.py, app.py ni el flujo de GitHub. La version de protocolo la fija meta.version_esquema (3.x), no el nombre del fichero ni el rotulo 'filtro.py v2' del informe.",
    "no_retroactividad": "Las entradas ya registradas no se recalculan ni se modifican. Ver protocolo.unicidad_del_test.nota_protocolo_v3_enmienda_46.",
    "_motor_anterior_enmienda_46": motor_ant,
}

tp = d["protocolo"]["test_de_permutacion"]
if tp["metodo"] != "permutacion por bloques contiguos": fallo("metodo inesperado")
tp["metodo"] = "rotacion circular de la mascara (enmienda 46, protocolo v3)"
tp["_metodo_sustituido_enmienda_46"] = "permutacion por bloques contiguos"
tp["rotacion_circular"] = {
    "enmienda": 46,
    "descripcion": "La mascara de bloque_2 se desplaza circularmente s dias y se recalcula el estadistico. Conserva el patron de rachas y huecos de la mascara y la estructura temporal de los retornos (tendencias, regimenes de volatilidad).",
    "estadistico": "mediana(retorno_N | mascara rotada) - mediana(retorno_N | resto). Mismo estadistico que el observado.",
    "serie_rotada": "Vector de los L dias de bloque_2 con dato de mascara y de retorno_N (tras eliminar faltantes), en orden cronologico.",
    "exclusion_dias": {
        "regla": "exclusion = dias_episodio",
        "valor_bajo_N_30": 30,
        "motivo": "Evita desplazamientos tan cortos que la mascara rotada comparta retorno futuro con la original."
    },
    "sorteo": "s entero uniforme en [exclusion, L - exclusion], con reemplazo: un unico vector de n_permutaciones enteros generado con numpy.random.default_rng(semilla).integers(exclusion, L - exclusion + 1, n_permutaciones).",
    "aborto": "Si L <= 2 x exclusion, filtro.py aborta.",
    "implementacion_de_referencia": "simulacion/nulo-restringido/nulos.py (sha256 fe957ced765e1a9f...), funcion p_rotacion. Equivalencia exacta de p-valores verificada antes de aceptar la enmienda (positivo contra p_rotacion(m, r); negativo contra p_rotacion(m, -r); bilateral contra calculo independiente).",
    "limitacion_empalme": "La rotacion une el final de bloque_2 con su inicio. Si hay dias activos a ambos lados del empalme a menos de exclusion dias, aparece un episodio artificial en todas las rotaciones de esa mascara. Declarado, no corregido; nulos.empalme_artificial lo diagnostica.",
    "coherencia": "La capa de gates ya usaba un nulo por rotacion (gates_cualitativos.parametros.metodo_de_umbral)."
}
ci = tp["capa_de_interpretacion"]
ci["evidencia_de_calibracion"]["vigencia"] = "HISTORICA desde la enmienda 46: describe el esquema por bloques contiguos, que ya no es el del motor."
ci["evidencia_de_calibracion_enmienda_46"] = {
    "naturaleza": "Simulacion con precio real BTC/USD (Bitstamp) y mascaras sinteticas independientes del precio, pasadas por el pipeline real. Es evidencia sobre el nulo, no sobre ninguna variable real. Ninguna variable real se uso para elegir el nulo.",
    "criterios_fijados_antes_de_medir": "Calibracion bajo ruido entre 3% y 7% en ambos escenarios (uniforme/concentrado); falso positivo del pipeline completo con IC95 superior <= 1%; pasar M3; entre los que cumplan, el de mayor potencia. Nunca elegir por significacion con variables reales.",
    "M1_calibracion_bajo_ruido": {
        "medicion_original": "Cola positiva: 5,0% / 5,2% (uniforme/concentrado). Precio sha256 4c38b968..., fichero no conservado en el repositorio: no reproducible.",
        "remedicion_reproducible": "1000 replicas por escenario, precio simulacion/nulo-restringido/btc_bitstamp_diario.csv (sha256 afcc5312b8922206...), script m1_bilateral.py. Cola positiva 5,3% [4,1-6,9] / 6,6% [5,2-8,3]; cola negativa 6,2% [4,9-7,9] / 6,1% [4,8-7,8]; bilateral 4,8% [3,6-6,3] / 6,0% [4,7-7,6]. IC95 de Wilson.",
        "bilateral": "Regla 3-7% fijada antes de medir. Cumple en ambos escenarios."
    },
    "M2_pipeline_completo": "Falso positivo 0/400 (IC95 superior <= 1%). Potencia a theta 0,084: 18,2% / 12,8%; a theta 0,168: 84,5% / 77,5% (uniforme/concentrado). Precio 4c38b968... (no reproducible, ver M1).",
    "M3_prueba_de_estres_mayer": {
        "resultado": "Mascara Mayer construida desde el propio precio, 1000 gemelos de BTC, cola del signo esperado (negativo): 9,5% [7,4-11,9], n=705. Falla el criterio 3-7%.",
        "estatus": "Rebajada de criterio M3 a prueba de estres documentada por esta enmienda. Cambio decidido por Rafa DESPUES de ver resultados; se declara como tal.",
        "otras_mascaras_de_precio": "En la medicion original otras mascaras derivadas del precio (vol30) mostraron inflacion de la cola negativa (8-11%)."
    },
    "control_emparejado": {
        "diseno": "Mismos 1000 gemelos; mascaras independientes del precio con la misma tasa de activacion y las mismas rachas y huecos que Mayer (reordenadas, semilla 900000+i). Regla fijada antes de medir: 3-7% atribuye el fallo de Mayer a la endogeneidad; > 7% impide adoptar el nulo; < 3% no concluyente.",
        "resultado": "Cola negativa 5,9% [4,4-7,7]; cola positiva 6,1% (n=830). Ficheros control_emparejado.py (479f83e0...) y control_emparejado.jsonl (9b137b0b...).",
        "conclusion": "El fallo con Mayer se atribuye a que la mascara se construye desde el propio precio (endogeneidad), no a la persistencia de la mascara."
    },
    "limite_declarado": "Variables construidas desde el propio precio de BTC o muy ligadas a el: el nulo puede producir falsos positivos por encima del nominal en la cola negativa (hasta ~9,5% medido con Mayer). Gates, Benjamini-Yekutieli y confirmacion forward siguen actuando despues.",
    "reservas": [
        "El IC95 superior del control emparejado (7,7%) supera el 7%; la estimacion puntual cumple.",
        "La causa del fallo con Mayer se deduce por descarte; no se mide directamente.",
        "En la remedicion reproducible de M1 varios IC95 superiores superan el 7% (hasta 8,3%); las estimaciones puntuales cumplen.",
        "M2 y la medicion original de M1 usaron un fichero de precio no conservado."
    ]
}

d["potencia_pipeline_v3"] = {
    "enmienda": 46,
    "alcance": "Pipeline completo de 6 etapas (gates 1/3/4, permutacion con rotacion circular, Benjamini-Yekutieli, confirmacion forward) sobre precio real de BTC con mascaras sinteticas independientes del precio. No sustituye a potencia_medida, que describe solo la capa de gates.",
    "cifras": {
        "falso_positivo_ruido_puro": "0/400",
        "deteccion_theta_0084": "18,2% uniforme / 12,8% concentrado",
        "deteccion_theta_0168": "84,5% uniforme / 77,5% concentrado"
    },
    "lectura": "Con el motor v3 un efecto medio (theta 0,084) llega raramente a CONFIRMADA; solo efectos grandes tienen probabilidad alta. Que una variable sea descartada no demuestra que no tenga efecto.",
    "supuestos_declarados": [
        "Mascaras sinteticas independientes del precio; el efecto se inyecta sumando theta al retorno_N de los dias activos y se mide theta realizado.",
        "Tamano y composicion de lote de la simulacion para Benjamini-Yekutieli: supuesto, misma reserva que lote_n=12 en mediciones previas.",
        "Precio sha256 4c38b968..., fichero no conservado."
    ],
    "cifras_retiradas": "Las cifras 62,5% / 52% y la tabla por m (m=3/6/12) se midieron con precio sintetico GBM y nulo por bloque contiguo. No valen para BTC real ni para el motor v3. Nunca figuraron en este archivo; quedan retiradas de la documentacion del proyecto."
}

reg = d["integridad"]["resolucion_de_entradas"]["regimen"]
reg["ampliacion_enmienda_46"] = {
    "regla": "Toda variable cuya primera entrada se escriba con meta.version_esquema 3.x declara regimen 'v3'.",
    "motivo": "Distinguir en el registro que variables se testearon con el nulo por rotacion circular.",
    "no_retroactiva": "Las variables ya registradas conservan su regimen.",
    "automatizacion": "No automatizada en filtro.py; se comprueba al redactar la ficha."
}

d["protocolo"]["unicidad_del_test"]["nota_protocolo_v3_enmienda_46"] = "El paso a protocolo v3 no reabre ninguna variable ya testeada ni le devuelve elegibilidad. Un reanalisis de variables ya testeadas con el nulo v3 solo puede ser informativo: no cambia estados, no consume presupuesto, no entra en la correccion Benjamini-Yekutieli de ningun lote ni en confirmacion forward. Debe prerregistrarse antes de ejecutarse, hacerse en una sola pasada sobre la familia completa y etiquetarse como reanalisis. Cualquier otro uso exige una decision doctrinal aparte."

d["meta"]["enmiendas"].append({
    "n": 46,
    "titulo": "protocolo v3: nulo por rotacion circular en el test de permutacion",
    "fecha": "2026-09-22",
    "motivo": "Con precio real de BTC, el nulo por bloque contiguo es extremadamente conservador (p <= 0,05 en 0% bajo ruido) y anula la potencia del test. Entre los nulos medidos contra criterios fijados antes de medir, la rotacion circular (nulo A) cumple calibracion y falso positivo; falla la prueba con Mayer, atribuida por control emparejado a la endogeneidad de esa mascara.",
    "partes": [
        "1. motor: nuevo motor 'batch_prds_rotacion', CONGELADO, protocolo v3; el anterior se conserva como _motor_anterior_enmienda_46.",
        "2. protocolo.test_de_permutacion: metodo pasa a rotacion circular; campo nuevo rotacion_circular; la evidencia de calibracion anterior queda marcada como historica; nueva evidencia_de_calibracion_enmienda_46 con M1, M2, M3 como prueba de estres, control emparejado, limite y reservas.",
        "3. potencia_pipeline_v3: potencia del pipeline completo con el motor v3; retirada documental de 62,5% / 52% y de la tabla por m.",
        "4. integridad.resolucion_de_entradas.regimen: las variables nuevas declaran regimen 'v3'.",
        "5. protocolo.unicidad_del_test: el reanalisis de variables ya testeadas solo puede ser informativo.",
        "6. meta.version_esquema 2.17.0 -> 3.0.0; filtro.py: DOCTRINA_COMPATIBLE '3.0' y nulo por rotacion en test_permutacion, con equivalencia exacta verificada contra nulos.p_rotacion."
    ],
    "naturaleza": "Cambio de motor. Por la nota del motor anterior exige protocolo v3. No retroactivo: ninguna entrada del registro se recalcula ni se modifica.",
    "momento": "Tras el cierre de 2026-Q3, antes de 2026-Q4. Ninguna variable en PROPUESTA o EN_TEST pendiente de ejecutar ni en EN_CONFIRMACION.",
    "decision": "Rafa, 2026-09-22: adopcion del nulo A; formalizacion como protocolo v3; regimen 'v3' para variables nuevas; reanalisis solo informativo."
})

# ---------------- filtro.py ----------------
fi = fib.decode("utf-8")
A1 = 'DOCTRINA_COMPATIBLE = "2.17"  # enmienda 45'
B1 = 'DOCTRINA_COMPATIBLE = "3.0"  # enmienda 46 (protocolo v3)'
A2 = '''    real = float(z[z["m"]]["retorno_N"].median() - z[~z["m"]]["retorno_N"].median())
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
'''
B2 = '''    real = float(z[z["m"]]["retorno_N"].median() - z[~z["m"]]["retorno_N"].median())
    vals = z["retorno_N"].values
    n = len(sel)

    # Enmienda 46 (protocolo v3): nulo por rotacion circular de la mascara.
    # Desplazamientos enteros uniformes en [excl, L - excl], con reemplazo,
    # excl = dias_episodio. Equivalente exacto de nulos.p_rotacion.
    rc = tp["rotacion_circular"]
    if rc["exclusion_dias"]["regla"] != "exclusion = dias_episodio":
        abortar("rotacion_circular.exclusion_dias.regla no reconocida por este filtro.py")
    excl = dias_ep
    mvals = z["m"].values.astype(bool)
    L = len(vals)
    if L <= 2 * excl:
        abortar(f"bloque_2 demasiado corto para la rotacion circular "
                f"({L} dias con dato, exclusion {excl})")
    rng = np.random.default_rng(tp["semilla"])
    desplazamientos = rng.integers(excl, L - excl + 1, tp["n_permutaciones"])
    difs = np.empty(len(desplazamientos))
    for k, s in enumerate(desplazamientos):
        mm = np.roll(mvals, int(s))
        difs[k] = np.median(vals[mm]) - np.median(vals[~mm])
'''
for a in (A1, A2):
    if fi.count(a) != 1: fallo("bloque de filtro.py no encontrado exactamente una vez")
fi = fi.replace(A1, B1).replace(A2, B2)

# ---------------- escritura y comprobaciones ----------------
os.makedirs("salida_46", exist_ok=True)
v2_out = json.dumps(d, ensure_ascii=False, indent=2).encode() + b"\n"
open("salida_46/v2.json", "wb").write(v2_out)
open("salida_46/filtro.py", "wb").write(fi.encode("utf-8"))
py_compile.compile("salida_46/filtro.py", cfile="/tmp/filtro46.pyc", doraise=True)

d2 = json.loads(v2_out)
if d2["meta"]["enmiendas"][:45] != orig["meta"]["enmiendas"]: fallo("enmiendas 1-45 alteradas")
if d2["motor"]["_motor_anterior_enmienda_46"] != orig["motor"]: fallo("motor anterior alterado")
for k in orig:
    if k not in ("meta", "motor", "protocolo", "integridad") and d2[k] != orig[k]: fallo(f"seccion {k} alterada")
cambiadas = sorted(set(d2) - set(orig))
if cambiadas != ["potencia_pipeline_v3"]: fallo(f"secciones nuevas inesperadas: {cambiadas}")

print("v2.json   ", SHA_V2_IN[:16], "->", sha(v2_out)[:16], len(v2_out), "bytes")
print("filtro.py ", SHA_FI_IN[:16], "->", sha(fi.encode())[:16], len(fi.encode()), "bytes")
print("OK enmienda 46 escrita en salida_46/ (registro.json no tocado)")
