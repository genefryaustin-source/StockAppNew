"""
Sprint 4 Phase 5 — Institutional Strategy Factory Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_intelligence_dashboard import build_options_intelligence_report
from modules.options.options_flow_regime_engine import build_flow_regime_report
from modules.options.options_market_maker_pressure_engine import build_market_maker_pressure_report
from modules.options.options_volatility_intelligence_engine import build_volatility_intelligence_report
from modules.options.options_trade_factory import build_trade_factory_report
from modules.options.options_trade_ranking_engine import ranked_candidates_frame


def _extract_chain_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    if isinstance(payload, dict):
        return payload
    return None


def render_strategy_factory_dashboard(
    ticker: str,
    chain_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader(f"🏭 Institutional Strategy Factory — {ticker.upper()}")
    st.caption("Synthesizes intelligence, flow, market-maker, and volatility regimes into ranked trade ideas")

    if chain_data is None:
        with st.spinner(f"Loading options chain for {ticker.upper()}…"):
            chain_data = get_options_chain(ticker)

    chain_data = _extract_chain_payload(chain_data)

    if not chain_data or chain_data.get("error"):
        st.error((chain_data or {}).get("error", f"No chain data available for {ticker.upper()}"))
        return {}

    max_candidates = st.slider(
        "Max trade candidates",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        key=f"strategy_factory_max_{ticker.upper()}",
    )

    with st.spinner("Building institutional strategy factory report…"):
        intelligence = build_options_intelligence_report(ticker, chain_data)
        flow = build_flow_regime_report(chain_data.get("all_rows"), min_volume=100)
        market_maker = build_market_maker_pressure_report(chain_data)
        volatility = build_volatility_intelligence_report(chain_data)

        report = build_trade_factory_report(
            ticker=ticker,
            chain_data=chain_data,
            intelligence_report=intelligence,
            flow_report=flow,
            market_maker_report=market_maker,
            volatility_report=volatility,
            max_candidates=max_candidates,
        )

    bias = report.get("bias", {})
    top = report.get("top_trade") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Directional Bias", bias.get("bias", "—"))
    c2.metric("Direction Score", f"{bias.get('direction_score', 0)}/100")
    c3.metric("Top Grade", top.get("grade", "—"))
    c4.metric("Top Score", f"{top.get('rank_score', 0)}/100" if top else "—")

    st.markdown("#### Factory Summary")
    st.info(report.get("summary", "No summary available."))

    if bias.get("reasons"):
        st.markdown("#### Bias Drivers")
        for reason in bias["reasons"]:
            st.markdown(f"- {reason}")

    st.markdown("#### Ranked Institutional Trade Ideas")
    candidates = report.get("candidates", [])
    table = ranked_candidates_frame(candidates)
    if not table.empty:
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.warning("No trade candidates generated.")

    with st.expander("Top Trade Template", expanded=True):
        templates = report.get("templates", [])
        if templates:
            st.json(templates[0])
        else:
            st.caption("No template available.")

    with st.expander("All Strategy Templates", expanded=False):
        templates = report.get("templates", [])
        if templates:
            for i, template in enumerate(templates[:10], 1):
                st.markdown(f"**{i}. {template.get('strategy')} — {template.get('direction')}**")
                st.json(template)
        else:
            st.caption("No templates available.")

    return report
