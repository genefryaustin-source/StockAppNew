"""
ui/admin/analytics_fabric_continuous_runtime_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_continuous_runtime_engine import (
    AnalyticsFabricContinuousRuntimeEngine,
    ContinuousRuntimeConfig,
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


def _records_table(records: list[Dict[str, Any]]) -> None:
    if not records:
        st.info("No records available.")
        return

    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
    )


def _metric_row(metrics: Dict[str, Any], keys: list[str]) -> None:
    cols = st.columns(max(1, len(keys)))

    for col, key in zip(cols, keys):
        value = metrics.get(key, "—")

        if isinstance(value, float):
            value = round(value, 4)

        col.metric(key.replace("_", " ").title(), value)


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
            config=ContinuousRuntimeConfig(
                enable_threaded_loop=False,
            ),
        )

    engine = st.session_state["analytics_fabric_continuous_runtime_engine"]
    engine.supervisor = supervisor
    engine.runtime_controller = runtime_controller
    engine.snapshot_scheduler = snapshot_scheduler
    engine.persistence_engine = persistence_engine

    return engine


def _render_config_editor(engine: AnalyticsFabricContinuousRuntimeEngine) -> None:
    st.subheader("Continuous Runtime Configuration")

    config = engine.config

    col1, col2, col3 = st.columns(3)

    with col1:
        loop_interval = st.number_input(
            "Loop Interval Seconds",
            min_value=0.1,
            value=float(config.loop_interval_seconds),
        )
        heartbeat_interval = st.number_input(
            "Heartbeat Interval Seconds",
            min_value=1.0,
            value=float(config.heartbeat_interval_seconds),
        )
        health_interval = st.number_input(
            "Health Check Interval Seconds",
            min_value=1.0,
            value=float(config.health_check_interval_seconds),
        )

    with col2:
        recovery_interval = st.number_input(
            "Recovery Interval Seconds",
            min_value=1.0,
            value=float(config.recovery_interval_seconds),
        )
        snapshot_interval = st.number_input(
            "Snapshot Interval Seconds",
            min_value=1.0,
            value=float(config.snapshot_interval_seconds),
        )
        governance_interval = st.number_input(
            "Governance Interval Seconds",
            min_value=1.0,
            value=float(config.governance_interval_seconds),
        )

    with col3:
        run_supervisor_each_tick = st.checkbox(
            "Run Supervisor Each Tick",
            value=config.run_supervisor_each_tick,
        )
        run_health_each_tick = st.checkbox(
            "Run Health Each Tick",
            value=config.run_health_each_tick,
        )
        run_recovery_on_degraded = st.checkbox(
            "Run Recovery On Degraded",
            value=config.run_recovery_on_degraded,
        )
        run_snapshot_on_start = st.checkbox(
            "Run Snapshot On Start",
            value=config.run_snapshot_on_start,
        )
        enable_threaded_loop = st.checkbox(
            "Enable Threaded Loop",
            value=config.enable_threaded_loop,
        )

    col4, col5 = st.columns(2)

    with col4:
        max_errors = st.number_input(
            "Max Consecutive Errors",
            min_value=1,
            value=int(config.max_consecutive_errors),
        )

    with col5:
        auto_pause = st.checkbox(
            "Auto Pause On Error Threshold",
            value=config.auto_pause_on_error_threshold,
        )
        auto_recover = st.checkbox(
            "Auto Recover On Error",
            value=config.auto_recover_on_error,
        )

    if st.button("Apply Runtime Configuration", use_container_width=True):
        engine.config = ContinuousRuntimeConfig(
            loop_interval_seconds=float(loop_interval),
            heartbeat_interval_seconds=float(heartbeat_interval),
            health_check_interval_seconds=float(health_interval),
            recovery_interval_seconds=float(recovery_interval),
            snapshot_interval_seconds=float(snapshot_interval),
            governance_interval_seconds=float(governance_interval),
            run_supervisor_each_tick=run_supervisor_each_tick,
            run_health_each_tick=run_health_each_tick,
            run_recovery_on_degraded=run_recovery_on_degraded,
            run_snapshot_on_start=run_snapshot_on_start,
            enable_threaded_loop=enable_threaded_loop,
            max_consecutive_errors=int(max_errors),
            auto_pause_on_error_threshold=auto_pause,
            auto_recover_on_error=auto_recover,
            metadata=config.metadata,
        )

        st.success("Continuous runtime configuration updated.")
        st.rerun()

    with st.expander("Raw Config", expanded=False):
        st.json(asdict(engine.config))


def render_analytics_fabric_continuous_runtime_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    supervisor: Optional[Any] = None,
    continuous_runtime: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Continuous Runtime Dashboard")

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

    engine = _get_continuous_runtime(
        supervisor=supervisor,
        runtime_controller=runtime_controller,
        snapshot_scheduler=snapshot_scheduler,
        persistence_engine=persistence_engine,
        continuous_runtime=continuous_runtime,
    )

    status = _safe_call(engine.runtime_status, default={})
    summary = _safe_call(engine.runtime_summary, default={})
    metrics = _safe_call(engine.runtime_metrics, default={})

    cols = st.columns(10)

    cols[0].metric("State", status.get("state", "—"))
    cols[1].metric("Thread Alive", status.get("thread_alive", False))
    cols[2].metric("Loops Started", metrics.get("loops_started", 0))
    cols[3].metric("Loops Completed", metrics.get("loops_completed", 0))
    cols[4].metric("Loops Failed", metrics.get("loops_failed", 0))
    cols[5].metric("Supervisor Cycles", metrics.get("supervisor_cycles", 0))
    cols[6].metric("Health Checks", metrics.get("health_checks", 0))
    cols[7].metric("Recovery Cycles", metrics.get("recovery_cycles", 0))
    cols[8].metric("Snapshots", metrics.get("snapshot_cycles", 0))
    cols[9].metric("Heartbeats", metrics.get("heartbeats", 0))

    tabs = st.tabs(
        [
            "Overview",
            "Runtime Controls",
            "Manual Loop",
            "Heartbeats",
            "Events",
            "Ticks",
            "Health",
            "Supervisor",
            "Recovery",
            "Snapshots",
            "Governance",
            "Metrics",
            "Configuration",
            "Exports",
        ]
    )

    with tabs[0]:
        st.header("Continuous Runtime Overview")

        st.json(summary)

        st.divider()

        st.subheader("Runtime Status")
        st.json(status)

    with tabs[1]:
        st.header("Runtime Controls")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("Start Runtime", use_container_width=True):
                st.json(engine.start_runtime())

        with col2:
            if st.button("Pause Runtime", use_container_width=True):
                st.json(engine.pause_runtime())

        with col3:
            if st.button("Resume Runtime", use_container_width=True):
                st.json(engine.resume_runtime())

        with col4:
            if st.button("Stop Runtime", use_container_width=True):
                st.json(engine.stop_runtime())

        st.divider()

        col5, col6 = st.columns(2)

        with col5:
            if st.button("Start Background Loop", use_container_width=True):
                st.json(engine.start_background_loop())

        with col6:
            if st.button("Emit Heartbeat", use_container_width=True):
                heartbeat = engine.emit_heartbeat()
                st.success("Heartbeat emitted.")
                st.json(heartbeat.as_dict())

    with tabs[2]:
        st.header("Manual Loop Execution")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Run One Tick", use_container_width=True):
                result = engine.run_once(force=False)
                st.success("Tick completed.")
                st.json(result.as_dict())

            if st.button("Run Forced Tick", use_container_width=True):
                result = engine.run_once(force=True)
                st.success("Forced tick completed.")
                st.json(result.as_dict())

        with col2:
            iterations = st.number_input(
                "Iterations",
                min_value=1,
                max_value=1000,
                value=5,
            )
            sleep_between = st.checkbox(
                "Sleep Between Iterations",
                value=False,
            )
            force_iterations = st.checkbox(
                "Force Iterations",
                value=False,
            )

            if st.button("Run Iterations", use_container_width=True):
                results = engine.run_for_iterations(
                    int(iterations),
                    sleep_between_iterations=sleep_between,
                    force=force_iterations,
                )
                st.success("Iteration run completed.")
                st.json(results)

    with tabs[3]:
        st.header("Heartbeat Monitoring")

        records = _safe_call(engine.heartbeat_records, default=[])

        _records_table(records)

        st.divider()

        if records:
            heartbeat_df = pd.DataFrame(records)
            st.line_chart(
                heartbeat_df[["loop_count", "uptime_seconds"]]
            )

    with tabs[4]:
        st.header("Event History")

        events = _safe_call(engine.event_history, default=[])

        _records_table(events)

        st.divider()

        if events:
            event_counts = (
                pd.DataFrame(events)
                .groupby("event_type")
                .size()
                .reset_index(name="count")
            )

            st.bar_chart(event_counts.set_index("event_type"))

    with tabs[5]:
        st.header("Tick History")

        ticks = _safe_call(engine.tick_records, default=[])

        _records_table(ticks)

        st.divider()

        if ticks:
            tick_df = pd.DataFrame(ticks)
            if "runtime_ms" in tick_df.columns:
                st.line_chart(tick_df[["runtime_ms"]])

    with tabs[6]:
        st.header("Runtime Health")

        health_check = _safe_call(engine.run_health_check, default={})
        supervisor_health = _safe_call(supervisor.supervisor_health, default={})
        runtime_health = _safe_call(runtime_controller.runtime_health, default={})

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

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Supervisor Health")
            st.json(supervisor_health)

        with col2:
            st.subheader("Runtime Controller Health")
            st.json(runtime_health)

        st.subheader("Health Check Result")
        st.json(health_check)

    with tabs[7]:
        st.header("Supervisor Linkage")

        supervisor_status = _safe_call(supervisor.supervisor_status, default={})
        supervisor_metrics = supervisor_status.get("metrics", {})

        _metric_row(
            supervisor_metrics,
            [
                "supervisor_cycles",
                "autonomous_cycles",
                "forecast_cycles",
                "optimization_cycles",
                "planning_cycles",
                "execution_cycles",
                "recovery_cycles",
                "snapshot_cycles",
                "failed_cycles",
            ],
        )

        st.divider()

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Run Supervisor Cycle", use_container_width=True):
                st.json(engine.run_supervisor_cycle(force=False))

        with col2:
            if st.button("Run Forced Supervisor Cycle", use_container_width=True):
                st.json(engine.run_supervisor_cycle(force=True))

        with col3:
            if st.button("Run Supervisor Autonomous Cycle", use_container_width=True):
                st.json(supervisor.run_autonomous_cycle())

        st.subheader("Supervisor Status")
        st.json(supervisor_status)

    with tabs[8]:
        st.header("Recovery Operations")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Run Recovery Cycle", use_container_width=True):
                st.json(engine.run_recovery_cycle())

        with col2:
            if st.button("Run Runtime Recovery Cycle", use_container_width=True):
                st.json(runtime_controller.run_recovery_cycle())

        st.divider()

        recovery_plans = [
            plan.as_dict()
            for plan in getattr(runtime_controller, "recovery_plans", [])
        ]

        _records_table(recovery_plans)

    with tabs[9]:
        st.header("Snapshot Collection")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Run Snapshot Cycle", use_container_width=True):
                st.json(engine.run_snapshot_cycle())

        with col2:
            if st.button("Create Supervisor Snapshot", use_container_width=True):
                snapshot = supervisor.supervisor_snapshot()
                st.json(snapshot.as_dict())

        with col3:
            if st.button("Create Runtime Snapshot", use_container_width=True):
                snapshot = runtime_controller.runtime_snapshot()
                st.json(snapshot.as_dict())

        st.divider()

        supervisor_snapshots = _safe_call(supervisor.snapshot_history, default=[])
        runtime_snapshots = [
            snapshot.as_dict()
            for snapshot in getattr(runtime_controller, "snapshots", [])
        ]

        st.subheader("Supervisor Snapshots")
        _records_table(supervisor_snapshots)

        st.subheader("Runtime Snapshots")
        _records_table(runtime_snapshots)

    with tabs[10]:
        st.header("Governance Enforcement")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Run Governance Cycle", use_container_width=True):
                st.json(engine.run_governance_cycle())

        with col2:
            if st.button("Supervisor Enforce Governance", use_container_width=True):
                st.json(supervisor.enforce_governance())

        governor = getattr(analytics_fabric, "execution_governor", None)

        if governor is not None:
            st.subheader("Execution Governor Summary")
            st.json(_safe_call(governor.governance_summary, default={}))
        else:
            st.info("No execution governor attached.")

    with tabs[11]:
        st.header("Continuous Runtime Metrics")

        st.dataframe(
            pd.DataFrame(
                [{"Metric": key, "Value": value} for key, value in metrics.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pd.DataFrame(
            [
                ("Started", metrics.get("loops_started", 0)),
                ("Completed", metrics.get("loops_completed", 0)),
                ("Failed", metrics.get("loops_failed", 0)),
                ("Supervisor", metrics.get("supervisor_cycles", 0)),
                ("Health", metrics.get("health_checks", 0)),
                ("Recovery", metrics.get("recovery_cycles", 0)),
                ("Snapshots", metrics.get("snapshot_cycles", 0)),
                ("Governance", metrics.get("governance_cycles", 0)),
                ("Heartbeats", metrics.get("heartbeats", 0)),
            ],
            columns=["Metric", "Value"],
        )

        st.bar_chart(chart_df.set_index("Metric"))

    with tabs[12]:
        _render_config_editor(engine)

    with tabs[13]:
        st.header("Exports")

        export_state = _safe_call(engine.export_state, default={})

        _download_json("Export Continuous Runtime State", export_state)
        _download_json("Export Runtime Metrics", metrics)
        _download_json("Export Event History", _safe_call(engine.event_history, default=[]))
        _download_json("Export Tick History", _safe_call(engine.tick_records, default=[]))
        _download_json("Export Heartbeat History", _safe_call(engine.heartbeat_records, default=[]))
        _download_json("Export Executive Continuous Runtime Package", export_state)

        st.json(export_state)


def render_continuous_runtime_dashboard(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_continuous_runtime_dashboard(
        analytics_fabric=analytics_fabric,
    )