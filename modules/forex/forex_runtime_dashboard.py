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


def render_forex_runtime_dashboard(
    db=None,
    user=None,
) -> None:

    st.title("Forex Runtime Dashboard")

    max_jobs = st.slider(
        "Max Jobs Per Tick",
        1,
        100,
        10,
        key="fx_runtime_max_jobs",
    )

    if st.button(
        "Run Runtime Tick",
        key="fx_runtime_tick",
    ):
        st.json(
            ForexRuntimeController().tick(
                max_jobs=max_jobs
            )
        )

    _render_snapshot("Runtime State")


if __name__ == "__main__":
    render_forex_runtime_dashboard()
