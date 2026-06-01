"""
ui/admin/analytics_fabric_validation_dashboard.py
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


def _safe_asdict(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        return [_safe_asdict(v) for v in value]

    if hasattr(value, "as_dict"):
        return value.as_dict()

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)

    return value


def _json_default(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def _safe_call(fn, default=None):
    try:
        return fn()
    except Exception as exc:
        return {
            "error": str(exc),
        } if default is None else default


def _result_to_checks(result: Any) -> pd.DataFrame:
    checks = getattr(result, "checks", None)

    if checks is None and isinstance(result, dict):
        checks = result.get("checks", [])

    rows = []

    for check in checks or []:
        data = _safe_asdict(check)

        rows.append(
            {
                "Name": data.get("name", data.get("test_name", "")),
                "Status": data.get("status", ""),
                "Duration MS": data.get("duration_ms", ""),
                "Message": data.get("message", ""),
                "Generated At": data.get("generated_at", ""),
            }
        )

    return pd.DataFrame(rows)


def _display_result(label: str, result: Any) -> None:
    data = _safe_asdict(result)

    if isinstance(data, dict):
        summary = data.get("summary", {})

        if summary:
            st.subheader("Summary")

            cols = st.columns(5)

            cols[0].metric("Status", summary.get("status", "—"))
            cols[1].metric("Passed", summary.get("passed", 0))
            cols[2].metric("Failed", summary.get("failed", 0))
            cols[3].metric("Warnings", summary.get("warnings", 0))
            cols[4].metric("Total", summary.get("total", 0))

        checks_df = _result_to_checks(result)

        if not checks_df.empty:
            st.subheader("Checks")
            st.dataframe(
                checks_df,
                use_container_width=True,
                hide_index=True,
            )

    with st.expander(f"{label} Raw Output", expanded=False):
        st.json(data)


def _download_result(label: str, result: Any) -> None:
    data = _safe_asdict(result)

    st.download_button(
        f"Download {label} JSON",
        data=json.dumps(data, indent=2, default=_json_default),
        file_name=f"{label.lower().replace(' ', '_')}_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )


def _metrics_table(data: Dict[str, Any]) -> None:
    rows = []

    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=_json_default)

        rows.append(
            {
                "Metric": key,
                "Value": value,
            }
        )

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No metrics available.")


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


def render_analytics_fabric_validation_dashboard(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    st.title("Analytics Fabric Validation Dashboard")

    fabric = _get_fabric(
        storage=storage,
        fabric=fabric,
    )

    if fabric is None:
        st.stop()

    if "analytics_validation_history" not in st.session_state:
        st.session_state["analytics_validation_history"] = []

    tabs = st.tabs(
        [
            "Validation",
            "Stress",
            "Performance",
            "SQLite",
            "Micro Benchmark",
            "Bulk Operations",
            "Fabric Validation",
            "Fabric Stress",
            "History",
            "Export",
        ]
    )

    with tabs[0]:
        _render_validation_tab(fabric)

    with tabs[1]:
        _render_stress_tab(fabric)

    with tabs[2]:
        _render_performance_tab(fabric)

    with tabs[3]:
        _render_sqlite_tab(fabric)

    with tabs[4]:
        _render_micro_benchmark_tab(fabric)

    with tabs[5]:
        _render_bulk_operations_tab(fabric)

    with tabs[6]:
        _render_fabric_validation_tab(fabric)

    with tabs[7]:
        _render_fabric_stress_tab(fabric)

    with tabs[8]:
        _render_history_tab()

    with tabs[9]:
        _render_export_tab()


def _store_history(
    name: str,
    result: Any,
    duration_seconds: float,
) -> None:
    st.session_state["analytics_validation_history"].append(
        {
            "name": name,
            "duration_seconds": round(duration_seconds, 4),
            "generated_at": utc_now_iso(),
            "result": _safe_asdict(result),
        }
    )

    if len(st.session_state["analytics_validation_history"]) > 100:
        st.session_state["analytics_validation_history"] = (
            st.session_state["analytics_validation_history"][-100:]
        )


def _render_validation_tab(fabric: Any) -> None:
    st.header("Analytics Harness Validation")

    st.caption(
        "Runs the original Analytics Fabric validation harness against the bootstrapped fabric."
    )

    if st.button("Run Analytics Validation Harness", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_test_harness import (
            run_analytics_validation,
        )

        result = run_analytics_validation(
            registry=fabric.registry,
            queue=fabric.execution_queue,
            scheduler=fabric.scheduler,
            balancer=fabric.workload_balancer,
            runtime_controller=fabric.runtime_controller,
            orchestrator=fabric.orchestrator,
            governor=fabric.resource_governor,
            optimizer=fabric.optimizer,
        )

        duration = time.perf_counter() - start
        _store_history("Analytics Validation Harness", result, duration)

        st.success("Analytics validation harness completed.")
        _display_result("Analytics Validation Harness", result)
        _download_result("Analytics Validation Harness", result)


def _render_stress_tab(fabric: Any) -> None:
    st.header("Analytics Stress Test Suite")

    col1, col2, col3 = st.columns(3)

    with col1:
        tenants = st.number_input("Tenants", min_value=1, max_value=100, value=5)

    with col2:
        universes = st.number_input("Universes / Tenant", min_value=1, max_value=100, value=5)

    with col3:
        registry_jobs = st.number_input("Registry Jobs", min_value=100, max_value=100000, value=1000)

    col4, col5, col6 = st.columns(3)

    with col4:
        queue_jobs = st.number_input("Queue Jobs", min_value=100, max_value=100000, value=1000)

    with col5:
        workers = st.number_input("Workers", min_value=1, max_value=500, value=20)

    with col6:
        worker_capacity = st.number_input("Worker Capacity", min_value=1, max_value=1000, value=25)

    if st.button("Run Analytics Stress Suite", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_stress_test_suite import (
            AnalyticsStressTestSuite,
            StressTestConfig,
        )

        config = StressTestConfig(
            db_path="data/analytics_dashboard_stress.db",
            reset_db=True,
            tenant_count=int(tenants),
            universes_per_tenant=int(universes),
            schedules_per_universe=1,
            registry_job_count=int(registry_jobs),
            queue_job_count=int(queue_jobs),
            worker_count=int(workers),
            worker_capacity=int(worker_capacity),
            balancer_job_count=int(queue_jobs),
            verbose=False,
        )

        from modules.analytics.analytics_stress_test_suite import build_default_dependencies

        deps = build_default_dependencies(config)

        suite = AnalyticsStressTestSuite(
            dependencies=deps,
            config=config,
        )

        result = suite.run_all()
        duration = time.perf_counter() - start

        _store_history("Analytics Stress Suite", result, duration)

        st.success("Analytics stress suite completed.")
        _display_result("Analytics Stress Suite", result)
        _download_result("Analytics Stress Suite", result)


def _render_performance_tab(fabric: Any) -> None:
    st.header("Performance Profiler")

    iterations = st.number_input(
        "Profiler Iterations",
        min_value=100,
        max_value=50000,
        value=1000,
    )

    if st.button("Run Performance Profile", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_performance_profiler import (
            AnalyticsPerformanceProfiler,
        )

        profiler = AnalyticsPerformanceProfiler(
            registry=fabric.registry,
            queue=fabric.execution_queue,
        )

        result = profiler.run_full_profile(
            iterations=int(iterations),
        )

        duration = time.perf_counter() - start
        _store_history("Performance Profile", result, duration)

        profiles = getattr(result, "operation_profiles", [])

        st.success("Performance profile completed.")

        if profiles:
            st.dataframe(
                pd.DataFrame([asdict(p) for p in profiles]),
                use_container_width=True,
                hide_index=True,
            )

        _download_result("Performance Profile", result)

        with st.expander("Raw Performance Profile", expanded=False):
            st.json(_safe_asdict(result))


def _render_sqlite_tab(fabric: Any) -> None:
    st.header("SQLite Operation Profiler")

    st.caption(
        "Runs operation-level profiling around registry and queue operations."
    )

    iterations = st.number_input(
        "SQLite Profile Iterations",
        min_value=10,
        max_value=10000,
        value=250,
    )

    if st.button("Run SQLite Operation Profile", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.sqlite_operation_profiler import (
            SQLiteOperationProfiler,
        )

        profiler = SQLiteOperationProfiler()

        for i in range(int(iterations)):
            with profiler.profile("registry.register_job"):
                job = fabric.registry.register_job(
                    tenant_id="SQLITE_PROFILE",
                    universe_id="SQLITE_PROFILE_UNIVERSE",
                    job_type="SQLITE_PROFILE",
                    priority="NORMAL",
                    payload={"i": i},
                )

            with profiler.profile("queue.enqueue_job"):
                fabric.execution_queue.enqueue_job(
                    tenant_id="SQLITE_PROFILE",
                    job_id=job.job_id,
                    priority="NORMAL",
                )

        result = profiler.report()

        duration = time.perf_counter() - start
        _store_history("SQLite Operation Profile", result, duration)

        st.success("SQLite operation profile completed.")

        operations = result.get("operations", {})
        sqlite_stats = result.get("sqlite", {})

        if operations:
            st.subheader("Operation Timings")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Operation": name,
                            **metrics,
                        }
                        for name, metrics in operations.items()
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("SQLite Statistics")
        _metrics_table(sqlite_stats)

        _download_result("SQLite Operation Profile", result)


def _render_micro_benchmark_tab(fabric: Any) -> None:
    st.header("Micro Benchmark")

    iterations = st.number_input(
        "Micro Benchmark Iterations",
        min_value=10,
        max_value=10000,
        value=500,
    )

    if st.button("Run Micro Benchmark", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_micro_benchmark import (
            AnalyticsMicroBenchmark,
        )

        benchmark = AnalyticsMicroBenchmark(
            registry=fabric.registry,
            queue=fabric.execution_queue,
        )

        result = benchmark.run_all(
            iterations=int(iterations),
        )

        duration = time.perf_counter() - start
        _store_history("Micro Benchmark", result, duration)

        st.success("Micro benchmark completed.")

        rows = []

        for key, value in result.items():
            data = asdict(value) if hasattr(value, "__dataclass_fields__") else value
            rows.append(data)

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        _download_result("Micro Benchmark", result)


def _render_bulk_operations_tab(fabric: Any) -> None:
    st.header("Bulk Operations Benchmark")

    jobs = st.number_input(
        "Bulk Stress Jobs",
        min_value=100,
        max_value=250000,
        value=10000,
    )

    if st.button("Run Bulk Stress Suite", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_bulk_stress_suite import (
            AnalyticsBulkStressSuite,
            BulkStressConfig,
        )

        suite = AnalyticsBulkStressSuite(
            BulkStressConfig(
                db_path="data/analytics_dashboard_bulk_stress.db",
                reset_db=True,
                job_count=int(jobs),
                verbose=False,
            )
        )

        result = suite.run()

        duration = time.perf_counter() - start
        _store_history("Bulk Stress Suite", result, duration)

        st.success("Bulk stress suite completed.")

        rows = []

        for phase, data in result.items():
            if isinstance(data, dict):
                rows.append(
                    {
                        "Phase": phase,
                        "Operations": data.get("operation_count"),
                        "Runtime Seconds": data.get("elapsed_seconds"),
                        "Throughput / Sec": data.get("throughput_per_second"),
                    }
                )
            else:
                rows.append(
                    {
                        "Phase": phase,
                        "Operations": "",
                        "Runtime Seconds": "",
                        "Throughput / Sec": data,
                    }
                )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        _download_result("Bulk Stress Suite", result)


def _render_fabric_validation_tab(fabric: Any) -> None:
    st.header("Full Fabric Integration Validation")

    if st.button("Run Fabric Validation Suite", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_fabric_validation_suite import (
            run_analytics_fabric_validation,
        )

        result = run_analytics_fabric_validation(
            fabric=fabric,
        )

        duration = time.perf_counter() - start
        _store_history("Fabric Integration Validation", result, duration)

        st.success(f"Fabric validation completed: {result.summary.status}")
        _display_result("Fabric Integration Validation", result)
        _download_result("Fabric Integration Validation", result)


def _render_fabric_stress_tab(fabric: Any) -> None:
    st.header("Full Fabric Stress Validation")

    col1, col2, col3 = st.columns(3)

    with col1:
        tenants = st.number_input("Fabric Stress Tenants", min_value=1, max_value=250, value=5)

    with col2:
        universes = st.number_input("Fabric Stress Universes / Tenant", min_value=1, max_value=250, value=5)

    with col3:
        jobs_per_universe = st.number_input("Jobs / Universe", min_value=1, max_value=10000, value=100)

    col4, col5, col6 = st.columns(3)

    with col4:
        workers = st.number_input("Fabric Stress Workers", min_value=1, max_value=1000, value=25)

    with col5:
        worker_capacity = st.number_input("Fabric Stress Worker Capacity", min_value=1, max_value=10000, value=250)

    with col6:
        providers = st.number_input("Providers", min_value=1, max_value=50, value=5)

    runtime_cycles = st.number_input(
        "Runtime Cycles",
        min_value=1,
        max_value=50,
        value=3,
    )

    if st.button("Run Fabric Stress Validation", use_container_width=True):
        start = time.perf_counter()

        from modules.analytics.analytics_fabric_stress_validation import (
            AnalyticsFabricStressConfig,
            run_analytics_fabric_stress_validation,
        )

        result = run_analytics_fabric_stress_validation(
            config=AnalyticsFabricStressConfig(
                db_path="data/analytics_dashboard_fabric_stress.db",
                reset_db=True,
                tenant_count=int(tenants),
                universes_per_tenant=int(universes),
                jobs_per_universe=int(jobs_per_universe),
                worker_count=int(workers),
                worker_capacity=int(worker_capacity),
                provider_count=int(providers),
                runtime_cycles=int(runtime_cycles),
                verbose=False,
            )
        )

        duration = time.perf_counter() - start
        _store_history("Fabric Stress Validation", result, duration)

        st.success(f"Fabric stress validation completed: {result.summary.status}")
        _display_result("Fabric Stress Validation", result)
        _download_result("Fabric Stress Validation", result)


def _render_history_tab() -> None:
    st.header("Validation History")

    history = st.session_state.get("analytics_validation_history", [])

    if not history:
        st.info("No validation history yet.")
        return

    rows = []

    for item in history:
        result = item.get("result", {})
        summary = result.get("summary", {}) if isinstance(result, dict) else {}

        rows.append(
            {
                "Name": item.get("name"),
                "Duration Seconds": item.get("duration_seconds"),
                "Generated At": item.get("generated_at"),
                "Status": summary.get("status"),
                "Passed": summary.get("passed"),
                "Failed": summary.get("failed"),
                "Warnings": summary.get("warnings"),
                "Total": summary.get("total"),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Clear History", use_container_width=True):
        st.session_state["analytics_validation_history"] = []
        st.rerun()


def _render_export_tab() -> None:
    st.header("Export Validation Results")

    history = st.session_state.get("analytics_validation_history", [])

    if not history:
        st.info("No validation history to export.")
        return

    json_payload = json.dumps(
        history,
        indent=2,
        default=_json_default,
    )

    st.download_button(
        "Download Validation History JSON",
        data=json_payload,
        file_name=f"analytics_validation_history_{int(time.time())}.json",
        mime="application/json",
        use_container_width=True,
    )

    rows = []

    for item in history:
        result = item.get("result", {})
        summary = result.get("summary", {}) if isinstance(result, dict) else {}

        rows.append(
            {
                "name": item.get("name"),
                "duration_seconds": item.get("duration_seconds"),
                "generated_at": item.get("generated_at"),
                "status": summary.get("status"),
                "passed": summary.get("passed"),
                "failed": summary.get("failed"),
                "warnings": summary.get("warnings"),
                "total": summary.get("total"),
            }
        )

    csv_payload = pd.DataFrame(rows).to_csv(index=False)

    st.download_button(
        "Download Validation History CSV",
        data=csv_payload,
        file_name=f"analytics_validation_history_{int(time.time())}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_analytics_validation_dashboard(
    storage: Optional[Any] = None,
    fabric: Optional[Any] = None,
) -> None:
    render_analytics_fabric_validation_dashboard(
        storage=storage,
        fabric=fabric,
    )