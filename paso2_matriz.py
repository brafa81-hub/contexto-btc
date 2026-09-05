#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASO 2 - Matriz fecha x token y agregado del denominador.
contexto-btc / ssr_capstables / lote 2026-Q3.

NO calcula el SSR ni toca el estadistico. Solo construye el denominador.

Orden de reglas (fijado en la ficha congelada, entrada 20):
  1. exclusion D6            -> ya aplicada en paso1 (solo se descargaron 82)
  2. inclusion 100M absolutos, dia a dia   (regla_de_inclusion.regla, D5)
  3. duplicados por gecko_id, dia a dia    (duplicados.regla, D7)
  4. tokens sin gecko_id                   -> se listan, no son deduplicables
  5. arranque con >= 2 tokens              (arranque_minimo_del_universo.regla)

Otros anclajes aplicados:
  denominador.campo_usado       -> totalCirculatingUSD de peggedUSD
  datos_faltantes               -> no se interpola; sin dato no computa ese dia
  altas_y_bajas                 -> point-in-time, sin borrado retroactivo
  stablecoins_extintas          -> no se prolonga ni se elimina el pasado
  depegs                        -> no se corrigen ni se filtran
"""
import json, os, csv, hashlib
from datetime import datetime, timezone, timedelta

CRUDO = "/home/claude/crudo"
SALIDA = "/home/claude/salida"
CORTE = "2026-09-03"          # constante del script
UMBRAL = 100_000_000.0        # USD, absoluto (D5)
ARRANQUE_MIN = 2              # tokens simultaneos

NO_ACREDITADOS = {"340", "13", "328", "398", "332", "407"}


def fecha(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def main():
    os.makedirs(SALIDA, exist_ok=True)
    cand = {c["id"]: c for c in json.load(open("/mnt/user-data/uploads/candidatos.json"))}
    ids = sorted(os.listdir(CRUDO))
    ids = [f[:-5] for f in ids if f.endswith(".json")]
    assert len(ids) == 82, f"se esperaban 82 ficheros crudos, hay {len(ids)}"

    # ---- 1. lectura cruda: {fecha: {id: capitalizacion}} ------------------
    bruto = {}
    dup_fecha_token = 0
    for tid in ids:
        serie = json.load(open(os.path.join(CRUDO, f"{tid}.json")))
        for punto in serie:
            f = fecha(punto["date"])
            if f > CORTE:
                continue
            v = (punto.get("totalCirculatingUSD") or {}).get("peggedUSD")
            if v is None:
                continue          # datos_faltantes: no se interpola
            v = float(v)
            if f in bruto and tid in bruto[f]:
                dup_fecha_token += 1
                bruto[f][tid] = max(bruto[f][tid], v)
            else:
                bruto.setdefault(f, {})[tid] = v
    assert dup_fecha_token == 0, f"colisiones fecha/token en origen: {dup_fecha_token}"

    # ---- 2. inclusion 100M dia a dia (D5) --------------------------------
    # ---- 3. duplicados por gecko_id dia a dia (D7) -----------------------
    sin_gecko = sorted({t for t in ids if not cand[t].get("gecko_id")})
    d7_activaciones = []
    filas = []
    detalle = []

    for f in sorted(bruto):
        incluidos = {t: v for t, v in bruto[f].items() if v >= UMBRAL}

        por_gecko = {}
        for t, v in incluidos.items():
            g = cand[t].get("gecko_id")
            if not g:
                continue
            por_gecko.setdefault(g, []).append((t, v))

        descartados = set()
        for g, lista in por_gecko.items():
            if len(lista) > 1:
                lista.sort(key=lambda x: (-x[1], x[0]))
                ganador = lista[0][0]
                for t, v in lista[1:]:
                    descartados.add(t)
                d7_activaciones.append(
                    {"fecha": f, "gecko_id": g, "conserva": ganador,
                     "descarta": [t for t, _ in lista[1:]]})

        finales = {t: v for t, v in incluidos.items() if t not in descartados}
        if not finales:
            continue

        agregado = sum(finales.values())
        peso_no_acred = sum(v for t, v in finales.items() if t in NO_ACREDITADOS)
        filas.append({
            "fecha": f,
            "denominador_usd": agregado,
            "n_tokens": len(finales),
            "peso_no_acreditados_pct": 100.0 * peso_no_acred / agregado,
        })
        for t, v in sorted(finales.items(), key=lambda x: -x[1]):
            detalle.append({"fecha": f, "id": t, "symbol": cand[t]["symbol"],
                            "gecko_id": cand[t].get("gecko_id") or "",
                            "capitalizacion_usd": v})

    # ---- 5. arranque con >= 2 tokens --------------------------------------
    arranque = next((r["fecha"] for r in filas if r["n_tokens"] >= ARRANQUE_MIN), None)
    assert arranque, "no existe ninguna fecha con 2 tokens simultaneos"
    filas = [r for r in filas if r["fecha"] >= arranque]
    detalle = [d for d in detalle if d["fecha"] >= arranque]

    # ---- salidas ----------------------------------------------------------
    p_agr = os.path.join(SALIDA, "ssr_capstables_denominador.csv")
    with open(p_agr, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha", "denominador_usd", "n_tokens", "peso_no_acreditados_pct"])
        for r in filas:
            w.writerow([r["fecha"], f"{r['denominador_usd']:.2f}", r["n_tokens"],
                        f"{r['peso_no_acreditados_pct']:.6f}"])

    p_det = os.path.join(SALIDA, "ssr_capstables_detalle.csv")
    with open(p_det, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha", "id", "symbol", "gecko_id", "capitalizacion_usd"])
        for d in detalle:
            w.writerow([d["fecha"], d["id"], d["symbol"], d["gecko_id"],
                        f"{d['capitalizacion_usd']:.2f}"])

    sha_agr = hashlib.sha256(open(p_agr, "rb").read()).hexdigest()
    sha_det = hashlib.sha256(open(p_det, "rb").read()).hexdigest()

    # ---- informe ----------------------------------------------------------
    huecos = []
    d0 = datetime.strptime(arranque, "%Y-%m-%d")
    d1 = datetime.strptime(filas[-1]["fecha"], "%Y-%m-%d")
    presentes = {r["fecha"] for r in filas}
    d = d0
    while d <= d1:
        s = d.strftime("%Y-%m-%d")
        if s not in presentes:
            huecos.append(s)
        d += timedelta(days=1)

    print("=" * 70)
    print("MATRIZ ssr_capstables - denominador")
    print("=" * 70)
    print(f"tokens DENTRO descargados     : 82")
    print(f"tokens sin gecko_id           : {len(sin_gecko)} -> {sin_gecko}")
    print(f"activaciones de D7 (duplicados): {len(d7_activaciones)}")
    print(f"arranque (>=2 tokens)         : {arranque}")
    print(f"ultima fecha                  : {filas[-1]['fecha']}")
    print(f"filas de serie                : {len(filas)}")
    print(f"huecos de calendario          : {len(huecos)}")
    print(f"n_tokens min / max            : {min(r['n_tokens'] for r in filas)} / "
          f"{max(r['n_tokens'] for r in filas)}")
    mx = max(filas, key=lambda r: r["peso_no_acreditados_pct"])
    print(f"peso maximo no acreditados    : {mx['peso_no_acreditados_pct']:.4f}%  "
          f"({mx['fecha']})")
    print()
    print(f"SHA-256 denominador.csv : {sha_agr}")
    print(f"SHA-256 detalle.csv     : {sha_det}")

    json.dump({"arranque": arranque, "corte": CORTE, "filas": len(filas),
               "sin_gecko_id": sin_gecko, "d7_activaciones": d7_activaciones,
               "sha256_denominador": sha_agr, "sha256_detalle": sha_det},
              open(os.path.join(SALIDA, "informe_matriz.json"), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
