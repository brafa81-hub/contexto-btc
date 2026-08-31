"""
ANALIZAR EVENTO — se ejecuta solo cuando disparador_precio.py detecta algo.

Coste: este script es el único de todo el pipeline de vigilancia que llama
a la API, y solo corre cuando ya hay un movimiento extremo confirmado por
disparador_precio.py (evaluación puramente numérica, coste cero). Según el
backtest de 15 años, eso ocurre entre 4 y 9 veces al año en el régimen
actual — el coste real de este pipeline es el de unas pocas llamadas al
mes, no de las ~2.190 comprobaciones anuales que hace el disparador.

QUÉ HACE
--------
Pide al modelo un análisis de impacto con la misma estructura acordada
para el pipeline semanal de noticias: verificación, mecanismo, dirección
y magnitud, horizonte, si ya está descontado, qué lo invalidaría, alcance.
La diferencia es que aquí el disparador ya confirmó el hecho objetivo (el
precio se movió); lo que pide el análisis es el porqué probable, con la
misma disciplina de no inventar certeza donde no la hay.

DÓNDE QUEDA EL RESULTADO
--------------------------
Se añade a eventos.json, un array append-only en el repo. El panel puede
leerlo y mostrar el más reciente; el histórico completo queda como
registro auditable de cada vez que el disparador saltó y qué se dijo
entonces — igual que el diario.py guarda las decisiones, esto guarda los
análisis del sistema.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

from data_loader import load_price_csv
from disparador_precio import evaluar, texto_disparo

MODELO = "claude-sonnet-4-6"
ARCHIVO_EVENTOS = "eventos.json"

PROMPT_SISTEMA = """Eres el analista de eventos de un panel de contexto de \
Bitcoin. Se te informa de un movimiento de precio extremo ya confirmado \
por un cálculo objetivo (no lo evalúas tú). Tu trabajo es dar contexto \
sobre el porqué probable, con esta estructura exacta:

1. VERIFICACIÓN: qué se sabe con certeza y qué es especulación en este \
momento.
2. MECANISMO: por qué algo así movería el precio, si hay una causa \
identificable.
3. DIRECCIÓN Y MAGNITUD: compara con episodios históricos análogos si \
existen. No inventes precisión que no tienes.
4. HORIZONTE: si el efecto (si lo hay) es de horas, semanas o meses.
5. YA DESCONTADO: si el mercado pudo haber anticipado esto antes del \
movimiento.
6. QUÉ LO INVALIDARÍA: qué confirmaría que esta lectura está equivocada.
7. ALCANCE: si es específico de BTC, de cripto en general, o macro.

Sé honesto sobre la incertidumbre. Si no hay una causa clara identificable \
en las últimas horas, dilo explícitamente en vez de forzar una narrativa. \
Este análisis es contexto para una persona que ya vio el movimiento en su \
panel — no repitas el dato numérico, ya lo tiene."""


def llamar_api(disparo: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Falta ANTHROPIC_API_KEY en el entorno.")

    mensaje = (
        f"Movimiento detectado: BTC {disparo['retorno']:+.1f}% en un día "
        f"({disparo['direccion']}) el {disparo['fecha']:%d/%m/%Y}. "
        f"Umbral que lo disparó: ±{disparo['umbral_pct']:.1f}% "
        f"(volatilidad reciente: {disparo['vol_30d_diaria_pct']:.1f}% diario). "
        f"Da tu análisis de contexto siguiendo la estructura indicada."
    )

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODELO,
            "max_tokens": 1200,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": mensaje}],
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    bloques = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(bloques).strip()


def guardar_evento(disparo: dict, analisis: str) -> None:
    registro = {
        "fecha": disparo["fecha"].strftime("%Y-%m-%d"),
        "generado": datetime.now(timezone.utc).isoformat(),
        "retorno_pct": round(disparo["retorno"], 2),
        "direccion": disparo["direccion"],
        "umbral_pct": round(disparo["umbral_pct"], 2),
        "vol_referencia_pct": round(disparo["vol_30d_diaria_pct"], 2),
        "analisis": analisis,
        "modelo": MODELO,
    }

    eventos = []
    if os.path.exists(ARCHIVO_EVENTOS):
        try:
            with open(ARCHIVO_EVENTOS, "r", encoding="utf-8") as f:
                eventos = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            eventos = []

    eventos.append(registro)
    with open(ARCHIVO_EVENTOS, "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)

    print(f"Guardado en {ARCHIVO_EVENTOS} ({len(eventos)} eventos en total)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv"
    disparo = evaluar(load_price_csv(path))

    if not disparo.get("disparo"):
        print("Sin disparo activo; este script no debería haberse llamado.")
        sys.exit(0)

    print(texto_disparo(disparo))
    print("\nLlamando a la API para el análisis de contexto...")
    analisis = llamar_api(disparo)
    print("\n" + analisis)

    guardar_evento(disparo, analisis)
