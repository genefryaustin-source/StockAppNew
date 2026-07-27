"""
ui/admin/analytics_fabric_history_control_center.py
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
)
from modules.analytics.analytics_fabric_snapshot_scheduler import (
    AnalyticsFabricSnapshotScheduler,
    SNAPSHOT_BENCHMARK,
    SNAPSHOT_CAPACITY,
    SNAPSHOT_CONTROL_TOWER,
    SNAPSHOT_EXECUTIVE,
    SNAPSHOT_FABRIC_HEALTH,
    SNAPSHOT_GLOBAL_PLAN,
    SNAPSHOT_GOVERNANCE,
    SNAPSHOT_PROVIDER,
    SNAPSHOT_STRESS,
    SNAPSHOT_TENANT_INTELLIGENCE,
    SNAPSHOT_VALIDATION,
)


SNAPSHOT_TYPES = [
    SNAPSHOT_CONTROL_TOWER,
    SNAPSHOT_EXECUTIVE,
    SNAPSHOT_VALIDATION,
    SNAPSHOT_STRESS,
    SNAPSHOT_BENCHMARK,
    SNAPSHOT_CAPACITY,
    SNAPSHOT_PROVIDER,
    SNAPSHOT_GOVERNANCE,
    SNAPSHOT_GLOBAL_PLAN,
    SNAPSHOT_TENANT_INTELLIGENCE,
    SNAPSHOT_FABRIC_HEALTH,
]


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _get_persistence_engine(
    persistence_engine=None,
):
    if persistence_engine is not None:
        return persistence_engine

    if "analytics_history_engine" not in st.session_state:
        st.session_state[
            "analytics_history_engine"
        ] = AnalyticsFabricPersistenceEngine()

    return st.session_state[
        "analytics_history_engine"
    ]


def _get_snapshot_scheduler(
    persistence_engine,
    analytics_fabric=None,
    snapshot_scheduler=None,
):
    if snapshot_scheduler is not None:
        return snapshot_scheduler

    if "analytics_snapshot_scheduler" not in st.session_state:
        st.session_state[
            "analytics_snapshot_scheduler"
        ] = AnalyticsFabricSnapshotScheduler(
            persistence_engine=persistence_engine,
            analytics_fabric=analytics_fabric,
        )

    scheduler = st.session_state[
        "analytics_snapshot_scheduler"
    ]

    if analytics_fabric is not None:
        scheduler.analytics_fabric = analytics_fabric

    return scheduler


def _df(rows):
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _json_download_button(
    label: str,
    payload: Dict[str, Any],
):
    st.download_button(
        label,
        data=json.dumps(
            payload,
            indent=2,
            default=str,
        ),
        file_name=f"{label.lower().replace(' ', '_')}.json",
        mime="application/json",
        use_container_width=True,
    )


def render_analytics_fabric_history_control_center(
    analytics_fabric=None,
    persistence_engine=None,
    snapshot_scheduler=None,
):
    st.title(
        "Analytics Fabric History Control Center"
    )

    persistence_engine = (
        _get_persistence_engine(
            persistence_engine
        )
    )

    scheduler = (
        _get_snapshot_scheduler(
            persistence_engine=persistence_engine,
            analytics_fabric=analytics_fabric,
            snapshot_scheduler=snapshot_scheduler,
        )
    )

    summary = scheduler.snapshot_summary()
    health = scheduler.snapshot_health()

    history_summary = (
        persistence_engine.summary()
    )

    total_jobs = len(
        scheduler.job_registry()
    )

    active_jobs = len(
        [
            j
            for j in scheduler.job_registry()
            if j["enabled"]
        ]
    )

    paused_jobs = (
        total_jobs - active_jobs
    )

    cols = st.columns(8)

    cols[0].metric(
        "Snapshot Jobs",
        total_jobs,
    )

    cols[1].metric(
        "Active Jobs",
        active_jobs,
    )

    cols[2].metric(
        "Paused Jobs",
        paused_jobs,
    )

    cols[3].metric(
        "Snapshots Created",
        summary.get(
            "snapshots_created",
            0,
        ),
    )

    cols[4].metric(
        "History Records",
        sum(
            [
                history_summary.get(
                    "validation_records",
                    0,
                ),
                history_summary.get(
                    "stress_records",
                    0,
                ),
                history_summary.get(
                    "benchmark_records",
                    0,
                ),
                history_summary.get(
                    "capacity_records",
                    0,
                ),
                history_summary.get(
                    "provider_records",
                    0,
                ),
                history_summary.get(
                    "governance_records",
                    0,
                ),
                history_summary.get(
                    "plan_records",
                    0,
                ),
            ]
        ),
    )

    cols[5].metric(
        "Retention Days",
        scheduler.retention_days,
    )

    cols[6].metric(
        "Success %",
        health.get(
            "success_rate",
            0,
        ),
    )

    cols[7].metric(
        "Avg Runtime MS",
        round(
            summary.get(
                "average_runtime_ms",
                0.0,
            ),
            2,
        ),
    )

    tabs = st.tabs(
        [
            "Overview",
            "Snapshot Scheduler",
            "Retention Policies",
            "History Exports",
            "Archive Management",
            "Trend Analysis",
            "Historical Intelligence",
            "Health Monitoring",
        ]
    )

    with tabs[0]:
        st.subheader(
            "Historical Intelligence Overview"
        )

        st.json(
            {
                "snapshot_summary": summary,
                "snapshot_health": health,
                "history_summary": history_summary,
            }
        )

    with tabs[1]:
        st.subheader(
            "Snapshot Scheduler"
        )

        snapshot_type = st.selectbox(
            "Snapshot Type",
            SNAPSHOT_TYPES,
        )

        interval = st.number_input(
            "Interval Seconds",
            min_value=60,
            value=3600,
        )

        if st.button(
            "Register Snapshot Job",
            use_container_width=True,
        ):
            job_id = (
                scheduler.register_snapshot_job(
                    snapshot_type=snapshot_type,
                    interval_seconds=int(
                        interval
                    ),
                )
            )

            st.success(
                f"Registered {job_id}"
            )

        st.divider()

        jobs = scheduler.job_registry()

        if jobs:
            st.dataframe(
                _df(jobs),
                use_container_width=True,
                hide_index=True,
            )

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "Run Snapshot Cycle",
                use_container_width=True,
            ):
                result = (
                    scheduler.run_snapshot_cycle()
                )
                st.json(result)

        with col2:
            if st.button(
                "Run All Snapshots",
                use_container_width=True,
            ):
                result = (
                    scheduler.run_all_snapshots()
                )
                st.json(result)

        with col3:
            if st.button(
                "Refresh",
                use_container_width=True,
            ):
                st.rerun()

        st.divider()

        selected_job = st.selectbox(
            "Manage Job",
            [""] + [
                job["job_id"]
                for job in jobs
            ],
        )

        if selected_job:

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button(
                    "Pause Job",
                    use_container_width=True,
                ):
                    scheduler.pause_snapshot_job(
                        selected_job
                    )
                    st.rerun()

            with c2:
                if st.button(
                    "Resume Job",
                    use_container_width=True,
                ):
                    scheduler.resume_snapshot_job(
                        selected_job
                    )
                    st.rerun()

            with c3:
                if st.button(
                    "Remove Job",
                    use_container_width=True,
                ):
                    scheduler.remove_snapshot_job(
                        selected_job
                    )
                    st.rerun()

    with tabs[2]:
        st.subheader(
            "Retention Policies"
        )

        retention_days = (
            st.number_input(
                "Retention Days",
                min_value=1,
                value=scheduler.retention_days,
            )
        )

        max_history_records = (
            st.number_input(
                "Max History Records",
                min_value=100,
                value=scheduler.max_history_records,
            )
        )

        if st.button(
            "Apply Retention Policy",
            use_container_width=True,
        ):
            scheduler.retention_days = (
                retention_days
            )

            scheduler.max_history_records = (
                max_history_records
            )

            st.success(
                "Retention updated"
            )

        st.json(
            {
                "retention_days": scheduler.retention_days,
                "max_history_records": scheduler.max_history_records,
            }
        )

    with tabs[3]:
        st.subheader(
            "History Exports"
        )

        if st.button(
            "Export JSON Package",
            use_container_width=True,
        ):
            path = (
                "analytics_history_export.json"
            )

            persistence_engine.export_history_json(
                path
            )

            st.success(path)

        if st.button(
            "Export Excel Package",
            use_container_width=True,
        ):
            path = (
                "analytics_history_export.xlsx"
            )

            persistence_engine.export_history_excel(
                path
            )

            st.success(path)

        export_payload = {
            "history_summary": history_summary,
            "snapshot_summary": summary,
            "snapshot_health": health,
        }

        _json_download_button(
            "Export Intelligence Package",
            export_payload,
        )

    with tabs[4]:
        st.subheader(
            "Archive Management"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "Cleanup Expired Snapshots",
                use_container_width=True,
            ):
                result = (
                    scheduler.cleanup_expired_snapshots()
                )
                st.json(result)

        with col2:
            if st.button(
                "Archive Old Snapshots",
                use_container_width=True,
            ):
                result = (
                    scheduler.archive_old_snapshots()
                )
                st.json(result)

    with tabs[5]:
        st.subheader(
            "Trend Analysis"
        )

        trends = {
            "validation": persistence_engine.calculate_validation_trends(),
            "performance": persistence_engine.calculate_performance_trends(),
            "capacity": persistence_engine.calculate_capacity_trends(),
            "providers": persistence_engine.calculate_provider_cost_trends(),
            "governance": persistence_engine.calculate_governance_trends(),
            "health": persistence_engine.calculate_health_trends(),
        }

        st.json(trends)

    with tabs[6]:
        st.subheader(
            "Historical Intelligence"
        )

        intelligence = {
            "validation_history": len(
                persistence_engine.get_validation_history()
            ),
            "stress_history": len(
                persistence_engine.get_stress_history()
            ),
            "benchmark_history": len(
                persistence_engine.get_benchmark_history()
            ),
            "capacity_history": len(
                persistence_engine.get_capacity_history()
            ),
            "provider_history": len(
                persistence_engine.get_provider_history()
            ),
            "governance_history": len(
                persistence_engine.get_governance_history()
            ),
            "plan_history": len(
                persistence_engine.get_global_plan_history()
            ),
            "health_history": len(
                persistence_engine.get_fabric_health_history()
            ),
        }

        st.dataframe(
            _df(
                [
                    {
                        "Category": k,
                        "Records": v,
                    }
                    for k, v in intelligence.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[7]:
        st.subheader(
            "Health Monitoring"
        )

        st.json(health)

        st.divider()

        execution_history = (
            scheduler.execution_history()
        )

        if execution_history:
            st.dataframe(
                _df(execution_history),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        st.json(
            scheduler.snapshot_summary()
        )


def render_analytics_history_control_center(
    analytics_fabric=None,
    persistence_engine=None,
    snapshot_scheduler=None,
):
    render_analytics_fabric_history_control_center(
        analytics_fabric=analytics_fabric,
        persistence_engine=persistence_engine,
        snapshot_scheduler=snapshot_scheduler,
    )