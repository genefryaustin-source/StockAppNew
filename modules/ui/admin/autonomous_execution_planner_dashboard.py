"""
ui/admin/autonomous_execution_planner_dashboard.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.analytics.autonomous_execution_planner import (
    AutonomousExecutionPlanner,
    ExecutionPlannerPolicy,
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


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "as_dict"):
        return value.as_dict()

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    return {"value": str(value)}


def _get_persistence_engine(engine=None):
    if engine is not None:
        return engine

    if "analytics_history_engine" not in st.session_state:
        st.session_state["analytics_history_engine"] = (
            AnalyticsFabricPersistenceEngine()
        )

    return st.session_state["analytics_history_engine"]


def _get_forecasting_engine(
    persistence_engine,
    forecasting_engine=None,
):
    if forecasting_engine is not None:
        return forecasting_engine

    if "analytics_forecasting_engine" not in st.session_state:
        st.session_state["analytics_forecasting_engine"] = (
            AnalyticsFabricForecastingEngine(
                persistence_engine=persistence_engine,
            )
        )

    return st.session_state["analytics_forecasting_engine"]


def _get_forecast_optimizer(
    forecasting_engine,
    persistence_engine,
    forecast_optimizer=None,
):
    if forecast_optimizer is not None:
        return forecast_optimizer

    if "autonomous_forecast_optimizer" not in st.session_state:
        st.session_state["autonomous_forecast_optimizer"] = (
            AutonomousForecastOptimizer(
                forecasting_engine=forecasting_engine,
                persistence_engine=persistence_engine,
            )
        )

    return st.session_state["autonomous_forecast_optimizer"]


def _get_execution_planner(
    persistence_engine,
    forecasting_engine,
    forecast_optimizer,
    analytics_fabric=None,
    execution_planner=None,
):
    if execution_planner is not None:
        return execution_planner

    if "autonomous_execution_planner" not in st.session_state:
        st.session_state["autonomous_execution_planner"] = (
            AutonomousExecutionPlanner(
                analytics_fabric=analytics_fabric,
                forecast_optimizer=forecast_optimizer,
                forecasting_engine=forecasting_engine,
                persistence_engine=persistence_engine,
            )
        )

    planner = st.session_state["autonomous_execution_planner"]

    planner.analytics_fabric = analytics_fabric
    planner.forecast_optimizer = forecast_optimizer
    planner.forecasting_engine = forecasting_engine
    planner.persistence_engine = persistence_engine

    return planner


def _json_download(
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
        file_name=(
            f"{label.lower().replace(' ', '_')}_"
            f"{int(time.time())}.json"
        ),
        mime="application/json",
        use_container_width=True,
    )


def _render_action_table(actions):
    if not actions:
        st.info("No actions available.")
        return

    rows = []

    for action in actions:
        data = _as_dict(action)

        rows.append(
            {
                "Action ID": data.get("action_id"),
                "Type": data.get("action_type"),
                "Title": data.get("title"),
                "Severity": data.get("severity"),
                "Status": data.get("status"),
                "Priority": data.get("priority"),
                "Requires Approval": data.get("requires_approval"),
                "Autonomous Allowed": data.get("autonomous_allowed"),
                "Expected Impact": data.get("expected_impact"),
                "Confidence": data.get("confidence_score"),
                "Generated At": data.get("generated_at"),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def _render_plan_summary(plan):
    if plan is None:
        st.info("No execution plan generated.")
        return

    plan_data = _as_dict(plan)

    cols = st.columns(7)

    cols[0].metric(
        "State",
        plan_data.get("state", "—"),
    )

    cols[1].metric(
        "Actions",
        len(plan_data.get("actions", [])),
    )

    cols[2].metric(
        "Approved",
        plan_data.get("approved_actions", 0),
    )

    cols[3].metric(
        "Pending Approval",
        plan_data.get("pending_approval_actions", 0),
    )

    cols[4].metric(
        "Blocked",
        plan_data.get("blocked_actions", 0),
    )

    cols[5].metric(
        "Impact",
        round(
            float(plan_data.get("estimated_impact", 0) or 0),
            4,
        ),
    )

    cols[6].metric(
        "Readiness",
        round(
            float(plan_data.get("readiness_score", 0) or 0),
            2,
        ),
    )


def _render_execution_result(result):
    if result is None:
        st.info("No execution result available.")
        return

    data = _as_dict(result)

    cols = st.columns(5)

    cols[0].metric("Status", data.get("status", "—"))
    cols[1].metric("Attempted", data.get("actions_attempted", 0))
    cols[2].metric("Completed", data.get("actions_completed", 0))
    cols[3].metric("Failed", data.get("actions_failed", 0))
    cols[4].metric("Plan", str(data.get("plan_id", ""))[-8:])

    results = data.get("results", [])

    if results:
        st.dataframe(
            pd.DataFrame(results),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Raw Execution Result", expanded=False):
        st.json(data)


def _render_policy_editor(planner: AutonomousExecutionPlanner):
    st.subheader("Execution Planner Policy")

    policy = planner.policy

    col1, col2, col3 = st.columns(3)

    with col1:
        allow_scaling = st.checkbox(
            "Allow Autonomous Scaling",
            value=policy.allow_autonomous_scaling,
        )

        allow_provider = st.checkbox(
            "Allow Provider Rebalance",
            value=policy.allow_autonomous_provider_rebalance,
        )

        allow_pause = st.checkbox(
            "Allow Universe Pause",
            value=policy.allow_autonomous_universe_pause,
        )

    with col2:
        allow_batch = st.checkbox(
            "Allow Batch Adjustment",
            value=policy.allow_autonomous_batch_adjustment,
        )

        allow_governance = st.checkbox(
            "Allow Governance Controls",
            value=policy.allow_autonomous_governance_controls,
        )

        allow_snapshots = st.checkbox(
            "Allow Snapshots",
            value=policy.allow_autonomous_snapshots,
        )

    with col3:
        high_threshold = st.slider(
            "High Impact Approval Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(policy.high_impact_approval_threshold),
            step=0.01,
        )

        critical_threshold = st.slider(
            "Critical Impact Approval Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(policy.critical_impact_approval_threshold),
            step=0.01,
        )

        min_confidence = st.slider(
            "Minimum Autonomous Confidence",
            min_value=0.0,
            max_value=1.0,
            value=float(policy.min_confidence_for_autonomous_action),
            step=0.01,
        )

    if st.button(
        "Apply Planner Policy",
        use_container_width=True,
    ):
        planner.policy = ExecutionPlannerPolicy(
            name=policy.name,
            enabled=policy.enabled,
            allow_autonomous_scaling=allow_scaling,
            allow_autonomous_provider_rebalance=allow_provider,
            allow_autonomous_universe_pause=allow_pause,
            allow_autonomous_batch_adjustment=allow_batch,
            allow_autonomous_governance_controls=allow_governance,
            allow_autonomous_snapshots=allow_snapshots,
            high_impact_approval_threshold=high_threshold,
            critical_impact_approval_threshold=critical_threshold,
            min_confidence_for_autonomous_action=min_confidence,
            max_worker_scale_delta_without_approval=(
                policy.max_worker_scale_delta_without_approval
            ),
            max_batch_size_multiplier_without_approval=(
                policy.max_batch_size_multiplier_without_approval
            ),
            metadata=policy.metadata,
        )

        st.success("Execution planner policy updated.")
        st.rerun()

    with st.expander("Raw Policy", expanded=False):
        st.json(asdict(planner.policy))


def render_autonomous_execution_planner_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    forecasting_engine: Optional[Any] = None,
    forecast_optimizer: Optional[Any] = None,
    execution_planner: Optional[Any] = None,
) -> None:
    st.title("Autonomous Execution Planner")

    persistence_engine = _get_persistence_engine(
        persistence_engine,
    )

    forecasting_engine = _get_forecasting_engine(
        persistence_engine,
        forecasting_engine,
    )

    forecast_optimizer = _get_forecast_optimizer(
        forecasting_engine,
        persistence_engine,
        forecast_optimizer,
    )

    planner = _get_execution_planner(
        persistence_engine=persistence_engine,
        forecasting_engine=forecasting_engine,
        forecast_optimizer=forecast_optimizer,
        analytics_fabric=analytics_fabric,
        execution_planner=execution_planner,
    )

    if "autonomous_execution_current_plan" not in st.session_state:
        st.session_state["autonomous_execution_current_plan"] = None

    if "autonomous_execution_last_result" not in st.session_state:
        st.session_state["autonomous_execution_last_result"] = None

    current_plan = st.session_state["autonomous_execution_current_plan"]
    last_result = st.session_state["autonomous_execution_last_result"]

    tabs = st.tabs(
        [
            "Overview",
            "Generate Plan",
            "Execution Plan",
            "Approval Center",
            "Dry Run",
            "Execute",
            "Action History",
            "Execution History",
            "Direct Plans",
            "Policy",
            "Exports",
        ]
    )

    with tabs[0]:
        st.header("Planner Overview")

        summary = _safe_call(
            planner.planner_summary,
            default={},
        )

        if not summary:
            summary = {
                "plans_generated": len(getattr(planner, "plan_history", [])),
                "plans_executed": len(getattr(planner, "execution_history", [])),
                "actions_generated": len(getattr(planner, "action_history", [])),
            }

        cols = st.columns(6)

        cols[0].metric(
            "Plans Generated",
            summary.get(
                "plans_generated",
                len(getattr(planner, "plan_history", [])),
            ),
        )

        cols[1].metric(
            "Plans Executed",
            summary.get(
                "plans_executed",
                len(getattr(planner, "execution_history", [])),
            ),
        )

        cols[2].metric(
            "Actions Generated",
            summary.get(
                "actions_generated",
                len(getattr(planner, "action_history", [])),
            ),
        )

        cols[3].metric(
            "Actions Completed",
            summary.get("actions_completed", 0),
        )

        cols[4].metric(
            "Actions Failed",
            summary.get("actions_failed", 0),
        )

        cols[5].metric(
            "Pending Approval",
            summary.get("pending_approval_actions", 0),
        )

        st.divider()

        st.subheader("Current Plan")
        _render_plan_summary(current_plan)

        if current_plan is not None:
            _render_action_table(current_plan.actions)

    with tabs[1]:
        st.header("Generate Execution Plan")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "Generate From Forecast Optimizer",
                use_container_width=True,
            ):
                plan = planner.build_execution_plan_from_optimizer()
                st.session_state["autonomous_execution_current_plan"] = plan
                st.success("Execution plan generated.")
                st.rerun()

        with col2:
            if st.button(
                "Generate From Fresh Optimization Report",
                use_container_width=True,
            ):
                report = forecast_optimizer.generate_optimization_report()
                plan = planner.build_execution_plan_from_optimizer(
                    optimization_report=report,
                )
                st.session_state["autonomous_execution_current_plan"] = plan
                st.success("Execution plan generated from fresh optimization report.")
                st.rerun()

        st.divider()

        st.subheader("Forecast Optimization Preview")

        optimization_report = _safe_call(
            forecast_optimizer.generate_optimization_report,
            default=None,
        )

        if optimization_report is not None:
            st.json(_as_dict(optimization_report))

    with tabs[2]:
        st.header("Execution Plan")

        if current_plan is None:
            st.info("Generate an execution plan first.")
        else:
            _render_plan_summary(current_plan)

            st.subheader("Actions")
            _render_action_table(current_plan.actions)

            with st.expander("Raw Execution Plan", expanded=False):
                st.json(current_plan.as_dict())

    with tabs[3]:
        st.header("Approval Center")

        if current_plan is None:
            st.info("No plan available for approval.")
        else:
            pending = [
                action
                for action in current_plan.actions
                if action.requires_approval
            ]

            st.metric(
                "Pending Approval Actions",
                len(pending),
            )

            _render_action_table(pending)

            if st.button(
                "Approve Entire Plan",
                use_container_width=True,
            ):
                approved_plan = planner.approve_plan(current_plan)
                st.session_state["autonomous_execution_current_plan"] = approved_plan
                st.success("Plan approved.")
                st.rerun()

    with tabs[4]:
        st.header("Dry Run Execution")

        if current_plan is None:
            st.info("No plan available for dry run.")
        else:
            if st.button(
                "Run Plan In Dry-Run Mode",
                use_container_width=True,
            ):
                result = planner.execute_plan(
                    current_plan,
                    dry_run=True,
                )

                st.session_state["autonomous_execution_last_result"] = result
                st.success("Dry-run execution completed.")
                st.rerun()

            _render_execution_result(last_result)

    with tabs[5]:
        st.header("Execute Plan")

        st.warning(
            "Real execution may call available local fabric methods. "
            "Approval-required actions will be skipped unless approved."
        )

        if current_plan is None:
            st.info("No plan available for execution.")
        else:
            require_confirm = st.checkbox(
                "I understand and want to run real execution.",
                value=False,
            )

            if st.button(
                "Execute Plan",
                use_container_width=True,
                disabled=not require_confirm,
            ):
                result = planner.execute_plan(
                    current_plan,
                    dry_run=False,
                )

                st.session_state["autonomous_execution_last_result"] = result
                st.success("Execution completed.")
                st.rerun()

            _render_execution_result(last_result)

    with tabs[6]:
        st.header("Action History")

        actions = getattr(
            planner,
            "action_history",
            [],
        )

        _render_action_table(actions)

    with tabs[7]:
        st.header("Execution History")

        executions = getattr(
            planner,
            "execution_history",
            [],
        )

        if not executions:
            st.info("No execution history available.")
        else:
            rows = [
                _as_dict(execution)
                for execution in executions
            ]

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[8]:
        st.header("Direct Plan Builders")

        st.subheader("Scale Workers Plan")

        col1, col2 = st.columns(2)

        with col1:
            current_capacity = st.number_input(
                "Current Capacity",
                min_value=0.0,
                value=100.0,
            )

        with col2:
            target_capacity = st.number_input(
                "Target Capacity",
                min_value=0.0,
                value=150.0,
            )

        if st.button(
            "Create Scale Workers Plan",
            use_container_width=True,
        ):
            plan = planner.create_scale_workers_plan(
                current_capacity=current_capacity,
                target_capacity=target_capacity,
            )
            st.session_state["autonomous_execution_current_plan"] = plan
            st.success("Scale workers plan created.")
            st.rerun()

        st.divider()

        col3, col4 = st.columns(2)

        with col3:
            provider = st.text_input(
                "Provider",
                value="",
            )

            if st.button(
                "Create Provider Rebalance Plan",
                use_container_width=True,
            ):
                plan = planner.create_provider_rebalance_plan(
                    provider=provider or None,
                )
                st.session_state["autonomous_execution_current_plan"] = plan
                st.success("Provider rebalance plan created.")
                st.rerun()

        with col4:
            if st.button(
                "Create Governance Controls Plan",
                use_container_width=True,
            ):
                plan = planner.create_governance_controls_plan()
                st.session_state["autonomous_execution_current_plan"] = plan
                st.success("Governance controls plan created.")
                st.rerun()

    with tabs[9]:
        _render_policy_editor(planner)

    with tabs[10]:
        st.header("Exports")

        export_payload = {
            "current_plan": (
                current_plan.as_dict()
                if current_plan is not None
                else None
            ),
            "last_result": (
                last_result.as_dict()
                if last_result is not None
                else None
            ),
            "planner_summary": _safe_call(
                planner.planner_summary,
                default={},
            ),
            "policy": asdict(planner.policy),
        }

        _json_download(
            "Export Execution Planner Package",
            export_payload,
        )

        if current_plan is not None:
            _json_download(
                "Export Current Execution Plan",
                current_plan.as_dict(),
            )

        if last_result is not None:
            _json_download(
                "Export Last Execution Result",
                last_result.as_dict(),
            )

        st.json(export_payload)


def render_execution_planner_dashboard(
    analytics_fabric: Optional[Any] = None,
    persistence_engine: Optional[Any] = None,
    forecasting_engine: Optional[Any] = None,
    forecast_optimizer: Optional[Any] = None,
    execution_planner: Optional[Any] = None,
) -> None:
    render_autonomous_execution_planner_dashboard(
        analytics_fabric=analytics_fabric,
        persistence_engine=persistence_engine,
        forecasting_engine=forecasting_engine,
        forecast_optimizer=forecast_optimizer,
        execution_planner=execution_planner,
    )