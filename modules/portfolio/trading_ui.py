from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from modules.portfolio import nav_service
from modules.portfolio.brokers.factory import get_broker
from modules.portfolio.order_service import OrderService
from modules.portfolio.execution_intelligence import (
    execution_risk_flags,
    suggest_order_strategy,
)
from modules.portfolio.accounting_service import AccountingService
from modules.portfolio.analytics_service import PortfolioAnalyticsService
from modules.portfolio.attribution_service import AttributionService
from modules.portfolio.risk_analytics_service import RiskAnalyticsService
from modules.portfolio.construction_service import PortfolioConstructionService
from modules.portfolio.alpha_engine import AlphaEngine
from modules.analytics.strategy_service import list_discovered_strategies
from modules.portfolio.strategy_bridge import StrategyBridge
from modules.portfolio.automation_service import PortfolioAutomationService
from modules.portfolio.strategy_run_service import StrategyRunService
from modules.portfolio.scheduler_service import PortfolioScheduler
from modules.portfolio.guardrail_service import GuardrailService
from modules.portfolio.alert_service import AlertService
from modules.portfolio.monitoring_service import MonitoringService
from modules.portfolio.strategy_allocator import StrategyAllocator
from modules.portfolio.strategy_decomposition_service import StrategyDecompositionService
from modules.portfolio.strategy_optimizer import StrategyWeightOptimizer
from modules.portfolio.constraint_optimizer import ConstraintAwareOptimizer
from modules.portfolio.live_intelligence_service import LivePortfolioIntelligenceService
from modules.portfolio.pm_command_center import render_pm_command_center
from modules.portfolio.strategy_ml_ranker import StrategyMLRanker
from modules.portfolio.event_engine import EventDrivenExecutionEngine
from modules.portfolio.event_processor import EventProcessor

from modules.api.api_ui import render_api_ui
from modules.portfolio.nav_service import NavService
import plotly.express as px
from modules.market_data.service import get_latest_price_map
from models.trading import (
    Portfolio,
    PortfolioPosition,
    TradeOrder,
    PortfolioCashLedger,
    PortfolioSnapshot,
    ClosedTrade,
)

try:
    from models.strategy_run import StrategyRun
except Exception:
    StrategyRun = None


# --------------------------
# Helper
# --------------------------

def _fetch_benchmark_history(symbol: str = "SPY", period: str = "6mo") -> pd.DataFrame:
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period=period)
        if hist is None or hist.empty:
            return pd.DataFrame()

        out = hist[["Close"]].copy()
        out = out.rename(columns={"Close": "Benchmark Close"})
        out.index = pd.to_datetime(out.index)
        out["Benchmark Return"] = out["Benchmark Close"].pct_change().fillna(0.0)
        out["Benchmark Cumulative Return"] = (1.0 + out["Benchmark Return"]).cumprod() - 1.0
        return out
    except Exception:
        return pd.DataFrame()


def _safe_price_from_quote(quote) -> float | None:
    if not isinstance(quote, dict):
        return None

    for key in ("price", "c", "last", "close", "regularMarketPrice"):
        value = quote.get(key)
        if value is not None:
            try:
                return float(value)
            except Exception:
                continue
    return None


# -------------------------
# Render
# -------------------------

