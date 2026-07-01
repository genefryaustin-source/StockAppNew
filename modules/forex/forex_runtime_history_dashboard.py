"""
===============================================================================
forex_runtime_history_dashboard.py

Sprint 30
Phase 2
Part 4A

Runtime History Dashboard

Phase 1
    ✓ Dashboard Framework
    ✓ Overview
    ✓ Timeline
    ✓ Runtime Replay

===============================================================================
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_runtime_history_engine import (
    get_forex_runtime_history_engine,
)


# =============================================================================
# Dashboard
# =============================================================================

class ForexRuntimeHistoryDashboard:

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):

        self.db = db

        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.engine = get_forex_runtime_history_engine(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    # =====================================================================
    # Entry
    # =====================================================================

    def render(self):

        st.title("⏳ Forex Runtime History")

        workspace = st.radio(
            "History Workspace",
            [
                "Overview",
                "Timeline",
                "Runtime Replay",
                "Provider Analytics",
                "Currency Strength",
                "Portfolio History",
                "AI Signal History",
                "Risk History",
            ],
            horizontal=True,
        )

        c1, c2 = st.columns([1,5])

        with c1:

            if st.button(
                "🔄 Refresh",
                use_container_width=True,
            ):
                st.rerun()

        if workspace == "Overview":
            self.render_overview()

        elif workspace == "Timeline":
            self.render_timeline()

        elif workspace == "Runtime Replay":
            self.render_runtime_replay()

        elif workspace == "Provider Analytics":
            self.render_provider_analytics()

        elif workspace == "Currency Strength":
            self.render_currency_strength()

        elif workspace == "Portfolio History":
            self.render_portfolio_history()

        elif workspace == "AI Signal History":
            self.render_ai_signal_history()

        elif workspace == "Risk History":
            self.render_risk_history()

    # =====================================================================
    # Overview
    # =====================================================================

    def render_overview(self):

        packet = self.engine.build_dashboard_packet()

        summary = packet["timeline_summary"]

        col1,col2,col3,col4 = st.columns(4)

        col1.metric(
            "Snapshots",
            summary["snapshot_count"],
        )

        col2.metric(
            "Tenant",
            self.tenant_id or "-",
        )

        col3.metric(
            "User",
            self.user_id or "-",
        )

        col4.metric(
            "Portfolio",
            self.portfolio_id or "-",
        )

        st.divider()

        st.subheader("Latest Runtime")

        latest = packet["latest_runtime"]

        if latest is None:

            st.info(
                "No runtime history available."
            )

            return

        st.json(latest)

    # =====================================================================
    # Timeline
    # =====================================================================

    def render_timeline(self):

        result = self.engine.load_user_timeline()

        timeline = result["timeline"]

        snapshots = timeline["snapshots"]

        if not snapshots:

            st.info(
                "No runtime history found."
            )

            return

        rows = []

        for snap in snapshots:

            rows.append({

                "Runtime":

                    snap["runtime_id"],

                "Build":

                    snap["build_number"],

                "Started":

                    snap["build_started_at"],

                "Completed":

                    snap["build_completed_at"],

                "Providers":

                    len(
                        snap["provider_history"]
                    ),

                "Signals":

                    len(
                        snap["ai_history"]
                    ),

                "Created":

                    snap["created_at"],

            })

        df = pd.DataFrame(rows)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================================
    # Replay
    # =====================================================================

    def render_runtime_replay(self):

        result = self.engine.load_user_timeline()

        timeline = result["timeline"]

        snapshots = timeline["snapshots"]

        if not snapshots:

            st.info(
                "No runtime history available."
            )

            return

        runtime_ids = [

            snap["runtime_id"]

            for snap in snapshots

        ]

        runtime_id = st.selectbox(

            "Runtime",

            runtime_ids,

        )

        replay = self.engine.replay_runtime(

            runtime_id,

        )

        st.subheader("Replay")

        st.json(replay["summary"])

        st.divider()

        st.subheader("Timeline")

        st.json(replay["timeline"])

    def render_provider_analytics(self):

        st.subheader("Provider Analytics")

        result = self.engine.provider_trends()

        providers = result.get("providers", [])

        if not providers:
            st.info("No provider history available.")
            return

        df = pd.DataFrame(providers)

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        st.subheader("Provider Health")

        cols = st.columns(4)

        cols[0].metric(
            "Providers",
            len(df),
        )

        cols[1].metric(
            "Avg Success %",
            f"{df.success_rate.mean() * 100:.1f}",
        )

        cols[2].metric(
            "Avg Latency",
            f"{df.avg_latency_ms.mean():.1f} ms",
        )

        cols[3].metric(
            "Quotes",
            int(df.quote_count.sum()),
        )

        st.divider()

        st.subheader("Provider Rankings")

        ranking = df.sort_values(
            [
                "success_rate",
                "avg_latency_ms",
            ],
            ascending=[
                False,
                True,
            ],
        )

        st.dataframe(
            ranking,
            hide_index=True,
            use_container_width=True,
        )

    def render_currency_strength(self):

        st.subheader(
            "Currency Strength History"
        )

        result = self.engine.currency_strength_trends()

        currencies = result.get(
            "currencies",
            [],
        )

        if not currencies:
            st.info(
                "No currency history available."
            )

            return

        df = pd.DataFrame(currencies)

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        st.subheader(
            "Strongest Currencies"
        )

        strongest = df.sort_values(
            "latest_strength",
            ascending=False,
        )

        st.dataframe(
            strongest[
                [
                    "currency",
                    "latest_strength",
                    "strength_change",
                    "latest_rank",
                    "latest_confidence",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        st.subheader(
            "Largest Movers"
        )

        movers = df.sort_values(
            "strength_change_pct",
            ascending=False,
        )

        st.dataframe(
            movers[
                [
                    "currency",
                    "strength_change_pct",
                    "latest_strength",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

    # =============================================================================
    # Portfolio History
    # Sprint 30 Phase 4C-1
    # =============================================================================

    def render_portfolio_history(self):

        st.subheader("Portfolio History")

        result = self.engine.portfolio_trends()

        if result["status"] == "no_data":
            st.info(
                "No portfolio history available."
            )

            return

        summary = result.get(
            "summary",
            {},
        )

        series = result.get(
            "series",
            [],
        )

        if not series:
            st.info(
                "No historical portfolio snapshots."
            )

            return

        # -----------------------------------------------------------------
        # Summary Metrics
        # -----------------------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Snapshots",
            summary.get(
                "observations",
                0,
            ),
        )

        c2.metric(
            "Current Equity",
            f"${summary.get('latest_equity', 0):,.2f}",
        )

        c3.metric(
            "Equity Change",
            f"${summary.get('equity_change', 0):,.2f}",
        )

        c4.metric(
            "Return %",
            f"{summary.get('equity_change_pct', 0):.2f}%",
        )

        st.divider()

        # -----------------------------------------------------------------
        # History Table
        # -----------------------------------------------------------------

        df = pd.DataFrame(series)

        st.subheader(
            "Historical Snapshots"
        )

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Equity History
        # -----------------------------------------------------------------

        st.subheader(
            "Equity History"
        )

        chart = (
            df[
                [
                    "created_at",
                    "equity",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "equity": "Equity",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Cash History
        # -----------------------------------------------------------------

        st.subheader(
            "Cash History"
        )

        chart = (
            df[
                [
                    "created_at",
                    "cash",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "cash": "Cash",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Unrealized PnL
        # -----------------------------------------------------------------

        st.subheader(
            "Unrealized PnL"
        )

        chart = (
            df[
                [
                    "created_at",
                    "unrealized_pnl",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "unrealized_pnl": "PnL",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Exposure
        # -----------------------------------------------------------------

        st.subheader(
            "Exposure"
        )

        chart = (
            df[
                [
                    "created_at",
                    "exposure",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "exposure": "Exposure",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Positions
        # -----------------------------------------------------------------

        st.subheader(
            "Position Count"
        )

        chart = (
            df[
                [
                    "created_at",
                    "positions",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "positions": "Positions",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Latest Snapshot
        # -----------------------------------------------------------------

        latest = df.iloc[-1]

        st.divider()

        st.subheader(
            "Latest Portfolio"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Cash",
            f"${latest.cash:,.2f}",
        )

        c2.metric(
            "Exposure",
            f"{latest.exposure:,.2f}",
        )

        c3.metric(
            "Positions",
            int(latest.positions),
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Unrealized PnL",
            f"${latest.unrealized_pnl:,.2f}",
        )

        c2.metric(
            "Realized PnL",
            f"${latest.realized_pnl:,.2f}",
        )

        c3.metric(
            "Equity",
            f"${latest.equity:,.2f}",
        )

        # -----------------------------------------------------------------
        # Export
        # -----------------------------------------------------------------

        st.divider()

        st.download_button(
            "Download Portfolio History CSV",
            df.to_csv(index=False),
            file_name="forex_portfolio_history.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # =============================================================================
    # AI Signal History
    # Sprint 30 Phase 4C-2
    # =============================================================================

    def render_ai_signal_history(self):

        st.subheader("AI Signal History")

        result = self.engine.ai_signal_trends()

        if result["status"] == "no_data":
            st.info(
                "No AI signal history available."
            )

            return

        summary = result.get(
            "summary",
            {},
        )

        signals = result.get(
            "signals",
            [],
        )

        df = pd.DataFrame(signals)

        # -----------------------------------------------------------------
        # Summary Metrics
        # -----------------------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Signals",
            summary.get(
                "signal_count",
                0,
            ),
        )

        c2.metric(
            "Average Confidence",
            f"{summary.get('avg_confidence', 0):.2f}",
        )

        c3.metric(
            "Average Score",
            f"{summary.get('avg_score', 0):.2f}",
        )

        c4.metric(
            "Recommendation Types",
            len(
                summary.get(
                    "recommendation_counts",
                    {},
                )
            ),
        )

        st.divider()

        # -----------------------------------------------------------------
        # Signal History
        # -----------------------------------------------------------------

        st.subheader(
            "Historical Signals"
        )

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Confidence Trend
        # -----------------------------------------------------------------

        st.subheader(
            "Confidence Trend"
        )

        chart = (
            df[
                [
                    "created_at",
                    "confidence",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "confidence": "Confidence",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Score Trend
        # -----------------------------------------------------------------

        st.subheader(
            "Score Trend"
        )

        chart = (
            df[
                [
                    "created_at",
                    "score",
                ]
            ]
            .rename(
                columns={
                    "created_at": "Snapshot",
                    "score": "Score",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        # -----------------------------------------------------------------
        # Recommendation Distribution
        # -----------------------------------------------------------------

        st.subheader(
            "Recommendation Distribution"
        )

        recommendation_counts = (
            summary.get(
                "recommendation_counts",
                {},
            )
        )

        dist = pd.DataFrame(
            {
                "Recommendation":
                    list(
                        recommendation_counts.keys()
                    ),
                "Count":
                    list(
                        recommendation_counts.values()
                    ),
            }
        )

        st.bar_chart(
            dist.set_index(
                "Recommendation"
            )
        )

        st.divider()

        # -----------------------------------------------------------------
        # Recommendation Statistics
        # -----------------------------------------------------------------

        st.subheader(
            "Recommendation Statistics"
        )

        stats_rows = []

        grouped = (
            df.groupby(
                "recommendation"
            )
        )

        for recommendation, grp in grouped:
            stats_rows.append(
                {

                    "Recommendation":
                        recommendation,

                    "Signals":
                        len(grp),

                    "Average Confidence":
                        grp["confidence"].mean(),

                    "Average Score":
                        grp["score"].mean(),

                    "Highest Score":
                        grp["score"].max(),

                    "Lowest Score":
                        grp["score"].min(),

                }
            )

        stats_df = pd.DataFrame(
            stats_rows
        )

        st.dataframe(
            stats_df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Latest AI Decision
        # -----------------------------------------------------------------

        latest = df.iloc[-1]

        st.subheader(
            "Latest AI Recommendation"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Recommendation",
            latest.recommendation,
        )

        c2.metric(
            "Confidence",
            f"{latest.confidence:.2f}",
        )

        c3.metric(
            "Score",
            f"{latest.score:.2f}",
        )

        st.text_area(
            "AI Explanation",
            latest.explanation,
            height=150,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Full Replay
        # -----------------------------------------------------------------

        st.subheader(
            "Historical AI Replay"
        )

        replay_index = st.selectbox(
            "Replay Signal",
            df.index,
            format_func=lambda i:
            f"{df.loc[i, 'created_at']} - "
            f"{df.loc[i, 'recommendation']}",
        )

        replay = df.loc[
            replay_index
        ]

        st.json(
            replay.to_dict()
        )

        st.divider()

        # -----------------------------------------------------------------
        # Export
        # -----------------------------------------------------------------

        st.download_button(

            "Download AI History CSV",

            df.to_csv(index=False),

            file_name="forex_ai_signal_history.csv",

            mime="text/csv",

            use_container_width=True,

        )

    # =============================================================================
    # Risk History
    # Sprint 30 Phase 4C-3-1
    #
    # Foundation
    # =============================================================================

    def render_risk_history(self):

        st.subheader("Risk History")

        #
        # Pull history from engine
        #
        timeline = self.engine._active_timeline()

        rows = []

        for snapshot in timeline.snapshots:

            risk = snapshot.risk_history

            if risk is None:
                continue

            rows.append({

                "Runtime":
                    snapshot.runtime_id,

                "Created":
                    snapshot.created_at.isoformat(),

                "Risk Score":
                    risk.risk_score,

                "Exposure":
                    risk.exposure,

                "Leverage":
                    risk.leverage,

                "Margin Used":
                    risk.margin_used,

                "Warnings":
                    len(risk.warnings),

            })

        if not rows:
            st.info(
                "No historical risk information available."
            )

            return

        df = pd.DataFrame(rows)

        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------

        summary1, summary2, summary3, summary4 = st.columns(4)

        summary1.metric(
            "Snapshots",
            len(df),
        )

        summary2.metric(
            "Latest Risk",
            f"{df.iloc[-1]['Risk Score']:.2f}",
        )

        summary3.metric(
            "Highest Risk",
            f"{df['Risk Score'].max():.2f}",
        )

        summary4.metric(
            "Average Risk",
            f"{df['Risk Score'].mean():.2f}",
        )

        st.divider()

        # -----------------------------------------------------------------
        # Historical Table
        # -----------------------------------------------------------------

        st.subheader(
            "Historical Risk Snapshots"
        )

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Risk Score Trend
        # -----------------------------------------------------------------

        st.subheader(
            "Risk Score Trend"
        )

        chart = (
            df[
                [
                    "Created",
                    "Risk Score",
                ]
            ]
            .rename(
                columns={
                    "Created": "Snapshot",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        st.divider()

        # -----------------------------------------------------------------
        # Exposure Trend
        # -----------------------------------------------------------------

        st.subheader(
            "Exposure Trend"
        )

        chart = (
            df[
                [
                    "Created",
                    "Exposure",
                ]
            ]
            .rename(
                columns={
                    "Created": "Snapshot",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        st.divider()

        # -----------------------------------------------------------------
        # Leverage Trend
        # -----------------------------------------------------------------

        st.subheader(
            "Leverage Trend"
        )

        chart = (
            df[
                [
                    "Created",
                    "Leverage",
                ]
            ]
            .rename(
                columns={
                    "Created": "Snapshot",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        st.divider()

        # -----------------------------------------------------------------
        # Margin Utilization
        # -----------------------------------------------------------------

        st.subheader(
            "Margin Utilization"
        )

        chart = (
            df[
                [
                    "Created",
                    "Margin Used",
                ]
            ]
            .rename(
                columns={
                    "Created": "Snapshot",
                }
            )
            .set_index(
                "Snapshot"
            )
        )

        st.line_chart(
            chart
        )

        st.divider()

        # -----------------------------------------------------------------
        # Current Risk Snapshot
        # -----------------------------------------------------------------

        latest = df.iloc[-1]

        st.subheader(
            "Latest Risk Snapshot"
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Risk Score",
            f"{latest['Risk Score']:.2f}",
        )

        c2.metric(
            "Exposure",
            f"{latest['Exposure']:.2f}",
        )

        c3.metric(
            "Leverage",
            f"{latest['Leverage']:.2f}",
        )

        c4.metric(
            "Margin Used",
            f"{latest['Margin Used']:.2f}",
        )

        st.divider()

        # -----------------------------------------------------------------
        # Risk Statistics
        # -----------------------------------------------------------------

        st.subheader(
            "Risk Statistics"
        )

        stats = pd.DataFrame(
            [
                {
                    "Statistic": "Minimum Risk",
                    "Value": df["Risk Score"].min(),
                },
                {
                    "Statistic": "Maximum Risk",
                    "Value": df["Risk Score"].max(),
                },
                {
                    "Statistic": "Average Risk",
                    "Value": df["Risk Score"].mean(),
                },
                {
                    "Statistic": "Average Exposure",
                    "Value": df["Exposure"].mean(),
                },
                {
                    "Statistic": "Average Leverage",
                    "Value": df["Leverage"].mean(),
                },
                {
                    "Statistic": "Average Margin",
                    "Value": df["Margin Used"].mean(),
                },
            ]
        )

        st.dataframe(
            stats,
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # -----------------------------------------------------------------
        # Export
        # -----------------------------------------------------------------

        st.download_button(
            "Download Risk History CSV",
            df.to_csv(index=False),
            file_name="forex_risk_history.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # =============================================================================
    # Risk Analytics
    # Sprint 30 Phase 4C-3-2
    #
    # Institutional Risk Analytics
    # =============================================================================

    def render_risk_analytics(self):

        st.subheader("Institutional Risk Analytics")

        timeline = self.engine._active_timeline()

        history = []

        for snapshot in timeline.snapshots:

            risk = snapshot.risk_history

            if risk is None:
                continue

            history.append({

                "Runtime":
                    snapshot.runtime_id,

                "Created":
                    snapshot.created_at.isoformat(),

                "Risk Score":
                    risk.risk_score,

                "Exposure":
                    risk.exposure,

                "Leverage":
                    risk.leverage,

                "Margin Used":
                    risk.margin_used,

                "Warnings":
                    risk.warnings,

            })

        if not history:
            st.info(
                "No historical risk analytics available."
            )

            return

        df = pd.DataFrame(history)

        # ------------------------------------------------------------------
        # Risk Classification
        # ------------------------------------------------------------------

        def classify(score):

            if score < 25:
                return "LOW"

            if score < 50:
                return "MODERATE"

            if score < 75:
                return "HIGH"

            return "CRITICAL"

        df["Severity"] = df["Risk Score"].apply(classify)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Critical",
            len(df[df.Severity == "CRITICAL"])
        )

        c2.metric(
            "High",
            len(df[df.Severity == "HIGH"])
        )

        c3.metric(
            "Moderate",
            len(df[df.Severity == "MODERATE"])
        )

        c4.metric(
            "Low",
            len(df[df.Severity == "LOW"])
        )

        st.divider()

        # ------------------------------------------------------------------
        # Severity Distribution
        # ------------------------------------------------------------------

        st.subheader(
            "Risk Severity Distribution"
        )

        severity = (
            df
            .groupby("Severity")
            .size()
            .reset_index(name="Count")
        )

        st.bar_chart(
            severity.set_index("Severity")
        )

        st.divider()

        # ------------------------------------------------------------------
        # Warning Timeline
        # ------------------------------------------------------------------

        st.subheader(
            "Warning Timeline"
        )

        warning_rows = []

        for _, row in df.iterrows():

            warnings = row["Warnings"]

            if not warnings:
                continue

            for warning in warnings:
                warning_rows.append({

                    "Created":
                        row["Created"],

                    "Runtime":
                        row["Runtime"],

                    "Severity":
                        row["Severity"],

                    "Warning":
                        warning,

                })

        if warning_rows:

            warnings_df = pd.DataFrame(
                warning_rows
            )

            st.dataframe(

                warnings_df,

                hide_index=True,

                use_container_width=True,

            )

        else:

            st.success(
                "No historical warnings."
            )

        st.divider()

        # ------------------------------------------------------------------
        # Exposure Analysis
        # ------------------------------------------------------------------

        st.subheader(
            "Exposure Analysis"
        )

        exposure = df[
            [
                "Created",
                "Exposure",
            ]
        ].rename(
            columns={
                "Created": "Snapshot",
            }
        ).set_index(
            "Snapshot"
        )

        st.area_chart(
            exposure
        )

        st.divider()

        # ------------------------------------------------------------------
        # Leverage Distribution
        # ------------------------------------------------------------------

        st.subheader(
            "Leverage Distribution"
        )

        leverage_stats = pd.DataFrame({

            "Metric": [

                "Minimum",

                "Average",

                "Maximum",

            ],

            "Leverage": [

                df["Leverage"].min(),

                df["Leverage"].mean(),

                df["Leverage"].max(),

            ]

        })

        st.dataframe(

            leverage_stats,

            hide_index=True,

            use_container_width=True,

        )

        st.divider()

        # ------------------------------------------------------------------
        # Margin Utilization
        # ------------------------------------------------------------------

        st.subheader(
            "Margin Utilization"
        )

        margin = df[
            [
                "Created",
                "Margin Used",
            ]
        ].rename(
            columns={
                "Created": "Snapshot",
            }
        ).set_index(
            "Snapshot"
        )

        st.line_chart(
            margin
        )

        st.divider()

        # ------------------------------------------------------------------
        # Drawdown Estimate
        # ------------------------------------------------------------------

        st.subheader(
            "Historical Drawdown"
        )

        df["Peak Risk"] = df[
            "Risk Score"
        ].cummax()

        df["Drawdown"] = (
                df["Peak Risk"] -
                df["Risk Score"]
        )

        drawdown = df[
            [
                "Created",
                "Drawdown",
            ]
        ].rename(
            columns={
                "Created": "Snapshot",
            }
        ).set_index(
            "Snapshot"
        )

        st.line_chart(
            drawdown
        )

        st.divider()

        # ------------------------------------------------------------------
        # Historical Replay
        # ------------------------------------------------------------------

        st.subheader(
            "Risk Replay"
        )

        replay_index = st.selectbox(

            "Risk Snapshot",

            df.index,

            format_func=lambda i:
            f"{df.loc[i, 'Created']} | "
            f"{df.loc[i, 'Severity']}"

        )

        st.json(

            df.loc[
                replay_index
            ].to_dict()

        )

        st.divider()

        # ------------------------------------------------------------------
        # Export
        # ------------------------------------------------------------------

        export = df.copy()

        export["Warnings"] = export[
            "Warnings"
        ].apply(
            lambda x:
            "; ".join(x)
            if isinstance(x, list)
            else ""
        )

        st.download_button(

            "Download Institutional Risk Analytics",

            export.to_csv(index=False),

            file_name="forex_risk_analytics.csv",

            mime="text/csv",

            use_container_width=True,

        )


# =============================================================================
# Singleton
# =============================================================================

_DASHBOARD = None


def get_forex_runtime_history_dashboard(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):

    global _DASHBOARD

    if (

        _DASHBOARD is None

        or getattr(
            _DASHBOARD,
            "db",
            None,
        ) is not db

        or getattr(
            _DASHBOARD,
            "tenant_id",
            None,
        ) != tenant_id

        or getattr(
            _DASHBOARD,
            "user_id",
            None,
        ) != user_id

        or getattr(
            _DASHBOARD,
            "portfolio_id",
            None,
        ) != portfolio_id

    ):

        _DASHBOARD = ForexRuntimeHistoryDashboard(

            db=db,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

    return _DASHBOARD


# =============================================================================
# Public API
# =============================================================================

def render_forex_runtime_history_dashboard(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):

    return get_forex_runtime_history_dashboard(

        db=db,

        tenant_id=tenant_id,

        user_id=user_id,

        portfolio_id=portfolio_id,

    ).render()