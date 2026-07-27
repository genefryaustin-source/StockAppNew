"""
ui/admin/analytics_fabric_forecasting_dashboard.py
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

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
        return {
            "error": str(exc)
        } if default is None else default


def _get_persistence_engine(
    persistence_engine=None,
):
    if persistence_engine is not None:
        return persistence_engine

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
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "analytics_forecasting_engine"
    ]


def _forecast_df(
    forecast: Dict[str, Any],
) -> pd.DataFrame:
    rows = []

    for key, value in forecast.items():
        rows.append(
            {
                "Metric": key,
                "Value": value,
            }
        )

    return pd.DataFrame(rows)


def _render_forecast(
    title: str,
    forecast: Dict[str, Any],
):
    st.subheader(title)

    cols = st.columns(6)

    cols[0].metric(
        "Current",
        round(
            forecast.get(
                "current_value",
                0,
            ),
            4,
        ),
    )

    cols[1].metric(
        "7 Days",
        round(
            forecast.get(
                "next_7_days",
                0,
            ),
            4,
        ),
    )

    cols[2].metric(
        "30 Days",
        round(
            forecast.get(
                "next_30_days",
                0,
            ),
            4,
        ),
    )

    cols[3].metric(
        "90 Days",
        round(
            forecast.get(
                "next_90_days",
                0,
            ),
            4,
        ),
    )

    cols[4].metric(
        "365 Days",
        round(
            forecast.get(
                "next_365_days",
                0,
            ),
            4,
        ),
    )

    cols[5].metric(
        "Confidence %",
        round(
            forecast.get(
                "confidence_score",
                0,
            ),
            2,
        ),
    )

    chart_df = pd.DataFrame(
        [
            (
                "Current",
                forecast.get(
                    "current_value",
                    0,
                ),
            ),
            (
                "7 Days",
                forecast.get(
                    "next_7_days",
                    0,
                ),
            ),
            (
                "30 Days",
                forecast.get(
                    "next_30_days",
                    0,
                ),
            ),
            (
                "90 Days",
                forecast.get(
                    "next_90_days",
                    0,
                ),
            ),
            (
                "365 Days",
                forecast.get(
                    "next_365_days",
                    0,
                ),
            ),
        ],
        columns=[
            "Period",
            "Value",
        ],
    )

    st.line_chart(
        chart_df.set_index(
            "Period"
        )
    )

    st.dataframe(
        _forecast_df(forecast),
        use_container_width=True,
        hide_index=True,
    )


def render_analytics_fabric_forecasting_dashboard(
    persistence_engine=None,
    forecasting_engine=None,
):
    st.title(
        "Analytics Fabric Forecasting Dashboard"
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

    report = (
        forecasting_engine
        .generate_forecast_report()
    )

    tabs = st.tabs(
        [
            "Executive Forecast",
            "Capacity Forecast",
            "Provider Spend Forecast",
            "Queue Forecast",
            "Worker Forecast",
            "Governance Forecast",
            "Tenant Forecast",
            "Universe Forecast",
            "Fabric Health Forecast",
            "Optimization Forecast",
            "Forecast History",
            "Forecast Exports",
        ]
    )

    with tabs[0]:

        st.subheader(
            "Executive Forecast Overview"
        )

        forecasts = {
            "Capacity":
                report.capacity_forecast,
            "Provider":
                report.provider_spend_forecast,
            "Queue":
                report.queue_growth_forecast,
            "Workers":
                report.worker_growth_forecast,
            "Governance":
                report.governance_risk_forecast,
            "Tenants":
                report.tenant_growth_forecast,
            "Universes":
                report.universe_growth_forecast,
            "Health":
                report.fabric_health_forecast,
            "Optimization":
                report.optimization_savings_forecast,
        }

        highest_growth = max(
            forecasts.items(),
            key=lambda x:
            x[1].get(
                "growth_rate",
                0,
            ),
        )

        lowest_confidence = min(
            forecasts.items(),
            key=lambda x:
            x[1].get(
                "confidence_score",
                0,
            ),
        )

        cols = st.columns(6)

        cols[0].metric(
            "Forecast Domains",
            len(forecasts),
        )

        cols[1].metric(
            "Highest Growth",
            highest_growth[0],
        )

        cols[2].metric(
            "Growth Rate",
            round(
                highest_growth[1].get(
                    "growth_rate",
                    0,
                ),
                4,
            ),
        )

        cols[3].metric(
            "Lowest Confidence",
            lowest_confidence[0],
        )

        cols[4].metric(
            "Confidence",
            round(
                lowest_confidence[1].get(
                    "confidence_score",
                    0,
                ),
                2,
            ),
        )

        cols[5].metric(
            "Report",
            report.report_id[-8:],
        )

        st.json(
            report.as_dict()
        )

    with tabs[1]:
        _render_forecast(
            "Capacity Forecast",
            report.capacity_forecast,
        )

    with tabs[2]:
        _render_forecast(
            "Provider Spend Forecast",
            report.provider_spend_forecast,
        )

    with tabs[3]:
        _render_forecast(
            "Queue Growth Forecast",
            report.queue_growth_forecast,
        )

    with tabs[4]:
        _render_forecast(
            "Worker Growth Forecast",
            report.worker_growth_forecast,
        )

    with tabs[5]:
        _render_forecast(
            "Governance Risk Forecast",
            report.governance_risk_forecast,
        )

    with tabs[6]:
        _render_forecast(
            "Tenant Growth Forecast",
            report.tenant_growth_forecast,
        )

    with tabs[7]:
        _render_forecast(
            "Universe Growth Forecast",
            report.universe_growth_forecast,
        )

    with tabs[8]:
        _render_forecast(
            "Fabric Health Forecast",
            report.fabric_health_forecast,
        )

    with tabs[9]:
        _render_forecast(
            "Optimization Savings Forecast",
            report.optimization_savings_forecast,
        )

    with tabs[10]:

        st.subheader(
            "Forecast History"
        )

        executive_history = (
            persistence_engine
            .get_executive_history()
        )

        if executive_history:

            df = pd.DataFrame(
                executive_history
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No forecast history available."
            )

    with tabs[11]:

        st.subheader(
            "Forecast Actions"
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "Generate Forecast Report",
                use_container_width=True,
            ):
                st.success(
                    "Forecast generated."
                )

            if st.button(
                "Save Forecast Report",
                use_container_width=True,
            ):
                forecasting_engine.save_forecast_report()
                st.success(
                    "Forecast report saved."
                )

            if st.button(
                "Save Capacity Forecast",
                use_container_width=True,
            ):
                forecasting_engine.save_capacity_forecast()
                st.success(
                    "Capacity forecast saved."
                )

        with col2:

            if st.button(
                "Save Provider Forecast",
                use_container_width=True,
            ):
                forecasting_engine.save_provider_forecast()
                st.success(
                    "Provider forecast saved."
                )

            if st.button(
                "Save Health Forecast",
                use_container_width=True,
            ):
                forecasting_engine.save_health_forecast()
                st.success(
                    "Health forecast saved."
                )

            if st.button(
                "Refresh Forecasts",
                use_container_width=True,
            ):
                st.rerun()

        st.divider()

        export_payload = (
            report.as_dict()
        )

        st.download_button(
            "Export Forecast JSON",
            data=json.dumps(
                export_payload,
                indent=2,
                default=str,
            ),
            file_name=(
                f"forecast_report_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        st.download_button(
            "Export Executive Forecast Package",
            data=json.dumps(
                export_payload,
                indent=2,
                default=str,
            ),
            file_name=(
                f"executive_forecast_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        st.json(
            {
                "Highest Growth Domain":
                    max(
                        [
                            (
                                k,
                                v.get(
                                    "growth_rate",
                                    0,
                                ),
                            )
                            for k, v in {
                                "capacity":
                                report.capacity_forecast,
                                "provider":
                                report.provider_spend_forecast,
                                "queue":
                                report.queue_growth_forecast,
                                "workers":
                                report.worker_growth_forecast,
                                "governance":
                                report.governance_risk_forecast,
                                "tenants":
                                report.tenant_growth_forecast,
                                "universes":
                                report.universe_growth_forecast,
                                "health":
                                report.fabric_health_forecast,
                                "optimization":
                                report.optimization_savings_forecast,
                            }.items()
                        ],
                        key=lambda x: x[1],
                    ),
                "Capacity Warning Threshold":
                    0.80,
                "Provider Spend Warning Threshold":
                    0.90,
                "Governance Risk Threshold":
                    0.75,
            }
        )


def render_analytics_forecasting_dashboard(
    persistence_engine=None,
    forecasting_engine=None,
):
    render_analytics_fabric_forecasting_dashboard(
        persistence_engine=persistence_engine,
        forecasting_engine=forecasting_engine,
    )