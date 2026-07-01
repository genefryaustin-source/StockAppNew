# =============================================================================
# File: modules/forex/risk/forex_var_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-2
#
# Build 1.1
#
# Institutional Value-at-Risk Dashboard
# =============================================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from typing import Optional
from typing import Any

from modules.forex.risk.forex_var_engine import (
    get_forex_var_engine,
)


# =============================================================================
# Dashboard
# =============================================================================

class ForexVaRDashboard:

    def __init__(

        self,

        db: Optional[Any] = None,

        tenant_id=None,

        user_id=None,

        portfolio_id=None,

    ):

        self.db = db

        self.tenant_id = tenant_id

        self.user_id = user_id

        self.portfolio_id = portfolio_id

        self.engine = get_forex_var_engine(

            db=db,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

    # -----------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------

    def render(self):

        st.title("Institutional Value-at-Risk")

        workspace = st.radio(

            "VaR Workspace",

            [

                "Overview",

                "Parametric VaR",

                "Historical VaR",

                "Monte Carlo",

                "Stress Testing",

                "Portfolio Risk",

                "History",

                "Executive Report",

            ],

            horizontal=True,

        )

        st.divider()

        if workspace == "Overview":

            self.render_overview()

        elif workspace == "Parametric VaR":

            self.render_parametric()

        elif workspace == "Historical VaR":

            self.render_historical()

        elif workspace == "Monte Carlo":

            self.render_monte_carlo()

        elif workspace == "Stress Testing":

            self.render_stress()

        elif workspace == "Portfolio Risk":

            self.render_portfolio()

        elif workspace == "History":

            self.render_history()

        elif workspace == "Executive Report":

            self.render_executive()

    # -----------------------------------------------------------------
    # Overview
    # -----------------------------------------------------------------

    def render_overview(self):

        packet = self.engine.dashboard_packet()

        parametric = packet["parametric"]

        historical = packet["historical"]

        expected = packet["expected_shortfall"]

        cols = st.columns(4)

        cols[0].metric(

            "Daily VaR",

            f"${parametric['daily_var']:,.2f}",

        )

        cols[1].metric(

            "Historical VaR",

            f"${historical['daily_var']:,.2f}",

        )

        cols[2].metric(

            "Expected Shortfall",

            f"${expected['expected_shortfall']:,.2f}",

        )

        cols[3].metric(

            "Portfolio Value",

            f"${parametric['portfolio_value']:,.2f}",

        )

        st.divider()

        st.subheader("Executive Risk Summary")

        executive = self.engine.executive_var_summary()

        st.json(executive)

    # -----------------------------------------------------------------

    def render_parametric(self):
        st.info("Parametric VaR workspace coming in Build 1.2")

    # -----------------------------------------------------------------

    def render_historical(self):
        st.info("Historical VaR workspace coming in Build 1.3")

    # -----------------------------------------------------------------

    def render_monte_carlo(self):
        st.info("Monte Carlo workspace coming in Build 1.4")

    # -----------------------------------------------------------------

    def render_stress(self):
        st.info("Stress Testing workspace coming in Build 2.1")

    # -----------------------------------------------------------------

    def render_portfolio(self):
        st.info("Portfolio Risk workspace coming in Build 2.2")

    # -----------------------------------------------------------------

    def render_history(self):
        st.info("History workspace coming in Build 2.3")

    # -----------------------------------------------------------------

    def render_executive(self):
        st.info("Executive Reporting coming in Build 3.1")


# =============================================================================
# Singleton
# =============================================================================

_DASHBOARD = None


def get_forex_var_dashboard(

    db=None,

    tenant_id=None,

    user_id=None,

    portfolio_id=None,

):

    global _DASHBOARD

    if (

        _DASHBOARD is None

        or _DASHBOARD.db is not db

        or _DASHBOARD.tenant_id != tenant_id

        or _DASHBOARD.user_id != user_id

        or _DASHBOARD.portfolio_id != portfolio_id

    ):

        _DASHBOARD = ForexVaRDashboard(

            db=db,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

    return _DASHBOARD


# =============================================================================
# Public Entry Point
# =============================================================================

def render_forex_var_dashboard(

    db=None,

    tenant_id=None,

    user_id=None,

    portfolio_id=None,

):

    return get_forex_var_dashboard(

        db=db,

        tenant_id=tenant_id,

        user_id=user_id,

        portfolio_id=portfolio_id,

    ).render()

# =============================================================================
# File: modules/forex/risk/forex_var_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-2
#
# Build 1.2
#
# Continue Immediately After Build 1.1
#
# Parametric VaR Workspace
# =============================================================================

# -----------------------------------------------------------------
# Parametric VaR
# -----------------------------------------------------------------

def render_parametric(self):
    st.subheader("Parametric Value-at-Risk")

    left, right = st.columns([1, 3])

    with left:
        confidence = st.selectbox(

            "Confidence Level",

            [0.90, 0.95, 0.975, 0.99],

            index=1,

            format_func=lambda x: f"{x * 100:.1f}%",

        )

        st.divider()

        if st.button(

                "Recalculate VaR",

                use_container_width=True,

        ):
            st.session_state["forex_var_refresh"] = True

    result = self.engine.calculate_parametric_var(

        confidence=confidence,

    )

    metrics = st.columns(4)

    metrics[0].metric(

        "Daily VaR",

        f"${result.daily_var:,.2f}",

    )

    metrics[1].metric(

        "Weekly VaR",

        f"${result.weekly_var:,.2f}",

    )

    metrics[2].metric(

        "Monthly VaR",

        f"${result.monthly_var:,.2f}",

    )

    metrics[3].metric(

        "Annual Volatility",

        f"{result.annualized_volatility:.2%}",

    )

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(

        [

            "Position VaR",

            "Component VaR",

            "Marginal VaR",

            "Currency VaR",

        ]

    )

    # --------------------------------------------------------------

    with tab1:
        st.subheader("Position Value-at-Risk")

        df = pd.DataFrame(

            self.engine.position_var_table(

                confidence,

            )

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    # --------------------------------------------------------------

    with tab2:
        st.subheader("Component VaR")

        df = pd.DataFrame(

            self.engine.component_var(

                confidence,

            )

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    # --------------------------------------------------------------

    with tab3:
        st.subheader("Marginal VaR")

        df = pd.DataFrame(

            self.engine.marginal_var(

                confidence,

            )

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    # --------------------------------------------------------------

    with tab4:
        st.subheader("Currency VaR")

        df = pd.DataFrame(

            self.engine.currency_var(

                confidence,

            )

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    st.divider()

    st.subheader("Diversification Benefit")

    diversification = self.engine.diversification_benefit(

        confidence,

    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(

        "Standalone VaR",

        f"${diversification['standalone_var']:,.2f}",

    )

    c2.metric(

        "Portfolio VaR",

        f"${diversification['portfolio_var']:,.2f}",

    )

    c3.metric(

        "Benefit",

        f"${diversification['benefit']:,.2f}",

    )

    c4.metric(

        "Benefit Ratio",

        f"{diversification['benefit_ratio']:.2%}",

    )

    st.divider()

    st.subheader("Executive Summary")

    summary = self.engine.executive_var_summary()

    st.json(summary)

    st.divider()

    export_df = pd.DataFrame(

        self.engine.position_var_table(

            confidence,

        )

    )

    csv = export_df.to_csv(

        index=False,

    ).encode("utf-8")

    st.download_button(

        "Download Position VaR",

        data=csv,

        file_name="forex_position_var.csv",

        mime="text/csv",

        use_container_width=True,

    )
# =============================================================================
# File: modules/forex/risk/forex_var_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-2
#
# Build 1.3
#
# Continue Immediately After Build 1.2
#
# Historical VaR Workspace
# =============================================================================

    # -----------------------------------------------------------------
    # Historical VaR
    # -----------------------------------------------------------------

    def render_historical(self):

        st.subheader("Historical Value-at-Risk")

        confidence = st.selectbox(

            "Historical Confidence",

            [0.90, 0.95, 0.975, 0.99],

            index=1,

            key="historical_var_confidence",

            format_func=lambda x: f"{x*100:.1f}%",

        )

        historical = self.engine.calculate_historical_var(

            confidence=confidence,

        )

        expected = self.engine.calculate_expected_shortfall(

            confidence=confidence,

        )

        comparison = self.engine.var_comparison(

            confidence=confidence,

        )

        metrics = st.columns(5)

        metrics[0].metric(

            "Daily Historical VaR",

            f"${historical.daily_var:,.2f}",

        )

        metrics[1].metric(

            "Weekly Historical VaR",

            f"${historical.weekly_var:,.2f}",

        )

        metrics[2].metric(

            "Monthly Historical VaR",

            f"${historical.monthly_var:,.2f}",

        )

        metrics[3].metric(

            "Expected Shortfall",

            f"${expected.expected_shortfall:,.2f}",

        )

        metrics[4].metric(

            "Tail Events",

            expected.tail_observations,

        )

        st.divider()

        tabs = st.tabs(

            [

                "Comparison",

                "Historical Statistics",

                "Tail Distribution",

                "Rolling VaR",

            ]

        )

        # -------------------------------------------------------------

        with tabs[0]:

            st.subheader(

                "Parametric vs Historical"

            )

            compare_df = pd.DataFrame(

                [

                    {

                        "Metric": "Parametric VaR",

                        "Value": comparison["parametric"],

                    },

                    {

                        "Metric": "Historical VaR",

                        "Value": comparison["historical"],

                    },

                    {

                        "Metric": "Expected Shortfall",

                        "Value": comparison["expected_shortfall"],

                    },

                    {

                        "Metric": "Difference",

                        "Value": comparison["difference"],

                    },

                    {

                        "Metric": "Difference %",

                        "Value": comparison["difference_pct"],

                    },

                ]

            )

            st.dataframe(

                compare_df,

                use_container_width=True,

                hide_index=True,

            )

        # -------------------------------------------------------------

        with tabs[1]:

            st.subheader(

                "Historical Portfolio Statistics"

            )

            stats = self.engine.historical_statistics()

            if stats:

                stats_df = pd.DataFrame(

                    [

                        {

                            "Metric": k,

                            "Value": v,

                        }

                        for k, v in stats.items()

                    ]

                )

                st.dataframe(

                    stats_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "No historical return series available."

                )

        # -------------------------------------------------------------

        with tabs[2]:

            st.subheader(

                "Tail Loss Distribution"

            )

            tail = pd.DataFrame(

                self.engine.tail_distribution(

                    confidence

                )

            )

            st.dataframe(

                tail,

                use_container_width=True,

                hide_index=True,

            )

        # -------------------------------------------------------------

        with tabs[3]:

            st.subheader(

                "Rolling Historical VaR"

            )

            rolling = self.engine.rolling_historical_var(

                confidence=confidence,

            )

            if rolling:

                rolling_df = pd.DataFrame(

                    {

                        "Observation":

                            range(

                                1,

                                len(rolling) + 1,

                            ),

                        "Historical VaR":

                            rolling,

                    }

                )

                st.line_chart(

                    rolling_df.set_index(

                        "Observation"

                    )

                )

                st.dataframe(

                    rolling_df,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "Insufficient historical observations."

                )

        st.divider()

        st.subheader("Historical Risk Summary")

        st.json(

            self.engine.historical_risk_summary()

        )

        st.divider()

        export = pd.DataFrame(

            self.engine.tail_distribution(

                confidence

            )

        )

        st.download_button(

            "Download Historical VaR",

            data=export.to_csv(

                index=False

            ).encode(

                "utf-8"

            ),

            file_name="forex_historical_var.csv",

            mime="text/csv",

            use_container_width=True,

        )

        # =============================================================================
        # File: modules/forex/risk/forex_var_dashboard.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-2
        #
        # Build 1.4
        #
        # Continue Immediately After Build 1.3
        #
        # Monte Carlo Workspace
        # =============================================================================

        # -----------------------------------------------------------------
        # Monte Carlo
        # -----------------------------------------------------------------

        def render_monte_carlo(self):

            st.subheader("Monte Carlo Value-at-Risk")

            left, right = st.columns([1, 3])

            with left:

                confidence = st.selectbox(

                    "Confidence Level",

                    [0.90, 0.95, 0.975, 0.99],

                    index=1,

                    key="mc_confidence",

                    format_func=lambda x: f"{x * 100:.1f}%",

                )

                simulations = st.slider(

                    "Simulation Runs",

                    min_value=1000,

                    max_value=100000,

                    value=10000,

                    step=1000,

                    key="mc_runs",

                )

            result = self.engine.calculate_monte_carlo(

                confidence=confidence,

                runs=simulations,

            )

            summary = self.engine.monte_carlo_summary(

                simulations,

            )

            percentiles = self.engine.monte_carlo_percentiles(

                simulations,

            )

            metrics = st.columns(5)

            metrics[0].metric(

                "95% Monte Carlo VaR",

                f"${result.percentile_95:,.2f}",

            )

            metrics[1].metric(

                "99% Monte Carlo VaR",

                f"${result.percentile_99:,.2f}",

            )

            metrics[2].metric(

                "Expected Shortfall",

                f"${result.expected_shortfall:,.2f}",

            )

            metrics[3].metric(

                "Worst Case",

                f"${result.worst_case:,.2f}",

            )

            metrics[4].metric(

                "Best Case",

                f"${result.best_case:,.2f}",

            )

            st.divider()

            tab1, tab2, tab3 = st.tabs(

                [

                    "Simulation Summary",

                    "Percentiles",

                    "Distribution",

                ]

            )

            # -------------------------------------------------------------

            with tab1:

                st.subheader(

                    "Simulation Statistics"

                )

                summary_df = pd.DataFrame(

                    [

                        {

                            "Metric": k,

                            "Value": v,

                        }

                        for k, v in summary.items()

                    ]

                )

                st.dataframe(

                    summary_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tab2:

                st.subheader(

                    "Portfolio Percentiles"

                )

                percentile_df = pd.DataFrame(

                    [

                        {

                            "Percentile": k,

                            "Portfolio Value": v,

                        }

                        for k, v in percentiles.items()

                    ]

                )

                st.dataframe(

                    percentile_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tab3:

                st.subheader(

                    "Simulated Portfolio Distribution"

                )

                values = self.engine.simulated_portfolio_values(

                    simulations,

                )

                if values:

                    chart = pd.DataFrame(

                        {

                            "Simulation":

                                range(

                                    1,

                                    len(values) + 1,

                                ),

                            "Portfolio Value":

                                values,

                        }

                    )

                    st.line_chart(

                        chart.set_index(

                            "Simulation"

                        )

                    )

                    st.dataframe(

                        chart.head(250),

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No simulations available."

                    )

            st.divider()

            st.subheader("Monte Carlo Simulation")

            st.json(

                result.to_dict()

            )

            st.divider()

            export = pd.DataFrame(

                {

                    "Simulation":

                        range(

                            1,

                            len(values) + 1,

                        ),

                    "Portfolio Value":

                        values,

                }

            )

            st.download_button(

                "Download Monte Carlo Results",

                data=export.to_csv(

                    index=False,

                ).encode(

                    "utf-8",

                ),

                file_name="forex_monte_carlo.csv",

                mime="text/csv",

                use_container_width=True,

            )

            # =============================================================================
            # File: modules/forex/risk/forex_var_dashboard.py
            #
            # Sprint 30
            # Phase 4C-3-3-2-2
            #
            # Build 2.1
            #
            # Continue Immediately After Build 1.4
            #
            # Stress Testing Workspace
            # =============================================================================

            # -----------------------------------------------------------------
            # Stress Testing
            # -----------------------------------------------------------------

            def render_stress(self):

                st.subheader("Institutional Stress Testing")

                left, right = st.columns([1, 3])

                with left:
                    scenario = st.selectbox(

                        "Scenario",

                        [

                            "RATE_SHOCK",

                            "USD_SURGE",

                            "USD_COLLAPSE",

                            "FLASH_CRASH",

                            "VOLATILITY",

                            "LIQUIDITY",

                            "CENTRAL_BANK",

                        ],

                    )

                    currency = st.text_input(

                        "Currency Shock",

                        value="USD",

                    ).upper()

                    currency_shock = st.slider(

                        "Currency Shock %",

                        -20.0,

                        20.0,

                        -5.0,

                        0.5,

                    ) / 100.0

                    pair = st.text_input(

                        "FX Pair",

                        value="EURUSD",

                    ).upper()

                    pair_shock = st.slider(

                        "Pair Shock %",

                        -20.0,

                        20.0,

                        -5.0,

                        0.5,

                    ) / 100.0

                    volatility_multiplier = st.slider(

                        "Volatility Multiplier",

                        1.0,

                        5.0,

                        1.50,

                        0.10,

                    )

                st.divider()

                stress_result = self.engine.execute_scenario(

                    scenario,

                )

                currency_result = self.engine.currency_shock(

                    currency,

                    currency_shock,

                )

                pair_result = self.engine.pair_shock(

                    pair,

                    pair_shock,

                )

                volatility_result = self.engine.volatility_shock(

                    volatility_multiplier,

                )

                margin_result = self.engine.margin_stress()

                liquidity_result = self.engine.liquidity_stress()

                survivability = self.engine.survivability_score()

                traffic = self.engine.traffic_light_rating()

                metrics = st.columns(5)

                metrics[0].metric(

                    "Portfolio Before",

                    f"${stress_result.portfolio_before:,.2f}",

                )

                metrics[1].metric(

                    "Portfolio After",

                    f"${stress_result.portfolio_after:,.2f}",

                )

                metrics[2].metric(

                    "PnL",

                    f"${stress_result.pnl_change:,.2f}",

                )

                metrics[3].metric(

                    "PnL %",

                    f"{stress_result.pnl_percent:.2%}",

                )

                metrics[4].metric(

                    "Scenario",

                    stress_result.scenario.value,

                )

                st.divider()

                tabs = st.tabs(

                    [

                        "Scenario",

                        "Currency Shock",

                        "Pair Shock",

                        "Volatility",

                        "Margin",

                        "Liquidity",

                        "Stress Ranking",

                    ]

                )

                # -------------------------------------------------------------

                with tabs[0]:
                    st.subheader(

                        "Scenario Result"

                    )

                    st.json(

                        stress_result.to_dict()

                    )

                # -------------------------------------------------------------

                with tabs[1]:
                    st.subheader(

                        "Currency Stress"

                    )

                    st.json(

                        currency_result

                    )

                # -------------------------------------------------------------

                with tabs[2]:
                    st.subheader(

                        "FX Pair Stress"

                    )

                    st.json(

                        pair_result

                    )

                # -------------------------------------------------------------

                with tabs[3]:
                    st.subheader(

                        "Volatility Shock"

                    )

                    df = pd.DataFrame(

                        volatility_result

                    )

                    st.dataframe(

                        df,

                        use_container_width=True,

                        hide_index=True,

                    )

                # -------------------------------------------------------------

                with tabs[4]:
                    st.subheader(

                        "Margin Stress"

                    )

                    st.json(

                        margin_result

                    )

                # -------------------------------------------------------------

                with tabs[5]:
                    st.subheader(

                        "Liquidity Stress"

                    )

                    st.json(

                        liquidity_result

                    )

                # -------------------------------------------------------------

                with tabs[6]:
                    st.subheader(

                        "Scenario Ranking"

                    )

                    ranking = pd.DataFrame(

                        self.engine.stress_ranking()

                    )

                    st.dataframe(

                        ranking,

                        use_container_width=True,

                        hide_index=True,

                    )

                st.divider()

                left, center, right = st.columns(3)

                with left:
                    st.subheader(

                        "Traffic Light"

                    )

                    st.success(

                        traffic["status"]

                    )

                    st.write(

                        traffic["message"]

                    )

                with center:
                    st.subheader(

                        "Survivability"

                    )

                    st.metric(

                        "Score",

                        survivability["score"],

                    )

                    st.metric(

                        "Rating",

                        survivability["rating"],

                    )

                with right:
                    st.subheader(

                        "Stress Summary"

                    )

                    st.json(

                        self.engine.stress_summary()

                    )

                st.divider()

                report = self.engine.stress_dashboard_packet()

                st.download_button(

                    "Download Stress Report (JSON)",

                    data=self.engine.export_json(),

                    file_name="forex_stress_report.json",

                    mime="application/json",

                    use_container_width=True,

                )

        # =============================================================================
        # File: modules/forex/risk/forex_var_dashboard.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-2
        #
        # Build 2.2
        #
        # Continue Immediately After Build 2.1
        #
        # Portfolio Risk Workspace
        # =============================================================================

        # -----------------------------------------------------------------
        # Portfolio Risk
        # -----------------------------------------------------------------

        def render_portfolio(self):

            st.subheader("Portfolio Risk Analytics")

            summary = self.engine.portfolio_summary()

            statistics = self.engine.build_portfolio_statistics()

            metrics = st.columns(6)

            metrics[0].metric(

                "Positions",

                statistics.total_positions,

            )

            metrics[1].metric(

                "Market Value",

                f"${statistics.total_market_value:,.2f}",

            )

            metrics[2].metric(

                "Notional",

                f"${statistics.total_notional:,.2f}",

            )

            metrics[3].metric(

                "Exposure",

                f"${statistics.total_exposure:,.2f}",

            )

            metrics[4].metric(

                "Leverage",

                f"{statistics.leverage:.2f}x",

            )

            metrics[5].metric(

                "Portfolio β",

                f"{statistics.beta:.2f}",

            )

            st.divider()

            tabs = st.tabs(

                [

                    "Statistics",

                    "Risk Contribution",

                    "Exposure",

                    "Correlation",

                    "Covariance",

                    "Diversification",

                ]

            )

            # -------------------------------------------------------------

            with tabs[0]:

                st.subheader(

                    "Portfolio Statistics"

                )

                stats_df = pd.DataFrame(

                    [

                        {

                            "Metric": key,

                            "Value": value,

                        }

                        for key, value in

                        statistics.to_dict().items()

                    ]

                )

                st.dataframe(

                    stats_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tabs[1]:

                st.subheader(

                    "Risk Contribution"

                )

                contribution = pd.DataFrame(

                    self.engine.risk_contribution()

                )

                st.dataframe(

                    contribution,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tabs[2]:

                st.subheader(

                    "Exposure Analysis"

                )

                c1, c2 = st.columns(2)

                with c1:
                    st.write("Currency Exposure")

                    exposure = pd.DataFrame(

                        [

                            {

                                "Currency": k,

                                "Exposure": v,

                            }

                            for k, v in

                            self.engine.currency_exposure().items()

                        ]

                    )

                    st.dataframe(

                        exposure,

                        use_container_width=True,

                        hide_index=True,

                    )

                with c2:
                    st.write("Directional Exposure")

                    direction = pd.DataFrame(

                        [

                            {

                                "Metric": k,

                                "Value": v,

                            }

                            for k, v in

                            self.engine.directional_exposure().items()

                        ]

                    )

                    st.dataframe(

                        direction,

                        use_container_width=True,

                        hide_index=True,

                    )

            # -------------------------------------------------------------

            with tabs[3]:

                st.subheader(

                    "Correlation Matrix"

                )

                correlation = (

                    self.engine

                    .correlation_matrix_dataframe()

                )

                if correlation.empty:

                    st.info(

                        "Correlation matrix unavailable."

                    )

                else:

                    st.dataframe(

                        correlation,

                        use_container_width=True,

                    )

            # -------------------------------------------------------------

            with tabs[4]:

                st.subheader(

                    "Covariance Matrix"

                )

                covariance = (

                    self.engine

                    .covariance_matrix_dataframe()

                )

                if covariance.empty:

                    st.info(

                        "Covariance matrix unavailable."

                    )

                else:

                    st.dataframe(

                        covariance,

                        use_container_width=True,

                    )

            # -------------------------------------------------------------

            with tabs[5]:

                st.subheader(

                    "Diversification"

                )

                diversification = (

                    self.engine

                    .diversification_benefit()

                )

                score = (

                    self.engine

                    .diversification_ratio()

                )

                c1, c2, c3 = st.columns(3)

                c1.metric(

                    "Diversification Ratio",

                    f"{score:.2f}",

                )

                c2.metric(

                    "Benefit",

                    f"${diversification['benefit']:,.2f}",

                )

                c3.metric(

                    "Benefit Ratio",

                    f"{diversification['benefit_ratio']:.2%}",

                )

                st.json(

                    diversification

                )

            st.divider()

            st.subheader(

                "Portfolio Summary"

            )

            st.json(summary)

            st.divider()

            export = pd.DataFrame(

                self.engine.risk_contribution()

            )

            st.download_button(

                "Download Portfolio Risk",

                data=export.to_csv(

                    index=False,

                ).encode(

                    "utf-8",

                ),

                file_name="forex_portfolio_risk.csv",

                mime="text/csv",

                use_container_width=True,

            )

        # =============================================================================
        # File: modules/forex/risk/forex_var_dashboard.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-2
        #
        # Build 2.3
        #
        # Continue Immediately After Build 2.2
        #
        # VaR History Workspace
        # =============================================================================

        # -----------------------------------------------------------------
        # History
        # -----------------------------------------------------------------

        def render_history(self):

            st.subheader("Value-at-Risk History")

            history = self.engine.historical_trend()

            analytics = self.engine.analytics_history

            if not history:
                st.info(

                    "No VaR history has been recorded."

                )

                return

            metrics = st.columns(4)

            metrics[0].metric(

                "Snapshots",

                len(history),

            )

            metrics[1].metric(

                "Current VaR",

                f"${history[-1]['var95']:,.2f}",

            )

            metrics[2].metric(

                "Current ES",

                f"${history[-1]['expected_shortfall']:,.2f}",

            )

            metrics[3].metric(

                "Portfolio Value",

                f"${history[-1]['portfolio_value']:,.2f}",

            )

            st.divider()

            tabs = st.tabs(

                [

                    "Timeline",

                    "VaR Trend",

                    "Volatility Trend",

                    "Analytics Snapshots",

                    "Runtime History",

                ]

            )

            # -------------------------------------------------------------

            with tabs[0]:

                st.subheader(

                    "Historical Timeline"

                )

                history_df = pd.DataFrame(

                    history

                )

                st.dataframe(

                    history_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tabs[1]:

                st.subheader(

                    "VaR Trend"

                )

                var_chart = pd.DataFrame(

                    {

                        "Observation":

                            range(

                                1,

                                len(history) + 1,

                            ),

                        "VaR95":

                            [

                                row["var95"]

                                for row in history

                            ],

                        "VaR99":

                            [

                                row["var99"]

                                for row in history

                            ],

                    }

                )

                st.line_chart(

                    var_chart.set_index(

                        "Observation"

                    )

                )

                st.dataframe(

                    var_chart,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tabs[2]:

                st.subheader(

                    "Volatility Trend"

                )

                volatility_df = pd.DataFrame(

                    {

                        "Observation":

                            range(

                                1,

                                len(history) + 1,

                            ),

                        "Volatility":

                            [

                                row["volatility"]

                                for row in history

                            ],

                    }

                )

                st.line_chart(

                    volatility_df.set_index(

                        "Observation"

                    )

                )

                st.dataframe(

                    volatility_df,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------

            with tabs[3]:

                st.subheader(

                    "Analytics Snapshots"

                )

                if analytics:

                    snapshot_df = pd.DataFrame(

                        [

                            snapshot.to_dict()

                            for snapshot in analytics

                        ]

                    )

                    st.dataframe(

                        snapshot_df,

                        use_container_width=True,

                        hide_index=True,

                    )

                else:

                    st.info(

                        "No analytics snapshots recorded."

                    )

            # -------------------------------------------------------------

            with tabs[4]:

                st.subheader(

                    "Runtime History"

                )

                runtime_df = pd.DataFrame(

                    history

                )[

                    [

                        "runtime",

                        "generated",

                        "method",

                        "portfolio_value",

                    ]

                ]

                st.dataframe(

                    runtime_df,

                    use_container_width=True,

                    hide_index=True,

                )

            st.divider()

            st.subheader(

                "History Statistics"

            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(

                "Maximum VaR",

                f"${max(r['var95'] for r in history):,.2f}",

            )

            c2.metric(

                "Minimum VaR",

                f"${min(r['var95'] for r in history):,.2f}",

            )

            c3.metric(

                "Average VaR",

                f"${pd.DataFrame(history)['var95'].mean():,.2f}",

            )

            c4.metric(

                "Average Volatility",

                f"{pd.DataFrame(history)['volatility'].mean():.4f}",

            )

            st.divider()

            export = pd.DataFrame(

                history

            )

            st.download_button(

                "Download VaR History",

                data=export.to_csv(

                    index=False,

                ).encode(

                    "utf-8",

                ),

                file_name="forex_var_history.csv",

                mime="text/csv",

                use_container_width=True,

            )

        # =============================================================================
        # File: modules/forex/risk/forex_var_dashboard.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-2
        #
        # Build 3.1
        #
        # Continue Immediately After Build 2.3
        #
        # Executive Risk Report Workspace
        # =============================================================================

        # -----------------------------------------------------------------
        # Executive Report
        # -----------------------------------------------------------------

        def render_executive(self):

            st.subheader("Executive Value-at-Risk Report")

            report = self.engine.dashboard_packet()

            executive = self.engine.executive_var_summary()

            stress = self.engine.executive_stress_scorecard()

            traffic = self.engine.traffic_light_rating()

            survivability = self.engine.survivability_score()

            metrics = st.columns(5)

            metrics[0].metric(

                "Portfolio Value",

                f"${report['parametric']['portfolio_value']:,.2f}",

            )

            metrics[1].metric(

                "Daily VaR",

                f"${report['parametric']['daily_var']:,.2f}",

            )

            metrics[2].metric(

                "Historical VaR",

                f"${report['historical']['daily_var']:,.2f}",

            )

            metrics[3].metric(

                "Expected Shortfall",

                f"${report['expected_shortfall']['expected_shortfall']:,.2f}",

            )

            metrics[4].metric(

                "Stress Score",

                f"{stress['stress_score']:.2f}",

            )

            st.divider()

            overview, portfolio, stress_tab, governance = st.tabs(

                [

                    "Executive Overview",

                    "Portfolio",

                    "Stress Intelligence",

                    "Governance",

                ]

            )

            # -------------------------------------------------------------
            # Executive Overview
            # -------------------------------------------------------------

            with overview:
                st.subheader(

                    "Executive Risk Dashboard"

                )

                c1, c2 = st.columns([2, 1])

                with c1:
                    summary = pd.DataFrame(

                        [

                            {

                                "Metric": "Portfolio Value",

                                "Value": report["parametric"]["portfolio_value"],

                            },

                            {

                                "Metric": "Daily VaR",

                                "Value": report["parametric"]["daily_var"],

                            },

                            {

                                "Metric": "Weekly VaR",

                                "Value": report["parametric"]["weekly_var"],

                            },

                            {

                                "Metric": "Monthly VaR",

                                "Value": report["parametric"]["monthly_var"],

                            },

                            {

                                "Metric": "Historical VaR",

                                "Value": report["historical"]["daily_var"],

                            },

                            {

                                "Metric": "Expected Shortfall",

                                "Value": report["expected_shortfall"]["expected_shortfall"],

                            },

                        ]

                    )

                    st.dataframe(

                        summary,

                        use_container_width=True,

                        hide_index=True,

                    )

                with c2:
                    color = {

                        "GREEN": "🟢",

                        "YELLOW": "🟡",

                        "ORANGE": "🟠",

                        "RED": "🔴",

                    }

                    st.metric(

                        "Traffic Light",

                        traffic["status"],

                    )

                    st.write(

                        color.get(

                            traffic["status"],

                            ""

                        )

                    )

                    st.info(

                        traffic["message"]

                    )

            # -------------------------------------------------------------
            # Portfolio
            # -------------------------------------------------------------

            with portfolio:
                st.subheader(

                    "Portfolio Analytics"

                )

                stats = self.engine.build_portfolio_statistics()

                stats_df = pd.DataFrame(

                    [

                        {

                            "Metric": k,

                            "Value": v,

                        }

                        for k, v in

                        stats.to_dict().items()

                    ]

                )

                st.dataframe(

                    stats_df,

                    use_container_width=True,

                    hide_index=True,

                )

                st.subheader(

                    "Largest Risk Positions"

                )

                largest = pd.DataFrame(

                    self.engine.largest_risk_positions(

                        10

                    )

                )

                st.dataframe(

                    largest,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------
            # Stress Intelligence
            # -------------------------------------------------------------

            with stress_tab:
                st.subheader(

                    "Executive Stress Assessment"

                )

                left, right = st.columns(2)

                with left:
                    st.metric(

                        "Stress Score",

                        f"{stress['stress_score']:.2f}",

                    )

                    st.metric(

                        "Survivability",

                        survivability["score"],

                    )

                    st.metric(

                        "Rating",

                        survivability["rating"],

                    )

                with right:
                    st.json(

                        traffic

                    )

                st.divider()

                st.subheader(

                    "Stress Ranking"

                )

                ranking = pd.DataFrame(

                    self.engine.stress_ranking()

                )

                st.dataframe(

                    ranking,

                    use_container_width=True,

                    hide_index=True,

                )

            # -------------------------------------------------------------
            # Governance
            # -------------------------------------------------------------

            with governance:
                st.subheader(

                    "Governance & Audit"

                )

                governance_df = pd.DataFrame(

                    [

                        {

                            "Item":

                                "Runtime ID",

                            "Value":

                                self.engine.runtime_id,

                        },

                        {

                            "Item":

                                "Tenant",

                            "Value":

                                self.engine.tenant_id,

                        },

                        {

                            "Item":

                                "User",

                            "Value":

                                self.engine.user_id,

                        },

                        {

                            "Item":

                                "Portfolio",

                            "Value":

                                self.engine.portfolio.portfolio_id,

                        },

                        {

                            "Item":

                                "Generated",

                            "Value":

                                report["generated_at"],

                        },

                    ]

                )

                st.dataframe(

                    governance_df,

                    use_container_width=True,

                    hide_index=True,

                )

            st.divider()

            st.subheader(

                "Complete Executive Report"

            )

            st.json(

                report

            )

            st.download_button(

                "Download Executive Report (JSON)",

                data=self.engine.export_json(),

                file_name="forex_executive_var_report.json",

                mime="application/json",

                use_container_width=True,

            )

        # =============================================================================
        # File: modules/forex/risk/forex_var_dashboard.py
        #
        # Sprint 30
        # Phase 4C-3-3-2-2
        #
        # Build 3.2
        #
        # Continue Immediately After Build 3.1
        #
        # Executive Analytics
        # Runtime Intelligence
        # Report Export Center
        # =============================================================================

        # -----------------------------------------------------------------
        # Executive Analytics
        # -----------------------------------------------------------------

        def render_executive_analytics(self):

            st.subheader("Executive Analytics")

            executive = self.engine.executive_var_summary()

            stress = self.engine.executive_stress_scorecard()

            left, right = st.columns(2)

            with left:
                st.write("### Portfolio Summary")

                summary_df = pd.DataFrame(

                    [

                        {

                            "Metric": key,

                            "Value": value,

                        }

                        for key, value in executive.items()

                        if not isinstance(

                        value,

                        (dict, list),

                    )

                    ]

                )

                st.dataframe(

                    summary_df,

                    use_container_width=True,

                    hide_index=True,

                )

            with right:
                st.write("### Stress Analytics")

                stress_df = pd.DataFrame(

                    [

                        {

                            "Metric": key,

                            "Value": value,

                        }

                        for key, value in stress.items()

                        if not isinstance(

                        value,

                        (dict, list),

                    )

                    ]

                )

                st.dataframe(

                    stress_df,

                    use_container_width=True,

                    hide_index=True,

                )

        # -----------------------------------------------------------------
        # Runtime Intelligence
        # -----------------------------------------------------------------

        def render_runtime_information(self):

            st.subheader("Runtime Information")

            runtime = pd.DataFrame(

                [

                    {

                        "Property":

                            "Runtime ID",

                        "Value":

                            self.engine.runtime_id,

                    },

                    {

                        "Property":

                            "Tenant",

                        "Value":

                            self.engine.tenant_id,

                    },

                    {

                        "Property":

                            "User",

                        "Value":

                            self.engine.user_id,

                    },

                    {

                        "Property":

                            "Portfolio",

                        "Value":

                            self.engine.portfolio.portfolio_id,

                    },

                    {

                        "Property":

                            "Configuration",

                        "Value":

                            self.engine.configuration_summary(),

                    },

                    {

                        "Property":

                            "Status",

                        "Value":

                            self.engine.status(),

                    },

                ]

            )

            st.dataframe(

                runtime,

                use_container_width=True,

                hide_index=True,

            )

        # -----------------------------------------------------------------
        # Export Center
        # -----------------------------------------------------------------

        def render_export_center(self):

            st.subheader("Report Export Center")

            packet = self.engine.dashboard_packet()

            json_report = self.engine.export_json()

            history = pd.DataFrame(

                self.engine.historical_trend()

            )

            contribution = pd.DataFrame(

                self.engine.risk_contribution()

            )

            component = pd.DataFrame(

                self.engine.component_var()

            )

            marginal = pd.DataFrame(

                self.engine.marginal_var()

            )

            left, right = st.columns(2)

            with left:
                st.download_button(

                    "Download Full JSON Report",

                    data=json_report,

                    file_name="forex_var_report.json",

                    mime="application/json",

                    use_container_width=True,

                )

                st.download_button(

                    "Download VaR History",

                    data=history.to_csv(

                        index=False,

                    ).encode("utf-8"),

                    file_name="forex_var_history.csv",

                    mime="text/csv",

                    use_container_width=True,

                )

                st.download_button(

                    "Download Risk Contribution",

                    data=contribution.to_csv(

                        index=False,

                    ).encode("utf-8"),

                    file_name="forex_risk_contribution.csv",

                    mime="text/csv",

                    use_container_width=True,

                )

            with right:
                st.download_button(

                    "Download Component VaR",

                    data=component.to_csv(

                        index=False,

                    ).encode("utf-8"),

                    file_name="forex_component_var.csv",

                    mime="text/csv",

                    use_container_width=True,

                )

                st.download_button(

                    "Download Marginal VaR",

                    data=marginal.to_csv(

                        index=False,

                    ).encode("utf-8"),

                    file_name="forex_marginal_var.csv",

                    mime="text/csv",

                    use_container_width=True,

                )

                st.download_button(

                    "Download Dashboard Packet",

                    data=pd.DataFrame(

                        [

                            {

                                "Section": k,

                                "Type": type(v).__name__,

                            }

                            for k, v in packet.items()

                        ]

                    ).to_csv(

                        index=False,

                    ).encode("utf-8"),

                    file_name="forex_dashboard_sections.csv",

                    mime="text/csv",

                    use_container_width=True,

                )

        # -----------------------------------------------------------------
        # Complete Executive Center
        # -----------------------------------------------------------------

        def render_executive_center(self):

            tabs = st.tabs(

                [

                    "Executive Analytics",

                    "Runtime",

                    "Exports",

                ]

            )

            with tabs[0]:
                self.render_executive_analytics()

            with tabs[1]:
                self.render_runtime_information()

            with tabs[2]:
                self.render_export_center()