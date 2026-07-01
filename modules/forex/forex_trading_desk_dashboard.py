
"""
modules/forex/forex_trading_desk_dashboard.py
"""

try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px
except Exception:
    st=None
    pd=None

from modules.forex.forex_trading_desk import get_forex_trading_desk
from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

class ForexTradingDeskDashboard:

    def __init__(self, db=None):
        self.desk=get_forex_trading_desk(db=db)

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

    def render(self, **kwargs):

        data = self.desk.dashboard(**kwargs)

        live = self._build_live_portfolio_packet(**kwargs)

        data["portfolio"] = live.get("portfolio", {})
        data["risk"] = live.get("risk", data.get("risk", {}))
        data["performance"] = live.get("performance", data.get("performance", {}))
        data["open_orders"] = live.get("open_orders", data.get("open_orders", []))
        data["filled_orders"] = live.get("filled_orders", data.get("filled_orders", []))
        data["execution_history"] = live.get("execution_history", [])
        data["cash_ledger"] = live.get("cash_ledger", [])
        data["system"] = live.get("system", {})

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

                orders = data.get(

                    "open_orders",

                    [],

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

                    "activity",

                    [],

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

            a.button(

                "New Order",

                use_container_width=True,

            )

            b.button(

                "Close Position",

                use_container_width=True,

            )

            c.button(

                "Reverse",

                use_container_width=True,

            )

            d.button(

                "Flatten",

                use_container_width=True,

            )

            e.button(
                "AI Trade",
                key="performance_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="portfolio_refresh_btn",
                use_container_width=True,
            )
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

            open_orders = data.get("open_orders", [])

            filled_orders = data.get("filled_orders", [])

            pending_orders = data.get("pending_orders", [])

            cancelled_orders = data.get("cancelled_orders", [])

            execution = data.get("execution", {})

            st.subheader("Institutional Order Management")

            # ==========================================================
            # Executive Order Metrics
            # ==========================================================

            row = st.columns(8)

            row[0].metric(

                "Open",

                len(open_orders),

            )

            row[1].metric(

                "Pending",

                len(pending_orders),

            )

            row[2].metric(

                "Filled",

                len(filled_orders),

            )

            row[3].metric(

                "Cancelled",

                len(cancelled_orders),

            )

            row[4].metric(

                "Fill Rate",

                f"{execution.get('fill_rate', 0):.1f}%",

            )

            row[5].metric(

                "Avg Fill",

                f"{execution.get('avg_fill_time', 0):.2f}s",

            )

            row[6].metric(

                "Avg Slippage",

                f"{execution.get('avg_slippage', 0):.4f}",

            )

            row[7].metric(

                "Latency",

                f"{execution.get('latency_ms', 0):,.0f} ms",

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

                feed = execution.get(

                    "execution_feed",

                    [],

                )

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

            executions = execution.get(

                "recent_executions",

                [],

            )

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

            # ==========================================================
            # Execution Timeline
            # ==========================================================

            st.divider()

            st.subheader(

                "Execution Timeline"

            )

            timeline = execution.get(

                "timeline",

                [],

            )

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

            st.success(

                "Institutional Order Analytics Loaded"

            )
        elif ws == "Risk":

            risk = data.get("risk", {})

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

            # ==========================================================
            # Position Risk
            # ==========================================================

            st.subheader(

                "Largest Position Risks"

            )

            positions = risk.get(

                "position_risk",

                [],

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

                equity = performance.get(

                    "equity_curve",

                    [],

                )

                if equity:

                    df = pd.DataFrame(equity)

                    if {

                        "date",

                        "equity",

                    }.issubset(df.columns):

                        df = df.set_index(

                            "date"

                        )

                        st.line_chart(

                            df["equity"]

                        )

                    else:

                        st.line_chart(df)

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

                returns = performance.get(

                    "daily_returns",

                    [],

                )

                if returns:

                    st.bar_chart(

                        returns

                    )

                else:

                    st.info(

                        "No daily returns."

                    )

            with right:

                st.subheader(

                    "Monthly Returns"

                )

                monthly = performance.get(

                    "monthly_returns",

                    [],

                )

                if monthly:

                    st.line_chart(

                        monthly

                    )

                else:

                    st.info(

                        "No monthly returns."

                    )

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

            allocation = portfolio.get(
                "allocation",
                [],
            )

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

            timeline = performance.get(

                "timeline",

                [],

            )

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

                use_container_width=True,

            )

            b.button(

                "Trade Attribution",

                use_container_width=True,

            )

            c.button(

                "Export CSV",

                use_container_width=True,

            )

            d.button(

                "Export PDF",

                use_container_width=True,

            )

            e.button(
                "Refresh",
                key="analytics_export_btn",
                use_container_width=True,
            )

            f.button(
                "Analytics",
                key="analytics_action_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional Performance Dashboard Loaded"

            )
        elif ws == "Strategy":

            strategy = data.get("strategy_lab", {})

            ai = data.get("executive_ai", {})

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

                "AI Score",

                ai.get(

                    "score",

                    0,

                ),

            )

            cards[7].metric(

                "Market Regime",

                ai.get(

                    "regime",

                    "UNKNOWN",

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

                summary = ai.get(

                    "summary",

                    "No AI summary available."

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

                    ai.get(

                        "bias",

                        "Neutral",

                    ),

                )

                st.metric(

                    "Confidence",

                    f"{ai.get('confidence', 0):.1f}%",

                )

                st.metric(

                    "Volatility",

                    ai.get(

                        "volatility",

                        "Normal",

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

                    recommendations

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

                        strategies

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

                        opportunities

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

            signal_counts = {

                "BUY":

                    strategy.get(

                        "buy_signals",

                        0,

                    ),

                "SELL":

                    strategy.get(

                        "sell_signals",

                        0,

                    ),

                "HOLD":

                    strategy.get(

                        "hold_signals",

                        0,

                    ),

            }

            signal_df = pd.DataFrame(

                {

                    "Signal":

                        list(

                            signal_counts.keys()

                        ),

                    "Count":

                        list(

                            signal_counts.values()

                        ),

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

                use_container_width=True,

            )

            b.button(

                "Generate Signals",

                use_container_width=True,

            )

            c.button(

                "Scan Market",

                use_container_width=True,

            )

            d.button(

                "Optimize",

                use_container_width=True,

            )

            e.button(
                "Export",
                key="strategy_export_btn",
                use_container_width=True,
            )

            f.button(
                "Refresh",
                key="strategy_history_refresh_btn",
                use_container_width=True,
            )

            st.success(

                "Institutional AI Strategy Center Loaded"

            )
        elif ws == "Journal":

            journal = data.get("journal", {})

            trades = journal.get(

                "trades",

                [],

            )

            notes = journal.get(

                "notes",

                [],

            )

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

                len(notes),

            )

            cards[1].metric(

                "Trades",

                len(trades),

            )

            cards[2].metric(

                "Winning Trades",

                journal.get(

                    "winning_trades",

                    0,

                ),

            )

            cards[3].metric(

                "Win Rate",

                f"{journal.get('win_rate', 0):.1f}%",

            )

            cards[4].metric(

                "Average Hold",

                journal.get(

                    "average_hold",

                    "0h",

                ),

            )

            cards[5].metric(

                "Average Gain",

                f"${journal.get('average_gain', 0):,.2f}",

            )

            cards[6].metric(

                "Average Loss",

                f"${journal.get('average_loss', 0):,.2f}",

            )

            cards[7].metric(

                "Expectancy",

                f"{journal.get('expectancy', 0):.2f}",

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

                "emotion_summary",

                {},

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

                "strategy_review",

                [],

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

                "improvements",

                [],

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

            # ==========================================================
            # Quick Actions
            # ==========================================================

            a, b, c, d, e, f = st.columns(6)

            a.button(

                "New Journal Entry",

                use_container_width=True,

            )

            b.button(

                "Review Trades",

                use_container_width=True,

            )

            c.button(

                "Export Journal",

                use_container_width=True,

            )

            d.button(

                "Performance Review",

                use_container_width=True,

            )
            e.button(
                "Psychology Report",
                key="improvement_export_btn",
                use_container_width=True,
            )



            f.button(
                "Refresh",
                key="imporovement_refresh_btn",
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
    if _INSTANCE is None:
        _INSTANCE=ForexTradingDeskDashboard(db=db)
    return _INSTANCE

def render_forex_trading_desk_dashboard(db=None, **kwargs):
    return get_forex_trading_desk_dashboard(db=db).render(**kwargs)
