import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet

def create_report(df, kpis: dict, acciones_texto: str, logo_path: str = None) -> bytes:
    """
    Genera un PDF simple con KPIs, acciones y un preview de tabla.
    - df: DataFrame con los datos ya limpios
    - kpis: diccionario de KPIs
    - acciones_texto: texto (IA o manual) a incluir
    - logo_path: ruta a un PNG/JPG opcional
    Devuelve: bytes del PDF listo para descargar
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=48, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    elements = []

    # --- Logo opcional (SOLO si la ruta existe) ---
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=140, height=40))
            elements.append(Spacer(1, 10))
        except Exception:
            # si falla el logo, continuamos sin él
            pass

    # --- Título ---
    elements.append(Paragraph("Reporte de ventas", styles["Title"]))
    elements.append(Spacer(1, 12))

    # --- KPIs (mostramos algunos si existen) ---
    elements.append(Paragraph("KPIs", styles["Heading2"]))
    kpi_lines = []
    pretty = {
        "ventas_totales": "Ventas totales",
        "ticket_promedio": "Ticket promedio",
        "n_transacciones": "Nº transacciones",
        "ventas_mes_actual": "Ventas mes actual",
        "variacion_mom_pct": "Variación MoM (%)",
        "clientes_unicos": "Clientes únicos",
        "productos_unicos": "Productos únicos",
    }
    for key, label in pretty.items():
        if key in kpis:
            val = kpis.get(key)
            kpi_lines.append(f"• {label}: {val:,}" if isinstance(val, int)
                             else f"• {label}: {val:,.2f}" if isinstance(val, float)
                             else f"• {label}: {val}")

    if not kpi_lines:
        kpi_lines = ["• (No se encontraron KPIs para mostrar)"]

    for line in kpi_lines:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 12))

    # --- Acciones ---
    elements.append(Paragraph("Acciones sugeridas", styles["Heading2"]))
    for linea in acciones_texto.splitlines():
        if linea.strip():
            elements.append(Paragraph(linea.strip().lstrip("•- "), styles["Normal"]))
    elements.append(Spacer(1, 12))

    # --- Preview de datos (tabla simple) ---
    '''elements.append(Paragraph("Vista previa de datos (primeras 10 filas)", styles["Heading2"]))
    try:
        head = [str(c) for c in df.columns.tolist()]
        body = df.head(10).astype(str).values.tolist()
        data = [head] + body
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EFF6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ]))
        elements.append(tbl)
    except Exception:
        elements.append(Paragraph("(No fue posible renderizar la tabla de preview)", styles["Italic"]))'''

    # --- Construcción ---
    doc.build(elements)
    pdf = buf.getvalue()
    buf.close()
    return pdf
