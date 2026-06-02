"""
modules/smc/smc_ui.py

Streamlit UI for the Smart Money Concepts page.
Mirrors the Phantom Flow feature set:
  - Live dashboard (trend bias, OB count, FVG count, structure, momentum, sweep)
  - Full SMC chart (candlesticks + OBs + FVGs + BOS/CHoCH + momentum panel)
  - Signal table (all active zones with price levels)

Add to app.py:
──────────────────────────────────────────────────────────
    elif page == "Smart Money":
        from modules.smc.smc_ui import render_smc_page
        render_smc_page(db, user)
──────────────────────────────────────────────────────────

Add "Smart Money" to the pages list in section 15 of app.py.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from modules.market_data.service import get_price_history
from modules.smc.smc_engine import analyse
from modules.smc.smc_chart import render_smc_chart


def render_smc_page(db, user):
    st.header("🔮 Smart Money Concepts")
    st.caption(
        "Order blocks · Fair value gaps · BOS/CHoCH structure · Momentum · "
        "Institutional bias detection"
    )

    # ── Controls ──────────────────────────────────────────────
    col_sym, col_tf, col_swing, col_run = st.columns([1, 1, 1, 1])
    with col_sym:
        symbol = st.text_input("Ticker", value="NVDA", key="smc_symbol").upper().strip()
    with col_tf:
        period = st.selectbox("Period", ["1mo","3mo","6mo","1y","2y"], index=2, key="smc_period")
    with col_swing:
        swing_len = st.slider("Swing sensitivity", 3, 10, 5, key="smc_swing")
    with col_run:
        st.write("")
        run = st.button("▶ Analyse", type="primary", key="smc_run", use_container_width=True)

    if not symbol:
        st.info("Enter a ticker to begin.")
        return

    cache_key = f"smc_{symbol}_{period}_{swing_len}"

    if run or cache_key not in st.session_state:
        with st.spinner(f"Running SMC analysis on {symbol}…"):
            try:
                df = get_price_history(db, symbol, period=period, interval="1d")
            except Exception as e:
                st.error(f"Failed to load price data: {e}")
                return

            if df is None or df.empty:
                st.warning(f"No price data for {symbol}.")
                return

            result = analyse(df, swing_length=swing_len)
            st.session_state[cache_key] = (df, result)

    if cache_key not in st.session_state:
        return

    df, result = st.session_state[cache_key]

    # ── Dashboard panel ───────────────────────────────────────
    _render_dashboard(result.dashboard, symbol)

    st.divider()

    # ── Chart ─────────────────────────────────────────────────
    fig = render_smc_chart(df, result, symbol=symbol)
    st.pyplot(fig, use_container_width=True)

    st.divider()

    # ── Signal tables ─────────────────────────────────────────
    tab_ob, tab_fvg, tab_struct = st.tabs([
        f"📦 Order Blocks ({len(result.order_blocks)})",
        f"〰️ Fair Value Gaps ({len(result.fvgs)})",
        f"🔗 Structure Events ({len(result.structure)})",
    ])

    with tab_ob:
        _render_ob_table(result.order_blocks)

    with tab_fvg:
        _render_fvg_table(result.fvgs)

    with tab_struct:
        _render_structure_table(result.structure)


# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────

def _render_dashboard(d: dict, symbol: str):
    trend       = d.get("trend", "Ranging")
    strength    = d.get("trend_strength", 0)
    active_obs  = d.get("active_obs", 0)
    active_fvgs = d.get("active_fvgs", 0)
    last_struct = d.get("last_structure", "—")
    support     = d.get("nearest_support")
    resistance  = d.get("nearest_resistance")
    mom_label   = d.get("momentum_label", "Neutral")
    mom_val     = d.get("momentum_value", 0)
    swept       = d.get("liquidity_swept", False)

    trend_emoji = "🟢" if trend == "Bullish" else "🔴" if trend == "Bearish" else "🟡"
    mom_emoji   = "🟢" if "Bull" in mom_label or mom_label == "Overbought" else \
                  "🔴" if "Bear" in mom_label or mom_label == "Oversold"   else "🟡"
    sweep_str   = "⚡ YES" if swept else "None"

    st.markdown(f"### 📊 {symbol} — SMC Dashboard")

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Bias",          f"{trend_emoji} {trend}")
    c2.metric("Trend Strength", f"{int(strength * 100)}%")
    c3.metric("Active OBs",    active_obs)
    c4.metric("Open FVGs",     active_fvgs)
    c5.metric("Momentum",      f"{mom_emoji} {mom_label}")
    c6.metric("Last Structure", _format_struct(last_struct))
    c7.metric("Liq. Sweep",    sweep_str)

    # Support / resistance row
    if support or resistance:
        sc, rc = st.columns(2)
        if support:
            sc.info(f"🟢 **Nearest OB Support:** ${support:,.2f}")
        if resistance:
            rc.warning(f"🔴 **Nearest OB Resistance:** ${resistance:,.2f}")


def _format_struct(kind: str) -> str:
    mapping = {
        "BOS_bull":   "BOS ↑",
        "BOS_bear":   "BOS ↓",
        "CHoCH_bull": "CHoCH ↑",
        "CHoCH_bear": "CHoCH ↓",
    }
    return mapping.get(kind, kind)


# ─────────────────────────────────────────────────────────────
# Signal tables
# ─────────────────────────────────────────────────────────────

def _render_ob_table(obs):
    if not obs:
        st.info("No active order blocks detected.")
        return

    rows = []
    for ob in obs:
        rows.append({
            "Type":      "🟢 Bullish" if ob.kind == "bullish" else "🔴 Bearish",
            "Top":       f"${ob.top:,.2f}",
            "Bottom":    f"${ob.bottom:,.2f}",
            "Midpoint":  f"${(ob.top + ob.bottom) / 2:,.2f}",
            "Strength":  f"{int(ob.strength * 100)}%",
            "Date":      ob.date[:10] if ob.date else "—",
            "Status":    "⚠️ Mitigated" if ob.mitigated else "✅ Active",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Order blocks are the last opposite-colour candle before a strong directional move. "
        "Price often returns to these zones before continuing."
    )


def _render_fvg_table(fvgs):
    if not fvgs:
        st.info("No open fair value gaps detected.")
        return

    rows = []
    for fvg in fvgs:
        size_pct = ((fvg.top - fvg.bottom) / fvg.bottom * 100) if fvg.bottom else 0
        rows.append({
            "Type":     "🟢 Bullish" if fvg.kind == "bullish" else "🔴 Bearish",
            "Top":      f"${fvg.top:,.2f}",
            "Bottom":   f"${fvg.bottom:,.2f}",
            "Size":     f"{size_pct:.2f}%",
            "Date":     fvg.date[:10] if fvg.date else "—",
            "Status":   "✅ Open" if not fvg.filled else "🔵 Filled",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Fair value gaps are price imbalances where a candle's body doesn't overlap the "
        "adjacent candles. Price frequently returns to fill these gaps."
    )


def _render_structure_table(structure):
    if not structure:
        st.info("No structure events detected. Try increasing the lookback period.")
        return

    rows = []
    for pt in reversed(structure[-20:]):
        kind_map = {
            "BOS_bull":   ("🟢 BOS ↑",   "Break of Structure — bullish continuation"),
            "BOS_bear":   ("🔴 BOS ↓",   "Break of Structure — bearish continuation"),
            "CHoCH_bull": ("🟡 CHoCH ↑", "Change of Character — potential reversal up"),
            "CHoCH_bear": ("🟠 CHoCH ↓", "Change of Character — potential reversal down"),
        }
        label, desc = kind_map.get(pt.kind, (pt.kind, ""))
        rows.append({
            "Event":       label,
            "Price":       f"${pt.price:,.2f}",
            "Date":        pt.date[:10] if pt.date else "—",
            "Description": desc,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "BOS = Break of Structure (trend continuation). "
        "CHoCH = Change of Character (potential trend reversal)."
    )
