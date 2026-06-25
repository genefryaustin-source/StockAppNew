"""
modules/reports/report_ui.py

PDF Research Report — Streamlit UI.

Lets users generate institutional-quality PDF tearsheets for any ticker.
Pre-populates all fields from existing app data (analytics, analyst,
sentiment, dark pool) and allows the user to customise before generating.

Add to app.py:
    elif page == "Research Reports":
        from modules.reports.report_ui import render_reports_page
        render_reports_page(db, user)
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from modules.reports.pdf_service import generate_report, load_report_data


def render_reports_page(db, user: dict):
    tenant_id = user.get("tenant_id", "")

    st.header("📄 PDF Research Reports")
    st.caption(
        "Generate institutional-quality investment tearsheets — "
        "investment thesis, factor scores, analyst consensus, EPS estimates, "
        "social sentiment, dark pool summary. Download as PDF."
    )

    # ── Ticker input ──────────────────────────────────────────
    col_sym, col_load = st.columns([3, 1])
    with col_sym:
        ticker = st.text_input(
            "Ticker", value="NVDA",
            placeholder="AAPL, NVDA, TSLA…",
            key="report_ticker",
        ).upper().strip()
    with col_load:
        st.write("")
        load_btn = st.button("Load Data", key="report_load",
                             use_container_width=True, type="secondary")

    if not ticker:
        st.info("Enter a ticker to begin.")
        return

    # Load data on button press or first visit
    cache_key = f"report_data_{ticker}"
    if load_btn or cache_key not in st.session_state:
        with st.spinner(f"Loading data for {ticker}…"):
            st.session_state[cache_key] = load_report_data(db, ticker, tenant_id)

    rdata = st.session_state.get(cache_key, {})

    # ── Report options ────────────────────────────────────────
    st.divider()
    st.markdown("#### Report Options")

    col1, col2, col3 = st.columns(3)
    with col1:
        company = st.text_input(
            "Company name",
            value=rdata.get("company") or ticker,
            key="report_company",
        )
        price = st.number_input(
            "Current price ($)",
            value=float(rdata.get("price") or 0),
            min_value=0.0, step=0.01, format="%.2f",
            key="report_price",
        )
    with col2:
        rating = st.selectbox(
            "Rating",
            ["Buy", "Strong Buy", "Hold", "Underperform", "Sell", "—"],
            index=["Buy", "Strong Buy", "Hold", "Underperform",
                   "Sell", "—"].index(rdata.get("rating", "—"))
            if rdata.get("rating", "—") in
            ["Buy", "Strong Buy", "Hold", "Underperform", "Sell", "—"]
            else 5,
            key="report_rating",
        )
        price_target = st.number_input(
            "Price target ($)",
            value=float(rdata.get("price_target") or 0),
            min_value=0.0, step=0.01, format="%.2f",
            key="report_pt",
        )
    with col3:
        sections = st.multiselect(
            "Include sections",
            ["EPS Estimates", "Analyst Upgrades", "Social Sentiment",
             "Dark Pool", "Risk Factors"],
            default=["EPS Estimates", "Analyst Upgrades",
                     "Social Sentiment", "Dark Pool", "Risk Factors"],
            key="report_sections",
        )

    # ── Investment thesis ─────────────────────────────────────
    st.markdown("#### Investment Thesis")
    st.caption(
        "Edit or generate. Use the AI button to auto-populate from your "
        "existing Stock Digest data, or type your own thesis."
    )

    col_ai, col_clear = st.columns([1, 5])
    with col_ai:
        gen_thesis = st.button("✨ Generate with AI", key="report_gen_thesis")

    if gen_thesis:
        with st.spinner("Generating investment thesis…"):
            thesis_text = _generate_thesis(ticker, rdata)
            st.session_state["report_thesis_text"] = thesis_text

    default_thesis = st.session_state.get(
        "report_thesis_text",
        rdata.get("thesis") or
        f"Enter your investment thesis for {ticker} here. "
        "Click 'Generate with AI' to auto-populate from app data."
    )
    thesis = st.text_area(
        "Investment thesis",
        value=default_thesis,
        height=150,
        key="report_thesis",
        label_visibility="collapsed",
    )

    # ── Factor scores preview ─────────────────────────────────
    fs = rdata.get("factor_scores", {})
    if fs:
        st.markdown("#### Factor Scores (from Analytics)")
        sc = st.columns(5)
        labels = ["Composite", "Quality", "Growth", "Value", "Momentum"]
        for col, lbl in zip(sc, labels):
            v = fs.get(lbl, 0)
            delta_color = "normal" if v >= 60 else "inverse" if v <= 40 else "off"
            col.metric(lbl, f"{v:.0f}", delta_color=delta_color)

    # ── Data preview ──────────────────────────────────────────
    with st.expander("📋 Preview loaded data", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Analyst Consensus**")
            st.caption(rdata.get("analyst_consensus") or "Not loaded")
            st.markdown("**EPS Estimates**")
            eps = rdata.get("eps_estimates", [])
            st.caption(f"{len(eps)} periods loaded" if eps else "None")
            st.markdown("**Upgrades/Downgrades**")
            ups = rdata.get("upgrades", [])
            st.caption(f"{len(ups)} events in last 90 days" if ups else "None")
        with col_b:
            st.markdown("**Social Sentiment**")
            sent = rdata.get("sentiment", {})
            if sent.get("composite_score") is not None:
                st.caption(
                    f"{sent.get('label', '—')} · "
                    f"Score: {sent.get('composite_score', 0):+.0f}"
                )
            else:
                st.caption("Not loaded")
            st.markdown("**Dark Pool**")
            dp = rdata.get("dark_pool", {})
            if dp.get("source") == "finra":
                st.caption(
                    f"FINRA · {dp.get('dark_pct', 0):.2f}% · "
                    f"Z-score {dp.get('z_score', 0):+.2f}"
                )
            else:
                st.caption("Not loaded or proxy mode")

    st.divider()

    # ── Generate button ───────────────────────────────────────
    col_gen, col_info = st.columns([1, 3])
    with col_gen:
        generate_btn = st.button(
            "📄 Generate PDF Report",
            type="primary",
            key="report_generate",
            use_container_width=True,
        )
    with col_info:
        st.caption(
            "Generates a 2-page institutional tearsheet including all selected sections. "
            "Typical generation time: 3–5 seconds."
        )

    if generate_btn:
        with st.spinner("Generating PDF…"):
            try:
                pdf_bytes = generate_report(
                    ticker=ticker,
                    company=company or ticker,
                    price=price or rdata.get("price") or 0,
                    rating=rating,
                    thesis=thesis,
                    metrics=rdata.get("metrics", {}),
                    factor_scores=rdata.get("factor_scores", {}),
                    price_target=price_target or rdata.get("price_target"),
                    analyst_consensus=rdata.get("analyst_consensus", ""),
                    eps_estimates=rdata.get("eps_estimates", [])
                                  if "EPS Estimates" in sections else [],
                    upgrades=rdata.get("upgrades", [])
                             if "Analyst Upgrades" in sections else [],
                    sentiment=rdata.get("sentiment", {})
                              if "Social Sentiment" in sections else {},
                    dark_pool=rdata.get("dark_pool", {})
                              if "Dark Pool" in sections else {},
                    risk_factors=_default_risks(ticker)
                                 if "Risk Factors" in sections else [],
                    report_date=datetime.now().strftime("%B %d, %Y"),
                )

                fname = (
                    f"{ticker}_research_report_"
                    f"{datetime.now().strftime('%Y%m%d')}.pdf"
                )
                st.download_button(
                    "📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    key="report_download",
                )
                st.success(
                    f"✅ Report generated — click **Download PDF Report** above. "
                    f"File: `{fname}`"
                )

            except Exception as e:
                st.error(f"Report generation failed: {e}")
                import traceback
                st.code(traceback.format_exc())


# ─────────────────────────────────────────────────────────────
# AI thesis generator
# ─────────────────────────────────────────────────────────────

def _generate_thesis(ticker: str, rdata: dict) -> str:
    """
    Generate investment thesis using Claude API.
    Uses existing Anthropic key already in the app.
    """
    try:
        import anthropic
        from modules.admin.tenant_api_keys import get_provider_key

        api_key = get_provider_key("ANTHROPIC_API_KEY")

        if not api_key:
            return _fallback_thesis(ticker, rdata)

        fs       = rdata.get("factor_scores", {})
        metrics  = rdata.get("metrics", {})
        sent     = rdata.get("sentiment", {})
        rating   = rdata.get("rating", "—")
        pt       = rdata.get("price_target")
        price    = rdata.get("price", 0)
        upside   = round((pt - price) / price * 100, 1) if pt and price else None

        prompt = f"""Write a concise 3-paragraph institutional investment thesis for {ticker}.

