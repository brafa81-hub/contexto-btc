"""
CALENDARIO DE EVENTOS — qué hay en la agenda que pueda mover el mercado.

POR QUÉ ESTE BLOQUE EXISTE Y LOS DEMÁS CANDIDATOS NO
-----------------------------------------------------
De todo lo que se evaluó para el panel, este es el único que no necesita
demostrar poder predictivo, porque no predice nada. Solo dice qué está
programado y cuándo.

Se midieron y descartaron: VIX, dólar, bono 10 años, tipo Fed, funding rate
e índice de Miedo y Codicia. Ninguno anticipaba el precio de BTC. Un
calendario no tiene ese problema: o hay reunión de la Fed el miércoles o no
la hay. No hay correlación que se rompa ni régimen que cambie.

QUÉ APORTA EN LA PRÁCTICA
--------------------------
BTC correlaciona 0,33 con el Nasdaq (ver correlacion.py). Los eventos que
mueven la renta variable estadounidense mueven a BTC con ella. Saber que
pasado mañana hay dato de inflación no dice hacia dónde irá el precio —
dice que ese día habrá más movimiento del habitual, y que decidir la
víspera sin saberlo es evitable.

LO QUE ESTE BLOQUE NO HACE
---------------------------
No estima la dirección ni la magnitud del impacto. Eso requeriría afirmar
que se sabe cómo va a reaccionar el mercado, y todo el análisis de este
proyecto apunta a que no se sabe.

FUENTES Y VERIFICACIÓN (29/08/2026)
------------------------------------
Fechas FOMC: calendario oficial de la Reserva Federal. Contrastadas con
federalreserve.gov/monetarypolicy/fomccalendars.htm. Las de 2027 son la
programación tentativa publicada por la Fed; cada fecha es provisional
hasta que se confirma en la reunión anterior.

Fechas CPI: calendario del Bureau of Labor Statistics. Las de 2026 son
oficiales. El BLS publica el calendario de 2027 en la segunda mitad de
2026, así que aquí solo se incluyen las confirmadas.

NOTA SOBRE EL MANTENIMIENTO
---------------------------
Las fechas están escritas en el código a propósito, no descargadas en
tiempo real: son ocho reuniones al año y doce datos, publicados con más de
un año de antelación. Descargarlas añadiría una dependencia de red que
puede fallar en silencio a cambio de casi nada.

El precio de esa decisión es que hay que actualizarlas. El módulo avisa
solo cuando se está quedando sin fechas futuras, para que el olvido no pase
desapercibido.
"""

from datetime import date, datetime

import pandas as pd

# Reuniones del FOMC. La fecha es la del ANUNCIO (segundo día), que es
# cuando se publica la decisión a las 14:00 ET.
# sep=True indica que además se publican las proyecciones (dot plot),
# reuniones que históricamente generan más movimiento.
FOMC = [
    ("2026-09-16", True), ("2026-10-28", False), ("2026-12-09", True),
    ("2027-01-27", False), ("2027-03-17", True), ("2027-04-28", False),
    ("2027-06-09", True), ("2027-07-28", False), ("2027-09-15", True),
    ("2027-10-27", False), ("2027-12-08", True),
]

# Publicaciones del CPI (dato de inflación), 8:30 ET.
# Solo las confirmadas oficialmente por el BLS.
CPI = [
    "2026-09-11", "2026-10-13", "2026-11-10", "2026-12-10",
]

# Umbral por debajo del cual el módulo avisa de que faltan fechas nuevas.
MESES_MINIMOS = 3


def _proximos(fechas, hoy: date, limite: int):
    """Filtra a futuro y devuelve los N más cercanos."""
    fut = [f for f in fechas if f["fecha"] >= hoy]
    return sorted(fut, key=lambda x: x["fecha"])[:limite]


def eventos_proximos(hoy: date = None, dias: int = 90, limite: int = 6) -> list:
    """
    Eventos programados en los próximos N días, ordenados por cercanía.

    Devuelve una lista de diccionarios con fecha, tipo, nombre y días
    restantes. Sin interpretación ni previsión: solo la agenda.
    """
    hoy = hoy or date.today()
    tope = hoy + pd.Timedelta(days=dias).to_pytimedelta()

    eventos = []
    for f, sep in FOMC:
        d = datetime.strptime(f, "%Y-%m-%d").date()
        eventos.append({
            "fecha": d,
            "tipo": "FOMC",
            "nombre": "Decisión de tipos de la Fed" + (" + proyecciones" if sep else ""),
            "relevancia": "alta" if sep else "media",
        })
    for f in CPI:
        d = datetime.strptime(f, "%Y-%m-%d").date()
        eventos.append({
            "fecha": d,
            "tipo": "CPI",
            "nombre": "Dato de inflación de EEUU",
            "relevancia": "alta",
        })

    prox = [e for e in _proximos(eventos, hoy, limite) if e["fecha"] <= tope]
    for e in prox:
        e["dias"] = (e["fecha"] - hoy).days
    return prox


def estado_calendario(hoy: date = None) -> dict:
    """
    Comprueba si quedan fechas futuras suficientes.

    Un calendario caducado no da error: simplemente deja de mostrar eventos,
    que es la forma más silenciosa de fallar. Esto lo hace visible.
    """
    hoy = hoy or date.today()
    todas = [datetime.strptime(f, "%Y-%m-%d").date() for f, _ in FOMC]
    todas += [datetime.strptime(f, "%Y-%m-%d").date() for f in CPI]
    futuras = [d for d in todas if d >= hoy]

    if not futuras:
        return {"ok": False, "mensaje": "El calendario no tiene ninguna fecha futura. "
                                        "Hay que actualizar calendario.py."}

    ultima = max(futuras)
    meses = (ultima - hoy).days / 30.4
    if meses < MESES_MINIMOS:
        return {"ok": False, "mensaje": f"El calendario solo llega hasta "
                                        f"{ultima:%d/%m/%Y}. Conviene actualizar "
                                        f"las fechas en calendario.py."}
    return {"ok": True, "hasta": ultima, "meses": meses}


def texto_proximo(hoy: date = None) -> str:
    """Una línea con el evento más cercano, para mostrar arriba del todo."""
    prox = eventos_proximos(hoy, dias=365, limite=1)
    if not prox:
        return ""
    e = prox[0]
    if e["dias"] == 0:
        cuando = "hoy"
    elif e["dias"] == 1:
        cuando = "mañana"
    else:
        cuando = f"en {e['dias']} días"
    return f"Próximo evento: **{e['nombre']}** {cuando} ({e['fecha']:%d/%m/%Y})."


if __name__ == "__main__":
    est = estado_calendario()
    if not est["ok"]:
        print("AVISO:", est["mensaje"], "\n")
    print("┌─ CALENDARIO (próximos 90 días) " + "─" * 34)
    ev = eventos_proximos()
    if not ev:
        print("│  Sin eventos programados en los próximos 90 días.")
    for e in ev:
        marca = "!" if e["relevancia"] == "alta" else " "
        print(f"│ {marca} {e['fecha']:%d/%m/%Y}  (en {e['dias']:>3} días)  {e['nombre']}")
    print("│")
    print("│  Esto no predice nada. Solo dice qué está en la agenda.")
    print("└" + "─" * 66)
