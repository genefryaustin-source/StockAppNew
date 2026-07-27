
from __future__ import annotations
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_covered_call_factory_engine import (
    build_covered_call_candidates,
    summarize_covered_call_factory,
)

def render_covered_call_factory_dashboard(
    ticker="",
    paper=True,
):
    st.subheader("🏭 Covered Call Factory")

    positions = load_portfolio_positions(
        ticker=ticker,
        paper=paper,
    )

    report = build_covered_call_candidates(
        positions=positions,
    )

    if not report.get("available"):
        st.info(report.get("reason"))
        return report

    st.info(
        summarize_covered_call_factory(report)
    )

    st.metric(
        "Covered Call Candidates",
        report.get("candidate_count", 0)
    )

    st.dataframe(
        report["candidates"],
        use_container_width=True,
        hide_index=True,
    )

    return report
