"""
JUICIO DE CONTEXTO — integra los bloques del panel en una lectura conjunta.

QUÉ HACE Y QUÉ NO
------------------
Toma los resultados que los bloques 01-08 ya calcularon y le pide al
modelo una sola cosa: **qué historia cuentan juntos, y dónde se
contradicen**. No calcula nada nuevo. No predice dirección. No recomienda
comprar ni vender.

Es la única capa del sistema donde interviene un modelo sobre los datos
numéricos, y su papel está deliberadamente acotado a lo que el código
hace mal: detectar que dos bloques dicen cosas incompatibles y explicarlo
en lenguaje llano.

LA RESTRICCIÓN QUE HACE ESTO SEGURO
------------------------------------
El riesgo evidente de esta capa es que el modelo, sin mala intención,
convierta "los flujos de ETF han mejorado" en "BTC probablemente subirá".
Eso sería atribuir capacidad direccional a una variable que se midió y no
la tiene.

Para impedirlo, el prompt incluye el registro completo de
CANDIDATAS_EVALUADAS de filtro.py: las doce variables con su veredicto
real. No es una instrucción vaga de "sé prudente" — es una lista concreta
de qué NO puede afirmarse, generada desde el mismo sitio donde viven los
resultados de los experimentos. Si mañana una variable cambia de estado
en filtro.py, la restricción se actualiza sola.

POR QUÉ NO HAY "PROBABILIDAD DE SUBIDA"
----------------------------------------
El experimento probabilidad_contexto_v1.1 se diseñó exactamente para
producir ese número, con protocolo congelado antes de ver datos. Resultó
SIN EVIDENCIA: ninguna celda alcanzó n≥20 y ≥10pp sobre el benchmark.
Mostrar un porcentaje de dirección aquí sería inventar la salida que ese
experimento demostró que no se puede construir.

MODELO
------
Sonnet para el juicio semanal habitual. La distinción Sonnet/Opus tiene
sentido si algún día se añade una revisión trimestral profunda, pero el
juicio semanal no la necesita: integrar ocho números y detectar
contradicciones no es una tarea de razonamiento largo.
"""

import json
import os
from datetime import datetime, timezone

import requests

MODELO = "claude-sonnet-5"
ARCHIVO_JUICIO = "juicio.json"


def _bloque_restricciones() -> str:
    """
    Construye la lista de qué puede y qué no puede afirmarse, leída del
    registro real de experimentos. Si filtro.py no está disponible, se
    devuelve una restricción genérica más estricta en vez de ninguna.
    """
    try:
        from filtro import CANDIDATAS_EVALUADAS as C
    except ImportError:
        return ("NO dispones del registro de experimentos. En su ausencia, "
                "no atribuyas capacidad direccional a NINGUNA variable.")

    rechazadas, aceptadas, pendientes = [], [], []
    for nombre, d in C.items():
        estado = d.get("estado", "")
        if estado == "RECHAZADA":
            rechazadas.append(nombre)
        elif estado.startswith("ACEPTADA"):
            aceptadas.append(f"{nombre} ({estado})")
        else:
            pendientes.append(f"{nombre} ({estado})")

    return (
        "REGISTRO DE EXPERIMENTOS DEL SISTEMA (esto no es opinión, son "
        "resultados medidos sobre 15 años de datos):\n\n"
        f"MEDIDAS Y RECHAZADAS como señal direccional — NO puedes afirmar "
        f"que anticipen la dirección del precio: {', '.join(rechazadas)}.\n\n"
        f"ACEPTADAS, con el alcance exacto que indica su estado: "
        f"{', '.join(aceptadas)}.\n\n"
        f"SIN CONCLUSIÓN todavía: {', '.join(pendientes)}.\n\n"
        "Puedes mencionar cualquiera de estas variables como CONTEXTO "
        "(qué está pasando ahora), pero no como PREDICCIÓN. Ejemplo de lo "
        "que NO debes escribir: 'los flujos de ETF han mejorado, lo que "
        "favorece una subida'. Ejemplo correcto: 'los flujos de ETF han "
        "mejorado; esta variable se midió y no demostró anticipar la "
        "dirección del precio, así que es contexto de demanda, no señal'."
    )


PROMPT_SISTEMA = """Eres el analista de contexto de un panel de Bitcoin. \
Recibes los resultados que los bloques del panel ya han calculado con \
fórmulas fijas. Tu trabajo NO es calcular nada ni predecir el precio: es \
responder a una sola pregunta que el código hace mal y tú haces bien:

**¿Qué historia cuentan estos datos en conjunto, y dónde se contradicen?**

La persona que lee esto no tiene tiempo ni formación técnica para cruzar \
ocho bloques mentalmente. Hazlo tú.

Devuelve exactamente esta estructura, breve:

**Lo que coincide** — qué piezas del panel apuntan en la misma dirección \
(sobre riesgo y contexto, nunca sobre dirección del precio). Una o dos \
frases.

**Lo que se contradice** — qué piezas dicen cosas incompatibles, y qué \
implica esa tensión. Esto es lo más valioso de tu análisis: si el bloque \
de magnitud sugiere movimientos amplios y el de correlación indica poca \
diversificación, esas dos cosas juntas significan algo que ninguna dice \
por separado. Si no hay contradicciones reales, dilo en una línea y no \
las inventes.

**Qué vigilar** — una o dos cosas concretas que podrían cambiar esta \
lectura en las próximas semanas.

**En una frase** — la síntesis, en lenguaje llano.

REGLAS INNEGOCIABLES:
- No digas si el precio va a subir o bajar. El sistema midió esa \
capacidad y no la tiene.
- No recomiendes comprar, vender, entrar ni salir.
- No inventes cifras. Usa solo los números que te doy.
- Si los datos no dan para un juicio interesante, dilo. "El contexto es \
poco informativo esta semana" es una conclusión válida y útil."""


