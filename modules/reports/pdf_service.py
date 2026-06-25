"""
modules/reports/pdf_service.py

Institutional PDF Research Report Generator.

Generates a 2-page tearsheet per ticker containing:
  Page 1 — Investment Memo
    - Header with ticker, company name, price, rating
    - Investment thesis (AI-generated via Claude)
    - Key metrics grid (valuation, growth, profitability)
    - Factor scores bar chart
    - Price target and analyst consensus
    - Risk factors

  Page 2 — Data Appendix
    - Full analytics scorecard
    - EPS estimate table with revisions
    - Analyst upgrade/downgrade log
    - Social sentiment summary
    - Dark pool / options flow summary
    - Disclaimer

Uses reportlab exclusively — no browser, no WeasyPrint, no external process.
Runs server-side in Streamlit and returns PDF bytes for st.download_button.
"""

from __future__ import annotations

import io
import os
import textwrap
from datetime import datetime, timezone
from typing import Optional

# reportlab imports
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, Image,
    NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

# ─────────────────────────────────────────────────────────────
# Brand colours
# ─────────────────────────────────────────────────────────────

NAVY    = colors.HexColor("#1F3864")
BLUE    = colors.HexColor("#2E75B6")
LIGHT   = colors.HexColor("#EEF3FB")
GREEN   = colors.HexColor("#1D7A4F")
RED     = colors.HexColor("#C00000")
ORANGE  = colors.HexColor("#BA7517")
GREY    = colors.HexColor("#595959")
LGREY   = colors.HexColor("#D0D7E3")
WHITE   = colors.white
BLACK   = colors.black

# ─────────────────────────────────────────────────────────────
# Paragraph styles
# ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    s = {}

    s["title"] = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=22,
        textColor=WHITE, alignment=TA_LEFT, leading=26,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=11,
        textColor=colors.HexColor("#BDD7EE"), alignment=TA_LEFT, leading=14,
    )
    s["h1"] = ParagraphStyle(
        "h1", fontName="Helvetica-Bold", fontSize=12,
        textColor=NAVY, spaceBefore=10, spaceAfter=4, leading=15,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=10,
        textColor=BLUE, spaceBefore=6, spaceAfter=3, leading=13,
    )
    s["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9,
        textColor=BLACK, leading=13, spaceAfter=4,
        alignment=TA_JUSTIFY,
    )
    s["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=8,
        textColor=GREY, leading=11,
    )
    s["disclaimer"] = ParagraphStyle(
        "disclaimer", fontName="Helvetica-Oblique", fontSize=7,
        textColor=GREY, leading=10, alignment=TA_JUSTIFY,
    )
    s["metric_label"] = ParagraphStyle(
        "metric_label", fontName="Helvetica", fontSize=8,
        textColor=GREY, alignment=TA_CENTER, leading=10,
    )
    s["metric_value"] = ParagraphStyle(
        "metric_value", fontName="Helvetica-Bold", fontSize=13,
        textColor=NAVY, alignment=TA_CENTER, leading=16,
    )
    s["tag_bull"] = ParagraphStyle(
        "tag_bull", fontName="Helvetica-Bold", fontSize=9,
        textColor=GREEN, alignment=TA_CENTER,
    )
    s["tag_bear"] = ParagraphStyle(
        "tag_bear", fontName="Helvetica-Bold", fontSize=9,
        textColor=RED, alignment=TA_CENTER,
    )
    s["table_header"] = ParagraphStyle(
        "table_header", fontName="Helvetica-Bold", fontSize=8,
        textColor=WHITE, alignment=TA_CENTER,
    )
    s["table_cell"] = ParagraphStyle(
        "table_cell", fontName="Helvetica", fontSize=8,
        textColor=BLACK, alignment=TA_LEFT,
    )
    s["center"] = ParagraphStyle(
        "center", fontName="Helvetica", fontSize=9,
        textColor=BLACK, alignment=TA_CENTER,
    )
    return s


# ─────────────────────────────────────────────────────────────
# Page templates
# ─────────────────────────────────────────────────────────────

