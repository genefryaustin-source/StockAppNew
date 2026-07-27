"""
ui/admin/analytics_fabric_command_center.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

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


# ============================================================
# Helpers
# ============================================================

def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _download_json(label: str, payload: Any):
    st.download_button(
        label,
        data=json.dumps(payload, indent=2, default=str),
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )


def _records_table(records):
    if not records:
        st.info("No records available.")
        return

    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# Dependency Resolution
# ============================================================

def _get_persistence_engine(engine=None):
    if engine:
        return engine

    if "analytics_history_engine" not in st.session_state:
        st.session_state["analytics_history_engine"] = AnalyticsFabricPersistenceEngine()

    return st.session_state["analytics_history_engine"]


def _get_runtime_controller(
    analytics_fabric=None,
    persistence_engine=None,
    runtime_controller=None,
):
    if runtime_controller:
        return runtime_controller

    if "analytics_runtime_controller" not in st.session_state:
        st.session_state["analytics_runtime_controller"] = AnalyticsFabricRuntimeController(
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

    return st.session_state["analytics_runtime_controller"]


def _get_snapshot_scheduler(
    persistence_engine,
    analytics_fabric=None,
):
    if "analytics_snapshot_scheduler" not in st.session_state:
        st.session_state["analytics_snapshot_scheduler"] = AnalyticsFabricSnapshotScheduler(
            persistence_engine=persistence_engine,
            analytics_fabric=analytics_fabric,
        )

    return st.session_state["analytics_snapshot_scheduler"]


def _get_supervisor(
    runtime_controller,
    persistence_engine,
    snapshot_scheduler,
    analytics_fabric=None,
):
    if "analytics_supervisor" not in st.session_state:
        st.session_state["analytics_supervisor"] = AnalyticsFabricAutonomousSupervisor(
            runtime_controller=runtime_controller,
            execution_governor=getattr(analytics_fabric, "execution_governor", None),
            persistence_engine=persistence_engine,
            snapshot_scheduler=snapshot_scheduler,
        )

    return st.session_state["analytics_supervisor"]


def _get_continuous_runtime(
    supervisor,
    runtime_controller,
    snapshot_scheduler,
    persistence_engine,
):
    if "analytics_continuous_runtime" not in st.session_state:
        st.session_state["analytics_continuous_runtime"] = AnalyticsFabricContinuousRuntimeEngine(
            supervisor=supervisor,
            runtime_controller=runtime_controller,
            snapshot_scheduler=snapshot_scheduler,
            persistence_engine=persistence_engine,
        )

    return st.session_state["analytics_continuous_runtime"]


def _get_command_processor(
    continuous_runtime,
    supervisor,
    runtime_controller,
    persistence_engine,
    analytics_fabric=None,
):
    if "analytics_command_processor" not in st.session_state:
        st.session_state["analytics_command_processor"] = AnalyticsFabricCommandProcessor(
            continuous_runtime_engine=continuous_runtime,
            supervisor=supervisor,
            runtime_controller=runtime_controller,
            orchestrator=getattr(analytics_fabric, "execution_orchestrator", None),
            persistence_engine=persistence_engine,
        )

    return st.session_state["analytics_command_processor"]


# ============================================================
# Dashboard
# ============================================================

def render_analytics_fabric_command_center(
    analytics_fabric: Optional[Any] = None,
):
    st.title("Analytics Fabric Command Center")

    persistence_engine = _get_persistence_engine()

    runtime_controller = _get_runtime_controller(
        analytics_fabric=analytics_fabric,
        persistence_engine=persistence_engine,
    )

    snapshot_scheduler = _get_snapshot_scheduler(
        persistence_engine=persistence_engine,
        analytics_fabric=analytics_fabric,
    )

    supervisor = _get_supervisor(
        runtime_controller,
        persistence_engine,
        snapshot_scheduler,
        analytics_fabric,
    )

    continuous_runtime = _get_continuous_runtime(
        supervisor,
        runtime_controller,
        snapshot_scheduler,
        persistence_engine,
    )

    command_processor = _get_command_processor(
        continuous_runtime,
        supervisor,
        runtime_controller,
        persistence_engine,
        analytics_fabric,
    )

    metrics = command_processor.command_metrics()

    cols = st.columns(8)

    cols[0].metric("Commands", metrics["commands_total"])
    cols[1].metric("Executed", metrics["commands_executed"])
    cols[2].metric("Failed", metrics["commands_failed"])
    cols[3].metric("Approved", metrics["commands_approved"])
    cols[4].metric("Rejected", metrics["commands_rejected"])
    cols[5].metric("Pending", metrics["pending_approval"])
    cols[6].metric("Batches", metrics["batches_total"])
    cols[7].metric("Success Rate", metrics["success_rate"])

    tabs = st.tabs(
        [
            "Command Submission",
            "Batch Commands",
            "Approval Queue",
            "Execution",
            "Results",
            "Audit Trail",
            "Metrics",
            "Exports",
        ]
    )

    # =====================================================
    # Command Submission
    # =====================================================

    with tabs[0]:
        st.header("Submit Command")

        command_type = st.selectbox(
            "Command Type",
            [c.value for c in AnalyticsCommandType],
        )

        requested_by = st.text_input(
            "Requested By",
            value="admin",
        )

        severity = st.selectbox(
            "Severity",
            ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
            index=0,
        )

        requires_approval = st.checkbox(
            "Requires Approval",
            value=False,
        )

        payload_json = st.text_area(
            "Payload (JSON)",
            value="{}",
            height=150,
        )

        execute_immediately = st.checkbox(
            "Execute Immediately",
            value=False,
        )

        if st.button("Submit Command", use_container_width=True):

            try:
                payload = json.loads(payload_json)

                command = command_processor.submit_command(
                    command_type=command_type,
                    requested_by=requested_by,
                    payload=payload,
                    severity=severity,
                    requires_approval=requires_approval,
                    execute_immediately=execute_immediately,
                )

                st.success(f"Command Submitted: {command.command_id}")
                st.json(command.as_dict())

            except Exception as exc:
                st.error(str(exc))

    # =====================================================
    # Batch Commands
    # =====================================================

    with tabs[1]:
        st.header("Batch Commands")

        sample = [
            {
                "command_type": "RUN_FORECAST",
                "payload": {},
            },
            {
                "command_type": "RUN_OPTIMIZATION",
                "payload": {},
            },
        ]

        batch_json = st.text_area(
            "Batch JSON",
            value=json.dumps(sample, indent=2),
            height=250,
        )

        execute_batch = st.checkbox(
            "Execute Batch Immediately",
            value=False,
        )

        if st.button("Submit Batch", use_container_width=True):

            try:
                commands = json.loads(batch_json)

                batch = command_processor.submit_batch(
                    commands,
                    execute_immediately=execute_batch,
                )

                st.success(f"Batch Created: {batch.batch_id}")
                st.json(batch.as_dict())

            except Exception as exc:
                st.error(str(exc))

        st.divider()

        st.subheader("Batch History")

        _records_table(
            command_processor.command_batch_history()
        )

    # =====================================================
    # Approval Queue
    # =====================================================

    with tabs[2]:
        st.header("Approval Queue")

        commands = command_processor.command_history()

        pending = [
            c for c in commands
            if c["status"] == "PENDING_APPROVAL"
        ]

        _records_table(pending)

        if pending:

            selected = st.selectbox(
                "Command",
                [p["command_id"] for p in pending],
            )

            reason = st.text_input(
                "Reason",
                value="Approved by operator",
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Approve", use_container_width=True):

                    command_processor.approve_command(
                        selected,
                        approved_by="admin",
                        reason=reason,
                    )

                    st.success("Approved")
                    st.rerun()

            with col2:
                if st.button("Reject", use_container_width=True):

                    command_processor.reject_command(
                        selected,
                        rejected_by="admin",
                        reason=reason,
                    )

                    st.warning("Rejected")
                    st.rerun()

    # =====================================================
    # Execution
    # =====================================================

    with tabs[3]:
        st.header("Execute Commands")

        commands = command_processor.command_history()

        executable = [
            c for c in commands
            if c["status"] in [
                "RECEIVED",
                "APPROVED",
            ]
        ]

        _records_table(executable)

        if executable:

            selected = st.selectbox(
                "Executable Command",
                [c["command_id"] for c in executable],
            )

            if st.button(
                "Execute Command",
                use_container_width=True,
            ):
                result = command_processor.execute_command(selected)

                st.success("Command Executed")
                st.json(result.as_dict())

    # =====================================================
    # Results
    # =====================================================

    with tabs[4]:
        st.header("Command Results")

        _records_table(
            command_processor.command_result_history()
        )

    # =====================================================
    # Audit
    # =====================================================

    with tabs[5]:
        st.header("Command Audit Trail")

        _records_table(
            command_processor.command_audit_history()
        )

        st.divider()

        st.subheader("Executions")

        _records_table(
            command_processor.command_execution_history()
        )

    # =====================================================
    # Metrics
    # =====================================================

    with tabs[6]:
        st.header("Command Metrics")

        metrics = command_processor.command_metrics()

        st.json(metrics)

        chart_df = pd.DataFrame(
            [
                ("Received", metrics["commands_received"]),
                ("Executed", metrics["commands_executed"]),
                ("Failed", metrics["commands_failed"]),
                ("Approved", metrics["commands_approved"]),
                ("Rejected", metrics["commands_rejected"]),
                ("Batch", metrics["batch_commands_executed"]),
            ],
            columns=["Metric", "Value"],
        )

        st.bar_chart(
            chart_df.set_index("Metric")
        )

    # =====================================================
    # Exports
    # =====================================================

    with tabs[7]:
        st.header("Exports")

        command_history = command_processor.command_history()
        results = command_processor.command_result_history()
        audits = command_processor.command_audit_history()
        executions = command_processor.command_execution_history()

        package = command_processor.export_executive_package()

        _download_json(
            "Export Commands",
            command_history,
        )

        _download_json(
            "Export Results",
            results,
        )

        _download_json(
            "Export Audit",
            audits,
        )

        _download_json(
            "Export Executions",
            executions,
        )

        _download_json(
            "Export Executive Package",
            package,
        )

        st.json(package)


def render_command_center(
    analytics_fabric=None,
):
    render_analytics_fabric_command_center(
        analytics_fabric=analytics_fabric,
    )