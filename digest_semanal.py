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
from fuentes_noticias import recoger_noticias

MODELO = "claude-sonnet-5"
ARCHIVO_NOTICIAS = "noticias.json"
DIAS_VENTANA = 8  # una semana + margen, por si el workflow se retrasa

# ---------------------------------------------------------------
# FILTRADO PREVIO — barato, determinista y auto-auditable
#
# En la primera ejecución real (31/08/2026) se descubrió que enviar a la
# API la lista cruda de EDGAR era caro e inútil:
#
#   - De 15 resultados, solo 12 eran documentos distintos. EDGAR devuelve
#     un resultado por EXHIBIT, no por filing.
#   - 7 de los 12 eran notas estructuradas de bancos que mencionan un ETF
#     de BTC como subyacente. Ruido rutinario semanal.
#
# EL PROBLEMA DE FILTRAR CON UNA LISTA FIJA
# ------------------------------------------
# Una lista de emisores escrita a mano, basada en una sola semana de
# datos, es exactamente el tipo de generalización que este proyecto ha
# ido descartando (ver filtro.py: el hash ribbon parecía coherente con 4
# años y se disolvió con 15). Si un emisor "de ruido" presenta algún día
# un filing que sí importa, una lista fija lo tira en silencio.
#
# Y el fallo silencioso es el peor: nadie se entera.
#
# CÓMO SE RESUELVE AQUÍ
# ---------------------
# El filtro NO decide por sí solo qué es ruido. Descarta únicamente lo que
# es ruido por CONSTRUCCIÓN (duplicados exactos del mismo documento) y
# marca el resto con una señal de prioridad. Los de prioridad baja no se
# eliminan: se agrupan y se mencionan al modelo en una sola línea, para
# que pueda pedir atención sobre ellos si detecta algo anómalo.
#
# Coste: unas pocas decenas de tokens extra. A cambio, nada desaparece
# sin dejar rastro, y no hace falta que nadie revise listas a mano.
# ---------------------------------------------------------------

# Patrones que, HISTÓRICAMENTE, corresponden a emisiones rutinarias. No se
# usan para eliminar, solo para bajar prioridad. Si algún día uno de estos
# resulta relevante, el modelo lo ve igualmente y puede señalarlo.
PATRONES_RUTINA = (
    "jpmorgan", "morgan stanley", "bank of nova scotia", "goldman sachs",
    "citigroup", "bofa finance", "royal bank of canada", "toronto-dominion",
    "ubs ag", "barclays bank", "hsbc", "wells fargo finance",
)

FORMULARIOS_RUTINA = ("424B2", "424B5", "424B3", "FWP")


def prioridad(filing: dict) -> str:
    """
    'alta' o 'baja'. Baja no significa descartado — significa que va
    resumido en una línea en vez de con análisis individual.
    """
    empresa = (filing.get("empresa") or "").lower()
    formulario = (filing.get("formulario") or "").upper()

    if any(p in empresa for p in PATRONES_RUTINA) and formulario in FORMULARIOS_RUTINA:
        return "baja"
    return "alta"


def preparar_filings(crudos: list) -> dict:
    """
    Deduplica y clasifica por prioridad. No elimina nada salvo duplicados
    exactos, que son ruido por construcción de la propia API de EDGAR.
    """
    vistos, unicos = set(), []
    for f in crudos:
        acc = f.get("accession")
        if acc and acc not in vistos:
            vistos.add(acc)
            unicos.append(f)

    altas = [f for f in unicos if prioridad(f) == "alta"]
    bajas = [f for f in unicos if prioridad(f) == "baja"]

    return {
        "altas": altas,
        "bajas": bajas,
        "n_crudos": len(crudos),
        "n_duplicados": len(crudos) - len(unicos),
    }


