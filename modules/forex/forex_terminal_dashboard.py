"""
modules/forex/forex_terminal_dashboard.py

Cycle-safe Streamlit terminal dashboard.

This file intentionally avoids importing forex_terminal_api at module import
time. It only performs lazy imports during render.
"""

from __future__ import annotations

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None


class ForexTerminalDashboard:
    def __init__(self, db=None, api=None):
        self.db = db
        self.api = api

    def _api(self):
        if self.api is not None:
            return self.api
        from modules.forex.forex_terminal_api import get_forex_terminal_api
        self.api = get_forex_terminal_api(db=self.db)
        return self.api

    def render(self, **kwargs):
        api = self._api()
        snapshot = api.get_terminal_snapshot(**kwargs)

        if st is None:
            return snapshot

        st.title("🌍 Forex Institutional Terminal")

        if st.button("Refresh", use_container_width=True):
            snapshot = api.refresh_terminal()

        workspace = st.radio(
            "Workspace",
            [
                "Command Center",
                "Trading Desk",
                "Portfolio",
                "Orders",
                "Risk",
                "Performance",
                "Journal",
                "AI Briefing",
                "Provider Health",
            ],
            horizontal=True,
        )

        trading_desk = snapshot.get("trading_desk", {}) if isinstance(snapshot, dict) else {}

        if workspace == "Command Center":
            st.json(snapshot.get("market_overview", snapshot) if isinstance(snapshot, dict) else snapshot)

        elif workspace == "Trading Desk":
            st.json(trading_desk or snapshot)

        elif workspace == "Portfolio":
            st.json(snapshot.get("portfolio", {}) if isinstance(snapshot, dict) else {})

        elif workspace == "Orders":
            open_orders = trading_desk.get("open_orders", [])
            filled_orders = trading_desk.get("filled_orders", [])
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Open Orders")
                st.dataframe(pd.DataFrame(open_orders) if pd else open_orders, use_container_width=True)
            with c2:
                st.subheader("Filled Orders")
                st.dataframe(pd.DataFrame(filled_orders) if pd else filled_orders, use_container_width=True)

        elif workspace == "Risk":
            st.json(trading_desk.get("risk", {}))

        elif workspace == "Performance":
            st.json(trading_desk.get("performance", {}))

        elif workspace == "Journal":
            st.json(trading_desk.get("journal", {}))

        elif workspace == "AI Briefing":
            st.json(snapshot.get("ai_briefing", {}) if isinstance(snapshot, dict) else {})

        elif workspace == "Provider Health":
            st.json(snapshot.get("provider_health", {}) if isinstance(snapshot, dict) else {})

        st.divider()
        if st.button("🛑 Emergency Stop", type="primary", use_container_width=True):
            st.warning(api.emergency_stop())

        return snapshot


_DASH = None


def get_forex_terminal_dashboard(db=None, api=None):
    global _DASH
    if _DASH is None or (db is not None and _DASH.db is None):
        _DASH = ForexTerminalDashboard(db=db, api=api)
    return _DASH


def render_forex_terminal_dashboard(db=None, **kwargs):
    return get_forex_terminal_dashboard(db=db).render(**kwargs)
