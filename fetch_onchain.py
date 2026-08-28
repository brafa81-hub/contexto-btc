"""
DATOS ON-CHAIN DE BITCOIN — BGeometrics (bitcoin-data.com)

HISTORIAL DE ESTA FUENTE (para que quede constancia de por qué cambiamos):
  1. Empezamos con CoinMetrics Community API (community-api.coinmetrics.io)
     → dejó de funcionar (403), la documentación actual apunta a otro dominio
  2. Probamos api.coinmetrics.io (URL "nueva" según su documentación)
     → responde, pero exige API key ahora (401) — ya no es de verdad gratis
  3. Se consultó a Grok, ChatGPT y Copilot por separado. Grok y Copilot
     coincidieron, de forma independiente, en BGeometrics/bitcoin-data.com.
     Verificado el 28/08/2026 contra la documentación oficial de bgeometrics.com:
     es un servicio real, con nodo Bitcoin propio, que calcula MVRV desde
     datos on-chain crudos (no reexporta otra fuente).

Plan gratuito de BGeometrics (según su documentación, sujeto a cambios):
  - Sin registro, sin API key para el plan Free
  - Últimos ~4 años de histórico diario (no desde 2011 como con CoinMetrics)
  - Límite aproximado de 15 peticiones/día — este script pide pocas
    llamadas (una por métrica), así que no debería acercarse al límite

Documentación: https://bitcoin-data.com/  ·  https://bgeometrics.com/api/

EJECUTAR EN TU ORDENADOR:
    python fetch_onchain.py --out btc_onchain.csv
"""

import argparse
import csv
import time

try:
    import requests
except ImportError:
    raise SystemExit("Falta 'requests'. Instala con: pip install requests")


BASE_URL = "https://bitcoin-data.com/v1"

# Métricas del plan Free que nos interesan. Si alguna no existe con ese
# nombre exacto, el script avisa y sigue con las demás en vez de fallar del todo.
#
# NOTA: 'active-address-count' se probó y da 404 — el nombre correcto del
# endpoint de BGeometrics para direcciones activas no está confirmado.
# Se deja fuera para no generar un aviso de error en cada ejecución; si en
# el futuro se confirma el nombre correcto (ver bitcoin-data.com/api/redoc.html),
# se puede añadir de nuevo aquí.
METRICAS = {
    "mvrv": "mvrv",
    "mvrv-zscore": "mvrv_zscore",
    "realized-price": "realized_price",
    "hashrate": "hashrate",
}


def fetch_metrica(nombre_endpoint):
    """Descarga el histórico completo (dentro del límite del plan Free) de una métrica."""
    url = f"{BASE_URL}/{nombre_endpoint}"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"  Aviso: no se pudo descargar '{nombre_endpoint}' ({e})")
        return None
    except Exception as e:
        print(f"  Aviso: error con '{nombre_endpoint}' ({e})")
        return None


def fetch_onchain(out="btc_onchain.csv"):
    resultados = {}
    for endpoint, columna in METRICAS.items():
        print(f"Descargando {endpoint}...")
        data = fetch_metrica(endpoint)
        if data:
            resultados[columna] = data
        time.sleep(1.5)  # el plan Free tiene un límite diario bajo, vamos con calma

    if not resultados:
        print("\nNo se descargó ninguna métrica. Revisa si bitcoin-data.com sigue activo:")
        print("  https://bitcoin-data.com/v1/mvrv/last")
        return

    # Unificar todas las métricas por fecha
    por_fecha = {}
    for columna, data in resultados.items():
        for item in data:
            fecha = item.get("d") or item.get("date")
            valor = item.get(columna.replace("_", "")) or item.get(list(item.keys())[-1])
            if fecha:
                por_fecha.setdefault(fecha, {})[columna] = valor

    campos = ["date"] + list(resultados.keys())
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(campos)
        for fecha in sorted(por_fecha.keys()):
            fila = [fecha] + [por_fecha[fecha].get(c, "") for c in resultados.keys()]
            w.writerow(fila)

    print(f"\nGuardado {len(por_fecha)} filas en {out}")
    print(f"Métricas incluidas: {', '.join(resultados.keys())}")
    print("Fuente: BGeometrics (bitcoin-data.com), plan Free — ~4 años de histórico")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="btc_onchain.csv")
    args = p.parse_args()
    fetch_onchain(out=args.out)

