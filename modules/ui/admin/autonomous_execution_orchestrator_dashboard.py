"""
ui/admin/autonomous_execution_orchestrator_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.analytics.autonomous_execution_orchestrator import (
    AutonomousExecutionOrchestrator,
)

from modules.analytics.autonomous_execution_planner import (
    AutonomousExecutionPlanner,
)

from modules.analytics.autonomous_forecast_optimizer import (
    AutonomousForecastOptimizer,
)

from modules.analytics.analytics_fabric_forecasting_engine import (
    AnalyticsFabricForecastingEngine,
)

from modules.analytics.analytics_fabric_persistence_engine import (
    AnalyticsFabricPersistenceEngine,
)


def _as_dict(obj):
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "as_dict"):
        return obj.as_dict()

    try:
        return asdict(obj)
    except Exception:
        return {"value": str(obj)}


def _download_button(
    label: str,
    payload: Any,
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


def _get_persistence_engine(engine=None):
    if engine:
        return engine

    if "analytics_persistence_engine" not in st.session_state:
        st.session_state[
            "analytics_persistence_engine"
        ] = AnalyticsFabricPersistenceEngine()

    return st.session_state[
        "analytics_persistence_engine"
    ]


def _get_forecasting_engine(
    persistence_engine,
    engine=None,
):
    if engine:
        return engine

    if "analytics_forecasting_engine" not in st.session_state:
        st.session_state[
            "analytics_forecasting_engine"
        ] = AnalyticsFabricForecastingEngine(
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "analytics_forecasting_engine"
    ]


def _get_optimizer(
    forecasting_engine,
    persistence_engine,
    optimizer=None,
):
    if optimizer:
        return optimizer

    if "analytics_optimizer" not in st.session_state:
        st.session_state[
            "analytics_optimizer"
        ] = AutonomousForecastOptimizer(
            forecasting_engine=forecasting_engine,
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "analytics_optimizer"
    ]


def _get_planner(
    optimizer,
    persistence_engine,
    planner=None,
):
    if planner:
        return planner

    if "analytics_execution_planner" not in st.session_state:
        st.session_state[
            "analytics_execution_planner"
        ] = AutonomousExecutionPlanner(
            forecast_optimizer=optimizer,
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "analytics_execution_planner"
    ]


def _get_orchestrator(
    planner,
    persistence_engine,
    orchestrator=None,
):
    if orchestrator:
        return orchestrator

    if "analytics_execution_orchestrator" not in st.session_state:
        st.session_state[
            "analytics_execution_orchestrator"
        ] = AutonomousExecutionOrchestrator(
            execution_planner=planner,
            persistence_engine=persistence_engine,
        )

    return st.session_state[
        "analytics_execution_orchestrator"
    ]


def _render_sessions(
    orchestrator,
):
    sessions = (
        orchestrator.session_registry()
    )

    if not sessions:
        st.info(
            "No execution sessions available."
        )
        return

    st.dataframe(
        pd.DataFrame(sessions),
        use_container_width=True,
        hide_index=True,
    )


def _render_audit(
    orchestrator,
):
    records = (
        orchestrator.audit_history()
    )

    if not records:
        st.info(
            "No audit records available."
        )
        return

    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
    )


def _render_results(
    orchestrator,
):
    results = (
        orchestrator.result_history()
    )

    if not results:
        st.info(
            "No execution history available."
        )
        return

    st.dataframe(
        pd.DataFrame(results),
        use_container_width=True,
        hide_index=True,
    )


def render_autonomous_execution_orchestrator_dashboard(
    analytics_fabric=None,
    persistence_engine=None,
    forecasting_engine=None,
    optimizer=None,
    planner=None,
    orchestrator=None,
):
    st.title(
        "Autonomous Execution Orchestrator"
    )

    persistence_engine = (
        _get_persistence_engine(
            persistence_engine
        )
    )

    forecasting_engine = (
        _get_forecasting_engine(
            persistence_engine,
            forecasting_engine,
        )
    )

    optimizer = (
        _get_optimizer(
            forecasting_engine,
            persistence_engine,
            optimizer,
        )
    )

    planner = (
        _get_planner(
            optimizer,
            persistence_engine,
            planner,
        )
    )

    orchestrator = (
        _get_orchestrator(
            planner,
            persistence_engine,
            orchestrator,
        )
    )

    if (
        "orchestrator_current_plan"
        not in st.session_state
    ):
        st.session_state[
            "orchestrator_current_plan"
        ] = None

    if (
        "orchestrator_current_result"
        not in st.session_state
    ):
        st.session_state[
            "orchestrator_current_result"
        ] = None

    plan = st.session_state[
        "orchestrator_current_plan"
    ]

    result = st.session_state[
        "orchestrator_current_result"
    ]

    metrics = (
        orchestrator.execution_summary()
    )

    cols = st.columns(8)

    cols[0].metric(
        "Started",
        metrics.get(
            "executions_started",
            0,
        ),
    )

    cols[1].metric(
        "Completed",
        metrics.get(
            "executions_completed",
            0,
        ),
    )

    cols[2].metric(
        "Failed",
        metrics.get(
            "executions_failed",
            0,
        ),
    )

    cols[3].metric(
        "Success Rate",
        f"{metrics.get('success_rate',0)*100:.1f}%",
    )

    cols[4].metric(
        "Avg Runtime",
        round(
            metrics.get(
                "average_execution_time_ms",
                0,
            ),
            2,
        ),
    )

    cols[5].metric(
        "Rollbacks",
        metrics.get(
            "rollbacks_triggered",
            0,
        ),
    )

    cols[6].metric(
        "Recoveries",
        metrics.get(
            "recoveries_triggered",
            0,
        ),
    )

    cols[7].metric(
        "Active",
        metrics.get(
            "active_sessions",
            0,
        ),
    )

    tabs = st.tabs(
        [
            "Overview",
            "Execution Sessions",
            "Execution Plans",
            "Execution Stages",
            "Execution Tasks",
            "Approval Center",
            "Live Execution",
            "Dry Run Console",
            "Rollback Center",
            "Recovery Center",
            "Audit Trail",
            "Execution History",
            "Metrics",
            "Exports",
        ]
    )

    with tabs[0]:

        st.subheader(
            "Execution Runtime Overview"
        )

        st.json(metrics)

    with tabs[1]:

        st.subheader(
            "Execution Sessions"
        )

        _render_sessions(
            orchestrator
        )

    with tabs[2]:

        st.subheader(
            "Execution Plans"
        )

        if st.button(
            "Generate Execution Plan",
            use_container_width=True,
        ):
            plan = (
                planner.build_execution_plan_from_optimizer()
            )

            st.session_state[
                "orchestrator_current_plan"
            ] = plan

            st.success(
                "Execution plan generated."
            )

            st.rerun()

        if plan:

            st.json(
                plan.as_dict()
            )

    with tabs[3]:

        st.subheader(
            "Execution Stages"
        )

        if plan:

            rows = []

            for stage in (
                orchestrator
                ._build_stages_from_plan(
                    plan
                )
            ):
                rows.append(
                    {
                        "Stage":
                            stage.stage_type,
                        "Status":
                            stage.status,
                        "Tasks":
                            len(
                                stage.tasks
                            ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[4]:

        st.subheader(
            "Execution Tasks"
        )

        if plan:

            rows = []

            for stage in (
                orchestrator
                ._build_stages_from_plan(
                    plan
                )
            ):
                for task in stage.tasks:

                    rows.append(
                        {
                            "Task":
                                task.task_id,
                            "Action":
                                task.action_type,
                            "Stage":
                                task.stage_type,
                            "Status":
                                task.status,
                        }
                    )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[5]:

        st.subheader(
            "Approval Center"
        )

        if plan:

            if st.button(
                "Approve Execution Plan",
                use_container_width=True,
            ):
                approved = (
                    planner.approve_plan(
                        plan
                    )
                )

                st.session_state[
                    "orchestrator_current_plan"
                ] = approved

                st.success(
                    "Plan approved."
                )

                st.rerun()

    with tabs[6]:

        st.subheader(
            "Live Execution"
        )

        if plan:

            if st.button(
                "Start Execution",
                use_container_width=True,
            ):
                result = (
                    orchestrator.execute_plan(
                        plan,
                        dry_run=False,
                    )
                )

                st.session_state[
                    "orchestrator_current_result"
                ] = result

                st.success(
                    "Execution completed."
                )

                st.rerun()

            if result:

                st.json(
                    result.as_dict()
                )

    with tabs[7]:

        st.subheader(
            "Dry Run Console"
        )

        if plan:

            if st.button(
                "Start Dry Run",
                use_container_width=True,
            ):
                result = (
                    orchestrator.execute_plan(
                        plan,
                        dry_run=True,
                    )
                )

                st.session_state[
                    "orchestrator_current_result"
                ] = result

                st.success(
                    "Dry run completed."
                )

                st.rerun()

    with tabs[8]:

        st.subheader(
            "Rollback Center"
        )

        sessions = (
            orchestrator.session_registry()
        )

        if sessions:

            selected = st.selectbox(
                "Session",
                [
                    s["session_id"]
                    for s in sessions
                ],
            )

            if st.button(
                "Rollback Execution",
                use_container_width=True,
            ):
                result = (
                    orchestrator.rollback_execution(
                        selected
                    )
                )

                st.json(result)

    with tabs[9]:

        st.subheader(
            "Recovery Center"
        )

        sessions = (
            orchestrator.session_registry()
        )

        if sessions:

            selected = st.selectbox(
                "Recover Session",
                [
                    s["session_id"]
                    for s in sessions
                ],
                key="recover_session",
            )

            if st.button(
                "Recover Execution",
                use_container_width=True,
            ):
                result = (
                    orchestrator.recover_execution(
                        selected
                    )
                )

                st.json(result)

    with tabs[10]:

        st.subheader(
            "Audit Trail"
        )

        _render_audit(
            orchestrator
        )

    with tabs[11]:

        st.subheader(
            "Execution History"
        )

        _render_results(
            orchestrator
        )

    with tabs[12]:

        st.subheader(
            "Runtime Metrics"
        )

        metrics_df = pd.DataFrame(
            [
                {
                    "Metric": k,
                    "Value": v,
                }
                for k, v in metrics.items()
            ]
        )

        st.dataframe(
            metrics_df,
            use_container_width=True,
            hide_index=True,
        )

        chart_df = pd.DataFrame(
            [
                (
                    "Started",
                    metrics.get(
                        "executions_started",
                        0,
                    ),
                ),
                (
                    "Completed",
                    metrics.get(
                        "executions_completed",
                        0,
                    ),
                ),
                (
                    "Failed",
                    metrics.get(
                        "executions_failed",
                        0,
                    ),
                ),
                (
                    "Rollbacks",
                    metrics.get(
                        "rollbacks_triggered",
                        0,
                    ),
                ),
                (
                    "Recoveries",
                    metrics.get(
                        "recoveries_triggered",
                        0,
                    ),
                ),
            ],
            columns=[
                "Metric",
                "Value",
            ],
        )

        st.bar_chart(
            chart_df.set_index(
                "Metric"
            )
        )

    with tabs[13]:

        st.subheader(
            "Exports"
        )

        export_package = {
            "metrics":
                metrics,
            "sessions":
                orchestrator.session_registry(),
            "audit":
                orchestrator.audit_history(),
            "results":
                orchestrator.result_history(),
            "current_plan":
                (
                    plan.as_dict()
                    if plan
                    else None
                ),
            "current_result":
                (
                    result.as_dict()
                    if result
                    else None
                ),
        }

        _download_button(
            "Export Executive Package",
            export_package,
        )

        _download_button(
            "Export Audit Trail",
            orchestrator.audit_history(),
        )

        _download_button(
            "Export Execution History",
            orchestrator.result_history(),
        )

        _download_button(
            "Export Runtime Metrics",
            metrics,
        )


def render_execution_orchestrator_dashboard(
    analytics_fabric=None,
):
    render_autonomous_execution_orchestrator_dashboard(
        analytics_fabric=analytics_fabric,
    )