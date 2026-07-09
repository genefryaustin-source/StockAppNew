
"""
modules/forex/forex_trading_desk_dashboard.py
"""
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
from modules.forex.forex_portfolio_manager import (
    get_forex_portfolio_manager,
)
try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px

except Exception:
    st=None
    pd=None
import logging

logger = logging.getLogger(__name__)
from modules.forex.forex_trading_desk import get_forex_trading_desk
from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
from modules.forex.forex_order_management_engine import (
    get_forex_order_management_engine,
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

        terminal = self._as_dict(snapshot)

        account = terminal.get("account", {})
        portfolio = terminal.get("portfolio", {})
        margin = terminal.get("margin", {})
        risk = terminal.get("risk", {})
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

        portfolio["summary"] = summary
        portfolio["positions"] = positions
        portfolio["currency_exposure"] = currency_exposure
        portfolio["pair_exposure"] = pair_exposure
        portfolio["performance"] = performance
        portfolio["margin"] = margin
        portfolio["risk"] = risk
        portfolio["system"] = terminal.get("system", {})

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

    def render(self, **kwargs):

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

                )

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

            f"Providers : {data.get('provider_health', {}).get('summary', {}).get('healthy', 0)}"

        )

        status_cols[5].info(

            f"Latency : {execution.get('latency_ms', 0)} ms"

        )

        status_cols[6].info(

            f"Spread : {execution.get('avg_spread', 0)}"

        )

        status_cols[7].success("AI ONLINE")

        st.divider()
        st.subheader("Live Market")

        quotes = data.get(

            "watchlist",

            []

        )

        if quotes:

            ticker = pd.DataFrame(quotes)

            preferred = [

                "pair",

                "bid",

                "ask",

                "spread",

                "change_pct",

                "signal",

            ]

            cols = [

                c

                for c in preferred

                if c in ticker.columns

            ]

            if cols:
                ticker = ticker[cols]

            st.dataframe(

                ticker,

                use_container_width=True,

                hide_index=True,

                height=180,

            )

        else:

            st.info(

                "No live quotes available."

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
            ],
            horizontal=True,
        )

        if ws == "Portfolio":

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

            row1[6].metric(
                "Daily P&L",
                f"{summary.get('daily_pnl', 0):,.2f}",
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

                st.subheader(
                    "Daily Performance"
                )

                pnl_history = performance.get(

                    "daily_pnl",

                    [],

                )

                if pnl_history:

                    st.bar_chart(

                        pnl_history

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

                st.metric(

                    "VaR",

                    risk.get(

                        "var95",

                        0,

                    ),

                )

                st.metric(

                    "Drawdown",

                    risk.get(

                        "drawdown",

                        0,

                    ),

                )

                st.metric(

                    "Leverage",

                    risk.get(

                        "leverage",

                        0,

                    ),

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

                activity = portfolio.get(
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
                st.session_state["ai_trade_new_order"] = True
                print("=" * 80)
                print("TOP OF CLOSE DIALOG")
                print("close_position_selected_id =",
                      st.session_state.get("close_position_selected_id"))
                print("widget =",
                      st.session_state.get("close_position_selector_widget"))
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

                        with st.spinner(

                                "Submitting order..."

                        ):

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
                                portfolio_id=kwargs.get("portfolio_id"),
                                account_id=kwargs.get("account_id"),
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
            # Performance Attribution
            # ==========================================================

            st.divider()

            st.subheader("Performance Attribution")

            left, center, right = st.columns([2, 2, 1])

            with left:

                attribution = performance.get(

                    "attribution",

                    {},

                )

                if attribution:

                    att_df = pd.DataFrame(

                        [

                            {

                                "Source": k,

                                "PnL": v,

                            }

                            for k, v in

                            attribution.items()

                        ]

                    )

                    st.bar_chart(

                        att_df.set_index(

                            "Source"

                        )

                    )

                    st.dataframe(

                        att_df,

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

                {},

            )

            left, right = st.columns(2)

            with left:

                if allocation:

                    alloc_df = pd.DataFrame(

                        {

                            "Asset":

                                list(

                                    allocation.keys()

                                ),

                            "Weight":

                                list(

                                    allocation.values()

                                ),

                        }

                    )

                    st.dataframe(

                        alloc_df,

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

                            names="Asset",

                            values="Weight",

                            hole=.45,

                        )

                        st.plotly_chart(

                            fig,

                            use_container_width=True,

                        )

                    except Exception:

                        pass

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
            # Watchlist
            # ==========================================================

            st.divider()

            st.subheader(

                "Forex Watchlist"

            )

            watchlist = data.get(

                "watchlist",

                [],

            )

            if watchlist:

                watch_df = pd.DataFrame(

                    watchlist

                )

                preferred = [

                    "pair",

                    "bid",

                    "ask",

                    "spread",

                    "change_pct",

                    "volume",

                    "atr",

                    "signal",

                ]

                cols = [

                    c

                    for c in preferred

                    if c in watch_df.columns

                ]

                if cols:
                    watch_df = watch_df[cols]

                st.dataframe(

                    watch_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No watchlist available."

                )

            # ==========================================================
            # Account Summary
            # ==========================================================

            st.divider()

            st.subheader(

                "Account Summary"

            )

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

            st.success(
                "Portfolio Dashboard Loaded Successfully"
            )

        elif ws == "Orders":

            portfolio = data.get("portfolio", {})

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

            st.subheader("Institutional Order Management")

            # ==========================================================
            # Executive Order Metrics
            # ==========================================================

            row = st.columns(8)

            row[0].metric(
                "Open Orders",
                len(open_orders),
            )

            row[1].metric(
                "Filled",
                len(filled_orders),
            )

            row[2].metric(
                "Executions",
                len(execution_history),
            )

            row[3].metric(
                "Pending",
                len(pending_orders),
            )

            row[4].metric(
                "Fill Rate",
                f"{execution.get('fill_rate', 0):.1f}%"
            )

            row[5].metric(
                "Latency",
                f"{execution.get('latency_ms', 0):,.0f} ms"
            )

            row[6].metric(
                "Slippage",
                f"{execution.get('avg_slippage', 0):.4f}"
            )

            row[7].metric(
                "Broker",
                broker_status.get(
                    "name",
                    "Paper",
                ),
            )

            st.divider()

            # ==========================================================
            # Execution Charts
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Orders by Status"

                )

                status = {

                    "Open": len(open_orders),

                    "Pending": len(pending_orders),

                    "Filled": len(filled_orders),

                    "Cancelled": len(cancelled_orders),

                }

                status_df = pd.DataFrame(

                    {

                        "Status":

                            list(status.keys()),

                        "Orders":

                            list(status.values()),

                    }

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

                metrics_df = pd.DataFrame(

                    [

                        {

                            "Metric": k,

                            "Value": v,

                        }

                        for k, v in

                        execution.items()

                    ]

                )

                st.dataframe(

                    metrics_df,

                    use_container_width=True,

                    hide_index=True,

                )

            st.divider()

            # ==========================================================
            # Open Orders
            # ==========================================================

            st.subheader(

                "Open Orders"

            )

            if open_orders:

                df = pd.DataFrame(

                    open_orders

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

            if filled_orders:

                df = pd.DataFrame(

                    filled_orders

                )

                preferred = [

                    "pair",

                    "side",

                    "filled_qty",

                    "avg_fill_price",

                    "commission",

                    "slippage",

                    "filled_at",

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

                    "No filled orders."

                )

            st.divider()

            # ==========================================================
            # Pending / Cancelled
            # ==========================================================

            left, right = st.columns(2)

            with left:

                st.subheader(

                    "Pending Orders"

                )

                if pending_orders:

                    st.dataframe(

                        pd.DataFrame(

                            pending_orders

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No pending orders."

                    )

            with right:

                st.subheader(

                    "Cancelled Orders"

                )

                if cancelled_orders:

                    st.dataframe(

                        pd.DataFrame(

                            cancelled_orders

                        ),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No cancelled orders."

                    )

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

            executions = execution_history

            if executions:

                exec_df = pd.DataFrame(

                    executions

                )

                preferred = [

                    "time",

                    "pair",

                    "side",

                    "quantity",

                    "price",

                    "slippage",

                    "latency",

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

            timeline = execution_history

            if timeline:

                timeline_df = pd.DataFrame(

                    timeline

                )

                if "latency" in timeline_df.columns:
                    st.line_chart(

                        timeline_df[

                            "latency"

                        ]

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

                risk.get(

                    "risk_score",

                    0,

                ),

            )

            cards[1].metric(

                "Daily VaR",

                f"${risk.get('var95', 0):,.2f}",

            )

            cards[2].metric(

                "99% VaR",

                f"${risk.get('var99', 0):,.2f}",

            )

            cards[3].metric(

                "Expected Shortfall",

                f"${risk.get('expected_shortfall', 0):,.2f}",

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

            with stats_left:

                st.subheader(
                    "Portfolio Statistics"
                )

                portfolio_stats = [

                    {
                        "Metric": "Open Positions",
                        "Value": summary.get("open_positions", 0),
                    },
                    {
                        "Metric": "Long Positions",
                        "Value": summary.get("long_count", 0),
                    },
                    {
                        "Metric": "Short Positions",
                        "Value": summary.get("short_count", 0),
                    },
                    {
                        "Metric": "Gross Exposure",
                        "Value": summary.get("gross_exposure", 0),
                    },
                    {
                        "Metric": "Leverage",
                        "Value": summary.get("leverage", 0),
                    },
                    {
                        "Metric": "Margin Used",
                        "Value": summary.get("margin_used", 0),
                    },
                    {
                        "Metric": "Buying Power",
                        "Value": summary.get("buying_power", 0),
                    },
                    {
                        "Metric": "Cash Balance",
                        "Value": summary.get("cash_balance", 0),
                    },

                ]

                st.dataframe(

                    pd.DataFrame(portfolio_stats),

                    use_container_width=True,

                    hide_index=True,

                )

            with stats_right:

                st.subheader(
                    "Risk & Performance"
                )

                risk_stats = [

                    {
                        "Metric": "Risk Score",
                        "Value": risk.get("risk_score", 0),
                    },
                    {
                        "Metric": "VaR (95%)",
                        "Value": risk.get("var95", 0),
                    },
                    {
                        "Metric": "Expected Shortfall",
                        "Value": risk.get("expected_shortfall", 0),
                    },
                    {
                        "Metric": "Max Drawdown",
                        "Value": risk.get("drawdown", 0),
                    },
                    {
                        "Metric": "Sharpe Ratio",
                        "Value": performance.get("sharpe", 0),
                    },
                    {
                        "Metric": "Sortino Ratio",
                        "Value": performance.get("sortino", 0),
                    },
                    {
                        "Metric": "Profit Factor",
                        "Value": performance.get("profit_factor", 0),
                    },
                    {
                        "Metric": "Win Rate",
                        "Value": performance.get("win_rate", 0),
                    },

                ]

                st.dataframe(

                    pd.DataFrame(risk_stats),

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

                st.metric(

                    "Confidence",

                    f"{alpha.get(

                        'confidence',

                        ai.get(

                            'confidence',

                            0,

                        ),

                    ):.1f}%",

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
        else:

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

_INSTANCE=None
def get_forex_trading_desk_dashboard(db=None):
    global _INSTANCE
    if _INSTANCE is None or getattr(_INSTANCE, "db", None) is not db:
        _INSTANCE = ForexTradingDeskDashboard(db=db)
    return _INSTANCE

def render_forex_trading_desk_dashboard(db=None, **kwargs):
    return get_forex_trading_desk_dashboard(db=db).render(**kwargs)
