"""
ui/admin/analytics_fabric_self_diagnostic_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_self_diagnostic_engine import (
    AnalyticsFabricSelfDiagnosticEngine,
)

from modules.analytics.analytics_fabric_control_plane import (
    AnalyticsFabricControlPlane,
)

from modules.analytics.analytics_fabric_command_processor import (
    AnalyticsFabricCommandProcessor,
)

from modules.analytics.analytics_fabric_continuous_runtime_engine import (
    AnalyticsFabricContinuousRuntimeEngine,
)

from modules.analytics.analytics_fabric_autonomous_supervisor import (
    AnalyticsFabricAutonomousSupervisor,
)

from modules.analytics.analytics_fabric_runtime_controller import (
    AnalyticsFabricRuntimeController,
)

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
)

from modules.analytics.analytics_fabric_snapshot_scheduler import (
    AnalyticsFabricSnapshotScheduler,
)


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "as_dict"):
        return value.as_dict()

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    return {"value": str(value)}


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _records_table(records: Any) -> None:
    if not records:
        st.info("No records available.")
        return

    if isinstance(records, dict):
        records = [records]

    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
    )


def _download_json(label: str, payload: Any) -> None:
    st.download_button(
        label,
        data=json.dumps(payload, indent=2, default=str),
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )


def _component_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []

    for component in report.get("component_reports", []):
        rows.append(
            {
                "Component": component.get("component"),
                "Health": component.get("health_score"),
                "Risk": component.get("risk_score"),
                "State": component.get("state"),
                "Findings": len(component.get("findings", [])),
                "Object Type": component.get("metrics", {}).get("object_type"),
                "Registered": component.get("metrics", {}).get("registered"),
            }
        )

    return rows


def _finding_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []

    for component in report.get("component_reports", []):
        component_name = component.get("component")

        for finding in component.get("findings", []):
            rows.append(
                {
                    "Component": component_name,
                    "Severity": finding.get("severity"),
                    "Title": finding.get("title"),
                    "Description": finding.get("description"),
                    "Recommendation": finding.get("recommendation"),
                    "Created At": finding.get("created_at"),
                }
            )

    return rows


def _history_rows(engine: AnalyticsFabricSelfDiagnosticEngine) -> List[Dict[str, Any]]:
    rows = []

    for report in engine.diagnostic_history:
        data = report.as_dict()

        rows.append(
            {
                "Generated At": data.get("generated_at"),
                "Report ID": data.get("report_id"),
                "Health": data.get("overall_health_score"),
                "Risk": data.get("overall_risk_score"),
                "State": data.get("state"),
                "Components": len(data.get("component_reports", [])),
                "Anomalies": len(data.get("anomalies", [])),
                "Predicted Failures": len(data.get("predicted_failures", [])),
                "Recommendations": len(data.get("recommendations", [])),
            }
        )

    return rows


def _get_persistence_engine(persistence_engine=None):
    if persistence_engine is not None:
        return persistence_engine

    if "analytics_history_engine" not in st.session_state:
        st.session_state["analytics_history_engine"] = AnalyticsFabricPersistenceEngine()

    return st.session_state["analytics_history_engine"]


def _get_runtime_controller(
    analytics_fabric=None,
    persistence_engine=None,
    runtime_controller=None,
):
    if runtime_controller is not None:
        return runtime_controller

    if "analytics_fabric_runtime_controller" not in st.session_state:
        st.session_state["analytics_fabric_runtime_controller"] = AnalyticsFabricRuntimeController(
            forecasting_engine=getattr(analytics_fabric, "forecasting_engine", None),
            optimizer=getattr(analytics_fabric, "optimizer", None),
            planner=getattr(analytics_fabric, "execution_planner", None),
            orchestrator=getattr(analytics_fabric, "execution_orchestrator", None),
            governor=getattr(analytics_fabric, "execution_governor", None),
            global_planner=getattr(analytics_fabric, "global_planner", None),
            worker_capacity_model=getattr(analytics_fabric, "worker_capacity_model", None),
            provider_cost_intelligence=getattr(analytics_fabric, "provider_cost_intelligence", None),
            persistence_engine=persistence_engine,
        )

    controller = st.session_state["analytics_fabric_runtime_controller"]
    controller.forecasting_engine = getattr(analytics_fabric, "forecasting_engine", None)
    controller.optimizer = getattr(analytics_fabric, "optimizer", None)
    controller.planner = getattr(analytics_fabric, "execution_planner", None)
    controller.orchestrator = getattr(analytics_fabric, "execution_orchestrator", None)
    controller.governor = getattr(analytics_fabric, "execution_governor", None)
    controller.global_planner = getattr(analytics_fabric, "global_planner", None)
    controller.worker_capacity_model = getattr(analytics_fabric, "worker_capacity_model", None)
    controller.provider_cost_intelligence = getattr(analytics_fabric, "provider_cost_intelligence", None)
    controller.persistence_engine = persistence_engine

    return controller


def _get_snapshot_scheduler(
    persistence_engine,
    analytics_fabric=None,
    snapshot_scheduler=None,
):
    if snapshot_scheduler is not None:
        return snapshot_scheduler

    if "analytics_snapshot_scheduler" not in st.session_state:
        st.session_state["analytics_snapshot_scheduler"] = AnalyticsFabricSnapshotScheduler(
            persistence_engine=persistence_engine,
            analytics_fabric=analytics_fabric,
        )

    scheduler = st.session_state["analytics_snapshot_scheduler"]
    scheduler.persistence_engine = persistence_engine
    scheduler.analytics_fabric = analytics_fabric

    return scheduler


def _get_supervisor(
    runtime_controller,
    persistence_engine,
    snapshot_scheduler,
    analytics_fabric=None,
    supervisor=None,
):
    if supervisor is not None:
        return supervisor

    if "analytics_fabric_autonomous_supervisor" not in st.session_state:
        st.session_state["analytics_fabric_autonomous_supervisor"] = AnalyticsFabricAutonomousSupervisor(
            runtime_controller=runtime_controller,
            execution_governor=getattr(analytics_fabric, "execution_governor", None),
            persistence_engine=persistence_engine,
            snapshot_scheduler=snapshot_scheduler,
        )

    supervisor_obj = st.session_state["analytics_fabric_autonomous_supervisor"]
    supervisor_obj.runtime_controller = runtime_controller
    supervisor_obj.execution_governor = getattr(analytics_fabric, "execution_governor", None)
    supervisor_obj.persistence_engine = persistence_engine
    supervisor_obj.snapshot_scheduler = snapshot_scheduler

    return supervisor_obj


def _get_continuous_runtime(
    supervisor,
    runtime_controller,
    snapshot_scheduler,
    persistence_engine,
    continuous_runtime=None,
):
    if continuous_runtime is not None:
        return continuous_runtime

    if "analytics_fabric_continuous_runtime_engine" not in st.session_state:
        st.session_state["analytics_fabric_continuous_runtime_engine"] = AnalyticsFabricContinuousRuntimeEngine(
            supervisor=supervisor,
            runtime_controller=runtime_controller,
            snapshot_scheduler=snapshot_scheduler,
            persistence_engine=persistence_engine,
        )

    engine = st.session_state["analytics_fabric_continuous_runtime_engine"]
    engine.supervisor = supervisor
    engine.runtime_controller = runtime_controller
    engine.snapshot_scheduler = snapshot_scheduler
    engine.persistence_engine = persistence_engine

    return engine


def _get_command_processor(
    continuous_runtime,
    supervisor,
    runtime_controller,
    persistence_engine,
    analytics_fabric=None,
    command_processor=None,
):
    if command_processor is not None:
        return command_processor

    if "analytics_command_processor" not in st.session_state:
        st.session_state["analytics_command_processor"] = AnalyticsFabricCommandProcessor(
            continuous_runtime_engine=continuous_runtime,
            supervisor=supervisor,
            runtime_controller=runtime_controller,
            orchestrator=getattr(analytics_fabric, "execution_orchestrator", None),
            persistence_engine=persistence_engine,
        )

    processor = st.session_state["analytics_command_processor"]
    processor.continuous_runtime_engine = continuous_runtime
    processor.supervisor = supervisor
    processor.runtime_controller = runtime_controller
    processor.orchestrator = getattr(analytics_fabric, "execution_orchestrator", None)
    processor.persistence_engine = persistence_engine

    return processor


def _get_control_plane(
    command_processor,
    continuous_runtime,
    supervisor,
    runtime_controller,
    persistence_engine,
    snapshot_scheduler,
    analytics_fabric=None,
    control_plane=None,
):
    if control_plane is not None:
        return control_plane

    if "analytics_fabric_control_plane" not in st.session_state:
        st.session_state["analytics_fabric_control_plane"] = AnalyticsFabricControlPlane(
            command_processor=command_processor,
            continuous_runtime_engine=continuous_runtime,
            autonomous_supervisor=supervisor,
            runtime_controller=runtime_controller,
            execution_orchestrator=getattr(analytics_fabric, "execution_orchestrator", None),
            forecasting_engine=getattr(analytics_fabric, "forecasting_engine", None),
            optimizer=getattr(analytics_fabric, "optimizer", None),
            execution_planner=getattr(analytics_fabric, "execution_planner", None),
            governor=getattr(analytics_fabric, "execution_governor", None),
            persistence_engine=persistence_engine,
            snapshot_scheduler=snapshot_scheduler,
            metadata={"source": "self_diagnostic_dashboard"},
        )

    plane = st.session_state["analytics_fabric_control_plane"]
    plane.command_processor = command_processor
    plane.continuous_runtime_engine = continuous_runtime
    plane.autonomous_supervisor = supervisor
    plane.runtime_controller = runtime_controller
    plane.execution_orchestrator = getattr(analytics_fabric, "execution_orchestrator", None)
    plane.forecasting_engine = getattr(analytics_fabric, "forecasting_engine", None)
    plane.optimizer = getattr(analytics_fabric, "optimizer", None)
    plane.execution_planner = getattr(analytics_fabric, "execution_planner", None)
    plane.governor = getattr(analytics_fabric, "execution_governor", None)
    plane.persistence_engine = persistence_engine
    plane.snapshot_scheduler = snapshot_scheduler

    return plane


def _get_diagnostic_engine(
    control_plane,
    command_processor,
    continuous_runtime,
    supervisor,
    runtime_controller,
    persistence_engine,
    analytics_fabric=None,
    diagnostic_engine=None,
):
    if diagnostic_engine is not None:
        return diagnostic_engine

    if "analytics_fabric_self_diagnostic_engine" not in st.session_state:
        st.session_state["analytics_fabric_self_diagnostic_engine"] = AnalyticsFabricSelfDiagnosticEngine(
            control_plane=control_plane,
            command_processor=command_processor,
            continuous_runtime_engine=continuous_runtime,
            autonomous_supervisor=supervisor,
            runtime_controller=runtime_controller,
            execution_orchestrator=getattr(analytics_fabric, "execution_orchestrator", None),
            execution_planner=getattr(analytics_fabric, "execution_planner", None),
            forecast_optimizer=getattr(analytics_fabric, "optimizer", None),
            forecasting_engine=getattr(analytics_fabric, "forecasting_engine", None),
            persistence_engine=persistence_engine,
        )

    engine = st.session_state["analytics_fabric_self_diagnostic_engine"]

    engine.control_plane = control_plane
    engine.command_processor = command_processor
    engine.continuous_runtime_engine = continuous_runtime
    engine.autonomous_supervisor = supervisor
    engine.runtime_controller = runtime_controller
    engine.execution_orchestrator = getattr(analytics_fabric, "execution_orchestrator", None)
    engine.execution_planner = getattr(analytics_fabric, "execution_planner", None)
    engine.forecast_optimizer = getattr(analytics_fabric, "optimizer", None)
    engine.forecasting_engine = getattr(analytics_fabric, "forecasting_engine", None)
    engine.persistence_engine = persistence_engine

    return engine


def render_analytics_fabric_self_diagnostic_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    supervisor: Optional[Any] = None,
    continuous_runtime: Optional[Any] = None,
    command_processor: Optional[Any] = None,
    control_plane: Optional[Any] = None,
    diagnostic_engine: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Self-Diagnostic Dashboard")

    persistence_engine = _get_persistence_engine(persistence_engine)

    runtime_controller = _get_runtime_controller(
        analytics_fabric=analytics_fabric,
        persistence_engine=persistence_engine,
        runtime_controller=runtime_controller,
    )

    snapshot_scheduler = _get_snapshot_scheduler(
        persistence_engine=persistence_engine,
        analytics_fabric=analytics_fabric,
        snapshot_scheduler=snapshot_scheduler,
    )

    supervisor = _get_supervisor(
        runtime_controller=runtime_controller,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
        analytics_fabric=analytics_fabric,
        supervisor=supervisor,
    )

    continuous_runtime = _get_continuous_runtime(
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        snapshot_scheduler=snapshot_scheduler,
        persistence_engine=persistence_engine,
        continuous_runtime=continuous_runtime,
    )

    command_processor = _get_command_processor(
        continuous_runtime=continuous_runtime,
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        persistence_engine=persistence_engine,
        analytics_fabric=analytics_fabric,
        command_processor=command_processor,
    )

    control_plane = _get_control_plane(
        command_processor=command_processor,
        continuous_runtime=continuous_runtime,
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
        analytics_fabric=analytics_fabric,
        control_plane=control_plane,
    )

    diagnostic_engine = _get_diagnostic_engine(
        control_plane=control_plane,
        command_processor=command_processor,
        continuous_runtime=continuous_runtime,
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        persistence_engine=persistence_engine,
        analytics_fabric=analytics_fabric,
        diagnostic_engine=diagnostic_engine,
    )

    if "analytics_fabric_last_diagnostic_report" not in st.session_state:
        st.session_state["analytics_fabric_last_diagnostic_report"] = None

    run_now = st.button(
        "Run Diagnostics",
        type="primary",
        use_container_width=True,
    )

    if run_now or st.session_state["analytics_fabric_last_diagnostic_report"] is None:
        report_obj = diagnostic_engine.run_diagnostics()
        st.session_state["analytics_fabric_last_diagnostic_report"] = report_obj.as_dict()

    report = st.session_state["analytics_fabric_last_diagnostic_report"] or {}

    cols = st.columns(7)

    cols[0].metric("State", report.get("state", "—"))
    cols[1].metric("Health", report.get("overall_health_score", 0))
    cols[2].metric("Risk", report.get("overall_risk_score", 0))
    cols[3].metric("Components", len(report.get("component_reports", [])))
    cols[4].metric("Anomalies", len(report.get("anomalies", [])))
    cols[5].metric("Predicted Failures", len(report.get("predicted_failures", [])))
    cols[6].metric("Recommendations", len(report.get("recommendations", [])))

    tabs = st.tabs(
        [
            "Executive Health",
            "Component Health",
            "Findings",
            "Anomalies",
            "Predicted Failures",
            "Recommendations",
            "Trends",
            "Snapshots",
            "Exports",
            "Raw Report",
        ]
    )

    with tabs[0]:
        st.header("Executive Health Summary")

        executive = _safe_call(
            diagnostic_engine.generate_executive_health_report,
            default={},
        )

        st.json(executive)

        _download_json(
            "Export Executive Health Report",
            executive,
        )

    with tabs[1]:
        st.header("Component Health Grid")

        component_rows = _component_rows(report)

        _records_table(component_rows)

        if component_rows:
            chart_df = pd.DataFrame(component_rows)

            st.subheader("Health by Component")
            st.bar_chart(
                chart_df.set_index("Component")["Health"]
            )

            st.subheader("Risk by Component")
            st.bar_chart(
                chart_df.set_index("Component")["Risk"]
            )

        st.divider()

        st.subheader("Component Drilldown")

        component_names = [
            row["Component"]
            for row in component_rows
            if row.get("Component")
        ]

        if component_names:
            selected = st.selectbox(
                "Component",
                component_names,
                key="diagnostic_component_drilldown",
            )

            selected_report = next(
                (
                    item for item in report.get("component_reports", [])
                    if item.get("component") == selected
                ),
                None,
            )

            if selected_report:
                st.json(selected_report)

    with tabs[2]:
        st.header("Diagnostic Findings")

        findings = _finding_rows(report)

        _records_table(findings)

    with tabs[3]:
        st.header("Anomaly Center")

        anomalies = report.get("anomalies", [])

        _records_table(anomalies)

    with tabs[4]:
        st.header("Predicted Failure Center")

        predictions = report.get("predicted_failures", [])

        _records_table(predictions)

    with tabs[5]:
        st.header("Recovery Recommendations")

        recommendations = report.get("recommendations", [])

        if recommendations:
            for index, recommendation in enumerate(recommendations, 1):
                st.info(f"{index}. {recommendation}")
        else:
            st.success("No recommendations. Fabric is healthy.")

    with tabs[6]:
        st.header("Diagnostic Trends")

        history_rows = _history_rows(diagnostic_engine)

        if history_rows:
            history_df = pd.DataFrame(history_rows)

            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Health Trend")
            st.line_chart(
                history_df.set_index("Generated At")["Health"]
            )

            st.subheader("Risk Trend")
            st.line_chart(
                history_df.set_index("Generated At")["Risk"]
            )
        else:
            st.info("No diagnostic history available.")

    with tabs[7]:
        st.header("Control Plane Health Snapshot")

        snapshot = _safe_call(
            diagnostic_engine.generate_control_plane_health_snapshot,
            default={},
        )

        st.json(snapshot)

        _download_json(
            "Export Control Plane Health Snapshot",
            snapshot,
        )

    with tabs[8]:
        st.header("Exports")

        health_report = _safe_call(
            diagnostic_engine.generate_health_report,
            default={},
        )

        executive_report = _safe_call(
            diagnostic_engine.generate_executive_health_report,
            default={},
        )

        snapshot = _safe_call(
            diagnostic_engine.generate_control_plane_health_snapshot,
            default={},
        )

        summary = _safe_call(
            diagnostic_engine.diagnostics_summary,
            default={},
        )

        _download_json("Export Health Report", health_report)
        _download_json("Export Executive Report", executive_report)
        _download_json("Export Snapshot", snapshot)
        _download_json("Export Diagnostic Summary", summary)

    with tabs[9]:
        st.header("Raw Diagnostic Report")
        st.json(report)


def render_self_diagnostic_dashboard(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_self_diagnostic_dashboard(
        analytics_fabric=analytics_fabric,
    )