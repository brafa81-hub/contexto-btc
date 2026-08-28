"""
REGISTRO HISTÓRICO — guarda una foto de cada informe generado.

Por qué existe: dentro de seis meses querrás poder mirar atrás y ver qué decía
el sistema cuando tomaste una decisión. Sin registro, esa información se pierde.

Además permite responder preguntas como:
  - ¿Cuándo estuvo el sistema marcando "barato" por última vez?
  - ¿Cómo ha evolucionado el MVRV en los últimos meses?
  - ¿Compré cuando el panel decía "caro"? (revisión honesta de tus decisiones)

El registro es un CSV simple. Se puede abrir en Excel.

USO:
    python registro.py guardar btc_long.csv          # añade la foto de hoy
    python registro.py guardar btc_long.csv --onchain btc_onchain.csv
    python registro.py ver                            # muestra el histórico
    python registro.py nota "Compré 500€"             # añade una anotación tuya
"""

import argparse
import csv
import os
from datetime import datetime

import pandas as pd

REGISTRO_PATH = "registro_btc.csv"

CAMPOS = [
    "fecha_registro", "fecha_datos", "precio",
    "vs_sma50", "vs_sma200", "vs_sma1000",
    "percentil_valoracion", "etiqueta_valoracion", "mayer_multiple",
    "drawdown_desde_ath", "dias_desde_ath",
    "ret_30d", "ret_90d", "ret_365d",
    "volatilidad_90d",
    "mvrv", "mvrv_zscore", "realized_price",
    "nota",
]


def guardar_registro(csv_precio: str, csv_onchain: str = None, nota: str = ""):
    from data_loader import load_price_csv
    from contexto_btc import calcular_situacion, calcular_valoracion, calcular_ciclo

    df = load_price_csv(csv_precio)
    s = calcular_situacion(df)
    v = calcular_valoracion(df)
    c = calcular_ciclo(df)

    fila = {
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fecha_datos": df.index[-1].strftime("%Y-%m-%d"),
        "precio": round(s["precio"], 2),
        "vs_sma50": round(s["vs_sma50"], 2),
        "vs_sma200": round(s["vs_sma200"], 2),
        "vs_sma1000": round(s["vs_sma1000"], 2) if pd.notna(s["vs_sma1000"]) else "",
        "percentil_valoracion": round(v["percentil"], 1),
        "etiqueta_valoracion": v["etiqueta"],
        "mayer_multiple": round(v["mayer_multiple"], 3),
        "drawdown_desde_ath": round(c["drawdown_actual"], 2),
        "dias_desde_ath": c["dias_desde_ath"],
        "ret_30d": round(c["ret_30d"], 2) if pd.notna(c["ret_30d"]) else "",
        "ret_90d": round(c["ret_90d"], 2) if pd.notna(c["ret_90d"]) else "",
        "ret_365d": round(c["ret_365d"], 2) if pd.notna(c["ret_365d"]) else "",
        "volatilidad_90d": round(s["vol_actual"], 1),
        "mvrv": "", "mvrv_zscore": "", "realized_price": "",
        "nota": nota,
    }

    if csv_onchain and os.path.exists(csv_onchain):
        try:
            from onchain import cargar_onchain, calcular_metricas
            dfo = calcular_metricas(cargar_onchain(csv_onchain))
            u = dfo.iloc[-1]
            fila["mvrv"] = round(u["mvrv"], 3) if pd.notna(u["mvrv"]) else ""
            fila["mvrv_zscore"] = round(u["mvrv_zscore"], 3) if pd.notna(u["mvrv_zscore"]) else ""
            fila["realized_price"] = round(u["realized_price"], 2) if pd.notna(u["realized_price"]) else ""
        except Exception as e:
            print(f"Aviso: no se pudieron añadir datos on-chain ({e})")

    existe = os.path.exists(REGISTRO_PATH)
    with open(REGISTRO_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if not existe:
            w.writeheader()
        w.writerow(fila)

    print(f"Registro guardado en {REGISTRO_PATH}")
    print(f"  {fila['fecha_datos']} · ${fila['precio']:,.0f} · {fila['etiqueta_valoracion']} "
          f"(percentil {fila['percentil_valoracion']})")


def ver_registro(n: int = 20):
    if not os.path.exists(REGISTRO_PATH):
        print(f"Todavía no hay registro. Créalo con: python registro.py guardar btc_long.csv")
        return
    df = pd.read_csv(REGISTRO_PATH)
    if df.empty:
        print("El registro está vacío.")
        return

    print(f"\nREGISTRO HISTÓRICO — {len(df)} entradas\n")
    cols = ["fecha_datos", "precio", "percentil_valoracion", "etiqueta_valoracion",
            "drawdown_desde_ath", "mvrv", "nota"]
    cols = [c for c in cols if c in df.columns]
    vista = df[cols].tail(n)
    print(vista.to_string(index=False))
    print()

    # Resumen útil
    if len(df) > 1:
        print(f"Primer registro:  {df['fecha_datos'].iloc[0]}  ${df['precio'].iloc[0]:,.0f}")
        print(f"Último registro:  {df['fecha_datos'].iloc[-1]}  ${df['precio'].iloc[-1]:,.0f}")
        cambio = (df['precio'].iloc[-1] / df['precio'].iloc[0] - 1) * 100
        print(f"Cambio de precio desde el primer registro: {cambio:+.1f}%")


def añadir_nota(texto: str):
    """Añade una anotación al último registro (ej. 'compré 500€')."""
    if not os.path.exists(REGISTRO_PATH):
        print("No hay registro todavía.")
        return
    df = pd.read_csv(REGISTRO_PATH)
    if df.empty:
        print("El registro está vacío.")
        return
    anterior = df.loc[df.index[-1], "nota"]
    nueva = f"{anterior} | {texto}" if pd.notna(anterior) and str(anterior).strip() else texto
    df.loc[df.index[-1], "nota"] = nueva
    df.to_csv(REGISTRO_PATH, index=False)
    print(f"Nota añadida al registro del {df['fecha_datos'].iloc[-1]}: {texto}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    g = sub.add_parser("guardar")
    g.add_argument("csv", nargs="?", default="btc_long.csv")
    g.add_argument("--onchain", default="btc_onchain.csv")
    g.add_argument("--nota", default="")

    vsub = sub.add_parser("ver")
    vsub.add_argument("-n", type=int, default=20)

    nsub = sub.add_parser("nota")
    nsub.add_argument("texto")

    args = p.parse_args()

    if args.cmd == "guardar":
        guardar_registro(args.csv, args.onchain, args.nota)
    elif args.cmd == "ver":
        ver_registro(args.n)
    elif args.cmd == "nota":
        añadir_nota(args.texto)
    else:
        p.print_help()
