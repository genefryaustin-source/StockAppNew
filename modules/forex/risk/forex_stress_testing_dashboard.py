# =============================================================================
# File: modules/forex/risk/forex_stress_testing_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-4
#
# Build 1.1
#
# Institutional Stress Testing Dashboard
# =============================================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from typing import Optional
from typing import Any

from modules.forex.risk.forex_stress_testing_engine import (
    get_forex_stress_testing_engine,
)


# =============================================================================
# Dashboard
# =============================================================================

class ForexStressTestingDashboard:

    def __init__(

        self,

        db: Optional[Any] = None,

        portfolio=None,

        tenant_id=None,

        user_id=None,

        portfolio_id=None,

    ):

        self.db = db

        self.portfolio = portfolio

        self.tenant_id = tenant_id

        self.user_id = user_id

        self.portfolio_id = portfolio_id

        self.engine = get_forex_stress_testing_engine(

            db=db,

            portfolio=portfolio,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self):

        st.title("Institutional Stress Testing")

        workspace = st.radio(

            "Stress Testing Workspace",

            [

                "Overview",

                "Scenario Analysis",

                "Historical Crisis",

                "Multi-Factor",

                "Runtime History",

                "Executive Report",

            ],

            horizontal=True,

        )

        st.divider()

        if workspace == "Overview":

            self.render_overview()

        elif workspace == "Scenario Analysis":

            self.render_scenarios()

        elif workspace == "Historical Crisis":

            self.render_historical()

        elif workspace == "Multi-Factor":

            self.render_multifactor()

        elif workspace == "Runtime History":

            self.render_runtime()

        elif workspace == "Executive Report":

            self.render_executive()

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    def render_overview(self):

        summary = self.engine.summary()

        traffic = self.engine.traffic_light()

        rating = self.engine.executive_rating()

        metrics = st.columns(5)

        metrics[0].metric(

            "Stress Runs",

            summary.get(

                "scenario_count",

                0,

            ),

        )

        metrics[1].metric(

            "Passed",

            summary.get(

                "passed",

                0,

            ),

        )

        metrics[2].metric(

            "Failed",

            summary.get(

                "failed",

                0,

            ),

        )

        metrics[3].metric(

            "Risk Rating",

            rating["rating"],

        )

        metrics[4].metric(

            "Traffic",

            traffic["status"],

        )

        st.divider()

        st.subheader(

            "Runtime Status"

        )

        st.json(

            self.engine.status()

        )

        st.divider()

        st.subheader(

            "Executive Summary"

        )

        st.json(

            self.engine.executive_scorecard()

        )

    # ------------------------------------------------------------------
    # Placeholder Workspaces
    # ------------------------------------------------------------------

    def render_scenarios(self):

        st.info(

            "Scenario Analysis workspace will be completed in Build 1.2"

        )

    def render_historical(self):

        st.info(

            "Historical Crisis workspace will be completed in Build 1.3"

        )

    def render_multifactor(self):

        st.info(

            "Multi-Factor workspace will be completed in Build 1.4"

        )

    def render_runtime(self):

        st.info(

            "Runtime History workspace will be completed in Build 2.1"

        )

    def render_executive(self):

        st.info(

            "Executive Report workspace will be completed in Build 2.2"

        )




# =============================================================================
# Singleton
# =============================================================================

_DASHBOARD = None


def get_forex_stress_testing_dashboard(

    db=None,

    portfolio=None,

    tenant_id=None,

    user_id=None,

    portfolio_id=None,

):

    global _DASHBOARD

    if (

        _DASHBOARD is None

        or _DASHBOARD.db is not db

        or _DASHBOARD.portfolio is not portfolio

        or _DASHBOARD.tenant_id != tenant_id

        or _DASHBOARD.user_id != user_id

        or _DASHBOARD.portfolio_id != portfolio_id

    ):

        _DASHBOARD = ForexStressTestingDashboard(

            db=db,

            portfolio=portfolio,

            tenant_id=tenant_id,

            user_id=user_id,

            portfolio_id=portfolio_id,

        )

    return _DASHBOARD

