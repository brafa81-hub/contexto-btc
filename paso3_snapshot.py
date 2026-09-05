#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASO 3 - Snapshot canonico de la matriz + serie SSR.
contexto-btc / ssr_capstables / lote 2026-Q3.

Formato del snapshot fijado por la ficha congelada (entrada 20):
  metrica_continua.fuente.snapshot.objeto
    "Matriz fecha por token con las columnas fecha, id_proveedor, gecko_id,
     totalCirculatingUSD e incluido_tras_reglas, ordenada por fecha y por
     id_proveedor."
  metrica_continua.fuente.snapshot.canonizacion
    "La misma declarada en registro.json, campo meta.canonizacion."
      -> json.dumps(obj, sort_keys=True, separators=(',',':'),
                    ensure_ascii=False).encode('utf-8')

Decisiones operativas validadas antes de generar (no son reglas nuevas, son
la forma de ejecutar reglas ya congeladas):
  1. El snapshot es JSON, no CSV: es la unica lectura que hace aplicable la
     canonizacion referenciada.
  2. El rango abarca desde el primer dato crudo, no desde el arranque, para
     que el propio arranque sea verificable dentro del snapshot.
  3. id_proveedor se ordena numericamente.

Reglas aplicadas, en el orden fijado:
  exclusion D6 (ya en paso1) -> inclusion 100M dia a dia (D5)
  -> duplicados por gecko_id dia a dia (D7) -> sin gecko_id se listan
  -> arranque con >=2 tokens
