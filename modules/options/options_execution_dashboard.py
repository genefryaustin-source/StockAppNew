"""Streamlit dashboard for Phase 7 Autonomous Options Execution Fabric."""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_mission_control import build_mission_control
from modules.options.options_trade_playbook_engine import list_playbooks
from modules.options.options_autopilot import AUTOPILOT_LEVELS, autopilot_policy
from modules.options.options_trade_journal_ai import explain_execution_report


def _load_execution_report(ticker: str, paper: bool, autopilot_level: int, force_refresh: bool = False) -> dict[str, Any]:
    key = f"options_execution_report_{ticker.upper()}_{paper}_{autopilot_level}"
    if force_refresh or key not in st.session_state:
        with st.spinner(f"Building execution intelligence for {ticker.upper()}..."):
            st.session_state[key] = build_mission_control(ticker, paper=paper, autopilot_level=autopilot_level)
    return st.session_state[key]


def _df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def render_options_execution_dashboard(ticker: str, paper: bool = True):
    ticker = ticker.upper().strip()
    st.subheader(f"🚀 Execution Command Center — {ticker}")
    st.caption("Trade queue · signals · guardrails · playbooks · execution analytics · autopilot")

    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        refresh = st.button("↺ Refresh", key=f"execution_refresh_{ticker}", use_container_width=True)
    with c2:
        level = st.selectbox(
            "Autopilot Level",
            list(AUTOPILOT_LEVELS.keys()),
            format_func=lambda x: f"Level {x} — {AUTOPILOT_LEVELS[x]}",
            index=1,
            key=f"execution_autopilot_level_{ticker}",
        )
    with c3:
        st.info("Live execution is disabled by default. Phase 7 queues and audits candidates unless you explicitly wire broker execution.")

    report = _load_execution_report(ticker, paper=paper, autopilot_level=int(level), force_refresh=refresh)
    watch = report.get("watchtower", {})
    signals = report.get("signals", {})
    queue = report.get("trade_queue", [])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Signal Score", f"{signals.get('combined_signal_score', 50)}")
    m2.metric("Direction", signals.get("direction", "Neutral"))
    m3.metric("Queued", watch.get("queued_trades", len(queue)))
    m4.metric("Approved", watch.get("approved_trades", 0))
    m5.metric("Blocked", watch.get("blocked_trades", 0))

    tabs = st.tabs([
        "🎯 Trade Queue",
        "📡 Signals",
        "⚡ Execution",
        "🔔 Alerts",
        "📖 Playbooks",
        "🛡 Guardrails",
        "📊 Analytics",
        "🤖 Autopilot",
    ])

    with tabs[0]:
        st.markdown("#### Recommended / Queued Trades")
        if queue:
            rows = []
            for q in queue:
                rows.append({
                    "Strategy": q.get("strategy"),
                    "Playbook": q.get("playbook"),
                    "Confidence": q.get("confidence"),
                    "Optimizer": q.get("optimizer_score"),
                    "Max Loss": q.get("max_loss"),
                    "Status": q.get("guardrail_status"),
                    "Failures": q.get("guardrail_failures"),
                    "Order Quality": (q.get("order_quality") or {}).get("order_quality_score"),
                    "Route": (q.get("order_ticket") or {}).get("route"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No trade candidates generated.")

    with tabs[1]:
        st.markdown("#### Signal Stack")
        cols = st.columns(4)
        cols[0].metric("Smart Money", signals.get("smart_money_score", "—"))
        cols[1].metric("Dealer", signals.get("dealer_score", "—"))
        cols[2].metric("Volatility", signals.get("volatility_score", "—"))
        cols[3].metric("Combined", signals.get("combined_signal_score", "—"))
        st.json(signals)

    with tabs[2]:
        st.markdown("#### Execution Routes")
        routes = report.get("routes", [])
        if routes:
            display = []
            for r in routes:
                display.append({
                    "Route ID": r.get("route_id"),
                    "Strategy": r.get("strategy"),
                    "Route": r.get("route"),
                    "Status": r.get("status"),
                    "Paper": r.get("paper"),
                    "Created": r.get("created_at"),
                })
            st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
        else:
            st.info("Autopilot level does not currently route trades.")

    with tabs[3]:
        st.markdown("#### Execution Alerts")
        st.dataframe(_df(report.get("alerts", [])), use_container_width=True, hide_index=True)

    with tabs[4]:
        st.markdown("#### Playbook Library")
        st.dataframe(pd.DataFrame(list_playbooks()), use_container_width=True, hide_index=True)
        st.markdown("#### Selected Playbook")
        st.json(report.get("playbook", {}))

    with tabs[5]:
        st.markdown("#### Active Guardrails")
        st.json(report.get("guardrails", {}))
        blocked = [q for q in queue if q.get("guardrail_status") == "blocked"]
        if blocked:
            st.warning(f"{len(blocked)} trade candidate(s) blocked by guardrails.")
            st.dataframe(pd.DataFrame(blocked), use_container_width=True, hide_index=True)

    with tabs[6]:
        st.markdown("#### Execution Analytics")
        total = len(queue)
        approved = len([q for q in queue if q.get("guardrail_status") == "approved"])
        avg_conf = sum(float(q.get("confidence") or 0) for q in queue) / max(1, total)
        avg_quality = sum(float((q.get("order_quality") or {}).get("order_quality_score") or 0) for q in queue) / max(1, total)
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Candidates", total)
        a2.metric("Approval Rate", f"{approved / max(1, total):.0%}")
        a3.metric("Avg Confidence", f"{avg_conf:.1f}")
        a4.metric("Avg Order Quality", f"{avg_quality:.1f}")
        st.info(explain_execution_report(report))

    with tabs[7]:
        st.markdown("#### Autopilot Policy")
        st.json(autopilot_policy(int(level)))
        st.markdown("#### Levels")
        st.dataframe(pd.DataFrame([{"Level": k, "Mode": v} for k, v in AUTOPILOT_LEVELS.items()]), use_container_width=True, hide_index=True)
