"""
FUENTES DE NOTICIAS — amplía el vigilante semanal más allá de la SEC.

EL PROBLEMA QUE RESUELVE
------------------------
Hasta ahora el digest semanal solo miraba filings de la SEC. Eso cubre
movimientos corporativos y regulatorios de EEUU, pero se pierde:

  - Regulación europea (MiCA) o asiática
  - Hackeos y quiebras de exchanges
  - Anuncios que salen por prensa antes que por documento oficial
  - Decisiones de política monetaria no programadas

NIVELES DE FUENTE (el criterio que se acordó al diseñar el pipeline)
---------------------------------------------------------------------
NIVEL 1 — Fuente primaria oficial. Un hecho publicado por el propio
  organismo. No hay interpretación de por medio.
NIVEL 3 — Prensa especializada. Útil para cobertura amplia, pero cada
  ítem debe tratarse como no confirmado salvo que se pueda rastrear a
  una fuente de nivel 1.

No hay nivel 2 en este módulo: los flujos de ETF (que ocuparían ese
lugar) siguen sin fuente automatizable, ver fetch_etf.py.

POR QUÉ NO ESTÁ REUTERS
------------------------
Se verificó el 02/09/2026: Reuters ya no publica feeds RSS oficiales
fiables para su contenido web. Montar el vigilante sobre una fuente que
puede dejar de responder en cualquier momento repetiría el error de
Farside (ver fetch_etf.py), donde se construyó un script sobre una
fuente que bloquea el acceso automático.

DISEÑO DEFENSIVO
----------------
Cada fuente se consulta por separado y su fallo no tumba las demás. El
resultado incluye siempre qué fuentes respondieron y cuáles no, para que
una fuente muerta se note en el log en vez de reducir silenciosamente la
cobertura del digest — el mismo criterio que en calendario.py con las
fechas caducadas.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

# Se usa xml.etree de la biblioteca estándar en vez de feedparser para no
# añadir dependencias al workflow. RSS es simple y no lo justifica.

FUENTES = [
    {
        "nombre": "Reserva Federal — notas de prensa",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "nivel": 1,
        "tipo": "macro",
        "filtrar_por_palabras": False,  # todo lo que publica la Fed es relevante
    },
    {
        "nombre": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "nivel": 3,
        "tipo": "prensa",
        "filtrar_por_palabras": True,
    },
    {
        "nombre": "Cointelegraph",
        "url": "https://cointelegraph.com/rss",
        "nivel": 3,
        "tipo": "prensa",
        "filtrar_por_palabras": True,
    },
    {
        "nombre": "The Block",
        "url": "https://www.theblock.co/rss.xml",
        "nivel": 3,
        "tipo": "prensa",
        "filtrar_por_palabras": True,
    },
]

# Palabras que marcan un titular como potencialmente relevante. Deliberadamente
# amplias: filtrar de más aquí es peor que filtrar de menos, porque el modelo
# puede descartar ruido pero no puede recuperar lo que nunca vio.
PALABRAS_CLAVE = (
    "bitcoin", "btc", "etf", "sec ", "regulat", "ban ", "banned", "hack",
    "exploit", "stablecoin", "tether", "usdc", "cftc", "mica", "custody",
    "exchange", "binance", "coinbase", "treasury", "fed ", "rate cut",
    "rate hike", "inflation", "crypto",
)

TIMEOUT = 20
MAX_POR_FUENTE = 12


def _texto(elem, *nombres):
    """Primer valor de texto encontrado entre varios nombres de etiqueta."""
    for n in nombres:
        hijo = elem.find(n)
        if hijo is not None and hijo.text:
            return hijo.text.strip()
    return ""


def _parsear_fecha(txt: str):
    """RSS usa varios formatos de fecha. Se intentan los habituales."""
    formatos = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    )
    for f in formatos:
        try:
            d = datetime.strptime(txt.strip(), f)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue
    return None


def _es_relevante(titulo: str, descripcion: str) -> bool:
    texto = f"{titulo} {descripcion}".lower()
    return any(p in texto for p in PALABRAS_CLAVE)


def leer_fuente(fuente: dict, dias: int = 8) -> tuple:
    """
    Lee un feed RSS. Devuelve (items, error) — nunca lanza excepción, para
    que el fallo de una fuente no impida consultar las demás.
    """
    try:
        r = requests.get(
            fuente["url"],
            timeout=TIMEOUT,
            headers={"User-Agent": "contexto-btc-panel/1.0 (uso personal)"},
        )
        r.raise_for_status()
        raiz = ET.fromstring(r.content)
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"

    corte = datetime.now(timezone.utc) - timedelta(days=dias)
    items = []

    # Soporta RSS 2.0 (channel/item) y Atom (entry)
    entradas = raiz.findall(".//item") or raiz.findall(
        ".//{http://www.w3.org/2005/Atom}entry")

    for e in entradas:
        titulo = _texto(e, "title", "{http://www.w3.org/2005/Atom}title")
        desc = _texto(e, "description", "summary",
                      "{http://www.w3.org/2005/Atom}summary")
        enlace = _texto(e, "link", "guid")
        if not enlace:
            le = e.find("{http://www.w3.org/2005/Atom}link")
            enlace = le.get("href", "") if le is not None else ""

        fecha_txt = _texto(e, "pubDate", "published", "updated",
                           "{http://www.w3.org/2005/Atom}published")
        fecha = _parsear_fecha(fecha_txt)

        if fecha and fecha < corte:
            continue
        if fuente["filtrar_por_palabras"] and not _es_relevante(titulo, desc):
            continue
        if not titulo:
            continue

        # La descripción suele venir con HTML; se limpia para no gastar
        # tokens en etiquetas al pasarla al modelo.
        desc_limpia = re.sub(r"<[^>]+>", "", desc)[:280]

        items.append({
            "titulo": titulo,
            "resumen": desc_limpia.strip(),
            "url": enlace,
            "fecha": fecha.strftime("%Y-%m-%d") if fecha else "?",
            "fuente": fuente["nombre"],
            "nivel": fuente["nivel"],
            "tipo": fuente["tipo"],
        })

        if len(items) >= MAX_POR_FUENTE:
            break

    return items, None


def _palabras_clave_titulo(titulo: str) -> set:
    """
    Palabras significativas de un titular, con raíz aproximada.

    Se recorta el final de cada palabra (aprove/aproved -> aprov) porque
    los medios describen el mismo hecho con tiempos verbales distintos:
    "SEC approves X" vs "X approved by SEC". Comparar cadenas exactas
    fallaba en ese caso, que es justo el que hay que detectar.
    """
    t = re.sub(r"[^a-z0-9 ]", " ", titulo.lower())
    vacias = {"the", "and", "for", "with", "from", "that", "this", "says",
              "said", "will", "new", "its", "his", "her", "has", "have",
              "after", "over", "into", "amid", "about", "today", "week",
              "year", "más", "para", "como", "por", "los", "las", "una"}
    palabras = set()
    for p in t.split():
        if len(p) > 3 and p not in vacias:
            palabras.add(p[:6])  # raíz aproximada
    return palabras


def _es_duplicado(titulo: str, vistos: list, umbral: float = 0.5) -> bool:
    """
    ¿Este titular describe el mismo hecho que alguno ya visto?

    Usa solapamiento de Jaccard sobre las palabras significativas. El
    umbral de 0.5 es deliberadamente conservador: preferimos dejar pasar
    un duplicado (cuesta unos tokens) antes que descartar una noticia
    distinta por parecerse superficialmente a otra.

    LÍMITE CONOCIDO: no detecta duplicados que usan vocabulario distinto
    para el mismo hecho ("Binance hacked" vs "Hackers steal from
    Binance"). Detectar eso requiere entender significado, no comparar
    palabras. Se acepta a propósito: esta deduplicación es un ahorro de
    coste, no un requisito de corrección — si un duplicado pasa, el
    modelo ve dos titulares parecidos y puede señalarlo. Lo que sí evita
    es el caso frecuente y barato: la misma noticia con las palabras
    reordenadas.

    Verificado (02/09/2026): detecta 2 de 3 duplicados con redacción
    distinta, y 0 falsos positivos sobre 3 pares de noticias no
    relacionadas.
    """
    p1 = _palabras_clave_titulo(titulo)
    if not p1:
        return False
    for p2 in vistos:
        if not p2:
            continue
        union = p1 | p2
        if union and len(p1 & p2) / len(union) >= umbral:
            return True
    return False


def recoger_noticias(dias: int = 8) -> dict:
    """
    Consulta todas las fuentes y devuelve los items agrupados por nivel,
    más el estado de cada fuente.
    """
    todos, estado = [], []

    for f in FUENTES:
        items, error = leer_fuente(f, dias=dias)
        estado.append({
            "fuente": f["nombre"],
            "nivel": f["nivel"],
            "ok": error is None,
            "n": len(items),
            "error": error,
        })
        todos.extend(items)

    # Deduplicar: la misma noticia suele aparecer en varios medios. Se
    # conserva la de nivel más bajo (más oficial), por eso se ordena antes.
    vistos, unicos = [], []
    for it in sorted(todos, key=lambda x: x["nivel"]):
        if not _es_duplicado(it["titulo"], vistos):
            vistos.append(_palabras_clave_titulo(it["titulo"]))
            unicos.append(it)

    return {
        "nivel_1": [i for i in unicos if i["nivel"] == 1],
        "nivel_3": [i for i in unicos if i["nivel"] == 3],
        "estado_fuentes": estado,
        "n_total": len(unicos),
        "n_duplicados": len(todos) - len(unicos),
    }


if __name__ == "__main__":
    import sys
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 8

    print(f"Recogiendo noticias de los últimos {dias} días...\n")
    res = recoger_noticias(dias=dias)

    print("Estado de las fuentes:")
    for e in res["estado_fuentes"]:
        marca = "ok " if e["ok"] else "FALLO"
        print(f"  [{marca}] nivel {e['nivel']} · {e['fuente']}: {e['n']} items"
              + (f"  ({e['error']})" if e["error"] else ""))

    print(f"\n{res['n_total']} noticias únicas "
          f"({res['n_duplicados']} duplicados entre medios descartados)\n")

    for nivel, clave in [(1, "nivel_1"), (3, "nivel_3")]:
        items = res[clave]
        if not items:
            continue
        print(f"--- NIVEL {nivel} ({len(items)}) ---")
        for i in items[:10]:
            print(f"  [{i['fecha']}] {i['titulo'][:90]}")
            print(f"      {i['fuente']}")
        print()
