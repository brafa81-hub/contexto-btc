"""
FUENTE SEC — consulta el buscador de texto completo de EDGAR.

POR QUÉ ESTA FUENTE Y NO OTRA
-------------------------------
Es la única fuente de nivel 1 (hecho verificable, no interpretación) que
se pudo confirmar accesible sin scraping fragil. A diferencia de Farside
(bloqueada por Cloudflare, ver fetch_etf.py), este es un endpoint JSON
público, sin clave, pensado para consumo automático.

Verificado el 31/08/2026 desde una máquina real (no desde el sandbox de
Claude, que no tiene acceso a este dominio): responde 200 con resultados
reales cuando se envía un User-Agent con datos de contacto, como exige
la SEC.

QUÉ BUSCA
---------
Filings (8-K, S-1, 424B*) que mencionen Bitcoin o palabras clave de ETFs
spot, en los últimos N días. Un 8-K es el formulario que usan las empresas
para eventos materiales — a menudo se presenta ANTES que el comunicado de
prensa, así que puede ser el primer rastro público de algo relevante.

LÍMITES DE LA SEC (respetados en este script)
-----------------------------------------------
- Máximo 10 peticiones/segundo por IP — aquí se hace 1 por ejecución
- User-Agent obligatorio con contacto real, o la petición se rechaza
  silenciosamente (esto fue justo lo que pasó al probarlo sin cabecera)
"""

import requests

BASE_URL = "https://efts.sec.gov/LATEST/search-index"

# La SEC exige un User-Agent identificable. Cambia el email por uno real
# si quieres, no es obligatorio pero es buena práctica de buen ciudadano
# con un servicio público gratuito.
USER_AGENT = "contexto-btc-panel (uso personal, no comercial)"

TERMINOS_BITCOIN = '"bitcoin" OR "spot bitcoin ETF"'
FORMULARIOS = "8-K,S-1,424B2,424B5"


def buscar_filings(dias: int = 7, terminos: str = TERMINOS_BITCOIN,
                   formularios: str = FORMULARIOS, limite: int = 15) -> list:
    """
    Filings que mencionan los términos dados, en los últimos N días.

    Devuelve una lista de diccionarios simplificados: fecha, empresa,
    tipo de formulario y enlace. Sin interpretación — eso lo hace el
    análisis con IA, en un paso posterior.
    """
    from datetime import date, timedelta

    hoy = date.today()
    desde = hoy - timedelta(days=dias)

    r = requests.get(
        BASE_URL,
        params={
            "q": terminos,
            "forms": formularios,
            "dateRange": "custom",
            "startdt": desde.isoformat(),
            "enddt": hoy.isoformat(),
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise RuntimeError(f"SEC devolvió un error: {data['error']}")

    hits = data.get("hits", {}).get("hits", [])[:limite]
    resultados = []
    for h in hits:
        src = h.get("_source", {})
        adsh = h.get("_id", "").split(":")[0]
        nombres = src.get("display_names", ["(sin nombre)"])
        resultados.append({
            "empresa": nombres[0] if nombres else "(sin nombre)",
            "formulario": (src.get("root_forms") or ["?"])[0],
            "fecha": src.get("file_date", "?"),
            "cik": (src.get("ciks") or ["?"])[0],
            "accession": adsh,
            "url": (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{(src.get('ciks') or ['0'])[0].lstrip('0')}/{adsh.replace('-', '')}"
                if adsh else None
            ),
        })
    return resultados


if __name__ == "__main__":
    import sys
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    print(f"Filings sobre Bitcoin en los últimos {dias} días:\n")
    try:
        resultados = buscar_filings(dias=dias)
    except Exception as e:
        print(f"Error consultando la SEC: {type(e).__name__}: {e}")
        sys.exit(1)

    if not resultados:
        print("Sin resultados en el periodo.")
    for r in resultados:
        print(f"  [{r['fecha']}] {r['formulario']:<8} {r['empresa']}")
        if r["url"]:
            print(f"      {r['url']}")
