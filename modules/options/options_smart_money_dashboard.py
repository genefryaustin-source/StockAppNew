"""
modules/options/options_smart_money_dashboard.py

Phase 1 Options Smart Money Center UI.

Renders:
- Whale Orders
- Sweep Activity
- Premium Flow
- Institutional Sentiment
- Top Contracts
- Conviction Tracker
- AI Smart Money Commentary

Uses the Phase 1 smart-money engine and existing options_flow service.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from modules.options.options_refresh_framework import render_refresh_controls

try:
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False


def _money(value: Any) -> str:
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}${v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:.1f}K"
    return f"{sign}${v:,.0f}"


def _pct(value: Any) -> str:
    try:
        v = float(value or 0)
        if abs(v) <= 1:
            return f"{v:.1%}"
        return f"{v:.1f}%"
    except Exception:
        return "—"


def _as_frame(rows: list[dict[str, Any]] | None, preferred: list[str] | None = None) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if preferred:
        cols = [c for c in preferred if c in df.columns]
        extras = [c for c in df.columns if c not in cols]
        df = df[cols + extras[:8]]
    return df


def _format_flow_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in ["premium_est", "call_premium", "put_premium", "net_premium", "total_premium"]:
        if col in out.columns:
            out[col] = out[col].apply(_money)
    for col in ["call_premium_pct", "put_premium_pct", "call_pct", "put_pct"]:
        if col in out.columns:
            out[col] = out[col].apply(_pct)
    return out


def _load_report(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"options_smart_money_report_{ticker.upper()}"
    if force_refresh and cache_key in st.session_state:
        del st.session_state[cache_key]
    if cache_key not in st.session_state:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        with st.spinner(f"Building smart money report for {ticker.upper()}…"):
            st.session_state[cache_key] = build_options_smart_money_report(ticker)
    return st.session_state[cache_key]


def render_options_smart_money_dashboard(ticker: str):
    """Render the Phase 1 Options Smart Money Center."""
    st.subheader(f"🐋 Options Smart Money Center — {ticker.upper()}")
    st.caption("Whale flow · sweep activity · premium imbalance · institutional sentiment · conviction scoring")

    refresh_state = render_refresh_controls(
        "options_smart_money",
        ticker if "ticker" in locals() else clean_ticker if "clean_ticker" in locals() else "",
        cache_prefixes=['options_smart_money_report_', 'ai_smart_money_commentary_'],
        default_mode="1 Minute",
    )


    c_refresh, c_note = st.columns([1, 5])
    with c_refresh:
        refresh = st.button("↺ Refresh", key=f"smart_money_refresh_main_{ticker.upper()}", use_container_width=True)
    with c_note:
        st.caption("Uses existing MarketData/Finnhub options-chain data and FINRA/proxy dark-pool intelligence when available.")

    report = _load_report(ticker, force_refresh=refresh)
    if report.get("error"):
        st.error(report.get("error"))
        with st.expander("Debug payload", expanded=False):
            st.json(report)
        return

    flow = report.get("flow", {}) or {}
    sentiment = report.get("sentiment", {}) or {}
    conviction = report.get("conviction_score", {}) or {}
    whale_summary = report.get("whale_summary", {}) or {}
    sweep_summary = report.get("sweep_summary", {}) or {}
    dark_pool = report.get("dark_pool", {}) or {}

    top = st.columns(6)
    top[0].metric("Sentiment", sentiment.get("label", "Neutral"), f"{sentiment.get('score', 50)}/100")
    top[1].metric("Conviction", conviction.get("label", "Low"), f"{conviction.get('score', 0)}/100")
    top[2].metric("Net Premium", _money(flow.get("net_premium")))
    top[3].metric("Call Premium", _money(flow.get("call_premium")))
    top[4].metric("Put Premium", _money(flow.get("put_premium")))
    top[5].metric("Whales / Sweeps", f"{whale_summary.get('whale_count', 0)} / {sweep_summary.get('sweep_count', 0)}")

    smart_tabs = st.tabs([
        "🐋 Whales",
        "⚡ Sweeps",
        "💰 Premium Flow",
        "📈 Institutional",
        "🎯 Top Contracts",
        "🔥 Conviction",
        "🤖 AI Read",
    ])

    with smart_tabs[0]:
        st.markdown("#### Whale / Block Activity")
        whales = report.get("whales", []) or []
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Whale Count", whale_summary.get("whale_count", len(whales)))
        c2.metric("Call Whales", whale_summary.get("call_whales", 0))
        c3.metric("Put Whales", whale_summary.get("put_whales", 0))
        c4.metric("Whale Premium", _money(whale_summary.get("total_premium", 0)))
        df = _as_frame(whales, ["ticker", "type", "expiry", "strike", "whale_class", "whale_score", "premium_fmt", "premium_est", "volume", "open_interest", "vol_oi_ratio", "direction"])
        if df.empty:
            st.info("No whale or block activity detected from the current unusual-contract set.")
        else:
            st.dataframe(_format_flow_table(df), use_container_width=True, hide_index=True)

    with smart_tabs[1]:
        st.markdown("#### Sweep / Aggressive Flow Activity")
        sweeps = report.get("sweeps", []) or []
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sweep Count", sweep_summary.get("sweep_count", len(sweeps)))
        c2.metric("Call Sweeps", sweep_summary.get("call_sweeps", 0))
        c3.metric("Put Sweeps", sweep_summary.get("put_sweeps", 0))
        c4.metric("Sweep Premium", _money(sweep_summary.get("total_premium", 0)))
        df = _as_frame(sweeps, ["ticker", "type", "expiry", "strike", "sweep_type", "sweep_score", "premium_fmt", "premium_est", "volume", "open_interest", "vol_oi_ratio", "opening_flow", "direction"])
        if df.empty:
            st.info("No sweep candidates detected at current thresholds.")
        else:
            st.dataframe(_format_flow_table(df), use_container_width=True, hide_index=True)

    with smart_tabs[2]:
        st.markdown("#### Premium Flow")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Premium", _money(flow.get("total_premium")))
        c2.metric("Net Premium", _money(flow.get("net_premium")))
        c3.metric("Call %", _pct(flow.get("call_premium_pct")))
        c4.metric("Put %", _pct(flow.get("put_premium_pct")))
        c5.metric("Bias", flow.get("bias", flow.get("net_sentiment", "Neutral")))

        exp_df = pd.DataFrame(report.get("premium_by_expiry") or [])
        strike_df = pd.DataFrame(report.get("premium_by_strike") or [])
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("##### By Expiration")
            if exp_df.empty:
                st.info("No expiration premium breakdown available.")
            else:
                st.dataframe(_format_flow_table(exp_df), use_container_width=True, hide_index=True)
        with c_right:
            st.markdown("##### By Strike")
            if strike_df.empty:
                st.info("No strike premium breakdown available.")
            else:
                st.dataframe(_format_flow_table(strike_df.head(30)), use_container_width=True, hide_index=True)

    with smart_tabs[3]:
        st.markdown("#### Institutional Sentiment")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score", f"{sentiment.get('score', 50)}/100")
        c2.metric("Label", sentiment.get("label", "Neutral"))
        c3.metric("Confidence", f"{sentiment.get('confidence', 0)}%")
        c4.metric("Dark Pool", dark_pool.get("signal", dark_pool.get("source", "Unavailable")))
        components = sentiment.get("components") or sentiment.get("drivers") or {}
        if components:
            st.markdown("##### Score Components")
            st.json(components)
        st.markdown("##### Dark Pool / Institutional Proxy")
        st.json(dark_pool)
        insiders = report.get("insiders") or []
        if insiders:
            with st.expander("Insider Transactions", expanded=False):
                st.dataframe(pd.DataFrame(insiders), use_container_width=True, hide_index=True)

    with smart_tabs[4]:
        st.markdown("#### Top Contracts by Premium")
        df = _as_frame(report.get("top_contracts", []), ["ticker", "type", "expiry", "strike", "premium_fmt", "premium_est", "volume", "open_interest", "vol_oi_ratio", "iv_pct", "otm_pct", "sentiment"])
        if df.empty:
            st.info("No unusual contracts available.")
        else:
            st.dataframe(_format_flow_table(df), use_container_width=True, hide_index=True)

    with smart_tabs[5]:
        st.markdown("#### Conviction Tracker")
        score = float(conviction.get("score", 0) or 0)
        label = conviction.get("label", "Low")
        st.progress(min(100, max(0, int(score))))
        st.metric("Institutional Conviction", f"{score:.1f}/100", label)
        drivers = conviction.get("drivers", {}) or {}
        if drivers:
            st.markdown("##### Drivers")
            st.json(drivers)
        if score >= 80:
            st.success("Very high conviction flow. Confirm liquidity, event risk, and whether the flow is opening or closing before acting.")
        elif score >= 62:
            st.info("High conviction flow. Monitor follow-through, price reaction, and repeated prints at similar strikes.")
        elif score >= 40:
            st.warning("Moderate conviction. Flow is notable but not decisive by itself.")
        else:
            st.info("Low conviction. No strong institutional options signal detected from current inputs.")

    with smart_tabs[6]:
        st.markdown("#### AI Smart Money Read")
        if st.button("Generate AI Smart Money Commentary", key=f"ai_smart_money_{ticker}", type="primary"):
            from modules.options.options_smart_money_ai import explain_smart_money_report
            with st.spinner("Generating institutional flow commentary…"):
                st.session_state[f"ai_smart_money_commentary_{ticker}"] = explain_smart_money_report(report)
        text = st.session_state.get(f"ai_smart_money_commentary_{ticker}")
        if text:
            st.info(text)
        else:
            st.caption("Click the button to generate an AI explanation of the smart-money report.")