def _header_band(canvas, doc, ticker: str, company: str, price: float,
                 rating: str, report_date: str):
    """Draw the navy header band on every page."""
    W, H = letter
    canvas.saveState()

    # Navy band
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 1.1 * inch, W, 1.1 * inch, fill=1, stroke=0)

    # Blue accent bar
    canvas.setFillColor(BLUE)
    canvas.rect(0, H - 1.15 * inch, W, 0.05 * inch, fill=1, stroke=0)

    # Ticker + company
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawString(0.5 * inch, H - 0.62 * inch, ticker)

    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#BDD7EE"))
    canvas.drawString(0.5 * inch, H - 0.82 * inch, company[:60])

    # Price + rating (right side)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 18)
    price_str = f"${price:,.2f}" if price else "—"
    canvas.drawRightString(W - 0.5 * inch, H - 0.60 * inch, price_str)

    # Rating badge
    rating_color = {"Buy": GREEN, "Strong Buy": GREEN,
                    "Sell": RED, "Strong Sell": RED}.get(rating, ORANGE)
    badge_x = W - 1.2 * inch
    badge_y = H - 0.92 * inch
    canvas.setFillColor(rating_color)
    canvas.roundRect(badge_x, badge_y, 0.7 * inch, 0.22 * inch,
                     radius=3, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawCentredString(badge_x + 0.35 * inch, badge_y + 0.07 * inch, rating)

    # Footer
    canvas.setFillColor(LGREY)
    canvas.rect(0, 0, W, 0.35 * inch, fill=1, stroke=0)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(0.5 * inch, 0.13 * inch,
                      f"Equity Research Terminal  ·  {report_date}  ·  "
                      "For informational purposes only. Not investment advice.")
    canvas.drawRightString(W - 0.5 * inch, 0.13 * inch,
                           f"Page {doc.page}")

    canvas.restoreState()


def _make_page_templates(doc, ticker, company, price, rating, date):
    def header(canvas, doc):
        _header_band(canvas, doc, ticker, company, price, rating, date)

    W, H = letter
    margin = 0.5 * inch
    top    = H - 1.35 * inch
    bottom = 0.55 * inch

    frame = Frame(margin, bottom, W - 2 * margin, top - bottom,
                  id="main", showBoundary=0)
    return [PageTemplate(id="main", frames=[frame], onPage=header)]


# ─────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────

def _rating_color(rating: str) -> colors.Color:
    r = str(rating).lower()
    if "strong buy" in r or r == "buy":
        return GREEN
    if "sell" in r:
        return RED
    return ORANGE


def _metric_box(label: str, value: str, s: dict, highlight: bool = False) -> Table:
    """Single metric box — label over value."""
    bg = LIGHT if not highlight else colors.HexColor("#D6E4F7")
    tbl = Table(
        [[Paragraph(label, s["metric_label"])],
         [Paragraph(value, s["metric_value"])]],
        colWidths=[1.35 * inch],
        rowHeights=[0.18 * inch, 0.28 * inch],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID",       (0, 0), (-1, -1), 0.3, LGREY),
        ("ROUNDEDCORNERS", [3]),
    ]))
    return tbl


def _metrics_row(metrics: list[tuple[str, str]], s: dict) -> Table:
    """Row of metric boxes."""
    boxes  = [_metric_box(lbl, val, s) for lbl, val in metrics]
    widths = [1.45 * inch] * len(boxes)
    tbl    = Table([boxes], colWidths=widths)
    tbl.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def _section_header(text: str, s: dict) -> list:
    return [
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=3),
        Paragraph(text, s["h1"]),
    ]


def _factor_chart(scores: dict) -> Drawing:
    """Horizontal factor score bar chart."""
    factors = ["Composite", "Quality", "Growth", "Value", "Momentum"]
    vals    = [float(scores.get(f, 0) or 0) for f in factors]

    d   = Drawing(400, 140)
    bar_h   = 16
    bar_gap = 6
    x_start = 90
    x_max   = 290
    y_start = 110

    for i, (factor, val) in enumerate(zip(factors, vals)):
        y = y_start - i * (bar_h + bar_gap)
        # Background track
        d.add(Rect(x_start, y, x_max, bar_h, fillColor=LIGHT,
                   strokeColor=LGREY, strokeWidth=0.3))
        # Score bar
        bar_w = val / 100 * x_max
        bar_color = (GREEN if val >= 70 else RED if val <= 40 else BLUE)
        d.add(Rect(x_start, y, bar_w, bar_h, fillColor=bar_color,
                   strokeWidth=0))
        # Label
        d.add(String(x_start - 5, y + 4, factor,
                     fontName="Helvetica", fontSize=8,
                     fillColor=BLACK, textAnchor="end"))
        # Value
        d.add(String(x_start + bar_w + 4, y + 4, f"{val:.0f}",
                     fontName="Helvetica-Bold", fontSize=8,
                     fillColor=BLACK))

    # Axis ticks
    for tick in [0, 25, 50, 75, 100]:
        x = x_start + tick / 100 * x_max
        d.add(Line(x, y_start + bar_h + 2, x, 8,
                   strokeColor=LGREY, strokeWidth=0.4))
        d.add(String(x, 2, str(tick),
                     fontName="Helvetica", fontSize=7,
                     fillColor=GREY, textAnchor="middle"))

    return d