Data available:
- Rating: {rating}
- Factor scores: Composite {fs.get('Composite', 0):.0f}, Quality {fs.get('Quality', 0):.0f}, Growth {fs.get('Growth', 0):.0f}, Value {fs.get('Value', 0):.0f}, Momentum {fs.get('Momentum', 0):.0f}
- P/E: {metrics.get('pe_ttm', '—')}, P/S: {metrics.get('ps_ttm', '—')}, EV/EBITDA: {metrics.get('ev_ebitda', '—')}
- Price target: ${pt:,.2f} ({upside:+.1f}% upside) if upside else "Not set"
- Social sentiment: {sent.get('label', 'Neutral')} (score {sent.get('composite_score', 0):+.0f})

Write 3 short paragraphs:
1. Investment case (key bull thesis in 2-3 sentences)
2. Key risks (2-3 sentences)  
3. Valuation / catalyst summary (2-3 sentences)

Be direct and factual. Use professional investment research tone. No bullet points."""

        client = anthropic.Anthropic(api_key=api_key)
        resp   = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()

    except Exception as e:
        return _fallback_thesis(ticker, rdata)


def _fallback_thesis(ticker: str, rdata: dict) -> str:
    """Structured fallback thesis when AI unavailable."""
    fs     = rdata.get("factor_scores", {})
    rating = rdata.get("rating", "—")
    comp   = fs.get("Composite", 0)
    strong = "strong" if comp >= 70 else "moderate" if comp >= 50 else "weak"

    return (
        f"{ticker} shows {strong} composite factor scores "
        f"(Composite: {comp:.0f}/100) with a current analyst rating of {rating}. "
        f"The quality and momentum scores suggest "
        f"{'a fundamentally sound business with positive price action' if comp >= 60 else 'areas for improvement across key fundamental metrics'}.\n\n"
        f"Key risks include sector-specific competitive pressures, macroeconomic sensitivity, "
        f"and potential valuation contraction if growth decelerates. "
        f"Investors should monitor quarterly earnings revisions and analyst target changes closely.\n\n"
        f"The current valuation and factor profile suggest "
        f"{'a favorable risk/reward for long-term investors' if comp >= 60 else 'caution near current levels until fundamentals improve'}. "
        f"Run the AI Stock Digest for {ticker} to generate a more detailed thesis "
        f"incorporating recent news and catalysts."
    )


def _default_risks(ticker: str) -> list[str]:
    return [
        f"Competitive pressures and market share risks specific to {ticker}'s sector",
        "Macroeconomic sensitivity — rising rates and slowing growth could compress multiples",
        "Execution risk on growth initiatives and capital allocation decisions",
        "Regulatory and geopolitical risks relevant to the business",
        "Earnings revision risk if consensus estimates prove too optimistic",
    ]