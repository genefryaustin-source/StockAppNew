import streamlit as st
import pandas as pd
from sqlalchemy import text, bindparam

from modules.portfolio.nav_service import NavService
from modules.portfolio.accounting_service import AccountingService
from modules.portfolio.reporting_service import ReportingService
from modules.portfolio.trading_ui import render_trading_ui
from modules.portfolio.pnl_dashboard import render_pnl_dashboard
from modules.portfolio.portfolio_assignment_service import PortfolioAssignmentService
from modules.portfolio.pdf_reporting_service import PDFReportingService
from models.trading import PortfolioPosition, TradeOrder


def render_portfolio_ui(db_session, user, market_data_service):

    print("🔥 NEW PORTFOLIO UI LOADED")

    role = (user.get("role") or "").lower()
    user_id = user.get("user_id")
    tenant_id = user.get("tenant_id")

    # =====================================================
    # 🔐 PORTFOLIO RESOLUTION
    # =====================================================

    portfolio_id = None
    portfolio_name = None

    # ---------------------------------
    # 👤 CLIENT FLOW
    # ---------------------------------
    if role == "client":

        assignment_service = PortfolioAssignmentService(db_session)

        portfolios = assignment_service.get_user_portfolios(
            tenant_id=tenant_id,
            user_id=user_id
        )

        print("DEBUG USER PORTFOLIOS:", portfolios)

        if not portfolios:
            st.warning("No portfolios assigned")
            return

        portfolio_id = st.session_state.get("selected_portfolio_id")

        if not portfolio_id:
            st.warning("No portfolio selected")
            st.stop()

        portfolio_name = st.session_state.get("portfolio_name")

    # ---------------------------------
    # 🧑‍💼 ADMIN FLOW
    # ---------------------------------
    else:

        portfolios = db_session.execute(text("""
            SELECT id, name
            FROM portfolios
            WHERE tenant_id = :tid
        """), {"tid": tenant_id}).fetchall()

        if not portfolios:
            st.warning("No portfolios found for tenant")
            return

        portfolio_map = {p[0]: p[1] for p in portfolios}

        selected = st.selectbox(
            "Select Portfolio",
            options=list(portfolio_map.keys()),
            format_func=lambda x: portfolio_map[x],
            key="admin_portfolio_selector"
        )

        portfolio_id = selected
        portfolio_name = portfolio_map[selected]

        st.session_state["portfolio_id"] = portfolio_id
        st.session_state["portfolio_name"] = portfolio_name

    # ---------------------------------
    # 🔥 FINAL GUARD
    # ---------------------------------
    if not portfolio_id:
        st.warning("No portfolio selected")
        st.stop()

    # ---------------------------------
    # 🔥 FALLBACK NAME FIX
    # ---------------------------------
    if not portfolio_name:
        try:
            result = db_session.execute(
                text("SELECT name FROM portfolios WHERE id = :pid"),
                {"pid": portfolio_id}
            ).fetchone()

            if result:
                portfolio_name = result[0]
                st.session_state["portfolio_name"] = portfolio_name

        except Exception as e:
            print("⚠️ Portfolio name lookup failed:", e)

    # =====================================================
    # 🧱 HEADER
    # =====================================================
    st.header("Portfolio")

    if portfolio_name:
        st.markdown(f"📁 {portfolio_name}")
    else:
        st.markdown("📁 Portfolio")

    # =====================================================
    # SERVICES
    # =====================================================
    nav_service = NavService(db_session, market_data_service)
    accounting = AccountingService(db_session)
    reporting = ReportingService()

    # =====================================================
    # TABS
    # =====================================================
    if role == "client":
        tab_overview, tab_reports = st.tabs(["📊 Overview", "📄 Reports"])
        tab_trading = tab_performance = None
    else:
        tab_overview, tab_trading, tab_performance, tab_intelligence, tab_reports = st.tabs([
            "📊 Overview",
            "💼 Trading",
            "📈 Performance",
            "🧠 Intelligence",
            "📄 Reports"
        ])

    # =====================================================
    # 📊 OVERVIEW
    # =====================================================
    with tab_overview:

        st.subheader("Overview")
        from modules.utils.data_utils import normalize_timeseries_df
        try:
            cash = float(accounting.get_cash_balance(portfolio_id))
            st.metric("Cash", f"${cash:,.2f}")
        except Exception as e:
            st.error(f"Cash error: {e}")

        try:
            nav_df = normalize_timeseries_df(
                nav_service.get_nav_history(portfolio_id)
            )

            if not nav_df.empty and "NAV" in nav_df.columns:
                nav_df = nav_df.sort_values("Date")
                st.line_chart(nav_df.set_index("Date")["NAV"])
            else:
                st.info("No NAV data")

        except Exception as e:
            st.error(f"NAV error: {e}")

        except Exception as e:
            st.error(f"NAV error: {e}")

        try:
            rows = db_session.execute(text("""
                SELECT symbol, qty, market_value, unrealized_pnl
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """), {"pid": portfolio_id}).fetchall()

            if rows:
                df = pd.DataFrame(rows, columns=["Symbol", "Qty", "Value", "PnL"])
                st.dataframe(df)

        except Exception as e:
            st.error(f"Positions error: {e}")

    # =====================================================
    # 💼 TRADING
    # =====================================================
    if tab_trading:
        with tab_trading:
            render_trading_ui(
                db_session=db_session,
                market_data_service=market_data_service,
                portfolio_id=portfolio_id,
                user_id=user_id
            )

    # =====================================================
    # 📈 PERFORMANCE
    # =====================================================
    if tab_performance:
        with tab_performance:
            render_pnl_dashboard(
                db_session=db_session,
                portfolio_id=portfolio_id
            )

    # =====================================================
    # 📄 REPORTS
    # =====================================================
    with tab_reports:

        st.subheader("📄 Reports")

        try:
            positions = db_session.query(PortfolioPosition).filter(
                PortfolioPosition.portfolio_id == portfolio_id
            ).all()

            positions_df = pd.DataFrame([{
                "symbol": p.symbol,
                "qty": p.qty,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl
            } for p in positions])

        except Exception as e:
            st.error(f"Positions error: {e}")
            positions_df = pd.DataFrame()

        try:
            equity = positions_df["market_value"].sum() if not positions_df.empty else 0
            pnl = positions_df["unrealized_pnl"].sum() if not positions_df.empty else 0

            st.metric("Equity", f"${equity:,.2f}")
            st.metric("PnL", f"${pnl:,.2f}")

        except Exception as e:
            st.error(f"Summary error: {e}")

        # PDF
        if st.button("Generate PDF"):

            try:
                pdf_service = PDFReportingService(
                    db_session,
                    nav_service,
                    accounting,
                    reporting
                )

                import tempfile
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                path = tmp.name
                tmp.close()

                pdf_service.generate_portfolio_report(portfolio_id, path)

                with open(path, "rb") as f:
                    st.download_button(
                        "Download Report",
                        data=f.read(),
                        file_name="portfolio_report.pdf",
                        mime="application/pdf"
                    )

            except Exception as e:
                st.error(f"PDF error: {e}")

    # =====================================================
    # 🧠 PORTFOLIO INTELLIGENCE (SNAPSHOT-BASED)
    # =====================================================
    with tab_intelligence:

        st.subheader("🧠 Portfolio Intelligence")

        try:
            # ---------------------------------
            # LOAD POSITIONS
            # ---------------------------------
            df_pos = pd.read_sql("""
                SELECT symbol, qty, market_value
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """, db_session.bind, params={"pid": portfolio_id})

            if df_pos.empty:
                st.info("No positions to analyze")
                st.stop()

            total_value = df_pos["market_value"].sum()
            df_pos["weight"] = df_pos["market_value"] / total_value

            symbols = df_pos["symbol"].str.upper().tolist()

            # ---------------------------------
            # LOAD ANALYTICS SNAPSHOTS (KEY FIX)
            # ---------------------------------


            query = text("""
                SELECT
                    symbol,
                    composite_score,
                    quality_score,
                    growth_score,
                    value_score,
                    momentum_score,
                    risk_score,
                    sector,
                    signal,
                    sentiment_score
                FROM analytics_snapshots
                WHERE tenant_id = :tid
                AND symbol IN :symbols
            """).bindparams(bindparam("symbols", expanding=True))

            analytics_df = pd.read_sql(
                query,
                db_session.bind,
                params={
                    "tid": tenant_id,
                    "symbols": symbols  # pass list, not tuple
                }
            )

            if analytics_df.empty:
                st.warning("No analytics snapshots available")
                st.stop()

            # normalize
            analytics_df.columns = [str(c).lower() for c in analytics_df.columns]
            df_pos.columns = [str(c).lower() for c in df_pos.columns]

            # ---------------------------------
            # MERGE
            # ---------------------------------
            df = df_pos.merge(analytics_df, on="symbol", how="left")

            # ---------------------------------
            # 🧠 PORTFOLIO SCORE
            # ---------------------------------
            if "composite_score" in df.columns:
                portfolio_score = (df["weight"] * df["composite_score"]).sum()

                st.metric(
                    "Portfolio Score",
                    f"{portfolio_score:.2f}"
                )

            # ---------------------------------
            # 📊 FACTOR EXPOSURE
            # ---------------------------------
            st.markdown("### Factor Exposure")

            factor_cols = [
                "quality_score",
                "growth_score",
                "value_score",
                "momentum_score"
            ]

            factor_data = {
                col.replace("_score", ""): (df["weight"] * df[col]).sum()
                for col in factor_cols
                if col in df.columns
            }

            if factor_data:
                st.bar_chart(pd.Series(factor_data))

            # ---------------------------------
            # 🏢 SECTOR EXPOSURE (NEW)
            # ---------------------------------
            st.markdown("### Sector Exposure")

            if "sector" in df.columns:
                sector_df = (
                    df.groupby("sector")["weight"]
                    .sum()
                    .sort_values(ascending=False)
                )
                st.bar_chart(sector_df)

            # ---------------------------------
            # 💰 TOP POSITIONS
            # ---------------------------------
            st.markdown("### Top Positions")

            top = df.sort_values("weight", ascending=False).head(5)

            st.dataframe(top[["symbol", "weight", "sector", "signal"]])

            # ---------------------------------
            # ⚠️ RISK SIGNALS
            # ---------------------------------
            st.markdown("### Risk Signals")

            concentration = top["weight"].sum()

            if concentration > 0.6:
                st.warning(f"High concentration: Top positions = {concentration:.0%}")

            if df["weight"].max() > 0.25:
                st.warning("Single position exceeds 25%")

            # ---------------------------------
            # 🧠 BENCHMARK INSIGHT (FINAL CLEAN FIX)
            # ---------------------------------
            st.markdown("### Benchmark Insight")

            try:
                bench = nav_service.compute_nav_vs_benchmark(portfolio_id, "SPY")

                if not bench or "comparison_df" not in bench:
                    st.info("Benchmark data unavailable")
                    st.stop()

                # ---------------------------------
                # CORRECT BENCHMARK CALC (FINAL)
                # ---------------------------------
                comp_df = pd.DataFrame(bench["comparison_df"])

                if len(comp_df) > 5:
                    # these are already cumulative returns
                    port_return = comp_df["cum_p"].iloc[-1]
                    bench_return = comp_df["cum_b"].iloc[-1]

                    excess = port_return - bench_return

                    # display
                    st.metric("Portfolio Return", f"{port_return:.2%}")
                    st.metric("Benchmark Return", f"{bench_return:.2%}")
                    st.metric("Excess Return vs SPY", f"{excess:.2%}")


            except Exception as e:
                st.error(f"Benchmark error: {e}")

        except Exception as e:
            st.error(f"Intelligence error: {e}")

        # ---------------------------------
        # ⏱ ATTRIBUTION WINDOW
        # ---------------------------------
        window_label = st.selectbox(
            "Attribution Window",
            options=["1M", "3M", "6M"],
            index=2,
            key="intelligence_window"
        )

        window_map = {
            "1M": "1mo",
            "3M": "3mo",
            "6M": "6mo",
        }

        attrib_period = window_map[window_label]

        # ---------------------------------
        # 💰 NAV-BASED CONTRIBUTION (REAL)
        # ---------------------------------
        st.markdown("### Contribution to Return")

        try:
            # ---------------------------------
            # LOAD POSITIONS
            # ---------------------------------
            df_pos = pd.read_sql("""
                SELECT symbol, qty, market_value
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """, db_session.bind, params={"pid": portfolio_id})

            if df_pos.empty:
                st.info("No positions available")
                st.stop()

            total_value = df_pos["market_value"].sum()
            df_pos["weight"] = df_pos["market_value"] / total_value

            symbols = df_pos["symbol"].tolist()

            # ---------------------------------
            # BUILD PRICE MATRIX
            # ---------------------------------
            price_data = {}
            for sym in symbols:
                hist = nav_service._safe_get_price_history(sym, period="6mo")

                if hist is not None and not hist.empty:
                    price_data[sym] = hist.set_index("Date")["Close"]

            if not price_data:
                st.warning("No price data available for contribution")
                st.stop()

            price_matrix = pd.concat(price_data, axis=1)
            price_matrix = price_matrix.sort_index().ffill().dropna()

            # ---------------------------------
            # RETURNS
            # ---------------------------------
            returns = price_matrix.pct_change().fillna(0)

            # ---------------------------------
            # ALIGN WEIGHTS
            # ---------------------------------
            weights = df_pos.set_index("symbol")["weight"]

            # ensure columns match
            returns = returns[weights.index.intersection(returns.columns)]

            # ---------------------------------
            # CONTRIBUTION CALC
            # ---------------------------------
            contrib = returns.mul(weights, axis=1)

            # cumulative contribution
            total_contrib = contrib.sum()

            contrib_df = pd.DataFrame({
                "symbol": total_contrib.index,
                "contribution": total_contrib.values
            }).sort_values("contribution", ascending=True)

            # ---------------------------------
            # DISPLAY
            # ---------------------------------
            st.dataframe(contrib_df)

            st.bar_chart(
                contrib_df.set_index("symbol")["contribution"]
            )

        except Exception as e:
            st.error(f"Contribution error: {e}")

        # ---------------------------------
        # 📊 BENCHMARK-RELATIVE CONTRIBUTION
        # ---------------------------------
        st.markdown("### Benchmark-Relative Contribution")

        try:
            df_pos = pd.read_sql("""
                SELECT symbol, qty, market_value
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """, db_session.bind, params={"pid": portfolio_id})

            if df_pos.empty:
                st.info("No positions available")
            else:
                total_value = df_pos["market_value"].sum()
                df_pos["weight"] = df_pos["market_value"] / total_value

                symbols = df_pos["symbol"].astype(str).str.upper().tolist()

                price_data = {}
                for sym in symbols:
                    hist = nav_service._safe_get_price_history(sym, period=attrib_period)
                    if hist is not None and not hist.empty:
                        price_data[sym] = hist.set_index("Date")["Close"].rename(sym)

                bench_hist = nav_service._safe_get_price_history("SPY", period=attrib_period)

                if bench_hist is None or bench_hist.empty:
                    st.info("Benchmark data unavailable for attribution")
                elif not price_data:
                    st.info("No position price data available")
                else:
                    price_matrix = pd.concat(price_data.values(), axis=1)
                    price_matrix = price_matrix.sort_index().ffill().dropna(how="all")

                    bench_series = bench_hist.set_index("Date")["Close"].reindex(price_matrix.index).ffill()

                    returns = price_matrix.pct_change().fillna(0)
                    bench_returns = bench_series.pct_change().fillna(0)

                    weights = (
                        df_pos.assign(symbol=df_pos["symbol"].astype(str).str.upper())
                        .set_index("symbol")["weight"]
                    )

                    usable = [c for c in returns.columns if c in weights.index]
                    returns = returns[usable]
                    weights = weights.reindex(usable).fillna(0)

                    excess_returns = returns.sub(bench_returns, axis=0)
                    rel_contrib = excess_returns.mul(weights, axis=1)
                    total_rel_contrib = rel_contrib.sum().sort_values()

                    rel_df = pd.DataFrame({
                        "symbol": total_rel_contrib.index,
                        "relative_contribution": total_rel_contrib.values
                    })

                    st.dataframe(rel_df, use_container_width=True)
                    st.bar_chart(rel_df.set_index("symbol")["relative_contribution"])

        except Exception as e:
            st.error(f"Relative contribution error: {e}")

        # ---------------------------------
        # 🏢 SECTOR ATTRIBUTION
        # ---------------------------------
        st.markdown("### Sector Attribution")

        try:
            df_pos = pd.read_sql("""
                SELECT symbol, market_value
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """, db_session.bind, params={"pid": portfolio_id})

            if df_pos.empty:
                st.info("No positions available for sector attribution")
            else:
                total_value = df_pos["market_value"].sum()
                df_pos["weight"] = df_pos["market_value"] / total_value
                df_pos["symbol"] = df_pos["symbol"].astype(str).str.upper()

                #from sqlalchemy import text, bindparam

                symbols = df_pos["symbol"].tolist()

                query = text("""
                    SELECT
                        symbol,
                        sector
                    FROM analytics_snapshots
                    WHERE tenant_id = :tid
                      AND symbol IN :symbols
                """).bindparams(bindparam("symbols", expanding=True))

                sector_df = pd.read_sql(
                    query,
                    db_session.bind,
                    params={"tid": tenant_id, "symbols": symbols}
                )

                if sector_df.empty:
                    st.info("No sector snapshot data available")
                else:
                    sector_df["symbol"] = sector_df["symbol"].astype(str).str.upper()
                    merged_sector = df_pos.merge(sector_df, on="symbol", how="left")
                    merged_sector["sector"] = merged_sector["sector"].fillna("Unknown")

                    sector_weights = (
                        merged_sector.groupby("sector")["weight"]
                        .sum()
                        .sort_values(ascending=False)
                    )

                    st.bar_chart(sector_weights)

                    sector_table = sector_weights.reset_index()
                    sector_table.columns = ["sector", "weight"]
                    st.dataframe(sector_table, use_container_width=True)

        except Exception as e:
            st.error(f"Sector attribution error: {e}")

        # ---------------------------------
        # 🤖 AI PORTFOLIO EXPLANATION
        # ---------------------------------
        st.markdown("### AI Portfolio Explanation")

        try:
            explanations = []

            # concentration
            if 'top' in locals():
                concentration = top["weight"].sum()
                if concentration >= 0.80:
                    explanations.append(
                        f"The portfolio is highly concentrated, with the top positions representing {concentration:.0%} of total value."
                    )
                elif concentration >= 0.60:
                    explanations.append(
                        f"The portfolio has elevated concentration risk, with the top positions representing {concentration:.0%} of total value."
                    )

            # portfolio score
            if "portfolio_score" in locals():
                if portfolio_score >= 65:
                    explanations.append(
                        f"The portfolio’s weighted composite score is strong at {portfolio_score:.2f}, suggesting above-average underlying analytics quality."
                    )
                elif portfolio_score <= 45:
                    explanations.append(
                        f"The portfolio’s weighted composite score is weak at {portfolio_score:.2f}, suggesting below-average underlying analytics quality."
                    )
                else:
                    explanations.append(
                        f"The portfolio’s weighted composite score is neutral at {portfolio_score:.2f}."
                    )

            # benchmark insight
            if "excess" in locals():
                if excess > 0.02:
                    explanations.append(
                        f"The portfolio is outperforming SPY by {excess:.2%} over the selected window."
                    )
                elif excess < -0.02:
                    explanations.append(
                        f"The portfolio is underperforming SPY by {abs(excess):.2%} over the selected window."
                    )
                else:
                    explanations.append(
                        "The portfolio is performing roughly in line with SPY over the selected window."
                    )

            # sector concentration
            if "sector_weights" in locals() and not sector_weights.empty:
                top_sector = sector_weights.index[0]
                top_sector_weight = sector_weights.iloc[0]
                if top_sector_weight >= 0.40:
                    explanations.append(
                        f"The portfolio is heavily tilted toward {top_sector}, which represents {top_sector_weight:.0%} of portfolio weight."
                    )

            # contribution leaders / laggards
            if "contrib_df" in locals() and not contrib_df.empty:
                worst = contrib_df.iloc[0]
                best = contrib_df.iloc[-1]
                explanations.append(
                    f"The largest positive contributor was {best['symbol']} ({best['contribution']:.2%}), while the largest drag was {worst['symbol']} ({worst['contribution']:.2%})."
                )

            if not explanations:
                st.info("Not enough data to generate an explanation yet.")
            else:
                for item in explanations:
                    st.write(f"- {item}")

        except Exception as e:
            st.error(f"AI explanation error: {e}")

        # ---------------------------------
        # 💵 REAL PNL ATTRIBUTION
        # ---------------------------------
        st.markdown("### Real PnL Attribution")

        try:
            pnl_pack = nav_service.compute_real_pnl_attribution(portfolio_id)

            pnl_summary = pnl_pack["summary"]
            pnl_detail = pnl_pack["detail"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Realized PnL", f"${pnl_summary['realized_pnl']:,.2f}")
            c2.metric("Unrealized PnL", f"${pnl_summary['unrealized_pnl']:,.2f}")
            c3.metric("Total PnL", f"${pnl_summary['total_pnl']:,.2f}")

            if pnl_detail is not None and not pnl_detail.empty:
                st.dataframe(pnl_detail, use_container_width=True)

                st.bar_chart(
                    pnl_detail.set_index("Symbol")["Total PnL"]
                )
            else:
                st.info("No PnL attribution data available.")

        except Exception as e:
            st.error(f"PnL attribution error: {e}")
        # ----------------------------------------
        # Lot Level PNL Attribution
        # ----------------------------------------

        st.markdown("### Lot-Level PnL Attribution")

        lot_method = st.selectbox(
            "Tax Lot Method",
            options=["FIFO", "LIFO"],
            index=0,
            key="tax_lot_method"
        )

        # ---------------------------------
        # 🧠 LOT ENGINE CALL (CLEAN)
        # ---------------------------------
        try:
            lot_pack = nav_service.compute_lot_level_pnl_attribution(
                portfolio_id=portfolio_id,
                method=lot_method
            )
        except Exception as e:
            st.error(f"Lot engine error: {e}")
            return



        if lot_pack is None:
            st.error("Lot engine returned None")
            return

        # ---------------------------------
        # SAFE ACCESS
        # ---------------------------------
        summary = lot_pack.get("summary", {})
        detail = lot_pack.get("detail", pd.DataFrame())
        realized_trades = lot_pack.get("realized_trades", pd.DataFrame())
        open_lots = lot_pack.get("open_lots", pd.DataFrame())
        positions = lot_pack.get("positions", pd.DataFrame())

        # ---------------------------------
        # METRICS
        # ---------------------------------
        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Realized PnL", f"${summary.get('realized_pnl', 0):,.2f}")
        c2.metric("Unrealized PnL", f"${summary.get('unrealized_pnl', 0):,.2f}")
        c3.metric("Total PnL", f"${summary.get('total_pnl', 0):,.2f}")
        c4.metric("Commission", f"${summary.get('total_commission', 0):,.2f}")
        c5.metric("Slippage", f"${summary.get('total_slippage', 0):,.2f}")

        st.caption(f"Method: {summary.get('method', 'N/A')}")

        # ---------------------------------
        # POSITION-LEVEL ATTRIBUTION
        # ---------------------------------
        st.markdown("### Position-Level Attribution")

        if positions is not None and not positions.empty:

            display_pos = positions.copy()

            # formatting
            for col in ["Realized PnL", "Unrealized PnL", "Total PnL"]:
                if col in display_pos.columns:
                    display_pos[col] = display_pos[col].astype(float).round(2)

            if "Contribution %" in display_pos.columns:
                display_pos["Contribution %"] = (display_pos["Contribution %"] * 100).round(2)

            st.dataframe(display_pos, use_container_width=True)

            # bar chart
            if "Symbol" in display_pos.columns and "Total PnL" in display_pos.columns:
                chart_df = display_pos.set_index("Symbol")["Total PnL"]
                st.bar_chart(chart_df)

        else:
            st.info("No position-level attribution available.")

        # ---------------------------------
        # BENCHMARK-RELATIVE ATTRIBUTION
        # ---------------------------------
        st.markdown("### Benchmark-Relative Attribution")

        try:
            bench_attr_pack = nav_service.compute_benchmark_relative_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol="SPY",
                method=lot_method
            )

            bench_attr_summary = bench_attr_pack.get("summary", {})
            bench_attr_detail = bench_attr_pack.get("detail", pd.DataFrame())

            if bench_attr_summary.get("status") != "ok":
                st.info(f"Benchmark-relative attribution unavailable: {bench_attr_summary.get('status')}")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("Benchmark", bench_attr_summary.get("benchmark_symbol", "SPY"))
                c2.metric("Benchmark Return", f"{bench_attr_summary.get('benchmark_return', 0.0) * 100:.2f}%")
                c3.metric("Total Excess Contribution",
                          f"{bench_attr_summary.get('total_excess_contribution', 0.0):,.2f}")

                if bench_attr_detail is not None and not bench_attr_detail.empty:
                    show_cols = [c for c in [
                        "Symbol",
                        "Weight",
                        "Total PnL",
                        "Portfolio Contribution %",
                        "Benchmark-Expected PnL",
                        "Excess Contribution",
                        "Excess Contribution %"
                    ] if c in bench_attr_detail.columns]

                    display_df = bench_attr_detail.copy()

                    for col in ["Weight", "Portfolio Contribution %", "Excess Contribution %"]:
                        if col in display_df.columns:
                            display_df[col] = (pd.to_numeric(display_df[col], errors="coerce").fillna(0.0) * 100).round(
                                2)

                    for col in ["Total PnL", "Benchmark-Expected PnL", "Excess Contribution"]:
                        if col in display_df.columns:
                            display_df[col] = pd.to_numeric(display_df[col], errors="coerce").fillna(0.0).round(2)

                    st.dataframe(display_df[show_cols], use_container_width=True)

                    if "Symbol" in bench_attr_detail.columns and "Excess Contribution" in bench_attr_detail.columns:
                        chart_df = bench_attr_detail.set_index("Symbol")["Excess Contribution"]
                        st.bar_chart(chart_df)
                else:
                    st.info("No benchmark-relative attribution detail available.")

        except Exception as e:
            st.error(f"Benchmark-relative attribution error: {e}")

        # ---------------------------------
        # SECTOR-LEVEL BENCHMARK ATTRIBUTION
        # ---------------------------------
        st.markdown("### Sector-Level Attribution")

        try:
            sector_pack = nav_service.compute_sector_benchmark_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol="SPY",
                method=lot_method
            )

            sector_summary = sector_pack.get("summary", {})
            sector_df = sector_pack.get("detail", pd.DataFrame())

            if sector_summary.get("status") != "ok":
                st.info("Sector attribution unavailable.")
            else:
                c1, c2 = st.columns(2)
                c1.metric("Top Sector", sector_summary.get("top_sector", "N/A"))
                c2.metric("Bottom Sector", sector_summary.get("bottom_sector", "N/A"))

                if sector_df is not None and not sector_df.empty:

                    display_df = sector_df.copy()

                    # formatting
                    for col in ["Weight", "Excess Contribution %"]:
                        if col in display_df.columns:
                            display_df[col] = (display_df[col] * 100).round(2)

                    for col in ["Total PnL", "Benchmark-Expected PnL", "Excess Contribution"]:
                        if col in display_df.columns:
                            display_df[col] = display_df[col].round(2)

                    show_cols = [c for c in [
                        "Sector",
                        "Weight",
                        "Total PnL",
                        "Benchmark-Expected PnL",
                        "Excess Contribution",
                        "Excess Contribution %"
                    ] if c in display_df.columns]

                    st.dataframe(display_df[show_cols], use_container_width=True)

                    if "Sector" in display_df.columns and "Excess Contribution" in display_df.columns:
                        chart_df = display_df.set_index("Sector")["Excess Contribution"]
                        st.bar_chart(chart_df)

                else:
                    st.info("No sector attribution data.")

        except Exception as e:
            st.error(f"Sector attribution error: {e}")

        # ---------------------------------
        # ALLOCATION VS SELECTION
        # ---------------------------------
        st.markdown("### Allocation vs Selection Attribution")

        try:
            alloc_pack = nav_service.compute_allocation_selection_attribution(
                portfolio_id=portfolio_id,
                benchmark_symbol="SPY",
                method=lot_method
            )

            alloc_summary = alloc_pack.get("summary", {})
            alloc_df = alloc_pack.get("detail", pd.DataFrame())

            if alloc_summary.get("status") != "ok":
                st.info("Allocation/Selection attribution unavailable.")
            else:
                c1, c2 = st.columns(2)
                c1.metric("Top Sector", alloc_summary.get("top_sector", "N/A"))
                c2.metric("Bottom Sector", alloc_summary.get("bottom_sector", "N/A"))

                if alloc_df is not None and not alloc_df.empty:

                    display_df = alloc_df.copy()

                    for col in [
                        "Weight",
                        "Benchmark Weight"
                    ]:
                        if col in display_df.columns:
                            display_df[col] = (display_df[col] * 100).round(2)

                    for col in [
                        "Allocation Effect",
                        "Selection Effect",
                        "Interaction Effect",
                        "Total Effect"
                    ]:
                        if col in display_df.columns:
                            display_df[col] = display_df[col].round(4)

                    show_cols = [c for c in [
                        "Sector",
                        "Weight",
                        "Benchmark Weight",
                        "Allocation Effect",
                        "Selection Effect",
                        "Interaction Effect",
                        "Total Effect"
                    ] if c in display_df.columns]

                    st.dataframe(display_df[show_cols], use_container_width=True)

                    if "Sector" in display_df.columns and "Total Effect" in display_df.columns:
                        st.bar_chart(display_df.set_index("Sector")["Total Effect"])

                else:
                    st.info("No allocation/selection data available.")

        except Exception as e:
            st.error(f"Allocation/Selection error: {e}")

        # ---------------------------------
        # AI RANKING / SIGNALS OVERLAY
        # ---------------------------------
        st.markdown("### AI Ranking / Signals Overlay")

        try:
            signal_pack = nav_service.compute_portfolio_signal_overlay(
                portfolio_id=portfolio_id,
                benchmark_symbol="SPY",
                method=lot_method
            )

            signal_summary = signal_pack.get("summary", {})
            leaders = signal_pack.get("leaders", pd.DataFrame())
            laggards = signal_pack.get("laggards", pd.DataFrame())

            c1, c2, c3 = st.columns(3)
            c1.metric("Portfolio Signal", signal_summary.get("signal", "Hold"))
            c2.metric("Signal Score", f"{signal_summary.get('signal_score', 50.0):.2f}")
            c3.metric("Excess vs Benchmark", f"{signal_summary.get('total_excess', 0.0):,.2f}")

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("#### Top Alpha Contributors")
                if leaders is not None and not leaders.empty:
                    show_cols = [c for c in ["Symbol", "Total PnL", "Excess Contribution", "Excess Contribution %"] if
                                 c in leaders.columns]
                    df_lead = leaders.copy()
                    if "Excess Contribution %" in df_lead.columns:
                        df_lead["Excess Contribution %"] = (
                                    pd.to_numeric(df_lead["Excess Contribution %"], errors="coerce").fillna(
                                        0.0) * 100).round(2)
                    st.dataframe(df_lead[show_cols], use_container_width=True)
                else:
                    st.info("No alpha leaders available.")

            with col_b:
                st.markdown("#### Top Draggers")
                if laggards is not None and not laggards.empty:
                    show_cols = [c for c in ["Symbol", "Total PnL", "Excess Contribution", "Excess Contribution %"] if
                                 c in laggards.columns]
                    df_lag = laggards.copy()
                    if "Excess Contribution %" in df_lag.columns:
                        df_lag["Excess Contribution %"] = (
                                    pd.to_numeric(df_lag["Excess Contribution %"], errors="coerce").fillna(
                                        0.0) * 100).round(2)
                    st.dataframe(df_lag[show_cols], use_container_width=True)
                else:
                    st.info("No laggards available.")

        except Exception as e:
            st.error(f"AI signals overlay error: {e}")

        # ---------------------------------
        # LOT-LEVEL ATTRIBUTION (FIXED)
        # ---------------------------------
        st.markdown("### Lot-Level Attribution")

        if detail is not None and not detail.empty:

            # ---------------------------------
            # SELECT ONLY CLEAN / RELEVANT COLUMNS
            # ---------------------------------
            show_cols = [c for c in [
                "Symbol",
                "Lot Status",
                "Qty",
                "Open Qty",
                "Cost Basis",
                "Effective Cost",
                "Sell Price",
                "Market Price",
                "Realized PnL",
                "Unrealized PnL",
                "Total PnL",
                "Total Contribution %"
            ] if c in detail.columns]

            # ---------------------------------
            # FORMAT DATA FOR DISPLAY
            # ---------------------------------
            display_df = detail.copy()

            for col in ["Realized PnL", "Unrealized PnL", "Total PnL"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].astype(float).round(2)

            if "Total Contribution %" in display_df.columns:
                display_df["Total Contribution %"] = (
                        display_df["Total Contribution %"] * 100
                ).round(2)

            # ---------------------------------
            # RENDER TABLE
            # ---------------------------------
            st.dataframe(display_df[show_cols], use_container_width=True)

            # ---------------------------------
            # SYMBOL-LEVEL CONTRIBUTION CHART
            # ---------------------------------
            if "Symbol" in display_df.columns and "Total PnL" in display_df.columns:
                chart_df = display_df.groupby("Symbol")["Total PnL"].sum()
                st.bar_chart(chart_df)

        else:
            st.info("No lot-level attribution data available.")

        # ---------------------------------
        # REALIZED TRADES
        # ---------------------------------
        st.markdown("#### Realized Trades")
        if realized_trades is not None and not realized_trades.empty:
            st.dataframe(realized_trades, use_container_width=True)
        else:
            st.info("No realized trades available.")

        # ---------------------------------
        # OPEN LOTS
        # ---------------------------------
        st.markdown("#### Open Lots")
        if open_lots is not None and not open_lots.empty:
            st.dataframe(open_lots, use_container_width=True)
        else:
            st.info("No open lots available.")



        # ---------------------------------
        # 🧠 TAX OPTIMIZATION ENGINE
        # ---------------------------------
        st.markdown("### Tax Optimization Engine")

        try:
            sells_df = pd.read_sql("""
                SELECT
                    id,
                    symbol,
                    COALESCE(filled_qty, qty, 0) AS sell_qty,
                    COALESCE(avg_fill_price, limit_price, 0) AS sell_price,
                    COALESCE(filled_at, submitted_at, created_at) AS sell_time
                FROM trade_orders
                WHERE portfolio_id = :pid
                  AND LOWER(side) = 'sell'
                  AND LOWER(COALESCE(status, '')) IN ('filled','partially_filled','executed')
                ORDER BY COALESCE(filled_at, submitted_at, created_at) DESC
            """, db_session.bind, params={"pid": portfolio_id})

            if sells_df.empty:
                st.info("No sell trades available for tax optimization.")
            else:
                sells_df["label"] = sells_df.apply(
                    lambda r: f"{r['symbol']} | Qty {r['sell_qty']} | Price {r['sell_price']} | {r['sell_time']}",
                    axis=1
                )

                sell_label = st.selectbox(
                    "Select Sell Trade",
                    sells_df["label"].tolist(),
                    key="tax_opt_sell_trade"
                )

                sell_row = sells_df[sells_df["label"] == sell_label].iloc[0]
                selected_sell_trade_id = str(sell_row["id"])

                tax_objective = st.selectbox(
                    "Tax Objective",
                    ["MIN_GAIN", "MAX_LOSS_HARVEST", "MAX_GAIN"],
                    index=0,
                    key="tax_opt_objective"
                )

                tax_pack = nav_service.compute_tax_optimized_lot_selection(
                    portfolio_id=portfolio_id,
                    sell_trade_id=selected_sell_trade_id,
                    objective=tax_objective,
                    method_fallback="FIFO",
                )

                tax_summary = tax_pack["summary"]
                tax_rec = tax_pack["recommendation"]

                if tax_summary.get("status") != "ok":
                    st.info(f"Optimizer status: {tax_summary.get('status')}")
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Requested Qty", f"{tax_summary['sell_qty_requested']:,.2f}")
                    c2.metric("Selected Qty", f"{tax_summary['sell_qty_selected']:,.2f}")
                    c3.metric("Unfilled Qty", f"{tax_summary['qty_unfilled']:,.2f}")
                    c4.metric("Est. Realized PnL", f"${tax_summary['estimated_realized_pnl']:,.2f}")

                    st.dataframe(tax_rec, use_container_width=True)

                    if st.button("Save Optimized Lot Selection", key="save_tax_optimized_lots"):
                        save_result = nav_service.apply_tax_optimized_selection(
                            portfolio_id=portfolio_id,
                            sell_trade_id=selected_sell_trade_id,
                            recommendation_df=tax_rec
                        )
                        st.success(f"Saved optimized lot selection: {save_result}")
                        tax_pack = nav_service.compute_tax_optimized_lot_selection(...)

                        summary = tax_pack.get("summary", {})

                        if summary.get("status") == "error":
                            st.error(f"Optimizer failed: {summary.get('message')}")

        except Exception as e:
            st.error(f"Tax optimization error: {e}")

        # ---------------------------------
        # 🚫 WASH SALE DETECTION
        # ---------------------------------
        st.markdown("### Wash Sale Detection")

        try:
            wash_pack = nav_service.detect_wash_sales(portfolio_id=portfolio_id)
            wash_summary = wash_pack.get("summary", {})
            wash_detail = wash_pack.get("detail", pd.DataFrame())

            c1, c2 = st.columns(2)
            c1.metric("Potential Wash Sales", wash_summary.get("wash_sale_count", 0))
            c2.metric("Flagged Symbols", wash_summary.get("flagged_symbols", 0))

            if wash_detail is not None and not wash_detail.empty:
                st.dataframe(wash_detail, use_container_width=True)
            else:
                st.info("No potential wash sales detected.")

        except Exception as e:
            st.error(f"Wash sale detection error: {e}")
            st.write("DEBUG open_lots:", open_lots)

        # ---------------------------------
        # 📊 TAX-ADJUSTED PORTFOLIO SCORE
        # ---------------------------------
        st.markdown("### Tax-Adjusted Portfolio Score")

        try:
            # If you already compute portfolio_score earlier in the intelligence tab, pass it in.
            # Otherwise this method will use 50.0 as a neutral fallback.
            tax_score_pack = nav_service.compute_tax_adjusted_portfolio_score(
                portfolio_id=portfolio_id,
                base_portfolio_score=portfolio_score if "portfolio_score" in locals() else None
            )

            tax_score_summary = tax_score_pack.get("summary", {})
            tax_score_detail = tax_score_pack.get("detail", pd.DataFrame())

            st.metric("Tax-Adjusted Score", f"{tax_score_summary.get('tax_adjusted_score', 0):.2f}")

            if tax_score_detail is not None and not tax_score_detail.empty:
                st.dataframe(tax_score_detail, use_container_width=True)

        except Exception as e:
            st.error(f"Tax-adjusted score error: {e}")