"""
snapshot_precio.py — Construye el snapshot congelado de precio de Contexto-BTC.

Obedece a v2.json -> fuente_de_precio, que esta FIJADA e inmutable:
    serie          BTC/USD, cierre diario, Bitstamp
    hora_de_corte  00:00:00 UTC del dia siguiente (cierre de la vela diaria UTC)
    dias_faltantes se arrastra el ultimo cierre un maximo de 2 dias seguidos;
                   un hueco de 3 dias o mas parte la serie
    duplicados     ante dos registros de la misma fecha se conserva el ultimo
    outliers       NO se eliminan. Ningun cierre se descarta ni se winsoriza.

El script NO decide nada: las fechas de inicio y corte son constantes
declaradas aqui arriba, no "lo que haya hoy". Ejecutarlo dos veces en dias
distintos debe producir el MISMO fichero y el MISMO SHA-256.

Uso:
    python snapshot_precio.py
    python snapshot_precio.py --salida otra_ruta.csv

Salida: snapshot_precio_btcusd.csv con dos columnas, fecha y cierre.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

# --- CONSTANTES DECLARADAS. No se derivan de la fecha de ejecucion. ---------
FECHA_INICIO = date(2015, 1, 1)
FECHA_CORTE = date(2026, 9, 3)   # ultima vela diaria UTC completa al fijarla
PAR = "btcusd"
STEP = 86400                     # 1 dia
LIMITE = 1000                    # maximo que admite el endpoint
URL = "https://www.bitstamp.net/api/v2/ohlc/{par}/"
SALIDA = "snapshot_precio_btcusd.csv"
MAX_ARRASTRE = 2                 # fuente_de_precio.dias_faltantes


def _unix(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def descargar():
    """
    Pagina el endpoint OHLC de Bitstamp hasta cubrir el rango completo.

    CUIDADO CON EL PARAMETRO 'end': si se envian 'start' y 'end' a la vez, el
    endpoint devuelve las ULTIMAS 'limit' velas del rango, no las primeras. Eso
    hacia que la primera peticion aterrizase ya en el final de la serie y el
    bucle terminase creyendo haber acabado. Se pagina solo con 'start' y se
    recorta despues por FECHA_CORTE en consolidar().
    """
    fin = _unix(FECHA_CORTE)
    velas, cursor, peticiones = [], _unix(FECHA_INICIO), 0
    MAX_PETICIONES = 40          # tope duro anti-bucle

    while cursor <= fin and peticiones < MAX_PETICIONES:
        url = URL.format(par=PAR) + f"?step={STEP}&limit={LIMITE}&start={cursor}"
        peticiones += 1
        print(f"  peticion {peticiones}: desde "
              f"{datetime.fromtimestamp(cursor, timezone.utc).date()}", end="")

        req = urllib.request.Request(url, headers={"User-Agent": "contexto-btc"})
        with urllib.request.urlopen(req, timeout=60) as r:
            cuerpo = json.loads(r.read().decode("utf-8"))

        if "data" not in cuerpo or "ohlc" not in cuerpo.get("data", {}):
            print("\nPARA: la respuesta de Bitstamp no tiene la forma esperada.")
            print(json.dumps(cuerpo, ensure_ascii=False)[:500])
            sys.exit(1)

        lote = cuerpo["data"]["ohlc"]
        if not lote:
            print("  -> vacio, fin")
            break

        primero = int(lote[0]["timestamp"])
        ultimo = int(lote[-1]["timestamp"])
        print(f"  -> {len(lote)} velas, "
              f"{datetime.fromtimestamp(primero, timezone.utc).date()} a "
              f"{datetime.fromtimestamp(ultimo, timezone.utc).date()}")

        velas.extend(lote)

        if ultimo < cursor:
            print("\nPARA: el endpoint no avanza (devuelve velas anteriores al "
                  "cursor). Se corta para no entrar en bucle.")
            sys.exit(1)
        cursor = ultimo + STEP
        time.sleep(1.0)          # cortesia con la API publica

    if peticiones >= MAX_PETICIONES:
        print(f"\nPARA: se alcanzo el tope de {MAX_PETICIONES} peticiones sin "
              f"cubrir el rango. No se escribe nada.")
        sys.exit(1)

    print(f"  {len(velas)} velas brutas en {peticiones} peticiones")
    return velas


def consolidar(velas):
    """
    Convierte las velas en un dict fecha -> cierre (como CADENA, tal cual la
    devuelve la API: no se reformatea el numero, para que el fichero sea
    reproducible byte a byte).
    """
    por_fecha, duplicados = {}, 0
    for v in velas:
        d = datetime.fromtimestamp(int(v["timestamp"]), timezone.utc).date()
        if d < FECHA_INICIO or d > FECHA_CORTE:
            continue
        if d in por_fecha:
            duplicados += 1
        por_fecha[d] = str(v["close"]).strip()   # gana el ultimo (doctrina)
    return por_fecha, duplicados


def revisar_huecos(por_fecha):
    """
    fuente_de_precio.dias_faltantes. El arrastre lo hace filtro.py al cargar;
    aqui SOLO se comprueba y se informa. Una racha de 3 dias o mas es motivo
    de parada: filtro.py abortaria despues.
    """
    d, ultimo = FECHA_INICIO, FECHA_CORTE
    faltantes = []
    while d <= ultimo:
        if d not in por_fecha:
            faltantes.append(d)
        d += timedelta(days=1)

    rachas, actual = [], []
    for f in faltantes:
        if actual and (f - actual[-1]).days == 1:
            actual.append(f)
        else:
            if actual:
                rachas.append(actual)
            actual = [f]
    if actual:
        rachas.append(actual)

    return faltantes, rachas


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=SALIDA)
    args = ap.parse_args(argv)

    print("SNAPSHOT DE PRECIO — Contexto-BTC")
    print(f"serie  : BTC/USD cierre diario, Bitstamp (fuente_de_precio, FIJADA)")
    print(f"rango  : {FECHA_INICIO} a {FECHA_CORTE}  "
          f"({(FECHA_CORTE - FECHA_INICIO).days + 1} dias naturales)")
    print("descargando...")

    velas = descargar()
    por_fecha, duplicados = consolidar(velas)

    if not por_fecha:
        print("\nPARA: no se obtuvo ninguna vela en el rango.")
        return 1

    fechas = sorted(por_fecha)
    print(f"\n  primera fecha : {fechas[0]}   cierre {por_fecha[fechas[0]]}")
    print(f"  ultima fecha  : {fechas[-1]}   cierre {por_fecha[fechas[-1]]}")
    print(f"  dias con dato : {len(fechas)}")
    print(f"  duplicados resueltos (gana el ultimo): {duplicados}")

    if fechas[0] != FECHA_INICIO:
        print(f"\n  AVISO: la serie no arranca en {FECHA_INICIO}.")
    if fechas[-1] != FECHA_CORTE:
        print(f"\nPARA: la serie termina en {fechas[-1]}, no en {FECHA_CORTE}. "
              f"No se escribe nada.")
        return 1

    faltantes, rachas = revisar_huecos(por_fecha)
    print(f"  dias sin dato : {len(faltantes)}")

    if rachas:
        peor = max(len(r) for r in rachas)
        print(f"  racha de ausencias mas larga: {peor} dia(s)")
        largas = [r for r in rachas if len(r) >= 3]
        if largas:
            print("\n" + "!" * 68)
            print("PARA. Hay huecos de 3 dias o mas. filtro.py abortaria:")
            for r in largas[:10]:
                print(f"  - {len(r)} dias desde {r[0]} hasta {r[-1]}")
            if len(largas) > 10:
                print(f"  ... y {len(largas) - 10} racha(s) mas")
            print("NO se escribe el CSV. Avisa antes de hacer nada.")
            print("!" * 68)
            return 1
        cortas = [r for r in rachas if len(r) <= MAX_ARRASTRE]
        print(f"  {len(cortas)} racha(s) de 1-2 dias: filtro.py las rellenara "
              f"arrastrando el ultimo cierre (permitido por la doctrina)")

    # --- escritura determinista -------------------------------------------
    # newline='\n' es obligatorio: en Windows el modo texto por defecto
    # escribiria CRLF y el SHA-256 no coincidiria con el de otra maquina.
    with open(args.salida, "w", encoding="utf-8", newline="\n") as f:
        f.write("fecha,cierre\n")
        for d in fechas:
            f.write(f"{d.isoformat()},{por_fecha[d]}\n")

    h = hashlib.sha256()
    with open(args.salida, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)

    print(f"\nOK  escrito {args.salida} ({len(fechas)} filas)")
    print(f"OK  SHA-256: {h.hexdigest()}")
    print("\nPasa este SHA-256 junto con las lineas de arriba. NO edites el CSV: "
          "cualquier cambio, incluso el final de linea, cambia el hash.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
