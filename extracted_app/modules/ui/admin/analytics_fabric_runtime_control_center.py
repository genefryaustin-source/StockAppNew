"""
ui/admin/analytics_fabric_runtime_control_center.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_runtime_controller import (
    AnalyticsFabricRuntimeController,
)

from modules.analytics.analytics_fabric_forecasting_engine import (
    AnalyticsFabricForecastingEngine,
)

from modules.analytics.autonomous_forecast_optimizer import (
    AutonomousForecastOptimizer,
)

from modules.analytics.autonomous_execution_planner import (
    AutonomousExecutionPlanner,
)

from modules.analytics.autonomous_execution_orchestrator import (
    AutonomousExecutionOrchestrator,
)

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
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


def _table_from_records(records: list[Dict[str, Any]]) -> None:
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


def _get_forecasting_engine(persistence_engine, engine=None):
    if engine is not None:
        return engine

    if "analytics_forecasting_engine" not in st.session_state:
        st.session_state["analytics_forecasting_engine"] = AnalyticsFabricForecastingEngine(
            persistence_engine=persistence_engine,
        )

    return st.session_state["analytics_forecasting_engine"]


def _get_optimizer(forecasting_engine, persistence_engine, optimizer=None):
    if optimizer is not None:
        return optimizer

    if "autonomous_forecast_optimizer" not in st.session_state:
        st.session_state["autonomous_forecast_optimizer"] = AutonomousForecastOptimizer(
            forecasting_engine=forecasting_engine,
            persistence_engine=persistence_engine,
        )

    return st.session_state["autonomous_forecast_optimizer"]


def _get_planner(
    optimizer,
    forecasting_engine,
    persistence_engine,
    analytics_fabric=None,
    planner=None,
):
    if planner is not None:
        return planner

    if "autonomous_execution_planner" not in st.session_state:
        st.session_state["autonomous_execution_planner"] = AutonomousExecutionPlanner(
            analytics_fabric=analytics_fabric,
            forecast_optimizer=optimizer,
            forecasting_engine=forecasting_engine,
            persistence_engine=persistence_engine,
        )

    planner_obj = st.session_state["autonomous_execution_planner"]
    planner_obj.analytics_fabric = analytics_fabric
    planner_obj.forecast_optimizer = optimizer
    planner_obj.forecasting_engine = forecasting_engine
    planner_obj.persistence_engine = persistence_engine

    return planner_obj


def _get_orchestrator(
    planner,
    persistence_engine,
    analytics_fabric=None,
    orchestrator=None,
):
    if orchestrator is not None:
        return orchestrator

    if "autonomous_execution_orchestrator" not in st.session_state:
        st.session_state["autonomous_execution_orchestrator"] = AutonomousExecutionOrchestrator(
            execution_planner=planner,
            analytics_fabric=analytics_fabric,
            persistence_engine=persistence_engine,
        )

    orch = st.session_state["autonomous_execution_orchestrator"]
    orch.execution_planner = planner
    orch.analytics_fabric = analytics_fabric
    orch.persistence_engine = persistence_engine

    return orch


def _get_runtime_controller(
    persistence_engine,
    forecasting_engine,
    optimizer,
    planner,
    orchestrator,
    analytics_fabric=None,
    runtime_controller=None,
):
    if runtime_controller is not None:
        return runtime_controller

    if "analytics_fabric_runtime_controller" not in st.session_state:
        st.session_state["analytics_fabric_runtime_controller"] = AnalyticsFabricRuntimeController(
            forecasting_engine=forecasting_engine,
            optimizer=optimizer,
            planner=planner,
            orchestrator=orchestrator,
            governor=getattr(analytics_fabric, "execution_governor", None),
            global_planner=getattr(analytics_fabric, "global_planner", None),
            worker_capacity_model=getattr(analytics_fabric, "worker_capacity_model", None),
            provider_cost_intelligence=getattr(analytics_fabric, "provider_cost_intelligence", None),
            persistence_engine=persistence_engine,
        )

    controller = st.session_state["analytics_fabric_runtime_controller"]
    controller.forecasting_engine = forecasting_engine
    controller.optimizer = optimizer
    controller.planner = planner
    controller.orchestrator = orchestrator
    controller.governor = getattr(analytics_fabric, "execution_governor", None)
    controller.global_planner = getattr(analytics_fabric, "global_planner", None)
    controller.worker_capacity_model = getattr(analytics_fabric, "worker_capacity_model", None)
    controller.provider_cost_intelligence = getattr(analytics_fabric, "provider_cost_intelligence", None)
    controller.persistence_engine = persistence_engine

    return controller


def render_analytics_fabric_runtime_control_center(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    forecasting_engine: Optional[Any] = None,
    optimizer: Optional[Any] = None,
    planner: Optional[Any] = None,
    orchestrator: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Runtime Control Center")

    persistence_engine = _get_persistence_engine(persistence_engine)
    forecasting_engine = _get_forecasting_engine(persistence_engine, forecasting_engine)
    optimizer = _get_optimizer(forecasting_engine, persistence_engine, optimizer)
    planner = _get_planner(
        optimizer,
        forecasting_engine,
        persistence_engine,
        analytics_fabric=analytics_fabric,
        planner=planner,
    )
    orchestrator = _get_orchestrator(
        planner,
        persistence_engine,
        analytics_fabric=analytics_fabric,
        orchestrator=orchestrator,
    )
    runtime_controller = _get_runtime_controller(
        persistence_engine,
        forecasting_engine,
        optimizer,
        planner,
        orchestrator,
        analytics_fabric=analytics_fabric,
        runtime_controller=runtime_controller,
    )

    status = _safe_call(runtime_controller.runtime_status, default={})
    health = _safe_call(runtime_controller.runtime_health, default={})
    metrics = _safe_call(runtime_controller.runtime_metrics, default={})
    summary = _safe_call(runtime_controller.runtime_summary, default={})

    cols = st.columns(9)

    cols[0].metric("State", status.get("state", "—"))
    cols[1].metric("Health", health.get("health_score", 0))
    cols[2].metric("Readiness", health.get("readiness_score", 0))
    cols[3].metric("Forecast Cycles", metrics.get("forecast_cycles", 0))
    cols[4].metric("Optimization Cycles", metrics.get("optimization_cycles", 0))
    cols[5].metric("Planning Cycles", metrics.get("planning_cycles", 0))
    cols[6].metric("Execution Cycles", metrics.get("execution_cycles", 0))
    cols[7].metric("Autonomous Cycles", metrics.get("autonomous_cycles", 0))
    cols[8].metric("Recovery Cycles", metrics.get("recovery_cycles", 0))

    tabs = st.tabs(
        [
            "Overview",
            "Runtime State",
            "Runtime Health",
            "Forecasting",
            "Optimization",
            "Planning",
            "Execution",
            "Governance",
            "Recovery",
            "Incidents",
            "Decisions",
            "Snapshots",
            "Metrics",
            "Control Tower",
            "Exports",
        ]
    )

    with tabs[0]:
        st.header("Runtime Overview")

        st.json(summary)

        st.divider()

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("Initialize Runtime", use_container_width=True):
                st.json(runtime_controller.initialize_runtime())

        with col2:
            if st.button("Start Runtime", use_container_width=True):
                st.json(runtime_controller.start_runtime())

        with col3:
            if st.button("Pause Runtime", use_container_width=True):
                st.json(runtime_controller.pause_runtime())

        with col4:
            if st.button("Resume Runtime", use_container_width=True):
                st.json(runtime_controller.resume_runtime())

        with col5:
            if st.button("Stop Runtime", use_container_width=True):
                st.json(runtime_controller.stop_runtime())

    with tabs[1]:
        st.header("Runtime State")

        st.json(_as_dict(runtime_controller.runtime_state))

        st.subheader("Runtime Status")
        st.json(status)

    with tabs[2]:
        st.header("Runtime Health")

        _metric_row(
            health,
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
                {"Area": "Capacity", "Score": health.get("capacity_score", 0)},
                {"Area": "Provider", "Score": health.get("provider_score", 0)},
                {"Area": "Governance", "Score": health.get("governance_score", 0)},
                {"Area": "Queue", "Score": health.get("queue_score", 0)},
                {"Area": "Readiness", "Score": health.get("readiness_score", 0)},
            ]
        )

        st.bar_chart(health_df.set_index("Area"))

        st.json(health)

    with tabs[3]:
        st.header("Forecasting")

        if st.button("Run Forecast Cycle", use_container_width=True):
            result = runtime_controller.run_forecasting_cycle()
            st.success("Forecast cycle completed.")
            st.json(result)

        st.divider()

        forecast_report = _safe_call(
            forecasting_engine.generate_forecast_report,
            default=None,
        )

        if forecast_report is not None:
            st.json(_as_dict(forecast_report))

    with tabs[4]:
        st.header("Optimization")

        if st.button("Run Optimization Cycle", use_container_width=True):
            result = runtime_controller.run_optimization_cycle()
            st.success("Optimization cycle completed.")
            st.json(result)

        st.divider()

        optimization_report = _safe_call(
            optimizer.generate_optimization_report,
            default=None,
        )

        if optimization_report is not None:
            st.json(_as_dict(optimization_report))

    with tabs[5]:
        st.header("Planning")

        if st.button("Run Planning Cycle", use_container_width=True):
            result = runtime_controller.run_planning_cycle()
            st.success("Planning cycle completed.")
            st.json(result)

        st.divider()

        if st.button("Generate Execution Plan", use_container_width=True):
            plan = planner.build_execution_plan_from_optimizer()
            st.session_state["runtime_control_current_plan"] = plan
            st.success("Execution plan generated.")
            st.json(plan.as_dict())

        plan = st.session_state.get("runtime_control_current_plan")
        if plan is not None:
            st.subheader("Current Execution Plan")
            st.json(plan.as_dict())

    with tabs[6]:
        st.header("Execution")

        if st.button("Run Execution Cycle", use_container_width=True):
            result = runtime_controller.run_execution_cycle()
            st.success("Execution cycle completed.")
            st.json(result)

        st.divider()

        plan = st.session_state.get("runtime_control_current_plan")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Run Autonomous Cycle", use_container_width=True):
                result = runtime_controller.run_autonomous_cycle()
                st.success("Autonomous cycle completed.")
                st.json(result)

        with col2:
            if st.button("Runtime Snapshot", use_container_width=True):
                snapshot = runtime_controller.runtime_snapshot()
                st.success("Runtime snapshot created.")
                st.json(snapshot.as_dict())

        if plan is not None:
            st.subheader("Orchestrated Plan Execution")

            col3, col4 = st.columns(2)

            with col3:
                if st.button("Dry Run Current Plan", use_container_width=True):
                    result = orchestrator.execute_plan(plan, dry_run=True)
                    st.session_state["runtime_control_last_execution"] = result
                    st.success("Dry run completed.")
                    st.json(result.as_dict())

            with col4:
                if st.button("Execute Current Plan", use_container_width=True):
                    result = orchestrator.execute_plan(plan, dry_run=False)
                    st.session_state["runtime_control_last_execution"] = result
                    st.success("Execution completed.")
                    st.json(result.as_dict())

        last_execution = st.session_state.get("runtime_control_last_execution")
        if last_execution is not None:
            st.subheader("Last Execution Result")
            st.json(last_execution.as_dict())

    with tabs[7]:
        st.header("Governance")

        governor = getattr(analytics_fabric, "execution_governor", None)

        if governor is not None:
            st.json(_safe_call(governor.governance_summary, default={}))
        else:
            st.info("No execution governor attached.")

        st.divider()

        st.subheader("Governance Pressure Detection")

        if st.button("Detect Governance Pressure", use_container_width=True):
            incident = runtime_controller.detect_governance_pressure()
            st.json(_as_dict(incident) if incident else {"status": "NO_INCIDENT"})

    with tabs[8]:
        st.header("Recovery")

        if st.button("Run Recovery Cycle", use_container_width=True):
            result = runtime_controller.run_recovery_cycle()
            st.success("Recovery cycle completed.")
            st.json(result)

        st.divider()

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("Detect Runtime Failure", use_container_width=True):
                st.json(_as_dict(runtime_controller.detect_runtime_failure()) or {"status": "OK"})

        with col2:
            if st.button("Detect Capacity Pressure", use_container_width=True):
                st.json(_as_dict(runtime_controller.detect_capacity_pressure()) or {"status": "OK"})

        with col3:
            if st.button("Detect Provider Pressure", use_container_width=True):
                st.json(_as_dict(runtime_controller.detect_provider_pressure()) or {"status": "OK"})

        with col4:
            if st.button("Detect Queue Pressure", use_container_width=True):
                st.json(_as_dict(runtime_controller.detect_queue_pressure()) or {"status": "OK"})

        with col5:
            if st.button("Detect Governance Pressure", use_container_width=True):
                st.json(_as_dict(runtime_controller.detect_governance_pressure()) or {"status": "OK"})

        st.subheader("Recovery Plans")
        _table_from_records(
            [
                plan.as_dict()
                for plan in getattr(runtime_controller, "recovery_plans", [])
            ]
        )

    with tabs[9]:
        st.header("Incidents")

        incidents = _safe_call(runtime_controller.runtime_incidents, default=[])

        _table_from_records(incidents)

        st.divider()

        if incidents:
            selected_incident = st.selectbox(
                "Create Recovery Plan For Incident",
                [incident["incident_id"] for incident in incidents],
            )

            if st.button("Create Recovery Plan", use_container_width=True):
                incident = next(
                    item for item in incidents
                    if item["incident_id"] == selected_incident
                )
                plan = runtime_controller.create_recovery_plan(incident)
                st.success("Recovery plan created.")
                st.json(plan.as_dict())

    with tabs[10]:
        st.header("Decisions")

        decisions = _safe_call(runtime_controller.runtime_decisions, default=[])

        _table_from_records(decisions)

    with tabs[11]:
        st.header("Snapshots")

        snapshots = [
            snapshot.as_dict()
            for snapshot in getattr(runtime_controller, "snapshots", [])
        ]

        _table_from_records(snapshots)

        st.divider()

        if st.button("Create Runtime Snapshot", use_container_width=True):
            snapshot = runtime_controller.runtime_snapshot()
            st.success("Snapshot created.")
            st.json(snapshot.as_dict())

    with tabs[12]:
        st.header("Runtime Metrics")

        metrics = _safe_call(runtime_controller.runtime_metrics, default={})

        st.dataframe(
            pd.DataFrame(
                [{"Metric": key, "Value": value} for key, value in metrics.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pd.DataFrame(
            [
                ("Forecast", metrics.get("forecast_cycles", 0)),
                ("Optimization", metrics.get("optimization_cycles", 0)),
                ("Planning", metrics.get("planning_cycles", 0)),
                ("Execution", metrics.get("execution_cycles", 0)),
                ("Autonomous", metrics.get("autonomous_cycles", 0)),
                ("Recovery", metrics.get("recovery_cycles", 0)),
            ],
            columns=["Cycle", "Count"],
        )

        st.bar_chart(chart_df.set_index("Cycle"))

        if st.button("Save Runtime Metrics", use_container_width=True):
            runtime_controller.save_runtime_metrics()
            st.success("Runtime metrics saved.")

    with tabs[13]:
        st.header("Control Tower")

        try:
            from ui.admin.analytics_fabric_control_tower import (
                render_analytics_fabric_control_tower,
            )

            render_analytics_fabric_control_tower(
                fabric=analytics_fabric,
            )

        except Exception as exc:
            st.error(f"Unable to render control tower: {exc}")

    with tabs[14]:
        st.header("Exports")

        export_package = {
            "runtime_status": _safe_call(runtime_controller.runtime_status, default={}),
            "runtime_summary": _safe_call(runtime_controller.runtime_summary, default={}),
            "runtime_health": _safe_call(runtime_controller.runtime_health, default={}),
            "runtime_metrics": _safe_call(runtime_controller.runtime_metrics, default={}),
            "runtime_decisions": _safe_call(runtime_controller.runtime_decisions, default=[]),
            "runtime_incidents": _safe_call(runtime_controller.runtime_incidents, default=[]),
            "runtime_snapshots": [
                snapshot.as_dict()
                for snapshot in getattr(runtime_controller, "snapshots", [])
            ],
            "orchestrator_summary": _safe_call(orchestrator.execution_summary, default={}),
        }

        _download_json("Export Runtime State", export_package["runtime_status"])
        _download_json("Export Runtime Health", export_package["runtime_health"])
        _download_json("Export Runtime Metrics", export_package["runtime_metrics"])
        _download_json("Export Runtime Decisions", export_package["runtime_decisions"])
        _download_json("Export Runtime Incidents", export_package["runtime_incidents"])
        _download_json("Export Executive Runtime Package", export_package)

        st.json(export_package)


def render_runtime_control_center(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_runtime_control_center(
        analytics_fabric=analytics_fabric,
    )