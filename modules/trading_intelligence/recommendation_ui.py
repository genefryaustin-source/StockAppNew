from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.portfolio.accounting_service import AccountingService
from modules.portfolio.order_service import OrderService
from modules.trading_intelligence.recommendation_orchestrator import RecommendationOrchestrator


def _format_money(value):
    try:
        if value is None:
            return "—"
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def render_trade_recommendation_center(
    db_session,
    market_data_service,
    portfolio_id: str,
    tenant_id: str | None,
    user_id: int | None = None,
):
    st.subheader("AI Stock Trade Recommendations")
    st.caption(
        "Orchestrates existing rankings, AI ranking, Smart Money, opportunity detection, and portfolio sizing into executable paper-trade ideas."
    )

    engine = RecommendationOrchestrator(
        db=db_session,
        tenant_id=tenant_id,
        portfolio_id=str(portfolio_id),
    )

    try:
        engine.ensure_schema()
    except Exception as e:
        st.error(f"Recommendation schema unavailable: {e}")
        return

    c1, c2, c3, c4 = st.columns(4)
    top_n = c1.number_input("Recommendations to show", min_value=5, max_value=100, value=25, step=5)
    min_score = c2.slider("Minimum conviction", min_value=0, max_value=100, value=70, step=5)
    risk_budget = c3.slider("Risk per trade", min_value=0.25, max_value=5.0, value=1.0, step=0.25, format="%.2f%%")
    max_alloc = c4.slider("Max allocation", min_value=1.0, max_value=25.0, value=10.0, step=1.0, format="%.0f%%")

    include_existing = st.checkbox(
        "Include symbols already held",
        value=False,
        key=f"trade_rec_include_existing_{portfolio_id}",
    )

    sector_relative = st.checkbox(
        "Use sector-relative ranking",
        value=False,
        key=f"trade_rec_sector_relative_{portfolio_id}",
    )

    scan_clicked = st.button(
        "Scan Stocks for Paper Trade Ideas",
        key=f"scan_trade_recommendations_{portfolio_id}",
        type="primary",
    )

    session_key = f"trade_recs_df_{portfolio_id}"

    if session_key not in st.session_state:
        st.session_state[session_key] = pd.DataFrame()

    if scan_clicked:

        try:

            cash = float(
                AccountingService(db_session).get_cash_balance(
                    portfolio_id
                ) or 0.0
            )

            with st.spinner(
                    "Scanning market for trade ideas..."
            ):

                recs = engine.generate_recommendations(
                    top_n=int(top_n),
                    min_score=float(min_score),
                    include_existing_positions=bool(include_existing),
                    cash_balance=cash,
                    risk_budget_pct=float(risk_budget),
                    max_position_pct=float(max_alloc),
                    sector_relative=bool(sector_relative),
                )

            if recs:
                engine.save_recommendations(
                    recs,
                    user_id=user_id,
                )

                df = pd.DataFrame(
                    [r.to_dict() for r in recs]
                )

            else:
                df = pd.DataFrame()

            st.session_state[session_key] = df

        except Exception as e:

            try:
                db_session.rollback()
            except Exception:
                pass

            st.error(
                f"Recommendation scan failed: {e}"
            )

            return

    df = st.session_state[session_key]


    if df is None or df.empty:
        st.info("No recommendations matched the current filters. Run analytics refresh or lower the minimum conviction.")
        _render_recent_history(engine)
        return

    display_cols = [
        "symbol", "recommendation", "conviction_score", "confidence_score",
        "current_price", "entry_price", "stop_price", "target_price",
        "risk_reward", "suggested_qty", "estimated_risk_dollars",
        "sector", "signal", "rationale",
    ]
    show = df[[c for c in display_cols if c in df.columns]].copy()
    show = show.rename(columns={
        "symbol": "Symbol",
        "recommendation": "Action",
        "conviction_score": "Conviction",
        "confidence_score": "Confidence",
        "current_price": "Current",
        "entry_price": "Entry",
        "stop_price": "Stop",
        "target_price": "Target",
        "risk_reward": "Risk/Reward",
        "suggested_qty": "Suggested Qty",
        "estimated_risk_dollars": "Est. Risk $",
        "sector": "Sector",
        "signal": "Signal",
        "rationale": "Rationale",
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

    tradable = df[(df["recommendation"].isin(["STRONG_BUY", "BUY"])) & (df["suggested_qty"] > 0)].copy()
    if tradable.empty:
        st.warning("No BUY recommendation currently has a valid suggested quantity. Check cash, price data, and risk settings.")
        _render_recent_history(engine)
        return

    symbol_options = tradable["symbol"].tolist()
    selected_symbol = st.selectbox(
        "Select recommendation to paper trade",
        options=symbol_options,
        key=f"selected_trade_recommendation_{portfolio_id}",
    )

    rec = tradable[tradable["symbol"] == selected_symbol].iloc[0].to_dict()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Action", rec.get("recommendation", "—"))
    m2.metric("Conviction", f"{float(rec.get('conviction_score', 0)):,.1f}")
    m3.metric("Entry", _format_money(rec.get("entry_price")))
    m4.metric("Stop", _format_money(rec.get("stop_price")))
    m5.metric("Target", _format_money(rec.get("target_price")))

    st.write(rec.get("rationale", ""))
    warnings = rec.get("warnings") or []
    if isinstance(warnings, list) and warnings:
        st.warning(" | ".join(warnings))

    q1, q2, q3 = st.columns(3)
    default_qty = max(1.0, float(rec.get("suggested_qty") or 1.0))
    qty = q1.number_input(
        "Paper trade quantity",
        min_value=1.0,
        value=float(default_qty),
        step=1.0,
        key=f"trade_rec_qty_{portfolio_id}_{selected_symbol}",
    )
    order_type = q2.selectbox(
        "Order type",
        options=["market", "limit"],
        index=0,
        key=f"trade_rec_order_type_{portfolio_id}_{selected_symbol}",
    )
    limit_price = q3.number_input(
        "Limit price",
        min_value=0.0,
        value=float(rec.get("entry_price") or rec.get("current_price") or 0.0),
        step=0.01,
        key=f"trade_rec_limit_{portfolio_id}_{selected_symbol}",
    )

    execute = st.button(
        f"Execute Paper Trade: BUY {selected_symbol}",
        key=f"execute_trade_recommendation_{portfolio_id}_{selected_symbol}",
    )

    if execute:
        try:
            service = OrderService(db_session, broker=None, market_data_service=market_data_service)
            execution_price = float(
                rec.get("entry_price")
                or rec.get("current_price")
                or limit_price
                or 0.0
            )

            order = service.submit_order(
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=selected_symbol,
                side="buy",
                qty=float(qty),
                order_type=order_type,
                tif="day",

                # Always provide a valid reference price
                limit_price=execution_price if execution_price > 0 else None,

                stop_price=None,
            )
            engine.mark_executed(selected_symbol, int(order.id))
            st.success(
                f"Paper trade submitted: BUY {order.qty:g} {order.symbol} at avg fill {order.avg_fill_price}."
            )
            st.rerun()
        except Exception as e:
            st.error(f"Failed to execute recommendation: {e}")

    _render_recent_history(engine)


def _render_recent_history(engine):
    with st.expander("Recent Recommendation History", expanded=False):
        try:
            hist = engine.load_recent_recommendations(limit=50)
            if hist.empty:
                st.caption("No saved recommendations yet.")
                return
            cols = [
                "created_at", "symbol", "recommendation", "conviction_score",
                "entry_price", "stop_price", "target_price", "suggested_qty",
                "executed", "executed_order_id", "rationale",
            ]
            st.dataframe(hist[[c for c in cols if c in hist.columns]], use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"Recommendation history unavailable: {e}")
