import json, hashlib

GENESIS = "0" * 64

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def hash_entry(entry, prev):
    e = {k: v for k, v in entry.items() if k != "hash"}
    e["hash_anterior"] = prev
    return e, hashlib.sha256(canon(e)).hexdigest()

V1_NOTA = ("Heredada de v1. Evaluada bajo reglas con sesgo de seleccion conocido y no corregido. "
           "No consume presupuesto v2 y no se re-testea bajo el protocolo v2.")

def v1(var, familia, estado, motivo):
    return {
        "id": var,
        "familia": familia,
        "regimen": "v1",
        "lote": "v1-historico",
        "fecha_propuesta": None,
        "fecha_corte_bloques": None,
        "estado": estado,
        "gate_alcanzado": "no_registrado_en_v1",
        "motivo": motivo,
        "consume_presupuesto_v2": False,
        "nota": V1_NOTA,
    }

entradas = []

# --- Historico v1: 9 rechazadas ---
rechazadas = [
    ("mvrv_z_score", "valoracion_onchain"),
    ("funding_rate", "flujos_derivados"),
    ("dxy", "macro"),
    ("fed_funds_rate", "macro"),
    ("vix", "macro"),
    ("nasdaq", "macro"),
    ("fear_and_greed_index", "sentimiento"),
    ("hashrate", "red_mineria"),
    ("m2_global", "macro"),
]
for var, fam in rechazadas:
    entradas.append(v1(var, fam, "RECHAZADA_PVALOR",
                       "No supero el filtro de cuatro pasos sobre 15 anios de datos de Bitstamp."))

# --- Historico v1: ETF flows, pendiente ---
etf = v1("etf_flows", "flujos_derivados", "PENDIENTE_REVISION",
         "Consistencia de signo fuera de muestra, pero episodios independientes insuficientes para el test de permutacion.")
etf["revision_estimada"] = "2030"
etf["condicion_de_reapertura"] = ("Solo cuando existan episodios independientes suficientes. Al reabrirse entrara como "
                                  "propuesta nueva bajo protocolo v2 y consumira presupuesto de su trimestre.")
entradas.append(etf)

# --- Historico v1: halving, sellado ---
hal = v1("halving_ciclo", "ciclo_temporal", "SELLADA_V1",
         "Unico hallazgo que supero el filtro de v1. p ~ 0.014-0.049 en la ventana 18-24 meses post-halving, con signo negativo.")
hal["referencia_doctrina"] = "v2.json -> sellados[0]"
entradas.append(hal)

# --- Lote 1 v2: Stablecoins / SSR ---
entradas.append({
    "id": "stablecoin_supply_ratio",
    "alias": "SSR",
    "familia": "liquidez_stablecoins",
    "regimen": "v2",
    "lote": "2026-Q3",
    "fecha_propuesta": "2026-09-03",
    "fecha_fin_ventana_test": "2026-09-03",
    "fecha_corte_bloques": None,
    "estado": "PROPUESTA",
    "gate_alcanzado": None,
    "justificacion": ("Mide la liquidez en stablecoins disponible frente a la capitalizacion de BTC. Familia de liquidez, "
                      "no representada por ninguna variable evaluada en v1. Serie con acceso programatico gratuito."),
    "consume_presupuesto_v2": False,
    "nota_presupuesto": "Consumira presupuesto al transitar a EN_TEST.",
    "theta_B2": None,
    "M": None,
    "estado_M": "PENDIENTE_DEFINICION",
    "unidad_theta": None,
})

# --- Encadenado ---
salida = []
prev = GENESIS
for e in entradas:
    body, h = hash_entry(e, prev)
    body["hash"] = h
    salida.append(body)
    prev = h

registro = {
    "meta": {
        "nombre": "Contexto-BTC — Registro inmutable de propuestas",
        "version_esquema": "2.0.0",
        "doctrina_asociada": "v2.json",
        "append_only": True,
        "algoritmo_hash": "sha256",
        "genesis": GENESIS,
        "ultimo_hash": prev,
        "n_entradas": len(salida),
        "regla": ("Ninguna entrada se edita ni se borra. Una correccion se registra como entrada nueva que referencia "
                  "la anterior. filtro.py verifica la cadena completa al arrancar y aborta si esta rota."),
        "canonizacion": "json.dumps(entrada_sin_hash, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode('utf-8')",
    },
    "presupuesto_por_trimestre": {
        "2026-Q3": {
            "propuestas_usadas": 0,
            "propuestas_maximas": 12,
            "familias_nuevas_usadas": 0,
            "familias_nuevas_maximas": 2,
            "nota": "SSR pertenece a una familia del catalogo inicial, por lo que no consume cuota de familia nueva.",
        }
    },
    "entradas": salida,
}

with open("/home/claude/v2/registro.json", "w", encoding="utf-8") as f:
    json.dump(registro, f, indent=2, ensure_ascii=False)

# --- Verificacion de la cadena ---
prev = GENESIS
ok = True
for e in salida:
    body = {k: v for k, v in e.items() if k != "hash"}
    if body.get("hash_anterior") != prev or hashlib.sha256(canon(body)).hexdigest() != e["hash"]:
        ok = False
        break
    prev = e["hash"]

print("entradas:", len(salida))
print("cadena valida:", ok)
print("ultimo hash:", prev[:16], "...")
