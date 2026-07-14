"""
modules/forex/forex_trading_desk_dashboard.py
"""
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
from modules.forex.forex_portfolio_manager import (
    get_forex_portfolio_manager,
)
from modules.forex.forex_watchlist_ai import ForexWatchlistAI
from modules.forex.forex_watchlist_factory import get_forex_watchlist_service

try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px

except Exception:
    st=None
    pd=None
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
from modules.forex.forex_trading_desk import get_forex_trading_desk
from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
from modules.forex.forex_order_management_engine import (
    get_forex_order_management_engine,
)
from modules.forex.forex_pending_orders_dashboard import (
    render_forex_pending_orders_dashboard,
)
from modules.forex.forex_positions_dashboard import (
    render_forex_positions_dashboard,
)
from modules.forex.forex_execution_dashboard_service import (
    ForexExecutionDashboardService,
)




class ForexTradingDeskDashboard:

    def __init__(self, db=None):
        self.db = db
        self.desk = get_forex_trading_desk(db=db)

    def _as_dict(self, value):
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if hasattr(value, "to_dict"):
            try:
                return value.to_dict()
            except Exception:
                return {}

        return {}

    def _list(self, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return []

    def _build_live_portfolio_packet(self, **kwargs):
        engine = get_forex_portfolio_engine(
            db=self.desk.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )

        snapshot = engine.get_terminal_snapshot(
            portfolio_id=kwargs.get("portfolio_id"),
            account_id=kwargs.get("account_id"),
            refresh=True,
            persist=True,
            include_orders=True,
            include_history=True,
        )

        portfolio = snapshot.portfolio or {}

        institutional_risk = portfolio.get(
            "institutional_risk",
            {},
        )

        portfolio_summary = institutional_risk.get(
            "portfolio_summary",
            {},
        )

        statistics = institutional_risk.get(
            "statistics",
            {},
        )

        parametric_var = institutional_risk.get(
            "parametric_var",
            {},
        )

        expected_shortfall = institutional_risk.get(
            "expected_shortfall",
            {},
        )

        terminal = self._as_dict(snapshot)

        account = terminal.get("account", {})
        portfolio = terminal.get("portfolio", {})
        margin = terminal.get("margin", {})
        risk = terminal.get("risk", {})
        risk = {
            **risk,

            "daily_var": parametric_var.get(
                "daily_var",
                0.0,
            ),

            "var_95": parametric_var.get(
                "daily_var",
                0.0,
            ),

            "daily_var_95": parametric_var.get(
                "daily_var",
                0.0,
            ),

            "var99": parametric_var.get(
                "var99",
                parametric_var.get(
                    "daily_var_99",
                    0.0,
                ),
            ),

            "expected_shortfall": expected_shortfall.get(
                "expected_shortfall",
                0.0,
            ),

            "expected_shortfall_95": expected_shortfall.get(
                "expected_shortfall",
                0.0,
            ),

            "gross_exposure": portfolio_summary.get(
                "gross_exposure",
                0.0,
            ),

            "net_exposure": portfolio_summary.get(
                "net_exposure",
                0.0,
            ),

            "directional": portfolio_summary.get(
                "directional",
                {},
            ),

            "currency_exposure": portfolio_summary.get(
                "currency_exposure",
                {},
            ),

            "effective_positions": portfolio_summary.get(
                "effective_positions",
                0.0,
            ),

            "diversification_ratio": portfolio_summary.get(
                "diversification_ratio",
                0.0,
            ),
        }
        performance = terminal.get("performance", {})
        positions = terminal.get("positions", [])
        currency_exposure = terminal.get("currency_exposure", [])
        pair_exposure = terminal.get("pair_exposure", [])

        summary = {
            "account_id": terminal.get("account_id"),
            "account_currency": account.get("account_currency", "USD"),
            "cash_balance": account.get("cash_balance", 0),
            "equity": account.get("equity", 0),
            "buying_power": margin.get("buying_power", margin.get("margin_available", 0)),
            "margin_used": margin.get("margin_used", 0),
            "margin_available": margin.get("margin_available", 0),
            "total_notional": portfolio.get("total_notional", 0),
            "total_market_value": portfolio.get("total_market_value", 0),
            "unrealized_pnl": portfolio.get("total_unrealized_pnl", 0),
            "realized_pnl": portfolio.get("total_realized_pnl", 0),
            "daily_pnl": performance.get("daily_pnl", 0),
            "open_positions": len(positions),
            "long_count": portfolio.get("long_count", 0),
            "short_count": portfolio.get("short_count", 0),
            "win_rate": performance.get("win_rate", 0),
            "gross_exposure": portfolio.get("total_notional", 0),
            "exposure_pct": portfolio.get("exposure_pct", 0),
            "risk_score": risk.get("risk_score", portfolio.get("risk_score", 0)),
            "leverage": margin.get("leverage", 0),

        }
        summary.update({

            "gross_exposure": risk.get("gross_exposure", 0),

            "net_exposure": risk.get("net_exposure", 0),

            "long_exposure": risk.get(
                "directional",
                {},
            ).get(
                "long",
                0,
            ),

            "short_exposure": risk.get(
                "directional",
                {},
            ).get(
                "short",
                0,
            ),

            "effective_positions": risk.get(
                "effective_positions",
                0,
            ),

            "diversification_ratio": risk.get(
                "diversification_ratio",
                0,
            ),

            "daily_var": risk.get(
                "daily_var",
                0,
            ),

            "expected_shortfall": risk.get(
                "expected_shortfall",
                risk.get(
                    "expected_shortfall_value",
                    0,
                ),
            ),
        })

        portfolio["summary"] = summary
        portfolio["positions"] = positions
        portfolio["currency_exposure"] = currency_exposure
        portfolio["pair_exposure"] = pair_exposure
        portfolio["performance"] = performance
        portfolio["margin"] = margin
        portfolio["risk"] = risk
        portfolio["system"] = terminal.get("system", {})

        watchlist_service = get_forex_watchlist_service(
            db=self.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )

        watchlist = watchlist_service.load_watchlist()

        pairs = [
            item.pair
            for item in watchlist.items
        ]

        quotes = self.desk.forex_service.get_quotes(
            pairs=pairs,
        )

        rows = []

        for pair, quote in quotes.items():
            rows.append({

                "pair": quote.pair,

                "bid": quote.bid,

                "ask": quote.ask,

                "mid": quote.mid,

                "spread": quote.spread,

                "provider": quote.provider,

                "volume": quote.volume,

                "timestamp": quote.timestamp,

                "source": quote.source,

            })

        print("=" * 100)
        print("LIVE PACKET")
        print("risk =", risk)
        print("institutional_risk =", institutional_risk)
        print("parametric_var =", parametric_var)
        print("expected_shortfall =", expected_shortfall)
        print("=" * 100)
        return {
            "portfolio": portfolio,
            "positions": positions,
            "currency_exposure": currency_exposure,
            "pair_exposure": pair_exposure,
            "risk": risk,
            "performance": performance,
            "margin": margin,
            "open_orders": terminal.get("open_orders", []),
            "filled_orders": terminal.get("filled_orders", []),
            "execution_history": terminal.get("execution_history", []),
            "cash_ledger": terminal.get("cash_ledger", []),
            "system": terminal.get("system", {}),

            "watchlist": rows,

             "providers": list(

        {

            row["provider"]

            for row in rows

            if row["provider"]

        }

    ),

    "provider_count": len(

        {

            row["provider"]

            for row in rows

            if row["provider"]

        }

    ),

    "latency_ms": 0,

    "signals": 0,

}

    def _execute_close_position(self, portfolio_engine, payload):
        try:
            return portfolio_engine.close_position(
                position_id=payload["position_id"],
                close_price=payload.get("close_price"),
            )
        except Exception as e:
            logger.exception("Close position failed: %s", e)
            return None

    def _execute_reverse_position(self, portfolio_engine, payload):
        """
        Reverse an existing position by:
            1. Closing the selected position
            2. Opening the opposite side using the same pair/units
        """

        try:

            position = portfolio_engine.get_position(
                position_id=payload["position_id"]
            )

            if position is None:
                raise ValueError(
                    f"Position {payload['position_id']} not found."
                )

            portfolio_engine.close_position(
                position_id=position.id,
                close_price=payload.get(
                    "close_price",
                    position.current_price,
                ),
            )

            opposite_side = (
                "SHORT"
                if position.side.upper() == "LONG"
                else "LONG"
            )

            return portfolio_engine.open_position(
                account_id=position.account_id,
                portfolio_id=position.portfolio_id,
                pair=position.pair,
                side=opposite_side,
                units=position.units,
                entry_price=payload.get(
                    "close_price",
                    position.current_price,
                ),
            )

        except Exception as exc:
            logger.exception(
                "Reverse position failed: %s",
                exc,
            )
            return None

    def _execute_flatten_all(self, portfolio_engine, portfolio_id):
        try:
            positions = portfolio_engine.list_positions(
                portfolio_id=portfolio_id,
                status="OPEN",
            )

            results = []
            for p in positions:
                results.append(
                    portfolio_engine.close_position(
                        position_id=p.id if hasattr(p, "id") else p["id"],
                        close_price=getattr(p, "current_price", None) if not isinstance(p, dict) else p.get(
                            "current_price"),
                    )
                )

            return results
        except Exception as e:
            logger.exception("Flatten failed: %s", e)
            return []

    def execute_trade_action(self, action: str, portfolio_engine, payload: dict):

        from modules.forex.forex_execution_job import ForexExecutionJob
        from modules.forex.forex_execution_queue import ForexExecutionQueue
        from modules.forex.forex_execution_audit import ForexExecutionAudit

        if not hasattr(self, "_exec_queue"):
            self._exec_queue = ForexExecutionQueue()

        if not hasattr(self, "_audit"):
            self._audit = ForexExecutionAudit()

        job = ForexExecutionJob(
            action=action,
            payload=payload
        )

        self._exec_queue.submit(job)

        result = self._exec_queue.process_next(
            executor=portfolio_engine
        )

        self._audit.log(
            job.id,
            action,
            payload,
            result,
            job.status
        )

        return result

    def _submit_forex_order(
            self,
            *,
            portfolio_engine,
            order_engine,
            kwargs,
            pair,
            side,
            units,
            stop_price=0.0,
            take_profit=0.0,
            limit_price=None,
            order_type="MARKET",
    ):

        # ---------------------------------------------------------
        # Resolve the active trading account
        # ---------------------------------------------------------

        account = portfolio_engine.get_account(
            portfolio_id=kwargs.get("portfolio_id"),
        )

        if account is None:
            st.error("No Forex account is available.")

            return {
                "status": "ERROR",
                "message": "No Forex account available.",
            }

        print("=" * 80)
        print("ORDER SUBMISSION")
        print("Portfolio :", account.portfolio_id)
        print("Account   :", account.id)
        print("Pair      :", pair)
        print("Side      :", side)
        print("Units     :", units)
        print("=" * 80)

        return order_engine.submit(
            pair=pair,
            side=side,
            units=units,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit=take_profit,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),

            # Always use the resolved account
            portfolio_id=account.portfolio_id,
            account_id=account.id,
        )

    def _get_order_context(
            self,
            *,
            portfolio_engine,
            kwargs,
    ) -> Dict[str, Any]:

        account = portfolio_engine.get_account(
            portfolio_id=kwargs.get("portfolio_id"),
        )

        if account is None:
            raise RuntimeError(
                "No Forex account available."
            )

        return {

            "account": account,

            "account_id": account.id,

            "portfolio_id": account.portfolio_id,

            "tenant_id": kwargs["tenant_id"],

            "user_id": kwargs["user_id"],

        }

    def render(self, **kwargs):

        tenant_id = kwargs.get("tenant_id")
        user_id = kwargs.get("user_id")
        portfolio_id = kwargs.get("portfolio_id")
        account_id = kwargs.get("account_id")

        #data = self.desk.dashboard(**kwargs)
        # ============================================================
        # Active Portfolio
        # ============================================================

        portfolio_manager = get_forex_portfolio_manager(
            db=self.desk.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )

        portfolios = portfolio_manager.portfolio_list()
        logger.debug("Forex portfolio list loaded: %s", portfolios)
        active = portfolio_manager.active_portfolio()

        if active:
            st.session_state.setdefault(
                "fx_active_portfolio_id",
                active["id"],
            )
            if portfolios:

                names = {
                    p["name"]: p["id"]
                    for p in portfolios
                }

                current_name = next(
                    (
                        p["name"]
                        for p in portfolios
                        if p["id"] ==
                           st.session_state["fx_active_portfolio_id"]
                    ),
                    list(names.keys())[0],
                )


                selected_name = st.selectbox(
                    "Trading Portfolio",
                    list(names.keys()),
                    index=list(names.keys()).index(current_name),
                    key="fx_active_portfolio_selector",
                )

                selected_id = names[selected_name]

                if (
                        selected_id !=
                        st.session_state["fx_active_portfolio_id"]
                ):
                    st.session_state[
                        "fx_active_portfolio_id"
                    ] = selected_id

                    portfolio_manager.set_default_portfolio(
                        selected_id
                    )
                    print("=" * 80)
                    print("TOP OF CLOSE DIALOG")
                    print("close_position_selected_id =",
                          st.session_state.get("close_position_selected_id"))
                    print("widget =",
                          st.session_state.get("close_position_selector_widget"))
                    print("=" * 80)
                    st.rerun()

                kwargs["portfolio_id"] = selected_id

            else:

                st.warning(
                    "No Forex portfolio exists. Please create one from the Portfolio workspace before trading."
                )

                st.stop()
        # =====================================================================
        # Sprint 26 Refactor
        # Single live portfolio packet for the render cycle.
        # Do NOT call self.desk.dashboard() here; it performs duplicate DB reads
        # and can trigger SQLAlchemy session provisioning conflicts.
        # =====================================================================
        live = self._build_live_portfolio_packet(**kwargs)

        data = dict(live or {})
        data.setdefault("portfolio", {})
        data.setdefault("risk", {})
        data.setdefault("performance", {})
        data.setdefault("open_orders", [])
        data.setdefault("filled_orders", [])
        data.setdefault("execution_history", [])
        data.setdefault("cash_ledger", [])
        data.setdefault("system", {})
        data.setdefault("execution", {})
        data.setdefault("executive_ai", {})
        data.setdefault("strategy_lab", {})
        data.setdefault("provider_health", {})
        data.setdefault("watchlist", [])
        data.setdefault(
            "generated_at",
            data.get("system", {}).get("generated_at", "--"),
        )

        order_engine = get_forex_order_management_engine(
            db=self.desk.db,
        )

        portfolio_engine = get_forex_portfolio_engine(
            db=self.desk.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )
        # ==========================================================
        # Live Market Quotes
        # ==========================================================

        watchlist_service = get_forex_watchlist_service(
            db=self.db,
            tenant_id=kwargs.get("tenant_id"),
            user_id=kwargs.get("user_id"),
            portfolio_id=kwargs.get("portfolio_id"),
        )

        watchlist = watchlist_service.load_watchlist()

        pairs = [
            item.pair
            for item in watchlist.items
        ]

        quotes = data.get("watchlist", [])

        portfolio = data.get("portfolio", {})
        summary = portfolio.get("summary", {})
        execution = data.get("execution", {})
        risk = data.get("risk", {})
        ai = data.get("executive_ai", {})
        strategy = data.get("strategy_lab", {})
        provider_health = data.get("provider_health", {})

        if st is None:
            return data

        with st.sidebar:

            st.subheader("Trading Session")

            st.metric(

                "Market",

                "FOREX"

            )

            st.metric(

                "Runtime",

                data.get(

                    "generated_at",

                    "--"

                )

            )

            st.metric(

                "Open Positions",

                summary.get(

                    "open_positions",

                    0,

                )

            )

            st.metric(

                "Risk Score",

                risk.get(
                    "risk_score",
                    0,
                ),

            )

            st.metric(

                "Win Rate",

                f"{summary.get('win_rate', 0):.1f}%"

            )

            st.divider()

            st.write("Quick Launch")

            st.button(

                "New Trade",

                use_container_width=True,

            )

            st.button(

                "AI Scanner",

                use_container_width=True,

            )

            st.button(

                "Portfolio",

                use_container_width=True,

            )

            st.button(

                "Risk",

                use_container_width=True,

            )

            st.button(

                "Execution",

                use_container_width=True,

            )

            st.button(

                "Refresh",

                use_container_width=True,

            )

        st.header("Forex Trading Desk")
        # ==============================================================
        # Bloomberg Header
        # ==============================================================



        st.caption("Institutional FX Trading Terminal")

        hdr1, hdr2, hdr3, hdr4, hdr5, hdr6 = st.columns(6)

        hdr1.metric(

            "Equity",

            f"${summary.get('equity', 0):,.2f}"

        )

        hdr2.metric(

            "Buying Power",

            f"${summary.get('buying_power', 0):,.2f}"

        )

        hdr3.metric(

            "Risk",

            risk.get(

                "risk_score",

                "--"

            )

        )

        hdr4.metric(

            "AI",

            ai.get(

                "market_bias",

                "Neutral"

            )

        )

        hdr5.metric(

            "Execution",

            execution.get(

                "fill_rate",

                0

            )

        )

        hdr6.metric(

            "Runtime",

            data.get(

                "generated_at",

                "--"

            )

        )

        st.divider()
        status_cols = st.columns(8)

        status_cols[0].success("● Market Open")

        status_cols[1].info(

            f"Pairs : {summary.get('open_positions', 0)}"

        )

        status_cols[2].info(

            f"Orders : {len(data.get('open_orders', []))}"

        )

        status_cols[3].info(

            f"Signals : {strategy.get('buy_signals', 0)}"

        )
        ai = data.get("executive_ai", {})
        strategy = data.get("strategy_lab", {})
        status_cols[4].info(

             f"Providers : {data.get('provider_count', 0)}"

        )

        status_cols[5].info(

            f"Latency : {execution.get('latency_ms', 0)} ms"

        )

        status_cols[6].info(

            f"Spread : {execution.get('avg_spread', 0)}"

        )

        status_cols[7].success("AI ONLINE")

        st.divider()

        watchlist = watchlist_service.load_watchlist()

        watchlist_ai = ForexWatchlistAI(
            portfolio_engine=portfolio_engine,
            order_engine=order_engine,
        )

        account_data = data.get("account", {})

        account_id = (
                account_data.get("id")
                or data.get("account_id")
                or kwargs.get("account_id")
        )

        rows = watchlist_ai.enrich_watchlist(
            watchlist=watchlist,
            account_id=account_id,
        )
        # ==========================================================
        # Live Market
        # ==========================================================

        st.subheader("Live Market")
        print("=" * 80)
        print("AI WATCHLIST")
        print(type(rows))
        print(len(rows) if isinstance(rows, list) else rows)

        if isinstance(rows, list):
            for r in rows[:5]:
                print(r)

        print("=" * 80)
        # Reuse the AI-enriched watchlist rows created in the
        # Forex Watchlist section.
        quotes = live.get("watchlist", [])
        print(type(quotes))
        print(len(quotes))
        print(quotes)
        print("=" * 80)
        if quotes:

            ticker = pd.DataFrame(quotes)

            preferred = [

                "pair",

                "bid",

                "ask",

                "mid",

                "spread",

                "provider",

                "volume",

                "timestamp",

            ]

            cols = [

                c

                for c in preferred

                if c in ticker.columns

            ]

            ticker = ticker[cols].copy()

            # --------------------------------------------
            # Formatting
            # --------------------------------------------

            if "bid" in ticker.columns:
                ticker["bid"] = ticker["bid"].map(lambda x: f"{x:.5f}")

            if "ask" in ticker.columns:
                ticker["ask"] = ticker["ask"].map(lambda x: f"{x:.5f}")

            if "mid" in ticker.columns:
                ticker["mid"] = ticker["mid"].map(lambda x: f"{x:.5f}")

            if "spread" in ticker.columns:
                ticker["spread"] = ticker["spread"].map(lambda x: f"{x:.5f}")

            if "volume" in ticker.columns:
                ticker["volume"] = ticker["volume"].map(lambda x: f"{x:,.0f}")

            ticker.rename(

                columns={

                    "pair": "Pair",

                    "bid": "Bid",

                    "ask": "Ask",

                    "mid": "Mid",

                    "spread": "Spread",

                    "provider": "Provider",

                    "volume": "Volume",

                    "timestamp": "Updated",

                },

                inplace=True,

            )

            st.dataframe(

                ticker,

                use_container_width=True,

                hide_index=True,

                height=220,

            )

        else:

            st.info(

                "No live market data available."

            )

        st.divider()



        c1,c2,c3,c4=st.columns(4)
        pf=data.get("portfolio",{}).get("summary",{})
        c1.metric("Positions",pf.get("open_positions",0))
        c2.metric("Notional",f"{pf.get('total_notional',0):,.0f}")
        c3.metric("Unrealized P&L",f"{pf.get('unrealized_pnl',0):,.2f}")
        c4.metric("Win Rate",f"{pf.get('win_rate',0)}%")

        ws=st.radio(
            "Trading Desk Workspace",
            [
                "Portfolio",
                "Orders",
                "Risk",
                "Performance",
                "Strategy",
                "Journal",
                "Providers",
                "Pending Orders (Detail)",
                "Live Positions (Detail)",
            ],
            horizontal=True,
        )

        if ws == "Portfolio":

            st.error("ACTIVE PORTFOLIO BLOCK")
            print("=" * 80)
            print("ACTIVE PORTFOLIO BLOCK")
            print("=" * 80)

            portfolio = data.get("portfolio", {})

            summary = portfolio.get("summary", {})

            positions = portfolio.get("positions", [])

            currency_exposure = portfolio.get("currency_exposure", [])
            pair_exposure = portfolio.get("pair_exposure", [])
            performance = portfolio.get("performance", {})
            margin = portfolio.get("margin", {})
            risk = portfolio.get("risk", {})

            exposure = {
                row.get("currency"): row.get("gross_exposure", row.get("net_exposure", 0))
                for row in currency_exposure
                if isinstance(row, dict)
            }

            account_currency = portfolio.get(
                "account_currency",
                "USD",
            )

            st.subheader("Portfolio Overview")

            # ==========================================================
            # Executive KPI Cards
            # ==========================================================

            row1 = st.columns(8)

            row1[0].metric(
                "Portfolio Value",
                f"{summary.get('equity', 0):,.2f}",
            )

            row1[1].metric(
                "Cash",
                f"{summary.get('cash_balance', 0):,.2f}",
            )

            row1[2].metric(
                "Buying Power",
                f"{summary.get('buying_power', 0):,.2f}",
            )

            row1[3].metric(
                "Margin Used",
                f"{summary.get('margin_used', 0):,.2f}",
            )

            row1[4].metric(
                "Free Margin",
                f"{summary.get('margin_available', 0):,.2f}",
            )

            row1[5].metric(
                "Open Positions",
                summary.get(
                    "open_positions",
                    len(positions),
                ),
            )

            # ---------------------------------------------------------
            # Daily P&L Metric
            # ---------------------------------------------------------

            daily_pnl = summary.get("daily_pnl", 0.0)

            # If daily_pnl is now a history list, use the latest value
            if isinstance(daily_pnl, list):

                if daily_pnl:

                    latest = daily_pnl[-1]

                    if isinstance(latest, dict):

                        daily_pnl = latest.get("pnl", 0.0)

                    else:

                        daily_pnl = 0.0

                else:

                    daily_pnl = 0.0

            # ---------------------------------------------------------
            # Daily P&L Metric
            # ---------------------------------------------------------

            daily_pnl = summary.get("daily_pnl", 0.0)

            # If daily_pnl is now a history list, use the latest value
            if isinstance(daily_pnl, list):

                if daily_pnl:

                    latest = daily_pnl[-1]

                    if isinstance(latest, dict):

                        daily_pnl = latest.get("pnl", 0.0)

                    else:

                        daily_pnl = 0.0

                else:

                    daily_pnl = 0.0

            row1[6].metric(
                "Daily P&L",
                f"{float(daily_pnl):,.2f}",
            )

            row1[7].metric(
                "Win Rate",
                f"{summary.get('win_rate', 0):.1f}%",
            )

            st.divider()

            # ==========================================================
            # Equity / Exposure
            # ==========================================================

            left, right = st.columns([2, 1])

            with left:

                st.subheader("Equity Curve")

                equity_history = performance.get(
                    "equity_curve",
                    [],
                )

                if equity_history and pd is not None:

                    df = pd.DataFrame(equity_history)

                    if "equity" in df.columns:

                        st.line_chart(
                            df["equity"]
                        )

                    else:

                        st.line_chart(df)

                else:

                    st.info(
                        "No equity history available."
                    )

            with right:

                st.subheader(
                    "Currency Exposure"
                )

                if exposure and pd is not None:

                    exp_df = pd.DataFrame(

                        {

                            "Currency":

                                list(exposure.keys()),

                            "Exposure":

                                list(exposure.values()),

                        }

                    )

                    st.dataframe(

                        exp_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                    try:

                        st.plotly_chart(

                            px.pie(

                                exp_df,

                                names="Currency",

                                values="Exposure",

                                hole=.55,

                            ),

                            use_container_width=True,

                        )

                    except Exception:

                        pass

                else:

                    st.info(
                        "No currency exposure."
                    )

            st.divider()

            # ==========================================================
            # Risk / Exposure / Daily P&L
            # ==========================================================

            c1, c2, c3 = st.columns(3)

            with c1:

                st.subheader(
                    "Exposure Summary"
                )

                st.metric(

                    "Gross Exposure",

                    f"{summary.get('gross_exposure', 0):,.2f}",

                )

                st.metric(

                    "Long Exposure",

                    f"{summary.get('long_exposure', 0):,.2f}",

                )

                st.metric(

                    "Short Exposure",

                    f"{summary.get('short_exposure', 0):,.2f}",

                )

            with c2:

                st.subheader("Daily Performance")

                equity = performance.get(
                    "equity_history",
                    [],
                )

                if equity:

                    df = pd.DataFrame(equity)

                    if "equity" in df.columns:
                        df["daily_pnl"] = df["equity"].diff()

                        st.bar_chart(
                            df["daily_pnl"].fillna(0)
                        )

                else:

                    st.info(
                        "No P&L history."
                    )

            with c3:

                st.subheader(
                    "Risk Summary"
                )

                risk = data.get(

                    "risk",

                    {},

                )

                st.metric(

                    "Risk Score",

                    risk.get(
                        "risk_score",
                        0,
                    ),

                )

                var95 = (
                        risk.get("daily_var")
                        or risk.get("var_95")
                        or risk.get("daily_var_95")
                        or 0
                )

                st.metric(
                    "VaR (95%)",
                    f"${risk.get('daily_var', risk.get('var_95', 0)):,.2f}",
                )

                st.metric(
                    "Expected Shortfall",
                    f"${risk.get('expected_shortfall', risk.get('expected_shortfall_value', 0)):,.2f}",
                )

                st.metric(
                    "Drawdown",
                    f"{risk.get('drawdown', 0):.2f}%",
                )

                st.metric(
                    "Leverage",
                    f"{margin.get('leverage', 0):.2f}x",
                )

            st.divider()

            # ==========================================================
            # Open Positions
            # ==========================================================

            st.subheader("Open Positions")

            positions = portfolio.get("positions", [])

            if positions:

                df = pd.DataFrame(positions)

                preferred = [

                    "pair",
                    "side",
                    "quantity",
                    "avg_price",
                    "market_price",
                    "market_value",
                    "unrealized_pnl",
                    "realized_pnl",
                    "day_pnl",
                    "exposure",
                    "leverage",
                    "margin_required",

                ]

                cols = [

                    c for c in preferred
                    if c in df.columns

                ]

                if cols:
                    df = df[cols]

                st.dataframe(

                    df,

                    use_container_width=True,

                    hide_index=True,

                    height=420,

                )

            else:

                st.info("No open positions.")

            st.divider()
            st.subheader("Closed Positions")

            closed_positions = portfolio.get("closed_positions", [])

            if closed_positions:

                df = pd.DataFrame(closed_positions)

                preferred = [
                    "pair",
                    "side",
                    "units",
                    "avg_entry_price",
                    "exit_price",
                    "realized_pnl",
                    "opened_at",
                    "closed_at",
                ]

                cols = [c for c in preferred if c in df.columns]

                if cols:
                    df = df[cols]

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    height=300,
                )

            else:
                st.info("No closed positions.")

            st.divider()

            # ==========================================================
            # Recent Activity
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Recent Orders"

                )

                orders = (
                        data.get("filled_orders", [])
                        + data.get("open_orders", [])
                )

                orders = sorted(
                    orders,
                    key=lambda x: (
                            x.get("filled_at")
                            or x.get("submitted_at")
                            or x.get("created_at")
                            or ""
                    ),
                    reverse=True,
                )

                if orders:

                    st.dataframe(

                        pd.DataFrame(

                            orders

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No orders."

                    )

            with right:

                st.subheader(

                    "Recent Activity"

                )

                activity = data.get(
                    "execution_history",
                    [],
                )

                activity = sorted(
                    activity,
                    key=lambda x: (
                            x.get("executed_at")
                            or x.get("created_at")
                            or ""
                    ),
                    reverse=True,
                )

                if activity:

                    st.dataframe(

                        pd.DataFrame(

                            activity

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No recent activity."

                    )

            st.divider()

            # ==========================================================
            # Quick Actions
            # ==========================================================

            st.subheader(
                "Quick Actions"
            )

            a, b, c, d, e, f = st.columns(6)

            # ==========================================================
            # New Order
            # ==========================================================

            if a.button(

                    "New Order",

                    key="portfolio_new_order_btn",

                    use_container_width=True,

            ):
                st.session_state["forex_show_order_ticket"] = True

                print("=" * 80)
                print("TOP OF CLOSE DIALOG")
                print("close_position_selected_id =",
                      st.session_state.get("close_position_selected_id"))
                print("widget =",
                      st.session_state.get("close_position_selector_widget"))
                print("=" * 80)
                st.rerun()

            # ==========================================================
            # Close Position
            # ==========================================================

            if b.button(

                    "Close Position",

                    key="portfolio_close_position_btn",

                    use_container_width=True,

            ):
                st.session_state["forex_close_position"] = True
                print("=" * 80)
                print("TOP OF CLOSE DIALOG")
                print("close_position_selected_id =",
                      st.session_state.get("close_position_selected_id"))
                print("widget =",
                      st.session_state.get("close_position_selector_widget"))
                print("=" * 80)
                st.rerun()

            # ==========================================================
            # Reverse Position
            # ==========================================================

            if c.button("Reverse", key="portfolio_reverse_btn", use_container_width=True):

                positions = portfolio.get("positions", [])

                if positions:
                    result = self.execute_trade_action(
                        "REVERSE_POSITION",
                        portfolio_engine,
                        {
                            "position": positions[0],
                        },
                    )

                    if result:
                        st.success("Position reversed")
                        print("=" * 80)
                        print("TOP OF CLOSE DIALOG")
                        print("close_position_selected_id =",
                              st.session_state.get("close_position_selected_id"))
                        print("widget =",
                              st.session_state.get("close_position_selector_widget"))
                        print("=" * 80)
                        st.rerun()
                    else:
                        st.error("Reverse failed")

            # ==========================================================
            # Flatten Portfolio
            # ==========================================================

            if d.button("Flatten", key="portfolio_flatten_btn", use_container_width=True):

                result = self.execute_trade_action(
                    "FLATTEN",
                    portfolio_engine,
                    {
                        "portfolio_id": kwargs.get("portfolio_id"),
                    },
                )

                if result is not None:
                    st.success("Portfolio flattened")
                    print("=" * 80)
                    print("TOP OF CLOSE DIALOG")
                    print("close_position_selected_id =",
                          st.session_state.get("close_position_selected_id"))
                    print("widget =",
                          st.session_state.get("close_position_selector_widget"))
                    print("=" * 80)
                    st.rerun()
                else:
                    st.error("Flatten failed")

            # ==========================================================
            # AI Trade
            # ==========================================================

            if e.button(
                    "AI Trade",
                    key="portfolio_ai_trade_btn",
                    use_container_width=True,
            ):
                # Reset other dialog state
                st.session_state["close_position_selected_id"] = None
                st.session_state["close_position_selector_widget"] = None

                # Launch AI Trade dialog
                st.session_state["ai_trade_new_order"] = True

                print("=" * 80)
                print("AI TRADE BUTTON")
                print(
                    "ai_trade_new_order =",
                    st.session_state.get("ai_trade_new_order"),
                )
                print("=" * 80)

                st.rerun()

            # ==========================================================
            # Refresh
            # ==========================================================

            if f.button(

                    "Refresh",

                    key="portfolio_refresh_btn",

                    use_container_width=True,

            ):
                print("=" * 80)
                print("TOP OF CLOSE DIALOG")
                print("close_position_selected_id =",
                      st.session_state.get("close_position_selected_id"))
                print("widget =",
                      st.session_state.get("close_position_selector_widget"))
                print("=" * 80)
                st.rerun()

            action = st.session_state.pop(

                "forex_trade_action",

                None,

            )
            if st.session_state.get(
                    "forex_show_order_ticket",
                    False,
            ):
                # ==========================================================
                # Institutional Order Ticket
                # ==========================================================

                st.divider()

                with st.container(border=True):

                    st.subheader(
                        "Institutional Forex Order Ticket"
                    )

                    c1, c2, c3 = st.columns(3)

                    pair = c1.selectbox(

                        "Currency Pair",

                        [

                            "EUR/USD",
                            "GBP/USD",
                            "USD/JPY",
                            "USD/CHF",
                            "AUD/USD",
                            "NZD/USD",
                            "USD/CAD",

                        ],

                        key="ticket_pair",

                    )

                    side = c2.radio(

                        "Side",

                        [

                            "BUY",
                            "SELL",

                        ],

                        horizontal=True,

                        key="ticket_side",

                    )

                    order_type = c3.selectbox(

                        "Order Type",

                        [

                            "MARKET",
                            "LIMIT",
                            "STOP",

                        ],

                        key="ticket_type",

                    )

                    st.divider()

                    c1, c2, c3 = st.columns(3)

                    quantity = c1.number_input(

                        "Units",

                        min_value=1000,

                        value=10000,

                        step=1000,

                        key="ticket_units",

                    )

                    limit_price = c2.number_input(

                        "Limit Price",

                        value=0.0,

                        format="%.5f",

                        key="ticket_limit",

                    )

                    stop_price = c3.number_input(

                        "Stop Loss",

                        value=0.0,

                        format="%.5f",

                        key="ticket_stop",

                    )

                    c1, c2 = st.columns(2)

                    take_profit = c1.number_input(

                        "Take Profit",

                        value=0.0,

                        format="%.5f",

                        key="ticket_tp",

                    )

                    account = c2.text_input(

                        "Account",

                        value="PAPER",

                        disabled=True,

                    )

                    st.divider()

                    preview = st.columns(4)

                    preview[0].metric(
                        "Units",
                        f"{quantity:,.0f}",
                    )

                    preview[1].metric(
                        "Side",
                        side,
                    )

                    preview[2].metric(
                        "Order",
                        order_type,
                    )

                    preview[3].metric(
                        "Portfolio",
                        kwargs.get(
                            "portfolio_id",
                            "--",
                        ),
                    )

                    st.divider()

                    left, right = st.columns(2)

                    submit = left.button(

                        "Submit Order",

                        key="ticket_submit",

                        use_container_width=True,

                    )

                    cancel = right.button(

                        "Cancel",

                        key="ticket_cancel",

                        use_container_width=True,

                    )

                    if cancel:
                        st.session_state[
                            "forex_show_order_ticket"
                        ] = False
                        print("=" * 80)
                        print("TOP OF CLOSE DIALOG")
                        print("close_position_selected_id =",
                              st.session_state.get("close_position_selected_id"))
                        print("widget =",
                              st.session_state.get("close_position_selector_widget"))
                        print("=" * 80)
                        print("=" * 80)
                        print("TOP OF CLOSE DIALOG")
                        print("close_position_selected_id =",
                              st.session_state.get("close_position_selected_id"))
                        print("widget =",
                              st.session_state.get("close_position_selector_widget"))
                        print("=" * 80)
                        st.rerun()

                    if submit:

                        with st.spinner("Submitting order..."):

                            account = portfolio_engine.get_account(
                                portfolio_id=kwargs.get("portfolio_id"),
                            )

                            if account is None:

                                st.error("No Forex account is available.")

                                return

                            print("=" * 80)
                            print("NEW ORDER SUBMISSION")
                            print("Portfolio :", account.portfolio_id)
                            print("Account   :", account.id)
                            print("Pair      :", pair)
                            print("Side      :", side)
                            print("OrderType :", order_type)
                            print("Units     :", quantity)
                            print("=" * 80)

                            result = order_engine.submit(
                                pair=pair,
                                side=side,
                                units=quantity,
                                order_type=order_type,
                                limit_price=(
                                    limit_price
                                    if order_type == "LIMIT"
                                    else None
                                ),
                                stop_price=stop_price,
                                take_profit=take_profit,

                                tenant_id=kwargs.get("tenant_id"),
                                user_id=kwargs.get("user_id"),

                                # Always use the active account
                                portfolio_id=account.portfolio_id,
                                account_id=account.id,
                            )


                        if str(result.get("status", "")).upper() in (

                                "FILLED",

                                "SUBMITTED",

                                "ACCEPTED",

                        ):

                            st.success(

                                result.get(

                                    "message",

                                    "Order submitted.",

                                )

                            )

                            st.session_state[
                                "forex_show_order_ticket"
                            ] = False
                            print("=" * 80)
                            print("TOP OF CLOSE DIALOG")
                            print("close_position_selected_id =",
                                  st.session_state.get("close_position_selected_id"))
                            print("widget =",
                                  st.session_state.get("close_position_selector_widget"))
                            print("=" * 80)
                            st.rerun()

                        else:

                            st.error(

                                result.get(

                                    "message",

                                    "Order failed.",

                                )

                            )
            if st.session_state.get("forex_close_position", False):

                st.divider()
                st.subheader("Close Position")

                positions = portfolio.get("positions", [])

                print("=" * 80)
                print("CLOSE DIALOG POSITIONS")
                for i, p in enumerate(positions):
                    print(
                        i,
                        p.get("id"),
                        p.get("pair"),
                        p.get("status"),
                        p.get("units"),
                    )
                print("=" * 80)

                if not positions:
                    st.info("No open positions.")

                else:

                    position_df = pd.DataFrame(positions)

                    display = position_df[
                        [
                            c
                            for c in [
                            "id",
                            "pair",
                            "side",
                            "units",
                            "avg_entry_price",
                            "current_price",
                            "unrealized_pnl",
                        ]
                            if c in position_df.columns
                        ]
                    ]

                    st.dataframe(
                        display,
                        use_container_width=True,
                        hide_index=True,
                    )

                    # ==========================================================
                    # Build stable lookup keyed ONLY by position id
                    # ==========================================================

                    position_rows = sorted(
                        [row.to_dict() for _, row in position_df.iterrows()],
                        key=lambda r: (
                            str(r["pair"]),
                            str(r["id"]),
                        ),
                    )

                    position_lookup = {
                        row["id"]: row
                        for row in position_rows
                    }

                    position_ids = list(position_lookup.keys())

                    print("=" * 80)
                    print("SELECTBOX OPTIONS")
                    for i, pid in enumerate(position_ids):
                        p = position_lookup[pid]
                        print(
                            i,
                            pid,
                            p["pair"],
                            p["side"],
                            p["units"],
                        )
                    print("=" * 80)

                    # ==========================================================
                    # Initialize persistent selected id
                    # ==========================================================

                    if (
                            "close_position_selected_id"
                            not in st.session_state
                            or st.session_state["close_position_selected_id"]
                            not in position_lookup
                    ):
                        st.session_state["close_position_selected_id"] = position_ids[0]

                    # ==========================================================
                    # Sync callback
                    # ==========================================================

                    def _close_position_changed():
                        st.session_state["close_position_selected_id"] = (
                            st.session_state["close_position_selector_widget"]
                        )

                        print("=" * 80)
                        print("CALLBACK")
                        print(
                            "selected:",
                            st.session_state["close_position_selected_id"],
                        )
                        print("=" * 80)

                    # ==========================================================
                    # Selectbox
                    # ==========================================================
                    print("=" * 80)
                    print("POSITION_DF")
                    print(position_df[["pair", "id"]])
                    print("=" * 80)

                    print("=" * 80)
                    print("LOOKUP KEYS")
                    print(list(position_lookup.keys()))
                    print("=" * 80)

                    print("=" * 80)
                    print("POSITION_IDS")
                    print(position_ids)
                    print("=" * 80)
                    selected_position_id = st.selectbox(
                        "Position",
                        options=position_ids,
                        index=position_ids.index(
                            st.session_state["close_position_selected_id"]
                        ),
                        key="close_position_selector_widget",
                        on_change=_close_position_changed,
                        format_func=lambda pid: (
                            f"{position_lookup[pid]['pair']} | "
                            f"{position_lookup[pid]['side']} | "
                            f"{position_lookup[pid]['units']:,.0f} units | "
                            f"{pid}"
                        ),
                    )

                    # Always trust the session copy
                    selected_position_id = st.session_state[
                        "close_position_selected_id"
                    ]

                    selected_position = position_lookup[selected_position_id]

                    st.write("Widget value:", selected_position_id)

                    print("=" * 80)
                    print("SESSION")
                    print(st.session_state["close_position_selected_id"])
                    print("=" * 80)

                    print("=" * 80)
                    print("SELECTBOX RETURNED")
                    print(selected_position_id)
                    print("=" * 80)

                    print("=" * 80)
                    print("SELECTED FROM UI")
                    print("id   :", selected_position["id"])
                    print("pair :", selected_position["pair"])
                    print("side :", selected_position["side"])
                    print("=" * 80)

                    print("=" * 80)
                    print("BUTTON PRESS STATE")
                    print("selected_id   :", selected_position_id)
                    print(
                        "session value :",
                        st.session_state["close_position_selected_id"],
                    )
                    print("=" * 80)

                    if st.button(
                            "Close Selected Position",
                            key="close_execute_btn",
                    ):

                        print("=" * 80)
                        print("BUTTON CLICKED")
                        print("selected_id   :", selected_position_id)
                        print(
                            "session value :",
                            st.session_state["close_position_selected_id"],
                        )
                        print("=" * 80)

                        payload = {
                            "position_id": selected_position_id,
                            "close_price": selected_position.get("current_price"),
                        }

                        print("=" * 80)
                        print("PAYLOAD GOING TO QUEUE")
                        print(payload)
                        print("=" * 80)

                        result = self.execute_trade_action(
                            "CLOSE_POSITION",
                            portfolio_engine,
                            payload,
                        )

                        if result:

                            st.success("Position closed successfully.")

                            # Remove stale widget state
                            st.session_state.pop(
                                "close_position_selector_widget",
                                None,
                            )

                            st.session_state.pop(
                                "close_position_selected_id",
                                None,
                            )

                            st.session_state["forex_close_position"] = False
                            print("=" * 80)
                            print("TOP OF CLOSE DIALOG")
                            print("close_position_selected_id =",
                                  st.session_state.get("close_position_selected_id"))
                            print("widget =",
                                  st.session_state.get("close_position_selector_widget"))
                            print("=" * 80)
                            st.rerun()

                        else:
                            st.error("Close position failed.")

            # ==========================================================
            # AI Trade Dialog
            # Phase 2
            # ==========================================================

            if st.session_state.get("ai_trade_new_order", False):

                @st.dialog("AI Assisted Trade", width="large")
                def render_ai_trade_dialog():

                    st.subheader("AI Trade Setup")

                    account = portfolio_engine.get_account(
                        portfolio_id=kwargs.get("portfolio_id"),
                    )

                    if account is None:
                        st.error("No Forex account is available.")

                        if st.button(
                                "Close",
                                key="ai_trade_close_no_account",
                                use_container_width=True,
                        ):
                            #st.session_state["ai_trade_new_order"] = False
                            st.rerun()

                        return

                    left, right = st.columns(2)

                    with left:

                        st.text_input(
                            "Account",
                            value=account.account_name,
                            disabled=True,
                            key="ai_trade_account_name",
                        )

                        # ----------------------------------------------------------
                        # Load watchlist pairs
                        # ----------------------------------------------------------

                        pairs = watchlist_service.get_pairs_for_ui()

                        if not pairs:
                            watchlist_service.seed_all_pairs()

                            pairs = watchlist_service.get_pairs_for_ui()

                        # ----------------------------------------------------------
                        # Currency Pair
                        # ----------------------------------------------------------

                        default_pair = st.session_state.get(
                            "ai_trade_pair"
                        )

                        if default_pair not in pairs:
                            default_pair = pairs[0]

                        pair = st.selectbox(

                            "Currency Pair",

                            options=pairs,

                            index=pairs.index(default_pair),

                            key="ai_trade_pair",

                        )

                        current_pair = st.session_state.get(
                            "ai_trade_previous_pair"
                        )

                        if current_pair != pair:
                            st.session_state["ai_trade_previous_pair"] = pair

                            st.session_state.pop(
                                "ai_trade_recommendation",
                                None,
                            )
                            st.session_state["ai_trade_previous_pair"] = pair

                        risk_pct = st.select_slider(
                            "Risk Per Trade",
                            options=[
                                0.25,
                                0.50,
                                1.00,
                                2.00,
                            ],
                            value=1.00,
                            format_func=lambda value: f"{value:.2f}%",
                            key="ai_trade_risk_pct",
                        )
                        recommendation = st.session_state.get(
                            "ai_trade_recommendation"
                        )

                    with right:

                        st.metric(
                            "Cash",
                            f"${account.cash_balance:,.2f}",
                        )

                        st.metric(
                            "Equity",
                            f"${account.equity:,.2f}",
                        )

                        st.metric(
                            "Buying Power",
                            f"${account.margin_available:,.2f}",
                        )

                        st.metric(
                            "Leverage",
                            f"{account.leverage:.1f}x",
                        )



                    st.divider()

                    if st.button(
                            "Analyze Trade",
                            key="ai_trade_analyze",
                            use_container_width=True,
                    ):

                        try:

                            #
                            # Clear any previous recommendation first
                            #
                            st.session_state.pop(
                                "ai_trade_recommendation",
                                None,
                            )

                            recommendation = portfolio_engine.recommend_position_from_signal(
                                account_id=account.id,
                                pair=pair,
                                risk_pct=float(risk_pct),
                            )

                            if recommendation is None:
                                st.error(
                                    "The AI was unable to generate a recommendation."
                                )

                                return

                            print("=" * 80)
                            print("AI RECOMMENDATION")
                            print(type(recommendation))
                            print(recommendation)
                            print("=" * 80)

                            st.session_state["ai_trade_recommendation"] = recommendation

                            st.rerun()

                        except Exception as exc:

                            st.exception(exc)

                    recommendation = st.session_state.get(
                        "ai_trade_recommendation"
                    )

                    signal = recommendation.get("signal", {}) if recommendation else {}
                    sizing = recommendation.get("sizing", {}) if recommendation else {}
                    recommended_side = (
                        recommendation.get("recommended_side")
                        if recommendation
                        else None
                    )
                    can_open = (
                        recommendation.get("can_open_position", False)
                        if recommendation
                        else False
                    )

                    if recommendation:

                        st.divider()

                        st.subheader("AI Recommendation")

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            st.metric(
                                "Recommendation",
                                signal.get("recommendation", "-"),
                            )

                            st.metric(
                                "Recommended Side",
                                recommended_side or "-",
                            )

                            st.metric(
                                "Confidence",
                                f"{float(signal.get('confidence', 0) or 0):.1f}%",
                            )

                        with col2:

                            st.metric(
                                "Entry",
                                signal.get("entry_price", "-"),
                            )

                            st.metric(
                                "Stop",
                                signal.get("stop_price", "-"),
                            )

                            st.metric(
                                "Risk / Reward",
                                signal.get("risk_reward", "-"),
                            )

                        with col3:

                            st.metric(
                                "Target",
                                signal.get("target_price", "-"),
                            )

                            st.metric(
                                "Units",
                                f"{float(sizing.get('suggested_units', 0) or 0):,.0f}",
                            )

                            st.metric(
                                "Margin Required",
                                f"${float(sizing.get('margin_required', 0) or 0):,.2f}",
                            )

                        rationale = signal.get("rationale")

                        if rationale:
                            st.markdown("#### AI Rationale")

                            st.write(rationale)

                        warnings = signal.get("warnings")

                        if warnings:
                            st.warning(warnings)

                        if can_open:
                            st.success("AI trade is eligible for execution.")
                        else:
                            st.warning(
                                "AI does not recommend opening this position."
                            )

                    left, right = st.columns(2)

                    with left:

                        if recommendation and can_open:

                            if st.button(
                                    "Execute AI Trade",
                                    key="execute_ai_trade",
                                    use_container_width=True,
                            ):

                                try:

                                    pair = str(signal.get("pair", "")).strip()

                                    side = str(
                                        recommended_side or ""
                                    ).upper()

                                    units = float(
                                        sizing.get("suggested_units") or 0.0
                                    )

                                    stop_price = float(
                                        signal.get("stop_price") or 0.0
                                    )

                                    target_price = float(
                                        signal.get("target_price") or 0.0
                                    )

                                    if not pair:
                                        st.error("AI recommendation did not include a currency pair.")
                                        return

                                    if not side:
                                        st.error("AI recommendation did not include a trade side.")
                                        return

                                    if units is None or float(units) <= 0:
                                        st.error("AI recommendation did not include a valid position size.")
                                        return

                                    result = self._submit_forex_order(
                                        portfolio_engine=portfolio_engine,
                                        order_engine=order_engine,
                                        kwargs=kwargs,
                                        pair=pair,
                                        side=side,
                                        units=units,
                                        stop_price=stop_price,
                                        take_profit=take_profit,
                                        limit_price=limit_price,
                                        order_type=order_type,
                                    )

                                except Exception as exc:
                                    st.exception(exc)
                                    return

                                status = str(result.get("status", "")).upper()

                                if status in ("FILLED", "SUBMITTED", "ACCEPTED"):

                                    st.success(result.get("message", "AI Trade submitted."))

                                    #
                                    # Clear dialog state
                                    #
                                    st.session_state.pop(
                                        "ai_trade_recommendation",
                                        None,
                                    )

                                    st.session_state.pop(
                                        "ai_trade_previous_pair",
                                        None,
                                    )

                                    st.session_state["ai_trade_new_order"] = False

                                    st.rerun()

                                else:

                                    st.error(
                                        result.get(
                                            "message",
                                            "AI Trade failed.",
                                        )
                                    )


                        else:

                            st.button(

                                "Execute AI Trade",

                                key="execute_ai_trade_disabled",

                                disabled=True,

                                use_container_width=True,

                            )



                    with right:

                        if st.button(
                                "Cancel",
                                key="cancel_ai_trade",
                                use_container_width=True,
                        ):
                            st.session_state.pop(
                                "ai_trade_recommendation",
                                None,
                            )

                            st.session_state.pop(
                                "ai_trade_previous_pair",
                                None,
                            )

                            st.session_state["ai_trade_new_order"] = False

                            st.rerun()

                render_ai_trade_dialog()


            # ==========================================================
            # Performance Attribution
            # ==========================================================

            st.divider()

            st.subheader("Performance Attribution")

            left, center, right = st.columns([2, 2, 1])

            with left:

                attribution = portfolio.get(
                    "performance_attribution",
                    [],
                )

                if attribution:

                    att_df = pd.DataFrame(attribution)

                    c1, c2, c3, c4 = st.columns(4)

                    best = att_df.sort_values(
                        "realized_pnl",
                        ascending=False,
                    ).iloc[0]

                    worst = att_df.sort_values(
                        "realized_pnl",
                        ascending=True,
                    ).iloc[0]

                    c1.metric(
                        "Pairs Traded",
                        len(att_df),
                    )

                    c2.metric(
                        "Best Pair",
                        best["pair"],
                    )

                    c3.metric(
                        "Worst Pair",
                        worst["pair"],
                    )

                    c4.metric(
                        "Total Realized",
                        f"${att_df['realized_pnl'].sum():,.2f}",
                    )

                    fig = px.bar(

                        att_df,

                        x="pair",

                        y="realized_pnl",

                        color="realized_pnl",

                        text="realized_pnl",

                        title="Realized P&L by Currency Pair",

                    )

                    st.plotly_chart(

                        fig,

                        use_container_width=True,

                    )

                    display = att_df[
                        [
                            "pair",
                            "trades",
                            "wins",
                            "losses",
                            "win_rate",
                            "realized_pnl",
                            "average_pnl",
                        ]
                    ].copy()

                    display.columns = [

                        "Pair",

                        "Trades",

                        "Wins",

                        "Losses",

                        "Win Rate %",

                        "Realized P&L",

                        "Average P&L",

                    ]

                    st.dataframe(

                        display,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(
                        "No attribution data."
                    )

            with center:

                monthly = performance.get(

                    "monthly_returns",

                    [],

                )

                st.subheader(

                    "Monthly Returns"

                )

                if monthly:

                    st.line_chart(

                        monthly

                    )

                else:

                    st.info(

                        "No monthly returns."

                    )

            with right:

                st.subheader(

                    "Performance"

                )

                st.metric(

                    "Sharpe",

                    performance.get(

                        "sharpe",

                        0,

                    ),

                )

                st.metric(

                    "Sortino",

                    performance.get(

                        "sortino",

                        0,

                    ),

                )

                st.metric(

                    "Profit Factor",

                    performance.get(

                        "profit_factor",

                        0,

                    ),

                )

                st.metric(

                    "Expectancy",

                    performance.get(

                        "expectancy",

                        0,

                    ),

                )

            # ==========================================================
            # Allocation
            # ==========================================================

            st.divider()

            st.subheader(

                "Portfolio Allocation"

            )

            allocation = portfolio.get(
                "allocation",
                [],
            )

            if allocation:
                alloc_df = pd.DataFrame(allocation)

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(

                    "Largest Position",

                    alloc_df.iloc[0]["pair"],

                )

                c2.metric(

                    "Largest Weight",

                    f"{alloc_df.iloc[0]['weight']:.2f}%",

                )

                c3.metric(

                    "Open Pairs",

                    len(alloc_df),

                )

                c4.metric(

                    "Total Exposure",

                    f"${alloc_df['market_value'].sum():,.2f}",

                )



            left, right = st.columns(2)

            with left:

                if allocation:

                    display = alloc_df[
                        [
                            "pair",
                            "side",
                            "weight",
                            "market_value",
                            "margin",
                            "unrealized_pnl",
                        ]
                    ].copy()

                    display.columns = [

                        "Pair",

                        "Side",

                        "Weight %",

                        "Market Value",

                        "Margin",

                        "Unrealized P&L",

                    ]

                    st.dataframe(

                        display,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(
                        "No allocation available."
                    )

            with right:

                if allocation:

                    try:

                        fig = px.pie(

                            alloc_df,

                            names="pair",

                            values="weight",

                            hole=0.45,

                        )

                        fig.update_layout(
                            title="Portfolio Allocation",
                        )

                        st.plotly_chart(

                            fig,

                            use_container_width=True,

                        )

                    except Exception as exc:

                        logger.exception(exc)

            # ==========================================================
            # Currency Exposure Detail
            # ==========================================================

            st.divider()

            st.subheader("Currency Exposure")

            exposure = portfolio.get(
                "currency_exposure",
                [],
            )

            if exposure:

                df = pd.DataFrame(exposure)

                if {

                    "currency",

                    "gross_exposure",

                }.issubset(df.columns):
                    chart = (

                        df

                        .set_index("currency")

                        [["gross_exposure"]]

                    )

                    st.bar_chart(chart)

                st.dataframe(

                    df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info("No currency exposure.")

            # ==========================================================
            # Forex Watchlist
            # ==========================================================

            st.divider()
            st.subheader("Forex Watchlist")

            # ----------------------------------------------------------
            # Load the persisted watchlist
            # ----------------------------------------------------------

            watchlist = watchlist_service.load_watchlist()
            items = list(getattr(watchlist, "items", []) or [])

            # ----------------------------------------------------------
            # Resolve the active Forex account
            # ----------------------------------------------------------

            account_data = data.get("account", {})

            account_id = (
                    account_data.get("id")
                    or data.get("account_id")
                    or kwargs.get("account_id")
            )

            if not account_id:
                account = portfolio_engine.get_account(
                    portfolio_id=kwargs.get("portfolio_id"),
                )

                if account is not None:
                    account_id = account.id

            # ----------------------------------------------------------
            # AI enrichment
            # ----------------------------------------------------------

            watchlist_ai = ForexWatchlistAI(
                portfolio_engine=portfolio_engine,
                order_engine=order_engine,
            )

            rows = []

            if items and account_id:
                try:
                    rows = watchlist_ai.enrich_watchlist(
                        watchlist=watchlist,
                        account_id=account_id,
                    ) or []
                except Exception as exc:
                    logger.exception(
                        "Failed to enrich Forex watchlist: %s",
                        exc,
                    )
                    st.warning(
                        "The watchlist loaded, but AI enrichment could not be completed."
                    )

            # ----------------------------------------------------------
            # Fallback to live market rows
            # ----------------------------------------------------------

            if not rows:
                live_rows = data.get("watchlist", [])

                rows = [
                    {
                        "pair": row.get("pair"),
                        "recommendation": "-",
                        "confidence": 0.0,
                        "recommended_side": "-",
                        "entry_price": row.get("mid", 0.0),
                        "stop_price": 0.0,
                        "target_price": 0.0,
                        "risk_reward": 0.0,
                        "suggested_units": 0.0,
                        "position_open": False,
                        "pending_orders": 0,
                    }
                    for row in live_rows
                    if isinstance(row, dict) and row.get("pair")
                ]

            # ----------------------------------------------------------
            # Summary
            # ----------------------------------------------------------

            whatchlist_summary = watchlist_ai.summarize(
                rows=rows,
            ) if rows else {
                "pair_count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "watch_count": 0,
                "average_confidence": 0.0,
            }

            # ----------------------------------------------------------
            # Display
            # ----------------------------------------------------------

            if rows:

                c1, c2, c3, c4, c5 = st.columns(5)

                c1.metric(
                    "Pairs",
                    whatchlist_summary.get("pair_count", len(rows)),
                )

                c2.metric(
                    "BUY",
                    whatchlist_summary.get("buy_count", 0),
                )

                c3.metric(
                    "SELL",
                    whatchlist_summary.get("sell_count", 0),
                )

                c4.metric(
                    "WATCH",
                    whatchlist_summary.get("watch_count", 0),
                )

                c5.metric(
                    "Avg Confidence",
                    f"{float(whatchlist_summary.get('average_confidence', 0) or 0):.1f}%",
                )

                watch_df = pd.DataFrame(rows)

                expected_columns = [
                    "pair",
                    "recommendation",
                    "confidence",
                    "recommended_side",
                    "entry_price",
                    "stop_price",
                    "target_price",
                    "risk_reward",
                    "suggested_units",
                    "position_open",
                    "pending_orders",
                ]

                for column in expected_columns:
                    if column not in watch_df.columns:
                        watch_df[column] = None

                display = watch_df[expected_columns].copy()

                display.columns = [
                    "Pair",
                    "Signal",
                    "Confidence",
                    "Side",
                    "Entry",
                    "Stop",
                    "Target",
                    "R/R",
                    "Units",
                    "Open",
                    "Pending",
                ]

                st.data_editor(
                    display,
                    hide_index=True,
                    disabled=True,
                    use_container_width=True,
                    key="forex_watchlist_grid",
                )

                st.divider()

                selected_pair = st.selectbox(
                    "Selected Pair",
                    options=display["Pair"].dropna().tolist(),
                    key="watchlist_selected_pair",
                )

                a1, a2, a3, a4 = st.columns(4)

                with a1:
                    if st.button(
                            "AI Trade",
                            key="watchlist_ai_trade",
                            use_container_width=True,
                    ):
                        st.session_state["ai_trade_selected_pair"] = selected_pair
                        st.session_state["ai_trade_new_order"] = True
                        st.rerun()

                with a2:
                    if st.button(
                            "Manual Trade",
                            key="watchlist_manual_trade",
                            use_container_width=True,
                    ):
                        st.session_state["new_order_selected_pair"] = selected_pair
                        st.session_state["new_order_dialog"] = True
                        st.rerun()

                with a3:
                    if st.button(
                            "Analyze",
                            key="watchlist_analyze",
                            use_container_width=True,
                    ):
                        try:
                            analysis = (
                                portfolio_engine.recommend_position_from_signal(
                                    account_id=account_id,
                                    pair=selected_pair,
                                    risk_pct=1.0,
                                )
                            )

                            st.session_state["watchlist_analysis"] = analysis
                            st.session_state["watchlist_analysis_pair"] = (
                                selected_pair
                            )

                            st.rerun()

                        except Exception as exc:
                            st.exception(exc)

                with a4:
                    st.button(
                        "Chart",
                        disabled=True,
                        key="watchlist_chart",
                        use_container_width=True,
                    )

            else:
                st.info("Watchlist is empty.")
            # ==========================================================
            # Watchlist AI Analysis
            # ==========================================================

            analysis = st.session_state.get(
                "watchlist_analysis"
            )

            if analysis:

                signal = analysis.get(
                    "signal",
                    {},
                )

                sizing = analysis.get(
                    "sizing",
                    {},
                )

                st.divider()

                st.subheader(

                    f"AI Analysis - {st.session_state.get('watchlist_analysis_pair', '')}"

                )

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(

                    "Recommendation",

                    signal.get(
                        "recommendation",
                        "-",
                    ),

                )

                c2.metric(

                    "Confidence",

                    f"{signal.get('confidence', 0):.1f}%",

                )

                c3.metric(

                    "Risk / Reward",

                    signal.get(
                        "risk_reward",
                        0,
                    ),

                )

                c4.metric(

                    "Suggested Side",

                    analysis.get(
                        "recommended_side",
                        "-",
                    ),

                )

                c1, c2, c3 = st.columns(3)

                c1.metric(

                    "Entry",

                    signal.get(
                        "entry_price",
                        "-",
                    ),

                )

                c2.metric(

                    "Stop",

                    signal.get(
                        "stop_price",
                        "-",
                    ),

                )

                c3.metric(

                    "Target",

                    signal.get(
                        "target_price",
                        "-",
                    ),

                )

                c1, c2, c3 = st.columns(3)

                c1.metric(

                    "Suggested Units",

                    f"{sizing.get('suggested_units', 0):,.0f}",

                )

                c2.metric(

                    "Margin Required",

                    f"${sizing.get('margin_required', 0):,.2f}",

                )

                c3.metric(

                    "Can Open",

                    "YES"

                    if analysis.get(
                        "can_open_position",
                        False,
                    )

                    else

                    "NO",

                )

                rationale = signal.get(

                    "rationale",

                    "",

                )

                if rationale:
                    st.markdown(

                        "#### AI Rationale"

                    )

                    st.write(

                        rationale

                    )

                    st.divider()

                    b1, b2 = st.columns(2)

                    with b1:

                        if st.button(

                                "Execute AI Trade",

                                key="watchlist_execute_ai_trade",

                                use_container_width=True,

                        ):
                            st.session_state["ai_trade_selected_pair"] = (
                                st.session_state.get(
                                    "watchlist_analysis_pair"
                                )
                            )

                            st.session_state["ai_trade_new_order"] = True

                            st.rerun()

                    with b2:

                        if st.button(

                                "Clear Analysis",

                                key="clear_watchlist_analysis",

                                use_container_width=True,

                        ):
                            st.session_state.pop(

                                "watchlist_analysis",

                                None,

                            )

                            st.session_state.pop(

                                "watchlist_analysis_pair",

                                None,

                            )

                            st.rerun()

            # ----------------------------------------------------------
            # Remove Pair
            # ----------------------------------------------------------


            if items:

                pair_remove = st.selectbox(
                    "Remove Pair",
                    options=[
                        item.pair
                        for item in items
                    ],
                    key="watchlist_remove_pair",
                )

                if st.button(
                        "Remove Pair",
                        key="watchlist_remove_button",
                        use_container_width=True,
                ):
                    watchlist_service.remove_pair(
                        pair=pair_remove,
                    )

                    st.rerun()

            else:

                st.info(
                    "The Forex watchlist is empty. Seed major or cross pairs below."
                )

            # ----------------------------------------------------------
            # Seed Buttons
            # IMPORTANT: outside `if items`
            # ----------------------------------------------------------

            left, right = st.columns(2)

            with left:

                if st.button(
                        "Seed Major Pairs",
                        key="seed_major_pairs",
                        use_container_width=True,
                ):
                    watchlist_service.seed_major_pairs()
                    st.rerun()

            with right:

                if st.button(
                        "Seed Cross Pairs",
                        key="seed_cross_pairs",
                        use_container_width=True,
                ):
                    watchlist_service.seed_cross_pairs()
                    st.rerun()

            # ==========================================================
            # Account Summary
            # IMPORTANT: outside `if items`
            # ==========================================================

            st.divider()



            st.subheader(
                "Account Summary"
            )
            print("=" * 80)
            print("ACCOUNT SUMMARY DEBUG")
            print("=" * 80)

            print("account =", account)
            print("summary =", summary)
            print("margin =", margin)

            print("=" * 80)
            row = st.columns(6)

            row[0].metric(

                "Currency",

                account_currency,

            )

            row[1].metric(

                "Cash",

                f"{summary.get('cash_balance', 0):,.2f}",

            )

            row[2].metric(

                "Equity",

                f"{summary.get('equity', 0):,.2f}",

            )

            row[3].metric(

                "Buying Power",

                f"{summary.get('buying_power', 0):,.2f}",

            )

            row[4].metric(

                "Margin Available",

                f"{summary.get('margin_available', 0):,.2f}",

            )

            row[5].metric(

                "Account Status",

                portfolio.get(

                    "status",

                    "ACTIVE",

                ),

            )

            st.divider()
            print("CHECKPOINT 4.7 ELIF Orders")
            st.success(
                "Portfolio Dashboard Loaded Successfully"
            )

        elif ws == "Orders":

            portfolio = data.get("portfolio", {})

            account = portfolio_engine.get_account(
                portfolio_id=kwargs.get("portfolio_id"),
            )

            dashboard_service = ForexExecutionDashboardService(
                db=self.desk.db,
            )

            with st.spinner(
                    "Loading institutional execution analytics..."
            ):

                dashboard = dashboard_service.build_dashboard(
                    account_id=account.id if account else None,
                    portfolio_id=kwargs.get("portfolio_id"),
                )

            #
            # NEW CODE STARTS HERE
            #

            cards = dashboard.get(
                "cards",
                {},
            )

            statistics = dashboard.get(
                "statistics",
                {},
            )

            quality = dashboard.get(
                "quality",
                {},
            )

            charts = dashboard.get(
                "charts",
                {},
            )

            distributions = dashboard.get(
                "distributions",
                {},
            )

            broker = dashboard.get(
                "broker",
                {},
            )

            timeline = dashboard.get(
                "timeline",
                [],
            )

            recent_executions = dashboard.get(
                "recent_executions",
                [],
            )

            execution_health = dashboard.get(
                "execution_health",
                {},
            )

            execution_intelligence = dashboard.get(
                "execution_intelligence",
                {},
            )

            executive_ai = dashboard.get(
                "executive_ai",
                {},
            )

            #
            # END OF NEW CODE
            #

            open_orders = data.get("open_orders", [])

            filled_orders = data.get("filled_orders", [])

            execution_history = data.get("execution_history", [])

            cash_ledger = data.get("cash_ledger", [])

            execution = data.get("execution", {})

            system = data.get("system", {})

            pending_orders = data.get(
                "pending_orders",
                [],
            )

            cancelled_orders = data.get(
                "cancelled_orders",
                [],
            )

            broker_status = system.get(
                "broker",
                {},
            )

            snapshot_time = system.get(
                "generated_at",
                "--",
            )
            print("=" * 80)
            print("EXECUTION DASHBOARD PACKET")
            print("cards                  :", cards.keys())
            print("statistics            :", statistics.keys())
            print("quality               :", quality.keys())
            print("broker                :", broker.keys())
            print("execution_health      :", execution_health)
            print("execution_intelligence:", execution_intelligence)
            print("=" * 80)

            st.subheader("Institutional Order Management")

            # ==========================================================
            # Institutional Execution Command Center
            # ==========================================================

            st.divider()

            st.subheader(
                "Execution Command Center"
            )

            health_score = float(
                execution_health.get(
                    "overall_score",
                    0.0,
                )
                or 0.0
            )

            health_grade = str(
                execution_health.get(
                    "grade",
                    "--",
                )
                or "--"
            )

            health_status = str(
                execution_health.get(
                    "status",
                    "--",
                )
                or "--"
            )

            intelligence_summary = execution_intelligence.get(
                "summary",
                {},
            )

            risk_level = str(
                intelligence_summary.get(
                    "risk_level",
                    "--",
                )
                or "--"
            )

            headline = str(
                intelligence_summary.get(
                    "headline",
                    "Execution intelligence unavailable.",
                )
                or "Execution intelligence unavailable."
            )

            active_alerts = execution_intelligence.get(
                "alerts",
                [],
            )

            recommendations = execution_intelligence.get(
                "recommendations",
                [],
            )

            command_cards = st.columns(4)

            command_cards[0].metric(
                "Execution Health",
                health_grade,
            )

            command_cards[1].metric(
                "Overall Score",
                f"{health_score:.1f}",
            )

            command_cards[2].metric(
                "Status",
                health_status,
            )

            command_cards[3].metric(
                "Execution Risk",
                risk_level,
            )

            st.info(
                headline
            )

            action_left, action_center_left, action_center_right, action_right = (
                st.columns(4)
            )

            with action_left:

                if st.button(
                        "Refresh Analytics",
                        key="orders_refresh_execution_analytics",
                        use_container_width=True,
                ):
                    st.rerun()

            with action_center_left:

                st.metric(
                    "Active Alerts",
                    len(active_alerts),
                )

            with action_center_right:

                st.metric(
                    "Recommendations",
                    len(recommendations),
                )

            with action_right:

                broker_name = broker.get(
                    "name",
                    broker.get(
                        "broker",
                        "Paper",
                    ),
                )

                st.metric(
                    "Broker",
                    broker_name,
                )

            if health_score >= 95:

                st.success(
                    "Execution quality is operating at institutional standards."
                )

            elif health_score >= 85:

                st.warning(
                    "Execution quality is acceptable but has optimization opportunities."
                )

            elif health_score > 0:

                st.error(
                    "Execution quality requires review."
                )

            else:

                st.info(
                    "Execution health is awaiting sufficient execution data."
                )
            print("=" * 100)
            print("EXECUTION COMMAND CENTER")
            print("=" * 100)
            print("health_score    :", health_score)
            print("health_grade    :", health_grade)
            print("health_status   :", health_status)
            print("risk_level      :", risk_level)
            print("headline        :", headline)
            print("alerts          :", len(active_alerts))
            print("recommendations :", len(recommendations))
            print("=" * 100)

            # ==========================================================
            # Institutional Execution Health Detail
            # ==========================================================

            st.divider()

            st.subheader(
                "Execution Health Analysis"
            )

            left, right = st.columns(
                [1.2, 1]
            )

            with left:

                score_df = pd.DataFrame(

                    [

                        {
                            "Category": "Fill Rate",
                            "Score": execution_health.get(
                                "fill_rate_score",
                                0,
                            ),
                        },

                        {
                            "Category": "Latency",
                            "Score": execution_health.get(
                                "latency_score",
                                0,
                            ),
                        },

                        {
                            "Category": "Slippage",
                            "Score": execution_health.get(
                                "slippage_score",
                                0,
                            ),
                        },

                        {
                            "Category": "Broker",
                            "Score": execution_health.get(
                                "broker_score",
                                0,
                            ),
                        },

                    ]

                )

                st.bar_chart(
                    score_df.set_index(
                        "Category"
                    )
                )

                st.dataframe(

                    score_df,

                    use_container_width=True,

                    hide_index=True,

                )

            with right:

                st.metric(

                    "Overall Score",

                    f"{execution_health.get('overall_score', 0):.1f}",

                )

                st.metric(

                    "Execution Grade",

                    execution_health.get(
                        "grade",
                        "--",
                    ),

                )

                st.metric(

                    "Execution Status",

                    execution_health.get(
                        "status",
                        "--",
                    ),

                )

                st.metric(

                    "Broker Rating",

                    execution_health.get(
                        "broker_score",
                        0,
                    ),

                )
            print("=" * 100)
            print("EXECUTION HEALTH DETAIL")
            print(score_df)
            print("=" * 100)

            # ==========================================================
            # Execution Quality Scorecard
            # ==========================================================

            st.divider()

            st.subheader(
                "Execution Quality Scorecard"
            )
            quality_summary = quality or {}
            average_latency = float(
                quality_summary.get(
                    "average_latency_ms",
                    quality_summary.get(
                        "latency_ms",
                        0,
                    ),
                )
                or 0
            )

            median_latency = float(
                quality_summary.get(
                    "median_latency_ms",
                    0,
                )
                or 0
            )

            p95_latency = float(
                quality_summary.get(
                    "p95_latency_ms",
                    0,
                )
                or 0
            )

            average_slippage = float(
                quality_summary.get(
                    "average_slippage",
                    quality_summary.get(
                        "avg_slippage",
                        0,
                    ),
                )
                or 0
            )

            average_cost = float(
                quality_summary.get(
                    "average_execution_cost",
                    0,
                )
                or 0
            )

            average_spread = float(
                quality_summary.get(
                    "average_spread",
                    0,
                )
                or 0
            )
            quality_cards = st.columns(6)

            quality_cards[0].metric(
                "Average Latency",
                f"{average_latency:,.1f} ms",
            )

            quality_cards[1].metric(
                "Median Latency",
                f"{median_latency:,.1f} ms",
            )

            quality_cards[2].metric(
                "95th Percentile",
                f"{p95_latency:,.1f} ms",
            )

            quality_cards[3].metric(
                "Average Slippage",
                f"{average_slippage:.6f}",
            )

            quality_cards[4].metric(
                "Average Spread",
                f"{average_spread:.6f}",
            )

            quality_cards[5].metric(
                "Execution Cost",
                f"{average_cost:.6f}",
            )
            left, right = st.columns(2)
            with left:

                quality_df = pd.DataFrame(

                    [

                        {
                            "Metric": "Latency",
                            "Value": average_latency,
                        },

                        {
                            "Metric": "Slippage",
                            "Value": average_slippage,
                        },

                        {
                            "Metric": "Spread",
                            "Value": average_spread,
                        },

                        {
                            "Metric": "Execution Cost",
                            "Value": average_cost,
                        },

                    ]

                )

                st.bar_chart(
                    quality_df.set_index(
                        "Metric"
                    )
                )
            with right:
                st.dataframe(

                    quality_df,

                    use_container_width=True,

                    hide_index=True,

                )
            print("=" * 100)
            print("EXECUTION QUALITY SCORECARD")
            print("Latency :", average_latency)
            print("Slippage:", average_slippage)
            print("Spread  :", average_spread)
            print("Cost    :", average_cost)
            print("=" * 100)

            # ==========================================================
            # Execution Trend Analysis
            # ==========================================================

            st.divider()

            st.subheader(
                "Execution Trend Analysis"
            )

            trend_source = dashboard.get(
                "recent_executions",
                recent_executions,
            )

            trend_df = pd.DataFrame(
                trend_source,
            )

            if not trend_df.empty:
                if "executed_at" in trend_df.columns:

                    trend_df["executed_at"] = pd.to_datetime(
                        trend_df["executed_at"],
                        errors="coerce",
                    )

                elif "timestamp" in trend_df.columns:

                    trend_df["executed_at"] = pd.to_datetime(
                        trend_df["timestamp"],
                        errors="coerce",
                    )

                    trend_df = trend_df.sort_values(
                        "executed_at"
                    )

                    left, center, right = st.columns(3)

                    with left:

                        st.markdown(
                            "#### Latency Trend"
                        )

                        if "latency_ms" in trend_df.columns:

                            st.line_chart(

                                trend_df.set_index(
                                    "executed_at"
                                )[
                                    "latency_ms"
                                ]

                            )

                        else:

                            st.info(
                                "Latency history unavailable."
                            )

                    with center:

                        st.markdown(
                            "#### Slippage Trend"
                        )

                        slippage_column = None

                        for candidate in (

                                "slippage",

                                "avg_slippage",

                                "average_slippage",

                        ):

                            if candidate in trend_df.columns:
                                slippage_column = candidate

                                break

                        if slippage_column:

                            st.line_chart(

                                trend_df.set_index(
                                    "executed_at"
                                )[
                                    slippage_column
                                ]

                            )

                        else:

                            st.info(
                                "Slippage history unavailable."
                            )

                    with right:

                        st.markdown(
                            "#### Execution Price"

                        )

                        price_column = None

                        for candidate in (

                                "execution_price",

                                "avg_fill_price",

                                "price",

                        ):

                            if candidate in trend_df.columns:
                                price_column = candidate

                                break

                        if price_column:

                            st.line_chart(

                                trend_df.set_index(
                                    "executed_at"
                                )[
                                    price_column
                                ]

                            )

                        else:

                            st.info(
                                "Execution price history unavailable."
                            )
                        st.markdown(
                            "#### Trend Summary"
                        )

                        summary_rows = [

                            {

                                "Metric": "Executions",

                                "Value": len(trend_df),

                            },

                            {

                                "Metric": "First Execution",

                                "Value": trend_df["executed_at"].min(),

                            },

                            {

                                "Metric": "Latest Execution",

                                "Value": trend_df["executed_at"].max(),

                            },

                        ]

                        st.dataframe(

                            pd.DataFrame(summary_rows),

                            use_container_width=True,

                            hide_index=True,

                        )
                print("=" * 100)
                print("EXECUTION TREND ANALYSIS")
                print("rows =", len(trend_df))
                print("columns =", list(trend_df.columns))
                print("=" * 100)
            st.divider()

            st.subheader(
                "Execution Trend Intelligence"
            )

            trend_intelligence = {

                "latency": "Stable",

                "slippage": "Stable",

                "fill_rate": "Stable",

                "execution_quality": "Stable",

                "overall": "Stable",

            }
            if (
                    not trend_df.empty
                    and "latency_ms" in trend_df.columns
                    and len(trend_df) >= 2
            ):

                latency_delta = (

                        trend_df["latency_ms"].iloc[-1]

                        -

                        trend_df["latency_ms"].iloc[0]

                )

                if latency_delta < -10:

                    trend_intelligence["latency"] = "Improving"

                elif latency_delta > 10:

                    trend_intelligence["latency"] = "Deteriorating"
                slippage_column = None

                for candidate in (

                        "slippage",

                        "avg_slippage",

                        "average_slippage",

                ):

                    if candidate in trend_df.columns:
                        slippage_column = candidate

                        break

                if (
                        slippage_column
                        and len(trend_df) >= 2
                ):

                    delta = (

                            trend_df[slippage_column].iloc[-1]

                            -

                            trend_df[slippage_column].iloc[0]

                    )

                    if delta < -0.0001:

                        trend_intelligence["slippage"] = "Improving"

                    elif delta > 0.0001:

                        trend_intelligence["slippage"] = "Deteriorating"
                    score = execution_health.get(
                        "overall_score",
                        0,
                    )

                    if score >= 95:

                        trend_intelligence["execution_quality"] = "Excellent"

                    elif score >= 85:

                        trend_intelligence["execution_quality"] = "Good"

                    else:

                        trend_intelligence["execution_quality"] = "Needs Review"

                    states = list(
                        trend_intelligence.values()
                    )

                    if "Deteriorating" in states:

                        trend_intelligence["overall"] = "Deteriorating"

                    elif "Improving" in states:

                        trend_intelligence["overall"] = "Improving"

                    else:

                        trend_intelligence["overall"] = "Stable"
                print("=" * 100)
                print("TREND INTELLIGENCE")
                print(trend_intelligence)
                print("=" * 100)

            # ==========================================================
            # Executive Order Metrics
            # ==========================================================

            row = st.columns(8)

            row[0].metric(
                "Open Orders",
                cards.get(
                    "open_orders",
                    len(open_orders),
                ),
            )

            row[1].metric(
                "Filled",
                cards.get(
                    "filled_orders",
                    len(filled_orders),
                ),
            )

            row[2].metric(
                "Executions",
                cards.get(
                    "executions",
                    len(execution_history),
                ),
            )

            row[3].metric(
                "Pending",
                cards.get(
                    "pending_orders",
                    len(pending_orders),
                ),
            )

            row[4].metric(
                "Fill Rate",
                f"{statistics.get(
                    'fill_rate',
                    execution.get(
                        'fill_rate',
                        0,
                    ),
                ):.1f}%"
            )

            row[5].metric(
                "Latency",
                f"{statistics.get(
                    'latency_ms',
                    execution.get(
                        'latency_ms',
                        0,
                    ),
                ):,.0f} ms",
            )

            row[6].metric(
                "Slippage",
                f"{quality.get(
                    'avg_slippage',
                    execution.get(
                        'avg_slippage',
                        0,
                    ),
                ):.4f}",
            )

            row[7].metric(
                "Broker",
                broker.get(
                    "name",
                    broker_status.get(
                        "name",
                        "Paper",
                    ),
                ),
            )

            print("=" * 100)
            print("ORDERS DASHBOARD SERVICE")
            print("=" * 100)
            print("cards =", cards)
            print("statistics =", statistics)
            print("quality =", quality)
            print("broker =", broker)
            print("=" * 100)

            # ==========================================================
            # Institutional Execution Health
            # ==========================================================

            st.divider()

            st.subheader(
                "Institutional Execution Health"
            )

            left, right = st.columns(2)

            left.metric(
                "Overall Score",
                f"{execution_health.get('overall_score', 0):.0f}",
            )

            left.metric(
                "Grade",
                execution_health.get(
                    "grade",
                    "--",
                ),
            )

            left.metric(
                "Status",
                execution_health.get(
                    "status",
                    "--",
                ),
            )

            right.metric(
                "Fill Rate Score",
                execution_health.get(
                    "fill_rate_score",
                    0,
                ),
            )

            right.metric(
                "Latency Score",
                execution_health.get(
                    "latency_score",
                    0,
                ),
            )

            right.metric(
                "Slippage Score",
                execution_health.get(
                    "slippage_score",
                    0,
                ),
            )

            right.metric(
                "Broker Score",
                execution_health.get(
                    "broker_score",
                    0,
                ),
            )

            # ==========================================================
            # Institutional Execution Intelligence
            # ==========================================================

            st.divider()

            st.subheader(
                "Institutional Execution Intelligence"
            )

            summary = execution_intelligence.get(
                "summary",
                {},
            )

            headline = summary.get(
                "headline",
                "Execution intelligence unavailable.",
            )

            st.info(headline)

            left, center, right = st.columns(3)

            left.metric(
                "Execution Score",
                f"{summary.get('overall_score', 0):.1f}",
            )

            center.metric(
                "Execution Grade",
                summary.get(
                    "grade",
                    "--",
                ),
            )

            right.metric(
                "Risk Level",
                summary.get(
                    "risk_level",
                    "--",
                ),
            )

            st.markdown("#### Recommendations")

            recommendations = execution_intelligence.get(
                "recommendations",
                [],
            )

            if recommendations:

                for recommendation in recommendations:
                    st.success(
                        recommendation
                    )

            else:

                st.info(
                    "No recommendations."
                )

            st.markdown("#### Alerts")

            alerts = execution_intelligence.get(
                "alerts",
                [],
            )

            if alerts:

                for alert in alerts:

                    severity = str(
                        alert.get(
                            "severity",
                            "",
                        )
                    ).upper()

                    message = alert.get(
                        "message",
                        "",
                    )

                    if severity == "CRITICAL":

                        st.error(message)

                    elif severity == "WARNING":

                        st.warning(message)

                    else:

                        st.info(message)

            else:

                st.success(
                    "No execution alerts."
                )

            st.markdown("#### Broker Analysis")

            broker_analysis = execution_intelligence.get(
                "broker_analysis",
                {},
            )

            broker_df = pd.DataFrame(

                [

                    {

                        "Metric": "Broker",

                        "Value": broker_analysis.get(
                            "broker_name",
                            "--",
                        ),

                    },

                    {

                        "Metric": "Fill Rate",

                        "Value": broker_analysis.get(
                            "fill_rate",
                            0,
                        ),

                    },

                    {

                        "Metric": "Reject Rate",

                        "Value": broker_analysis.get(
                            "reject_rate",
                            0,
                        ),

                    },

                    {

                        "Metric": "Average Latency",

                        "Value": broker_analysis.get(
                            "average_latency_ms",
                            0,
                        ),

                    },

                    {

                        "Metric": "Average Slippage",

                        "Value": broker_analysis.get(
                            "average_slippage",
                            0,
                        ),

                    },

                    {

                        "Metric": "Execution Grade",

                        "Value": broker_analysis.get(
                            "execution_grade",
                            "--",
                        ),

                    },

                ]

            )

            st.dataframe(

                broker_df,

                use_container_width=True,

                hide_index=True,

            )

            st.markdown("#### Execution Cost Analysis")

            cost_analysis = execution_intelligence.get(
                "cost_analysis",
                {},
            )

            cost_df = pd.DataFrame(

                [

                    {

                        "Metric": "Total Commission",

                        "Value": cost_analysis.get(
                            "total_commission",
                            0,
                        ),

                    },

                    {

                        "Metric": "Average Commission",

                        "Value": cost_analysis.get(
                            "average_commission",
                            0,
                        ),

                    },

                    {

                        "Metric": "Execution Cost",

                        "Value": cost_analysis.get(
                            "total_execution_cost",
                            0,
                        ),

                    },

                    {

                        "Metric": "Average Cost",

                        "Value": cost_analysis.get(
                            "average_execution_cost",
                            0,
                        ),

                    },

                    {

                        "Metric": "Spread",

                        "Value": cost_analysis.get(
                            "average_spread",
                            0,
                        ),

                    },

                ]

            )

            st.dataframe(

                cost_df,

                use_container_width=True,

                hide_index=True,

            )

            st.markdown("#### Execution Risk Analysis")

            risk_analysis = execution_intelligence.get(
                "risk_analysis",
                {},
            )

            risk_df = pd.DataFrame(

                [

                    {

                        "Metric": "Risk Level",

                        "Value": risk_analysis.get(
                            "risk_level",
                            "--",
                        ),

                    },

                    {

                        "Metric": "Latency",

                        "Value": risk_analysis.get(
                            "average_latency_ms",
                            0,
                        ),

                    },

                    {

                        "Metric": "Reject Rate",

                        "Value": risk_analysis.get(
                            "reject_rate",
                            0,
                        ),

                    },

                    {

                        "Metric": "Pending Orders",

                        "Value": risk_analysis.get(
                            "pending_order_count",
                            0,
                        ),

                    },

                    {

                        "Metric": "Open Orders",

                        "Value": risk_analysis.get(
                            "open_order_count",
                            0,
                        ),

                    },

                ]

            )

            st.dataframe(

                risk_df,

                use_container_width=True,

                hide_index=True,

            )

            print("=" * 100)
            print("EXECUTION INTELLIGENCE UI")
            print(
                execution_intelligence.get(
                    "summary",
                    {},
                )
            )
            print(
                "Recommendations:",
                len(
                    execution_intelligence.get(
                        "recommendations",
                        [],
                    )
                ),
            )
            print(
                "Alerts:",
                len(
                    execution_intelligence.get(
                        "alerts",
                        [],
                    )
                ),
            )
            print("=" * 100)



            st.divider()

            # ==========================================================
            # Execution Charts
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Orders by Status"

                )

                status_rows = distributions.get(
                    "status_distribution",
                    [],
                )

                if status_rows:

                    status_df = pd.DataFrame(
                        status_rows,
                    )

                else:

                    status_df = pd.DataFrame(
                        [

                            {

                                "status": "Open",

                                "orders": len(open_orders),

                            },

                            {

                                "status": "Pending",

                                "orders": len(pending_orders),

                            },

                            {

                                "status": "Filled",

                                "orders": len(filled_orders),

                            },

                            {

                                "status": "Cancelled",

                                "orders": len(cancelled_orders),

                            },

                        ]

                    )



                st.bar_chart(

                    status_df.set_index(

                        "Status"

                    )

                )

                st.dataframe(

                    status_df,

                    use_container_width=True,

                    hide_index=True,

                )

            with right:

                st.subheader(

                    "Execution Statistics"

                )

                rows = [

                    {

                        "Metric": key.replace(
                            "_",
                            " ",
                        ).title(),

                        "Value": value,

                    }

                    for key, value in statistics.items()

                    if not isinstance(
                        value,
                        (
                            dict,
                            list,
                        ),
                    )

                ]

                metrics_df = pd.DataFrame(rows)

                st.divider()

                st.subheader(
                    "Execution Quality"
                )

                quality_rows = [

                    {

                        "Metric": key.replace(
                            "_",
                            " ",
                        ).title(),

                        "Value": value,

                    }

                    for key, value in quality.items()

                    if not isinstance(
                        value,
                        (
                            dict,
                            list,
                        ),
                    )

                ]

                if quality_rows:
                    st.dataframe(

                        pd.DataFrame(
                            quality_rows,
                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                    st.divider()

                    st.subheader(
                        "Broker Analytics"
                    )

                    broker_rows = [

                        {

                            "Metric": key.replace(
                                "_",
                                " ",
                            ).title(),

                            "Value": value,

                        }

                        for key, value in broker.items()

                        if not isinstance(
                            value,
                            (
                                dict,
                                list,
                            ),
                        )

                    ]

                    if broker_rows:
                        st.dataframe(

                            pd.DataFrame(
                                broker_rows,
                            ),

                            use_container_width=True,

                            hide_index=True,

                        )

                    print("=" * 100)
                    print("EXECUTION ANALYTICS PACKET")
                    print("=" * 100)

                    print("statistics")
                    print(statistics)

                    print("quality")
                    print(quality)

                    print("charts")
                    print(charts)

                    print("distributions")
                    print(distributions)

                    print("broker")
                    print(broker)

                    print("=" * 100)

            st.divider()

            # ==========================================================
            # Open Orders
            # ==========================================================

            st.subheader(
                "Open Orders"
            )

            dashboard_open_orders = dashboard.get(
                "open_orders",
                open_orders,
            )

            if dashboard_open_orders:

                df = pd.DataFrame(
                    dashboard_open_orders,
                )

                preferred = [
                    "pair",
                    "side",
                    "order_type",
                    "quantity",
                    "price",
                    "status",
                    "submitted_at",
                    "strategy",
                ]

                cols = [
                    c
                    for c in preferred
                    if c in df.columns
                ]

                if cols:
                    df = df[cols]

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.info(
                    "No open orders."
                )

            st.divider()

            # ==========================================================
            # Filled Orders
            # ==========================================================

            st.subheader(
                "Filled Orders"
            )

            dashboard_filled_orders = dashboard.get(
                "filled_orders",
                filled_orders,
            )

            if dashboard_filled_orders:

                filled_df = pd.DataFrame(
                    dashboard_filled_orders,
                )

                if "filled_at" in filled_df.columns:
                    filled_df = filled_df.sort_values(
                        "filled_at",
                        ascending=False,
                    )

                preferred = [

                    "filled_at",

                    "pair",

                    "side",

                    "order_type",

                    "filled_qty",

                    "avg_fill_price",

                    "execution_price",

                    "commission",

                    "slippage",

                    "latency_ms",

                    "broker",

                    "strategy",

                    "status",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in filled_df.columns

                ]

                if cols:
                    filled_df = filled_df[cols]

                st.dataframe(

                    filled_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No filled orders."

                )

            print("=" * 80)
            print("FILLED ORDERS VALIDATION")
            print(
                "dashboard_filled_orders =",
                len(dashboard_filled_orders),
            )
            print("=" * 80)

            st.divider()



            st.subheader("Closed Positions History")

            closed_positions = portfolio.get("closed_positions", [])

            if closed_positions:

                df = pd.DataFrame(closed_positions)

                preferred = [
                    "pair",
                    "side",
                    "units",
                    "avg_entry_price",
                    "exit_price",
                    "realized_pnl",
                    "opened_at",
                    "closed_at",
                    "status",
                ]

                cols = [c for c in preferred if c in df.columns]

                if cols:
                    df = df[cols]

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    height=350,
                )

            else:
                st.info("No closed positions.")

            st.divider()

            # ==========================================================
            # Pending / Cancelled
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Pending Orders"

                )
                dashboard_pending_orders = dashboard.get(

                    "pending_orders",

                    pending_orders,

                )

                if dashboard_pending_orders:

                    st.dataframe(

                        df=pd.DataFrame(

                            dashboard_pending_orders,

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                    print("=" * 80)
                    print("PENDING ORDERS VALIDATION")
                    print("dashboard_pending_orders =", len(dashboard_pending_orders))
                    print("=" * 80)

                else:

                    st.info(

                        "No pending orders."

                    )

            with right:

                st.subheader(

                    "Cancelled Orders"

                )
                dashboard_cancelled_orders = dashboard.get(

                    "cancelled_orders",

                    cancelled_orders,

                )

                if dashboard_cancelled_orders:

                    st.dataframe(

                        df=pd.DataFrame(

                            dashboard_cancelled_orders,

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No cancelled orders."

                    )

                print("=" * 80)
                print("CANCELLED ORDERS VALIDATION")
                print(
                    "dashboard_cancelled_orders =",
                    len(dashboard_cancelled_orders),
                )
                print("=" * 80)

            st.divider()

            # ==========================================================
            # Execution Quality
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Execution Quality"

                )

                st.metric(

                    "Fill Rate",

                    f"{execution.get('fill_rate', 0):.1f}%",

                )

                st.metric(

                    "Slippage",

                    execution.get(

                        "avg_slippage",

                        0,

                    ),

                )

                st.metric(

                    "Reject Rate",

                    execution.get(

                        "reject_rate",

                        0,

                    ),

                )

                st.metric(

                    "Latency",

                    execution.get(

                        "latency_ms",

                        0,

                    ),

                )

            with right:

                st.subheader(

                    "Execution Feed"

                )

                feed = execution_history

                if feed:

                    st.dataframe(

                        pd.DataFrame(

                            feed

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No execution feed."

                    )

            st.divider()

            # ==========================================================
            # Quick Actions
            # ==========================================================

            st.subheader(

                "Order Actions"

            )

            a, b, c, d, e, f = st.columns(6)

            a.button(

                "New Order",

                use_container_width=True,

            )

            b.button(

                "Modify",

                use_container_width=True,

            )

            c.button(

                "Cancel",

                use_container_width=True,

            )

            d.button(

                "Close All",

                use_container_width=True,

            )

            e.button(
                "Export",
                key="order_action_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="order_action_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Order Management Dashboard Loaded"

            )
            # ==========================================================
            # Order Distribution
            # ==========================================================

            st.divider()

            st.subheader("Order Distribution")

            left, right = st.columns(2)

            with left:

                pair_count = {}

                for order in open_orders + filled_orders:
                    pair = order.get(

                        "pair",

                        "Unknown",

                    )

                    pair_count[pair] = (

                            pair_count.get(

                                pair,

                                0,

                            ) + 1

                    )

                if pair_count:

                    pair_df = pd.DataFrame(

                        {

                            "Pair":

                                list(

                                    pair_count.keys()

                                ),

                            "Orders":

                                list(

                                    pair_count.values()

                                ),

                        }

                    )

                    st.bar_chart(

                        pair_df.set_index(

                            "Pair"

                        )

                    )

                    st.dataframe(

                        pair_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No order activity."

                    )

            with right:

                side_count = {

                    "BUY": 0,

                    "SELL": 0,

                }

                for order in open_orders + filled_orders:

                    side = str(

                        order.get(

                            "side",

                            "",

                        )

                    ).upper()

                    if side in side_count:
                        side_count[side] += 1

                side_df = pd.DataFrame(

                    {

                        "Side":

                            list(

                                side_count.keys()

                            ),

                        "Orders":

                            list(

                                side_count.values()

                            ),

                    }

                )

                st.bar_chart(

                    side_df.set_index(

                        "Side"

                    )

                )

                st.dataframe(

                    side_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # ==========================================================
            # Order Type Analysis
            # ==========================================================

            st.divider()

            st.subheader(

                "Order Type Analytics"

            )

            order_types = {}

            for order in (

                    open_orders +

                    filled_orders +

                    pending_orders

            ):
                t = order.get(

                    "order_type",

                    "UNKNOWN",

                )

                order_types[t] = (

                        order_types.get(

                            t,

                            0,

                        ) + 1

                )

            if order_types:

                df = pd.DataFrame(

                    {

                        "Order Type":

                            list(

                                order_types.keys()

                            ),

                        "Count":

                            list(

                                order_types.values()

                            ),

                    }

                )

                st.bar_chart(

                    df.set_index(

                        "Order Type"

                    )

                )

                st.dataframe(

                    df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No order types available."

                )


            # ==========================================================
            # Execution Performance
            # ==========================================================

            st.divider()

            st.subheader(

                "Execution Performance"

            )

            perf_cols = st.columns(6)

            perf_cols[0].metric(

                "Avg Fill",

                execution.get(

                    "avg_fill_time",

                    0,

                ),

            )

            perf_cols[1].metric(

                "Latency",

                execution.get(

                    "latency_ms",

                    0,

                ),

            )

            perf_cols[2].metric(

                "Fill Rate",

                f"{execution.get('fill_rate', 0):.1f}%",

            )

            perf_cols[3].metric(

                "Reject Rate",

                f"{execution.get('reject_rate', 0):.1f}%",

            )

            perf_cols[4].metric(

                "Avg Spread",

                execution.get(

                    "avg_spread",

                    0,

                ),

            )

            perf_cols[5].metric(

                "Commission",

                execution.get(

                    "commission",

                    0,

                ),

            )

            # ==========================================================
            # Recent Executions
            # ==========================================================

            st.divider()

            st.subheader(

                "Recent Executions"

            )
            dashboard_recent_executions = dashboard.get(
                "recent_executions",
                execution_history,
            )

            #executions = execution_history

            if dashboard_recent_executions:

                exec_df = pd.DataFrame(
                    dashboard_recent_executions,
                )

                preferred = [

                    "executed_at",

                    "pair",

                    "side",

                    "execution_type",

                    "order_type",

                    "requested_units",

                    "filled_units",

                    "execution_price",

                    "avg_fill_price",

                    "commission",

                    "slippage",

                    "latency_ms",

                    "status",

                    "broker",

                    "strategy",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in exec_df.columns

                ]

                if cols:
                    exec_df = exec_df[cols]

                st.dataframe(

                    exec_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No executions available."

                )

            print("=" * 80)
            print("RECENT EXECUTIONS VALIDATION")
            print(
                "dashboard_recent_executions =",
                len(dashboard_recent_executions),
            )
            print("=" * 80)
            st.divider()

            st.subheader(
                "Cash Ledger"
            )

            if cash_ledger:

                ledger_df = pd.DataFrame(
                    cash_ledger
                )

                st.dataframe(

                    ledger_df,

                    use_container_width=True,

                    hide_index=True,

                    height=250,

                )

            else:

                st.info(
                    "No cash ledger activity."
                )

            # ==========================================================
            # Execution Timeline
            # ==========================================================

            st.divider()

            st.subheader(

                "Execution Timeline"

            )
            dashboard_timeline = dashboard.get(
                "timeline",
                execution_history,
            )


            if dashboard_timeline:

                timeline_df = pd.DataFrame(
                    dashboard_timeline,
                )

                if "timestamp" in timeline_df.columns:

                    timeline_df = timeline_df.sort_values(
                        "timestamp",
                        ascending=False,
                    )

                elif "executed_at" in timeline_df.columns:

                    timeline_df = timeline_df.sort_values(
                        "executed_at",
                        ascending=False,
                    )

                preferred = [

                    "timestamp",

                    "executed_at",

                    "event_type",

                    "pair",

                    "side",

                    "units",

                    "price",

                    "status",

                    "broker",

                    "strategy",

                    "message",

                ]
                cols = [

                    c

                    for c in preferred

                    if c in timeline_df.columns

                ]

                if cols:
                    timeline_df = timeline_df[cols]

                st.dataframe(

                    timeline_df,

                    use_container_width=True,

                    hide_index=True,

                )


            else:

                st.info(

                    "Timeline unavailable."

                )

            print("=" * 80)
            print("TIMELINE VALIDATION")
            print(
                "dashboard_timeline =",
                len(dashboard_timeline),
            )
            print("=" * 80)

            st.divider()



            st.subheader(
                "Broker Status"
            )

            left, right = st.columns(2)

            with left:

                st.metric(

                    "Broker",

                    broker_status.get(
                        "name",
                        "Paper",
                    ),

                )

                st.metric(

                    "Connection",

                    broker_status.get(
                        "status",
                        "Connected",
                    ),

                )

            with right:

                st.metric(

                    "Snapshot",

                    snapshot_time,

                )

                st.metric(

                    "Orders",

                    len(open_orders),

                )

            st.success(

                "Institutional Order Analytics Loaded"

            )
        elif ws == "Risk":

            risk = data.get("risk", {})

            # ==========================================================
            # Live Risk Engines
            # ==========================================================

            try:

                from modules.forex.risk.forex_var_engine import (
                    get_forex_var_engine,
                )

                var_engine = get_forex_var_engine(
                    db=self.desk.db,
                )

                var_report = var_engine.calculate_portfolio_var(

                    portfolio_id=kwargs.get(
                        "portfolio_id"
                    ),

                    confidence_levels=[95, 99],

                )

                if isinstance(var_report, dict):
                    risk.update(var_report)

            except Exception:

                pass

            try:

                from modules.forex.forex_runtime_history_engine import (
                    get_forex_runtime_history_engine,
                )

                runtime_history = get_forex_runtime_history_engine(

                    db=self.desk.db,

                    tenant_id=kwargs.get("tenant_id"),

                    user_id=kwargs.get("user_id"),

                    portfolio_id=kwargs.get("portfolio_id"),

                )

                history = runtime_history.build_dashboard_packet()

            except Exception:

                history = {}

                if history:
                    risk["var_history"] = history.get(
                        "var_history",
                        [],
                    )

                    risk["drawdown_history"] = history.get(
                        "drawdown_history",
                        [],
                    )

            except Exception:

                pass

            # ==========================================================
            # Live Risk Alerts
            # ==========================================================

            alerts = []

            risk_score = risk.get("risk_score", 0)

            if risk_score >= 90:

                alerts.append({

                    "severity": "CRITICAL",

                    "category": "Portfolio",

                    "message": "Portfolio risk score exceeds critical threshold.",

                })

            elif risk_score >= 75:

                alerts.append({

                    "severity": "WARNING",

                    "category": "Portfolio",

                    "message": "Portfolio risk score is elevated.",

                })

            margin_used = summary.get("margin_used", 0)
            buying_power = summary.get("buying_power", 0)

            if buying_power > 0:

                utilization = margin_used / buying_power

                if utilization >= 0.90:

                    alerts.append({

                        "severity": "CRITICAL",

                        "category": "Margin",

                        "message": "Margin utilization exceeds 90%.",

                    })

                elif utilization >= 0.75:

                    alerts.append({

                        "severity": "WARNING",

                        "category": "Margin",

                        "message": "Margin utilization exceeds 75%.",

                    })

            leverage = summary.get("leverage", 0)

            if leverage >= 10:
                alerts.append({

                    "severity": "WARNING",

                    "category": "Leverage",

                    "message": f"Leverage is {leverage:.2f}x.",

                })

            risk["alerts"] = alerts

            try:

                from modules.forex.risk.forex_stress_testing_engine import (
                    get_forex_stress_testing_engine,
                )

                stress_engine = get_forex_stress_testing_engine(

                    db=self.desk.db,

                    portfolio=portfolio,

                    tenant_id=kwargs.get("tenant_id"),

                    user_id=kwargs.get("user_id"),

                    portfolio_id=kwargs.get("portfolio_id"),

                )

                risk["stress_tests"] = stress_engine.latest_results()

                risk["stress_summary"] = stress_engine.summary()

            except Exception as e:

                risk["stress_tests"] = []

                risk["stress_summary"] = {}

                logger.exception(
                    "Stress engine failed: %s",
                    e,
                )

            portfolio = data.get("portfolio", {})

            summary = portfolio.get("summary", {})

            st.subheader("Institutional Risk Command Center")

            # ==========================================================
            # Executive Risk Cards
            # ==========================================================

            cards = st.columns(8)

            cards[0].metric(
                "Risk Score",
                f"{risk.get('risk_score', 0):.2f}",
            )

            cards[1].metric(
                "Daily VaR",
                f"${risk.get('daily_var', risk.get('var_95', 0)):,.2f}",
            )

            cards[2].metric(
                "99% VaR",
                f"${risk.get('var_99', risk.get('var99', 0)):,.2f}",
            )

            cards[3].metric(
                "Expected Shortfall",
                f"${risk.get('expected_shortfall_value', risk.get('expected_shortfall_95', 0)):,.2f}",
            )

            cards[4].metric(

                "Drawdown",

                f"{risk.get('drawdown', 0):.2f}%",

            )

            cards[5].metric(

                "Leverage",

                f"{risk.get('leverage', 0):.2f}x",

            )

            cards[6].metric(

                "Margin Used",

                f"{summary.get('margin_used', 0):,.2f}",

            )

            cards[7].metric(

                "Free Margin",

                f"{summary.get('margin_available', 0):,.2f}",

            )

            st.divider()

            # ==========================================================
            # Exposure Dashboard
            # ==========================================================

            left, center, right = st.columns([2, 2, 1])

            with left:

                st.subheader(

                    "Currency Exposure"

                )

                exposure = risk.get(

                    "currency_exposure",

                    {},

                )

                if exposure:

                    exposure_df = pd.DataFrame(

                        {

                            "Currency":

                                list(

                                    exposure.keys()

                                ),

                            "Exposure":

                                list(

                                    exposure.values()

                                ),

                        }

                    )

                    st.bar_chart(

                        exposure_df.set_index(

                            "Currency"

                        )

                    )

                    st.dataframe(

                        exposure_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "Exposure unavailable."

                    )

            with center:

                st.subheader("Pair Exposure")

                pairs = portfolio.get(

                    "pair_exposure",

                    [],

                )

                if pairs:

                    df = pd.DataFrame(pairs)

                    if {

                        "pair",

                        "gross_exposure",

                    }.issubset(df.columns):
                        st.bar_chart(

                            df.set_index(

                                "pair"

                            )[

                                [

                                    "gross_exposure"

                                ]

                            ]

                        )

                    st.dataframe(

                        df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info("No pair exposure.")



            with right:

                st.subheader(

                    "Limits"

                )

                st.metric(

                    "Gross Exposure",

                    risk.get(

                        "gross_exposure",

                        0,

                    ),

                )

                st.metric(

                    "Net Exposure",

                    risk.get(

                        "net_exposure",

                        0,

                    ),

                )

                st.metric(

                    "Max Position",

                    risk.get(

                        "largest_position",

                        0,

                    ),

                )

                st.metric(

                    "Concentration",

                    risk.get(

                        "concentration",

                        0,

                    ),

                )

            st.divider()

            # ==========================================================
            # VaR Trend
            # ==========================================================

            st.subheader(

                "Value-at-Risk History"

            )

            var_history = risk.get(

                "var_history",

                [],

            )

            if var_history:

                history_df = pd.DataFrame(

                    var_history

                )

                if "var95" in history_df.columns:
                    st.line_chart(

                        history_df.set_index(

                            history_df.index

                        )[

                            [

                                "var95",

                                "var99",

                            ]

                        ]

                    )

                st.dataframe(

                    history_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "VaR history unavailable."

                )
            st.divider()

            st.subheader(
                "Stress Testing"
            )

            stress = risk.get(
                "stress_tests",
                [],
            )

            if stress:

                stress_df = pd.DataFrame(stress)

                st.dataframe(

                    stress_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(
                    "No stress tests available."
                )

            st.divider()

            # ==========================================================
            # Drawdown Analytics
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Drawdown History"

                )

                drawdown = risk.get(

                    "drawdown_history",

                    [],

                )

                if drawdown:

                    st.area_chart(

                        drawdown

                    )

                else:

                    st.info(

                        "No drawdown history."

                    )

            with right:

                st.subheader(

                    "Margin Utilization"

                )

                margin = pd.DataFrame(

                    [

                        {

                            "Metric":

                                "Used",

                            "Value":

                                summary.get(

                                    "margin_used",

                                    0,

                                ),

                        },

                        {

                            "Metric":

                                "Available",

                            "Value":

                                summary.get(

                                    "margin_available",

                                    0,

                                ),

                        },

                    ]

                )

                st.bar_chart(

                    margin.set_index(

                        "Metric"

                    )

                )

                st.dataframe(

                    margin,

                    use_container_width=True,

                    hide_index=True,

                )

            st.divider()

            # ==========================================================
            # Risk Alerts
            # ==========================================================

            st.subheader(

                "Active Risk Alerts"

            )

            alerts = risk.get(

                "alerts",

                [],

            )

            if alerts:

                alert_df = pd.DataFrame(

                    alerts

                )

                st.dataframe(

                    alert_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.success(

                    "No active risk alerts."

                )

            st.divider()

            st.subheader(
                "Scenario Analysis"
            )

            scenario = risk.get(
                "scenario_analysis",
                [],
            )

            if scenario:

                scenario_df = pd.DataFrame(
                    scenario
                )

                st.dataframe(

                    scenario_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(
                    "No scenario analysis."
                )

            st.divider()

            # ==========================================================
            # Position Risk
            # ==========================================================

            st.subheader(

                "Largest Position Risks"

            )

            positions = portfolio.get(
                "positions",
                []
            )

            if positions:

                risk_df = pd.DataFrame(

                    positions

                )

                st.dataframe(

                    risk_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No position risk data."

                )



            st.divider()

            st.subheader(
                "Risk Heat Map"
            )

            pair_risk = portfolio.get(
                "pair_exposure",
                [],
            )

            if pair_risk:

                df = pd.DataFrame(pair_risk)

                if {
                    "pair",
                    "gross_exposure",
                }.issubset(df.columns):
                    st.bar_chart(

                        df.set_index(
                            "pair"
                        )[[
                            "gross_exposure"
                        ]]

                    )
                st.divider()
            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(

                "Run VaR",

                use_container_width=True,

            )

            b.button(

                "Stress Test",

                use_container_width=True,

            )

            c.button(

                "Exposure",

                use_container_width=True,

            )

            d.button(

                "Flatten Risk",

                use_container_width=True,

            )

            e.button(
                "Export Risk",
                key="postion_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="position_risk_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional Risk Dashboard Loaded"

            )
        elif ws == "Performance":

            performance = data.get("performance", {})

            portfolio = data.get("portfolio", {})

            summary = portfolio.get("summary", {})

            # ==========================================================
            # Runtime History
            # ==========================================================

            try:

                from modules.forex.forex_runtime_history_engine import (
                    get_forex_runtime_history_engine,
                )

                runtime = get_forex_runtime_history_engine(

                    db=self.desk.db,

                    tenant_id=kwargs.get("tenant_id"),

                    user_id=kwargs.get("user_id"),

                    portfolio_id=kwargs.get("portfolio_id"),

                )

                history = runtime.build_dashboard_packet()

            except Exception:

                history = {}

            st.subheader("Institutional Performance Analytics")

            # ==========================================================
            # Executive Performance Cards
            # ==========================================================
            print("=" * 80)
            print("TRADING DESK RISK OBJECT")
            print(risk)
            print("=" * 80)
            st.write(risk)
            cards = st.columns(8)

            cards[0].metric(

                "Net P&L",

                f"${performance.get('net_pnl', 0):,.2f}",

            )

            cards[1].metric(

                "Gross P&L",

                f"${performance.get('gross_pnl', 0):,.2f}",

            )

            cards[2].metric(

                "Today's P&L",

                f"${performance.get('daily_pnl', 0):,.2f}",

            )

            cards[3].metric(

                "Win Rate",

                f"{performance.get('win_rate', 0):.1f}%",

            )

            cards[4].metric(

                "Sharpe",

                f"{performance.get('sharpe', 0):.2f}",

            )

            cards[5].metric(

                "Sortino",

                f"{performance.get('sortino', 0):.2f}",

            )

            cards[6].metric(

                "Profit Factor",

                f"{performance.get('profit_factor', 0):.2f}",

            )

            cards[7].metric(

                "Expectancy",

                f"{performance.get('expectancy', 0):.2f}",

            )

            st.divider()

            # ==========================================================
            # Equity Curve / Cumulative Return
            # ==========================================================

            left, right = st.columns([2, 1])

            with left:

                st.subheader("Equity Curve")

                portfolio_trends = history.get(
                    "portfolio_trends",
                    {}
                )

                equity = portfolio_trends.get(
                    "series",
                    []
                )

                if equity:

                    df = pd.DataFrame(equity)

                    if {
                        "created_at",
                        "equity",
                    }.issubset(df.columns):

                        st.line_chart(

                            df.set_index(
                                "created_at"
                            )[["equity"]]

                        )

                    else:

                        st.dataframe(
                            df,
                            use_container_width=True,
                        )

                else:

                    st.info(

                        "No equity history."

                    )

            with right:

                st.subheader(

                    "Portfolio Snapshot"

                )

                st.metric(

                    "Equity",

                    f"${summary.get('equity', 0):,.2f}",

                )

                st.metric(

                    "Cash",

                    f"${summary.get('cash_balance', 0):,.2f}",

                )

                st.metric(

                    "Buying Power",

                    f"${summary.get('buying_power', 0):,.2f}",

                )

                st.metric(

                    "Open Positions",

                    summary.get(

                        "open_positions",

                        0,

                    ),

                )

            st.divider()

            # ==========================================================
            # Returns Analysis
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Daily Returns"

                )

                returns = []

                if equity:

                    df = pd.DataFrame(equity)

                    if "equity" in df.columns:
                        df["daily_return"] = df["equity"].pct_change()

                        returns = df["daily_return"].fillna(0)
                        st.bar_chart(returns)



                else:

                    st.info(

                        "No daily returns."

                    )

            with right:

                st.subheader(

                    "Monthly Returns"

                )

                monthly = []

                if equity:

                    df = pd.DataFrame(equity)

                    if {
                        "created_at",
                        "equity",
                    }.issubset(df.columns):
                        df["created_at"] = pd.to_datetime(df["created_at"])

                        monthly = (

                            df

                            .set_index("created_at")

                            .resample("M")

                            .last()["equity"]

                            .pct_change()

                            .fillna(0)

                        )

                st.line_chart(monthly)

            st.divider()

            # ==========================================================
            # Trade Statistics
            # ==========================================================

            stats_left, stats_right = st.columns(2)

            # ----------------------------------------------------------
            # Normalize portfolio objects
            # ----------------------------------------------------------

            portfolio_summary = portfolio.get(
                "summary",
                {},
            )

            risk_summary = portfolio.get(
                "risk",
                risk,
            )

            margin_summary = portfolio.get(
                "margin",
                margin,
            )

            performance_summary = portfolio.get(
                "performance",
                performance,
            )

            directional = risk_summary.get(
                "directional",
                {},
            )

            portfolio_summary["gross_exposure"] = risk_summary.get(
                "gross_exposure",
                portfolio_summary.get(
                    "gross_exposure",
                    0,
                ),
            )

            portfolio_summary["net_exposure"] = risk_summary.get(
                "net_exposure",
                portfolio_summary.get(
                    "net_exposure",
                    0,
                ),
            )

            portfolio_summary["long_exposure"] = directional.get(
                "long",
                portfolio_summary.get(
                    "long_exposure",
                    0,
                ),
            )

            portfolio_summary["short_exposure"] = directional.get(
                "short",
                portfolio_summary.get(
                    "short_exposure",
                    0,
                ),
            )

            # ==========================================================
            # Portfolio Statistics
            # ==========================================================

            with stats_left:

                st.subheader(
                    "Portfolio Statistics"
                )

                portfolio_stats = [

                    {
                        "Metric": "Open Positions",
                        "Value": portfolio_summary.get(
                            "open_positions",
                            0,
                        ),
                    },

                    {
                        "Metric": "Long Positions",
                        "Value": portfolio_summary.get(
                            "long_count",
                            0,
                        ),
                    },

                    {
                        "Metric": "Short Positions",
                        "Value": portfolio_summary.get(
                            "short_count",
                            0,
                        ),
                    },

                    {
                        "Metric": "Gross Exposure",
                        "Value": portfolio_summary.get(
                            "gross_exposure",
                            0,
                        ),
                    },

                    {
                        "Metric": "Net Exposure",
                        "Value": portfolio_summary.get(
                            "net_exposure",
                            0,
                        ),
                    },

                    {
                        "Metric": "Long Exposure",
                        "Value": portfolio_summary.get(
                            "long_exposure",
                            0,
                        ),
                    },

                    {
                        "Metric": "Short Exposure",
                        "Value": portfolio_summary.get(
                            "short_exposure",
                            0,
                        ),
                    },

                    {
                        "Metric": "Diversification",
                        "Value": portfolio_summary.get(
                            "diversification_ratio",
                            0,
                        ),
                    },

                    {
                        "Metric": "Effective Positions",
                        "Value": portfolio_summary.get(
                            "effective_positions",
                            portfolio_summary.get(
                                "open_positions",
                                0,
                            ),
                        ),
                    },

                    {
                        "Metric": "Leverage",
                        "Value": margin_summary.get(
                            "leverage",
                            0,
                        ),
                    },

                    {
                        "Metric": "Margin Used",
                        "Value": margin_summary.get(
                            "margin_used",
                            0,
                        ),
                    },

                    {
                        "Metric": "Buying Power",
                        "Value": margin_summary.get(
                            "buying_power",
                            0,
                        ),
                    },

                    {
                        "Metric": "Margin Available",
                        "Value": margin_summary.get(
                            "margin_available",
                            0,
                        ),
                    },

                    {
                        "Metric": "Cash Balance",
                        "Value": portfolio_summary.get(
                            "cash_balance",
                            portfolio_summary.get(
                                "cash",
                                0,
                            ),
                        ),
                    },

                ]

                portfolio_stats_df = pd.DataFrame(
                    portfolio_stats,
                )

                st.dataframe(

                    portfolio_stats_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # ==========================================================
            # Risk & Performance
            # ==========================================================

            with stats_right:

                st.subheader(
                    "Risk & Performance"
                )

                risk_stats = [

                    {
                        "Metric": "Risk Score",
                        "Value": risk_summary.get(
                            "risk_score",
                            0,
                        ),
                    },

                    {
                        "Metric": "Daily VaR (95%)",
                        "Value": risk_summary.get(
                            "daily_var",
                            risk_summary.get(
                                "var_95",
                                0,
                            ),
                        ),
                    },

                    {
                        "Metric": "Expected Shortfall",
                        "Value": risk_summary.get(
                            "expected_shortfall_value",
                            risk_summary.get(
                                "expected_shortfall",
                                risk_summary.get(
                                    "expected_shortfall_95",
                                    0,
                                ),
                            ),
                        ),
                    },

                    {
                        "Metric": "Maximum Drawdown",
                        "Value": risk_summary.get(
                            "drawdown",
                            0,
                        ),
                    },

                    {
                        "Metric": "Sharpe Ratio",
                        "Value": performance_summary.get(
                            "sharpe",
                            0,
                        ),
                    },

                    {
                        "Metric": "Sortino Ratio",
                        "Value": performance_summary.get(
                            "sortino",
                            0,
                        ),
                    },

                    {
                        "Metric": "Profit Factor",
                        "Value": performance_summary.get(
                            "profit_factor",
                            0,
                        ),
                    },

                    {
                        "Metric": "Win Rate",
                        "Value": performance_summary.get(
                            "win_rate",
                            0,
                        ),
                    },

                    {
                        "Metric": "Expectancy",
                        "Value": performance_summary.get(
                            "expectancy",
                            0,
                        ),
                    },

                ]

                risk_stats_df = pd.DataFrame(
                    risk_stats,
                )

                st.dataframe(

                    risk_stats_df,

                    use_container_width=True,

                    hide_index=True,

                )

            st.divider()



            # ==========================================================
            # Portfolio Allocation
            # ==========================================================

            st.subheader(
                "Portfolio Allocation"
            )

            positions = portfolio.get(
                "positions",
                []
            )

            allocation = []

            total = summary.get(
                "total_market_value",
                0,
            )

            for pos in positions:
                mv = pos.get(
                    "market_value",
                    0,
                )

                allocation.append({

                    "pair": pos.get("pair"),

                    "allocation_pct":

                        (mv / total * 100)

                        if total

                        else 0,

                })

            if allocation:

                allocation_df = pd.DataFrame(allocation)

                if {
                    "pair",
                    "allocation_pct",
                }.issubset(allocation_df.columns):
                    st.bar_chart(

                        allocation_df.set_index("pair")[
                            ["allocation_pct"]
                        ]

                    )

                st.dataframe(

                    allocation_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(
                    "No allocation data available."
                )

            st.divider()



            # ==========================================================
            # Performance Timeline
            # ==========================================================

            st.subheader(

                "Performance Timeline"

            )

            timeline = equity

            if timeline:

                timeline_df = pd.DataFrame(

                    timeline

                )

                if "pnl" in timeline_df.columns:
                    st.area_chart(

                        timeline_df.set_index(

                            timeline_df.index

                        )["pnl"]

                    )

                st.dataframe(

                    timeline_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "Timeline unavailable."

                )

            st.divider()

            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(
                "Performance Report",
                key="performance_report_btn",
                use_container_width=True,
            )

            b.button(
                "Trade Attribution",
                key="performance_attribution_btn",
                use_container_width=True,
            )

            c.button(
                "Export CSV",
                key="performance_export_csv_btn",
                use_container_width=True,
            )

            d.button(
                "Export PDF",
                key="performance_export_pdf_btn",
                use_container_width=True,
            )

            e.button(
                "Refresh",
                key="performance_refresh_btn",
                use_container_width=True,
            )

            f.button(
                "Analytics",
                key="performance_analytics_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional Performance Dashboard Loaded"

            )
        elif ws == "Strategy":

            strategy = data.get("strategy_lab", {})

            ai = data.get("executive_ai", {})

            # ==========================================================
            # Live Strategy Engines
            # ==========================================================

            try:

                from modules.forex.forex_ai import (
                    get_forex_ai,
                )

                ai_engine = get_forex_ai(
                    db=self.desk.db,
                )

                ai = ai_engine.dashboard_packet(
                    portfolio_id=kwargs.get("portfolio_id"),
                )

            except Exception:
                pass

            try:

                from modules.forex.forex_alpha_model import (
                    get_forex_alpha_model,
                )

                alpha_engine = get_forex_alpha_model(
                    db=self.desk.db,
                )

                alpha = alpha_engine.dashboard_packet(
                    portfolio_id=kwargs.get("portfolio_id"),
                )

            except Exception:

                alpha = {}

            try:

                from modules.forex.forex_strategy_lab import (
                    get_forex_strategy_lab,
                )

                strategy_engine = get_forex_strategy_lab(
                    db=self.desk.db,
                )

                strategy = strategy_engine.dashboard_packet(
                    portfolio_id=kwargs.get("portfolio_id"),
                )

            except Exception:
                pass

            recommendations = strategy.get(

                "recommendations",

                []

            )

            opportunities = strategy.get(

                "opportunities",

                []

            )

            strategies = strategy.get(

                "strategies",

                []

            )

            st.subheader(

                "Institutional AI Strategy Center"

            )

            # ==========================================================
            # Executive KPI Cards
            # ==========================================================
            print("=" * 80)
            print("TRADING DESK RISK OBJECT")
            print(risk)
            print("=" * 80)
            print("risk keys:", list(risk.keys()))
            cards = st.columns(8)

            cards[0].metric(

                "AI Signals",

                len(recommendations),

            )

            cards[1].metric(

                "Active Strategies",

                len(strategies),

            )

            cards[2].metric(

                "Market Opportunities",

                len(opportunities),

            )

            cards[3].metric(

                "Buy Signals",

                strategy.get(

                    "buy_signals",

                    0,

                ),

            )

            cards[4].metric(

                "Sell Signals",

                strategy.get(

                    "sell_signals",

                    0,

                ),

            )

            cards[5].metric(

                "Average Confidence",

                f"{strategy.get('avg_confidence', 0):.1f}%",

            )

            cards[6].metric(

                "Alpha Score",

                alpha.get(

                    "alpha_score",

                    ai.get(

                        "score",

                        0,

                    ),

                ),

            )

            cards[7].metric(

                "Market Regime",

                alpha.get(

                    "regime",

                    ai.get(

                        "regime",

                        "UNKNOWN",

                    ),

                ),

            )

            st.divider()

            # ==========================================================
            # Executive Summary
            # ==========================================================

            left, right = st.columns([2, 1])

            with left:

                st.subheader(

                    "Executive AI Summary"

                )

                summary = alpha.get(

                    "executive_summary",

                    ai.get(

                        "summary",

                        "No AI summary available.",

                    ),

                )

                st.info(

                    summary

                )

            with right:

                st.subheader(

                    "Market Outlook"

                )

                st.metric(

                    "Bias",

                    alpha.get(

                        "bias",

                        ai.get(

                            "bias",

                            "Neutral",

                        ),

                    ),

                )

                confidence_value = alpha.get(

                    'confidence',

                    ai.get(

                        'confidence',

                        0,

                    ),

                )

                st.metric(

                    "Confidence",

                    f"{confidence_value:.1f}%",

                )

                st.metric(

                    "Market Regime",

                    alpha.get(

                        "market_regime",

                        ai.get(

                            "regime",

                            "UNKNOWN",

                        ),

                    ),

                )

            st.divider()

            # ==========================================================
            # AI Recommendations
            # ==========================================================

            st.subheader(

                "Trade Recommendations"

            )

            if recommendations:

                rec_df = pd.DataFrame(

                    alpha.get(
                        "recommendations",
                        recommendations,
                    )

                )

                preferred = [

                    "pair",

                    "direction",

                    "confidence",

                    "conviction",

                    "entry",

                    "target",

                    "stop",

                    "risk_reward",

                    "strategy",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in rec_df.columns

                ]

                if cols:
                    rec_df = rec_df[cols]

                st.dataframe(

                    rec_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No recommendations available."

                )

            st.divider()

            # ==========================================================
            # Strategy Performance
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Strategy Performance"

                )

                if strategies:

                    strategy_df = pd.DataFrame(

                        alpha.get(
                            "strategy_rankings",
                            strategies,
                        )

                    )

                    if "return_pct" in strategy_df.columns:
                        st.bar_chart(

                            strategy_df.set_index(

                                "name"

                            )[

                                "return_pct"

                            ]

                        )

                    st.dataframe(

                        strategy_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No strategy performance available."

                    )

            with right:

                st.subheader(

                    "Opportunity Scanner"

                )

                if opportunities:

                    opp_df = pd.DataFrame(

                        alpha.get(
                            "opportunities",
                            opportunities,
                        )

                    )

                    st.dataframe(

                        opp_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No market opportunities."

                    )

            st.divider()

            # ==========================================================
            # AI Signal Distribution
            # ==========================================================

            st.subheader(
                "Signal Distribution"
            )

            # ==========================================================
            # Build Signal Counts From Live Recommendations
            # ==========================================================

            live_recommendations = alpha.get(
                "recommendations",
                recommendations,
            )

            buy_count = 0
            sell_count = 0
            hold_count = 0

            for rec in live_recommendations:

                direction = str(
                    rec.get(
                        "direction",
                        rec.get(
                            "signal",
                            "HOLD",
                        ),
                    )
                ).upper()

                if direction == "BUY":

                    buy_count += 1

                elif direction == "SELL":

                    sell_count += 1

                else:

                    hold_count += 1

            signal_df = pd.DataFrame(

                {

                    "Signal": [

                        "BUY",
                        "SELL",
                        "HOLD",

                    ],

                    "Count": [

                        buy_count,
                        sell_count,
                        hold_count,

                    ],

                }

            )

            st.bar_chart(

                signal_df.set_index(
                    "Signal"
                )

            )

            st.dataframe(

                signal_df,

                use_container_width=True,

                hide_index=True,

            )

            st.divider()
            st.divider()

            st.subheader(
                "Market Regime"
            )

            regime = alpha.get(
                "market_regime",
                {},
            )

            if regime:

                st.json(regime)

            else:

                st.info(
                    "No market regime available."
                )

            st.subheader(
                "AI Consensus"
            )

            consensus = ai.get(
                "consensus",
                [],
            )

            if consensus:

                consensus_df = pd.DataFrame(consensus)

                st.dataframe(

                    consensus_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(
                    "No AI consensus available."
                )

            # ==========================================================
            # Strategy History
            # ==========================================================

            st.subheader(

                "Strategy History"

            )

            history = strategy.get(

                "history",

                [],

            )

            if history:

                history_df = pd.DataFrame(

                    history

                )

                st.dataframe(

                    history_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No strategy history."

                )

            st.divider()

            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(
                "Run AI",
                key="strategy_run_ai_btn",
                use_container_width=True,
            )

            b.button(
                "Generate Signals",
                key="strategy_generate_signals_btn",
                use_container_width=True,
            )

            c.button(
                "Scan Market",
                key="strategy_scan_market_btn",
                use_container_width=True,
            )

            d.button(
                "Optimize",
                key="strategy_optimize_btn",
                use_container_width=True,
            )

            e.button(
                "Export",
                key="strategy_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="strategy_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional AI Strategy Center Loaded"

            )
        elif ws == "Journal":

            journal = data.get("journal", {})

            # ==========================================================
            # Live Journal Engines
            # ==========================================================

            # ==========================================================
            # Live Trade Journal
            # ==========================================================

            try:

                from modules.forex.forex_trade_journal import (
                    get_forex_trade_journal,
                )

                journal_engine = get_forex_trade_journal(
                    db=self.desk.db,
                )

                journal_data = journal_engine.entries(
                    limit=250,
                )

                journal = {

                    "entries": journal_data.get(
                        "entries",
                        [],
                    ),

                    "count": journal_data.get(
                        "count",
                        0,
                    ),

                    "status": journal_data.get(
                        "status",
                        "READY",
                    ),

                }

            except Exception:

                journal = {

                    "entries": [],

                    "count": 0,

                    "status": "ERROR",

                }

            entries = journal.get(
                "entries",
                [],
            )

            trades = entries

            notes = entries

            mistakes = journal.get(

                "mistakes",

                [],

            )

            st.subheader(

                "Institutional Trading Journal"

            )

            # ==========================================================
            # Executive Cards
            # ==========================================================
            print("=" * 80)
            print("TRADING DESK RISK OBJECT")
            print(risk)
            print("=" * 80)
            print("risk keys:", list(risk.keys()))
            cards = st.columns(8)

            cards[0].metric(
                "Journal Entries",
                journal.get(
                    "count",
                    len(entries),
                ),
            )

            cards[1].metric(
                "Recorded Trades",
                len(entries),
            )

            cards[2].metric(
                "Closed Trades",
                journal.get(
                    "closed_trades",
                    len(trades),
                ),
            )

            cards[3].metric(
                "Win Rate",
                f"{journal.get('win_rate', 0):.1f}%"
            )

            cards[4].metric(
                "Average Hold",
                journal.get(
                    "average_hold_time",
                    journal.get(
                        "average_hold",
                        "0h",
                    ),
                ),
            )

            cards[5].metric(
                "Realized P&L",
                f"${journal.get('realized_pnl', 0):,.2f}"
            )

            cards[6].metric(
                "Average R-Multiple",
                f"{journal.get('avg_r_multiple', 0):.2f}"
            )

            cards[7].metric(
                "Expectancy",
                f"{journal.get('expectancy', 0):.2f}"
            )

            st.divider()

            # ==========================================================
            # Trade Journal
            # ==========================================================

            st.subheader(

                "Trade Journal"

            )

            if trades:

                df = pd.DataFrame(

                    trades

                )

                preferred = [

                    "date",

                    "pair",

                    "side",

                    "entry",

                    "exit",

                    "pnl",

                    "strategy",

                    "setup",

                    "emotion",

                    "notes",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in df.columns

                ]

                if cols:
                    df = df[cols]

                st.dataframe(

                    df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No journaled trades."

                )

            st.divider()

            # ==========================================================
            # Trading Mistakes
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Mistake Log"

                )

                if mistakes:

                    mistake_df = pd.DataFrame(

                        mistakes

                    )

                    st.dataframe(

                        mistake_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.success(

                        "No recorded mistakes."

                    )

            with right:

                st.subheader(

                    "Trading Notes"

                )

                if notes:

                    notes_df = pd.DataFrame(

                        notes

                    )

                    st.dataframe(

                        notes_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No notes available."

                    )

            st.divider()

            # ==========================================================
            # Emotional Analytics
            # ==========================================================

            st.subheader(

                "Emotional Analytics"

            )

            emotions = journal.get(
                "emotion_distribution",
                journal.get(
                    "emotion_summary",
                    {},
                ),
            )

            if emotions:

                emotion_df = pd.DataFrame(

                    {

                        "Emotion":

                            list(

                                emotions.keys()

                            ),

                        "Count":

                            list(

                                emotions.values()

                            ),

                    }

                )

                st.bar_chart(

                    emotion_df.set_index(

                        "Emotion"

                    )

                )

                st.dataframe(

                    emotion_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No emotional analytics."

                )

            st.divider()

            # ==========================================================
            # Strategy Review
            # ==========================================================

            st.subheader(

                "Strategy Review"

            )

            review = journal.get(
                "trade_review",
                journal.get(
                    "strategy_review",
                    [],
                ),
            )

            if review:

                review_df = pd.DataFrame(

                    review

                )

                st.dataframe(

                    review_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No strategy review available."

                )

            st.divider()

            # ==========================================================
            # Improvement Tracker
            # ==========================================================

            st.subheader(

                "Improvement Tracker"

            )

            improvements = journal.get(
                "improvement_tracker",
                journal.get(
                    "improvements",
                    [],
                ),
            )

            if improvements:

                improvement_df = pd.DataFrame(

                    improvements

                )

                st.dataframe(

                    improvement_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No improvement items."

                )

            st.divider()

            st.divider()

            st.subheader(
                "Trade Distribution"
            )

            if trades:

                trade_df = pd.DataFrame(trades)

                if "strategy" in trade_df.columns:
                    dist = (

                        trade_df["strategy"]

                        .value_counts()

                        .rename_axis("Strategy")

                        .reset_index(name="Trades")

                    )

                    st.bar_chart(

                        dist.set_index(
                            "Strategy"
                        )

                    )

                    st.dataframe(

                        dist,

                        use_container_width=True,

                        hide_index=True,

                    )

            else:

                st.info(
                    "No trade distribution available."
                )

            st.divider()

            st.subheader(
                "Journal Activity"
            )

            if trades:

                trade_df = pd.DataFrame(trades)

                if "date" in trade_df.columns:
                    trade_df["date"] = pd.to_datetime(
                        trade_df["date"]
                    )

                    monthly = (

                        trade_df

                        .set_index("date")

                        .resample("M")

                        .size()

                    )

                    st.line_chart(monthly)

            else:

                st.info(
                    "No journal activity."
                )

            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(
                "New Journal Entry",
                key="journal_new_entry_btn",
                use_container_width=True,
            )

            b.button(
                "Review Trades",
                key="journal_review_trades_btn",
                use_container_width=True,
            )

            c.button(
                "Export Journal",
                key="journal_export_btn",
                use_container_width=True,
            )

            d.button(
                "Performance Review",
                key="journal_performance_review_btn",
                use_container_width=True,
            )

            e.button(
                "Psychology Report",
                key="journal_psychology_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="journal_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional Trading Journal Loaded"

            )
        elif ws == "Providers":

            providers = data.get(

                "provider_health",

                {},

            )

            st.subheader(

                "Market Data Provider Operations Center"

            )

            # ==========================================================
            # Executive KPI Cards
            # ==========================================================

            summary = providers.get(

                "summary",

                {},

            )
            print("=" * 80)
            print("TRADING DESK RISK OBJECT")
            print(risk)
            print("=" * 80)
            print("risk keys:", list(risk.keys()))
            cards = st.columns(8)

            cards[0].metric(

                "Providers",

                summary.get(

                    "provider_count",

                    0,

                ),

            )

            cards[1].metric(

                "Healthy",

                summary.get(

                    "healthy",

                    0,

                ),

            )

            cards[2].metric(

                "Warning",

                summary.get(

                    "warning",

                    0,

                ),

            )

            cards[3].metric(

                "Offline",

                summary.get(

                    "offline",

                    0,

                ),

            )

            cards[4].metric(

                "Avg Latency",

                f"{summary.get('avg_latency_ms', 0):,.0f} ms",

            )

            cards[5].metric(

                "Success Rate",

                f"{summary.get('success_rate', 0):.1f}%",

            )

            cards[6].metric(

                "Failovers",

                summary.get(

                    "failovers",

                    0,

                ),

            )

            cards[7].metric(

                "Health Score",

                f"{summary.get('health_score', 0):.1f}",

            )

            st.divider()

            # ==========================================================
            # Provider Health Table
            # ==========================================================

            st.subheader(

                "Provider Status"

            )

            provider_rows = providers.get(

                "providers",

                [],

            )

            if provider_rows:

                provider_df = pd.DataFrame(

                    provider_rows

                )

                preferred = [

                    "provider",

                    "status",

                    "latency_ms",

                    "success_rate",

                    "requests_today",

                    "failures",

                    "health_score",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in provider_df.columns

                ]

                if cols:
                    provider_df = provider_df[cols]

                st.dataframe(

                    provider_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No provider information."

                )

            st.divider()

            # ==========================================================
            # Latency Analytics
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Latency"

                )

                if provider_rows:

                    latency = pd.DataFrame(

                        provider_rows

                    )

                    if {

                        "provider",

                        "latency_ms",

                    }.issubset(

                        latency.columns

                    ):
                        latency = latency[

                            [

                                "provider",

                                "latency_ms",

                            ]

                        ]

                        st.bar_chart(

                            latency.set_index(

                                "provider"

                            )

                        )

                        st.dataframe(

                            latency,

                            use_container_width=True,

                            hide_index=True,

                        )

                else:

                    st.info(

                        "No latency metrics."

                    )

            with right:

                st.subheader(

                    "Success Rate"

                )

                if provider_rows:

                    success = pd.DataFrame(

                        provider_rows

                    )

                    if {

                        "provider",

                        "success_rate",

                    }.issubset(

                        success.columns

                    ):
                        success = success[

                            [

                                "provider",

                                "success_rate",

                            ]

                        ]

                        st.bar_chart(

                            success.set_index(

                                "provider"

                            )

                        )

                        st.dataframe(

                            success,

                            use_container_width=True,

                            hide_index=True,

                        )

                else:

                    st.info(

                        "No provider metrics."

                    )

            st.divider()

            # ==========================================================
            # Provider Activity
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Provider Utilization"

                )

                if provider_rows:

                    util = pd.DataFrame(

                        provider_rows

                    )

                    if {

                        "provider",

                        "requests_today",

                    }.issubset(

                        util.columns

                    ):
                        util = util[

                            [

                                "provider",

                                "requests_today",

                            ]

                        ]

                        st.bar_chart(

                            util.set_index(

                                "provider"

                            )

                        )

                        st.dataframe(

                            util,

                            use_container_width=True,

                            hide_index=True,

                        )

                else:

                    st.info(

                        "No utilization statistics."

                    )

            with right:

                st.subheader(

                    "Failure Analysis"

                )

                if provider_rows:

                    failure = pd.DataFrame(

                        provider_rows

                    )

                    if {

                        "provider",

                        "failures",

                    }.issubset(

                        failure.columns

                    ):
                        failure = failure[

                            [

                                "provider",

                                "failures",

                            ]

                        ]

                        st.bar_chart(

                            failure.set_index(

                                "provider"

                            )

                        )

                        st.dataframe(

                            failure,

                            use_container_width=True,

                            hide_index=True,

                        )

                else:

                    st.info(

                        "No failure statistics."

                    )

            st.divider()

            # ==========================================================
            # Provider Events
            # ==========================================================

            st.subheader(

                "Provider Events"

            )

            events = providers.get(

                "events",

                [],

            )

            if events:

                event_df = pd.DataFrame(

                    events

                )

                st.dataframe(

                    event_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.success(

                    "No provider alerts."

                )

            st.divider()

            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(

                "Refresh Providers",

                use_container_width=True,

            )

            b.button(

                "Run Health Check",

                use_container_width=True,

            )

            c.button(

                "Reconnect",

                use_container_width=True,

            )

            d.button(

                "Provider Report",

                use_container_width=True,

            )

            e.button(
                "Export",
                key="diagnostics_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="diagnostics_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Provider Operations Center Loaded"

            )

        elif ws == "Pending Orders (Detail)":

            portfolio_engine = get_forex_portfolio_engine(
                db=self.desk.db,
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                portfolio_id=kwargs.get("portfolio_id"),
            )
            render_forex_pending_orders_dashboard(
                db=self.desk.db,
                portfolio_engine=portfolio_engine,
                **kwargs,
            )
            return

        elif ws == "Live Positions (Detail)":

            portfolio_engine = get_forex_portfolio_engine(
                db=self.desk.db,
                tenant_id=kwargs.get("tenant_id"),
                user_id=kwargs.get("user_id"),
                portfolio_id=kwargs.get("portfolio_id"),
            )
            render_forex_positions_dashboard(
                db=self.desk.db,
                portfolio_engine=portfolio_engine,
                **kwargs,
            )
            return


_INSTANCE=None
def get_forex_trading_desk_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None or getattr(_INSTANCE, "db", None) is not db:
        _INSTANCE = ForexTradingDeskDashboard(db=db)
    return _INSTANCE

def render_forex_trading_desk_dashboard(db=None, **kwargs):
    return get_forex_trading_desk_dashboard(db=db).render(**kwargs)