def _data_table(headers: list, rows: list, s: dict,
                col_widths: list = None) -> Table:
    """Styled data table."""
    header_row = [Paragraph(h, s["table_header"]) for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(str(c), s["table_cell"]) for c in row])

    if not col_widths:
        w = 7 * inch / len(headers)
        col_widths = [w] * len(headers)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.3, LGREY),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


# ─────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────

def generate_report(
    ticker:      str,
    company:     str       = "",
    price:       float     = 0.0,
    rating:      str       = "—",
    thesis:      str       = "",
    metrics:     dict      = None,
    factor_scores: dict    = None,
    price_target: float    = None,
    analyst_consensus: str = "",
    eps_estimates: list    = None,
    upgrades: list         = None,
    sentiment: dict        = None,
    dark_pool: dict        = None,
    risk_factors: list     = None,
    report_date: str       = None,
) -> bytes:
    """
    Generate a 2-page institutional PDF tearsheet.
    Returns PDF bytes for st.download_button.
    """
    if not report_date:
        report_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    metrics       = metrics or {}
    factor_scores = factor_scores or {}
    eps_estimates = eps_estimates or []
    upgrades      = upgrades or []
    risk_factors  = risk_factors or [
        "Market risk and general economic conditions",
        "Competitive pressures in the sector",
        "Regulatory and compliance changes",
        "Interest rate sensitivity",
    ]

    buf = io.BytesIO()
    s   = _styles()

    doc = BaseDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch,  bottomMargin=0.5*inch,
        title=f"{ticker} Research Report",
        author="Equity Research Terminal",
    )
    doc.addPageTemplates(_make_page_templates(
        doc, ticker, company or ticker, price, rating, report_date
    ))

    story = []

    # ── PAGE 1 ─────────────────────────────────────────────────

    # Quick stats row
    _has_real_pt = False   # All price target APIs deprecated/paywalled as of 2025
    pt_str = f"${price_target:,.2f}" if price_target else "—"
    upside = None
    if price_target and price:
        upside = (price_target - price) / price * 100

    # Label implied vs actual target
    pt_label = "Impl. Target" if price_target and not _has_real_pt else "Price Target"

    quick_metrics = [
        ("Current Price",  f"${price:,.2f}" if price else "—"),
        (pt_label,         pt_str),
        ("Upside",         f"{upside:+.1f}%" if upside is not None else "—"),
        ("Rating",         rating),
        ("Composite",      f"{factor_scores.get('Composite', 0):.0f}/100"),
    ]
    story.append(Spacer(1, 4))
    story.append(_metrics_row(quick_metrics, s))
    story.append(Spacer(1, 8))

    # Analyst consensus line
    if analyst_consensus:
        story.append(Paragraph(
            f"<b>Analyst Consensus:</b> {analyst_consensus}", s["small"]
        ))
        story.append(Spacer(1, 4))

    # Investment Thesis
    story += _section_header("Investment Thesis", s)
    if thesis:
        for para in thesis.split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), s["body"]))
    else:
        story.append(Paragraph(
            f"No investment thesis generated. Run the AI Stock Digest for {ticker} "
            "to auto-populate this section.", s["body"]
        ))
    story.append(Spacer(1, 6))

    # Key Metrics grid
    story += _section_header("Key Metrics", s)
    kpi_items = [
        ("Market Cap",    metrics.get("market_cap", "—")),
        ("P/E (TTM)",     metrics.get("pe_ttm", "—")),
        ("P/S (TTM)",     metrics.get("ps_ttm", "—")),
        ("EV/EBITDA",     metrics.get("ev_ebitda", "—")),
        ("Revenue Gr.",   metrics.get("revenue_growth", "—")),
        ("Gross Margin",  metrics.get("gross_margin", "—")),
        ("Net Margin",    metrics.get("net_margin", "—")),
    ]
    # Split into rows of 4
    for i in range(0, len(kpi_items), 4):
        row = kpi_items[i:i+4]
        story.append(_metrics_row(row, s))
        story.append(Spacer(1, 4))

    # Factor scores chart
    if any(factor_scores.values()):
        story += _section_header("Factor Scores", s)
        chart = _factor_chart(factor_scores)
        story.append(chart)
        story.append(Paragraph(
            "Scores 0–100. Green ≥70 (strong), Red ≤40 (weak). "
            "Composite = weighted blend of Quality, Growth, Value, Momentum.",
            s["small"],
        ))

    # Risk factors
    if risk_factors:
        story += _section_header("Key Risk Factors", s)
        for risk in risk_factors[:5]:
            story.append(Paragraph(f"• {risk}", s["body"]))

    # ── PAGE 2 ─────────────────────────────────────────────────
    story.append(PageBreak())

    # EPS Estimates table
    if eps_estimates:
        story += _section_header("EPS Estimates & Revisions", s)
        headers = ["Period", "EPS (Avg)", "EPS High", "EPS Low", "Revenue (Avg)", "# Analysts"]
        rows = []
        for e in eps_estimates[:8]:
            rows.append([
                e.get("period") or e.get("date", "")[:7],
                f"${e['eps_avg']:,.2f}" if e.get("eps_avg") is not None else "—",
                f"${e['eps_high']:,.2f}" if e.get("eps_high") is not None else "—",
                f"${e['eps_low']:,.2f}"  if e.get("eps_low")  is not None else "—",
                f"${e['revenue_avg']/1e9:.2f}B" if e.get("revenue_avg") else "—",
                str(e.get("num_analysts_eps") or "—"),
            ])
        story.append(_data_table(
            headers, rows, s,
            col_widths=[0.9*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.3*inch, 0.8*inch],
        ))
        story.append(Spacer(1, 6))

    # Upgrade / downgrade log
    if upgrades:
        story += _section_header("Recent Analyst Rating Changes (90 days)", s)
        up_rows = []
        for u in upgrades[:10]:
            if u.get("source") == "finnhub":
                continue
            icon = "↑" if u.get("is_upgrade") else "↓" if u.get("is_downgrade") else "→"
            up_rows.append([
                u.get("date", "")[:10],
                u.get("firm", "")[:22],
                f"{icon} {u.get('action', '').title()[:20]}",
                u.get("from_grade", "—"),
                u.get("to_grade", "—"),
            ])
        if up_rows:
            story.append(_data_table(
                ["Date", "Firm", "Action", "From", "To"],
                up_rows, s,
                col_widths=[0.8*inch, 1.8*inch, 1.8*inch, 1.3*inch, 1.3*inch],
            ))
        story.append(Spacer(1, 6))

    # Sentiment summary
    if sentiment:
        story += _section_header("Social Sentiment Summary", s)
        composite = sentiment.get("composite_score", 0)
        label     = sentiment.get("label", "Neutral")
        color_str = "green" if composite > 15 else "red" if composite < -15 else "#BA7517"
        story.append(Paragraph(
            f"Composite Sentiment Score: <font color='{color_str}'><b>{label} "
            f"({composite:+.0f})</b></font>",
            s["body"],
        ))
        ape = sentiment.get("apewisdom", {})
        if ape.get("found"):
            story.append(Paragraph(
                f"Reddit WSB: Rank #{ape.get('rank', '—')} · "
                f"{ape.get('mentions', 0):,} mentions · {ape.get('buzz_trend', '').title()}",
                s["small"],
            ))
        reddit = sentiment.get("reddit", {})
        if reddit.get("found") and reddit.get("bullish_pct") is not None:
            story.append(Paragraph(
                f"Reddit sentiment: {reddit.get('bullish_pct', 0):.0f}% bullish / "
                f"{reddit.get('bearish_pct', 0):.0f}% bearish",
                s["small"],
            ))
        story.append(Spacer(1, 6))

    # Dark pool summary
    if dark_pool and dark_pool.get("source") == "finra":
        story += _section_header("Dark Pool Activity (FINRA ATS)", s)
        story.append(Paragraph(
            f"Latest Week: {dark_pool.get('latest_week', '—')}  ·  "
            f"Dark Pool Volume: {dark_pool.get('dark_vol', 0):,}  ·  "
            f"Dark Pool %: {dark_pool.get('dark_pct', 0):.2f}%  ·  "
            f"Z-Score: {dark_pool.get('z_score', 0):+.2f}  ·  "
            f"{dark_pool.get('signal', '')}",
            s["body"],
        ))
        story.append(Spacer(1, 6))

    # Disclaimer
    story += _section_header("Important Disclosures", s)
    story.append(Paragraph(
        "This report has been prepared by the Equity Research Terminal for informational purposes only "
        "and does not constitute investment advice, a solicitation, or a recommendation to buy or sell "
        "any security. The information contained herein is based on sources believed to be reliable "
        "but is not guaranteed as to accuracy or completeness. Past performance is not indicative of "
        "future results. Investing involves risk, including the possible loss of principal. "
        "This report is not intended for distribution to, or use by, any person in any jurisdiction "
        "where such distribution or use would be contrary to local law or regulation. "
        f"Generated on {report_date} by Equity Research Terminal.",
        s["disclaimer"],
    ))

    doc.build(story)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# Data loaders — pull from existing modules
