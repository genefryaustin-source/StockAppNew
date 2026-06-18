"""
Risk Limits & Portfolio Guardrails Dashboard.

Fixed to be self-contained:
- accepts ticker/paper/positions safely from options_ui.py
- loads positions when not passed in
- builds risk_report locally before evaluating guardrails
- preserves compatibility if a pre-built risk_report is passed through kwargs
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.options.options_risk_guardrails_engine import (
    evaluate_portfolio_guardrails,
)
from modules.options.options_portfolio_risk_engine import (
    build_portfolio_risk_report,
)
from modules.options.options_portfolio_engine import (
    load_portfolio_positions,
)


def _table(df: Any) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_risk_guardrails_dashboard(
    ticker: str | None = None,
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
    risk_report: dict[str, Any] | None = None,
    *args,
    **kwargs,
) -> dict[str, Any]:
    """
    Render portfolio guardrails.

    Supports both call styles:

        render_risk_guardrails_dashboard(ticker=ticker, paper=paper)

    and legacy/prebuilt-report style:

        render_risk_guardrails_dashboard(risk_report=report)
    """

    st.subheader("🛡 Risk Limits & Portfolio Guardrails")
    st.caption("Portfolio Greek limits · Guardrail breaches · Risk status")

    # Backward compatibility: allow risk_report to be supplied through kwargs.
    if risk_report is None:
        risk_report = kwargs.get("risk_report")

    # If caller did not provide a risk report, build it locally.
    if risk_report is None:
        if positions is None:
            try:
                with st.spinner("Loading options portfolio positions…"):
                    positions = load_portfolio_positions(
                        ticker=ticker or "",
                        paper=paper,
                    )
            except Exception as e:
                st.error(f"Unable to load portfolio positions: {e}")
                return {
                    "available": False,
                    "reason": str(e),
                    "passed": False,
                    "breaches": ["Unable to load portfolio positions."],
                    "breach_count": 1,
                    "risk_level": "UNKNOWN",
                }

        try:
            risk_report = build_portfolio_risk_report(positions)
        except Exception as e:
            st.error(f"Unable to build portfolio risk report: {e}")
            return {
                "available": False,
                "reason": str(e),
                "passed": False,
                "breaches": ["Unable to build portfolio risk report."],
                "breach_count": 1,
                "risk_level": "UNKNOWN",
            }

    if not risk_report or not risk_report.get("available", True):
        reason = (risk_report or {}).get("reason", "No portfolio risk report available.")
        st.info(reason)
        return {
            "available": False,
            "reason": reason,
            "passed": True,
            "breaches": [],
            "breach_count": 0,
            "risk_level": "UNKNOWN",
        }

    try:
        result = evaluate_portfolio_guardrails(risk_report)
    except Exception as e:
        st.error(f"Unable to evaluate portfolio guardrails: {e}")
        return {
            "available": False,
            "reason": str(e),
            "passed": False,
            "breaches": ["Guardrail evaluation failed."],
            "breach_count": 1,
            "risk_level": "UNKNOWN",
        }

    passed = bool(result.get("passed", False))
    breaches = result.get("breaches", []) or []
    breach_count = int(result.get("breach_count", len(breaches)))
    risk_level = result.get("risk_level", "UNKNOWN")

    c1, c2, c3 = st.columns(3)
    c1.metric("Guardrail Status", "Passed" if passed else "Breached")
    c2.metric("Breaches", breach_count)
    c3.metric("Risk Level", risk_level)

    if passed:
        st.success("All portfolio guardrails passed.")
    else:
        st.error(f"{breach_count} guardrail breach{'es' if breach_count != 1 else ''} detected.")

    if breaches:
        st.markdown("#### Active Breaches")
        for breach in breaches:
            st.warning(str(breach))
    else:
        st.markdown("#### Active Breaches")
        st.caption("No active guardrail breaches.")

    with st.expander("Portfolio Risk Report", expanded=False):
        st.json(
            {
                "risk_score": risk_report.get("risk_score"),
                "net_greeks": risk_report.get("net_greeks"),
                "available": risk_report.get("available", True),
            }
        )

        positions_df = risk_report.get("positions")
        _table(positions_df)

    return result