def construir_contexto(situacion: dict, valoracion: dict, ciclo: dict,
                       rango: dict, avisos_regimen: list,
                       correlacion: dict = None, texto_halving: str = "",
                       eventos: list = None) -> str:
    """Serializa el estado de los bloques en texto para el modelo."""
    L = []
    L.append("ESTADO ACTUAL DEL PANEL\n")

    L.append(f"Precio: ${situacion.get('precio', 0):,.0f}")
    L.append(f"Respecto a media 200 días: {situacion.get('vs_sma200', 0):+.1f}%")
    L.append(f"Caída desde máximos: {ciclo.get('drawdown_actual', 0):+.1f}%")
    L.append(f"Rentabilidad 90 días: {ciclo.get('ret_90d', 0):+.1f}%")
    L.append("")

    L.append(f"Valoración: percentil {valoracion.get('percentil', 0):.0f} "
             f"({valoracion.get('etiqueta', '?')})")
    L.append("  NOTA: este percentil ordenaba bien el retorno del año siguiente "
             "hasta 2020, pero ese orden se rompió desde 2021.")
    L.append("")

    L.append(f"Volatilidad 30d: {rango.get('vol', 0)*100:.0f}% "
             f"(cuartil {rango.get('cuartil', '?')}, "
             f"percentil {rango.get('vol_pct', 0):.0f})")
    b = rango.get("bandas", {})
    if b:
        L.append(f"Oscilación esperada en 30 días: "
                 f"{b.get('p50', {}).get('amplitud', 0)*100:.0f}% la mitad de "
                 f"los meses, {b.get('p95', {}).get('amplitud', 0)*100:.0f}% "
                 f"en 1 de cada 20")
    L.append("")

    if correlacion and correlacion.get("disponible"):
        L.append(f"Correlación con Nasdaq (180d): "
                 f"{correlacion.get('correlacion', 0):.2f} "
                 f"— {correlacion.get('etiqueta', '')}")
        c_ = correlacion.get("caidas", {})
        if c_:
            L.append(f"  Con este nivel, cuando el Nasdaq cayó >5% en un mes, "
                     f"BTC cayó también el {c_.get('acompana')}% de las veces "
                     f"(mediana {c_.get('mediana')}%)")
        L.append("")

    if avisos_regimen:
        L.append("AVISOS DE AUTOAUDITORÍA DEL PANEL:")
        for a in avisos_regimen:
            L.append(f"  [{a.get('nivel', '?')}] {a.get('texto', '')}")
        L.append("")

    if texto_halving:
        L.append(f"CICLO: {texto_halving}")
        L.append("")

    if eventos:
        L.append("EVENTOS PROGRAMADOS PRÓXIMOS:")
        for e in eventos[:4]:
            L.append(f"  {e['fecha']:%d/%m} (en {e['dias']} días): {e['nombre']}")
        L.append("")

    return "\n".join(L)


def llamar_api(contexto: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Falta ANTHROPIC_API_KEY en el entorno.")

    mensaje = f"{_bloque_restricciones()}\n\n---\n\n{contexto}"

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODELO,
            # Sonnet 5 razona antes de responder y ese razonamiento consume
            # del mismo presupuesto (ver incidencia en digest_semanal.py).
            # El juicio es corto, pero el margen evita quedarse sin espacio.
            "max_tokens": 4000,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": mensaje}],
        },
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()

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
            f"bloques={tipos})."
        )
    return texto


def guardar_juicio(juicio: str, contexto: str) -> None:
    registro = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "juicio": juicio,
        "contexto_usado": contexto,
        "modelo": MODELO,
    }
    previos = []
    if os.path.exists(ARCHIVO_JUICIO):
        try:
            with open(ARCHIVO_JUICIO, "r", encoding="utf-8") as f:
                previos = json.load(f)
        except (json.JSONDecodeError, OSError):
            previos = []
    previos.append(registro)
    previos = previos[-26:]  # medio año
    with open(ARCHIVO_JUICIO, "w", encoding="utf-8") as f:
        json.dump(previos, f, ensure_ascii=False, indent=2)
    print(f"Guardado en {ARCHIVO_JUICIO} ({len(previos)} juicios conservados)")


def cargar_juicio(path: str = ARCHIVO_JUICIO) -> dict | None:
    """Último juicio generado, para mostrarlo en el panel."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            js = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not js or not js[-1].get("juicio", "").strip():
        return None
    return js[-1]


if __name__ == "__main__":
    from data_loader import load_price_csv
    from contexto_btc import calcular_situacion, calcular_valoracion, calcular_ciclo
    from rango import calcular_rango_esperado
    from regimen import informe as informe_regimen
    from calendario import eventos_proximos
    from halving import texto_aviso as texto_halving

    df = load_price_csv("btc_long.csv")
    s, v, c = calcular_situacion(df), calcular_valoracion(df), calcular_ciclo(df)
    rg = calcular_rango_esperado(df)
    aud = informe_regimen(df)

    corr = None
    if os.path.exists("macro.csv"):
        from correlacion import cargar_macro, calcular_correlacion
        corr = calcular_correlacion(df, cargar_macro("macro.csv"))

    ctx = construir_contexto(s, v, c, rg, aud["avisos"], corr,
                             texto_halving(), eventos_proximos(dias=45))
    print(ctx)
    print("\nLlamando a la API...")
    j = llamar_api(ctx)
    print("\n" + j)
    guardar_juicio(j, ctx)
