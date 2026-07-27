"""
modules/forex/forex_validation_operations_dashboard.py

Forex Validation Operations Dashboard
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_validation_operations_center import (
    ForexValidationOperationsCenter,
)

from modules.forex.forex_validation_runtime_controller import (
    ForexValidationRuntimeController,
)

from modules.forex.forex_validation_scheduler import (
    ForexValidationScheduler,
)

from modules.forex.forex_validation_notification_engine import (
    ForexValidationNotificationEngine,
)

from modules.forex.forex_validation_sla_engine import (
    ForexValidationSLAEngine,
)

from modules.forex.forex_validation_slo_engine import (
    ForexValidationSLOEngine,
)

from modules.forex.forex_validation_resource_optimizer import (
    ForexValidationResourceOptimizer,
)


def _render_summary(snapshot: dict):

    summary = snapshot.get("summary", {})

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Scheduled Jobs",
        summary.get("scheduled_jobs", 0),
    )

    c2.metric(
        "Validation Runs",
        summary.get("validation_runs", 0),
    )

    c3.metric(
        "Passed",
        summary.get("passed_runs", 0),
    )

    c4.metric(
        "Failed",
        summary.get("failed_runs", 0),
    )

    c5.metric(
        "Notifications",
        summary.get("notifications", 0),
    )


def _render_table(title: str, rows):

    st.subheader(title)

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(f"No {title.lower()} available.")


def render_forex_validation_operations_dashboard(
    db=None,
    user=None,
):

    st.title("Forex Validation Operations Dashboard")

    operations = ForexValidationOperationsCenter()

    runtime = ForexValidationRuntimeController()

    scheduler = ForexValidationScheduler()

    notifications = ForexValidationNotificationEngine()

    optimizer = ForexValidationResourceOptimizer()

    snapshot = operations.snapshot()

    _render_summary(snapshot)

    st.divider()

    ###################################################################

    st.subheader("Validation Operations")

    col1, col2, col3, col4 = st.columns(4)

    if col1.button(
        "Run Runtime Tick",
        key="fx_val_ops_tick",
    ):

        st.json(runtime.tick())

        st.rerun()

    if col2.button(
        "Run Validation",
        key="fx_val_ops_run",
    ):

        st.json(runtime.run_once())

        st.rerun()

    if col3.button(
        "Schedule Validation",
        key="fx_val_ops_schedule",
    ):

        st.json(
            scheduler.schedule_full_validation()
        )

        st.rerun()

    if col4.button(
        "Optimize Resources",
        key="fx_val_ops_optimize",
    ):

        st.json(
            optimizer.optimize()
        )

    st.divider()

    ###################################################################

    sla = ForexValidationSLAEngine().evaluate_operations()

    slo = ForexValidationSLOEngine().calculate()

    c1, c2 = st.columns(2)

    with c1:

        st.subheader("SLA")

        st.json(sla)

    with c2:

        st.subheader("SLO")

        st.json(slo)

    st.divider()

    ###################################################################

    _render_table(
        "Scheduled Jobs",
        snapshot.get("jobs", []),
    )

    _render_table(
        "Validation Runs",
        snapshot.get("runs", []),
    )

    _render_table(
        "Notifications",
        notifications.list_notifications(),
    )

    st.divider()

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
            optimizer.analyze()
        )