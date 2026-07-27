from __future__ import annotations
import pandas as pd
import streamlit as st

try:
    from .forex_operations_center import ForexOperationsCenter
    from .forex_scheduler import ForexScheduler
    from .forex_runtime_controller import ForexRuntimeController
    from .forex_autonomous_optimizer import ForexAutonomousOptimizer
    from .forex_resource_governor import ForexResourceGovernor
    from .forex_control_plane import ForexControlPlane
    from .forex_common import default_pairs
except Exception:
    from forex_operations_center import ForexOperationsCenter
    from forex_scheduler import ForexScheduler
    from forex_runtime_controller import ForexRuntimeController
    from forex_autonomous_optimizer import ForexAutonomousOptimizer
    from forex_resource_governor import ForexResourceGovernor
    from forex_control_plane import ForexControlPlane
    from forex_common import default_pairs


def _render_snapshot(title: str = "Forex Operations Snapshot") -> None:
    center = ForexOperationsCenter()
    snap = center.snapshot()
    st.subheader(title)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", snap["summary"].get("total_jobs", 0))
    c2.metric("Open Jobs", snap["summary"].get("open_jobs", 0))
    c3.metric("Succeeded", snap["summary"].get("succeeded_jobs", 0))
    c4.metric("Failed", snap["summary"].get("failed_jobs", 0))

    if snap["jobs"]:
        st.caption("Latest Jobs")
        st.dataframe(pd.DataFrame(snap["jobs"]), use_container_width=True, hide_index=True)
    if snap["events"]:
        st.caption("Runtime Events")
        st.dataframe(pd.DataFrame(snap["events"]), use_container_width=True, hide_index=True)


def render_forex_scheduler_dashboard(  db=None,
    user=None,) -> None:
    st.title("Forex Scheduler Dashboard")
    pairs = st.multiselect("Schedule Pairs", default_pairs(), default=default_pairs()[:3], key="fx_sched_pairs")
    job_types = st.multiselect(
        "Job Types",
        ["market_snapshot", "spread_scan", "strength_scan", "risk_scan", "macro_regime", "sentiment_scan", "central_bank_scan", "carry_scan", "intermarket_scan"],
        default=["market_snapshot", "strength_scan", "risk_scan"],
        key="fx_sched_job_types",
    )
    enqueue = st.checkbox("Queue Immediately", value=True, key="fx_sched_enqueue")
    if st.button("Create Scheduled Jobs", key="fx_sched_create"):
        created = ForexScheduler().schedule_cycle(pairs=pairs, job_types=job_types, enqueue=enqueue)
        st.success(f"Created {len(created)} jobs.")
    _render_snapshot("Scheduler Queue")


if __name__ == "__main__":
    render_forex_scheduler_dashboard()