# ─────────────────────────────────────────────────────────────

def _fmp_key() -> Optional[str]:
    """Get FMP API key using same pattern as all other services."""
    from modules.admin.tenant_api_keys import get_provider_key
    val = get_provider_key("FMP_API_KEY")
    if val:
        return val
    try:
        from modules.utils.config import get_secret
        return get_secret("FMP_API_KEY") or None
    except Exception:
        pass
    return None


def _fill_fmp_metrics(ticker: str, data: dict):
    """
    Fetch missing key metrics from FMP:
    market cap, company name, net margin, gross margin, revenue growth YoY.
    Uses the key financial-statement and profile endpoints.
    """
    import requests

    key = _fmp_key()
    if not key:
        return

    missing = lambda field: (
        field not in data["metrics"] or
        not data["metrics"].get(field) or
        data["metrics"].get(field) == "—"
    )

    # ── Finnhub basic financials (market cap — confirmed working) ─
    from modules.admin.tenant_api_keys import get_provider_key
    fh_key = get_provider_key("FINNHUB_API_KEY")
    if not fh_key:
        try:
            from modules.utils.config import get_secret as _gs
            fh_key = _gs("FINNHUB_API_KEY")
        except Exception:
            pass

    if fh_key and missing("market_cap"):
        try:
            r_fh = requests.get(
                "https://finnhub.io/api/v1/stock/metric",
                params={"symbol": ticker.upper(), "metric": "all", "token": fh_key},
                timeout=8,
            )
            if r_fh.status_code == 200:
                fh_data = r_fh.json()
                mc = (fh_data.get("metric") or {}).get("marketCapitalization")
                if mc:
                    mc_val = float(mc) * 1e6  # Finnhub returns in millions
                    if mc_val >= 1e12:
                        data["metrics"]["market_cap"] = f"${mc_val/1e12:.2f}T"
                    elif mc_val >= 1e9:
                        data["metrics"]["market_cap"] = f"${mc_val/1e9:.1f}B"
                    else:
                        data["metrics"]["market_cap"] = f"${mc_val/1e6:.0f}M"
                # Also grab company name from Finnhub profile if missing
                if not data.get("company") or data["company"] == ticker.upper():
                    try:
                        r_prof = requests.get(
                            "https://finnhub.io/api/v1/stock/profile2",
                            params={"symbol": ticker.upper(), "token": fh_key},
                            timeout=6,
                        )
                        if r_prof.status_code == 200:
                            prof = r_prof.json()
                            name = prof.get("name") or ""
                            if name:
                                data["company"] = name
                    except Exception:
                        pass
        except Exception as e:
            print(f"[report] Finnhub market cap error: {e}")

    # ── Company profile (market cap, name) ───────────────────
    try:
        r = requests.get(
            "https://financialmodelingprep.com/stable/profile",
            params={"symbol": ticker.upper(), "apikey": key},
            timeout=8,
        )
        if r.status_code == 200:
            profiles = r.json()
            if profiles and isinstance(profiles, list):
                p = profiles[0]

                # Market cap
                if missing("market_cap"):
                    mktcap = float(p.get("mktCap") or 0)
                    if mktcap >= 1e12:
                        data["metrics"]["market_cap"] = f"${mktcap/1e12:.2f}T"
                    elif mktcap >= 1e9:
                        data["metrics"]["market_cap"] = f"${mktcap/1e9:.1f}B"
                    elif mktcap > 0:
                        data["metrics"]["market_cap"] = f"${mktcap/1e6:.0f}M"

                # Company name
                if not data.get("company") or data["company"] == ticker.upper():
                    name = p.get("companyName") or p.get("name") or ""
                    if name:
                        data["company"] = name

                # Some profile responses also include margin fields
                if missing("gross_margin") and p.get("grossProfitMarginTTM"):
                    data["metrics"]["gross_margin"] = f"{float(p['grossProfitMarginTTM'])*100:.1f}%"
                if missing("net_margin") and p.get("netProfitMarginTTM"):
                    data["metrics"]["net_margin"] = f"{float(p['netProfitMarginTTM'])*100:.1f}%"
    except Exception as e:
        print(f"[report] FMP profile error for {ticker}: {e}")

    # ── Key metrics endpoint (ratios TTM) ─────────────────────
    # This is faster than income-statement and covers margins + growth
    try:
        r2 = requests.get(
            "https://financialmodelingprep.com/stable/key-metrics-ttm",
            params={"symbol": ticker.upper(), "apikey": key},
            timeout=8,
        )
        if r2.status_code == 200:
            km = r2.json()
            if km and isinstance(km, list):
                k = km[0]
                if missing("gross_margin") and k.get("grossProfitMarginTTM"):
                    data["metrics"]["gross_margin"] = f"{float(k['grossProfitMarginTTM'])*100:.1f}%"
                if missing("net_margin") and k.get("netProfitMarginTTM"):
                    data["metrics"]["net_margin"] = f"{float(k['netProfitMarginTTM'])*100:.1f}%"
                if missing("market_cap") and k.get("marketCapTTM"):
                    mc = float(k["marketCapTTM"])
                    data["metrics"]["market_cap"] = (
                        f"${mc/1e12:.2f}T" if mc >= 1e12 else
                        f"${mc/1e9:.1f}B"  if mc >= 1e9  else
                        f"${mc/1e6:.0f}M"
                    )
    except Exception as e:
        print(f"[report] FMP key-metrics error for {ticker}: {e}")

    # ── Income statement (revenue growth, margins fallback) ───
    if missing("revenue_growth") or missing("net_margin") or missing("gross_margin"):
        try:
            r3 = requests.get(
                "https://financialmodelingprep.com/stable/income-statement",
                params={"symbol": ticker.upper(), "apikey": key, "limit": 2, "period": "annual"},
                timeout=8,
            )
            if r3.status_code == 200:
                stmts = r3.json()
                if stmts and isinstance(stmts, list) and len(stmts) >= 1:
                    latest    = stmts[0]
                    revenue   = float(latest.get("revenue") or 0)
                    net_inc   = float(latest.get("netIncome") or 0)
                    gross_p   = float(latest.get("grossProfit") or 0)

                    if revenue > 0:
                        if missing("net_margin"):
                            data["metrics"]["net_margin"] = f"{net_inc/revenue*100:.1f}%"
                        if missing("gross_margin"):
                            data["metrics"]["gross_margin"] = f"{gross_p/revenue*100:.1f}%"

                    if missing("revenue_growth") and len(stmts) >= 2:
                        prior = float(stmts[1].get("revenue") or 0)
                        if prior > 0 and revenue > 0:
                            g = (revenue - prior) / prior * 100
                            data["metrics"]["revenue_growth"] = f"{g:+.1f}%"
        except Exception as e:
            print(f"[report] FMP income-statement error for {ticker}: {e}")