# =============================================================================
# Public Entry Point
# =============================================================================

def render_forex_stress_testing_dashboard(

    db=None,

    portfolio=None,

    tenant_id=None,

    user_id=None,

    portfolio_id=None,

):

    return get_forex_stress_testing_dashboard(

        db=db,

        portfolio=portfolio,

        tenant_id=tenant_id,

        user_id=user_id,

        portfolio_id=portfolio_id,

    ).render()

# =============================================================================
# File: modules/forex/risk/forex_stress_testing_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-4
#
# Build 1.2
#
# Continue Immediately After Build 1.1
#
# Scenario Analysis Workspace
# =============================================================================

# ------------------------------------------------------------------
# Scenario Analysis
# ------------------------------------------------------------------

def render_scenarios(self):

st.subheader("Institutional Scenario Analysis")

scenario = st.selectbox(

"Stress Scenario",

self.engine.available_scenarios(),

)

col1, col2, col3 = st.columns(3)

with col1:

if st.button(

"Run Scenario",

use_container_width=True,

):
st.session_state["stress_result"] = (

self.engine.execute(

scenario

)

)

with col2:

if st.button(

"Run Complete Suite",

use_container_width=True,

):
self.engine.execute_all()

with col3:

if st.button(

"Persist Results",

use_container_width=True,

):
self.engine.persist_all_results()

st.success(

"Stress history saved."

)

st.divider()

result = st.session_state.get(

"stress_result"

)

if result is None:

history = self.engine.latest_results()

if history:

result = history[-1]

if isinstance(result, dict):

result = result

else:

result = result.to_dict()

if result is None:
st.info(

"Execute a scenario to begin."

)

return

if hasattr(result, "to_dict"):
result = result.to_dict()

metrics = st.columns(5)

metrics[0].metric(

"Portfolio Before",

f"${result['portfolio_before']:,.2f}",

)

metrics[1].metric(

"Portfolio After",

f"${result['portfolio_after']:,.2f}",

)

metrics[2].metric(

"PnL",

f"${result['pnl']:,.2f}",

)

metrics[3].metric(

"PnL %",

f"{result['pnl_pct']:.2%}",

)

metrics[4].metric(

"Survivability",

f"{result['survivability_score']:.1f}",

)

st.divider()

tabs = st.tabs(

[

"Scenario",

"Scenario Metadata",

"Scenario Library",

"Executed Results",

]

)

# --------------------------------------------------------------

with tabs[0]:

st.subheader(

"Scenario Result"

)

st.json(

result

)

# --------------------------------------------------------------

with tabs[1]:

st.subheader(

"Scenario Metadata"

)

metadata = result.get(

"metadata",

{},

)

metadata_df = pd.DataFrame(

[

{

"Field": k,

"Value": v,

}

for k, v in

metadata.items()

]

)

st.dataframe(

metadata_df,

use_container_width=True,

hide_index=True,

)

# --------------------------------------------------------------

with tabs[2]:

st.subheader(

"Available Scenarios"

)

scenario_rows = []

for name in self.engine.available_scenarios():
definition = self.engine.get_scenario(

name

)

scenario_rows.append(

{

"Scenario":

definition.scenario.value,

"Title":

definition.title,

"Shock":

definition.shock_pct,

"Volatility":

definition.volatility_multiplier,

"Liquidity":

definition.liquidity_haircut,

}

)

st.dataframe(

pd.DataFrame(

scenario_rows

),

use_container_width=True,

hide_index=True,

)

# --------------------------------------------------------------

with tabs[3]:

st.subheader(

"Executed Scenario Results"

)

results = pd.DataFrame(

self.engine.latest_results()

)

if not results.empty:

st.dataframe(

results,

use_container_width=True,

hide_index=True,

)

