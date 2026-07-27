"""
Sprint 4 Phase 1 — Options Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_max_pain_engine import calculate_max_pain, summarize_max_pain
from modules.options.options_gamma_wall_engine import calculate_gamma_walls, summarize_gamma_walls
from modules.options.options_pin_risk_engine import calculate_pin_risk, summarize_pin_risk
from modules.options.options_expiration_pressure_engine import calculate_expiration_pressure, summarize_expiration_pressure
from modules.options.options_liquidity_engine import calculate_liquidity_score, summarize_liquidity


def _safe_metric_value(value: Any, money: bool = False) -> str:
    if value is None:
        return "—"
    try:
        if money:
            return f"${float(value):,.2f}"
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)
    except Exception:
        return str(value)


def build_options_intelligence_report(ticker: str, chain_data: dict[str, Any] | None = None, expiry: str | None = None) -> dict[str, Any]:
    if chain_data is None:
        chain_data = get_options_chain(ticker)

    expirations = chain_data.get("expirations", []) if chain_data else []
    selected_expiry = expiry or (expirations[0] if expirations else None)

    max_pain = calculate_max_pain(chain_data, selected_expiry)
    gamma = calculate_gamma_walls(chain_data, selected_expiry)
    pin = calculate_pin_risk(chain_data, selected_expiry)
    pressure = calculate_expiration_pressure(chain_data, selected_expiry)
    liquidity = calculate_liquidity_score(chain_data, selected_expiry)

    components = [max_pain, gamma, pin, pressure, liquidity]
    available_count = sum(1 for c in components if c.get("available"))

    liquidity_score = liquidity.get("liquidity_score") if liquidity.get("available") else 0
    pin_probability = pin.get("pin_probability", 0) * 100 if pin.get("available") else 0
    pressure_score = pressure.get("pressure_score", 50) if pressure.get("available") else 50

    institutional_score = round(
        (float(liquidity_score or 0) * 0.40)
        + (float(pin_probability or 0) * 0.25)
        + (abs(float(pressure_score or 50) - 50) * 2 * 0.20)
        + (available_count / len(components) * 100 * 0.15),
        2,
    )

    if institutional_score >= 75:
        grade = "INSTITUTIONAL"
    elif institutional_score >= 60:
        grade = "ACTIONABLE"
    elif institutional_score >= 45:
        grade = "WATCHLIST"
    else:
        grade = "LOW_QUALITY"

    return {
        "ticker": ticker.upper(),
        "expiry": selected_expiry,
        "chain_data": chain_data,
        "max_pain": max_pain,
        "gamma": gamma,
        "pin": pin,
        "pressure": pressure,
        "liquidity": liquidity,
        "institutional_score": institutional_score,
        "grade": grade,
        "summary": [
            summarize_max_pain(max_pain),
            summarize_gamma_walls(gamma),
            summarize_pin_risk(pin),
            summarize_expiration_pressure(pressure),
            summarize_liquidity(liquidity),
        ],
    }


def render_options_intelligence_dashboard(ticker: str, chain_data: dict[str, Any] | None = None) -> dict[str, Any]:
    st.subheader(f"🧠 Options Intelligence — {ticker.upper()}")
    st.caption("Max pain · Gamma walls · Pin risk · Expiration pressure · Liquidity quality")

    if chain_data is None:
        with st.spinner(f"Loading options chain for {ticker.upper()}…"):
            chain_data = get_options_chain(ticker)

    if not chain_data or chain_data.get("error"):
        st.error((chain_data or {}).get("error", f"No chain data available for {ticker.upper()}"))
        return {}

    expirations = chain_data.get("expirations", [])
    if not expirations:
        st.warning("No expirations available for options intelligence.")
        return {}

    expiry = st.selectbox("Expiration", expirations, index=0, key=f"options_intel_expiry_{ticker.upper()}")
    report = build_options_intelligence_report(ticker, chain_data, expiry)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Institutional Score", f"{report['institutional_score']}/100")
    c2.metric("Grade", report["grade"])
    c3.metric("Max Pain", _safe_metric_value(report["max_pain"].get("max_pain"), money=True))
    c4.metric("Pin Risk", report["pin"].get("risk_level", "—"))

    g1, g2, g3, g4 = st.columns(4)
    gamma = report["gamma"]
    pressure = report["pressure"]
    liquidity = report["liquidity"]
    g1.metric("Call Wall", _safe_metric_value(gamma.get("call_wall"), money=True))
    g2.metric("Put Wall", _safe_metric_value(gamma.get("put_wall"), money=True))
    g3.metric("Pressure", pressure.get("expiration_pressure", "—"))
    g4.metric("Liquidity", liquidity.get("spread_quality", "—"))

    st.markdown("#### Institutional Summary")
    for line in report["summary"]:
        st.markdown(f"- {line}")

    with st.expander("Gamma Walls", expanded=False):
        walls = gamma.get("top_gamma_walls")
        if isinstance(walls, pd.DataFrame) and not walls.empty:
            st.dataframe(walls, use_container_width=True, hide_index=True)
        else:
            st.caption("No gamma wall table available.")

    with st.expander("Pin Candidates", expanded=False):
        pins = report["pin"].get("top_pin_candidates")
        if isinstance(pins, pd.DataFrame) and not pins.empty:
            st.dataframe(pins, use_container_width=True, hide_index=True)
        else:
            st.caption("No pin candidate table available.")

    with st.expander("Max Pain Payout Table", expanded=False):
        payout = report["max_pain"].get("payout_table")
        if isinstance(payout, pd.DataFrame) and not payout.empty:
            st.dataframe(payout.head(25), use_container_width=True, hide_index=True)
        else:
            st.caption("No max pain payout table available.")

    return report
