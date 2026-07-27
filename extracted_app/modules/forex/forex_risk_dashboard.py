from __future__ import annotations

from typing import Any, Optional
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from modules.forex.forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
except Exception:
    from forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine


def _df(rows: Any) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def render_forex_risk_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    portfolio_engine: Optional[ForexPortfolioEngine] = None,
) -> None:
    engine = portfolio_engine or get_forex_portfolio_engine(
        tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db
    )

    st.title("Forex Risk Dashboard")
    workspace = st.radio(
        "Forex Risk Workspace",
        ["Overview", "Exposure", "Margin", "Positions", "Sizing"],
        horizontal=True,
        key="forex_risk_workspace",
    )

    account_id = st.text_input("Forex Account ID", value="", key="forex_risk_account_id")

    if not account_id:
        st.info("Enter a Forex Account ID to load risk analytics.")
        return

    if workspace == "Overview":
        if st.button("Refresh Forex Risk", key="forex_risk_refresh"):
            risk = engine.calculate_risk(account_id=account_id)
            snapshot = engine.get_snapshot(account_id=account_id, persist=True, refresh=True)
            st.session_state["forex_risk_result"] = risk.to_dict()
            st.session_state["forex_risk_snapshot"] = snapshot.to_dict() if snapshot else {}

        risk = st.session_state.get("forex_risk_result")
        snapshot = st.session_state.get("forex_risk_snapshot")
        if risk:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Risk Score", risk.get("risk_score"))
            c2.metric("Exposure %", risk.get("exposure_pct"))
            c3.metric("Margin Used", risk.get("margin_used"))
            c4.metric("Margin Available", risk.get("margin_available"))
            if risk.get("warnings"):
                st.warning(risk.get("warnings"))
            st.json(risk)
        if snapshot:
            st.subheader("Portfolio Snapshot")
            st.json(snapshot)

    elif workspace == "Exposure":
        snapshot = engine.get_snapshot(account_id=account_id, persist=False, refresh=True)
        rows = snapshot.positions if snapshot else []
        df = _df(rows)
        if df.empty:
            st.info("No open Forex positions.")
        else:
            fig = px.bar(df, x="pair", y="notional_value", color="side", title="Notional Exposure by Pair")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif workspace == "Margin":
        snapshot = engine.get_snapshot(account_id=account_id, persist=False, refresh=True)
        if snapshot:
            c1, c2, c3 = st.columns(3)
            c1.metric("Equity", snapshot.equity)
            c2.metric("Margin Used", snapshot.margin_used)
            c3.metric("Margin Available", snapshot.margin_available)
            margin_df = pd.DataFrame([
                {"metric": "Used", "value": snapshot.margin_used},
                {"metric": "Available", "value": snapshot.margin_available},
            ])
            fig = px.pie(margin_df, names="metric", values="value", title="Margin Utilization")
            st.plotly_chart(fig, use_container_width=True)

    elif workspace == "Positions":
        positions = engine.list_positions(account_id=account_id, status="ALL")
        df = _df([p.to_dict() for p in positions])
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif workspace == "Sizing":
        pair = st.text_input("Sizing Pair", value="EUR/USD", key="forex_sizing_pair")
        entry = st.number_input("Entry Price", min_value=0.000001, value=1.10, step=0.0001, format="%.6f", key="forex_sizing_entry")
        stop = st.number_input("Stop Price", min_value=0.000001, value=1.09, step=0.0001, format="%.6f", key="forex_sizing_stop")
        risk_pct = st.slider("Risk Per Trade %", 0.1, 5.0, 2.0, 0.1, key="forex_sizing_risk_pct") / 100.0
        if st.button("Calculate Position Size", key="forex_sizing_button"):
            result = engine.position_size_from_risk(account_id=account_id, pair=pair, entry_price=entry, stop_price=stop, risk_pct=risk_pct)
            st.json(result)


def render(**kwargs: Any) -> None:
    render_forex_risk_dashboard(**kwargs)