else:

st.info(

"No executed scenarios."

)

st.divider()

export = pd.DataFrame(

self.engine.latest_results()

)

st.download_button(

"Download Scenario Results",

data=export.to_csv(

index=False,

).encode(

"utf-8"

),

file_name="forex_stress_scenarios.csv",

mime="text/csv",

use_container_width=True,

)


# =============================================================================
# File: modules/forex/risk/forex_stress_testing_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-4
#
# Build 1.3
#
# Continue Immediately After Build 1.2
#
# Historical Crisis Replay Workspace
# =============================================================================

    # ------------------------------------------------------------------
    # Historical Crisis Replay
    # ------------------------------------------------------------------

    def render_historical(self):

        st.subheader("Historical Crisis Replay")

        crises = self.engine.historical_crises()

        crisis_names = [

            c["name"]

            for c in crises

        ]

        selected = st.selectbox(

            "Historical Crisis",

            crisis_names,

        )

        left, center, right = st.columns(3)

        with left:

            if st.button(

                "Replay Crisis",

                use_container_width=True,

            ):

                st.session_state[

                    "historical_crisis"

                ] = self.engine.replay_crisis(

                    selected

                )

        with center:

            if st.button(

                "Replay Entire Library",

                use_container_width=True,

            ):

                self.engine.replay_all_crises()

                st.success(

                    "Historical replay complete."

                )

        with right:

            if st.button(

                "Persist Results",

                use_container_width=True,

            ):

                self.engine.persist_all_results()

                st.success(

                    "Historical results saved."

                )

        st.divider()

        crisis = st.session_state.get(

            "historical_crisis"

        )

        if crisis is None:

            st.info(

                "Select a crisis and click Replay Crisis."

            )

            return

        if hasattr(

            crisis,

            "to_dict",

        ):

            crisis = crisis.to_dict()

        metrics = st.columns(5)

        metrics[0].metric(

            "Portfolio Before",

            f"${crisis['portfolio_before']:,.2f}",

        )

        metrics[1].metric(

            "Portfolio After",

            f"${crisis['portfolio_after']:,.2f}",

        )

        metrics[2].metric(

            "Loss",

            f"${abs(crisis['pnl']):,.2f}",

        )

        metrics[3].metric(

            "Loss %",

            f"{abs(crisis['pnl_pct']):.2%}",

        )

        metrics[4].metric(

            "Survivability",

            f"{crisis['survivability_score']:.1f}",

        )

        st.divider()

        tabs = st.tabs(

            [

                "Replay Result",

                "Historical Library",

                "Historical Ranking",

                "Historical Statistics",

            ]

        )

        # ----------------------------------------------------------

        with tabs[0]:

            st.subheader(

                "Replay Result"

            )

            st.json(

                crisis

            )

        # ----------------------------------------------------------

        with tabs[1]:

            st.subheader(

                "Historical Crisis Library"

            )

            st.dataframe(

                pd.DataFrame(

                    crises

                ),

                use_container_width=True,

                hide_index=True,

            )

        # ----------------------------------------------------------

        with tabs[2]:

            st.subheader(

                "Historical Crisis Ranking"

            )

            ranking = pd.DataFrame(

                self.engine

                .historical_crisis_ranking()

            )

            st.dataframe(

                ranking,

                use_container_width=True,

                hide_index=True,

            )

        # ----------------------------------------------------------

        with tabs[3]:

            st.subheader(

                "Historical Statistics"

            )

            stats = self.engine.crisis_statistics()

            stats_df = pd.DataFrame(

                [

                    {

                        "Metric": k,

                        "Value": v,

                    }

                    for k, v in

                    stats.items()

                ]

            )

            st.dataframe(

                stats_df,

                use_container_width=True,

                hide_index=True,

            )

        st.divider()

        st.subheader(

            "Historical Dashboard Packet"

        )

        st.json(

            self.engine

            .historical_dashboard_packet()

        )

        st.download_button(

            "Download Historical Crisis Report",

            data=pd.DataFrame(

                self.engine

                .historical_crisis_ranking()

            ).to_csv(

                index=False,

            ).encode(

                "utf-8",

            ),

            file_name="forex_historical_crisis.csv",

            mime="text/csv",

            use_container_width=True,

        )
