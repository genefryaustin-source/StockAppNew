"""
modules/forex/forex_validation_scheduler_dashboard.py

Forex Validation Scheduler Dashboard
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.forex.forex_validation_scheduler import (
    ForexValidationScheduler,
)

from modules.forex.forex_validation_runtime_controller import (
    ForexValidationRuntimeController,
)

from modules.forex.forex_validation_operations_center import (
    ForexValidationOperationsCenter,
)


def _render_job_table():

    scheduler = ForexValidationScheduler()

    jobs = scheduler.list_jobs()

    st.subheader("Scheduled Validation Jobs")

    if jobs:

        df = pd.DataFrame(jobs)

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info("No validation jobs scheduled.")


def render_forex_validation_scheduler_dashboard(
    db=None,
    user=None,
):

    st.title("Forex Validation Scheduler Dashboard")

    scheduler = ForexValidationScheduler()

    runtime = ForexValidationRuntimeController()

    operations = ForexValidationOperationsCenter()

    col1, col2, col3, col4 = st.columns(4)

    if col1.button(
        "Schedule Full Validation",
        key="fx_val_sched_full",
    ):

        result = scheduler.schedule_full_validation()

        st.success("Validation scheduled.")

        st.json(result)

    if col2.button(
        "Schedule Nightly",
        key="fx_val_sched_nightly",
    ):

        result = scheduler.schedule_nightly_validation()

        st.success("Nightly validation scheduled.")

        st.json(result)

    if col3.button(
        "Schedule Release Validation",
        key="fx_val_sched_release",
    ):

        result = scheduler.schedule_release_validation()

        st.success("Release validation scheduled.")

        st.json(result)

    if col4.button(
        "Schedule Pre-Deployment",
        key="fx_val_sched_predeploy",
    ):

        result = scheduler.schedule_predeployment_validation()

        st.success("Pre-deployment validation scheduled.")

        st.json(result)

    st.divider()

    st.subheader("Runtime")

    max_jobs = st.slider(
        "Maximum Jobs Per Runtime Tick",
        min_value=1,
        max_value=50,
        value=5,
        key="fx_val_runtime_tick_jobs",
    )

    col1, col2 = st.columns(2)

    if col1.button(
        "Run Runtime Tick",
        key="fx_val_runtime_tick",
    ):

        result = runtime.tick(
            max_jobs=max_jobs,
        )

        st.json(result)

    if col2.button(
        "Run Validation Now",
        key="fx_val_runtime_now",
    ):

        result = runtime.run_once()

        st.json(result)

    st.divider()

    snapshot = operations.snapshot()

    metrics = snapshot["summary"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Scheduled Jobs",
        metrics.get("scheduled_jobs", 0),
    )

    c2.metric(
        "Validation Runs",
        metrics.get("validation_runs", 0),
    )

    c3.metric(
        "Passed Runs",
        metrics.get("passed_runs", 0),
    )

    c4.metric(
        "Failed Runs",
        metrics.get("failed_runs", 0),
    )

    st.divider()

    _render_job_table()

    with st.expander(
        "Operations Snapshot",
        expanded=False,
    ):

        st.json(snapshot)