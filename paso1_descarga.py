#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASO 1 - Descarga cruda. contexto-btc / ssr_capstables / lote 2026-Q3.

No calcula nada. Solo descarga y guarda la respuesta literal del proveedor
para cada token que la regla D6 deja DENTRO del universo.

Anclajes doctrinales (ficha congelada, entrada 20):
  metrica_continua.fuente.denominador.agregado_del_proveedor_rechazado
    -> prohibido usar /stablecoincharts/all sin filtro. Se descarga token a
       token con ?stablecoin={id}.
"""
import json, os, sys, time, hashlib, urllib.request

BASE = "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin={}"
CRUDO = "/home/claude/crudo"

# ---------------------------------------------------------------- D6: FUERA
# 14 ya congelados en clasificacion_d6.py + 4 resueltos en esta sesion
FUERA_PREVIOS = {"213","237","173","129","272","132","244","241","282","243",
                 "23","21","109","172"}
FUERA_NUEVOS  = {"306","339","125","283"}
FUERA = FUERA_PREVIOS | FUERA_NUEVOS

# Tokens DENTRO cuya naturaleza NO pudo acreditarse con el protocolo
# documental congelado. Entran (la ausencia de evidencia no acredita la
# exclusion) y se declaran nominalmente.
NO_ACREDITADOS = {"340","13","328","398","332","407"}


def main():
    cand = json.load(open("/mnt/user-data/uploads/candidatos.json"))
    assert len(cand) == 100, "el universo candidato no tiene 100 tokens"

    ids_cand = {c["id"] for c in cand}
    faltan = FUERA - ids_cand
    assert not faltan, f"ids FUERA que no estan entre los candidatos: {faltan}"
    faltan = NO_ACREDITADOS - ids_cand
    assert not faltan, f"ids no acreditados fuera del candidato: {faltan}"

    dentro = [c for c in cand if c["id"] not in FUERA]
    print(f"candidatos: {len(cand)}  FUERA(D6): {len(FUERA)}  DENTRO: {len(dentro)}")
    assert len(dentro) == 82, f"se esperaban 82 DENTRO, hay {len(dentro)}"

    os.makedirs(CRUDO, exist_ok=True)
    for i, c in enumerate(dentro, 1):
        destino = os.path.join(CRUDO, f"{c['id']}.json")
        if os.path.exists(destino):
            continue
        url = BASE.format(c["id"])
        for intento in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    bruto = r.read()
                break
            except Exception as e:
                if intento == 3:
                    print(f"FALLO {c['id']} {c['symbol']}: {e}", file=sys.stderr)
                    sys.exit(1)
                time.sleep(2 * (intento + 1))
        json.loads(bruto)          # validacion: debe ser JSON legible
        open(destino, "wb").write(bruto)
        print(f"[{i:3d}/82] id={c['id']:>4}  {c['symbol']:<12} "
              f"{len(bruto)/1024:8.1f} KB  sha={hashlib.sha256(bruto).hexdigest()[:8]}")
        time.sleep(0.25)

    print("\ndescarga completa")


if __name__ == "__main__":
    main()