def render_trading_ui(db_session, market_data_service, portfolio_id: int, user_id: int | None = None,
                      risk_report_df=None, alert_service=None):
    if user_id is None and st.session_state.get("user", {}).get("role") == "client":
        st.warning("Trading is disabled for client accounts.")
        return

    portfolio = (
        db_session.query(Portfolio)
        .filter(Portfolio.id == portfolio_id)
        .one_or_none()
    )

    if portfolio:
        st.caption(f"Active portfolio: {portfolio.name} ({getattr(portfolio, 'base_currency', 'USD')})")


        st.divider()
    st.subheader("Trading & Execution")

    trading_cfg = st.secrets.get("trading", {
        "DEFAULT_BROKER": "paper",
        "ENABLE_LIVE_TRADING": False,
    })

    accounting = AccountingService(db_session)
    accounting.ensure_seed_cash(portfolio_id)
    totals = accounting.record_snapshot(portfolio_id)

    col1, col2, col3 = st.columns(3)
    broker_name = col1.selectbox("Broker", ["paper", "alpaca"], index=0, key=f"broker_name_{portfolio_id}")
    enable_live = bool(trading_cfg.get("ENABLE_LIVE_TRADING", False))
    mode = col2.selectbox(
        "Mode",
        ["paper", "live"] if enable_live else ["paper"],
        index=0,
        key=f"broker_mode_{portfolio_id}",
    )
    live = mode == "live"

    if live:
        st.error("⚠️ LIVE TRADING ENABLED — REAL MONEY AT RISK")

    broker = get_broker(
        market_data_service=market_data_service,
        broker_name=broker_name,
        live=live,
    )

    try:
        buying_power = broker.get_buying_power()
        col3.metric("Broker Buying Power", f"${buying_power:,.2f}")
    except Exception as e:
        col3.warning(f"Buying power unavailable: {e}")

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Cash", f"${totals['cash']:,.2f}")
    s2.metric("Market Value", f"${totals['market_value']:,.2f}")
    s3.metric("Equity", f"${totals['equity']:,.2f}")
    s4.metric("Net P&L", f"${totals['net_pnl']:,.2f}")

    p1, p2 = st.columns(2)
    p1.metric("Realized P&L", f"${totals['realized_pnl']:,.2f}")
    p2.metric("Unrealized P&L", f"${totals['unrealized_pnl']:,.2f}")

    with st.form(f"trade_ticket_form_{portfolio_id}"):
        t1, t2, t3, t4 = st.columns(4)
        symbol = t1.text_input("Symbol", value="AAPL").upper().strip()
        side = t2.selectbox("Side", ["buy", "sell"])
        qty = t3.number_input("Qty", min_value=1.0, step=1.0, value=10.0)
        order_type = t4.selectbox("Order Type", ["market", "limit", "stop", "stop_limit"])

        t5, t6, t7 = st.columns(3)
        tif = t5.selectbox("Time in Force", ["day", "gtc"])
        limit_price = t6.number_input("Limit Price", min_value=0.0, value=0.0, step=0.01)
        stop_price = t7.number_input("Stop Price", min_value=0.0, value=0.0, step=0.01)

        limit_price = limit_price if limit_price > 0 else None
        stop_price = stop_price if stop_price > 0 else None

        spread_bps = None
        volatility_pct = None
        adv_ratio = None

        flags = execution_risk_flags(side, order_type, spread_bps, adv_ratio)
        suggestion = suggest_order_strategy(spread_bps, volatility_pct)

        if flags:
            st.warning(" | ".join(flags))
        st.info(suggestion)

        submitted = st.form_submit_button("Submit Order")

    if submitted:
        try:
            service = OrderService(db_session, broker, market_data_service)
            order = service.submit_order(
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type=order_type,
                tif=tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )
            st.success(
                f"Order submitted: {order.symbol} {order.side} {order.qty} "
                f"| status={order.status} | broker_order_id={order.broker_order_id}"
            )
            st.rerun()
        except Exception as e:
            st.error(f"Trade submission failed: {e}")

    st.markdown("### Equity Curve")
    snapshots = (
        db_session.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioSnapshot.as_of.asc())
        .all()
    )

    if snapshots:
        df_snap = pd.DataFrame([
            {
                "As Of": s.as_of,
                "Cash": s.cash,
                "Market Value": s.market_value,
                "Equity": s.equity,
                "Realized P&L": s.realized_pnl,
                "Unrealized P&L": s.unrealized_pnl,
                "Net P&L": s.net_pnl,
            }
            for s in snapshots
        ])
        df_chart = df_snap.set_index("As Of")[["Equity"]]
        st.line_chart(df_chart)
    else:
        df_snap = pd.DataFrame()
        st.caption("No portfolio snapshots yet.")

    st.markdown("### Open / Recent Orders")
    orders = (
        db_session.query(TradeOrder)
        .filter(TradeOrder.portfolio_id == portfolio_id)
        .order_by(TradeOrder.created_at.desc())
        .limit(200)
        .all()
    )

    if orders:
        df_orders = pd.DataFrame([
            {
                "Created": o.created_at,
                "Symbol": o.symbol,
                "Side": o.side,
                "Type": o.order_type,
                "Qty": o.qty,
                "Filled Qty": o.filled_qty,
                "Avg Fill": o.avg_fill_price,
                "Status": o.status,
                "Broker": o.broker,
                "Commission": o.actual_commission,
                "Slippage": o.actual_slippage,
            }
            for o in orders
        ])
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    else:
        df_orders = pd.DataFrame()
        st.caption("No orders yet.")

    st.markdown("### Current Positions")
    positions = (
        db_session.query(PortfolioPosition)
        .filter(PortfolioPosition.portfolio_id == portfolio_id)
        .order_by(PortfolioPosition.symbol.asc())
        .all()
    )

    if positions:
        df_pos = pd.DataFrame([
            {
                "Symbol": p.symbol,
                "Qty": p.qty,
                "Avg Cost": p.avg_cost,
                "Market Price": p.market_price,
                "Market Value": p.market_value,
                "Unrealized P&L": p.unrealized_pnl,
                "Realized P&L": p.realized_pnl,
                "Updated": p.updated_at,
            }
            for p in positions
        ])
        st.dataframe(df_pos, use_container_width=True, hide_index=True)
    else:
        df_pos = pd.DataFrame()
        st.caption("No positions yet.")

    st.markdown("### Cash Ledger")
    ledger = (
        db_session.query(PortfolioCashLedger)
        .filter(PortfolioCashLedger.portfolio_id == portfolio_id)
        .order_by(PortfolioCashLedger.created_at.desc())
        .limit(100)
        .all()
    )

    if ledger:
        df_ledger = pd.DataFrame([
            {
                "Created": x.created_at,
                "Type": x.entry_type,
                "Amount": x.amount,
                "Currency": getattr(x, "currency", "USD"),
                "Order ID": x.trade_order_id,
                "Notes": x.notes,
            }
            for x in ledger
        ])
        st.dataframe(df_ledger, use_container_width=True, hide_index=True)
    else:
        st.caption("No cash ledger entries yet.")

    st.markdown("### Closed Trades")
    closed_trades = (
        db_session.query(ClosedTrade)
        .filter(ClosedTrade.portfolio_id == portfolio_id)
        .order_by(ClosedTrade.closed_at.desc())
        .limit(200)
        .all()
    )

    if closed_trades:
        df_closed = pd.DataFrame([
            {
                "Closed At": x.closed_at,
                "Symbol": x.symbol,
                "Entry Qty": x.entry_qty,
                "Exit Qty": x.exit_qty,
                "Entry Price": x.entry_price,
                "Exit Price": x.exit_price,
                "Gross P&L": x.gross_pnl,
                "Net P&L": x.net_pnl,
                "Commission": x.commission,
                "Slippage": x.slippage,
                "Holding Period (Days)": x.holding_period_days,
                "Side Open": x.side_open,
                "Side Close": x.side_close,
                "Notes": x.notes,
            }
            for x in closed_trades
        ])
        st.dataframe(df_closed, use_container_width=True, hide_index=True)
    else:
        df_closed = pd.DataFrame()
        st.caption("No closed trades yet.")

    st.divider()
    st.header("Analytics")

    analytics = PortfolioAnalyticsService(
        df_snap if not df_snap.empty else None,
        df_closed if not df_closed.empty else None,
    )
    returns_df = analytics.prepare_snapshot_returns()
    stats = analytics.summary_stats(returns_df)
    concentration_df = analytics.position_concentration(df_pos if not df_pos.empty else None)
    exposure = analytics.exposure_stats(df_pos if not df_pos.empty else None)
    trade_stats = analytics.trade_stats(df_orders if not df_orders.empty else None)

    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Total Return", f"{stats['total_return']:.2%}")
    a2.metric("Annualized Return", f"{stats['annualized_return']:.2%}")
    a3.metric("Annualized Vol", f"{stats['annualized_volatility']:.2%}")
    a4.metric("Sharpe", f"{stats['sharpe']:.2f}")
    a5.metric("Max Drawdown", f"{stats['max_drawdown']:.2%}")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Gross Exposure", f"${exposure['gross_exposure']:,.2f}")
    b2.metric("Net Exposure", f"${exposure['net_exposure']:,.2f}")
    b3.metric("Long Exposure", f"${exposure['long_exposure']:,.2f}")
    b4.metric("Short Exposure", f"${exposure['short_exposure']:,.2f}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Orders", trade_stats["total_orders"])
    c2.metric("Filled", trade_stats["filled_orders"])
    c3.metric("Buys", trade_stats["buy_orders"])
    c4.metric("Sells", trade_stats["sell_orders"])
    c5.metric("Avg Slippage", f"${trade_stats['avg_slippage']:,.4f}")

    closed_stats = analytics.closed_trade_stats()

    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Closed Trades", closed_stats["closed_trades"])
    d2.metric("Wins", closed_stats["wins"])
    d3.metric("Losses", closed_stats["losses"])
    d4.metric("Win Rate", f"{closed_stats['win_rate']:.2%}")
    d5.metric("Profit Factor", f"{closed_stats['profit_factor']:.2f}")
    d6.metric("Expectancy", f"${closed_stats['expectancy']:,.2f}")

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Closed Gross P&L", f"${closed_stats['gross_pnl']:,.2f}")
    e2.metric("Closed Net P&L", f"${closed_stats['net_pnl']:,.2f}")
    e3.metric("Avg Winner", f"${closed_stats['avg_win']:,.2f}")
    e4.metric("Avg Loser", f"${closed_stats['avg_loss']:,.2f}")

    st.markdown("### Returns & Drawdown")
    if not returns_df.empty:
        st.line_chart(returns_df[["Cumulative Return", "Drawdown"]])
    else:
        st.caption("Not enough snapshot history for returns analytics yet.")

    # ---------------------------------
    # 📊 BENCHMARK (ALIGNED + FIXED)
    # ---------------------------------
    from sqlalchemy import text
    from modules.portfolio.nav_service import NavService
    import plotly.express as px

    st.divider()
    st.subheader("Benchmark Comparison")

    pnl_rows = db_session.execute(text("""
        SELECT closed_at, net_pnl
        FROM closed_trades
        WHERE portfolio_id = :pid
    """), {"pid": portfolio_id}).fetchall()

    # ✅ DO NOT RETURN — JUST INFORM
    if not pnl_rows:
        st.info("Benchmark comparison will appear once portfolio history builds up.")

    # ---------------------------------
    # EXISTING PANELS (KEEP)
    # ---------------------------------
    st.markdown("### Position Concentration")
    if not concentration_df.empty:
        show_cols = [c for c in ["Symbol", "Market Value", "Weight", "Unrealized P&L", "Realized P&L"] if
                     c in concentration_df.columns]
        st.dataframe(concentration_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.caption("No concentration data yet.")

    st.markdown("### Realized Attribution by Symbol")
    attrib = analytics.attribution_by_symbol()
    if not attrib.empty:
        st.dataframe(attrib, use_container_width=True, hide_index=True)
    else:
        st.caption("No realized attribution yet.")

    # ---------------------------------
    # 🔥 BENCHMARK LOAD + METRICS
    # ---------------------------------
    nav_service = NavService(db_session, market_data_service)

    bench = None
    benchmark_metrics = None

    try:
        bench = nav_service.get_benchmark_history(symbol="SPY", days=180)
        benchmark_metrics = nav_service.compute_benchmark_metrics(
            portfolio_id=portfolio_id,
            benchmark_symbol="SPY",
            days=180,
        )
    except Exception as e:
        print("Benchmark load error:", e)

    # ---------------------------------
    # 📈 BENCHMARK DISPLAY (FIXED)
    # ---------------------------------
    st.markdown("### Benchmark Attribution")

    if not benchmark_metrics:
        st.caption("Benchmark metrics unavailable (insufficient aligned history).")

    else:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Alpha (Ann.)", f"{benchmark_metrics['alpha'] * 100:.2f}%")
        c2.metric("Beta", f"{benchmark_metrics['beta']:.2f}")
        c3.metric("Tracking Error", f"{benchmark_metrics['tracking_error'] * 100:.2f}%")
        c4.metric("Relative Return", f"{benchmark_metrics['relative_return'] * 100:.2f}%")

        # ---------------------------------
        # 📊 PERFORMANCE CHART (ALIGNED)
        # ---------------------------------
        aligned_df = benchmark_metrics["aligned_df"].copy()

        chart_df = aligned_df[["Date", "cum_portfolio", "cum_benchmark", "active_return"]].rename(columns={
            "cum_portfolio": "Portfolio",
            "cum_benchmark": "Benchmark",
            "active_return": "Active Return",
        })

        fig = px.line(
            chart_df,
            x="Date",
            y=["Portfolio", "Benchmark", "Active Return"],
            title="Portfolio vs Benchmark (Aligned Returns)",
        )

        st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------
    # ATTRIBUTION
    # ---------------------------------
    attribution = AttributionService(
        positions_df=df_pos if df_pos is not None and not df_pos.empty else None,
        returns_df=returns_df if returns_df is not None and not returns_df.empty else None,
        benchmark_df=bench if bench is not None and not bench.empty else None,
        market_data_service=market_data_service,
    )


    st.subheader("Sector Exposure")
    sector_df = attribution.sector_exposure()
    if not sector_df.empty:
        st.dataframe(sector_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Sector data unavailable")

    st.subheader("Benchmark Attribution")

    if not benchmark_metrics:
        st.caption("Benchmark comparison will appear once enough aligned NAV history builds up.")
    else:
        b1, b2, b3, b4 = st.columns(4)

        b1.metric("Alpha (Ann.)", f"{benchmark_metrics['alpha'] * 100:.2f}%")
        b2.metric("Beta", f"{benchmark_metrics['beta']:.2f}")
        b3.metric("Tracking Error", f"{benchmark_metrics['tracking_error'] * 100:.2f}%")
        b4.metric("Relative Return", f"{benchmark_metrics['relative_return'] * 100:.2f}%")

        aligned_df = benchmark_metrics["aligned_df"].copy()

        chart_df = aligned_df[["Date", "cum_portfolio", "cum_benchmark", "active_return"]].copy()
        chart_df = chart_df.rename(columns={
            "cum_portfolio": "Portfolio",
            "cum_benchmark": "Benchmark",
            "active_return": "Active Return",
        })

        fig = px.line(
            chart_df,
            x="Date",
            y=["Portfolio", "Benchmark", "Active Return"],
            title="Aligned Portfolio vs Benchmark Returns",
        )

        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Top Detractors")
    detractors = attribution.top_detractors()
    if not detractors.empty:
        st.dataframe(detractors[["Symbol", "Weight", "Contribution"]], use_container_width=True, hide_index=True)

    st.subheader("Factor Snapshot")
    factors = attribution.factor_snapshot()

    f1, f2, f3 = st.columns(3)
    f1.metric("Max Position Weight", f"{factors.get('concentration', 0):.2%}")
    f2.metric("Diversification Score", f"{factors.get('diversification', 0):.2%}")
    f3.metric("Positions", factors.get("num_positions", 0))

    st.divider()
    st.header("Risk Engine")

    risk = RiskAnalyticsService(
        returns_df=returns_df if not returns_df.empty else None,
        positions_df=df_pos if not df_pos.empty else None,
    )

    hist_var = risk.historical_var(confidence=0.95)
    param_var = risk.parametric_var(confidence_z=1.65)
    es_95 = risk.expected_shortfall(confidence=0.95)
    conc = risk.concentration_risk()
    vol_regime = risk.volatility_regime()
    dd_alert = risk.drawdown_alert(
        threshold=float(st.secrets.get("trading", {}).get("DRAWDOWN_ALERT_THRESHOLD", -0.10))
    )

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Hist VaR 95%", f"{hist_var:.2%}")
    r2.metric("Param VaR 95%", f"{param_var:.2%}")
    r3.metric("Expected Shortfall", f"{es_95:.2%}")
    r4.metric("Vol Regime", vol_regime["regime"])

    r5, r6, r7 = st.columns(3)
    r5.metric("Max Position Weight", f"{conc['max_weight']:.2%}")
    r6.metric("HHI", f"{conc['hh_index']:.3f}")
    r7.metric("Effective N", f"{conc['effective_n']:.2f}")

    if dd_alert["triggered"]:
        st.error(f"Drawdown alert triggered: {dd_alert['current_drawdown']:.2%}")
    else:
        st.success(f"Current drawdown within threshold: {dd_alert['current_drawdown']:.2%}")

    st.markdown("### Stress Testing")
    stress_df = risk.stress_test()
    if not stress_df.empty:
        st.dataframe(stress_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No stress data yet.")

    st.markdown("### Position Risk Contribution")
    risk_contrib_df = risk.position_risk_contribution()
    if not risk_contrib_df.empty:
        st.dataframe(risk_contrib_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No position risk contribution data yet.")

    st.divider()
    st.header("Risk Guardrails")

    guardrails = GuardrailService(db_session)

    current_dd = guardrails.current_drawdown(portfolio_id)
    orders_today = guardrails.orders_today(portfolio_id)
    gross_exposure_now = guardrails.gross_exposure(df_pos if not df_pos.empty else pd.DataFrame())
    max_weight_now = guardrails.max_position_weight(df_pos if not df_pos.empty else pd.DataFrame())

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Current Drawdown", f"{current_dd:.2%}")
    g2.metric("Orders Today", orders_today)
    g3.metric("Gross Exposure", f"${gross_exposure_now:,.2f}")
    g4.metric("Max Position Weight", f"{max_weight_now:.2%}")

    if bool(trading_cfg.get("KILL_SWITCH", False)):
        st.error("Kill switch is ON. Live execution should be blocked.")
    elif not bool(trading_cfg.get("ENABLE_LIVE_TRADING", False)):
        st.warning("Live trading is OFF in config.")
    else:
        st.success("Live trading guardrails are enabled.")
    st.divider()
    st.header("Reconciliation Engine")

    from modules.portfolio.reconciliation_service import ReconciliationService

    recon = ReconciliationService(db_session, broker)

    # Convert existing data
    db_positions_df = df_pos.copy() if not df_pos.empty else pd.DataFrame()
    db_orders_df = df_orders.copy() if not df_orders.empty else pd.DataFrame()
    db_cash = totals.get("cash", 0.0)

    # ---------------------------------
    # Positions
    # ---------------------------------
    st.subheader("Position Reconciliation")

    pos_diff = recon.reconcile_positions(db_positions_df)

    if not pos_diff.empty:
        st.error("Position mismatches detected")
        st.dataframe(pos_diff, use_container_width=True)

        if st.button("Auto-Fix Positions"):
            updated = recon.auto_fix_positions(pos_diff)
            st.success(f"Updated {updated} positions")
            st.rerun()
    else:
        st.success("Positions reconciled")

    # ---------------------------------
    # Orders
    # ---------------------------------
    st.subheader("Order Reconciliation")

    order_diff = recon.reconcile_orders(db_orders_df)

    if not order_diff.empty:
        st.warning("Order mismatches detected")
        st.dataframe(order_diff, use_container_width=True)
    else:
        st.success("Orders reconciled")

    # ---------------------------------
    # Cash
    # ---------------------------------
    st.subheader("Cash Reconciliation")

    cash_check = recon.reconcile_cash(db_cash)

    st.metric("Broker Cash", f"${cash_check['broker_cash']:,.2f}")
    st.metric("DB Cash", f"${cash_check['db_cash']:,.2f}")
    st.metric("Difference", f"${cash_check['difference']:,.2f}")

    if abs(cash_check["difference"]) > 1:
        st.error("Cash mismatch detected")
    else:
        st.success("Cash reconciled")

    st.header("Portfolio Construction Engine")

    constructor = PortfolioConstructionService(
        positions_df=df_pos if not df_pos.empty else None
    )

    current_weights_df = constructor.current_weights()

    st.subheader("Current Weights")
    if not current_weights_df.empty:
        st.dataframe(current_weights_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No current positions")

    saved_alpha_targets = st.session_state.get(f"alpha_target_df_{portfolio_id}")
    construction_target_df = None

    if saved_alpha_targets:
        with st.expander("Saved Alpha Targets in Session", expanded=False):
            st.dataframe(pd.DataFrame(saved_alpha_targets), use_container_width=True, hide_index=True)
            if st.button("Use Alpha Targets for Construction", key=f"use_alpha_{portfolio_id}"):
                construction_target_df = pd.DataFrame(saved_alpha_targets)
                st.success("Alpha targets loaded into construction engine")

    st.subheader("Target Portfolio")

    mode = st.selectbox(
        "Construction Mode",
        ["Equal Weight", "Manual"],
        key=f"construction_mode_{portfolio_id}",
    )

    symbols_input = st.text_input(
        "Target Symbols (comma separated)",
        value="AAPL,MSFT,GOOGL",
        key=f"construction_symbols_{portfolio_id}",
    )
    symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]

    if construction_target_df is None:
        if mode == "Equal Weight":
            construction_target_df = constructor.equal_weight(symbols)
        else:
            weights_input = st.text_area(
                "Manual Weights (JSON format)",
                value='{"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.3}',
                key=f"manual_weights_{portfolio_id}",
            )
            try:
                weights_dict = json.loads(weights_input)
                construction_target_df = constructor.manual_weights(weights_dict)
            except Exception:
                construction_target_df = pd.DataFrame()
                st.error("Invalid JSON format")

    if construction_target_df is not None and not construction_target_df.empty:
        st.dataframe(construction_target_df, use_container_width=True, hide_index=True)


    st.divider()
    st.header("Multi-Strategy Portfolio Allocator")

    allocator = StrategyAllocator()

    strategies = list_discovered_strategies(db_session, tenant_id=user_id)

    multi_strategy_targets = {}
    allocation_weights = {}

    if not strategies:
        st.caption("No discovered strategies available for allocation.")
    else:
        selected_strategy_labels = st.multiselect(
            "Select Strategies to Combine",
            options=[
                f"{s.name} | Sharpe {round(s.sharpe or 0, 2)} | Alpha {round(s.alpha or 0, 2)}"
                for s in strategies
            ],
            key=f"multi_strategy_select_{portfolio_id}",
        )

        label_to_strategy = {
            f"{s.name} | Sharpe {round(s.sharpe or 0, 2)} | Alpha {round(s.alpha or 0, 2)}": s
            for s in strategies
        }

        if selected_strategy_labels:
            st.subheader("Strategy Allocations")

            for label in selected_strategy_labels:
                strat = label_to_strategy[label]
                allocation_weights[strat.name] = st.slider(
                    f"Capital Weight: {strat.name}",
                    min_value=0.0,
                    max_value=1.0,
                    value=1.0 / len(selected_strategy_labels),
                    step=0.05,
                    key=f"alloc_{portfolio_id}_{strat.name}",
                )

                bridge = StrategyBridge(db_session, tenant_id=user_id)
                df_target = bridge.load_strategy_to_weights(strat)

                if df_target is not None and not df_target.empty:
                    multi_strategy_targets[strat.name] = df_target

            if multi_strategy_targets:
                st.subheader("Strategy Mix")
                mix_df = allocator.strategy_mix_table(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=allocation_weights,
                )
                if not mix_df.empty:
                    st.dataframe(mix_df, use_container_width=True, hide_index=True)

                combined_target_df = allocator.weighted_allocate(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=allocation_weights,
                )

                st.subheader("Combined Target Weights")
                if not combined_target_df.empty:
                    st.dataframe(combined_target_df, use_container_width=True, hide_index=True)

                    # ---------------------------------
                    # Build price map
                    # ---------------------------------
                    combined_prices = {}

                    if not df_pos.empty and "Symbol" in df_pos.columns:
                        for _, row in df_pos.iterrows():
                            sym = row.get("Symbol")
                            px = row.get("Market Price")
                            if sym and px is not None:
                                combined_prices[str(sym).upper()] = float(px)

                    for sym in combined_target_df["Symbol"].tolist():
                        if sym not in combined_prices:
                            try:
                                q = market_data_service.get_quote(sym)
                                px = _safe_price_from_quote(q)
                                if px is not None:
                                    combined_prices[sym] = px
                            except Exception:
                                pass

                    combined_rebalance_df = constructor.generate_rebalance_trades(
                        target_df=combined_target_df,
                        prices=combined_prices,
                        portfolio_value=float(totals.get("equity", 0.0)),
                    )

                    st.subheader("Combined Rebalance Plan")
                    if not combined_rebalance_df.empty:
                        st.dataframe(combined_rebalance_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No combined rebalance required.")

                    c1, c2 = st.columns(2)

                    if c1.button("Save Combined Targets to Session", key=f"save_combined_targets_{portfolio_id}"):
                        st.session_state[f"combined_target_df_{portfolio_id}"] = combined_target_df.to_dict(
                            orient="records")
                        st.success("Combined targets saved to session.")

                    if c2.button("Execute Combined Rebalance", key=f"execute_combined_rebalance_{portfolio_id}"):
                        if combined_rebalance_df.empty:
                            st.warning("No combined trades to execute.")
                        else:
                            try:
                                valid, reasons = guardrails.validate_rebalance_plan(
                                    portfolio_id=portfolio_id,
                                    rebalance_df=combined_rebalance_df,
                                    positions_df=df_pos if not df_pos.empty else pd.DataFrame(),
                                    equity=float(totals.get("equity", 0.0)),
                                    config=trading_cfg,
                                )

                                if not valid:
                                    st.error("Execution blocked by guardrails:")
                                    for reason in reasons:
                                        st.write(f"- {reason}")
                                else:
                                    service = OrderService(db_session, broker, market_data_service)

                                    for _, row in combined_rebalance_df.iterrows():
                                        service.submit_order(
                                            portfolio_id=portfolio_id,
                                            user_id=user_id,
                                            symbol=str(row["Symbol"]).upper(),
                                            side=str(row["Side"]).lower(),
                                            qty=float(row["Qty"]),
                                            order_type="market",
                                            tif="day",
                                        )

                                    try:
                                        run_service = StrategyRunService(db_session)
                                        run_service.log_run(
                                            portfolio_id=portfolio_id,
                                            strategy_name="multi_strategy_allocator",
                                            trigger_type="manual",
                                            status="executed",
                                            target_df=combined_target_df,
                                            drift_threshold=None,
                                            notes="Executed combined strategy allocation",
                                        )
                                    except Exception as log_err:
                                        print("MULTI-STRATEGY LOG ERROR:", log_err)

                                    st.success("Combined rebalance executed.")
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Combined rebalance failed: {e}")

    st.divider()
    st.header("Strategy P&L Decomposition")

    decomposition = StrategyDecompositionService(
        positions_df=df_pos if not df_pos.empty else None,
        closed_trades_df=df_closed if not df_closed.empty else None,
    )

    if "multi_strategy_targets" in locals() and multi_strategy_targets and "allocation_weights" in locals() and allocation_weights:
        sleeve_df = decomposition.sleeve_contribution(
            strategy_targets=multi_strategy_targets,
            allocation_weights=allocation_weights,
        )

        overlap_df = decomposition.overlap_matrix(multi_strategy_targets)
        symbol_map_df = decomposition.symbol_strategy_map(multi_strategy_targets)
        closed_attr_df = decomposition.closed_trade_attribution_by_strategy(
            strategy_targets=multi_strategy_targets,
            allocation_weights=allocation_weights,
        )

        st.subheader("Sleeve Contribution")
        if not sleeve_df.empty:
            st.dataframe(sleeve_df, use_container_width=True, hide_index=True)

            s1, s2, s3 = st.columns(3)
            s1.metric("Top Sleeve P&L", f"${float(sleeve_df['Sleeve Estimated P&L'].max()):,.2f}")
            s2.metric("Worst Sleeve P&L", f"${float(sleeve_df['Sleeve Estimated P&L'].min()):,.2f}")
            s3.metric(
                "Best Capital Efficiency",
                f"{float(sleeve_df['Capital Efficiency'].max()):.2%}"
            )
        else:
            st.caption("No sleeve contribution data yet.")

        st.subheader("Strategy Overlap Matrix")
        if not overlap_df.empty:
            st.dataframe(overlap_df, use_container_width=True)
        else:
            st.caption("No overlap data available.")

        st.subheader("Symbol Overlap Attribution")
        if not symbol_map_df.empty:
            st.dataframe(symbol_map_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No overlapping symbol map available.")

        st.subheader("Closed Trade Attribution by Strategy")
        if not closed_attr_df.empty:
            st.dataframe(closed_attr_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No closed trade attribution available.")

    else:
        st.caption("Build a multi-strategy portfolio first to view decomposition.")
    st.divider()
    st.header("Strategy Weight Optimizer")

    optimizer = StrategyWeightOptimizer()

    # We can only optimize if multi-strategy portfolio exists
    if (
        "multi_strategy_targets" in locals() and multi_strategy_targets and
        "allocation_weights" in locals() and allocation_weights
    ):
        # Build strategy metrics from discovered strategies + decomposition if available
        strategy_metric_rows = []

        # Map discovered strategy rows
        discovered_strategy_map = {}
        if strategies:
            for s in strategies:
                discovered_strategy_map[s.name] = s

        sleeve_df = pd.DataFrame()
        overlap_df = pd.DataFrame()

        try:
            sleeve_df = decomposition.sleeve_contribution(
                strategy_targets=multi_strategy_targets,
                allocation_weights=allocation_weights,
            )
        except Exception:
            sleeve_df = pd.DataFrame()

        try:
            overlap_df = decomposition.overlap_matrix(multi_strategy_targets)
        except Exception:
            overlap_df = pd.DataFrame()

        for strategy_name in multi_strategy_targets.keys():
            strat_obj = discovered_strategy_map.get(strategy_name)

            sharpe = float(getattr(strat_obj, "sharpe", 0.0) or 0.0)
            alpha_val = float(getattr(strat_obj, "alpha", 0.0) or 0.0)
            max_dd = float(getattr(strat_obj, "max_drawdown", 0.0) or 0.0)

            cap_eff = 0.0
            if not sleeve_df.empty and "Strategy" in sleeve_df.columns:
                match = sleeve_df[sleeve_df["Strategy"] == strategy_name]
                if not match.empty and "Capital Efficiency" in match.columns:
                    cap_eff = float(match["Capital Efficiency"].iloc[0] or 0.0)

            strategy_metric_rows.append({
                "Strategy": strategy_name,
                "Sharpe": sharpe,
                "Alpha": alpha_val,
                "Max Drawdown": max_dd,
                "Capital Efficiency": cap_eff,
            })

        strategy_metrics_df = pd.DataFrame(strategy_metric_rows)

        if not strategy_metrics_df.empty:
            st.subheader("Strategy Metrics")
            st.dataframe(strategy_metrics_df, use_container_width=True, hide_index=True)

            max_strategy_weight = st.slider(
                "Max Strategy Weight",
                min_value=0.10,
                max_value=1.00,
                value=0.50,
                step=0.05,
                key=f"max_strategy_weight_{portfolio_id}",
            )

            overlap_penalty = st.slider(
                "Overlap Penalty",
                min_value=0.00,
                max_value=1.00,
                value=0.15,
                step=0.05,
                key=f"overlap_penalty_{portfolio_id}",
            )

            drawdown_penalty = st.slider(
                "Drawdown Penalty",
                min_value=0.00,
                max_value=1.00,
                value=0.25,
                step=0.05,
                key=f"drawdown_penalty_{portfolio_id}",
            )

            optimized_df = optimizer.optimize_weights(
                strategy_metrics_df=strategy_metrics_df,
                overlap_matrix_df=overlap_df if not overlap_df.empty else None,
                max_strategy_weight=max_strategy_weight,
                overlap_penalty=overlap_penalty,
                drawdown_penalty=drawdown_penalty,
            )

            st.subheader("Optimized Strategy Weights")
            st.dataframe(optimized_df, use_container_width=True, hide_index=True)

            if st.button("Apply Optimized Strategy Weights", key=f"apply_optimized_strategy_weights_{portfolio_id}"):
                optimized_alloc = {
                    row["Strategy"]: float(row["Optimized Weight"])
                    for _, row in optimized_df.iterrows()
                }

                st.session_state[f"optimized_allocation_weights_{portfolio_id}"] = optimized_alloc
                st.success("Optimized strategy weights saved to session.")

            optimized_alloc_saved = st.session_state.get(f"optimized_allocation_weights_{portfolio_id}")

            if optimized_alloc_saved:
                st.subheader("Saved Optimized Allocation")
                st.json(optimized_alloc_saved)

                optimized_target_df = allocator.weighted_allocate(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=optimized_alloc_saved,
                )

                st.subheader("Optimized Combined Portfolio Weights")
                if not optimized_target_df.empty:
                    st.dataframe(optimized_target_df, use_container_width=True, hide_index=True)

                    optimized_prices = {}

                    if not df_pos.empty and "Symbol" in df_pos.columns:
                        for _, row in df_pos.iterrows():
                            sym = row.get("Symbol")
                            px = row.get("Market Price")
                            if sym and px is not None:
                                optimized_prices[str(sym).upper()] = float(px)

                    for sym in optimized_target_df["Symbol"].tolist():
                        if sym not in optimized_prices:
                            try:
                                q = market_data_service.get_quote(sym)
                                px = _safe_price_from_quote(q)
                                if px is not None:
                                    optimized_prices[sym] = px
                            except Exception:
                                pass

                    optimized_rebalance_df = constructor.generate_rebalance_trades(
                        target_df=optimized_target_df,
                        prices=optimized_prices,
                        portfolio_value=float(totals.get("equity", 0.0)),
                    )

                    st.subheader("Optimized Rebalance Plan")
                    if not optimized_rebalance_df.empty:
                        st.dataframe(optimized_rebalance_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No optimized rebalance required.")

                    oc1, oc2 = st.columns(2)

                    if oc1.button("Save Optimized Targets to Session", key=f"save_optimized_targets_{portfolio_id}"):
                        st.session_state[f"optimized_target_df_{portfolio_id}"] = optimized_target_df.to_dict(orient="records")
                        st.success("Optimized targets saved to session.")

                    if oc2.button("Execute Optimized Rebalance", key=f"execute_optimized_rebalance_{portfolio_id}"):
                        if optimized_rebalance_df.empty:
                            st.warning("No optimized trades to execute.")
                        else:
                            try:
                                valid, reasons = guardrails.validate_rebalance_plan(
                                    portfolio_id=portfolio_id,
                                    rebalance_df=optimized_rebalance_df,
                                    positions_df=df_pos if not df_pos.empty else pd.DataFrame(),
                                    equity=float(totals.get("equity", 0.0)),
                                    config=trading_cfg,
                                )

                                if not valid:
                                    st.error("Execution blocked by guardrails:")
                                    for reason in reasons:
                                        st.write(f"- {reason}")
                                else:
                                    service = OrderService(db_session, broker, market_data_service)

                                    for _, row in optimized_rebalance_df.iterrows():
                                        service.submit_order(
                                            portfolio_id=portfolio_id,
                                            user_id=user_id,
                                            symbol=str(row["Symbol"]).upper(),
                                            side=str(row["Side"]).lower(),
                                            qty=float(row["Qty"]),
                                            order_type="market",
                                            tif="day",
                                        )

                                    try:
                                        run_service = StrategyRunService(db_session)
                                        run_service.log_run(
                                            portfolio_id=portfolio_id,
                                            strategy_name="strategy_weight_optimizer",
                                            trigger_type="manual",
                                            status="executed",
                                            target_df=optimized_target_df,
                                            drift_threshold=None,
                                            notes="Executed optimized multi-strategy allocation",
                                        )
                                    except Exception as log_err:
                                        print("OPTIMIZER LOG ERROR:", log_err)

                                    st.success("Optimized rebalance executed.")
                                    st.rerun()

                            except Exception as e:
                                st.error(f"Optimized rebalance failed: {e}")
                else:
                    st.caption("No optimized targets produced.")
        else:
            st.caption("No strategy metrics available for optimization.")
    else:
        st.caption("Create a multi-strategy allocation first to optimize strategy weights.")

    st.subheader("Rebalance Plan")

    prices: dict[str, float] = {}
    if not df_pos.empty and "Symbol" in df_pos.columns:
        for _, row in df_pos.iterrows():
            sym = row.get("Symbol")
            px = row.get("Market Price")
            if sym and px is not None:
                prices[str(sym).upper()] = float(px)

    portfolio_value = float(totals.get("equity", 0.0))

    rebalance_df = constructor.generate_rebalance_trades(
        target_df=construction_target_df if construction_target_df is not None else pd.DataFrame(),
        prices=prices,
        portfolio_value=portfolio_value,
    )

    if not rebalance_df.empty:
        st.dataframe(rebalance_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No rebalance trades needed")
    st.divider()
    st.header("Constraint-Aware Optimizer (Phase 18)")

    constraint_opt = ConstraintAwareOptimizer()

    if (
            "multi_strategy_targets" in locals()
            and multi_strategy_targets
            and "allocation_weights" in locals()
            and allocation_weights
    ):

        st.subheader("Constraints")

        max_strategy_weight = st.slider(
            "Max Strategy Weight",
            0.10, 1.00, 0.50, 0.05,
            key=f"c_max_strat_{portfolio_id}"
        )

        turnover_penalty = st.slider(
            "Turnover Penalty",
            0.0, 1.0, 0.20, 0.05,
            key=f"c_turnover_{portfolio_id}"
        )

        overlap_penalty = st.slider(
            "Overlap Penalty",
            0.0, 1.0, 0.15, 0.05,
            key=f"c_overlap_{portfolio_id}"
        )

        drawdown_penalty = st.slider(
            "Drawdown Penalty",
            0.0, 1.0, 0.25, 0.05,
            key=f"c_dd_{portfolio_id}"
        )

        vol_target = st.slider(
            "Target Volatility (optional)",
            0.05, 0.50, 0.20, 0.01,
            key=f"c_vol_{portfolio_id}"
        )

        optimized_df = constraint_opt.optimize(
            strategy_metrics_df=strategy_metrics_df,
            overlap_matrix_df=overlap_df,
            current_weights=allocation_weights,
            max_strategy_weight=max_strategy_weight,
            turnover_penalty=turnover_penalty,
            overlap_penalty=overlap_penalty,
            drawdown_penalty=drawdown_penalty,
            vol_target=vol_target,
        )

        st.subheader("Constraint Optimized Weights")
        st.dataframe(optimized_df, use_container_width=True, hide_index=True)

        if st.button("Apply Constraint Optimized Weights"):
            new_alloc = {
                row["Strategy"]: float(row["Weight"])
                for _, row in optimized_df.iterrows()
            }

            st.session_state[f"constraint_alloc_{portfolio_id}"] = new_alloc
            st.success("Constraint weights applied")

        saved = st.session_state.get(f"constraint_alloc_{portfolio_id}")

        if saved:
            st.subheader("Constraint Allocation (Active)")
            st.json(saved)

            final_target_df = allocator.weighted_allocate(
                strategy_targets=multi_strategy_targets,
                allocation_weights=saved,
            )

            st.subheader("Final Portfolio (Constraint Optimized)")
            st.dataframe(final_target_df, use_container_width=True, hide_index=True)
    st.subheader("Execute Rebalance")
    if not rebalance_df.empty:
        if st.button("Execute Rebalance Trades", key=f"execute_construction_{portfolio_id}"):
            try:
                service = OrderService(db_session, broker, market_data_service)

                for _, row in rebalance_df.iterrows():
                    service.submit_order(
                        portfolio_id=portfolio_id,
                        user_id=user_id,
                        symbol=row["Symbol"],
                        side=row["Side"],
                        qty=float(row["Qty"]),
                        order_type="market",
                        tif="day",
                    )

                st.success("Rebalance orders submitted")
                st.rerun()

            except Exception as e:
                st.error(f"Rebalance failed: {e}")

    automation_target_df = None

    optimized_targets_saved = st.session_state.get(f"optimized_target_df_{portfolio_id}")
    combined_targets_saved = st.session_state.get(f"combined_target_df_{portfolio_id}")
    alpha_targets_saved = st.session_state.get(f"alpha_target_df_{portfolio_id}")

    if optimized_targets_saved:
        automation_target_df = pd.DataFrame(optimized_targets_saved)
    elif combined_targets_saved:
        automation_target_df = pd.DataFrame(combined_targets_saved)
    elif construction_target_df is not None and not construction_target_df.empty:
        automation_target_df = construction_target_df.copy()
    elif alpha_targets_saved:
        automation_target_df = pd.DataFrame(alpha_targets_saved)
    else:
        automation_target_df = None

    st.divider()
    st.header("Alpha Engine")

    alpha = AlphaEngine(market_data_service=market_data_service)

    alpha_mode = st.selectbox(
        "Alpha Universe Source",
        ["Manual Universe", "Current Positions"],
        key=f"alpha_mode_{portfolio_id}",
    )

    if alpha_mode == "Manual Universe":
        alpha_symbols_input = st.text_area(
            "Alpha Universe Symbols",
            value="AAPL,MSFT,NVDA,GOOGL,AMZN,META,PLTR,TSLA,AVGO,CRM",
            key=f"alpha_symbols_{portfolio_id}",
        )
        alpha_symbols = [s.strip().upper() for s in alpha_symbols_input.split(",") if s.strip()]
    else:
        alpha_symbols = []
        if not df_pos.empty and "Symbol" in df_pos.columns:
            alpha_symbols = [str(x).upper() for x in df_pos["Symbol"].dropna().tolist()]

    max_top_n = max(1, min(25, len(alpha_symbols) if alpha_symbols else 10))
    default_top_n = min(5, max_top_n)

    top_n = st.slider(
        "Top N Holdings",
        min_value=1,
        max_value=max_top_n,
        value=default_top_n,
        key=f"alpha_top_n_{portfolio_id}",
    )

    max_weight = st.slider(
        "Max Position Weight",
        min_value=0.05,
        max_value=0.50,
        value=0.20,
        step=0.01,
        key=f"alpha_max_weight_{portfolio_id}",
    )

    signal_df = alpha.build_signal_frame(alpha_symbols) if alpha_symbols else pd.DataFrame()

    if not signal_df.empty:
        st.subheader("Alpha Scores")
        st.dataframe(signal_df, use_container_width=True, hide_index=True)

        alpha_target_df = alpha.scores_to_target_weights(
            signal_df=signal_df,
            top_n=top_n,
            max_weight=max_weight,
        )
        combined_targets_saved = st.session_state.get(f"combined_target_df_{portfolio_id}")

        if combined_targets_saved:
            automation_target_df = pd.DataFrame(combined_targets_saved)
        elif construction_target_df is not None and not construction_target_df.empty:
            automation_target_df = construction_target_df.copy()
        elif saved_alpha_targets:
            automation_target_df = pd.DataFrame(saved_alpha_targets)

        st.subheader("Alpha Target Weights")
        st.dataframe(alpha_target_df, use_container_width=True, hide_index=True)

        alpha_prices: dict[str, float] = {}

        if not df_pos.empty:
            for _, row in df_pos.iterrows():
                sym = row.get("Symbol")
                px = row.get("Market Price")
                if sym and px is not None:
                    alpha_prices[str(sym).upper()] = float(px)

        for sym in alpha_target_df["Symbol"].tolist():
            if sym not in alpha_prices:
                try:
                    q = market_data_service.get_quote(sym)
                    px = _safe_price_from_quote(q)
                    if px is not None:
                        alpha_prices[sym] = px
                except Exception:
                    pass

        alpha_rebalance_df = constructor.generate_rebalance_trades(
            target_df=alpha_target_df,
            prices=alpha_prices,
            portfolio_value=float(totals.get("equity", 0.0)),
        )

        st.subheader("Alpha Rebalance Plan")
        if not alpha_rebalance_df.empty:
            st.dataframe(alpha_rebalance_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No alpha rebalance trades generated.")

        cxa, cxb = st.columns(2)

        if cxa.button("Apply Alpha Targets to Construction Engine", key=f"apply_alpha_{portfolio_id}"):
            st.session_state[f"alpha_target_df_{portfolio_id}"] = alpha_target_df.to_dict(orient="records")
            st.success("Alpha targets saved in session for this portfolio.")

        if cxb.button("Execute Alpha Rebalance", key=f"exec_alpha_{portfolio_id}"):
            if alpha_rebalance_df.empty:
                st.warning("No alpha trades to execute.")
            else:
                try:
                    service = OrderService(db_session, broker, market_data_service)

                    for _, row in alpha_rebalance_df.iterrows():
                        service.submit_order(
                            portfolio_id=portfolio_id,
                            user_id=user_id,
                            symbol=str(row["Symbol"]).upper(),
                            side=str(row["Side"]).lower(),
                            qty=float(row["Qty"]),
                            order_type="market",
                            tif="day",
                        )

                    st.success("Alpha rebalance orders submitted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Alpha rebalance failed: {e}")
    else:
        st.caption("No alpha scores available yet.")

    st.divider()
    st.header("Discovered Strategy Execution")

    strategies = list_discovered_strategies(db_session, tenant_id=user_id)

    strategy_target_df = pd.DataFrame()

    if not strategies:
        st.caption("No discovered strategies available.")
    else:
        strat_map = {
            f"{s.name} | Sharpe {round(s.sharpe or 0, 2)} | Alpha {round(s.alpha or 0, 2)}": s
            for s in strategies
        }

        selected_label = st.selectbox(
            "Select Strategy",
            list(strat_map.keys()),
            key=f"discovered_strategy_{portfolio_id}",
        )

        selected_strategy = strat_map[selected_label]

        st.write("Factors:", selected_strategy.factors)
        st.write("Holdings:", selected_strategy.holdings)

        bridge = StrategyBridge(db_session, tenant_id=user_id)

        if st.button("Convert Strategy → Portfolio", key=f"convert_strategy_{portfolio_id}"):
            strategy_target_df = bridge.load_strategy_to_weights(selected_strategy)

            if strategy_target_df.empty:
                st.warning("Strategy has no valid holdings")
            else:
                st.subheader("Target Weights")
                st.dataframe(strategy_target_df, use_container_width=True, hide_index=True)

                strategy_prices: dict[str, float] = {}

                for sym in strategy_target_df["Symbol"]:
                    try:
                        q = market_data_service.get_quote(sym)
                        px = _safe_price_from_quote(q)
                        if px is not None:
                            strategy_prices[sym] = px
                    except Exception:
                        continue

                strategy_rebalance_df = constructor.generate_rebalance_trades(
                    target_df=strategy_target_df,
                    prices=strategy_prices,
                    portfolio_value=float(totals["equity"]),
                )

                st.subheader("Rebalance Plan")
                st.dataframe(strategy_rebalance_df, use_container_width=True, hide_index=True)

                if st.button("Execute Strategy", key=f"execute_strategy_{portfolio_id}"):
                    service = OrderService(db_session, broker, market_data_service)

                    for _, row in strategy_rebalance_df.iterrows():
                        service.submit_order(
                            portfolio_id=portfolio_id,
                            user_id=user_id,
                            symbol=row["Symbol"],
                            side=row["Side"],
                            qty=float(row["Qty"]),
                            order_type="market",
                            tif="day",
                        )

                    st.success("Strategy executed")
                    st.rerun()

    st.divider()
    st.header("Live Portfolio Intelligence")

    intelligence = LivePortfolioIntelligenceService(
        positions_df=df_pos if not df_pos.empty else None,
        orders_df=df_orders if not df_orders.empty else None,
        closed_trades_df=df_closed if not df_closed.empty else None,
        returns_df=returns_df if not returns_df.empty else None,
    )

    target_allocations_live = {}
    actual_allocations_live = {}

    if "allocation_weights" in locals() and allocation_weights:
        target_allocations_live = {k: float(v) for k, v in allocation_weights.items()}

    sleeve_df_live = pd.DataFrame()
    if (
        "multi_strategy_targets" in locals()
        and multi_strategy_targets
        and "allocation_weights" in locals()
        and allocation_weights
    ):
        try:
            sleeve_df_live = decomposition.sleeve_contribution(
                strategy_targets=multi_strategy_targets,
                allocation_weights=allocation_weights,
            )
        except Exception:
            sleeve_df_live = pd.DataFrame()

    if not sleeve_df_live.empty and "Strategy" in sleeve_df_live.columns and "Sleeve Market Value" in sleeve_df_live.columns:
        total_sleeve_mv = float(sleeve_df_live["Sleeve Market Value"].sum())
        if total_sleeve_mv > 0:
            actual_allocations_live = {
                row["Strategy"]: float(row["Sleeve Market Value"]) / total_sleeve_mv
                for _, row in sleeve_df_live.iterrows()
            }

    drift_live_df = intelligence.sleeve_drift(
        target_allocations=target_allocations_live,
        actual_allocations=actual_allocations_live,
    )

    slip_stats = intelligence.slippage_summary()
    decay_stats = intelligence.alpha_decay(window=10)

    trigger_stats = intelligence.reweight_trigger(
        drift_df=drift_live_df,
        drift_threshold=0.05,
        alpha_decay_flag=decay_stats["decaying"],
        slippage_threshold=0.02,
    )
    if trigger_stats["trigger"]:
        try:
            alert_service.push(
                level="warning",
                title="Portfolio reweight trigger",
                message=" | ".join(trigger_stats["reasons"]),
                source="live_intelligence",
                metadata={"portfolio_id": portfolio_id},
            )
        except Exception:
            pass
    health = intelligence.portfolio_health_score(drift_df=drift_live_df)

    li1, li2, li3, li4 = st.columns(4)
    li1.metric("Health Score", f"{health['score']:.1f}")
    li2.metric("Health Regime", health["regime"])
    li3.metric("Avg Slippage", f"${slip_stats['avg_slippage']:,.4f}")
    li4.metric("Alpha Decay", "Yes" if decay_stats["decaying"] else "No")

    li5, li6, li7 = st.columns(3)
    li5.metric("Recent Avg Return", f"{decay_stats['recent_avg_return']:.4%}")
    li6.metric("Older Avg Return", f"{decay_stats['older_avg_return']:.4%}")
    li7.metric("Total Slippage", f"${slip_stats['total_slippage']:,.2f}")

    st.subheader("Sleeve Drift Monitor")
    if not drift_live_df.empty:
        st.dataframe(drift_live_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No sleeve drift data available yet.")

    st.subheader("Reweight Trigger")
    if trigger_stats["trigger"]:
        st.warning("Reweight trigger activated")
        for reason in trigger_stats["reasons"]:
            st.write(f"- {reason}")
    else:
        st.success("No reweight trigger currently active")

    if trigger_stats["trigger"]:
        if st.button("Save Reweight Alert", key=f"save_reweight_alert_{portfolio_id}"):
            st.session_state[f"reweight_alert_{portfolio_id}"] = {
                "triggered": True,
                "reasons": trigger_stats["reasons"],
                "health": health,
            }
            st.success("Reweight alert saved to session.")

    saved_reweight_alert = st.session_state.get(f"reweight_alert_{portfolio_id}")
    if saved_reweight_alert:
        st.subheader("Saved Reweight Alert")
        st.json(saved_reweight_alert)
    st.divider()
    st.header("ML Strategy Ranking Engine")

    ml_ranker = StrategyMLRanker()

    if (
        "multi_strategy_targets" in locals()
        and multi_strategy_targets
        and "allocation_weights" in locals()
        and allocation_weights
        and "strategies" in locals()
        and strategies
    ):
        strategy_metric_rows = []
        discovered_strategy_map = {s.name: s for s in strategies}

        sleeve_for_rank = pd.DataFrame()
        closed_attr_for_rank = pd.DataFrame()
        overlap_for_rank = pd.DataFrame()

        try:
            if "decomposition" in locals():
                sleeve_for_rank = decomposition.sleeve_contribution(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=allocation_weights,
                )
                closed_attr_for_rank = decomposition.closed_trade_attribution_by_strategy(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=allocation_weights,
                )
                overlap_for_rank = decomposition.overlap_matrix(multi_strategy_targets)
        except Exception:
            sleeve_for_rank = pd.DataFrame()
            closed_attr_for_rank = pd.DataFrame()
            overlap_for_rank = pd.DataFrame()

        for strategy_name in multi_strategy_targets.keys():
            strat_obj = discovered_strategy_map.get(strategy_name)

            strategy_metric_rows.append({
                "Strategy": strategy_name,
                "Sharpe": float(getattr(strat_obj, "sharpe", 0.0) or 0.0),
                "Alpha": float(getattr(strat_obj, "alpha", 0.0) or 0.0),
                "Max Drawdown": float(getattr(strat_obj, "max_drawdown", 0.0) or 0.0),
                "Capital Efficiency": 0.0,
            })

        rank_metrics_df = pd.DataFrame(strategy_metric_rows)

        if not sleeve_for_rank.empty and "Strategy" in sleeve_for_rank.columns and "Capital Efficiency" in sleeve_for_rank.columns:
            cap_eff_map = {
                row["Strategy"]: float(row["Capital Efficiency"])
                for _, row in sleeve_for_rank.iterrows()
            }
            rank_metrics_df["Capital Efficiency"] = rank_metrics_df["Strategy"].map(cap_eff_map).fillna(0.0)

        # Lightweight alpha decay proxy by strategy
        alpha_decay_map = {}
        if "health" in locals():
            # Global fallback; later this can become sleeve-specific
            global_decay = 1.0 if str(health.get("regime", "")).lower() == "action needed" else 0.0
        else:
            global_decay = 0.0

        for strategy_name in rank_metrics_df["Strategy"].tolist():
            alpha_decay_map[strategy_name] = global_decay

        overlap_penalty_map = {}
        if not overlap_for_rank.empty:
            for strategy_name in rank_metrics_df["Strategy"].tolist():
                if strategy_name in overlap_for_rank.index:
                    row = overlap_for_rank.loc[strategy_name]
                    overlap_penalty_map[strategy_name] = float(row.sum() - row.get(strategy_name, 0.0))
                else:
                    overlap_penalty_map[strategy_name] = 0.0

        feature_df = ml_ranker.build_feature_frame(
            strategy_metrics_df=rank_metrics_df,
            closed_attr_df=closed_attr_for_rank if not closed_attr_for_rank.empty else None,
            sleeve_df=sleeve_for_rank if not sleeve_for_rank.empty else None,
        )

        if not feature_df.empty:
            st.subheader("ML Features")
            st.dataframe(feature_df, use_container_width=True, hide_index=True)

            ranked_df = ml_ranker.score_strategies(
                features_df=feature_df,
                alpha_decay_map=alpha_decay_map,
                overlap_penalty_map=overlap_penalty_map,
            )

            st.subheader("ML Strategy Ranking")
            st.dataframe(ranked_df, use_container_width=True, hide_index=True)

            rank_max_weight = st.slider(
                "ML Rank Max Strategy Weight",
                min_value=0.10,
                max_value=1.00,
                value=0.50,
                step=0.05,
                key=f"ml_rank_max_weight_{portfolio_id}",
            )

            ml_alloc_df = ml_ranker.rank_to_allocations(
                ranked_df=ranked_df,
                max_strategy_weight=rank_max_weight,
            )

            st.subheader("ML Suggested Strategy Weights")
            st.dataframe(ml_alloc_df, use_container_width=True, hide_index=True)

            if st.button("Apply ML Strategy Weights", key=f"apply_ml_rank_weights_{portfolio_id}"):
                ml_alloc_map = {
                    row["Strategy"]: float(row["Rank Weight"])
                    for _, row in ml_alloc_df.iterrows()
                }
                st.session_state[f"ml_rank_alloc_{portfolio_id}"] = ml_alloc_map
                st.success("ML-ranked strategy weights saved to session.")

            ml_rank_alloc_saved = st.session_state.get(f"ml_rank_alloc_{portfolio_id}")

            if ml_rank_alloc_saved:
                st.subheader("Saved ML Allocation")
                st.json(ml_rank_alloc_saved)

                ml_target_df = allocator.weighted_allocate(
                    strategy_targets=multi_strategy_targets,
                    allocation_weights=ml_rank_alloc_saved,
                )

                st.subheader("ML Combined Portfolio Weights")
                if not ml_target_df.empty:
                    st.dataframe(ml_target_df, use_container_width=True, hide_index=True)

                    ml_prices = {}

                    if not df_pos.empty and "Symbol" in df_pos.columns:
                        for _, row in df_pos.iterrows():
                            sym = row.get("Symbol")
                            px = row.get("Market Price")
                            if sym and px is not None:
                                ml_prices[str(sym).upper()] = float(px)

                    for sym in ml_target_df["Symbol"].tolist():
                        if sym not in ml_prices:
                            try:
                                q = market_data_service.get_quote(sym)
                                px = _safe_price_from_quote(q)
                                if px is not None:
                                    ml_prices[sym] = px
                            except Exception:
                                pass

                    ml_rebalance_df = constructor.generate_rebalance_trades(
                        target_df=ml_target_df,
                        prices=ml_prices,
                        portfolio_value=float(totals.get("equity", 0.0)),
                    )

                    st.subheader("ML Rebalance Plan")
                    if not ml_rebalance_df.empty:
                        st.dataframe(ml_rebalance_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No ML rebalance required.")

                    m1, m2 = st.columns(2)

                    if m1.button("Save ML Targets to Session", key=f"save_ml_targets_{portfolio_id}"):
                        st.session_state[f"ml_target_df_{portfolio_id}"] = ml_target_df.to_dict(orient="records")
                        st.success("ML targets saved to session.")

                    if m2.button("Execute ML Rebalance", key=f"execute_ml_rebalance_{portfolio_id}"):
                        if ml_rebalance_df.empty:
                            st.warning("No ML trades to execute.")
                        else:
                            try:
                                valid, reasons = guardrails.validate_rebalance_plan(
                                    portfolio_id=portfolio_id,
                                    rebalance_df=ml_rebalance_df,
                                    positions_df=df_pos if not df_pos.empty else pd.DataFrame(),
                                    equity=float(totals.get("equity", 0.0)),
                                    config=trading_cfg,
                                )

                                if not valid:
                                    st.error("Execution blocked by guardrails:")
                                    for reason in reasons:
                                        st.write(f"- {reason}")
                                else:
                                    service = OrderService(db_session, broker, market_data_service)

                                    for _, row in ml_rebalance_df.iterrows():
                                        service.submit_order(
                                            portfolio_id=portfolio_id,
                                            user_id=user_id,
                                            symbol=str(row["Symbol"]).upper(),
                                            side=str(row["Side"]).lower(),
                                            qty=float(row["Qty"]),
                                            order_type="market",
                                            tif="day",
                                        )

                                    try:
                                        run_service = StrategyRunService(db_session)
                                        run_service.log_run(
                                            portfolio_id=portfolio_id,
                                            strategy_name="ml_strategy_ranker",
                                            trigger_type="manual",
                                            status="executed",
                                            target_df=ml_target_df,
                                            drift_threshold=None,
                                            notes="Executed ML-ranked strategy allocation",
                                        )
                                    except Exception as log_err:
                                        print("ML RANK LOG ERROR:", log_err)

                                    st.success("ML rebalance executed.")
                                    st.rerun()

                            except Exception as e:
                                st.error(f"ML rebalance failed: {e}")
                else:
                    st.caption("No ML combined targets produced.")
        else:
            st.caption("No ML feature frame available.")
    else:
        st.caption("Build a multi-strategy portfolio first to use ML ranking.")

    st.divider()
    st.header("Event-Driven Execution Engine")

    event_engine_key = f"event_engine_{portfolio_id}"
    if event_engine_key not in st.session_state:
        st.session_state[event_engine_key] = EventDrivenExecutionEngine()

    event_engine = st.session_state[event_engine_key]

    # ---------------------------------
    # Event creation from live intelligence / automation conditions
    # ---------------------------------
    if "automation_target_df" in locals() and automation_target_df is not None and not automation_target_df.empty:
        if st.button("Queue Rebalance Event", key=f"queue_rebalance_event_{portfolio_id}"):
            evt = event_engine.build_rebalance_event(
                portfolio_id=portfolio_id,
                target_df=automation_target_df,
                reason="Manual queue from automation target",
                priority="high",
            )
            st.success(f"Queued event: {evt['event_type']}")

    if "trigger_stats" in locals() and trigger_stats.get("trigger"):
        if st.button("Queue Triggered Reweight Event", key=f"queue_triggered_event_{portfolio_id}"):
            if automation_target_df is not None and not automation_target_df.empty:
                evt = event_engine.build_rebalance_event(
                    portfolio_id=portfolio_id,
                    target_df=automation_target_df,
                    reason="Live intelligence reweight trigger",
                    priority="critical",
                )
                st.success(f"Queued event: {evt['event_type']}")

    queued_events = event_engine.list_events()

    st.subheader("Queued Events")
    if queued_events:
        event_df = pd.DataFrame([
            {
                "Timestamp": e["timestamp"],
                "Type": e["event_type"],
                "Priority": e["priority"],
                "Source": e["source"],
                "Status": e["status"],
            }
            for e in queued_events
        ])
        st.dataframe(event_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No queued events.")

    event_auto_execute = st.checkbox(
        "Allow event processor to execute trades immediately",
        value=False,
        key=f"event_auto_execute_{portfolio_id}",
    )

    ep1, ep2, ep3 = st.columns(3)

    if ep1.button("Process Next Event", key=f"process_next_event_{portfolio_id}"):
        next_event = event_engine.pop_next()

        if not next_event:
            st.info("No queued events.")
        else:
            processor = EventProcessor(
                db_session=db_session,
                broker=broker,
                market_data_service=market_data_service,
                constructor=constructor,
                guardrails=guardrails,
                monitoring_service=monitoring_service if 'monitoring_service' in locals() else None,
                alert_service=alert_service if 'alert_service' in locals() else None,
            )

            event_result = processor.process_event(
                event=next_event,
                portfolio_id=portfolio_id,
                user_id=user_id,
                totals=totals,
                df_pos=df_pos if not df_pos.empty else pd.DataFrame(),
                trading_cfg=trading_cfg,
                auto_execute=event_auto_execute,
            )

            st.write(event_result)

            if "rebalance_df" in event_result and isinstance(event_result["rebalance_df"], pd.DataFrame):
                if not event_result["rebalance_df"].empty:
                    st.subheader("Event Rebalance Plan")
                    st.dataframe(event_result["rebalance_df"], use_container_width=True, hide_index=True)

                    if event_result["status"] == "planned":
                        if st.button("Approve Event Rebalance to Session", key=f"approve_event_rebalance_{portfolio_id}"):
                            st.session_state[f"approved_event_rebalance_{portfolio_id}"] = event_result["rebalance_df"].to_dict(orient="records")
                            st.success("Event rebalance plan saved for approval workflow.")

    if ep2.button("Queue Alert Event", key=f"queue_alert_event_{portfolio_id}"):
        evt = event_engine.build_alert_event(
            portfolio_id=portfolio_id,
            title="Manual alert event",
            message="Portfolio manager created a manual alert event",
            priority="normal",
        )
        st.success(f"Queued event: {evt['event_type']}")

    if ep3.button("Clear Event Queue", key=f"clear_event_queue_{portfolio_id}"):
        event_engine.clear()
        st.success("Event queue cleared.")

    approved_event_rebalance = st.session_state.get(f"approved_event_rebalance_{portfolio_id}")
    if approved_event_rebalance:
        st.subheader("Approved Event Rebalance")
        approved_event_df = pd.DataFrame(approved_event_rebalance)
        st.dataframe(approved_event_df, use_container_width=True, hide_index=True)

        if st.button("Execute Approved Event Rebalance", key=f"execute_approved_event_rebalance_{portfolio_id}"):
            try:
                valid, reasons = guardrails.validate_rebalance_plan(
                    portfolio_id=portfolio_id,
                    rebalance_df=approved_event_df,
                    positions_df=df_pos if not df_pos.empty else pd.DataFrame(),
                    equity=float(totals.get("equity", 0.0)),
                    config=trading_cfg,
                )

                if not valid:
                    st.error("Execution blocked by guardrails:")
                    for reason in reasons:
                        st.write(f"- {reason}")
                else:
                    service = OrderService(db_session, broker, market_data_service)

                    for _, row in approved_event_df.iterrows():
                        service.submit_order(
                            portfolio_id=portfolio_id,
                            user_id=user_id,
                            symbol=str(row["Symbol"]).upper(),
                            side=str(row["Side"]).lower(),
                            qty=float(row["Qty"]),
                            order_type="market",
                            tif="day",
                        )

                    try:
                        run_service = StrategyRunService(db_session)
                        run_service.log_run(
                            portfolio_id=portfolio_id,
                            strategy_name="event_driven_execution",
                            trigger_type="event",
                            status="executed",
                            target_df=approved_event_df,
                            drift_threshold=None,
                            notes="Executed approved event-driven rebalance",
                        )
                    except Exception as log_err:
                        print("EVENT EXECUTION LOG ERROR:", log_err)

                    st.success("Approved event rebalance executed.")
                    st.session_state.pop(f"approved_event_rebalance_{portfolio_id}", None)
                    st.rerun()

            except Exception as e:
                st.error(f"Approved event rebalance failed: {e}")
    st.divider()
    st.header("Automation & Drift Rebalancing")

    automation = PortfolioAutomationService(constructor)

    drift_threshold = st.slider(
        "Drift Threshold",
        min_value=0.01,
        max_value=0.20,
        value=0.05,
        step=0.01,
        key=f"drift_threshold_{portfolio_id}",
    )

    min_trade_pct = st.slider(
        "Minimum Trade % of Portfolio",
        min_value=0.001,
        max_value=0.05,
        value=0.01,
        step=0.001,
        key=f"min_trade_pct_{portfolio_id}",
    )

    auto_execute = st.checkbox(
        "Allow one-click rebalance execution",
        value=False,
        key=f"auto_execute_flag_{portfolio_id}",
    )

    st.caption(
        "This version does not execute automatically in the background. It plans automatically and executes only on explicit confirmation.")

    ml_targets_saved = st.session_state.get(f"ml_target_df_{portfolio_id}")
    optimized_targets_saved = st.session_state.get(f"optimized_target_df_{portfolio_id}")
    combined_targets_saved = st.session_state.get(f"combined_target_df_{portfolio_id}")
    alpha_targets_saved = st.session_state.get(f"alpha_target_df_{portfolio_id}")

    automation_target_df = None

    if ml_targets_saved:
        automation_target_df = pd.DataFrame(ml_targets_saved)
    elif optimized_targets_saved:
        automation_target_df = pd.DataFrame(optimized_targets_saved)
    elif combined_targets_saved:
        automation_target_df = pd.DataFrame(combined_targets_saved)
    elif construction_target_df is not None and not construction_target_df.empty:
        automation_target_df = construction_target_df.copy()
    elif alpha_targets_saved:
        automation_target_df = pd.DataFrame(alpha_targets_saved)

        auto_prices: dict[str, float] = {}

        if not df_pos.empty:
            for _, row in df_pos.iterrows():
                sym = row.get("Symbol")
                px = row.get("Market Price")
                if sym and px is not None:
                    auto_prices[str(sym).upper()] = float(px)

        for sym in automation_target_df["Symbol"].tolist():
            if sym not in auto_prices:
                try:
                    q = market_data_service.get_quote(sym)
                    px = _safe_price_from_quote(q)
                    if px is not None:
                        auto_prices[sym] = px
                except Exception:
                    pass

        automation_result = automation.generate_rebalance_if_needed(
            target_df=automation_target_df,
            prices=auto_prices,
            portfolio_value=float(totals.get("equity", 0.0)),
            drift_threshold=float(drift_threshold),
            min_trade_pct=float(min_trade_pct),
        )

        drift_df = automation_result["drift_df"]
        automation_rebalance_df = automation_result["rebalance_df"]

        st.subheader("Drift Analysis")
        if drift_df is not None and not drift_df.empty:
            st.dataframe(drift_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No drift analysis available.")

        if automation_result["triggered"]:
            st.warning("Drift threshold exceeded. Rebalance recommended.")
        else:
            st.success("Portfolio is within drift threshold.")

        st.subheader("Automation Rebalance Plan")
        if automation_rebalance_df is not None and not automation_rebalance_df.empty:
            st.dataframe(automation_rebalance_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No rebalance trades required.")

        if automation_result["triggered"] and automation_rebalance_df is not None and not automation_rebalance_df.empty:
            exec_col1, exec_col2 = st.columns(2)

            if exec_col1.button("Approve Rebalance Plan", key=f"approve_rebalance_{portfolio_id}"):
                st.session_state[f"approved_rebalance_{portfolio_id}"] = automation_rebalance_df.to_dict(
                    orient="records")
                st.success("Rebalance plan approved for execution.")

            approved = st.session_state.get(f"approved_rebalance_{portfolio_id}")

            if approved:
                st.subheader("Approved Rebalance Plan")
                st.dataframe(pd.DataFrame(approved), use_container_width=True, hide_index=True)

                if exec_col2.button("Execute Approved Rebalance", key=f"execute_approved_rebalance_{portfolio_id}"):
                    try:
                        service = OrderService(db_session, broker, market_data_service)
                        approved_df = pd.DataFrame(approved)

                        valid, reasons = guardrails.validate_rebalance_plan(
                            portfolio_id=portfolio_id,
                            rebalance_df=approved_df,
                            positions_df=df_pos if not df_pos.empty else pd.DataFrame(),
                            equity=float(totals.get("equity", 0.0)),
                            config=trading_cfg,
                        )

                        if not valid:
                            st.error("Execution blocked by guardrails:")
                            for reason in reasons:
                                st.write(f"- {reason}")
                        else:
                            for _, row in approved_df.iterrows():
                                service.submit_order(
                                    portfolio_id=portfolio_id,
                                    user_id=user_id,
                                    symbol=str(row["Symbol"]).upper(),
                                    side=str(row["Side"]).lower(),
                                    qty=float(row["Qty"]),
                                    order_type="market",
                                    tif="day",
                                )

                            try:
                                run_service = StrategyRunService(db_session)
                                run_service.log_run(
                                    portfolio_id=portfolio_id,
                                    strategy_name="approved_rebalance",
                                    trigger_type="manual",
                                    status="executed",
                                    target_df=approved_df,
                                    drift_threshold=drift_threshold,
                                    notes="Executed with guardrails",
                                )
                            except Exception as log_err:
                                print("LOG ERROR:", log_err)

                            st.success("Approved rebalance executed.")
                            st.session_state.pop(f"approved_rebalance_{portfolio_id}", None)
                            st.rerun()

                    except Exception as e:
                        st.error(f"Execution failed: {e}")

        if auto_execute:
            st.info("One-click execution is enabled, but explicit confirmation is still required in this version.")
    else:
        st.caption(
            "No target weights available for automation. Generate targets from construction, alpha, or strategy sections first.")

    st.subheader("Strategy Run History")

    runs = []
    if StrategyRun is not None:
        try:
            runs = (
                db_session.query(StrategyRun)
                .filter(StrategyRun.portfolio_id == portfolio_id)
                .order_by(StrategyRun.created_at.desc())
                .limit(50)
                .all()
            )
        except Exception:
            runs = []

    if runs:
        df_runs = pd.DataFrame([
            {
                "Created": r.created_at,
                "Strategy": r.strategy_name,
                "Trigger": r.trigger_type,
                "Status": r.status,
                "Drift Threshold": r.drift_threshold,
                "Notes": r.notes,
            }
            for r in runs
        ])
        st.dataframe(df_runs, use_container_width=True, hide_index=True)
    else:
        st.caption("No strategy run history yet.")

    st.divider()
    st.header("Scheduler (Phase 11+)")

    alert_key = f"alert_service_{portfolio_id}"
    monitoring_key = f"monitoring_service_{portfolio_id}"
    scheduler_key = f"scheduler_{portfolio_id}"

    if alert_key not in st.session_state:
        st.session_state[alert_key] = AlertService()

    if monitoring_key not in st.session_state:
        st.session_state[monitoring_key] = MonitoringService()

    if scheduler_key not in st.session_state:
        st.session_state[scheduler_key] = PortfolioScheduler(
            db_session=db_session,
            market_data_service=market_data_service,
            constructor=constructor,
            user_id=user_id,
            broker=broker,
            alert_service=st.session_state[alert_key],
            monitoring_service=st.session_state[monitoring_key],
        )

    alert_service = st.session_state[alert_key]
    monitoring_service = st.session_state[monitoring_key]
    scheduler = st.session_state[scheduler_key]

    sc1, sc2, sc3 = st.columns(3)
    interval = sc1.slider("Interval (seconds)", 10, 300, 60, key=f"scheduler_interval_{portfolio_id}")

    if sc2.button("Start Scheduler", key=f"start_scheduler_{portfolio_id}"):
        scheduler.start(interval_seconds=interval)
        st.success("Scheduler started")

    if sc3.button("Stop Scheduler", key=f"stop_scheduler_{portfolio_id}"):
        scheduler.stop()
        st.warning("Scheduler stopped")

    st.caption("Runs strategy → drift → rebalance loop in background thread.")

    stale = monitoring_service.is_stale(max_age_seconds=max(interval * 2, 60))
    m1, m2, m3 = st.columns(3)
    m1.metric("Scheduler Running", "Yes" if scheduler.running else "No")
    m2.metric("Last Status", monitoring_service.last_cycle_status)
    m3.metric("Heartbeat", "Stale" if stale else "Fresh")

    if monitoring_service.last_heartbeat:
        st.caption(
            f"Last heartbeat: {monitoring_service.last_heartbeat} | "
            f"Message: {monitoring_service.last_cycle_message}"
        )

    st.divider()
    st.header("Alerts")

    alert_level = st.selectbox(
        "Filter Alerts",
        ["all", "info", "warning", "error"],
        key=f"alert_filter_{portfolio_id}",
    )

    if st.button("Clear Alerts", key=f"clear_alerts_{portfolio_id}"):
        try:
            alert_service.clear()
        except Exception:
            pass
        st.success("Alerts cleared")

    alerts = alert_service.list_alerts(None if alert_level == "all" else alert_level)

    if alerts:
        for alert in alerts[:25]:
            ts = alert["timestamp"]
            title = alert["title"]
            msg = alert["message"]
            source = alert["source"]
            level = alert["level"]

            if level == "error":
                st.error(f"[{ts}] {title} | {source} | {msg}")
            elif level == "warning":
                st.warning(f"[{ts}] {title} | {source} | {msg}")
            else:
                st.info(f"[{ts}] {title} | {source} | {msg}")
    else:
        st.caption("No alerts.")
        # ---------------------------------
        # PM COMMAND CENTER (Phase 20)
        # ---------------------------------

        if st.checkbox("Enable PM Command Center", key=f"pm_cc_toggle_{portfolio_id}"):

            # Gather required data
            alerts = []
            try:
                alerts = alert_service.list_alerts()
            except Exception:
                alerts = []

            rebalance_preview = pd.DataFrame()
            try:
                if 'rebalance_df' in locals():
                    rebalance_preview = rebalance_df
            except Exception:
                rebalance_preview = pd.DataFrame()

            df_pos = pd.DataFrame()
            render_pm_command_center(
                portfolio_id=portfolio_id,
                totals=totals,
                health=health if 'health' in locals() else {},
                drift_df=drift_live_df if 'drift_live_df' in locals() else pd.DataFrame(),
                sleeve_df=sleeve_df_live if 'sleeve_df_live' in locals() else pd.DataFrame(),
                optimized_df=optimized_df if 'optimized_df' in locals() else pd.DataFrame(),
                alerts=alerts,
                monitoring_service=monitoring_service if 'monitoring_service' in locals() else None,
                rebalance_df=rebalance_preview,
            )

    st.divider()




    render_api_ui(
        db_session=db_session,
        portfolio_id=portfolio_id,
        totals=totals,
        health=health if 'health' in locals() else {},
        df_pos=df_pos if not df_pos.empty else pd.DataFrame(),
        sleeve_df=sleeve_df_live if 'sleeve_df_live' in locals() else pd.DataFrame(),
        trades_df=rebalance_df if 'rebalance_df' in locals() else pd.DataFrame(),
        risk_df=risk_report_df if 'risk_report_df' in locals() else pd.DataFrame(),
    )
    st.divider()
    st.header("Execution Audit Feed")

    audit_df = monitoring_service.audit_df()
    if not audit_df.empty:
        st.dataframe(audit_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No audit events yet.")