# =============================================================================
# File: modules/forex/risk/forex_stress_testing_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-4
#
# Build 1.4
#
# Continue Immediately After Build 1.3
#
# Multi-Factor Institutional Stress Workspace
# =============================================================================

    # ------------------------------------------------------------------
    # Multi-Factor Stress
    # ------------------------------------------------------------------

    def render_multifactor(self):

        st.subheader("Multi-Factor Institutional Stress")

        left, right = st.columns([1, 3])

        with left:

            scenarios = self.engine.available_scenarios()

            selected = st.multiselect(

                "Stress Factors",

                scenarios,

                default=scenarios[:3],

            )

            execute = st.button(

                "Execute Multi-Factor Scenario",

                use_container_width=True,

            )

            run_suite = st.button(

                "Run Institutional Crisis Suite",

                use_container_width=True,

            )

        if execute:

            if selected:

                st.session_state["multifactor_result"] = (

                    self.engine.apply_multi_factor(

                        selected

                    )

                )

            else:

                st.warning(

                    "Select at least one scenario."

                )

        if run_suite:

            self.engine.execute_crisis_suite()

            st.success(

                "Institutional crisis suite completed."

            )

        result = st.session_state.get(

            "multifactor_result"

        )

        if result is None:

            st.info(

                "Execute a multi-factor scenario."

            )

            return

        if hasattr(result, "to_dict"):

            result = result.to_dict()

        metrics = st.columns(5)

        metrics[0].metric(

            "Portfolio Before",

            f"${result['portfolio_before']:,.2f}",

        )

        metrics[1].metric(

            "Portfolio After",

            f"${result['portfolio_after']:,.2f}",

        )

        metrics[2].metric(

            "PnL",

            f"${result['pnl']:,.2f}",

        )

        metrics[3].metric(

            "PnL %",

            f"{result['pnl_pct']:.2%}",

        )

        metrics[4].metric(

            "Survivability",

            f"{result['survivability_score']:.1f}",

        )

        st.divider()

        tabs = st.tabs(

            [

                "Scenario Result",

                "Institutional Ranking",

                "Composite Score",

                "Scenario Metadata",

            ]

        )

        # --------------------------------------------------------------

        with tabs[0]:

            st.subheader(

                "Multi-Factor Result"

            )

            st.json(

                result

            )

        # --------------------------------------------------------------

        with tabs[1]:

            st.subheader(

                "Institutional Crisis Ranking"

            )

            ranking = pd.DataFrame(

                self.engine.crisis_ranking()

            )

            st.dataframe(

                ranking,

                use_container_width=True,

                hide_index=True,

            )

        # --------------------------------------------------------------

        with tabs[2]:

            st.subheader(

                "Institutional Composite Score"

            )

            score = self.engine.institutional_score()

            traffic = self.engine.traffic_light()

            rating = self.engine.executive_rating()

            c1, c2, c3 = st.columns(3)

            c1.metric(

                "Composite Score",

                score,

            )

            c2.metric(

                "Traffic",

                traffic["status"],

            )

            c3.metric(

                "Rating",

                rating["rating"],

            )

            st.json(

                self.engine.institutional_summary()

            )

        # --------------------------------------------------------------

        with tabs[3]:

            st.subheader(

                "Scenario Metadata"

            )

            metadata = result.get(

                "metadata",

                {},

            )

            metadata_df = pd.DataFrame(

                [

                    {

                        "Scenario": k,

                        "Configuration": str(v),

                    }

                    for k, v in metadata.items()

                ]

            )

            st.dataframe(

                metadata_df,

                use_container_width=True,

                hide_index=True,

            )

        st.divider()

        st.subheader(

            "Institutional Dashboard"

        )

        st.json(

            self.engine.dashboard_packet()

        )

        export = pd.DataFrame(

            self.engine.crisis_ranking()

        )

        st.download_button(

            "Download Multi-Factor Results",

            data=export.to_csv(

                index=False,

            ).encode(

                "utf-8",

            ),

            file_name="forex_multifactor_stress.csv",

            mime="text/csv",

            use_container_width=True,

        )
