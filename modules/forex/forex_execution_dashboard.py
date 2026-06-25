from __future__ import annotations

from typing import Any, Optional
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from modules.forex.forex_trading_engine import ForexTradingEngine, get_forex_trading_engine
except Exception:
    from forex_trading_engine import ForexTradingEngine, get_forex_trading_engine


def render_forex_execution_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    trading_engine: Optional[ForexTradingEngine] = None,
) -> None:
    engine = trading_engine or get_forex_trading_engine(
        tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db
    )

    st.title("Forex Execution Dashboard")
    workspace = st.radio(
        "Forex Execution Workspace",
        ["Submit Order", "Orders", "Trades", "Positions"],
        horizontal=True,
        key="forex_execution_workspace",
    )

    account_id = st.text_input("Forex Account ID", value="", key="forex_exec_account_id")

    if workspace == "Submit Order":
        c1, c2, c3 = st.columns(3)
        pair = c1.text_input("Order Pair", value="EUR/USD", key="forex_exec_pair")
        side = c2.selectbox("Order Side", ["BUY", "SELL"], key="forex_exec_side")
        order_type = c3.selectbox("Order Type", ["MARKET", "LIMIT", "STOP", "STOP_LIMIT", "TAKE_PROFIT"], key="forex_exec_order_type")

        c4, c5, c6 = st.columns(3)
        units = c4.number_input("Order Units", min_value=1.0, value=1000.0, step=100.0, key="forex_exec_units")
        limit_price = c5.number_input("Limit Price", min_value=0.0, value=0.0, step=0.0001, format="%.6f", key="forex_exec_limit")
        stop_price = c6.number_input("Stop Price", min_value=0.0, value=0.0, step=0.0001, format="%.6f", key="forex_exec_stop")

        target_price = st.number_input("Target Price", min_value=0.0, value=0.0, step=0.0001, format="%.6f", key="forex_exec_target")
        use_ai = st.checkbox("Attach AI Signal", value=True, key="forex_exec_use_ai")

        if st.button("Submit Forex Order", key="forex_exec_submit", use_container_width=True):
            if not account_id:
                st.error("Forex Account ID is required.")
            else:
                order = engine.submit_order(
                    account_id=account_id,
                    pair=pair,
                    side=side,
                    order_type=order_type,
                    units=units,
                    limit_price=limit_price or None,
                    stop_price=stop_price or None,
                    target_price=target_price or None,
                    use_ai=use_ai,
                )
                st.success(f"Order {order.status}")
                st.json(order.to_dict())

    elif workspace == "Orders":
        status = st.selectbox("Order Status", ["ALL", "PENDING", "SUBMITTED", "FILLED", "CANCELLED", "REJECTED"], key="forex_orders_status")
        if st.button("Load Orders", key="forex_orders_load"):
            rows = [o.to_dict() for o in engine.list_orders(account_id=account_id or None, status=status)]
            st.session_state["forex_orders_rows"] = rows
        df = pd.DataFrame(st.session_state.get("forex_orders_rows", []))
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not df.empty and "status" in df.columns:
            fig = px.histogram(df, x="status", title="Forex Orders by Status")
            st.plotly_chart(fig, use_container_width=True)

    elif workspace == "Trades":
        status = st.selectbox("Trade Status", ["ALL", "OPEN", "CLOSED"], key="forex_trades_status")
        if st.button("Load Trades", key="forex_trades_load"):
            rows = [t.to_dict() for t in engine.list_trades(account_id=account_id or None, status=status)]
            st.session_state["forex_trades_rows"] = rows
        df = pd.DataFrame(st.session_state.get("forex_trades_rows", []))
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif workspace == "Positions":
        if st.button("Sync Positions", key="forex_positions_sync"):
            if not account_id:
                st.error("Forex Account ID is required.")
            else:
                rows = engine.sync_positions(account_id=account_id)
                st.session_state["forex_positions_rows"] = rows
        df = pd.DataFrame(st.session_state.get("forex_positions_rows", []))
        st.dataframe(df, use_container_width=True, hide_index=True)


def render(**kwargs: Any) -> None:
    render_forex_execution_dashboard(**kwargs)