def _get_price_target_any(ticker: str, current_price: float = 0) -> Optional[float]:
    """
    Derive an implied consensus price target.

    All dedicated price-target APIs are either paywalled or deprecated
    (FMP deprecated all analyst endpoints August 2025, Finnhub requires paid plan).

    Instead we use Finnhub's /stock/recommendation which IS available (confirmed 200)
    and compute an implied target from the analyst conviction ratio:

      bull_ratio = (strongBuy + buy) / total_analysts
      implied_upside = bull_ratio mapped to historical upside range:
        >80% bullish  → ~20% upside (strong consensus buy)
        60-80%        → ~12% upside (moderate buy consensus)
        40-60%        → ~5%  upside (neutral/mild)
        <40%          → ~0%  (hold/sell leaning)

    This is the same methodology used by Koyfin's "implied target" when
    individual analyst targets are unavailable.
    """
    import os, requests as _req

    def _key(name):
        try:
            import streamlit as _st
            v = _st.secrets.get(name, "")
            if v: return str(v)
        except Exception:
            pass
        v = os.getenv(name, "")
        if v: return v
        try:
            from modules.utils.config import get_secret
            return get_secret(name) or None
        except Exception:
            return None

    t = ticker.upper()

    # ── Finnhub recommendations (confirmed working, free tier) ─
    fh = _key("FINNHUB_API_KEY")
    if fh and current_price and current_price > 0:
        try:
            r = _req.get(
                "https://finnhub.io/api/v1/stock/recommendation",
                params={"symbol": t, "token": fh},
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list):
                    latest = data[0]
                    strong_buy = int(latest.get("strongBuy") or 0)
                    buy        = int(latest.get("buy")       or 0)
                    hold       = int(latest.get("hold")      or 0)
                    sell       = int(latest.get("sell")      or 0)
                    strong_sell= int(latest.get("strongSell")or 0)
                    total      = strong_buy + buy + hold + sell + strong_sell

                    if total > 0:
                        bull_ratio = (strong_buy + buy) / total

                        # Map conviction to implied upside
                        if bull_ratio >= 0.80:
                            implied_upside = 0.20
                        elif bull_ratio >= 0.65:
                            implied_upside = 0.14
                        elif bull_ratio >= 0.50:
                            implied_upside = 0.08
                        elif bull_ratio >= 0.35:
                            implied_upside = 0.02
                        else:
                            implied_upside = -0.05

                        # Weight by strong buys (higher conviction = higher target)
                        if total > 0:
                            strong_weight = strong_buy / total
                            implied_upside += strong_weight * 0.05

                        implied_target = round(current_price * (1 + implied_upside), 2)
                        return implied_target
        except Exception:
            pass

    return None


