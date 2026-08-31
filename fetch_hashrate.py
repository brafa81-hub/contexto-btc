"""
HASHRATE HISTÓRICO LARGO — desde 2009, para poder validarlo de verdad.

POR QUÉ HACE FALTA
------------------
El hashrate que ya tenemos (btc_onchain.csv, vía BGeometrics) solo cubre
desde 2022: cuatro años, dos épocas evaluables. El filtro exige tres épocas
para emitir veredicto, así que el resultado quedó en PROVISIONAL.

Lo medido con esos cuatro años, por si sirve de referencia al comparar:

    Formulación              2021-2023   2024-2026   Signo
    variación 30d               +0.067      +0.050   coherente
    hash ribbon (30/60)         +0.057      +0.132   coherente
    hash ribbon, a 90 días      -0.166      +0.116   CAMBIA

A 30 días el signo aguanta; a 90 se invierte. Encaja con el patrón que
aparece en todo este proyecto: el horizonte corto resiste, el largo no.

Pero con dos épocas no se distingue una relación real de una casualidad:
dos monedas al aire salen cara las dos veces el 25% de las veces.

FUENTE: blockchain.com
  - Gratis, sin registro, sin clave
  - Serie diaria desde 2009
  - Es el proveedor más antiguo y citado de esta métrica

QUÉ SE HARÁ DESPUÉS
-------------------
Con 15 años habrá cinco épocas evaluables y el filtro podrá dar veredicto.
Se probarán las mismas cuatro formulaciones, a 30 y 90 días, y se aplicarán
los pasos 2 (¿anticipa o acompaña?) y 4 (¿se distingue del azar?), que con
los datos cortos ni siquiera llegaron a ejecutarse.

Aviso: probar 4 formulaciones × 2 horizontes son 8 pruebas. Con 8 pruebas
al 5% se espera 0,4 falsos positivos por azar. Si sale algo justo en el
límite, habrá que tratarlo con la desconfianza correspondiente.

EJECUTAR:
    python fetch_hashrate.py --out hashrate.csv
"""

import argparse

try:
    import pandas as pd
    import requests
except ImportError:
    raise SystemExit("Faltan dependencias. Instala con: pip install pandas requests")


URL = "https://api.blockchain.info/charts/hash-rate"


def fetch_hashrate(out: str = "hashrate.csv") -> None:
    print("Descargando hashrate histórico de blockchain.com...")

    try:
        r = requests.get(
            URL,
            params={"timespan": "all", "format": "json", "sampled": "false"},
            timeout=60,
            headers={"User-Agent": "contexto-btc/1.0"},
        )
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        raise SystemExit(
            f"\nblockchain.com respondió HTTP {code}.\n"
            f"Si persiste, comprueba manualmente en el navegador:\n  {URL}?timespan=all&format=json"
        )
    except Exception as e:
        raise SystemExit(f"\nError de conexión: {type(e).__name__}: {e}")

    datos = r.json().get("values", [])
    if not datos:
        raise SystemExit(
            "\nLa respuesta no contiene datos. La estructura de la API puede "
            "haber cambiado; revisa la respuesta en el navegador."
        )

    s = pd.Series(
        [d["y"] for d in datos],
        index=pd.to_datetime([d["x"] for d in datos], unit="s"),
        name="hashrate",
    )
    # La API devuelve muestreo irregular en los primeros años. Se pasa a
    # diario con interpolación hacia adelante: el hashrate es una magnitud
    # continua, no un evento, así que rellenar es legítimo aquí.
    s = s.resample("D").mean().ffill()
    s.index.name = "date"
    s.to_csv(out)

    print(f"\nGuardado {len(s)} días en {out}")
    print(f"Rango: {s.index[0].date()} a {s.index[-1].date()}")
    print(f"Años cubiertos: {(s.index[-1] - s.index[0]).days / 365:.1f}")

    # Comprobación de cobertura por época, que es lo que determina si el
    # filtro podrá emitir veredicto o se quedará en PROVISIONAL otra vez.
    print("\nCobertura por época (el filtro necesita 3 con datos):")
    epocas = [("2011", "2014"), ("2015", "2017"), ("2018", "2020"),
              ("2021", "2023"), ("2024", "2026")]
    con_datos = 0
    for a, b in epocas:
        n = len(s.loc[a:b])
        marca = "ok " if n > 100 else "vacía"
        if n > 100:
            con_datos += 1
        print(f"  [{marca}] {a}-{b}: {n} días")
    print(f"\nÉpocas evaluables: {con_datos}. "
          f"{'Suficiente para veredicto.' if con_datos >= 3 else 'Seguirá siendo PROVISIONAL.'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="hashrate.csv")
    args = p.parse_args()
    fetch_hashrate(out=args.out)
