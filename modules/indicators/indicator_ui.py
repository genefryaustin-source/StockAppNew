"""
modules/indicators/indicator_ui.py

Custom Indicator Builder — Streamlit UI.

Full page for:
  - Writing custom indicator conditions in plain English
  - Previewing the parsed formula with condition badges
  - Testing on a single symbol instantly
  - Running across the full universe
  - Saving formulas as reusable templates
  - Combining with screener filters for deeper analysis

Add to app.py:
    pages list: "Indicator Builder"
    elif page == "Indicator Builder":
        from modules.indicators.indicator_ui import render_indicator_builder
        render_indicator_builder(db, user)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from modules.indicators.indicator_builder import (
    IndicatorFormula,
    evaluate_formula,
    scan_universe,
    translate_indicator,
)


# ─────────────────────────────────────────────────────────────
# Examples
# ─────────────────────────────────────────────────────────────

EXAMPLES = [
    "RSI crossed above 30 in the last 3 days while price is above the 200-day MA",
    "Golden cross: 50-day SMA crossed above 200-day SMA in the past week",
    "MACD bullish crossover in the last 3 days with volume 1.5x average",
    "RSI below 30 (oversold) and price above 50-day moving average",
    "Bollinger Band squeeze with price near the upper band",
    "52-week high breakout in the last 3 days on above-average volume",
    "Death cross: 50-day SMA crossed below 200-day SMA in the past 5 days",
    "RSI crossed below 70 in the last 2 days — overbought reversal signal",
    "Price above 200-day EMA with MACD histogram positive",
    "Three consecutive higher highs with RSI above 50",
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _load_symbols(db, tenant_id: str) -> list[str]:
    try:
        from modules.analytics.models import AnalyticsSnapshot
        rows = (
            db.query(AnalyticsSnapshot.symbol)
            .filter(AnalyticsSnapshot.tenant_id == tenant_id)
            .distinct().all()
        )
        return sorted([r[0] for r in rows if r and r[0]])
    except Exception:
        return []


def _render_formula_badges(formula: IndicatorFormula):
    """Render a visual summary row of all active conditions."""
    badges = []

    if formula.rsi_cross_above is not None:
        badges.append(f"📈 RSI({formula.rsi_cross_above_period}) crossed >{formula.rsi_cross_above} in {formula.rsi_cross_above_days}d")
    if formula.rsi_cross_below is not None:
        badges.append(f"📉 RSI({formula.rsi_cross_below_period}) crossed <{formula.rsi_cross_below} in {formula.rsi_cross_below_days}d")
    if formula.rsi_above is not None:
        badges.append(f"RSI > {formula.rsi_above}")
    if formula.rsi_below is not None:
        badges.append(f"RSI < {formula.rsi_below}")
    if formula.price_above_sma is not None:
        badges.append(f"Price > SMA{formula.price_above_sma}")
    if formula.price_below_sma is not None:
        badges.append(f"Price < SMA{formula.price_below_sma}")
    if formula.price_above_ema is not None:
        badges.append(f"Price > EMA{formula.price_above_ema}")
    if formula.price_below_ema is not None:
        badges.append(f"Price < EMA{formula.price_below_ema}")
    if formula.sma_cross_above_fast and formula.sma_cross_above_slow:
        badges.append(f"⭐ SMA{formula.sma_cross_above_fast} > SMA{formula.sma_cross_above_slow} in {formula.sma_cross_above_days}d")
    if formula.sma_cross_below_fast and formula.sma_cross_below_slow:
        badges.append(f"💀 SMA{formula.sma_cross_below_fast} < SMA{formula.sma_cross_below_slow} in {formula.sma_cross_below_days}d")
    if formula.macd_cross_above:
        badges.append(f"MACD bull cross in {formula.macd_cross_above_days}d")
    if formula.macd_cross_below:
        badges.append(f"MACD bear cross in {formula.macd_cross_below_days}d")
    if formula.macd_positive:
        badges.append("MACD hist > 0")
    if formula.bb_squeeze:
        badges.append(f"BB squeeze (width < {formula.bb_squeeze_threshold})")
    if formula.price_above_bb_upper:
        badges.append("Price > BB upper")
    if formula.price_below_bb_lower:
        badges.append("Price < BB lower")
    if formula.volume_spike is not None:
        badges.append(f"Volume > {formula.volume_spike:.1f}x avg")
    if formula.high_52w_breakout:
        badges.append(f"52w breakout in {formula.high_52w_breakout_days}d")
    if formula.low_52w_breakdown:
        badges.append(f"52w breakdown in {formula.low_52w_breakdown_days}d")
    if formula.higher_highs:
        badges.append(f"{formula.higher_highs_count} higher highs in {formula.higher_highs_days}d")
    if formula.sector:
        badges.append(f"Sector: {formula.sector}")

    if badges:
        st.markdown(
            " &nbsp;·&nbsp; ".join(f"<code>{b}</code>" for b in badges),
            unsafe_allow_html=True,
        )
    else:
        st.caption("No conditions parsed.")


def _render_results_table(results: list[dict], formula_name: str):
    if not results:
        st.info("No symbols matched all conditions.")
        return

    st.success(f"✅ **{len(results)} matches** for: {formula_name}")

    # Summary metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Matches", len(results))
    c2.metric(
        "Avg Composite",
        f"{pd.DataFrame(results)['composite'].mean():.1f}"
        if results and results[0].get("composite") else "N/A"
    )
    c3.metric(
        "Buy Rated",
        len([r for r in results if r.get("rating") in ("Buy", "Strong Buy")])
    )

    df = pd.DataFrame([{
        "Symbol":    r["symbol"],
        "Price":     f"${r['price']:,.2f}" if r.get("price") else "—",
        "Sector":    r.get("sector", "—"),
        "Rating":    r.get("rating", "—"),
        "Composite": f"{r['composite']:.0f}" if r.get("composite") else "—",
        "Momentum":  f"{r['momentum']:.0f}" if r.get("momentum") else "—",
        "RSI(14)":   f"{r['rsi_14']:.1f}" if r.get("rsi_14") else "—",
        "Conditions Met": r.get("conditions_met", 0),
        "Detail":    r.get("conditions", "—"),
    } for r in results])

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️ Export CSV",
        data=csv,
        file_name=f"indicator_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="indicator_export_csv",
    )


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_indicator_builder(db, user: dict):
    tenant_id = user.get("tenant_id", "")

    st.header("⚗️ Custom Indicator Builder")
    st.caption(
        "Describe a technical condition in plain English. "
        "Claude translates it into precise indicator logic and scans your universe."
    )

    tab_build, tab_saved = st.tabs([
        "🔬 Build & Scan",
        "📁 Saved Formulas",
    ])

    with tab_build:
        _render_build_tab(db, tenant_id)

    with tab_saved:
        _render_saved_tab(db, tenant_id)


# ─────────────────────────────────────────────────────────────
# Build tab
# ─────────────────────────────────────────────────────────────

def _render_build_tab(db, tenant_id: str):

    # ── Examples ──────────────────────────────────────────────
    with st.expander("💡 Example conditions", expanded=False):
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLES):
            with cols[i % 2]:
                if st.button(ex, key=f"ind_ex_{i}", use_container_width=True):
                    st.session_state["ind_query"] = ex

    # ── Input ─────────────────────────────────────────────────
    query = st.text_area(
        "Describe your technical condition",
        placeholder="e.g. RSI crossed above 30 in the last 3 days while price is above the 200-day MA",
        key="ind_query",
        height=75,
    )

    col_parse, col_clear = st.columns([1, 5])
    with col_parse:
        parse_btn = st.button(
            "🧠 Parse",
            type="primary",
            key="ind_parse_btn",
            use_container_width=True,
        )
    with col_clear:
        if st.button("✕ Clear", key="ind_clear_btn"):
            for k in ["ind_query", "ind_formula", "ind_results"]:
                st.session_state.pop(k, None)
            st.rerun()

    if parse_btn and query.strip():
        with st.spinner("Translating with Claude…"):
            formula = translate_indicator(query)
            st.session_state["ind_formula"] = formula
            st.session_state.pop("ind_results", None)

    formula: Optional[IndicatorFormula] = st.session_state.get("ind_formula")

    if not formula:
        st.info("Enter a condition above and click **🧠 Parse** to see how it's interpreted.")
        return

    # ── Parsed formula preview ────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Parsed Formula")

    if formula.plain_summary:
        st.success(formula.plain_summary)

    for w in formula.warnings:
        st.warning(f"⚠️ {w}")

    _render_formula_badges(formula)

    if not formula.has_conditions():
        st.error("No conditions could be parsed. Try rephrasing your query.")
        return

    with st.expander("View raw formula JSON", expanded=False):
        st.json(formula.to_dict())

    # ── Quick test on one symbol ──────────────────────────────
    st.markdown("#### 🧪 Quick test")
    test_col, btn_col = st.columns([2, 1])
    with test_col:
        test_sym = st.text_input(
            "", placeholder="Test symbol (e.g. NVDA)",
            key="ind_test_sym", label_visibility="collapsed",
        )
    with btn_col:
        test_btn = st.button("▶ Test", key="ind_test_btn", use_container_width=True)

    if test_btn and test_sym.strip():
        sym = test_sym.strip().upper()
        with st.spinner(f"Evaluating {sym}…"):
            try:
                db.rollback()
            except Exception:
                pass
            from modules.market_data.service import get_price_history
            try:
                df = get_price_history(db, sym, period=formula.price_period, interval="1d")
            except Exception:
                df = None

            matched, passed, failed = evaluate_formula(sym, formula, df)

        if matched:
            st.success(f"✅ **{sym} MATCHES**")
            for p in passed:
                st.markdown(f"  ✓ {p}")
        else:
            st.info(f"❌ **{sym} does not match**")
            for p in passed:
                st.markdown(f"  ✓ {p}")
            for f_ in failed:
                st.markdown(f"  ✗ {f_}")

    # ── Run on universe ───────────────────────────────────────
    st.markdown("#### 🔭 Scan universe")

    symbols = _load_symbols(db, tenant_id)

    col_info, col_run = st.columns([3, 1])
    with col_info:
        st.caption(f"{len(symbols)} symbols in your universe")
    with col_run:
        scan_btn = st.button(
            "▶ Run Scan",
            type="primary",
            key="ind_scan_btn",
            use_container_width=True,
        )

    if not symbols:
        st.warning("No symbols in universe. Run analytics first to populate.")
        return

    if scan_btn:
        progress_bar = st.progress(0.0, text="Starting scan…")
        status_text  = st.empty()

        def _progress(pct, sym):
            progress_bar.progress(pct, text=f"Scanning {sym}…")
            status_text.caption(f"Checking {sym}…")

        results = scan_universe(
            formula=formula,
            symbols=symbols,
            db=db,
            tenant_id=tenant_id,
            progress_callback=_progress,
        )
        progress_bar.empty()
        status_text.empty()

        st.session_state["ind_results"] = results
        st.session_state["ind_results_formula"] = formula.formula_name

    results = st.session_state.get("ind_results")
    if results is not None:
        st.markdown("---")
        _render_results_table(
            results,
            st.session_state.get("ind_results_formula", formula.formula_name),
        )

        # ── Save this formula ─────────────────────────────────
        st.markdown("---")
        st.markdown("#### 💾 Save formula")
        save_name = st.text_input(
            "Formula name",
            value=formula.formula_name,
            key="ind_save_name",
        )
        if st.button("💾 Save", key="ind_save_btn"):
            saved = st.session_state.get("ind_saved_formulas", [])
            saved.append({
                "name":       save_name,
                "query":      query,
                "formula":    formula.to_dict(),
                "saved_at":   datetime.now(timezone.utc).isoformat(),
                "match_count": len(results),
            })
            st.session_state["ind_saved_formulas"] = saved
            st.success(f"✅ Saved **{save_name}**. Find it in **📁 Saved Formulas**.")


# ─────────────────────────────────────────────────────────────
# Saved formulas tab
# ─────────────────────────────────────────────────────────────

def _render_saved_tab(db, tenant_id: str):
    st.subheader("Saved indicator formulas")

    saved = st.session_state.get("ind_saved_formulas", [])

    if not saved:
        st.info(
            "No saved formulas yet. "
            "Build and run a scan, then click **💾 Save** to store it here."
        )
        return

    symbols = _load_symbols(db, tenant_id)

    for i, entry in enumerate(reversed(saved)):
        name      = entry.get("name", "Unnamed")
        query     = entry.get("query", "")
        saved_at  = entry.get("saved_at", "")
        matches   = entry.get("match_count", "?")

        ts_str = ""
        if saved_at:
            try:
                ts = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
                ts_str = ts.strftime("%b %d %H:%M")
            except Exception:
                ts_str = saved_at[:16]

        with st.expander(
            f"**{name}** · {matches} matches · {ts_str}",
            expanded=False,
        ):
            st.caption(f"Query: {query}")
            formula = IndicatorFormula.from_dict(entry.get("formula", {}))
            _render_formula_badges(formula)

            col_run, col_del = st.columns([1, 1])
            with col_run:
                if st.button(
                    "▶ Re-run Scan", key=f"saved_run_{i}",
                    use_container_width=True,
                ):
                    if not symbols:
                        st.warning("No symbols in universe.")
                    else:
                        progress_bar = st.progress(0.0)

                        def _p(pct, sym):
                            progress_bar.progress(pct)

                        results = scan_universe(formula, symbols, db, tenant_id, _p)
                        progress_bar.empty()
                        _render_results_table(results, name)

            with col_del:
                if st.button(
                    "🗑 Delete", key=f"saved_del_{i}",
                    use_container_width=True,
                ):
                    actual_i = len(saved) - 1 - i
                    st.session_state["ind_saved_formulas"].pop(actual_i)
                    st.rerun()