"""
DIGEST SEMANAL DE NOTICIAS — se ejecuta una vez a la semana, vía GitHub Actions.

QUÉ HACE
--------
1. Recoge filings recientes de la SEC que mencionen Bitcoin (fuente_sec.py,
   nivel 1: hecho verificable, no interpretación).
2. Si hay algo nuevo desde la última ejecución, pide a Sonnet un análisis
   de impacto con la estructura acordada.
3. Guarda el resultado en noticias.json, append-only, igual que hace
   analizar_evento.py con eventos.json.

POR QUÉ SOLO LA SEC DE MOMENTO
---------------------------------
Farside (flujos de ETF) quedó fuera del pipeline automático: bloquea
scraping (ver fetch_etf.py) y solo se pudo conseguir el dato a mano vía
HTML. No tiene sentido automatizar algo que requiere intervención manual
cada vez — eso no es un pipeline, es trabajo disfrazado de automatización.

Si en el futuro aparece una fuente de flujos de ETF accesible por API
(algunos proveedores de pago la ofrecen), se puede añadir aquí sin tocar
el resto de la estructura.

POR QUÉ NO SE REPITE EL MISMO FILING DOS SEMANAS SEGUIDAS
-------------------------------------------------------------
Se guarda qué accession numbers ya se analizaron (en el propio
noticias.json) y se filtran antes de llamar a la API. Sin esto, cada
ejecución volvería a analizar y facturar por filings de la semana
anterior que no han cambiado.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

from fuente_sec import buscar_filings

MODELO = "claude-sonnet-5"
ARCHIVO_NOTICIAS = "noticias.json"
DIAS_VENTANA = 8  # una semana + margen, por si el workflow se retrasa

PROMPT_SISTEMA = """Eres el analista semanal de un panel de contexto de \
Bitcoin. Se te da una lista de filings recientes de la SEC que mencionan \
Bitcoin o ETFs spot de Bitcoin. No sabes de antemano si son relevantes — \
tu primer trabajo es decidir cuáles importan y cuáles son ruido \
administrativo (renovaciones rutinarias, correcciones menores).

Para cada filing que consideres relevante, da un análisis con esta \
estructura exacta:

1. VERIFICACIÓN: qué dice el filing con certeza (es fuente primaria, así \
que esto debería ser sólido).
2. MECANISMO: por qué esto podría importar para el precio o el mercado \
de BTC.
3. DIRECCIÓN Y MAGNITUD: compara con precedentes si los conoces. No \
inventes precisión que no tienes.
4. HORIZONTE: si el efecto, de haberlo, es de días, semanas o meses.
5. YA DESCONTADO: si es plausible que el mercado ya lo supiera antes de \
este filing.
6. QUÉ LO INVALIDARÍA: qué haría que esta lectura estuviera equivocada.
7. ALCANCE: específico de una empresa, del sector ETF, o del mercado BTC \
en general.

Si ningún filing de la lista es relevante (trámites rutinarios, ruido \
administrativo), dilo explícitamente en una frase y no fuerces un \
análisis de siete puntos sobre algo que no lo merece. Sé honesto sobre \
la incertidumbre en todo momento."""


def cargar_analizados() -> set:
    """
    Accession numbers ya procesados con éxito, para no repetir ni facturar
    de más. Los digests con 'analisis' vacío (como el fallo del 31/08/2026,
    causado por max_tokens agotándose antes del texto) NO cuentan como
    vistos: sus filings deben poder reintentarse.
    """
    if not os.path.exists(ARCHIVO_NOTICIAS):
        return set()
    try:
        with open(ARCHIVO_NOTICIAS, "r", encoding="utf-8") as f:
            registros = json.load(f)
        vistos = set()
        for r in registros:
            if r.get("analisis", "").strip():
                vistos.update(r.get("accessions_incluidos", []))
        return vistos
    except (json.JSONDecodeError, FileNotFoundError):
        return set()


def llamar_api(filings: list) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Falta ANTHROPIC_API_KEY en el entorno.")

    lista = "\n".join(
        f"- [{f['fecha']}] {f['formulario']} · {f['empresa']} · {f['url'] or 'sin enlace'}"
        for f in filings
    )
    mensaje = f"Filings de la SEC de esta semana relacionados con Bitcoin:\n\n{lista}"

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODELO,
            "max_tokens": 3000,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": mensaje}],
        },
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()

    # Diagnóstico: se registra siempre el motivo de parada y el uso de
    # tokens, para que un análisis vacío no vuelva a pasar desapercibido
    # como pasó en la primera ejecución real (stop_reason venía en
    # 'max_tokens' antes de que el modelo llegara a escribir texto).
    stop = data.get("stop_reason", "?")
    uso = data.get("usage", {})
    print(f"  stop_reason={stop}  tokens_entrada={uso.get('input_tokens')}  "
          f"tokens_salida={uso.get('output_tokens')}")

    bloques = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    texto = "\n".join(bloques).strip()

    if not texto:
        # No se guarda un digest vacío en silencio: mejor fallar de forma
        # visible que dejar un registro sin contenido en noticias.json.
        raise RuntimeError(
            f"La API respondió sin texto utilizable (stop_reason={stop}). "
            f"Respuesta completa para depurar: {json.dumps(data)[:2000]}"
        )

    if stop == "max_tokens":
        texto += "\n\n[Aviso: la respuesta se cortó por límite de longitud.]"

    return texto


def guardar_digest(filings: list, analisis: str) -> None:
    registro = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "periodo_dias": DIAS_VENTANA,
        "n_filings": len(filings),
        "accessions_incluidos": [f["accession"] for f in filings],
        "analisis": analisis,
        "modelo": MODELO,
    }

    digests = []
    if os.path.exists(ARCHIVO_NOTICIAS):
        try:
            with open(ARCHIVO_NOTICIAS, "r", encoding="utf-8") as f:
                digests = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            digests = []

    digests.append(registro)
    # se conservan los últimos 26 (medio año) para no dejar crecer el
    # archivo sin límite; el histórico completo sigue en el historial
    # de commits de git si hace falta consultarlo
    digests = digests[-26:]

    with open(ARCHIVO_NOTICIAS, "w", encoding="utf-8") as f:
        json.dump(digests, f, ensure_ascii=False, indent=2)

    print(f"Guardado en {ARCHIVO_NOTICIAS} ({len(digests)} digests conservados)")


if __name__ == "__main__":
    print(f"Buscando filings de la SEC de los últimos {DIAS_VENTANA} días...")
    try:
        todos = buscar_filings(dias=DIAS_VENTANA)
    except Exception as e:
        print(f"Error consultando la SEC: {type(e).__name__}: {e}")
        sys.exit(1)

    ya_vistos = cargar_analizados()
    nuevos = [f for f in todos if f["accession"] not in ya_vistos]

    print(f"  {len(todos)} filings totales, {len(nuevos)} nuevos desde la última vez")

    if not nuevos:
        print("Nada nuevo que analizar esta semana.")
        sys.exit(0)

    print("\nLlamando a la API para el análisis...")
    analisis = llamar_api(nuevos)
    print("\n" + analisis)

    guardar_digest(nuevos, analisis)
