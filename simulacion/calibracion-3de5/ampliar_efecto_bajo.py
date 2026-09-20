"""
ampliar_efecto_bajo.py — Amplia SOLO el nivel efecto_bajo con semillas
nuevas, sin tocar nada mas.

Motivo: bajo una tasa base realista, efecto_bajo aporta entre el 24% y el
48% de las variables que llegan a EN_CONFIRMACION, pero la medicion previa
solo dejo 34 (uniforme) / 39 (concentrado) casos. Es el cuello de botella
de precision de la curva P(CONFIRMADA | theta_B2).

Reutiliza SIN MODIFICAR medicion_supervivencia.correr_nivel_con_desglose,
que a su vez reutiliza pipeline_end_to_end.procesar_replica / aplicar_by /
forward_de_replica del motor validado
(sha256 04e5a9cc606d35957ea01dc1d4d735cb93fba0c17f77a4ec6d1679bebbabd66d).

Semillas: arrancan en 900000 (uniforme) / 1900000 (concentrado), muy lejos
del rango 70000/1070000 usado en la medicion previa, para que no haya
solape de replicas.

NO escribe en v2.json, filtro.py ni registro.json.
"""
import sys, json, argparse
sys.path.insert(0, '.')

import medicion_supervivencia as ms
import pipeline_end_to_end as pe

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1600)
    ap.add_argument("--escenario", type=str, required=True)
    ap.add_argument("--out", type=str, default="ampliacion_efecto_bajo.json")
    args = ap.parse_args()

    phi = pe.ESCENARIOS_PHI[args.escenario]
    theta = pe.NIVELES["efecto_bajo"]
    semilla_base = 900000 if args.escenario == "uniforme" else 1900000

    print(f"=== AMPLIACION efecto_bajo / {args.escenario} (phi={phi}) ===")
    print(f"n={args.n}, semilla_base={semilla_base}, theta_nominal={theta}")

    res = ms.correr_nivel_con_desglose(
        "efecto_bajo", theta, n_replicas=args.n,
        semilla_base=semilla_base, phi=phi,
    )

    try:
        with open(args.out, "r", encoding="utf-8") as f:
            todo = json.load(f)
    except FileNotFoundError:
        todo = {}
    todo[args.escenario] = res
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(todo, f, indent=2, ensure_ascii=False, default=str)
    print(f"Guardado en {args.out}")
