"""
modules/forex/forex_validation_runtime_dashboard.py

Forex Validation Runtime Dashboard
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_validation_runtime_controller import (
    ForexValidationRuntimeController,
)

from modules.forex.forex_validation_operations_center import (
    ForexValidationOperationsCenter,
)

from modules.forex.forex_validation_resource_optimizer import (
    ForexValidationResourceOptimizer,
)

from modules.forex.forex_validation_cluster_manager import (
    cluster_manager,
)

from modules.forex.forex_validation_failover_manager import (
    ForexValidationFailoverManager,
)


def _render_metrics(snapshot: dict):

    summary = snapshot.get("summary", {})

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Runtime Jobs",
        summary.get("runtime_jobs", 0),
    )

    c2.metric(
        "Queued",
        summary.get("queued_jobs", 0),
    )

    c3.metric(
        "Completed",
        summary.get("completed_jobs", 0),
    )

    c4.metric(
        "Failed",
        summary.get("failed_jobs", 0),
    )

    c5.metric(
        "Workers",
        summary.get("workers", 0),
    )


def render_forex_validation_runtime_dashboard(
    db=None,
    user=None,
):

    st.title("Forex Validation Runtime Dashboard")

    runtime = ForexValidationRuntimeController()

    operations = ForexValidationOperationsCenter()

    optimizer = ForexValidationResourceOptimizer()

    failover = ForexValidationFailoverManager()

    cluster = cluster_manager()

    snapshot = operations.snapshot()

    _render_metrics(snapshot)

    st.divider()

    #######################################################################

    st.subheader("Runtime Control")

    max_jobs = st.slider(
        "Maximum Jobs Per Tick",
        min_value=1,
        max_value=100,
        value=10,
        key="fx_validation_runtime_max_jobs",
    )

    col1, col2, col3, col4 = st.columns(4)

    if col1.button(
        "Run Runtime Tick",
        key="fx_validation_runtime_tick",
    ):

        st.json(
            runtime.tick(
                max_jobs=max_jobs,
            )
        )

        st.rerun()

    if col2.button(
        "Run Single Validation",
        key="fx_validation_runtime_once",
    ):

        st.json(
            runtime.run_once()
        )

        st.rerun()

    if col3.button(
        "Heartbeat",
        key="fx_validation_runtime_heartbeat",
    ):

        st.json(
            cluster.heartbeat()
        )

    if col4.button(
        "Run Failover Recovery",
        key="fx_validation_runtime_failover",
    ):

        st.json(
            failover.run()
        )

    st.divider()

    #######################################################################

    st.subheader("Cluster Status")

    metrics = cluster.cluster_metrics()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Workers",
        metrics["workers"],
    )

    c2.metric(
        "Idle",
        metrics["idle_workers"],
    )

    c3.metric(
        "Active Jobs",
        metrics["active_jobs"],
    )

    c4.metric(
        "Queued Jobs",
        metrics["queued_jobs"],
    )

    workers = cluster.worker_snapshot()

    if workers:

        st.dataframe(
            pd.DataFrame(workers),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    #######################################################################

    st.subheader("Runtime Optimization")

    if st.button(
        "Analyze Runtime",
        key="fx_validation_runtime_analyze",
    ):

        st.json(
            optimizer.analyze()
        )

    if st.button(
        "Optimize Runtime",
        key="fx_validation_runtime_optimize",
    ):

        st.json(
            optimizer.optimize()
        )

    st.divider()

    #######################################################################

    with st.expander(
        "Operations Snapshot",
        expanded=False,
    ):

        st.json(snapshot)

    with st.expander(
        "Cluster Health",
        expanded=False,
    ):

        st.json(
            cluster.health()
        )

    with st.expander(
        "Failover Statistics",
        expanded=False,
    ):

        st.json(
            failover.statistics()
        )