"""
ui/admin/autonomous_forecast_optimizer_dashboard.py
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.autonomous_forecast_optimizer import (
    AutonomousForecastOptimizer,
)

from modules.analytics.analytics_fabric_forecasting_engine import (
    AnalyticsFabricForecastingEngine,
)

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
)


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _get_persistence_engine(engine=None):
    if engine is not None:
        return engine

    if "analytics_history_engine" not in st.session_state:
        st.session_state[
            "analytics_history_engine"
        ] = AnalyticsFabricPersistenceEngine()

    return st.session_state[
        "analytics_history_engine"
    ]


def _get_forecasting_engine(
    persistence_engine,
    forecasting_engine=None,
):
    if forecasting_engine is not None:
        return forecasting_engine

    if "analytics_forecasting_engine" not in st.session_state:
        st.session_state[
            "analytics_forecasting_engine"
        ] = AnalyticsFabricForecastingEngine(
            persistence_engine=persistence_engine
        )

    return st.session_state[
        "analytics_forecasting_engine"
    ]


def _get_optimizer(
    forecasting_engine,
    persistence_engine,
    optimizer=None,
):
    if optimizer is not None:
        return optimizer

    if "autonomous_forecast_optimizer" not in st.session_state:
        st.session_state[
            "autonomous_forecast_optimizer"
        ] = AutonomousForecastOptimizer(
            forecasting_engine=forecasting_engine,
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "autonomous_forecast_optimizer"
    ]


def _render_plan(
    title: str,
    plan: Dict[str, Any],
):
    st.subheader(title)

    if not plan:
        st.info("No data.")
        return

    st.json(plan)

    try:
        df = pd.DataFrame(
            [
                {
                    "Field": k,
                    "Value": str(v),
                }
                for k, v in plan.items()
            ]
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )
    except Exception:
        pass


def _render_recommendations(
    recommendations,
):
    if not recommendations:
        st.info(
            "No recommendations available."
        )
        return

    df = pd.DataFrame(
        recommendations
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def _build_readiness(
    report,
):
    return {
        "capacity_ready": True,
        "provider_ready": True,
        "governance_ready": True,
        "tenant_ready": True,
        "universe_ready": True,
        "overall_ready": (
            report.overall_score >= 70
        ),
    }


def render_autonomous_forecast_optimizer_dashboard(
    persistence_engine=None,
    forecasting_engine=None,
    optimizer=None,
):
    st.title(
        "Autonomous Forecast Optimizer"
    )

    persistence_engine = (
        _get_persistence_engine(
            persistence_engine
        )
    )

    forecasting_engine = (
        _get_forecasting_engine(
            persistence_engine,
            forecasting_engine,
        )
    )

    optimizer = _get_optimizer(
        forecasting_engine,
        persistence_engine,
        optimizer,
    )

    report = (
        optimizer.generate_optimization_report()
    )

    readiness = (
        _build_readiness(report)
    )

    recommendations = (
        report.recommendations
    )

    cols = st.columns(8)

    cols[0].metric(
        "Optimization Score",
        report.overall_score,
    )

    cols[1].metric(
        "Recommendations",
        len(recommendations),
    )

    cols[2].metric(
        "Capacity Gain",
        round(
            report.capacity_plan.get(
                "recommended_capacity",
                0,
            ),
            2,
        ),
    )

    cols[3].metric(
        "Queue Reduction",
        round(
            report.queue_plan.get(
                "target_queue",
                0,
            ),
            2,
        ),
    )

    cols[4].metric(
        "Risk Reduction",
        round(
            report.governance_plan.get(
                "target_risk",
                0,
            ),
            2,
        ),
    )

    cols[5].metric(
        "Tenant Growth",
        round(
            report.tenant_plan.get(
                "target_tenants",
                0,
            ),
            2,
        ),
    )

    cols[6].metric(
        "Universe Growth",
        round(
            report.universe_plan.get(
                "target_universes",
                0,
            ),
            2,
        ),
    )

    cols[7].metric(
        "Execution Ready",
        "YES"
        if readiness[
            "overall_ready"
        ]
        else "NO",
    )

    tabs = st.tabs(
        [
            "Executive Optimization",
            "Capacity Optimization",
            "Provider Optimization",
            "Queue Optimization",
            "Governance Optimization",
            "Tenant Expansion",
            "Universe Expansion",
            "Fabric Health Optimization",
            "Recommendations",
            "Optimization History",
            "Execution Readiness",
            "Exports",
        ]
    )

    with tabs[0]:

        st.subheader(
            "Executive Optimization Summary"
        )

        st.json(
            report.as_dict()
        )

    with tabs[1]:

        _render_plan(
            "Capacity Optimization Plan",
            report.capacity_plan,
        )

        chart_df = pd.DataFrame(
            {
                "Metric": [
                    "Current",
                    "Projected",
                    "Recommended",
                ],
                "Value": [
                    report.capacity_plan.get(
                        "current_capacity",
                        0,
                    ),
                    report.capacity_plan.get(
                        "projected_capacity",
                        0,
                    ),
                    report.capacity_plan.get(
                        "recommended_capacity",
                        0,
                    ),
                ],
            }
        )

        st.bar_chart(
            chart_df.set_index(
                "Metric"
            )
        )

    with tabs[2]:

        _render_plan(
            "Provider Optimization Plan",
            report.provider_plan,
        )

    with tabs[3]:

        _render_plan(
            "Queue Optimization Plan",
            report.queue_plan,
        )

    with tabs[4]:

        _render_plan(
            "Governance Optimization Plan",
            report.governance_plan,
        )

    with tabs[5]:

        _render_plan(
            "Tenant Expansion Plan",
            report.tenant_plan,
        )

    with tabs[6]:

        _render_plan(
            "Universe Expansion Plan",
            report.universe_plan,
        )

    with tabs[7]:

        _render_plan(
            "Fabric Health Plan",
            report.health_plan,
        )

    with tabs[8]:

        st.subheader(
            "Recommendation Center"
        )

        _render_recommendations(
            recommendations
        )

    with tabs[9]:

        st.subheader(
            "Optimization History"
        )

        history = (
            persistence_engine
            .get_executive_history()
        )

        if history:
            st.dataframe(
                pd.DataFrame(history),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No optimization history available."
            )

    with tabs[10]:

        st.subheader(
            "Execution Readiness"
        )

        st.json(readiness)

        readiness_df = pd.DataFrame(
            [
                {
                    "Domain": k,
                    "Ready": v,
                }
                for k, v in readiness.items()
            ]
        )

        st.dataframe(
            readiness_df,
            use_container_width=True,
            hide_index=True,
        )

    with tabs[11]:

        st.subheader(
            "Optimization Actions"
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "Generate Optimization Report",
                use_container_width=True,
            ):
                st.success(
                    "Optimization report generated."
                )

            if st.button(
                "Save Optimization Report",
                use_container_width=True,
            ):
                optimizer.save_optimization_report()
                st.success(
                    "Optimization report saved."
                )

            if st.button(
                "Save Capacity Optimization",
                use_container_width=True,
            ):
                optimizer.save_capacity_optimization()
                st.success(
                    "Capacity optimization saved."
                )

        with col2:

            if st.button(
                "Save Provider Optimization",
                use_container_width=True,
            ):
                optimizer.save_provider_optimization()
                st.success(
                    "Provider optimization saved."
                )

            if st.button(
                "Save Governance Optimization",
                use_container_width=True,
            ):
                optimizer.save_governance_optimization()
                st.success(
                    "Governance optimization saved."
                )

            if st.button(
                "Refresh Optimizations",
                use_container_width=True,
            ):
                st.rerun()

        st.divider()

        export_payload = (
            report.as_dict()
        )

        st.download_button(
            "Export Optimization Report JSON",
            data=json.dumps(
                export_payload,
                indent=2,
                default=str,
            ),
            file_name=(
                f"optimization_report_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        st.download_button(
            "Export Executive Optimization Package",
            data=json.dumps(
                export_payload,
                indent=2,
                default=str,
            ),
            file_name=(
                f"executive_optimization_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        st.download_button(
            "Export Readiness Assessment",
            data=json.dumps(
                readiness,
                indent=2,
                default=str,
            ),
            file_name=(
                f"readiness_assessment_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )


def render_optimizer_dashboard(
    persistence_engine=None,
    forecasting_engine=None,
    optimizer=None,
):
    render_autonomous_forecast_optimizer_dashboard(
        persistence_engine=persistence_engine,
        forecasting_engine=forecasting_engine,
        optimizer=optimizer,
    )