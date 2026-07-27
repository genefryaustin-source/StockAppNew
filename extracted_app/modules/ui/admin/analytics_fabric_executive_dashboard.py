"""
ui/admin/analytics_fabric_executive_dashboard.py
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


def _json_default(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


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


def _table_from_dict(data: Dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=_json_default)
        rows.append({"Metric": key, "Value": value})

    return pd.DataFrame(rows)


def _json_view(label: str, data: Any, expanded: bool = False) -> None:
    with st.expander(label, expanded=expanded):
        st.json(_as_dict(data))


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


def render_analytics_fabric_executive_dashboard(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Executive Dashboard")

    fabric = _get_fabric(storage=storage, fabric=fabric)

    if fabric is None:
        st.stop()

    tabs = st.tabs(
        [
            "Executive Overview",
            "Tenant KPIs",
            "Universe KPIs",
            "Provider Spend",
            "Worker Capacity",
            "Planning Forecast",
            "Governance Risk",
            "Optimization Savings",
            "Fabric Health",
            "Export",
        ]
    )

    with tabs[0]:
        _render_executive_overview(fabric)

    with tabs[1]:
        _render_tenant_kpis(fabric)

    with tabs[2]:
        _render_universe_kpis(fabric)

    with tabs[3]:
        _render_provider_spend(fabric)

    with tabs[4]:
        _render_worker_capacity(fabric)

    with tabs[5]:
        _render_planning_forecast(fabric)

    with tabs[6]:
        _render_governance_risk(fabric)

    with tabs[7]:
        _render_optimization_savings(fabric)

    with tabs[8]:
        _render_fabric_health(fabric)

    with tabs[9]:
        _render_export(fabric)


def _render_executive_overview(fabric: Any) -> None:
    st.header("Executive Overview")

    summary = _safe_call(lambda: fabric.summary(), default={})
    queue_metrics = _safe_call(lambda: fabric.execution_queue.queue_metrics(), default={})
    runtime_metrics = _safe_call(lambda: fabric.runtime_controller.runtime_metrics(), default={})
    provider_summary = _safe_call(lambda: fabric.provider_cost_intelligence.summary(), default={})
    capacity_summary = _safe_call(lambda: fabric.worker_capacity_model.capacity_summary(), default={})
    governance_summary = _safe_call(lambda: fabric.execution_governor.governance_summary(), default={})
    planner_summary = _safe_call(lambda: fabric.global_planner.planner_summary(), default={})
    intelligence_summary = _safe_call(lambda: fabric.tenant_universe_intelligence.intelligence_summary(), default={})

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Queue Depth", queue_metrics.get("queue_depth", 0))
    col2.metric("Active Leases", queue_metrics.get("active_leases", 0))
    col3.metric("Runtime Workers", runtime_metrics.get("workers_total", runtime_metrics.get("workers_online", 0)))
    col4.metric("Providers", provider_summary.get("providers", 0))

    col5, col6, col7, col8 = st.columns(4)

    col5.metric("Worker Profiles", capacity_summary.get("worker_profiles", 0))
    col6.metric("Governance Decisions", governance_summary.get("decisions", 0))
    col7.metric("Global Plans", planner_summary.get("plans_generated", 0))
    col8.metric("Tenant Profiles", intelligence_summary.get("tenant_profiles", 0))

    st.divider()

    executive_state = {
        "fabric": {
            "fabric_id": summary.get("fabric_id"),
            "db_path": summary.get("db_path"),
            "created_at": summary.get("created_at"),
        },
        "queue": queue_metrics,
        "runtime": runtime_metrics,
        "providers": provider_summary,
        "capacity": capacity_summary,
        "governance": governance_summary,
        "planner": planner_summary,
        "tenant_intelligence": intelligence_summary,
        "generated_at": utc_now_iso(),
    }

    st.subheader("Executive State Summary")
    st.dataframe(
        _table_from_dict(
            {
                "Queue Depth": queue_metrics.get("queue_depth", 0),
                "Active Leases": queue_metrics.get("active_leases", 0),
                "Providers": provider_summary.get("providers", 0),
                "Best Provider": provider_summary.get("best_provider"),
                "Worker Profiles": capacity_summary.get("worker_profiles", 0),
                "Fleet Profiles": capacity_summary.get("fleet_profiles", 0),
                "Governance Decisions": governance_summary.get("decisions", 0),
                "Governance Actions": governance_summary.get("actions", 0),
                "Registered Universes": planner_summary.get("registered_universes", 0),
                "Plans Generated": planner_summary.get("plans_generated", 0),
                "Tenant Profiles": intelligence_summary.get("tenant_profiles", 0),
                "Universe Profiles": intelligence_summary.get("universe_profiles", 0),
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    _json_view("Raw Executive State", executive_state)


def _render_tenant_kpis(fabric: Any) -> None:
    st.header("Tenant KPIs")

    engine = fabric.tenant_universe_intelligence
    profiles = list(getattr(engine, "tenant_profiles", {}).values())

    if not profiles:
        st.info("No tenant profiles available. Run tenant intelligence first.")
        if st.button("Generate Sample Tenant KPI Data", use_container_width=True):
            from modules.analytics.tenant_universe_intelligence_engine import TenantTelemetrySample

            engine.analyze(
                tenant_samples=[
                    TenantTelemetrySample(
                        tenant_id="EXEC_TENANT_A",
                        jobs_submitted=5000,
                        jobs_completed=4800,
                        jobs_failed=100,
                        queue_depth=150,
                        active_jobs=75,
                        total_cost_usd=250.0,
                        provider_calls=5000,
                        avg_runtime_seconds=4.5,
                        sla_breaches=3,
                        universes_active=20,
                        universes_deferred=2,
                    ),
                    TenantTelemetrySample(
                        tenant_id="EXEC_TENANT_B",
                        jobs_submitted=2500,
                        jobs_completed=2300,
                        jobs_failed=150,
                        queue_depth=400,
                        active_jobs=100,
                        total_cost_usd=180.0,
                        provider_calls=3000,
                        avg_runtime_seconds=7.5,
                        sla_breaches=10,
                        universes_active=15,
                        universes_deferred=5,
                    ),
                ]
            )
            st.rerun()
        return

    rows = [asdict(p) for p in profiles]

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    ranked = engine.tenant_rankings(profiles)

    st.subheader("Tenant Risk Ranking")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Tenant": p.tenant_id,
                    "State": p.state,
                    "Risk Score": p.risk_score,
                    "Consumption Score": p.consumption_score,
                    "Efficiency Score": p.efficiency_score,
                    "Cost / Job": p.cost_per_job,
                    "Queue Pressure": p.queue_pressure,
                    "SLA Breach Rate": p.sla_breach_rate,
                }
                for p in ranked
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_universe_kpis(fabric: Any) -> None:
    st.header("Universe KPIs")

    engine = fabric.tenant_universe_intelligence
    profiles = list(getattr(engine, "universe_profiles", {}).values())

    if not profiles:
        st.info("No universe profiles available. Run tenant/universe intelligence first.")
        if st.button("Generate Sample Universe KPI Data", use_container_width=True):
            from modules.analytics.tenant_universe_intelligence_engine import UniverseTelemetrySample

            engine.analyze(
                universe_samples=[
                    UniverseTelemetrySample(
                        tenant_id="EXEC_TENANT_A",
                        universe_id="EXEC_UNIVERSE_A",
                        universe_name="Executive Universe A",
                        jobs_submitted=2000,
                        jobs_completed=1950,
                        jobs_failed=20,
                        symbols_processed=1000,
                        analytics_generated=850,
                        refresh_interval_minutes=60,
                        avg_runtime_seconds=5.0,
                        p95_runtime_seconds=12.0,
                        total_cost_usd=90.0,
                        provider_calls=2000,
                        stale_symbols=25,
                        sla_breaches=1,
                    ),
                    UniverseTelemetrySample(
                        tenant_id="EXEC_TENANT_B",
                        universe_id="EXEC_UNIVERSE_B",
                        universe_name="Executive Universe B",
                        jobs_submitted=1000,
                        jobs_completed=850,
                        jobs_failed=100,
                        symbols_processed=900,
                        analytics_generated=150,
                        refresh_interval_minutes=15,
                        avg_runtime_seconds=320.0,
                        p95_runtime_seconds=600.0,
                        total_cost_usd=150.0,
                        provider_calls=1500,
                        stale_symbols=250,
                        sla_breaches=8,
                    ),
                ]
            )
            st.rerun()
        return

    st.dataframe(
        pd.DataFrame([asdict(p) for p in profiles]),
        use_container_width=True,
        hide_index=True,
    )

    ranked = engine.universe_rankings(profiles)

    st.subheader("Universe Risk Ranking")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Tenant": p.tenant_id,
                    "Universe": p.universe_id,
                    "Name": p.universe_name,
                    "State": p.state,
                    "Risk Score": p.risk_score,
                    "Analytics Yield": p.analytics_yield,
                    "Refresh Efficiency": p.refresh_efficiency_score,
                    "Execution Efficiency": p.execution_efficiency_score,
                    "Cost / Analytic": p.cost_per_analytic,
                    "SLA Breach Rate": p.sla_breach_rate,
                }
                for p in ranked
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_provider_spend(fabric: Any) -> None:
    st.header("Provider Spend")

    engine = fabric.provider_cost_intelligence

    summary = _safe_call(lambda: engine.summary(), default={})
    profiles = list(getattr(engine, "provider_profiles", {}).values())

    _metric_row(
        summary,
        ["providers", "samples", "recommendations", "best_provider"],
    )

    st.divider()

    if not profiles:
        st.info("No provider profiles available.")
        if st.button("Generate Sample Provider Spend Data", use_container_width=True):
            from modules.analytics.provider_cost_intelligence import ProviderUsageSample

            for provider, requests, cost, failures, throttles in [
                ("POLYGON", 10000, 125.0, 50, 20),
                ("MARKETDATA", 8000, 80.0, 80, 50),
                ("ALPHA_VANTAGE", 5000, 25.0, 200, 300),
                ("YAHOO", 2000, 0.0, 400, 500),
            ]:
                engine.record_usage(
                    ProviderUsageSample(
                        provider=provider,
                        requests=requests,
                        successes=max(0, requests - failures),
                        failures=failures,
                        throttles=throttles,
                        quota_used=requests,
                        quota_limit=max(requests * 3, 1),
                        average_latency_ms=250.0 + failures,
                        total_cost_usd=cost,
                    )
                )
                engine.build_provider_profile(provider)

            engine.generate_recommendations()
            st.rerun()
        return

    provider_df = pd.DataFrame([asdict(p) for p in profiles])

    st.dataframe(
        provider_df,
        use_container_width=True,
        hide_index=True,
    )

    spend_rows = [
        {
            "Provider": p.provider,
            "Status": p.status,
            "Requests": p.requests,
            "Total Cost USD": p.total_cost_usd,
            "Cost / Request": p.cost_per_request,
            "Quota Utilization": p.quota_utilization,
            "Failure Rate": p.failure_rate,
            "Throttle Rate": p.throttle_rate,
            "Routing Score": p.routing_score,
        }
        for p in profiles
    ]

    st.subheader("Provider Spend Ranking")

    st.dataframe(
        pd.DataFrame(spend_rows).sort_values(
            by=["Total Cost USD", "Quota Utilization"],
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_worker_capacity(fabric: Any) -> None:
    st.header("Worker Capacity")

    model = fabric.worker_capacity_model
    summary = _safe_call(lambda: model.capacity_summary(), default={})

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

    latest_fleet = summary.get("latest_fleet") or {}
    latest_forecast = summary.get("latest_forecast") or {}

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Workers Online", latest_fleet.get("workers_online", 0))
    col2.metric("Total Capacity", latest_fleet.get("total_capacity", 0))
    col3.metric("Available Capacity", latest_fleet.get("available_capacity", 0))
    col4.metric("Avg Utilization", latest_fleet.get("avg_utilization", 0))

    st.subheader("Capacity Forecast")

    if latest_forecast:
        st.dataframe(
            _table_from_dict(latest_forecast),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No capacity forecast available.")

    if st.button("Generate Sample Capacity Forecast", use_container_width=True):
        from modules.analytics.worker_capacity_model import WorkerTelemetrySample

        report = model.analyze(
            samples=[
                WorkerTelemetrySample(
                    worker_id="EXEC_WORKER_A",
                    state="ONLINE",
                    capacity=100,
                    active_jobs=80,
                    completed_jobs=10000,
                    failed_jobs=50,
                    avg_runtime_seconds=3.0,
                    queue_depth_seen=5000,
                    active_leases=80,
                ),
                WorkerTelemetrySample(
                    worker_id="EXEC_WORKER_B",
                    state="ONLINE",
                    capacity=100,
                    active_jobs=25,
                    completed_jobs=9000,
                    failed_jobs=25,
                    avg_runtime_seconds=2.5,
                    queue_depth_seen=5000,
                    active_leases=25,
                ),
            ],
            queue_depth=5000,
            active_leases=105,
            tenant_id=None,
        )

        st.success("Capacity forecast generated.")
        _json_view("Capacity Report", report.as_dict(), expanded=True)


def _render_planning_forecast(fabric: Any) -> None:
    st.header("Planning Forecast")

    planner = fabric.global_planner
    summary = _safe_call(lambda: planner.planner_summary(), default={})

    _metric_row(
        summary,
        [
            "registered_universes",
            "deferred_universes",
            "paused_universes",
            "plans_generated",
            "latest_plan_state",
        ],
    )

    st.divider()

    latest_plan = None

    if getattr(planner, "plan_history", []):
        latest_plan = planner.plan_history[-1]

    if latest_plan is None:
        st.info("No global execution plan available.")
        if st.button("Generate Sample Executive Plan", use_container_width=True):
            planner.register_universe(
                tenant_id="EXEC_TENANT_A",
                universe_id="EXEC_UNIVERSE_A",
                universe_name="Executive Universe A",
                priority="HIGH",
                estimated_jobs=1000,
                estimated_runtime_seconds=2000.0,
                estimated_cost_usd=50.0,
            )

            worker_report = fabric.worker_capacity_model.analyze_from_runtime(
                workers=[
                    {
                        "worker_id": "EXEC_PLANNER_WORKER",
                        "state": "ONLINE",
                        "capacity": 5000,
                        "active_jobs": 500,
                        "jobs_completed": 10000,
                        "jobs_failed": 25,
                        "avg_runtime_seconds": 3.0,
                    }
                ],
                queue_metrics={"queue_depth": 1000, "active_leases": 500},
            )

            provider_profiles = list(
                getattr(fabric.provider_cost_intelligence, "provider_profiles", {}).values()
            )

            planner.build_execution_plan(
                queue_metrics={"queue_depth": 1000, "active_leases": 500},
                worker_report=worker_report,
                provider_profiles=provider_profiles,
                tenant_metrics={"pressure": 0.25},
                universe_metrics={},
            )
            st.rerun()
        return

    plan_dict = latest_plan.as_dict()

    forecast = plan_dict.get("forecast", {})

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Plan State", plan_dict.get("state"))
    col2.metric("Total Universes", plan_dict.get("total_universes"))
    col3.metric("Active Universes", plan_dict.get("active_universes"))
    col4.metric("Deferred Universes", plan_dict.get("deferred_universes"))

    st.subheader("Execution Forecast")

    st.dataframe(
        _table_from_dict(forecast),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Universe Plans")

    universe_plans = plan_dict.get("universe_plans", [])

    if universe_plans:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Tenant": p.get("tenant_id"),
                        "Universe": p.get("universe_id"),
                        "State": p.get("state"),
                        "Priority": p.get("priority"),
                        "Priority Score": p.get("priority_score"),
                        "Estimated Jobs": p.get("estimated_jobs"),
                        "Estimated Cost USD": p.get("estimated_cost_usd"),
                    }
                    for p in universe_plans
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_governance_risk(fabric: Any) -> None:
    st.header("Governance Risk")

    governor = fabric.execution_governor
    summary = _safe_call(lambda: governor.governance_summary(), default={})

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

    decision_counts = summary.get("decision_counts", {})
    severity_counts = summary.get("severity_counts", {})

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Decision Counts")
        st.dataframe(
            _table_from_dict(decision_counts),
            use_container_width=True,
            hide_index=True,
        )

    with col2:
        st.subheader("Severity Counts")
        st.dataframe(
            _table_from_dict(severity_counts),
            use_container_width=True,
            hide_index=True,
        )

    if getattr(governor, "decision_history", []):
        st.subheader("Recent Governance Decisions")
        st.dataframe(
            pd.DataFrame(
                [
                    asdict(d)
                    for d in governor.decision_history[-100:]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_optimization_savings(fabric: Any) -> None:
    st.header("Optimization Savings")

    optimizer = fabric.optimizer

    metrics = _safe_call(lambda: optimizer.optimization_metrics(), default={})

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

    estimated_savings = {
        "Estimated Queue Savings %": metrics.get("estimated_queue_improvement_pct", 0),
        "Estimated Cost Savings %": metrics.get("estimated_cost_savings_pct", 0),
        "Estimated Runtime Savings %": metrics.get("estimated_runtime_improvement_pct", 0),
        "Recommendations Generated": metrics.get("recommendations_generated", 0),
        "Successful Optimizations": metrics.get("successful_optimizations", 0),
        "Failed Optimizations": metrics.get("failed_optimizations", 0),
    }

    st.subheader("Optimization Business Impact")

    st.dataframe(
        _table_from_dict(estimated_savings),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Generate Optimization Plan", use_container_width=True):
        plan = _safe_call(lambda: optimizer.generate_optimization_plan(), default={})
        st.success("Optimization plan generated.")
        _json_view("Optimization Plan", plan, expanded=True)


def _render_fabric_health(fabric: Any) -> None:
    st.header("Fabric Health")

    from modules.analytics.analytics_fabric_bootstrap import run_fabric_health_check

    if st.button("Run Executive Health Check", use_container_width=True):
        health = run_fabric_health_check(fabric)

        st.success(f"Fabric Health Status: {health.status}")

        checks = health.as_dict().get("checks", {})

        rows = []

        for name, check in checks.items():
            if isinstance(check, dict):
                rows.append(
                    {
                        "Component": name,
                        "Available": check.get("available"),
                        "Class": check.get("class"),
                        "Error": check.get("error"),
                    }
                )
            else:
                rows.append(
                    {
                        "Component": name,
                        "Available": None,
                        "Class": None,
                        "Error": str(check),
                    }
                )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        _json_view("Raw Health Check", health.as_dict())

    summary = _safe_call(lambda: fabric.summary(), default={})

    st.subheader("Current Fabric Summary")

    st.dataframe(
        _table_from_dict(
            {
                "Fabric ID": summary.get("fabric_id"),
                "DB Path": summary.get("db_path"),
                "Created At": summary.get("created_at"),
                "Generated At": summary.get("generated_at"),
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_export(fabric: Any) -> None:
    st.header("Executive Export")

    export_state = {
        "generated_at": utc_now_iso(),
        "fabric_summary": _safe_call(lambda: fabric.summary(), default={}),
        "provider_state": _safe_call(lambda: fabric.provider_cost_intelligence.export_state(), default={}),
        "capacity_summary": _safe_call(lambda: fabric.worker_capacity_model.capacity_summary(), default={}),
        "governance_state": _safe_call(lambda: fabric.execution_governor.export_state(), default={}),
        "planner_state": _safe_call(lambda: fabric.global_planner.export_state(), default={}),
        "tenant_intelligence_state": _safe_call(lambda: fabric.tenant_universe_intelligence.export_state(), default={}),
        "optimizer_metrics": _safe_call(lambda: fabric.optimizer.optimization_metrics(), default={}),
    }

    st.download_button(
        "Download Executive Analytics Report JSON",
        data=json.dumps(export_state, indent=2, default=_json_default),
        file_name=f"analytics_fabric_executive_report_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.subheader("Export Preview")

    _json_view("Executive Report JSON", export_state, expanded=True)


def render_analytics_executive_dashboard(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_executive_dashboard(
        storage=storage,
        fabric=fabric,
    )