"""
modules/options/options_volatility_dashboard.py

Phase 4 Volatility & Earnings Intelligence dashboard.
Integrates IV Rank, IV Percentile, term structure, skew, earnings move,
event pricing, and AI volatility commentary into the Options Workstation.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False

from modules.options.options_data_service import get_options_chain
from modules.options.options_volatility_surface_engine import build_volatility_surface
from modules.options.options_iv_rank_engine import calculate_iv_rank
from modules.options.options_iv_percentile_engine import calculate_iv_percentile
from modules.options.options_volatility_term_structure import analyze_term_structure
from modules.options.options_skew_analyzer import analyze_skew
from modules.options.options_earnings_volatility_engine import estimate_earnings_volatility
from modules.options.options_event_pricing_engine import classify_event_pricing
from modules.options.options_volatility_ai import explain_volatility_report


def _spot(data: dict[str, Any]) -> float:
    try:
        return float(data.get("spot") or data.get("underlying_price") or data.get("lastTradePrice") or 0.0)
    except Exception:
        return 0.0


def _load_report(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    key = f"phase4_vol_report_{ticker.upper()}"
    if force_refresh or key not in st.session_state:
        chain = get_options_chain(ticker)
        if "error" in chain:
            st.session_state[key] = {"ticker": ticker.upper(), "error": chain.get("error")}
            return st.session_state[key]
        spot = _spot(chain)
        surface = build_volatility_surface(chain)
        iv_rank = calculate_iv_rank(surface)
        iv_pct = calculate_iv_percentile(surface)
        term = analyze_term_structure(surface)
        skew = analyze_skew(surface, spot=spot)
        earnings = estimate_earnings_volatility(surface, spot=spot, days_to_event=7) if spot else {}
        event = classify_event_pricing(iv_rank, iv_pct, earnings, term, skew)
        st.session_state[key] = {
            "ticker": ticker.upper(),
            "spot": spot,
            "surface": surface,
            "iv_rank": iv_rank,
            "iv_percentile": iv_pct,
            "term_structure": term,
            "skew": skew,
            "earnings": earnings,
            "event_pricing": event,
        }
    return st.session_state[key]


def _fmt_pct(v: Any) -> str:
    try:
        if v is None:
            return "—"
        return f"{float(v):.1%}"
    except Exception:
        return "—"


def _fmt_num(v: Any, suffix: str = "") -> str:
    try:
        if v is None:
            return "—"
        return f"{float(v):,.1f}{suffix}"
    except Exception:
        return "—"


def render_options_volatility_dashboard(ticker: str):
    st.subheader(f"📊 Volatility & Earnings Intelligence — {ticker.upper()}")
    st.caption("IV rank · IV percentile · volatility surface · term structure · skew · earnings/event pricing · AI volatility read")

    c_refresh, c_note = st.columns([1, 5])
    with c_refresh:
        refresh = st.button("↺ Refresh", key=f"phase4_vol_refresh_{ticker.upper()}", use_container_width=True)
    with c_note:
        st.caption("Uses the existing options chain. Historical IV is approximated from current cross-sectional chain data unless you later wire a historical IV store.")

    report = _load_report(ticker, force_refresh=refresh)
    if report.get("error"):
        st.error(report["error"])
        return

    iv_rank = report.get("iv_rank", {})
    iv_pct = report.get("iv_percentile", {})
    term = report.get("term_structure", {})
    skew = report.get("skew", {})
    earnings = report.get("earnings", {})
    event = report.get("event_pricing", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Spot", f"${report.get('spot', 0):,.2f}")
    c2.metric("IV Rank", _fmt_num(iv_rank.get("iv_rank"), "%"), iv_rank.get("label"))
    c3.metric("IV Percentile", _fmt_num(iv_pct.get("iv_percentile"), "%"), iv_pct.get("label"))
    c4.metric("Term Regime", term.get("regime", "—"))
    c5.metric("Event Pricing", event.get("label", "—"))

    tabs = st.tabs([
        "📊 Overview",
        "📈 IV Rank & Percentile",
        "🧬 Surface",
        "📉 Term Structure",
        "⚡ Skew",
        "🎯 Earnings Vol",
        "📅 Event Pricing",
        "🤖 Vol AI",
    ])

    with tabs[0]:
        st.markdown("#### Volatility Regime Summary")
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Median IV", _fmt_pct((report.get("surface", {}).get("summary") or {}).get("median_iv")))
        o2.metric("Front IV", _fmt_pct(term.get("front_iv")))
        o3.metric("Back IV", _fmt_pct(term.get("back_iv")))
        o4.metric("Expected Event Move", _fmt_pct(earnings.get("expected_move_pct")))
        st.info(
            f"**Read:** {event.get('label', 'Balanced event pricing')} · "
            f"{term.get('regime', 'term structure unavailable')} · "
            f"{skew.get('label', 'skew unavailable')} · "
            f"{earnings.get('vol_crush_label', 'crush unavailable')}"
        )

    with tabs[1]:
        st.markdown("#### IV Rank & Percentile")
        st.json({"iv_rank": iv_rank, "iv_percentile": iv_pct})

    with tabs[2]:
        st.markdown("#### Volatility Surface")
        surface_rows = report.get("surface", {}).get("surface", [])
        if surface_rows:
            df = pd.DataFrame(surface_rows)
            show = [c for c in ["expiry", "dte", "strike", "type", "iv", "volume", "open_interest"] if c in df.columns]
            st.dataframe(df[show].sort_values(["dte", "strike", "type"]).head(500), use_container_width=True, hide_index=True)
            if PLOTLY and {"dte", "strike", "iv"}.issubset(df.columns):
                try:
                    piv = df.pivot_table(index="dte", columns="strike", values="iv", aggfunc="mean")
                    fig = go.Figure(go.Surface(z=(piv.values * 100), x=[str(x) for x in piv.columns], y=[str(y) for y in piv.index]))
                    fig.update_layout(height=430, title="IV Surface", scene=dict(xaxis_title="Strike", yaxis_title="DTE", zaxis_title="IV %"))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as exc:
                    st.info(f"Surface chart unavailable: {exc}")
        else:
            st.info("No surface rows available.")

    with tabs[3]:
        st.markdown("#### Volatility Term Structure")
        points = term.get("points", [])
        if points:
            df = pd.DataFrame(points)
            st.dataframe(df, use_container_width=True, hide_index=True)
            if PLOTLY and {"dte", "median_iv"}.issubset(df.columns):
                fig = go.Figure(go.Scatter(x=df["dte"], y=df["median_iv"] * 100, mode="lines+markers", name="Median IV"))
                fig.update_layout(height=360, title="Term Structure", xaxis_title="DTE", yaxis_title="Median IV %")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(term.get("error", "No term structure points available."))

    with tabs[4]:
        st.markdown("#### Skew Analysis")
        s1, s2, s3 = st.columns(3)
        s1.metric("Call Skew", _fmt_pct(skew.get("call_skew")))
        s2.metric("Put Skew", _fmt_pct(skew.get("put_skew")))
        s3.metric("Risk Reversal", _fmt_pct(skew.get("risk_reversal")))
        st.info(skew.get("label", "Skew unavailable"))
        rows = skew.get("strike_skew") or []
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tabs[5]:
        st.markdown("#### Earnings Volatility")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Event IV", _fmt_pct(earnings.get("event_iv")))
        e2.metric("Expected Move", f"${earnings.get('expected_earnings_move', 0):,.2f}")
        e3.metric("Move %", _fmt_pct(earnings.get("expected_move_pct")))
        e4.metric("Crush Risk", earnings.get("vol_crush_label", "—"))
        st.json(earnings)

    with tabs[6]:
        st.markdown("#### Event Pricing")
        st.metric("Pricing Read", event.get("label", "—"))
        st.markdown("**Recommended Strategy Families**")
        for s in event.get("recommended_strategies", []):
            st.markdown(f"- {s}")
        st.json(event.get("inputs", {}))

    with tabs[7]:
        st.markdown("#### AI Volatility Analysis")
        if st.button("Generate Volatility AI Read", key=f"phase4_vol_ai_{ticker.upper()}", type="primary"):
            st.session_state[f"phase4_vol_ai_text_{ticker.upper()}"] = explain_volatility_report(report)
        text = st.session_state.get(f"phase4_vol_ai_text_{ticker.upper()}")
        if text:
            st.markdown(text)
        else:
            st.info("Click the button to generate the volatility desk read.")
