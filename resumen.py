"""
RESUMEN EN UNA FRASE — "¿qué quiere decirnos este sistema, ahora mismo?"

QUÉ ES Y QUÉ NO ES
-------------------
Es una síntesis, no un análisis nuevo. No calcula nada que el resto del
panel no calcule ya — toma los resultados que ya existen (situación,
valoración, rango esperado, correlación, avisos de régimen) y los
convierte en una frase legible sin abrir ningún bloque.

Por eso NO usa la API: sería el mismo error que se evitó en el resto del
sistema — meter algo no determinista justo en el sitio que más se lee,
la frase que resume todo. Esta frase sale de una plantilla con reglas
fijas sobre números ya calculados. Mismo input, misma frase, siempre.

QUÉ NO HACE
-----------
No dice si comprar, mantener o vender. Igual que el resto del sistema no
lo dice, este resumen tampoco puede inventarlo solo por resumir. Si dijera
"parece buen momento para entrar", estaría añadiendo una opinión que
ningún otro bloque del panel sostiene — y el filtro.py existe precisamente
para no colar afirmaciones sin medir.

ESTRUCTURA DE LA FRASE
------------------------
Tres piezas, siempre en el mismo orden, para que la persona aprenda a
leerla de un vistazo con el tiempo:

  1. Dónde está el precio (caro/normal/barato, según su propia historia)
  2. Cuánto se mueve ahora (volatilidad alta/normal/baja)
  3. El aviso más urgente activo, si lo hay (régimen roto, evento cerca,
     ventana de halving) — porque eso es lo que cambia la lectura de
     las dos primeras piezas
"""


def _describir_valoracion(percentil: float) -> str:
    if percentil >= 80:
        return "está caro según su propia historia"
    elif percentil >= 60:
        return "está algo por encima de su media histórica"
    elif percentil >= 40:
        return "está en su rango normal de valoración"
    elif percentil >= 20:
        return "está algo por debajo de su media histórica"
    else:
        return "está barato según su propia historia"


def _describir_volatilidad(cuartil: str) -> str:
    return {
        "muy baja": "se mueve muy poco últimamente",
        "baja": "se mueve menos de lo habitual",
        "alta": "se mueve más de lo habitual",
        "muy alta": "se está moviendo mucho",
    }.get(cuartil, "tiene una volatilidad difícil de clasificar ahora mismo")


def _aviso_mas_urgente(avisos_regimen: list, texto_calendario: str,
                       texto_halving: str) -> str | None:
    """
    Un único aviso, el más relevante de los que estén activos. Orden de
    prioridad: régimen roto > halving > calendario — porque un régimen
    roto significa que los propios cálculos del panel pueden no ser
    fiables ahora mismo, que es más urgente que un evento programado.
    """
    altos = [a["texto"] for a in avisos_regimen if a.get("nivel") == "alto"]
    if altos:
        return ("la calibración del panel puede no ser fiable ahora mismo "
                "(ver el aviso en el bloque 06)")
    if texto_halving:
        return "estás en una ventana histórica ligada al ciclo de halving"
    if texto_calendario:
        return "hay un evento macro importante en los próximos días"
    return None


def generar_resumen(situacion: dict, valoracion: dict, rango: dict,
                    avisos_regimen: list, correlacion: dict = None,
                    texto_calendario: str = "", texto_halving: str = "") -> str:
    """
    Construye la frase de síntesis a partir de resultados ya calculados
    por el resto del panel. No vuelve a calcular nada.
    """
    precio = situacion.get("precio")
    desc_valor = _describir_valoracion(valoracion.get("percentil", 50))
    desc_vol = _describir_volatilidad(rango.get("cuartil", ""))

    frase = f"Ahora mismo, BTC {desc_valor} y {desc_vol}"

    if correlacion and correlacion.get("disponible"):
        if correlacion.get("tramo") == "alta":
            frase += ", y apenas diversifica frente a la bolsa tradicional"

    urgente = _aviso_mas_urgente(avisos_regimen, texto_calendario, texto_halving)
    if urgente:
        frase += f" — y {urgente}"

    frase += "."

    return frase


def generar_subtexto() -> str:
    """
    La aclaración que siempre acompaña al resumen, para que nunca se lea
    la frase de arriba como una recomendación. Es fija a propósito: la
    persona debe poder confiar en que dice siempre lo mismo.
    """
    return (
        "Esto describe la situación, no dice qué hacer. El sistema no "
        "predice si el precio subirá o bajará — eso se comprobó y no se "
        "puede saber con los datos disponibles. Solo ayuda a entender "
        "cuánto puede moverse y cuánto tiene sentido arriesgar."
    )


if __name__ == "__main__":
    import sys
    from data_loader import load_price_csv
    from contexto_btc import calcular_situacion, calcular_valoracion
    from rango import calcular_rango_esperado
    from regimen import informe as informe_regimen

    df = load_price_csv(sys.argv[1] if len(sys.argv) > 1 else "btc_long.csv")
    s = calcular_situacion(df)
    v = calcular_valoracion(df)
    rg = calcular_rango_esperado(df)
    aud = informe_regimen(df)

    print(generar_resumen(s, v, rg, aud["avisos"]))
    print()
    print(generar_subtexto())