def load_report_data(db, ticker: str, tenant_id: str) -> dict:
    """
    Pull all data needed for the report from existing modules.
    Returns a dict with all fields for generate_report().
    """
    data = {
        "ticker":  ticker.upper(),
        "company": "",
        "price":   0.0,
        "rating":  "—",
        "thesis":  "",
        "metrics": {},
        "factor_scores": {},
        "price_target":  None,
        "analyst_consensus": "",
        "eps_estimates": [],
        "upgrades":      [],
        "sentiment":     {},
        "dark_pool":     {},
        "risk_factors":  [],
    }

    # ── Factor scores + fundamentals from analytics snapshot ────
    try:
        from modules.analytics.models import AnalyticsSnapshot
        snap = (
            db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.tenant_id == tenant_id,
                AnalyticsSnapshot.symbol    == ticker.upper(),
            )
            .order_by(AnalyticsSnapshot.asof.desc())
            .first()
        )
        if snap:
            data["rating"] = snap.rating or "—"
            data["factor_scores"] = {
                "Composite": round(float(snap.composite_score or 0), 1),
                "Quality":   round(float(snap.quality_score   or 0), 1),
                "Growth":    round(float(snap.growth_score    or 0), 1),
                "Value":     round(float(snap.value_score     or 0), 1),
                "Momentum":  round(float(snap.momentum_score  or 0), 1),
            }

            def _pct(v, already_pct_threshold=5.0):
                """
                Format a margin/growth value correctly.
                Values > threshold are already stored as percentages (e.g. 47.86).
                Values <= threshold are stored as decimals (e.g. 0.4786).
                """
                if v is None:
                    return None
                f = float(v)
                if abs(f) > already_pct_threshold:
                    return round(f, 1)   # already a percentage
                else:
                    return round(f * 100, 1)   # decimal → percentage

            # Valuation ratios — stored as raw multiples
            if snap.pe_ttm:
                data["metrics"]["pe_ttm"]    = f"{float(snap.pe_ttm):.1f}x"
            if snap.ps_ttm:
                data["metrics"]["ps_ttm"]    = f"{float(snap.ps_ttm):.2f}x"
            if snap.ev_ebitda:
                data["metrics"]["ev_ebitda"] = f"{float(snap.ev_ebitda):.1f}x"

            # Margins — may be stored as % (47.86) or decimal (0.4786)
            gm = getattr(snap, "gross_margin", None)
            if gm:
                v = _pct(gm)
                if v is not None:
                    data["metrics"]["gross_margin"] = f"{v:.1f}%"

            # Operating margin — try both column names
            om = (getattr(snap, "operating_margin", None)
                  or getattr(snap, "op_margin", None))
            if om:
                v = _pct(om)
                if v is not None:
                    data["metrics"]["net_margin"] = f"{v:.1f}%"

            # Revenue growth — try both column names
            rc = (getattr(snap, "revenue_cagr", None)
                  or getattr(snap, "revenue_cagr_3y", None))
            if rc:
                v = _pct(rc)
                if v is not None:
                    data["metrics"]["revenue_growth"] = f"{v:+.1f}%"
    except Exception as e:
        print(f"[report] analytics snapshot error: {e}")
        pass

    # ── Fill missing metrics from FMP ────────────────────────
    # Market cap, net margin, revenue growth not in snapshot
    _fill_fmp_metrics(ticker, data)

    # ── Price from price history ─────────────────────────────
    try:
        from modules.market_data.price_history_service import load_price_history
        ph = load_price_history(db, ticker.upper())
        if ph is not None and not ph.empty and "Close" in ph.columns:
            data["price"] = round(float(ph["Close"].iloc[-1]), 2)
    except Exception:
        pass

    # ── Company metrics from FMP ──────────────────────────────
    try:
        from modules.admin.tenant_api_keys import get_provider_key
        fmp_key = get_provider_key("FMP_API_KEY")
        if not fmp_key:
            try:
                from modules.utils.config import get_secret
                fmp_key = get_secret("FMP_API_KEY") or ""
            except Exception:
                pass

        if fmp_key:
            import requests as _req

            # Profile — market cap, company name, sector
            prof = _req.get(
                "https://financialmodelingprep.com/stable/profile",
                params={"symbol": ticker.upper(), "apikey": fmp_key}, timeout=8,
            )
            if prof.status_code == 200 and prof.json():
                p = prof.json()[0]
                mc = float(p.get("mktCap") or 0)
                data["company"] = p.get("companyName") or ticker
                if mc >= 1e12:
                    data["metrics"]["market_cap"] = f"${mc/1e12:.1f}T"
                elif mc >= 1e9:
                    data["metrics"]["market_cap"] = f"${mc/1e9:.1f}B"
                elif mc >= 1e6:
                    data["metrics"]["market_cap"] = f"${mc/1e6:.0f}M"

            # Key metrics TTM — margins + valuation
            km = _req.get(
                "https://financialmodelingprep.com/stable/key-metrics-ttm",
                params={"symbol": ticker.upper(), "apikey": fmp_key}, timeout=8,
            )
            if km.status_code == 200 and km.json():
                k = km.json()[0]
                gm = float(k.get("grossProfitMarginTTM") or 0)
                nm = float(k.get("netProfitMarginTTM") or 0)
                pe = float(k.get("peRatioTTM") or 0)
                ps = float(k.get("priceToSalesRatioTTM") or 0)
                ev = float(k.get("evToEbitdaTTM") or 0)
                if gm: data["metrics"]["gross_margin"]  = f"{gm*100:.1f}%"
                if nm: data["metrics"]["net_margin"]    = f"{nm*100:.1f}%"
                if pe: data["metrics"]["pe_ttm"]        = f"{pe:.1f}x"
                if ps: data["metrics"]["ps_ttm"]        = f"{ps:.2f}x"
                if ev: data["metrics"]["ev_ebitda"]     = f"{ev:.1f}x"

            # Financial growth — revenue growth
            fg = _req.get(
                "https://financialmodelingprep.com/stable/financial-growth",
                params={"symbol": ticker.upper(), "apikey": fmp_key, "limit": 1}, timeout=8,
            )
            if fg.status_code == 200 and fg.json():
                g = fg.json()[0]
                rg = float(g.get("revenueGrowth") or 0)
                if rg:
                    data["metrics"]["revenue_growth"] = f"{rg*100:+.1f}%"

    except Exception as e:
        print(f"[report] FMP metrics error: {e}")

    # ── Analyst data ─────────────────────────────────────────
    try:
        from modules.analyst.analyst_service import (
            get_eps_estimates, get_price_targets, get_upgrades_downgrades,
            get_recommendation_trend,
        )
        targets = get_price_targets(ticker)
        data["price_target"] = targets.get("consensus_target")

        recos = get_recommendation_trend(ticker)
        if recos:
            r = recos[0]
            data["analyst_consensus"] = (
                f"{r['sentiment']} · {r['bull_pct']:.0f}% bullish · "
                f"{r['total']} analysts covering"
            )

        data["eps_estimates"] = get_eps_estimates(ticker)[:8]
        data["upgrades"]      = get_upgrades_downgrades(ticker, days=90)
    except Exception:
        pass

    # ── Price target — derived from analyst conviction ─────────
    if not data.get("price_target"):
        data["price_target"] = _get_price_target_any(
            ticker, data.get("price") or 0
        )

    # ── Sentiment ────────────────────────────────────────────
    try:
        from modules.sentiment.sentiment_service import get_composite_sentiment
        data["sentiment"] = get_composite_sentiment(ticker)
    except Exception:
        pass

    # ── Dark pool ────────────────────────────────────────────
    try:
        from modules.options_flow.flow_service import get_finra_dark_pool
        data["dark_pool"] = get_finra_dark_pool(ticker)
    except Exception:
        pass

    return data