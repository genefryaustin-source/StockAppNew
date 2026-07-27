
from __future__ import annotations

from typing import Any, Dict

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None


def _table(rows, height: int = 420):
    if st is None:
        return rows
    if pd is None:
        st.json(rows)
        return
    df = pd.DataFrame(rows or [])
    if df.empty:
        st.info("No rows available.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def render_forex_executive_decision_center(data: Dict[str, Any] | None = None, db=None):
    """
    Phase 19 workspace renderer.

    Add to forex_terminal_dashboard.py:

        "Executive Decision Center"

    and route:

        elif workspace == "Executive Decision Center":
            from modules.forex.forex_executive_decision_dashboard import render_forex_executive_decision_center
            render_forex_executive_decision_center(data, db=self.db)
    """
    data = data or {}

    if st is None:
        from modules.forex.forex_executive_command_center import get_forex_executive_command_center
        return get_forex_executive_command_center(db=db).dashboard(snapshot=data.get("raw_snapshot") or data)

    st.markdown("### 🏛️ Executive Decision Center")
    st.caption("Institutional decision support • paper-trading safe • no live broker execution")

    try:
        from modules.forex.forex_executive_command_center import get_forex_executive_command_center
        payload = get_forex_executive_command_center(db=db).dashboard(snapshot=data.get("raw_snapshot") or data)
    except Exception as exc:
        st.error(f"Executive Decision Center failed: {exc}")
        return

    summary = payload.get("executive_summary") or {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Decisions", summary.get("decision_count", 0))
    c2.metric("Approved", summary.get("approved_count", 0))
    c3.metric("Constraints", "PASS" if summary.get("portfolio_constraints_approved") else "REVIEW")
    c4.metric("Ops", summary.get("operations_status", "UNKNOWN"))
    top = summary.get("top_trade") or {}
    c5.metric("Top Trade", f"{top.get('pair', '-')} {top.get('side', '')}".strip())

    tabs = st.tabs([
        "Executive Summary",
        "Decision Engine",
        "Opportunity Scanner",
        "Risk Committee",
        "AI Deal Room",
        "Trade Queue",
        "Portfolio Constraints",
        "Real-Time Monitor",
        "Execution Readiness",
    ])

    with tabs[0]:
        st.json(summary)
    with tabs[1]:
        st.json(payload.get("decision_engine", {}))
    with tabs[2]:
        scanner = payload.get("opportunity_scanner", {})
        _table(scanner.get("opportunities", []))
        with st.expander("Opportunity Scanner Payload", expanded=False):
            st.json(scanner)
    with tabs[3]:
        committee = payload.get("risk_committee", {})
        rows = []
        for item in committee.get("reviews", []):
            trade = item.get("trade", {})
            review = item.get("risk_review", {})
            rows.append({
                "Pair": trade.get("pair"),
                "Side": trade.get("side"),
                "Decision": item.get("risk_committee_decision"),
                "Approved": review.get("approved"),
                "Errors": " | ".join(review.get("errors", [])),
                "Warnings": " | ".join(review.get("warnings", [])),
            })
        _table(rows)
        with st.expander("Risk Committee Payload", expanded=False):
            st.json(committee)
    with tabs[4]:
        deal_room = payload.get("ai_deal_room", {})
        rows = []
        for item in deal_room.get("reviews", []):
            trade = item.get("trade", {})
            vote = item.get("vote", {})
            rows.append({
                "Pair": trade.get("pair"),
                "Side": trade.get("side"),
                "Decision": vote.get("decision"),
                "Approvals": vote.get("approvals"),
                "Rejects": vote.get("rejects"),
                "Rationale": item.get("rationale"),
            })
        _table(rows)
        with st.expander("AI Deal Room Payload", expanded=False):
            st.json(deal_room)
    with tabs[5]:
        _table(payload.get("trade_queue", []), height=460)
    with tabs[6]:
        st.json(payload.get("portfolio_constraints", {}))
    with tabs[7]:
        st.json(payload.get("real_time_monitor", {}))
    with tabs[8]:
        st.json(payload.get("execution_readiness", {}))

    with st.expander("Full Executive Command Center Payload", expanded=False):
        st.json(payload)
