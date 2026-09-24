"""
Exportación del panel (bloques 01-08) a JSON y PDF.

Aprobado 2026-09-23. Solo empaqueta valores que app.py ya ha calculado:
no hay lógica de cálculo nueva, ni reglas, ni indicadores. Excluye a
propósito el tablero de decisión, el diario (09) y el digest semanal (10).
"""

import io
import json
import math
import re
from datetime import date, datetime

import numpy as np
import pandas as pd

AVISO_GENERAL = (
    "Contexto descriptivo del mercado. No predice la dirección del precio, no "
    "recomienda comprar ni vender y no es asesoramiento financiero. De estos "
    "bloques, solo el 06 (rango esperado a 30 días) se apoya en una relación "
    "validada por épocas; el resto es descriptivo."
)


# ---------------------------------------------------------------
# Limpieza de tipos para JSON
# ---------------------------------------------------------------
def limpiar(obj):
    """Convierte tipos numpy/pandas a tipos JSON; NaN -> None."""
    if isinstance(obj, dict):
        return {str(k): limpiar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [limpiar(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else f
    if obj is pd.NaT:
        return None
    return obj


def construir_json(datos):
    """Bytes UTF-8 del JSON con los datos en bruto de los bloques 01-08."""
    return json.dumps(limpiar(datos), ensure_ascii=False, indent=2).encode("utf-8")


# ---------------------------------------------------------------
# PDF
# ---------------------------------------------------------------
_SUSTITUCIONES = {"−": "-", "–": "-", "—": "-", "≈": "~", "⚠": "", "×": "x"}


def _txt(s):
    """Texto seguro para las fuentes base de ReportLab (cp1252) + negritas."""
    s = str(s)
    for a, b in _SUSTITUCIONES.items():
        s = s.replace(a, b)
    s = s.encode("cp1252", errors="ignore").decode("cp1252")
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s).replace("*", "")


def construir_pdf(datos):
    """Bytes del PDF legible con los bloques 01-08 (usa las 'filas' y 'tablas')."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Contexto BTC - bloques 01-08", author="Contexto-BTC",
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4)
    cuerpo = ParagraphStyle("c", parent=ss["BodyText"], fontSize=9.5, leading=12.5)
    nota = ParagraphStyle("n", parent=cuerpo, fontSize=8.3, leading=10.5,
                          textColor=colors.HexColor("#555048"))
    celda = ParagraphStyle("t", parent=cuerpo, fontSize=8.8, leading=11)

    def tabla(filas, cabecera=None):
        data = ([cabecera] if cabecera else []) + filas
        data = [[Paragraph(_txt(x), celda) for x in fila] for fila in data]
        ancho = doc.width / max(len(data[0]), 1)
        t = Table(data, colWidths=[ancho] * len(data[0]), hAlign="LEFT")
        estilo = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9b3a4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if cabecera:
            estilo.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e4d9")))
        t.setStyle(TableStyle(estilo))
        return t

    m = limpiar(datos["meta"])
    el = [
        Paragraph(_txt("¿Dónde está Bitcoin? · Bloques 01-08"), h1),
        Paragraph(_txt(f"Datos a {m['fecha_datos']} · Precio ${m['precio']:,.0f} · "
                       f"Generado {m['generado']}"), cuerpo),
        Paragraph(_txt(f"Capital indicado: {m['capital_eur']:,.0f} € · "
                       f"Pérdida tolerable indicada: {m['perdida_tolerable_eur']:,.0f} €"), cuerpo),
        Spacer(1, 4),
        Paragraph(_txt(AVISO_GENERAL), nota),
    ]
    for clave, b in datos["bloques"].items():
        el.append(Paragraph(_txt(f"{clave} · {b['titulo']}"), h2))
        for fila in b.get("filas", []):
            el.append(Paragraph(_txt(fila), cuerpo))
        for t in b.get("tablas", []):
            if t.get("titulo"):
                el.append(Spacer(1, 3))
                el.append(Paragraph(_txt(f"**{t['titulo']}**"), cuerpo))
            el.append(Spacer(1, 2))
            el.append(tabla(t["filas"], t.get("cabecera")))
        for n in b.get("notas", []):
            el.append(Spacer(1, 2))
            el.append(Paragraph(_txt(n), nota))

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6a6558"))
        canvas.drawString(18 * mm, 9 * mm, "Contexto-BTC · no es una recomendación · "
                          "Precio: Bitstamp · On-chain: BGeometrics".encode("cp1252").decode("cp1252"))
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"pág. {doc_.page}")
        canvas.restoreState()

    doc.build(el, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


def quitar_presentacion(datos):
    """Copia para el JSON: quita 'filas'/'tablas' (texto de presentación del PDF)."""
    out = {"aviso": AVISO_GENERAL, "meta": datos["meta"], "bloques": {}}
    for k, b in datos["bloques"].items():
        out["bloques"][k] = {x: v for x, v in b.items() if x not in ("filas", "tablas")}
    return out