# =============================================================================
# File: modules/forex/risk/forex_stress_testing_dashboard.py
#
# Sprint 30
# Phase 4C-3-3-2-4
#
# Build 2.1
#
# Continue Immediately After Build 1.4
#
# Runtime History Workspace
# =============================================================================

    # ------------------------------------------------------------------
    # Runtime History
    # ------------------------------------------------------------------

    def render_runtime(self):

        st.subheader("Stress Testing Runtime History")

        history = self.engine.history()

        if not history:

            st.info(

                "No stress history has been recorded."

            )

            return

        runtime = self.engine.runtime_statistics()

        metrics = st.columns(5)

        metrics[0].metric(

            "Executions",

            runtime.get(

                "executions",

                0,

            ),

        )

        metrics[1].metric(

            "Average PnL",

            f"${runtime.get('average_pnl',0):,.2f}",

        )

        metrics[2].metric(

            "Worst PnL",

            f"${runtime.get('worst_pnl',0):,.2f}",

        )

        metrics[3].metric(

            "Best PnL",

            f"${runtime.get('best_pnl',0):,.2f}",

        )

        metrics[4].metric(

            "Average Survivability",

            f"{runtime.get('average_survivability',0):.1f}",

        )

        st.divider()

        tabs = st.tabs(

            [

                "Execution History",

                "Performance Trend",

                "Runtime Statistics",

                "Database Records",

            ]

        )

        # --------------------------------------------------------------

        with tabs[0]:

            st.subheader(

                "Stress Execution History"

            )

            history_df = pd.DataFrame(

                history

            )

            st.dataframe(

                history_df,

                use_container_width=True,

                hide_index=True,

            )

        # --------------------------------------------------------------

        with tabs[1]:

            st.subheader(

                "Historical Trend"

            )

            trend = pd.DataFrame(

                self.engine.history_trend()

            )

            if not trend.empty:

                chart = trend.copy()

                chart["Execution"] = range(

                    1,

                    len(chart) + 1,

                )

                st.line_chart(

                    chart.set_index(

                        "Execution"

                    )[

                        [

                            "pnl_pct",

                            "survivability",

                        ]

                    ]

                )

                st.dataframe(

                    trend,

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.info(

                    "Trend data unavailable."

                )

        # --------------------------------------------------------------

        with tabs[2]:

            st.subheader(

                "Runtime Analytics"

            )

            runtime_df = pd.DataFrame(

                [

                    {

                        "Metric": k,

                        "Value": v,

                    }

                    for k, v in

                    runtime.items()

                ]

            )

            st.dataframe(

                runtime_df,

                use_container_width=True,

                hide_index=True,

            )

        # --------------------------------------------------------------

        with tabs[3]:

            st.subheader(

                "Database Records"

            )

            db_df = pd.DataFrame(

                history

            )

            st.dataframe(

                db_df,

                use_container_width=True,

                hide_index=True,

            )

        st.divider()

        st.subheader(

            "Runtime Health"

        )

        st.json(

            self.engine.status()

        )

        st.divider()

        export = pd.DataFrame(

            history

        )

        st.download_button(

            "Download Runtime History",

            data=export.to_csv(

                index=False,

            ).encode(

                "utf-8",

            ),

            file_name="forex_stress_runtime_history.csv",

            mime="text/csv",

            use_container_width=True,

        )