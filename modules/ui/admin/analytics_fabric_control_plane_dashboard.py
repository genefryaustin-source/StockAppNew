"""
ui/admin/analytics_fabric_control_plane_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_control_plane import (
    AnalyticsFabricControlPlane,
    ControlPlaneServiceType,
)

from modules.analytics.analytics_fabric_command_processor import (
    AnalyticsFabricCommandProcessor,
    AnalyticsCommandType,
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


def _records_table(records) -> None:
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
            metadata={"source": "control_plane_dashboard"},
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


def render_analytics_fabric_control_plane_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    snapshot_scheduler: Optional[Any] = None,
    supervisor: Optional[Any] = None,
    continuous_runtime: Optional[Any] = None,
    command_processor: Optional[Any] = None,
    control_plane: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Control Plane")

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

    status = _safe_call(control_plane.global_status, default={})
    health = status.get("health", {})
    metrics = status.get("metrics", {})

    cols = st.columns(9)

    cols[0].metric("State", status.get("state", {}).get("state", "—"))
    cols[1].metric("Health", health.get("health_score", 0))
    cols[2].metric("Services", metrics.get("registered_services", 0))
    cols[3].metric("Active", metrics.get("active_services", 0))
    cols[4].metric("Degraded", metrics.get("degraded_services", 0))
    cols[5].metric("Failed", metrics.get("failed_services", 0))
    cols[6].metric("Commands", metrics.get("commands_processed", 0))
    cols[7].metric("Snapshots", metrics.get("snapshots_created", 0))
    cols[8].metric("Uptime", metrics.get("uptime_seconds", 0))

    tabs = st.tabs(
        [
            "Global Status",
            "Global Health",
            "Service Inventory",
            "Service Registration",
            "Platform Lifecycle",
            "Command Routing",
            "Recovery",
            "Snapshots",
            "Events",
            "Metrics",
            "Executive Export",
        ]
    )

    with tabs[0]:
        st.header("Global Status")
        st.json(status)

    with tabs[1]:
        st.header("Global Health")

        _metric_row(
            health,
            [
                "health_score",
                "registered_services",
                "active_services",
                "degraded_services",
                "failed_services",
                "stopped_services",
            ],
        )

        st.divider()

        inventory = _safe_call(control_plane.service_inventory, default=[])

        if inventory:
            health_df = pd.DataFrame(
                [
                    {
                        "Service": item.get("name"),
                        "Health": item.get("health_score", 0),
                    }
                    for item in inventory
                ]
            )
            st.bar_chart(health_df.set_index("Service"))

        st.json(health)

    with tabs[2]:
        st.header("Service Inventory")

        inventory = _safe_call(control_plane.service_inventory, default=[])

        _records_table(inventory)

        st.divider()

        if inventory:
            selected_service = st.selectbox(
                "Inspect Service",
                [item["service_id"] for item in inventory],
            )

            if st.button("Refresh Service Status", use_container_width=True):
                st.json(control_plane.service_status(selected_service))

    with tabs[3]:
        st.header("Service Registration")

        service_type = st.selectbox(
            "Service Type",
            [item.value for item in ControlPlaneServiceType],
        )

        service_name = st.text_input(
            "Service Name",
            value="External Analytics Service",
        )

        priority = st.number_input(
            "Priority",
            min_value=1,
            value=200,
        )

        metadata_json = st.text_area(
            "Metadata JSON",
            value="{}",
            height=120,
        )

        if st.button("Register Placeholder Service", use_container_width=True):
            try:
                metadata = json.loads(metadata_json)

                service = control_plane.register_service(
                    service_type=service_type,
                    name=service_name,
                    instance=None,
                    priority=int(priority),
                    metadata=metadata,
                )

                st.success("Service registered.")
                st.json(service.as_dict())

            except Exception as exc:
                st.error(str(exc))

        st.divider()

        registrations = _safe_call(control_plane.registration_history, default=[])

        st.subheader("Registration History")
        _records_table(registrations)

    with tabs[4]:
        st.header("Platform Lifecycle")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("Platform Start", use_container_width=True):
                st.json(control_plane.platform_start())

        with col2:
            if st.button("Platform Pause", use_container_width=True):
                st.json(control_plane.platform_pause())

        with col3:
            if st.button("Platform Resume", use_container_width=True):
                st.json(control_plane.platform_resume())

        with col4:
            if st.button("Platform Stop", use_container_width=True):
                st.json(control_plane.platform_stop())

        st.divider()

        st.subheader("Current Lifecycle State")
        st.json(_as_dict(control_plane.state))

    with tabs[5]:
        st.header("Command Routing")

        command_type = st.selectbox(
            "Command Type",
            [item.value for item in AnalyticsCommandType],
        )

        payload_json = st.text_area(
            "Payload JSON",
            value="{}",
            height=120,
        )

        execute_immediately = st.checkbox(
            "Execute Immediately",
            value=True,
        )

        if st.button("Route Command Through Control Plane", use_container_width=True):
            try:
                payload = json.loads(payload_json)

                result = control_plane.route_command(
                    command_type,
                    payload=payload,
                    execute_immediately=execute_immediately,
                )

                st.success("Command routed.")
                st.json(result)

            except Exception as exc:
                st.error(str(exc))

        st.divider()

        st.subheader("Command Processor Metrics")
        st.json(_safe_call(command_processor.command_metrics, default={}))

        st.subheader("Recent Commands")
        _records_table(_safe_call(command_processor.command_history, default=[]))

    with tabs[6]:
        st.header("Recovery")

        if st.button("Run Control Plane Recovery", use_container_width=True):
            result = control_plane.control_plane_recovery()
            st.success("Recovery completed.")
            st.json(result)

        st.divider()

        st.subheader("Runtime Incidents")
        st.json(_safe_call(runtime_controller.runtime_incidents, default=[]))

        st.subheader("Supervisor Incidents")
        st.json(_safe_call(supervisor.incident_history, default=[]))

    with tabs[7]:
        st.header("Snapshots")

        if st.button("Create Control Plane Snapshot", use_container_width=True):
            snapshot = control_plane.create_snapshot()
            st.success("Snapshot created.")
            st.json(snapshot.as_dict())

        st.divider()

        _records_table(_safe_call(control_plane.snapshot_history, default=[]))

    with tabs[8]:
        st.header("Events")

        _records_table(_safe_call(control_plane.event_history, default=[]))

    with tabs[9]:
        st.header("Metrics")

        metrics = _safe_call(control_plane.control_plane_metrics, default={})

        st.dataframe(
            pd.DataFrame(
                [{"Metric": key, "Value": value} for key, value in metrics.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pd.DataFrame(
            [
                ("Registered", metrics.get("registered_services", 0)),
                ("Active", metrics.get("active_services", 0)),
                ("Degraded", metrics.get("degraded_services", 0)),
                ("Failed", metrics.get("failed_services", 0)),
                ("Commands", metrics.get("commands_processed", 0)),
                ("Snapshots", metrics.get("snapshots_created", 0)),
                ("Recoveries", metrics.get("recoveries_triggered", 0)),
            ],
            columns=["Metric", "Value"],
        )

        st.bar_chart(chart_df.set_index("Metric"))

    with tabs[10]:
        st.header("Executive Export")

        export_state = _safe_call(control_plane.export_state, default={})
        executive_package = _safe_call(control_plane.export_executive_package, default={})

        _download_json("Export Control Plane State", export_state)
        _download_json("Export Executive Control Plane Package", executive_package)
        _download_json("Export Service Inventory", _safe_call(control_plane.service_inventory, default=[]))
        _download_json("Export Events", _safe_call(control_plane.event_history, default=[]))
        _download_json("Export Snapshots", _safe_call(control_plane.snapshot_history, default=[]))
        _download_json("Export Metrics", _safe_call(control_plane.control_plane_metrics, default={}))

        st.subheader("Executive Package Preview")
        st.json(executive_package)


def render_control_plane_dashboard(
    analytics_fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_control_plane_dashboard(
        analytics_fabric=analytics_fabric,
    )