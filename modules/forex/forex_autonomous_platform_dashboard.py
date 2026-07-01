"""
modules/forex/forex_autonomous_platform_dashboard.py

Phase 20H — Streamlit renderer helper for Autonomous Trading Platform.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None


def render_forex_autonomous_trading_platform(data: Dict[str, Any] | None = None, db=None):
    data = data or {}

    from modules.forex.forex_autonomous_command_center import get_forex_autonomous_command_center
    payload = get_forex_autonomous_command_center(db=db).dashboard(snapshot=data.get("raw_snapshot") or data)

    if st is None:
        return payload

    st.markdown("### 🤖 Autonomous Trading Platform")
    st.caption("Closed-loop institutional research and paper-trading orchestration. Live execution remains disabled.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mode", payload.get("mode", "UNKNOWN"))
    c2.metric("Live Execution", "OFF" if not payload.get("live_execution_enabled") else "ON")
    c3.metric("Status", payload.get("status", "UNKNOWN"))
    c4.metric("Generated", str(payload.get("generated_at", "-"))[-14:])

    tabs = st.tabs([
        "Autonomous Command Center",
        "Autonomous Strategies",
        "Learning Engine",
        "Execution Intelligence",
        "Portfolio Manager",
        "Performance Analytics",
        "Enterprise Operations",
    ])

    with tabs[0]:
        st.json(payload)
    with tabs[1]:
        st.json(payload.get("autonomous_strategies", {}))
    with tabs[2]:
        st.json(payload.get("learning_engine", {}))
    with tabs[3]:
        st.json(payload.get("execution_intelligence", {}))
    with tabs[4]:
        st.json(payload.get("portfolio_manager", {}))
    with tabs[5]:
        st.json(payload.get("performance_analytics", {}))
    with tabs[6]:
        st.json(payload.get("enterprise_operations", {}))

    return payload