PROMPT_SISTEMA = """Eres el analista semanal de un panel de contexto de \
Bitcoin. La persona que lo lee no tiene tiempo ni conocimiento técnico \
para verificar filings por su cuenta: confía en tu criterio para decidir \
qué merece su atención. Sé el filtro que ella no puede ser.

LO QUE PUEDES Y NO PUEDES VER: solo recibes METADATOS (empresa, tipo de \
formulario, fecha, enlace). NO has leído el contenido. Por tanto:

- Di lo que el formulario y el emisor permiten inferir, marcando que es \
inferencia.
- NO afirmes qué dice el filing por dentro.
- Un análisis honesto y corto vale más que uno completo e inventado.

Recibirás dos grupos:

**PRIORITARIOS**: analiza cada uno, breve (una o dos frases por punto):
1. QUÉ ES: qué tipo de evento sugiere este formulario para este emisor.
2. POR QUÉ PODRÍA IMPORTAR: mecanismo por el que afectaría a BTC.
3. MAGNITUD PROBABLE: comparado con precedentes. Si no tienes base para \
estimarla, dilo.
4. HORIZONTE: días, semanas o meses.

**RUTINARIOS**: emisiones bancarias habituales (notas estructuradas con \
ETFs de BTC como subyacente). Normalmente son ruido y basta con una línea \
diciendo cuántos hubo. PERO revísalos: si detectas algo anómalo — un \
emisor que no suele aparecer, un volumen inusual de filings del mismo \
banco, un formulario raro para ese emisor — dilo explícitamente. Eres la \
única salvaguarda contra que algo relevante se pierda en ese grupo.

**NOTICIAS NIVEL 1** (fuente oficial: Reserva Federal): son hechos \
publicados por el propio organismo. Puedes tratarlos como confirmados. \
Analiza solo los que puedan afectar a BTC.

**NOTICIAS NIVEL 3** (prensa especializada): NO son fuente primaria. \
Trátalos como no confirmados salvo que el propio titular remita a un \
organismo oficial. Aquí tu trabajo es sobre todo descartar: la mayoría \
serán titulares de relleno, precios o especulación, y esos no merecen \
ni una línea. Menciona solo lo que sea un hecho verificable con impacto \
plausible — regulación de cualquier país, hackeos, quiebras, decisiones \
judiciales. Si algo parece importante pero solo lo dice un medio, dilo \
así: "reportado por [medio], sin confirmación oficial".

CIERRE OBLIGATORIO: termina con una sección "QUÉ HACER ESTA SEMANA" de \
una a tres líneas, en lenguaje llano, sin jerga. Si nada merece atención, \
dilo claramente: "Nada esta semana requiere tu atención" es una \
conclusión perfectamente válida y útil. No inventes relevancia para \
justificar el análisis."""


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


