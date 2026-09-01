"""
LECTURA DEL DIGEST — presenta en el panel lo que genera digest_semanal.py.

PRINCIPIO DE DISEÑO
-------------------
El digest completo son varios miles de caracteres: cinco filings analizados
en cuatro puntos cada uno, más el grupo de rutinarios. Nadie va a leer eso
cada domingo, y pedirlo sería repetir el error de diseñar para un lector
que no existe.

Por eso este módulo separa dos cosas:

  - La sección "QUÉ HACER ESTA SEMANA": tres líneas en lenguaje llano.
    Se muestra siempre, destacada. Es lo único que hay que leer.
  - El resto del análisis: se puede desplegar si se quiere, pero está
    plegado por defecto.

Si el digest no trae esa sección (porque el modelo se saltó el formato o
la respuesta se cortó), se muestra el texto completo en vez de fallar en
silencio — mejor un bloque feo que un bloque vacío sin explicación.

FRESCURA
--------
El workflow corre los domingos. Si el archivo tiene más de 10 días, algo
ha fallado en el pipeline (workflow desactivado, error recurrente, límite
de API). El panel lo dice en vez de mostrar información vieja como si
fuera actual — el mismo criterio que en calendario.py con las fechas
caducadas.
"""

import json
import os
import re
from datetime import datetime, timezone

DIAS_PARA_CONSIDERAR_VIEJO = 10

# El modelo cierra con este encabezado (ver PROMPT_SISTEMA en
# digest_semanal.py). Se aceptan variantes de formato markdown por si
# cambia el nivel de encabezado o el uso de negritas.
PATRON_CIERRE = re.compile(
    r"#{1,4}\s*\**\s*QU[ÉE]\s+HACER\s+ESTA\s+SEMANA\s*\**\s*\n(.*)",
    re.IGNORECASE | re.DOTALL,
)


def cargar_digest(path: str = "noticias.json") -> dict | None:
    """Último digest generado, o None si no hay ninguno todavía."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            digests = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not digests:
        return None

    ultimo = digests[-1]
    if not ultimo.get("analisis", "").strip():
        return None

    return ultimo


def separar_secciones(analisis: str) -> tuple:
    """
    Devuelve (resumen_accionable, analisis_completo).

    Si no encuentra la sección de cierre, devuelve (None, texto completo)
    para que el panel muestre algo útil igualmente.
    """
    m = PATRON_CIERRE.search(analisis)
    if not m:
        return None, analisis

    resumen = m.group(1).strip()
    cuerpo = analisis[: m.start()].strip()
    return resumen, cuerpo


def antiguedad_dias(digest: dict) -> float | None:
    """Días transcurridos desde que se generó el digest."""
    try:
        gen = datetime.fromisoformat(digest["generado"])
        if gen.tzinfo is None:
            gen = gen.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - gen).total_seconds() / 86400
    except (KeyError, ValueError):
        return None


def estado(digest: dict) -> dict:
    """Resumen del estado del digest para el panel."""
    dias = antiguedad_dias(digest)
    return {
        "dias": dias,
        "viejo": dias is not None and dias > DIAS_PARA_CONSIDERAR_VIEJO,
        "n_prioritarios": digest.get("n_prioritarios", 0),
        "n_rutinarios": digest.get("n_rutinarios", 0),
        "fecha": digest.get("generado", "")[:10],
    }


if __name__ == "__main__":
    d = cargar_digest()
    if not d:
        print("Sin digest disponible todavía.")
    else:
        est = estado(d)
        resumen, cuerpo = separar_secciones(d["analisis"])
        print(f"Digest del {est['fecha']} "
              f"({est['n_prioritarios']} prioritarios, "
              f"{est['n_rutinarios']} rutinarios)")
        if est["viejo"]:
            print(f"AVISO: tiene {est['dias']:.0f} días — el pipeline puede estar fallando.")
        print("\n--- QUÉ HACER ESTA SEMANA ---")
        print(resumen or "(el digest no trae sección de cierre)")
