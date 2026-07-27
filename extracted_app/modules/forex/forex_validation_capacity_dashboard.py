from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _status_ok(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = str(value.get("status", "")).lower()
    return bool(value.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "approved", "online", "optimized"
    }

try:
    import streamlit as st
except Exception:
    st = None

try:
    import pandas as pd
except Exception:
    pd = None


def render_forex_validation_capacity_dashboard(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Capacity Dashboard")
    st.caption("Capacity planning, resource optimization, queue sizing, SLA, and SLO posture.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Analyze Capacity", key="fx_val_capacity_analyze"):
            Planner = _safe_import(
                "modules.forex.forex_validation_capacity_planner",
                "ForexValidationCapacityPlanner",
            )
            st.session_state["fx_val_capacity_result"] = Planner().analyze()

    with col2:
        if st.button("Optimize Resources", key="fx_val_capacity_optimize"):
            Optimizer = _safe_import(
                "modules.forex.forex_validation_resource_optimizer",
                "ForexValidationResourceOptimizer",
            )
            st.session_state["fx_val_capacity_result"] = Optimizer().optimize()

    with col3:
        if st.button("Refresh SLO", key="fx_val_capacity_slo"):
            SLO = _safe_import(
                "modules.forex.forex_validation_slo_engine",
                "ForexValidationSLOEngine",
            )
            st.session_state["fx_val_capacity_slo"] = SLO().calculate()

    st.divider()

    Ops = _safe_import(
        "modules.forex.forex_validation_operations_center",
        "ForexValidationOperationsCenter",
    )
    snapshot = Ops().snapshot()
    summary = snapshot.get("summary", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Scheduled Jobs", summary.get("scheduled_jobs", 0))
    m2.metric("Validation Runs", summary.get("validation_runs", 0))
    m3.metric("Passed Runs", summary.get("passed_runs", 0))
    m4.metric("Failed Runs", summary.get("failed_runs", 0))

    st.subheader("Capacity Result")
    st.json(st.session_state.get("fx_val_capacity_result", {"status": "not_run"}))

    st.subheader("SLA / SLO")
    SLA = _safe_import(
        "modules.forex.forex_validation_sla_engine",
        "ForexValidationSLAEngine",
    )
    SLO = _safe_import(
        "modules.forex.forex_validation_slo_engine",
        "ForexValidationSLOEngine",
    )

    sla_result = SLA().evaluate_operations()
    slo_result = st.session_state.get("fx_val_capacity_slo") or SLO().calculate()
    error_budget = SLO().error_budget()

    c1, c2, c3 = st.columns(3)
    c1.metric("SLA", sla_result.get("status", "unknown").upper())
    c2.metric("SLO", slo_result.get("status", "unknown").upper())
    c3.metric("Error Budget", error_budget.get("error_budget_remaining", 0))

    with st.expander("SLA Details", expanded=False):
        st.json(sla_result)

    with st.expander("SLO Details", expanded=False):
        st.json(slo_result)

    runs = snapshot.get("runs", [])
    if runs:
        st.subheader("Recent Validation Runs")
        rows = [
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "passed": run.get("passed"),
                "completed_at": run.get("completed_at"),
            }
            for run in runs
        ]
        if pd is not None:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.json(rows)
