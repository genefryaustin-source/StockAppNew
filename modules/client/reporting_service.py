from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from datetime import datetime

import matplotlib.pyplot as plt
import os


def _build_nav_chart(nav_series, path):
    plt.figure()
    nav_series.plot(title="Portfolio NAV")
    plt.xlabel("Date")
    plt.ylabel("Value")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _build_drawdown_chart(nav_series, path):
    import numpy as np

    running_max = nav_series.cummax()
    drawdown = (nav_series - running_max) / running_max

    plt.figure()
    drawdown.plot(title="Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def generate_client_report(
    file_path,
    portfolio_id,
    nav_series,
    summary,
    performance,
    risk,
    factor,
    branding=None,
):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(file_path, pagesize=letter)

    elements = []

    # ---------------------------------
    # 🎨 BRANDING
    # ---------------------------------
    firm_name = branding.get("firm_name", "Portfolio Report") if branding else "Portfolio Report"
    logo_path = branding.get("logo_path") if branding else None

    if logo_path and os.path.exists(logo_path):
        elements.append(Image(logo_path, width=2*inch, height=1*inch))

    elements.append(Paragraph(firm_name, styles["Title"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"Portfolio ID: {portfolio_id}", styles["Normal"]))
    elements.append(Paragraph(f"Generated: {datetime.now()}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 📊 SUMMARY
    # ---------------------------------
    elements.append(Paragraph("Portfolio Summary", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    summary_table = Table(summary)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 📈 NAV CHART
    # ---------------------------------
    nav_chart_path = file_path.replace(".pdf", "_nav.png")
    _build_nav_chart(nav_series, nav_chart_path)

    elements.append(Paragraph("Portfolio NAV", styles["Heading2"]))
    elements.append(Spacer(1, 10))
    elements.append(Image(nav_chart_path, width=6*inch, height=3*inch))
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 📉 DRAWDOWN CHART
    # ---------------------------------
    dd_chart_path = file_path.replace(".pdf", "_dd.png")
    _build_drawdown_chart(nav_series, dd_chart_path)

    elements.append(Paragraph("Drawdown", styles["Heading2"]))
    elements.append(Spacer(1, 10))
    elements.append(Image(dd_chart_path, width=6*inch, height=3*inch))
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 📊 PERFORMANCE
    # ---------------------------------
    elements.append(Paragraph("Performance", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    perf_table = Table(performance)
    perf_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(perf_table)
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 📊 RISK
    # ---------------------------------
    elements.append(Paragraph("Risk Metrics", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    risk_table = Table(risk)
    risk_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(risk_table)
    elements.append(Spacer(1, 20))

    # ---------------------------------
    # 🧠 FACTOR
    # ---------------------------------
    elements.append(Paragraph("Factor Attribution", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    factor_table = Table(factor)
    factor_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(factor_table)

    # ---------------------------------
    # BUILD
    # ---------------------------------
    doc.build(elements)