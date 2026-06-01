"""
ui/admin/analytics_fabric_control_tower.py
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)} if default is None else default


def _to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "as_dict"):
        return value.as_dict()

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    return {"value": str(value)}


def _health_badge(score: float) -> str:
    if score >= 90:
        return "🟢 GREEN"
    if score >= 75:
        return "🟡 YELLOW"
    if score >= 60:
        return "🟠 ORANGE"
    if score >= 40:
        return "🔴 RED"
    return "🚨 CRITICAL"


def _metric_row(metrics: Dict[str, Any], keys: list[str]) -> None:
    cols = st.columns(max(1, len(keys)))

    for col, key in zip(cols, keys):
        value = metrics.get(key, "—")

        if isinstance(value, float):
            value = round(value, 4)

        col.metric(
            key.replace("_", " ").title(),
            value,
        )


def _json_view(title: str, data: Any) -> None:
    with st.expander(title, expanded=False):
        st.json(_to_dict(data))


def _get_fabric(storage=None, fabric=None):
    if fabric is not None:
        return fabric

    if "analytics_fabric" in st.session_state:
        return st.session_state["analytics_fabric"]

    try:
        from modules.analytics.analytics_fabric_bootstrap import (
            AnalyticsFabricConfig,
            build_analytics_fabric,
        )

        built = build_analytics_fabric(
            AnalyticsFabricConfig(
                db_path="data/analytics_fabric.db",
                reset_db=False,
            )
        )

        st.session_state["analytics_fabric"] = built
        return built

    except Exception as exc:
        st.error(f"Unable to initialize Analytics Fabric: {exc}")
        return None


def calculate_runtime_health_score(runtime_metrics: Dict[str, Any]) -> float:
    score = 100.0

    failed_jobs = runtime_metrics.get("failed_jobs", 0)

    if failed_jobs > 0:
        score -= min(50, failed_jobs * 0.5)

    workers_online = runtime_metrics.get("workers_online", 0)
    workers_total = runtime_metrics.get("workers_total", workers_online)

    if workers_total > 0:
        availability = workers_online / workers_total
        score *= availability

    return round(max(0.0, min(100.0, score)), 2)


def calculate_capacity_health_score(capacity_summary: Dict[str, Any]) -> float:
    latest_fleet = capacity_summary.get("latest_fleet", {})

    utilization = latest_fleet.get("avg_utilization", 0)

    if utilization <= 0:
        return 75.0

    if utilization <= 0.75:
        return 100.0

    if utilization <= 0.85:
        return 85.0

    if utilization <= 0.95:
        return 65.0

    return 35.0


def calculate_provider_health_score(provider_summary: Dict[str, Any]) -> float:
    providers = provider_summary.get("providers", 0)

    if providers <= 0:
        return 50.0

    recommendations = provider_summary.get("recommendations", 0)

    score = 100.0 - min(40.0, recommendations * 2)

    return round(max(0.0, score), 2)


def calculate_governance_health_score(governance_summary: Dict[str, Any]) -> float:
    actions = governance_summary.get("actions", 0)
    quarantined = governance_summary.get("quarantined_workers", 0)
    paused = governance_summary.get("paused_universes", 0)

    penalty = (
        (actions * 2)
        + (quarantined * 5)
        + (paused * 3)
    )

    return round(max(0.0, 100.0 - penalty), 2)


def calculate_intelligence_health_score(
    intelligence_summary: Dict[str, Any]
) -> float:
    tenant_profiles = intelligence_summary.get(
        "tenant_profiles",
        0,
    )

    universe_profiles = intelligence_summary.get(
        "universe_profiles",
        0,
    )

    if tenant_profiles == 0 and universe_profiles == 0:
        return 50.0

    score = min(
        100.0,
        (tenant_profiles * 2)
        + (universe_profiles * 0.25),
    )

    return round(score, 2)


def calculate_fabric_health_score(
    runtime_score: float,
    capacity_score: float,
    provider_score: float,
    governance_score: float,
    intelligence_score: float,
) -> float:
    score = (
        runtime_score
        + capacity_score
        + provider_score
        + governance_score
        + intelligence_score
    ) / 5.0

    return round(score, 2)


def render_analytics_fabric_control_tower(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Control Tower")

    fabric = _get_fabric(
        storage=storage,
        fabric=fabric,
    )

    if fabric is None:
        st.stop()

    queue_metrics = _safe_call(
        lambda: fabric.execution_queue.queue_metrics(),
        {},
    )

    runtime_metrics = _safe_call(
        lambda: fabric.runtime_controller.runtime_metrics(),
        {},
    )

    provider_summary = _safe_call(
        lambda: fabric.provider_cost_intelligence.summary(),
        {},
    )

    capacity_summary = _safe_call(
        lambda: fabric.worker_capacity_model.capacity_summary(),
        {},
    )

    governance_summary = _safe_call(
        lambda: fabric.execution_governor.governance_summary(),
        {},
    )

    planner_summary = _safe_call(
        lambda: fabric.global_planner.planner_summary(),
        {},
    )

    intelligence_summary = _safe_call(
        lambda: fabric.tenant_universe_intelligence.intelligence_summary(),
        {},
    )

    optimizer_metrics = _safe_call(
        lambda: fabric.optimizer.optimization_metrics(),
        {},
    )

    runtime_score = calculate_runtime_health_score(
        runtime_metrics
    )

    capacity_score = calculate_capacity_health_score(
        capacity_summary
    )

    provider_score = calculate_provider_health_score(
        provider_summary
    )

    governance_score = calculate_governance_health_score(
        governance_summary
    )

    intelligence_score = calculate_intelligence_health_score(
        intelligence_summary
    )

    fabric_health = calculate_fabric_health_score(
        runtime_score,
        capacity_score,
        provider_score,
        governance_score,
        intelligence_score,
    )

    st.success(
        f"Fabric Health Score: {fabric_health} "
        f"({_health_badge(fabric_health)})"
    )

    tabs = st.tabs(
        [
            "Overview",
            "Operations",
            "Executive",
            "Validation",
            "Runtime",
            "Queue",
            "Capacity",
            "Providers",
            "Governance",
            "Planning",
            "Intelligence",
            "Optimizer",
            "Exports",
        ]
    )

    with tabs[0]:
        st.header("Control Tower Overview")

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        col1.metric(
            "Queued Jobs",
            queue_metrics.get("queue_depth", 0),
        )

        col2.metric(
            "Active Leases",
            queue_metrics.get("active_leases", 0),
        )

        col3.metric(
            "Workers",
            runtime_metrics.get(
                "workers_online",
                0,
            ),
        )

        col4.metric(
            "Providers",
            provider_summary.get(
                "providers",
                0,
            ),
        )

        col5.metric(
            "Plans",
            planner_summary.get(
                "plans_generated",
                0,
            ),
        )

        col6.metric(
            "Tenant Profiles",
            intelligence_summary.get(
                "tenant_profiles",
                0,
            ),
        )

        st.divider()

        health_rows = [
            {
                "Area": "Runtime",
                "Score": runtime_score,
                "Status": _health_badge(runtime_score),
            },
            {
                "Area": "Capacity",
                "Score": capacity_score,
                "Status": _health_badge(capacity_score),
            },
            {
                "Area": "Providers",
                "Score": provider_score,
                "Status": _health_badge(provider_score),
            },
            {
                "Area": "Governance",
                "Score": governance_score,
                "Status": _health_badge(governance_score),
            },
            {
                "Area": "Intelligence",
                "Score": intelligence_score,
                "Status": _health_badge(intelligence_score),
            },
        ]

        st.dataframe(
            pd.DataFrame(health_rows),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[1]:
        from ui.admin.analytics_fabric_operations_center import (
            render_analytics_fabric_operations_center,
        )

        render_analytics_fabric_operations_center(
            storage=storage,
            fabric=fabric,
        )

    with tabs[2]:
        from ui.admin.analytics_fabric_executive_dashboard import (
            render_analytics_fabric_executive_dashboard,
        )

        render_analytics_fabric_executive_dashboard(
            storage=storage,
            fabric=fabric,
        )

    with tabs[3]:
        from ui.admin.analytics_fabric_validation_dashboard import (
            render_analytics_fabric_validation_dashboard,
        )

        render_analytics_fabric_validation_dashboard(
            storage=storage,
            fabric=fabric,
        )

    with tabs[4]:
        st.header("Runtime Status")

        _metric_row(
            runtime_metrics,
            [
                "workers_total",
                "workers_online",
                "active_jobs",
                "completed_jobs",
                "failed_jobs",
            ],
        )

        _json_view(
            "Runtime Metrics",
            runtime_metrics,
        )

    with tabs[5]:
        st.header("Queue Status")

        _metric_row(
            queue_metrics,
            [
                "queue_depth",
                "active_leases",
                "unclaimed_jobs",
            ],
        )

        _json_view(
            "Queue Metrics",
            queue_metrics,
        )

    with tabs[6]:
        st.header("Capacity Status")

        st.metric(
            "Capacity Health",
            capacity_score,
        )

        _json_view(
            "Capacity Summary",
            capacity_summary,
        )

    with tabs[7]:
        st.header("Provider Status")

        st.metric(
            "Provider Health",
            provider_score,
        )

        _json_view(
            "Provider Summary",
            provider_summary,
        )

    with tabs[8]:
        st.header("Governance Status")

        st.metric(
            "Governance Health",
            governance_score,
        )

        _json_view(
            "Governance Summary",
            governance_summary,
        )

    with tabs[9]:
        st.header("Planning Status")

        _json_view(
            "Planner Summary",
            planner_summary,
        )

    with tabs[10]:
        st.header("Tenant Intelligence")

        st.metric(
            "Intelligence Health",
            intelligence_score,
        )

        _json_view(
            "Tenant Intelligence Summary",
            intelligence_summary,
        )

    with tabs[11]:
        st.header("Optimizer Status")

        _json_view(
            "Optimizer Metrics",
            optimizer_metrics,
        )

    with tabs[12]:
        st.header("Control Tower Export")

        export_state = {
            "generated_at": utc_now_iso(),
            "fabric_health": fabric_health,
            "runtime_health": runtime_score,
            "capacity_health": capacity_score,
            "provider_health": provider_score,
            "governance_health": governance_score,
            "intelligence_health": intelligence_score,
            "queue_metrics": queue_metrics,
            "runtime_metrics": runtime_metrics,
            "provider_summary": provider_summary,
            "capacity_summary": capacity_summary,
            "governance_summary": governance_summary,
            "planner_summary": planner_summary,
            "intelligence_summary": intelligence_summary,
            "optimizer_metrics": optimizer_metrics,
        }

        payload = json.dumps(
            export_state,
            indent=2,
            default=str,
        )

        st.download_button(
            "Export Control Tower Snapshot",
            payload,
            file_name=(
                f"analytics_control_tower_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        st.download_button(
            "Export Executive Snapshot",
            payload,
            file_name=(
                f"analytics_executive_snapshot_"
                f"{int(time.time())}.json"
            ),
            mime="application/json",
            use_container_width=True,
        )

        _json_view(
            "Export Preview",
            export_state,
        )


def render_analytics_control_tower(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_control_tower(
        storage=storage,
        fabric=fabric,
    )