def llamar_api(grupos: dict, noticias: dict = None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Falta ANTHROPIC_API_KEY en el entorno.")

    def formatear(fs):
        return "\n".join(
            f"- [{f['fecha']}] {f['formulario']} · {f['empresa']} · {f['url'] or 'sin enlace'}"
            for f in fs
        )

    def formatear_noticias(items):
        return "\n".join(
            f"- [{i['fecha']}] {i['titulo']} ({i['fuente']})"
            + (f"\n    {i['resumen']}" if i["resumen"] else "")
            for i in items
        )

    partes = []
    if grupos["altas"]:
        partes.append("**PRIORITARIOS**\n" + formatear(grupos["altas"]))
    else:
        partes.append("**PRIORITARIOS**\n(ninguno esta semana)")

    if grupos["bajas"]:
        partes.append("**RUTINARIOS**\n" + formatear(grupos["bajas"]))

    if noticias:
        if noticias.get("nivel_1"):
            partes.append("**NOTICIAS NIVEL 1**\n"
                          + formatear_noticias(noticias["nivel_1"]))
        if noticias.get("nivel_3"):
            partes.append("**NOTICIAS NIVEL 3**\n"
                          + formatear_noticias(noticias["nivel_3"]))
        # Las fuentes caídas se informan al modelo: si una semana falta
        # cobertura, debe poder decirlo en vez de dar por hecho que no
        # pasó nada en esa área.
        caidas = [e["fuente"] for e in noticias.get("estado_fuentes", [])
                  if not e["ok"]]
        if caidas:
            partes.append("**AVISO DE COBERTURA**\nEstas fuentes no "
                          "respondieron esta semana: " + ", ".join(caidas)
                          + ". Menciónalo si es relevante para la confianza "
                            "del análisis.")

    mensaje = (
        "Información de esta semana relacionada con Bitcoin "
        "(filings de la SEC y noticias):\n\n"
        + "\n\n".join(partes)
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
            # Con el filtrado previo (deduplicación + descarte de ruido
            # bancario), la lista pasó de 15 resultados crudos a ~5 filings
            # reales. 8000 da margen holgado para analizarlos con la
            # estructura de 5 puntos, incluyendo el razonamiento interno
            # de Sonnet 5, que también consume de este presupuesto.
            "max_tokens": 8000,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": mensaje}],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()

    # Diagnóstico: se registra siempre el motivo de parada, el uso de
    # tokens y si hubo bloque de razonamiento, para que un análisis vacío
    # no vuelva a pasar desapercibido ni sea necesario adivinar la causa
    # leyendo el JSON crudo como hizo falta la primera vez.
    stop = data.get("stop_reason", "?")
    uso = data.get("usage", {})
    tipos = [b.get("type") for b in data.get("content", [])]
    print(f"  stop_reason={stop}  tokens_entrada={uso.get('input_tokens')}  "
          f"tokens_salida={uso.get('output_tokens')}  bloques={tipos}")

    bloques = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    texto = "\n".join(bloques).strip()

    if not texto:
        raise RuntimeError(
            f"La API respondió sin texto utilizable (stop_reason={stop}, "
            f"bloques={tipos}). Si stop_reason sigue siendo 'max_tokens' con "
            f"este límite, el número de filings de la semana probablemente "
            f"superó el margen — considera subir max_tokens de nuevo o "
            f"dividir el análisis en dos llamadas."
        )

    if stop == "max_tokens":
        texto += "\n\n[Aviso: la respuesta se cortó por límite de longitud.]"

    return texto


def guardar_digest(grupos: dict, analisis: str, noticias: dict = None) -> None:
    todos = grupos["altas"] + grupos["bajas"]
    registro = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "periodo_dias": DIAS_VENTANA,
        "n_prioritarios": len(grupos["altas"]),
        "n_rutinarios": len(grupos["bajas"]),
        "n_duplicados_descartados": grupos["n_duplicados"],
        "accessions_incluidos": [f["accession"] for f in todos],
        "n_noticias_nivel1": len(noticias["nivel_1"]) if noticias else 0,
        "n_noticias_nivel3": len(noticias["nivel_3"]) if noticias else 0,
        "fuentes_caidas": [e["fuente"] for e in noticias["estado_fuentes"]
                           if not e["ok"]] if noticias else [],
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
    # --- 1. Filings de la SEC (nivel 1, fuente primaria) ---
    print(f"Buscando filings de la SEC de los últimos {DIAS_VENTANA} días...")
    try:
        todos = buscar_filings(dias=DIAS_VENTANA)
    except Exception as e:
        print(f"Error consultando la SEC: {type(e).__name__}: {e}")
        todos = []

    g = preparar_filings(todos)
    ya_vistos = cargar_analizados()
    g["altas"] = [f for f in g["altas"] if f["accession"] not in ya_vistos]
    g["bajas"] = [f for f in g["bajas"] if f["accession"] not in ya_vistos]

    print(f"  {g['n_crudos']} resultados de EDGAR")
    print(f"  −{g['n_duplicados']} duplicados (EDGAR devuelve uno por exhibit)")
    print(f"  {len(g['altas'])} prioritarios · {len(g['bajas'])} rutinarios (nuevos)")

    # --- 2. Noticias (Fed nivel 1 + prensa nivel 3) ---
    # El fallo de esta parte NO impide el digest: si las fuentes de noticias
    # caen, el análisis sigue haciéndose con los filings y el propio modelo
    # recibe aviso de qué cobertura falta.
    print(f"\nRecogiendo noticias de los últimos {DIAS_VENTANA} días...")
    try:
        noticias = recoger_noticias(dias=DIAS_VENTANA)
        for e in noticias["estado_fuentes"]:
            marca = "ok " if e["ok"] else "FALLO"
            print(f"  [{marca}] {e['fuente']}: {e['n']} items"
                  + (f"  ({e['error']})" if e["error"] else ""))
        print(f"  {len(noticias['nivel_1'])} de nivel 1 · "
              f"{len(noticias['nivel_3'])} de nivel 3 "
              f"({noticias['n_duplicados']} duplicados entre medios)")
    except Exception as e:
        print(f"  Error recogiendo noticias: {type(e).__name__}: {e}")
        noticias = None

    hay_filings = bool(g["altas"] or g["bajas"])
    hay_noticias = bool(noticias and (noticias["nivel_1"] or noticias["nivel_3"]))

    if not hay_filings and not hay_noticias:
        print("\nNada nuevo que analizar esta semana.")
        sys.exit(0)

    print("\nLlamando a la API para el análisis...")
    analisis = llamar_api(g, noticias)
    print("\n" + analisis)

    guardar_digest(g, analisis, noticias)
