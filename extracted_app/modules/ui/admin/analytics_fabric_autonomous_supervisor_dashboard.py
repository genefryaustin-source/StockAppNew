"""
ui/admin/analytics_fabric_autonomous_supervisor_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_autonomous_supervisor import (
    AnalyticsFabricAutonomousSupervisor,
    SupervisorPolicy,
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


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


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


def _download_json(label: str, payload: Any) -> None:
    st.download_button(
        label,
        data=json.dumps(payload, indent=2, default=str),
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )


def _metric_row(metrics: Dict[str, Any], keys: list[str]) -> None:
    cols = st.columns(max(1, len(keys)))

    for col, key in zip(cols, keys):
        value = metrics.get(key, "—")

        if isinstance(value, float):
            value = round(value, 4)

        col.metric(key.replace("_", " ").title(), value)


def _records_table(records: list[Dict[str, Any]]) -> None:
    if not records:
        st.info("No records available.")
        return

    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
    )


def _get_persistence_engine(engine=None):
    if engine is not None:
        return engine

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


def _render_policy_editor(supervisor: AnalyticsFabricAutonomousSupervisor) -> None:
    st.subheader("Supervisor Policy")

    policy = supervisor.policy

    col1, col2, col3 = st.columns(3)

    with col1:
        enabled = st.checkbox("Policy Enabled", value=policy.enabled)
        autonomous_mode_enabled = st.checkbox(
            "Autonomous Mode Enabled",
            value=policy.autonomous_mode_enabled,
        )
        allow_runtime_start = st.checkbox(
            "Allow Runtime Start",
            value=policy.allow_runtime_start,
        )
        allow_runtime_pause = st.checkbox(
            "Allow Runtime Pause",
            value=policy.allow_runtime_pause,
        )

    with col2:
        allow_recovery_automation = st.checkbox(
            "Allow Recovery Automation",
            value=policy.allow_recovery_automation,
        )
        allow_snapshot_creation = st.checkbox(
            "Allow Snapshot Creation",
            value=policy.allow_snapshot_creation,
        )
        allow_governance_enforcement = st.checkbox(
            "Allow Governance Enforcement",
            value=policy.allow_governance_enforcement,
        )

    with col3:
        min_health_score = st.number_input(
            "Minimum Health Score",
            min_value=0.0,
            max_value=100.0,
            value=float(policy.min_health_score),
        )
        min_readiness_score = st.number_input(
            "Minimum Readiness Score",
            min_value=0.0,
            max_value=100.0,
            value=float(policy.min_readiness_score),
        )
        critical_health_score = st.number_input(
            "Critical Health Score",
            min_value=0.0,
            max_value=100.0,
            value=float(policy.critical_health_score),
        )
        critical_readiness_score = st.number_input(
            "Critical Readiness Score",
            min_value=0.0,
            max_value=100.0,
            value=float(policy.critical_readiness_score),
        )

    st.divider()

    col4, col5, col6, col7 = st.columns(4)

    with col4:
        forecast_interval = st.number_input(
            "Forecast Interval Seconds",
            min_value=1,
            value=int(policy.forecast_interval_seconds),
        )
        optimization_interval = st.number_input(
            "Optimization Interval Seconds",
            min_value=1,
            value=int(policy.optimization_interval_seconds),
        )

    with col5:
        planning_interval = st.number_input(
            "Planning Interval Seconds",
            min_value=1,
            value=int(policy.planning_interval_seconds),
        )
        execution_interval = st.number_input(
            "Execution Interval Seconds",
            min_value=1,
            value=int(policy.execution_interval_seconds),
        )

    with col6:
        autonomous_interval = st.number_input(
            "Autonomous Interval Seconds",
            min_value=1,
            value=int(policy.autonomous_cycle_interval_seconds),
        )
        recovery_interval = st.number_input(
            "Recovery Interval Seconds",
            min_value=1,
            value=int(policy.recovery_interval_seconds),
        )

    with col7:
        snapshot_interval = st.number_input(
            "Snapshot Interval Seconds",
            min_value=1,
            value=int(policy.snapshot_interval_seconds),
        )
        max_failed_degraded = st.number_input(
            "Failed Cycles Before Degraded",
            min_value=1,
            value=int(policy.max_failed_cycles_before_degraded),
        )
        max_failed_pause = st.number_input(
            "Failed Cycles Before Pause",
            min_value=1,
            value=int(policy.max_failed_cycles_before_pause),
        )

    if st.button("Apply Supervisor Policy", use_container_width=True):
        supervisor.policy = SupervisorPolicy(
            policy_id=policy.policy_id,
            enabled=enabled,
            autonomous_mode_enabled=autonomous_mode_enabled,
            allow_runtime_start=allow_runtime_start,
            allow_runtime_pause=allow_runtime_pause,
            allow_recovery_automation=allow_recovery_automation,
            allow_snapshot_creation=allow_snapshot_creation,
            allow_governance_enforcement=allow_governance_enforcement,
            forecast_interval_seconds=int(forecast_interval),
            optimization_interval_seconds=int(optimization_interval),
            planning_interval_seconds=int(planning_interval),
            execution_interval_seconds=int(execution_interval),
            autonomous_cycle_interval_seconds=int(autonomous_interval),
            recovery_interval_seconds=int(recovery_interval),
            snapshot_interval_seconds=int(snapshot_interval),
            min_health_score=float(min_health_score),
            min_readiness_score=float(min_readiness_score),
            critical_health_score=float(critical_health_score),
            critical_readiness_score=float(critical_readiness_score),
            max_failed_cycles_before_degraded=int(max_failed_degraded),
            max_failed_cycles_before_pause=int(max_failed_pause),
            metadata=policy.metadata,
        )

        supervisor.update_cycle_schedule("forecast", int(forecast_interval))
        supervisor.update_cycle_schedule("optimization", int(optimization_interval))
        supervisor.update_cycle_schedule("planning", int(planning_interval))
        supervisor.update_cycle_schedule("execution", int(execution_interval))
        supervisor.update_cycle_schedule("autonomous", int(autonomous_interval))
        supervisor.update_cycle_schedule("recovery", int(recovery_interval))
        supervisor.update_cycle_schedule("snapshot", int(snapshot_interval))

        st.success("Supervisor policy updated.")
        st.rerun()

    with st.expander("Raw Policy", expanded=False):
        st.json(asdict(supervisor.policy))


def render_analytics_fabric_autonomous_supervisor_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    supervisor: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Autonomous Supervisor")

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

    status = _safe_call(supervisor.supervisor_status, default={})
    health = _safe_call(supervisor.supervisor_health, default={})
    metrics = status.get("metrics", {})

    cols = st.columns(10)

    cols[0].metric("State", status.get("state", "—"))
    cols[1].metric("Health", health.get("supervisor_health_score", 0))
    cols[2].metric("Autonomous", metrics.get("autonomous_cycles", 0))
    cols[3].metric("Forecast", metrics.get("forecast_cycles", 0))
    cols[4].metric("Optimization", metrics.get("optimization_cycles", 0))
    cols[5].metric("Planning", metrics.get("planning_cycles", 0))
    cols[6].metric("Execution", metrics.get("execution_cycles", 0))
    cols[7].metric("Recovery", metrics.get("recovery_cycles", 0))
    cols[8].metric("Open Incidents", status.get("open_incidents", 0))
    cols[9].metric("Decisions", metrics.get("decisions_generated", 0))

    tabs = st.tabs(
        [
            "Overview",
            "Supervisor State",
            "Autonomous Cycles",
            "Cycle Schedules",
            "Runtime Health",
            "Governance",
            "Incident Center",
            "Recovery Center",
            "Decision Center",
            "Snapshots",
            "Metrics",
            "Cycle History",
            "Policy",
            "Exports",
        ]
    )

    with tabs[0]:
        st.header("Supervisor Overview")

        st.json(status)

        st.divider()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("Start Supervisor", use_container_width=True):
                st.json(supervisor.start_supervisor())

        with col2:
            if st.button("Pause Supervisor", use_container_width=True):
                st.json(supervisor.pause_supervisor())

        with col3:
            if st.button("Resume Supervisor", use_container_width=True):
                st.json(supervisor.resume_supervisor())

        with col4:
            if st.button("Stop Supervisor", use_container_width=True):
                st.json(supervisor.stop_supervisor())

    with tabs[1]:
        st.header("Supervisor State")

        st.json(
            {
                "status": status,
                "health": health,
                "policy": asdict(supervisor.policy),
            }
        )

    with tabs[2]:
        st.header("Autonomous Cycles")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Run Supervisor Cycle", use_container_width=True):
                result = supervisor.run_supervisor_cycle(force=False)
                st.success("Supervisor cycle completed.")
                st.json(result)

            if st.button("Run Forced Supervisor Cycle", use_container_width=True):
                result = supervisor.run_supervisor_cycle(force=True)
                st.success("Forced supervisor cycle completed.")
                st.json(result)

        with col2:
            if st.button("Run Autonomous Cycle", use_container_width=True):
                result = supervisor.run_autonomous_cycle()
                st.success("Autonomous cycle completed.")
                st.json(result)

            if st.button("Run Forecast Cycle", use_container_width=True):
                result = supervisor.run_forecasting_cycle()
                st.success("Forecast cycle completed.")
                st.json(result)

        with col3:
            if st.button("Run Optimization Cycle", use_container_width=True):
                result = supervisor.run_optimization_cycle()
                st.success("Optimization cycle completed.")
                st.json(result)

            if st.button("Run Planning Cycle", use_container_width=True):
                result = supervisor.run_planning_cycle()
                st.success("Planning cycle completed.")
                st.json(result)

        st.divider()

        col4, col5, col6 = st.columns(3)

        with col4:
            if st.button("Run Execution Cycle", use_container_width=True):
                result = supervisor.run_execution_cycle()
                st.success("Execution cycle completed.")
                st.json(result)

        with col5:
            if st.button("Run Recovery Cycle", use_container_width=True):
                result = supervisor.run_recovery_cycle()
                st.success("Recovery cycle completed.")
                st.json(result)

        with col6:
            if st.button("Create Snapshot", use_container_width=True):
                result = supervisor.run_snapshot_cycle()
                st.success("Snapshot cycle completed.")
                st.json(result)

    with tabs[3]:
        st.header("Cycle Schedules")

        schedules = _safe_call(supervisor.list_cycle_schedules, default=[])

        _records_table(schedules)

        st.divider()

        schedule_names = [item.get("name") for item in schedules]

        if schedule_names:
            selected_schedule = st.selectbox("Schedule", schedule_names)

            selected_record = next(
                item for item in schedules
                if item.get("name") == selected_schedule
            )

            interval = st.number_input(
                "Interval Seconds",
                min_value=1,
                value=int(selected_record.get("interval_seconds", 300)),
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Update Interval", use_container_width=True):
                    supervisor.update_cycle_schedule(selected_schedule, int(interval))
                    st.success("Schedule interval updated.")
                    st.rerun()

            with col2:
                if st.button("Pause Schedule", use_container_width=True):
                    supervisor.pause_cycle_schedule(selected_schedule)
                    st.success("Schedule paused.")
                    st.rerun()

            with col3:
                if st.button("Resume Schedule", use_container_width=True):
                    supervisor.resume_cycle_schedule(selected_schedule)
                    st.success("Schedule resumed.")
                    st.rerun()

    with tabs[4]:
        st.header("Runtime Health")

        runtime_status = _safe_call(runtime_controller.runtime_status, default={})
        runtime_health = _safe_call(runtime_controller.runtime_health, default={})
        runtime_metrics = _safe_call(runtime_controller.runtime_metrics, default={})

        _metric_row(
            runtime_health,
            [
                "health_score",
                "capacity_score",
                "provider_score",
                "governance_score",
                "queue_score",
                "readiness_score",
            ],
        )

        st.divider()

        health_df = pd.DataFrame(
            [
                {"Area": "Capacity", "Score": runtime_health.get("capacity_score", 0)},
                {"Area": "Provider", "Score": runtime_health.get("provider_score", 0)},
                {"Area": "Governance", "Score": runtime_health.get("governance_score", 0)},
                {"Area": "Queue", "Score": runtime_health.get("queue_score", 0)},
                {"Area": "Readiness", "Score": runtime_health.get("readiness_score", 0)},
            ]
        )

        st.bar_chart(health_df.set_index("Area"))

        st.subheader("Runtime Status")
        st.json(runtime_status)

        st.subheader("Runtime Metrics")
        st.json(runtime_metrics)

    with tabs[5]:
        st.header("Governance")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Enforce Governance", use_container_width=True):
                result = supervisor.enforce_governance()
                st.success("Governance enforcement completed.")
                st.json(result)

        with col2:
            if st.button("Enforce Health", use_container_width=True):
                result = supervisor.enforce_health()
                st.success("Health enforcement completed.")
                st.json(result)

        st.divider()

        governor = getattr(analytics_fabric, "execution_governor", None)

        if governor is not None:
            st.subheader("Execution Governor Summary")
            st.json(_safe_call(governor.governance_summary, default={}))
        else:
            st.info("No execution governor attached.")

    with tabs[6]:
        st.header("Incident Center")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Detect Incidents", use_container_width=True):
                result = supervisor.detect_incidents()
                st.success("Incident detection completed.")
                st.json(result)

        with col2:
            if st.button("Refresh Incident Center", use_container_width=True):
                st.rerun()

        st.divider()

        incidents = _safe_call(supervisor.incident_history, default=[])

        _records_table(incidents)

    with tabs[7]:
        st.header("Recovery Center")

        if st.button("Run Recovery Cycle", use_container_width=True):
            result = supervisor.run_recovery_cycle()
            st.success("Recovery cycle completed.")
            st.json(result)

        st.divider()

        recovery_plans = [
            plan.as_dict()
            for plan in getattr(runtime_controller, "recovery_plans", [])
        ]

        st.subheader("Runtime Recovery Plans")
        _records_table(recovery_plans)

        st.subheader("Supervisor Recovery Metrics")
        st.json(
            {
                "recoveries_triggered": metrics.get("recoveries_triggered", 0),
                "recovery_cycles": metrics.get("recovery_cycles", 0),
            }
        )

    with tabs[8]:
        st.header("Decision Center")

        decisions = _safe_call(supervisor.decision_history, default=[])

        _records_table(decisions)

    with tabs[9]:
        st.header("Snapshots")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Create Supervisor Snapshot", use_container_width=True):
                snapshot = supervisor.supervisor_snapshot()
                st.success("Supervisor snapshot created.")
                st.json(snapshot.as_dict())

        with col2:
            if st.button("Run Snapshot Cycle", use_container_width=True):
                result = supervisor.run_snapshot_cycle()
                st.success("Snapshot cycle completed.")
                st.json(result)

        st.divider()

        snapshots = _safe_call(supervisor.snapshot_history, default=[])

        _records_table(snapshots)

    with tabs[10]:
        st.header("Metrics")

        metrics_df = pd.DataFrame(
            [
                {"Metric": key, "Value": value}
                for key, value in metrics.items()
            ]
        )

        st.dataframe(
            metrics_df,
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pd.DataFrame(
            [
                ("Supervisor", metrics.get("supervisor_cycles", 0)),
                ("Autonomous", metrics.get("autonomous_cycles", 0)),
                ("Forecast", metrics.get("forecast_cycles", 0)),
                ("Optimization", metrics.get("optimization_cycles", 0)),
                ("Planning", metrics.get("planning_cycles", 0)),
                ("Execution", metrics.get("execution_cycles", 0)),
                ("Recovery", metrics.get("recovery_cycles", 0)),
                ("Snapshot", metrics.get("snapshot_cycles", 0)),
                ("Failed", metrics.get("failed_cycles", 0)),
            ],
            columns=["Cycle", "Count"],
        )

        st.bar_chart(chart_df.set_index("Cycle"))

    with tabs[11]:
        st.header("Cycle History")

        cycles = _safe_call(supervisor.cycle_results, default=[])

        _records_table(cycles)

    with tabs[12]:
        _render_policy_editor(supervisor)

    with tabs[13]:
        st.header("Exports")

        export_package = {
            "supervisor_status": _safe_call(supervisor.supervisor_status, default={}),
            "supervisor_health": _safe_call(supervisor.supervisor_health, default={}),
            "supervisor_metrics": metrics,
            "policy": asdict(supervisor.policy),
            "schedules": _safe_call(supervisor.list_cycle_schedules, default=[]),
            "decisions": _safe_call(supervisor.decision_history, default=[]),
            "incidents": _safe_call(supervisor.incident_history, default=[]),
            "snapshots": _safe_call(supervisor.snapshot_history, default=[]),
            "cycles": _safe_call(supervisor.cycle_results, default=[]),
            "runtime_status": _safe_call(runtime_controller.runtime_status, default={}),
            "runtime_health": _safe_call(runtime_controller.runtime_health, default={}),
            "runtime_metrics": _safe_call(runtime_controller.runtime_metrics, default={}),
        }

        _download_json("Export Supervisor State", export_package["supervisor_status"])
        _download_json("Export Supervisor Metrics", export_package["supervisor_metrics"])
        _download_json("Export Decisions", export_package["decisions"])
        _download_json("Export Incidents", export_package["incidents"])
        _download_json("Export Snapshots", export_package["snapshots"])
        _download_json("Export Cycle History", export_package["cycles"])
        _download_json("Export Executive Supervisor Package", export_package)

        st.json(export_package)


def render_autonomous_supervisor_dashboard(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_autonomous_supervisor_dashboard(
        analytics_fabric=analytics_fabric,
    )