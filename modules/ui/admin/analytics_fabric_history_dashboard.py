"""
ui/admin/analytics_fabric_history_dashboard.py
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
)


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {
            "error": str(exc),
        } if default is None else default


def _history_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    normalized = []

    for row in rows:
        cleaned = {}

        for key, value in row.items():
            if isinstance(value, (dict, list)):
                cleaned[key] = json.dumps(value, default=str)
            else:
                cleaned[key] = value

        normalized.append(cleaned)

    return pd.DataFrame(normalized)


def _render_table(title: str, rows: List[Dict[str, Any]]) -> None:
    st.subheader(title)

    if not rows:
        st.info("No records available.")
        return

    st.dataframe(
        _history_df(rows),
        use_container_width=True,
        hide_index=True,
    )


def _render_metric_cards(metrics: Dict[str, Any]) -> None:
    if not metrics:
        return

    cols = st.columns(min(len(metrics), 6))

    for col, (key, value) in zip(cols, metrics.items()):
        if isinstance(value, float):
            value = round(value, 4)

        col.metric(
            key.replace("_", " ").title(),
            value,
        )


def _download_json(
    label: str,
    payload: Any,
):
    st.download_button(
        f"Export {label} JSON",
        data=json.dumps(
            payload,
            indent=2,
            default=str,
        ),
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )


def _download_csv(
    label: str,
    rows: List[Dict[str, Any]],
):
    if not rows:
        return

    csv_data = _history_df(rows).to_csv(
        index=False
    )

    st.download_button(
        f"Export {label} CSV",
        data=csv_data,
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _get_engine(
    persistence_engine: Optional[
        AnalyticsFabricPersistenceEngine
    ] = None,
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


def render_analytics_fabric_history_dashboard(
    persistence_engine: Optional[
        AnalyticsFabricPersistenceEngine
    ] = None,
):
    st.title(
        "Analytics Fabric History Dashboard"
    )

    engine = _get_engine(
        persistence_engine
    )

    summary = _safe_call(
        engine.summary,
        {},
    )

    st.subheader(
        "Historical Analytics Overview"
    )

    _render_metric_cards(
        {
            "validation_records": summary.get(
                "validation_records",
                0,
            ),
            "stress_records": summary.get(
                "stress_records",
                0,
            ),
            "benchmark_records": summary.get(
                "benchmark_records",
                0,
            ),
            "provider_records": summary.get(
                "provider_records",
                0,
            ),
            "governance_records": summary.get(
                "governance_records",
                0,
            ),
            "health_records": summary.get(
                "health_records",
                0,
            ),
        }
    )

    tabs = st.tabs(
        [
            "Validation History",
            "Stress History",
            "Benchmark History",
            "Capacity Forecast History",
            "Provider History",
            "Governance History",
            "Planning History",
            "Tenant Intelligence History",
            "Control Tower History",
            "Executive History",
            "Fabric Health History",
            "Trend Analysis",
            "Exports",
        ]
    )

    with tabs[0]:
        rows = engine.get_validation_history()

        _render_table(
            "Validation History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_validation_trends()
        )

        _download_json(
            "Validation History",
            rows,
        )

        _download_csv(
            "Validation History",
            rows,
        )

    with tabs[1]:
        rows = engine.get_stress_history()

        _render_table(
            "Stress History",
            rows,
        )

        _download_json(
            "Stress History",
            rows,
        )

        _download_csv(
            "Stress History",
            rows,
        )

    with tabs[2]:
        rows = engine.get_benchmark_history()

        _render_table(
            "Benchmark History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_performance_trends()
        )

        _download_json(
            "Benchmark History",
            rows,
        )

        _download_csv(
            "Benchmark History",
            rows,
        )

    with tabs[3]:
        rows = engine.get_capacity_history()

        _render_table(
            "Capacity Forecast History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_capacity_trends()
        )

        _download_json(
            "Capacity Forecast History",
            rows,
        )

        _download_csv(
            "Capacity Forecast History",
            rows,
        )

    with tabs[4]:
        rows = engine.get_provider_history()

        _render_table(
            "Provider History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_provider_cost_trends()
        )

        _download_json(
            "Provider History",
            rows,
        )

        _download_csv(
            "Provider History",
            rows,
        )

    with tabs[5]:
        rows = engine.get_governance_history()

        _render_table(
            "Governance History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_governance_trends()
        )

        _download_json(
            "Governance History",
            rows,
        )

        _download_csv(
            "Governance History",
            rows,
        )

    with tabs[6]:
        rows = engine.get_global_plan_history()

        _render_table(
            "Planning History",
            rows,
        )

        _download_json(
            "Planning History",
            rows,
        )

        _download_csv(
            "Planning History",
            rows,
        )

    with tabs[7]:
        rows = engine.get_tenant_intelligence_history()

        _render_table(
            "Tenant Intelligence History",
            rows,
        )

        _download_json(
            "Tenant Intelligence History",
            rows,
        )

        _download_csv(
            "Tenant Intelligence History",
            rows,
        )

    with tabs[8]:
        rows = engine.get_control_tower_history()

        _render_table(
            "Control Tower History",
            rows,
        )

        _download_json(
            "Control Tower History",
            rows,
        )

        _download_csv(
            "Control Tower History",
            rows,
        )

    with tabs[9]:
        rows = engine.get_executive_history()

        _render_table(
            "Executive History",
            rows,
        )

        _download_json(
            "Executive History",
            rows,
        )

        _download_csv(
            "Executive History",
            rows,
        )

    with tabs[10]:
        rows = engine.get_fabric_health_history()

        _render_table(
            "Fabric Health History",
            rows,
        )

        _render_metric_cards(
            engine.calculate_health_trends()
        )

        _download_json(
            "Fabric Health History",
            rows,
        )

        _download_csv(
            "Fabric Health History",
            rows,
        )

    with tabs[11]:
        st.subheader(
            "Historical Trend Analysis"
        )

        validation_trends = (
            engine.calculate_validation_trends()
        )

        performance_trends = (
            engine.calculate_performance_trends()
        )

        capacity_trends = (
            engine.calculate_capacity_trends()
        )

        provider_trends = (
            engine.calculate_provider_cost_trends()
        )

        governance_trends = (
            engine.calculate_governance_trends()
        )

        health_trends = (
            engine.calculate_health_trends()
        )

        trend_rows = []

        for group_name, trend_data in [
            (
                "Validation",
                validation_trends,
            ),
            (
                "Performance",
                performance_trends,
            ),
            (
                "Capacity",
                capacity_trends,
            ),
            (
                "Providers",
                provider_trends,
            ),
            (
                "Governance",
                governance_trends,
            ),
            (
                "Health",
                health_trends,
            ),
        ]:
            for metric, value in trend_data.items():
                trend_rows.append(
                    {
                        "Category": group_name,
                        "Metric": metric,
                        "Value": value,
                    }
                )

        if trend_rows:
            st.dataframe(
                pd.DataFrame(trend_rows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No trend information available."
            )

    with tabs[12]:
        st.subheader(
            "Export Historical Analytics"
        )

        export_payload = {
            "summary": summary,
            "validation": engine.get_validation_history(),
            "stress": engine.get_stress_history(),
            "benchmark": engine.get_benchmark_history(),
            "capacity": engine.get_capacity_history(),
            "providers": engine.get_provider_history(),
            "governance": engine.get_governance_history(),
            "plans": engine.get_global_plan_history(),
            "tenant_intelligence": (
                engine.get_tenant_intelligence_history()
            ),
            "control_tower": (
                engine.get_control_tower_history()
            ),
            "executive": (
                engine.get_executive_history()
            ),
            "health": (
                engine.get_fabric_health_history()
            ),
        }

        st.download_button(
            "Export Complete History JSON",
            data=json.dumps(
                export_payload,
                indent=2,
                default=str,
            ),
            file_name=(
                f"analytics_fabric_history_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        if st.button(
            "Export Excel Workbook",
            use_container_width=True,
        ):
            output_file = (
                "analytics_fabric_history.xlsx"
            )

            engine.export_history_excel(
                output_file
            )

            st.success(
                f"Workbook exported: {output_file}"
            )

        st.json(summary)


def render_analytics_history_dashboard(
    persistence_engine: Optional[
        AnalyticsFabricPersistenceEngine
    ] = None,
):
    render_analytics_fabric_history_dashboard(
        persistence_engine
    )