"""
import json, os, csv, hashlib
from datetime import datetime, timezone

CRUDO = "/home/claude/crudo"
SALIDA = "/home/claude/salida"
PRECIO = "/home/claude/repo/snapshot_precio_btcusd.csv"
CORTE = "2026-09-03"
UMBRAL = 100_000_000.0
ARRANQUE_MIN = 2
NO_ACREDITADOS = {"340", "13", "328", "398", "332", "407"}


def fecha(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def canonizar(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    os.makedirs(SALIDA, exist_ok=True)
    cand = {c["id"]: c for c in json.load(open("/mnt/user-data/uploads/candidatos.json"))}
    ids = [f[:-5] for f in sorted(os.listdir(CRUDO)) if f.endswith(".json")]
    assert len(ids) == 82

    # ---- lectura cruda ----------------------------------------------------
    bruto = {}
    for tid in ids:
        for p in json.load(open(os.path.join(CRUDO, f"{tid}.json"))):
            f = fecha(p["date"])
            if f > CORTE:
                continue
            v = (p.get("totalCirculatingUSD") or {}).get("peggedUSD")
            if v is None:
                continue
            assert tid not in bruto.get(f, {}), f"colision {f}/{tid}"
            bruto.setdefault(f, {})[tid] = float(v)

    # ---- reglas dia a dia -------------------------------------------------
    matriz = []          # todas las filas, con la marca incluido_tras_reglas
    agregado = {}        # fecha -> (denominador, n_tokens, peso_no_acreditados)
    d7 = []

    for f in sorted(bruto):
        dia = bruto[f]
        incluidos = {t: v for t, v in dia.items() if v >= UMBRAL}

        por_gecko = {}
        for t, v in incluidos.items():
            g = cand[t].get("gecko_id")
            if g:
                por_gecko.setdefault(g, []).append((t, v))

        descartados = set()
        for g, lst in por_gecko.items():
            if len(lst) > 1:
                lst.sort(key=lambda x: (-x[1], int(x[0])))
                descartados |= {t for t, _ in lst[1:]}
                d7.append({"fecha": f, "gecko_id": g, "conserva": lst[0][0],
                           "descarta": [t for t, _ in lst[1:]]})

        finales = {t: v for t, v in incluidos.items() if t not in descartados}

        for t in sorted(dia, key=lambda x: int(x)):
            matriz.append({
                "fecha": f,
                "id_proveedor": t,
                "gecko_id": cand[t].get("gecko_id") or None,
                "totalCirculatingUSD": dia[t],
                "incluido_tras_reglas": t in finales,
            })

        if finales:
            tot = sum(finales.values())
            na = sum(v for t, v in finales.items() if t in NO_ACREDITADOS)
            agregado[f] = (tot, len(finales), 100.0 * na / tot)

    # ---- arranque ---------------------------------------------------------
    arranque = next(f for f in sorted(agregado) if agregado[f][1] >= ARRANQUE_MIN)

    # ---- snapshot canonico ------------------------------------------------
    matriz.sort(key=lambda r: (r["fecha"], int(r["id_proveedor"])))
    blob = canonizar(matriz)
    sha_snapshot = hashlib.sha256(blob).hexdigest()
    p_snap = os.path.join(SALIDA, "snapshot_matriz_ssr_capstables.json")
    open(p_snap, "wb").write(blob)
    assert hashlib.sha256(open(p_snap, "rb").read()).hexdigest() == sha_snapshot

    # ---- serie SSR para filtro.py ----------------------------------------
    precio = {}
    for r in csv.DictReader(open(PRECIO)):
        precio[r["fecha"]] = float(r["cierre"])

    ssr, sin_precio = [], []
    for f in sorted(agregado):
        if f < arranque:
            continue
        if f not in precio:
            sin_precio.append(f)
            continue
        ssr.append((f, precio[f] / agregado[f][0]))

    p_ssr = os.path.join(SALIDA, "ssr_capstables.csv")
    with open(p_ssr, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha", "valor"])
        for f, v in ssr:
            w.writerow([f, repr(v)])
    sha_ssr = hashlib.sha256(open(p_ssr, "rb").read()).hexdigest()

    # ---- informe ----------------------------------------------------------
    b1_lim = "2023-03-31"
    cot = lambda sub: max(sub, key=lambda f: agregado[f][2]) if sub else None
    utiles = [f for f in sorted(agregado) if f >= arranque]
    g = cot(utiles); b1 = cot([f for f in utiles if f <= b1_lim])
    b2 = cot([f for f in utiles if f > b1_lim])

    print("=" * 72)
    print(f"filas de la matriz (snapshot) : {len(matriz)}")
    print(f"rango de la matriz            : {matriz[0]['fecha']} .. {matriz[-1]['fecha']}")
    print(f"tokens distintos              : {len({r['id_proveedor'] for r in matriz})}")
    print(f"filas incluido_tras_reglas    : {sum(r['incluido_tras_reglas'] for r in matriz)}")
    print(f"activaciones D7               : {len(d7)}")
    print(f"arranque (>=2 tokens)         : {arranque}")
    print(f"filas de la serie SSR         : {len(ssr)}  ({ssr[0][0]} .. {ssr[-1][0]})")
    print(f"dias sin precio BTC           : {len(sin_precio)}"
          + (f"  {sin_precio[:5]}" if sin_precio else ""))
    print()
    print(f"cota no acreditados global    : {agregado[g][2]:.4f}%  ({g})")
    print(f"cota no acreditados bloque_1  : {agregado[b1][2]:.4f}%  ({b1})")
    print(f"cota no acreditados bloque_2  : {agregado[b2][2]:.4f}%  ({b2})")
    print()
    print(f"SHA-256 snapshot matriz : {sha_snapshot}")
    print(f"SHA-256 serie SSR       : {sha_ssr}")

    json.dump({"corte": CORTE, "arranque": arranque,
               "filas_matriz": len(matriz), "filas_ssr": len(ssr),
               "sin_gecko_id": sorted({r["id_proveedor"] for r in matriz
                                       if r["gecko_id"] is None}, key=int),
               "d7_activaciones": d7,
               "sha256_snapshot_matriz": sha_snapshot,
               "sha256_serie_ssr": sha_ssr},
              open(os.path.join(SALIDA, "informe_snapshot.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
