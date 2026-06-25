from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _is_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    return bool(payload.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "saved", "exported", "scheduled"
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

try:
    import streamlit as st
except Exception:
    st = None

try:
    import pandas as pd
except Exception:
    pd = None


class ForexValidationCommandCenter:
    """Programmatic command interface for Forex validation operations."""

    def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        Scheduler = _safe_import("modules.forex.forex_validation_scheduler", "ForexValidationScheduler")
        Runtime = _safe_import("modules.forex.forex_validation_runtime_controller", "ForexValidationRuntimeController")
        Ops = _safe_import("modules.forex.forex_validation_operations_center", "ForexValidationOperationsCenter")
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")

        command = command.lower().strip()

        if command == "schedule_full":
            return Scheduler().schedule_full_validation()
        if command == "schedule_nightly":
            return Scheduler().schedule_nightly_validation()
        if command == "schedule_predeployment":
            return Scheduler().schedule_predeployment_validation()
        if command == "schedule_release":
            return Scheduler().schedule_release_validation()
        if command == "run_tick":
            return Runtime().tick(max_jobs=int(kwargs.get("max_jobs", 5)))
        if command == "run_now":
            return Runtime().run_once(
                include_stress=bool(kwargs.get("include_stress", False)),
                stress_jobs=int(kwargs.get("stress_jobs", 100)),
            )
        if command == "release_tick":
            return Runtime().release_tick()
        if command == "snapshot":
            return Ops().snapshot()
        if command == "clear":
            return Ops().clear_validation_state()
        if command == "reports":
            payload = Center().run_full_validation()
            return Center().generate_reports(payload)

        return {"status": "unknown_command", "command": command, "checked_at": _utc_now()}


def render_forex_validation_command_center(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Command Center")
    st.caption("Schedule, execute, inspect, and report Forex validation operations.")

    command_center = ForexValidationCommandCenter()

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Schedule Full", key="fx_val_cmd_schedule_full"):
        st.json(command_center.execute("schedule_full"))
    if c2.button("Schedule Nightly", key="fx_val_cmd_schedule_nightly"):
        st.json(command_center.execute("schedule_nightly"))
    if c3.button("Schedule Predeployment", key="fx_val_cmd_schedule_predeployment"):
        st.json(command_center.execute("schedule_predeployment"))
    if c4.button("Schedule Release", key="fx_val_cmd_schedule_release"):
        st.json(command_center.execute("schedule_release"))

    st.divider()
    max_jobs = st.slider("Max Validation Jobs Per Tick", 1, 25, 5, key="fx_val_cmd_max_jobs")
    stress_jobs = st.selectbox("Stress Jobs", [100, 500, 1000, 5000], key="fx_val_cmd_stress_jobs")
    include_stress = st.checkbox("Include Stress", value=False, key="fx_val_cmd_include_stress")

    r1, r2, r3, r4 = st.columns(4)
    if r1.button("Run Pending Tick", key="fx_val_cmd_run_tick"):
        st.json(command_center.execute("run_tick", max_jobs=max_jobs))
    if r2.button("Run Now", key="fx_val_cmd_run_now"):
        st.json(command_center.execute("run_now", include_stress=include_stress, stress_jobs=stress_jobs))
    if r3.button("Release Tick", key="fx_val_cmd_release_tick"):
        st.json(command_center.execute("release_tick"))
    if r4.button("Generate Reports", key="fx_val_cmd_reports"):
        st.json(command_center.execute("reports"))

    st.divider()
    snapshot = command_center.execute("snapshot")
    summary = snapshot.get("summary", {})
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jobs", summary.get("scheduled_jobs", 0))
    m2.metric("Runs", summary.get("validation_runs", 0))
    m3.metric("Passed", summary.get("passed_runs", 0))
    m4.metric("Failed", summary.get("failed_runs", 0))

    runs = snapshot.get("runs", [])
    if runs:
        st.subheader("Validation Runs")
        rows = [
            {
                "run_id": r.get("run_id"),
                "status": r.get("status"),
                "passed": r.get("passed"),
                "completed_at": r.get("completed_at"),
            }
            for r in runs
        ]
        if pd is not None:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.json(rows)

    notes = snapshot.get("notifications", [])
    if notes:
        st.subheader("Notifications")
        if pd is not None:
            st.dataframe(pd.DataFrame(notes), use_container_width=True, hide_index=True)
        else:
            st.json(notes)
