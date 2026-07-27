"""
ui/admin/analytics_fabric_operations_center.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {
            "error": str(exc),
        } if default is None else default


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "as_dict"):
        return value.as_dict()

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    return {
        "value": str(value),
    }


def _json_view(label: str, data: Any) -> None:
    with st.expander(label, expanded=False):
        st.json(_as_dict(data))


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


def _dict_to_df(data: Dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=str)
        rows.append(
            {
                "Metric": key,
                "Value": value,
            }
        )

    return pd.DataFrame(rows)


def _render_summary_table(title: str, data: Dict[str, Any]) -> None:
    st.subheader(title)

    if not data:
        st.info("No data available.")
        return

    st.dataframe(
        _dict_to_df(data),
        use_container_width=True,
        hide_index=True,
    )


def _get_fabric(storage: Optional[Any] = None, fabric: Optional[Any] = None) -> Any:
    if fabric is not None:
        return fabric

    if "analytics_fabric" in st.session_state:
        return st.session_state["analytics_fabric"]

    try:
        from modules.analytics.analytics_fabric_bootstrap import (
            AnalyticsFabricConfig,
            build_analytics_fabric,
        )

        db_path = "data/analytics_fabric.db"

        if storage is not None:
            db_path = getattr(storage, "db_path", db_path)

        built = build_analytics_fabric(
            AnalyticsFabricConfig(
                db_path=db_path,
                reset_db=False,
            )
        )

        st.session_state["analytics_fabric"] = built

        return built

    except Exception as exc:
        st.error(f"Unable to initialize Analytics Fabric: {exc}")
        return None


def render_analytics_fabric_operations_center(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Operations Center")

    fabric = _get_fabric(
        storage=storage,
        fabric=fabric,
    )

    if fabric is None:
        st.stop()

    tabs = st.tabs(
        [
            "Overview",
            "Health",
            "Runtime",
            "Queue",
            "Scheduler",
            "Capacity",
            "Providers",
            "Governance",
            "Planning",
            "Tenant Intelligence",
            "Optimizer",
            "Validation",
            "Export",
        ]
    )

    with tabs[0]:
        _render_overview(fabric)

    with tabs[1]:
        _render_health(fabric)

    with tabs[2]:
        _render_runtime(fabric)

    with tabs[3]:
        _render_queue(fabric)

    with tabs[4]:
        _render_scheduler(fabric)

    with tabs[5]:
        _render_capacity(fabric)

    with tabs[6]:
        _render_providers(fabric)

    with tabs[7]:
        _render_governance(fabric)

    with tabs[8]:
        _render_planning(fabric)

    with tabs[9]:
        _render_tenant_intelligence(fabric)

    with tabs[10]:
        _render_optimizer(fabric)

    with tabs[11]:
        _render_validation(fabric)

    with tabs[12]:
        _render_export(fabric)


def _render_overview(fabric: Any) -> None:
    st.header("Fabric Overview")

    summary = _safe_call(
        lambda: fabric.summary(),
        default={},
    )

    st.caption("Single-pane overview of the analytics fabric runtime.")

    _metric_row(
        summary,
        [
            "fabric_id",
            "db_path",
            "created_at",
        ],
    )

    st.divider()

    component_rows = []

    for key, value in summary.items():
        if isinstance(value, dict):
            status = value.get("status", "available")
            if "error" in value:
                status = "error"

            component_rows.append(
                {
                    "Component": key,
                    "Status": status,
                    "Details": json.dumps(value, default=str),
                }
            )

    if component_rows:
        st.dataframe(
            pd.DataFrame(component_rows),
            use_container_width=True,
            hide_index=True,
        )

    _json_view(
        "Raw Fabric Summary",
        summary,
    )


def _render_health(fabric: Any) -> None:
    st.header("Health & Controls")

    col1, col2, col3 = st.columns(3)

    with col1:
        run_health = st.button(
            "Run Health Check",
            use_container_width=True,
        )

    with col2:
        run_validation = st.button(
            "Run Integration Validation",
            use_container_width=True,
        )

    with col3:
        run_stress = st.button(
            "Run Small Stress Validation",
            use_container_width=True,
        )

    if run_health:
        from modules.analytics.analytics_fabric_bootstrap import (
            run_fabric_health_check,
        )

        health = run_fabric_health_check(fabric)

        st.success(f"Health Check Status: {health.status}")
        _json_view(
            "Health Check Details",
            health.as_dict(),
        )

    if run_validation:
        from modules.analytics.analytics_fabric_validation_suite import (
            run_analytics_fabric_validation,
        )

        result = run_analytics_fabric_validation(
            fabric=fabric,
        )

        st.success(f"Validation Status: {result.summary.status}")

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Check": c.name,
                        "Status": c.status,
                        "Message": c.message,
                    }
                    for c in result.checks
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        _json_view(
            "Validation Details",
            result.as_dict(),
        )

    if run_stress:
        from modules.analytics.analytics_fabric_stress_validation import (
            AnalyticsFabricStressConfig,
            run_analytics_fabric_stress_validation,
        )

        result = run_analytics_fabric_stress_validation(
            fabric=fabric,
            config=AnalyticsFabricStressConfig(
                db_path=fabric.config.db_path,
                reset_db=False,
                tenant_count=2,
                universes_per_tenant=2,
                jobs_per_universe=25,
                worker_count=5,
                worker_capacity=50,
                provider_count=2,
                runtime_cycles=1,
                verbose=False,
            ),
        )

        st.success(f"Stress Validation Status: {result.summary.status}")

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Check": c.name,
                        "Status": c.status,
                        "Duration MS": c.duration_ms,
                        "Message": c.message,
                    }
                    for c in result.checks
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        _json_view(
            "Stress Validation Details",
            result.as_dict(),
        )


def _render_runtime(fabric: Any) -> None:
    st.header("Runtime Operations")

    metrics = _safe_call(
        lambda: fabric.runtime_controller.runtime_metrics(),
        default={},
    )

    _metric_row(
        metrics,
        [
            "workers_total",
            "workers_online",
            "active_jobs",
            "completed_jobs",
            "failed_jobs",
        ],
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Start Runtime", use_container_width=True):
            result = _safe_call(
                lambda: fabric.runtime_controller.start(
                    metadata={"source": "operations_center"}
                ),
                default={},
            )
            st.success("Runtime start requested.")
            _json_view("Start Result", result)

    with col2:
        if st.button("Run Runtime Tick", use_container_width=True):
            def execute_callback(job: Any, lease: Any) -> Dict[str, Any]:
                return {
                    "job_id": getattr(job, "job_id", None),
                    "lease_id": getattr(lease, "lease_id", None),
                    "result_ref": "operations_center_tick",
                }

            tick = _safe_call(
                lambda: fabric.runtime_controller.tick(
                    execute_callback=execute_callback
                ),
                default={},
            )

            st.success("Runtime tick executed.")
            _json_view("Runtime Tick Result", tick)

    _render_summary_table(
        "Runtime Metrics",
        metrics,
    )


def _render_queue(fabric: Any) -> None:
    st.header("Queue Operations")

    metrics = _safe_call(
        lambda: fabric.execution_queue.queue_metrics(),
        default={},
    )

    _metric_row(
        metrics,
        [
            "queue_depth",
            "active_leases",
            "unclaimed_jobs",
        ],
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Recover Expired Leases", use_container_width=True):
            recovered = _safe_call(
                lambda: fabric.execution_queue.recover_expired_leases(),
                default=0,
            )
            st.success(f"Recovered leases: {recovered}")

    with col2:
        if st.button("Refresh Queue Metrics", use_container_width=True):
            st.rerun()

    _render_summary_table(
        "Queue Metrics",
        metrics,
    )


def _render_scheduler(fabric: Any) -> None:
    st.header("Scheduler Operations")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run Scheduler Cycle", use_container_width=True):
            result = _safe_call(
                lambda: fabric.scheduler.run_scheduler_cycle(),
                default={},
            )
            st.success("Scheduler cycle completed.")
            _json_view(
                "Scheduler Cycle Result",
                result,
            )

    with col2:
        if st.button("Refresh Scheduler State", use_container_width=True):
            st.rerun()

    metrics = {}

    if hasattr(fabric.scheduler, "scheduler_metrics"):
        metrics = _safe_call(
            lambda: fabric.scheduler.scheduler_metrics(),
            default={},
        )

    elif hasattr(fabric.scheduler, "metrics"):
        metrics = _safe_call(
            lambda: fabric.scheduler.metrics(),
            default={},
        )

    _render_summary_table(
        "Scheduler Metrics",
        metrics,
    )


def _render_capacity(fabric: Any) -> None:
    st.header("Worker Capacity")

    summary = _safe_call(
        lambda: fabric.worker_capacity_model.capacity_summary(),
        default={},
    )

    _metric_row(
        summary,
        [
            "samples",
            "worker_profiles",
            "fleet_profiles",
            "forecasts",
            "recommendations",
        ],
    )

    st.divider()

    if st.button("Run Sample Capacity Analysis", use_container_width=True):
        from modules.analytics.worker_capacity_model import WorkerTelemetrySample

        queue_metrics = _safe_call(
            lambda: fabric.execution_queue.queue_metrics(),
            default={},
        )

        report = fabric.worker_capacity_model.analyze(
            samples=[
                WorkerTelemetrySample(
                    worker_id="ops_worker_1",
                    tenant_id="OPS",
                    state="ONLINE",
                    capacity=10,
                    active_jobs=7,
                    completed_jobs=100,
                    failed_jobs=2,
                    avg_runtime_seconds=5.0,
                ),
                WorkerTelemetrySample(
                    worker_id="ops_worker_2",
                    tenant_id="OPS",
                    state="ONLINE",
                    capacity=10,
                    active_jobs=2,
                    completed_jobs=100,
                    failed_jobs=1,
                    avg_runtime_seconds=4.0,
                ),
            ],
            queue_depth=int(queue_metrics.get("queue_depth", 0)),
            active_leases=int(queue_metrics.get("active_leases", 0)),
            tenant_id="OPS",
        )

        st.success("Capacity analysis completed.")
        _json_view(
            "Capacity Report",
            report.as_dict(),
        )

    _json_view(
        "Capacity Summary",
        summary,
    )


def _render_providers(fabric: Any) -> None:
    st.header("Provider Intelligence")

    summary = _safe_call(
        lambda: fabric.provider_cost_intelligence.summary(),
        default={},
    )

    _metric_row(
        summary,
        [
            "providers",
            "samples",
            "recommendations",
            "best_provider",
        ],
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        provider = st.text_input(
            "Provider Name",
            value="OPS_PROVIDER",
        )

    with col2:
        requests = st.number_input(
            "Sample Requests",
            min_value=1,
            value=1000,
        )

    if st.button("Record Provider Sample", use_container_width=True):
        from modules.analytics.provider_cost_intelligence import (
            ProviderUsageSample,
        )

        engine = fabric.provider_cost_intelligence

        engine.record_usage(
            ProviderUsageSample(
                provider=provider,
                requests=int(requests),
                successes=max(0, int(requests) - 10),
                failures=5,
                throttles=5,
                quota_used=int(requests),
                quota_limit=max(int(requests) * 10, 1),
                average_latency_ms=250.0,
                total_cost_usd=float(requests) * 0.005,
            )
        )

        profile = engine.build_provider_profile(provider)
        recommendations = engine.generate_recommendations()

        st.success("Provider sample recorded.")
        _json_view(
            "Provider Profile",
            profile,
        )
        _json_view(
            "Provider Recommendations",
            {
                "recommendations": [
                    asdict(r) for r in recommendations
                ]
            },
        )

    rankings = _safe_call(
        lambda: fabric.provider_cost_intelligence.rank_providers(),
        default=[],
    )

    if rankings:
        st.dataframe(
            pd.DataFrame(
                [asdict(p) for p in rankings]
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_governance(fabric: Any) -> None:
    st.header("Execution Governance")

    summary = _safe_call(
        lambda: fabric.execution_governor.governance_summary(),
        default={},
    )

    _metric_row(
        summary,
        [
            "evaluations",
            "decisions",
            "actions",
            "paused_universes",
            "disabled_providers",
            "quarantined_workers",
        ],
    )

    st.divider()

    if st.button("Evaluate Runtime Governance", use_container_width=True):
        queue_metrics = _safe_call(
            lambda: fabric.execution_queue.queue_metrics(),
            default={},
        )

        worker_report = fabric.worker_capacity_model.analyze_from_runtime(
            workers=[
                {
                    "worker_id": "gov_ops_worker",
                    "state": "ONLINE",
                    "capacity": 10,
                    "active_jobs": 8,
                    "jobs_completed": 100,
                    "jobs_failed": 2,
                    "avg_runtime_seconds": 5.0,
                }
            ],
            queue_metrics=queue_metrics,
            tenant_id="OPS",
        )

        provider_profiles = list(
            getattr(
                fabric.provider_cost_intelligence,
                "provider_profiles",
                {},
            ).values()
        )

        evaluation = fabric.execution_governor.evaluate_runtime_state(
            queue_metrics=queue_metrics,
            fleet_profile=worker_report.fleet_profile,
            provider_profiles=provider_profiles,
            tenant_metrics={"pressure": 0.25},
            universe_metrics={"pressure": 0.20},
        )

        st.success("Governance evaluation completed.")
        _json_view(
            "Governance Evaluation",
            evaluation.as_dict(),
        )

    _json_view(
        "Governance Summary",
        summary,
    )


def _render_planning(fabric: Any) -> None:
    st.header("Global Planning")

    summary = _safe_call(
        lambda: fabric.global_planner.planner_summary(),
        default={},
    )

    _metric_row(
        summary,
        [
            "registered_universes",
            "deferred_universes",
            "paused_universes",
            "capacity_reservations",
            "plans_generated",
        ],
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        tenant_id = st.text_input("Tenant", value="OPS")

    with col2:
        universe_id = st.text_input("Universe", value="OPS_UNIVERSE")

    with col3:
        estimated_jobs = st.number_input(
            "Estimated Jobs",
            min_value=1,
            value=100,
        )

    if st.button("Register Universe + Build Plan", use_container_width=True):
        fabric.global_planner.register_universe(
            tenant_id=tenant_id,
            universe_id=universe_id,
            universe_name=universe_id,
            priority="HIGH",
            estimated_jobs=int(estimated_jobs),
            estimated_runtime_seconds=float(estimated_jobs) * 2.0,
            estimated_cost_usd=float(estimated_jobs) * 0.002,
        )

        queue_metrics = _safe_call(
            lambda: fabric.execution_queue.queue_metrics(),
            default={},
        )

        worker_report = fabric.worker_capacity_model.analyze_from_runtime(
            workers=[
                {
                    "worker_id": "planner_ops_worker",
                    "state": "ONLINE",
                    "capacity": 500,
                    "active_jobs": 25,
                    "jobs_completed": 1000,
                    "jobs_failed": 3,
                    "avg_runtime_seconds": 4.0,
                }
            ],
            queue_metrics=queue_metrics,
            tenant_id=tenant_id,
        )

        provider_profiles = list(
            getattr(
                fabric.provider_cost_intelligence,
                "provider_profiles",
                {},
            ).values()
        )

        plan = fabric.global_planner.build_execution_plan(
            queue_metrics=queue_metrics,
            worker_report=worker_report,
            provider_profiles=provider_profiles,
            tenant_metrics={"pressure": 0.1},
            universe_metrics={},
        )

        st.success("Global plan generated.")
        _json_view(
            "Global Execution Plan",
            plan.as_dict(),
        )

    _json_view(
        "Planner Summary",
        summary,
    )


def _render_tenant_intelligence(fabric: Any) -> None:
    st.header("Tenant Intelligence")

    summary = _safe_call(
        lambda: fabric.tenant_universe_intelligence.intelligence_summary(),
        default={},
    )

    _metric_row(
        summary,
        [
            "tenant_samples",
            "universe_samples",
            "tenant_profiles",
            "universe_profiles",
            "recommendations",
        ],
    )

    st.divider()

    if st.button("Run Sample Tenant Intelligence", use_container_width=True):
        from modules.analytics.tenant_universe_intelligence_engine import (
            TenantTelemetrySample,
            UniverseTelemetrySample,
        )

        report = fabric.tenant_universe_intelligence.analyze(
            tenant_samples=[
                TenantTelemetrySample(
                    tenant_id="OPS",
                    jobs_submitted=1000,
                    jobs_completed=950,
                    jobs_failed=20,
                    queue_depth=50,
                    active_jobs=25,
                    total_cost_usd=10.0,
                    provider_calls=1000,
                    avg_runtime_seconds=5.0,
                    sla_breaches=1,
                    universes_active=1,
                    universes_deferred=0,
                )
            ],
            universe_samples=[
                UniverseTelemetrySample(
                    tenant_id="OPS",
                    universe_id="OPS_UNIVERSE",
                    universe_name="OPS_UNIVERSE",
                    jobs_submitted=1000,
                    jobs_completed=950,
                    jobs_failed=20,
                    symbols_processed=500,
                    analytics_generated=450,
                    refresh_interval_minutes=60,
                    avg_runtime_seconds=5.0,
                    total_cost_usd=10.0,
                    provider_calls=1000,
                    stale_symbols=10,
                    sla_breaches=1,
                )
            ],
        )

        st.success("Tenant intelligence generated.")
        _json_view(
            "Tenant Intelligence Report",
            report.as_dict(),
        )

    _json_view(
        "Tenant Intelligence Summary",
        summary,
    )


def _render_optimizer(fabric: Any) -> None:
    st.header("Optimizer")

    metrics = _safe_call(
        lambda: fabric.optimizer.optimization_metrics(),
        default={},
    )

    _metric_row(
        metrics,
        [
            "telemetry_samples",
            "plans_generated",
            "recommendations_generated",
            "successful_optimizations",
            "failed_optimizations",
        ],
    )

    st.divider()

    if st.button("Generate Optimization Plan", use_container_width=True):
        plan = _safe_call(
            lambda: fabric.optimizer.generate_optimization_plan(),
            default={},
        )

        st.success("Optimization plan generated.")
        _json_view(
            "Optimization Plan",
            plan,
        )

    _render_summary_table(
        "Optimization Metrics",
        metrics,
    )


def _render_validation(fabric: Any) -> None:
    st.header("Validation & Benchmarking")

    st.info(
        "Use these controls for targeted integration and stress validation. "
        "Large stress runs can take time depending on hardware."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run Integration Validation", use_container_width=True):
            from modules.analytics.analytics_fabric_validation_suite import (
                run_analytics_fabric_validation,
            )

            result = run_analytics_fabric_validation(
                fabric=fabric,
            )

            st.success(f"Integration Status: {result.summary.status}")

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Check": c.name,
                            "Status": c.status,
                            "Message": c.message,
                        }
                        for c in result.checks
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    with col2:
        if st.button("Run Small Stress Validation", use_container_width=True):
            from modules.analytics.analytics_fabric_stress_validation import (
                AnalyticsFabricStressConfig,
                run_analytics_fabric_stress_validation,
            )

            result = run_analytics_fabric_stress_validation(
                fabric=fabric,
                config=AnalyticsFabricStressConfig(
                    db_path=fabric.config.db_path,
                    reset_db=False,
                    tenant_count=2,
                    universes_per_tenant=2,
                    jobs_per_universe=25,
                    worker_count=5,
                    worker_capacity=50,
                    provider_count=2,
                    runtime_cycles=1,
                    verbose=False,
                ),
            )

            st.success(f"Stress Status: {result.summary.status}")

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Check": c.name,
                            "Status": c.status,
                            "Duration MS": c.duration_ms,
                            "Message": c.message,
                        }
                        for c in result.checks
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


def _render_export(fabric: Any) -> None:
    st.header("Export Fabric State")

    state = {
        "fabric_summary": _safe_call(
            lambda: fabric.summary(),
            default={},
        ),
        "provider_state": _safe_call(
            lambda: fabric.provider_cost_intelligence.export_state(),
            default={},
        ),
        "governance_state": _safe_call(
            lambda: fabric.execution_governor.export_state(),
            default={},
        ),
        "planner_state": _safe_call(
            lambda: fabric.global_planner.export_state(),
            default={},
        ),
        "tenant_intelligence_state": _safe_call(
            lambda: fabric.tenant_universe_intelligence.export_state(),
            default={},
        ),
    }

    st.download_button(
        "Download Fabric State JSON",
        data=json.dumps(state, indent=2, default=str),
        file_name="analytics_fabric_state.json",
        mime="application/json",
        use_container_width=True,
    )

    _json_view(
        "Current Fabric State",
        state,
    )


def render_analytics_operations_center(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_operations_center(
        storage=storage,
        fabric=fabric,
    )