"""
modules/analytics/analytics_stress_test_suite.py

Analytics Fabric Stress Test Suite

Purpose
-------
Runs higher-volume validation against the Analytics Fabric backend modules:

    - UniverseJobRegistry
    - UniverseExecutionQueue
    - IntelligentAnalyticsScheduler
    - UniverseWorkloadBalancer
    - UniverseRuntimeController
    - UniverseAnalyticsOrchestrator
    - AnalyticsResourceGovernor
    - AutonomousAnalyticsOptimizer

This suite is intentionally UI-independent and can be executed from:

    python -m modules.analytics.analytics_stress_test_suite

or imported from another runner.

It focuses on:
    - load simulation
    - integration pressure
    - queue/lease behavior
    - scheduler fan-out
    - balancer capacity behavior
    - runtime tick behavior
    - governor overload decisions
    - optimizer recommendation generation

Design rules:
    - no global runtime state
    - explicit dependency injection
    - short-lived SQLite handled by underlying services
    - deterministic generated IDs where practical
    - clear PASS/WARN/FAIL reporting
"""

from __future__ import annotations

import argparse
import os
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 2)


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def ensure_parent(path: str) -> None:
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Result Models
# =============================================================================

@dataclass
class StressTestResult:
    test_name: str
    status: str
    message: str
    duration_ms: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    traceback_text: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class StressTestSuiteResult:
    suite_name: str
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    results: List[StressTestResult] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> int:
        return len([r for r in self.results if r.status == "PASS"])

    @property
    def failed(self) -> int:
        return len([r for r in self.results if r.status == "FAIL"])

    @property
    def warnings(self) -> int:
        return len([r for r in self.results if r.status == "WARN"])

    @property
    def total(self) -> int:
        return len(self.results)

    def summary(self) -> Dict[str, Any]:
        return {
            "suite": self.suite_name,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "total": self.total,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "config": self.config,
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            **self.summary(),
            "results": [asdict(r) for r in self.results],
        }


@dataclass
class StressTestConfig:
    db_path: str = "data/analytics_fabric_stress_test.db"
    reset_db: bool = True

    tenant_count: int = 10
    universes_per_tenant: int = 10
    schedules_per_universe: int = 1
    registry_job_count: int = 10000
    queue_job_count: int = 10000
    worker_count: int = 50
    worker_capacity: int = 25
    balancer_job_count: int = 10000

    runtime_claim_limit: int = 250
    optimizer_samples: int = 25

    fail_fast: bool = False
    verbose: bool = True

    @property
    def total_universes(self) -> int:
        return self.tenant_count * self.universes_per_tenant

    @property
    def total_schedules(self) -> int:
        return self.total_universes * self.schedules_per_universe


# =============================================================================
# Dependency Factory
# =============================================================================

@dataclass
class AnalyticsFabricDependencies:
    registry: Any
    queue: Any
    scheduler: Any
    balancer: Any
    runtime_controller: Any
    orchestrator: Any
    governor: Any
    optimizer: Any


def build_default_dependencies(config: StressTestConfig) -> AnalyticsFabricDependencies:
    """
    Builds fresh Analytics Fabric dependencies for stress testing.

    This assumes the previously-built analytics modules exist:

        modules.analytics.universe_job_registry
        modules.analytics.universe_execution_queue
        modules.analytics.universe_workload_balancer
        modules.analytics.universe_runtime_controller
        modules.analytics.intelligent_analytics_scheduler
        modules.analytics.universe_analytics_orchestrator
        modules.analytics.analytics_resource_governor
        modules.analytics.autonomous_analytics_optimizer
    """

    ensure_parent(config.db_path)

    if config.reset_db and os.path.exists(config.db_path):
        os.remove(config.db_path)

    from modules.analytics.universe_job_registry import UniverseJobRegistry
    from modules.analytics.universe_execution_queue import UniverseExecutionQueue
    from modules.analytics.universe_workload_balancer import UniverseWorkloadBalancer
    from modules.analytics.universe_runtime_controller import UniverseRuntimeController
    from modules.analytics.intelligent_analytics_scheduler import IntelligentAnalyticsScheduler
    from modules.analytics.universe_analytics_orchestrator import UniverseAnalyticsOrchestrator
    from modules.analytics.analytics_resource_governor import AnalyticsResourceGovernor
    from modules.analytics.autonomous_analytics_optimizer import AutonomousAnalyticsOptimizer

    registry = UniverseJobRegistry(db_path=config.db_path)
    queue = UniverseExecutionQueue(registry=registry, db_path=config.db_path)
    balancer = UniverseWorkloadBalancer()
    runtime = UniverseRuntimeController(
        registry=registry,
        queue=queue,
        balancer=balancer,
        db_path=config.db_path,
        max_claims_per_tick=config.runtime_claim_limit,
    )
    scheduler = IntelligentAnalyticsScheduler(registry=registry)
    orchestrator = UniverseAnalyticsOrchestrator(
        registry=registry,
        scheduler=scheduler,
        execution_queue=queue,
        workload_balancer=balancer,
        runtime_controller=runtime,
    )
    governor = AnalyticsResourceGovernor()
    optimizer = AutonomousAnalyticsOptimizer()

    return AnalyticsFabricDependencies(
        registry=registry,
        queue=queue,
        scheduler=scheduler,
        balancer=balancer,
        runtime_controller=runtime,
        orchestrator=orchestrator,
        governor=governor,
        optimizer=optimizer,
    )


# =============================================================================
# Stress Suite
# =============================================================================

class AnalyticsStressTestSuite:
    """
    Higher-volume Analytics Fabric validation suite.

    The suite intentionally runs tests in dependency order:

        1. tenant/universe setup
        2. scheduler load
        3. registry load
        4. queue load
        5. balancer load
        6. runtime load
        7. governor overload
        8. optimizer pressure

    Each test returns a StressTestResult rather than raising,
    so failures are visible and actionable.
    """

    def __init__(
        self,
        *,
        dependencies: AnalyticsFabricDependencies,
        config: StressTestConfig,
    ) -> None:
        self.deps = dependencies
        self.config = config
        self.tenant_ids: List[str] = []
        self.universe_ids_by_tenant: Dict[str, List[str]] = {}
        self.generated_job_ids: List[Tuple[str, str]] = []

    # =========================================================================
    # Public Runner
    # =========================================================================

    def run_all(self) -> StressTestSuiteResult:
        suite = StressTestSuiteResult(
            suite_name="Analytics Fabric Stress Validation",
            config=asdict(self.config),
        )

        tests: List[Callable[[], StressTestResult]] = [
            self.test_setup_tenants_and_universes,
            self.test_scheduler_load,
            self.test_registry_load,
            self.test_queue_load,
            self.test_balancer_load,
            self.test_runtime_load,
            self.test_governor_overload,
            self.test_optimizer_pressure,
        ]

        for test in tests:
            result = test()
            suite.results.append(result)

            if self.config.verbose:
                self._print_result(result)

            if self.config.fail_fast and result.status == "FAIL":
                break

        suite.completed_at = utc_now_iso()
        return suite

    # =========================================================================
    # Test 1: Tenants / Universes
    # =========================================================================

    def test_setup_tenants_and_universes(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            for tenant_idx in range(self.config.tenant_count):
                tenant_id = f"stress_tenant_{tenant_idx:04d}"
                self.tenant_ids.append(tenant_id)

                if hasattr(self.deps.orchestrator, "register_tenant"):
                    self.deps.orchestrator.register_tenant(
                        tenant_id=tenant_id,
                        tenant_name=f"Stress Tenant {tenant_idx}",
                        max_jobs=max(
                            self.config.registry_job_count,
                            self.config.queue_job_count,
                            5000,
                        ),
                        metadata={"source": "stress_test"},
                    )

                self.universe_ids_by_tenant[tenant_id] = []

                for universe_idx in range(self.config.universes_per_tenant):
                    universe_id = f"stress_universe_{tenant_idx:04d}_{universe_idx:04d}"
                    self.universe_ids_by_tenant[tenant_id].append(universe_id)

                    if hasattr(self.deps.orchestrator, "register_universe"):
                        self.deps.orchestrator.register_universe(
                            tenant_id=tenant_id,
                            universe_id=universe_id,
                            universe_name=f"Stress Universe {tenant_idx}-{universe_idx}",
                            description="Stress test universe",
                            metadata={
                                "symbol_count": 100,
                                "source": "stress_test",
                            },
                        )

            expected_universes = self.config.total_universes
            actual_universes = sum(len(v) for v in self.universe_ids_by_tenant.values())

            if actual_universes != expected_universes:
                return self._result(
                    "Tenant/Universe Setup",
                    "FAIL",
                    "Universe count mismatch.",
                    start,
                    {
                        "expected_universes": expected_universes,
                        "actual_universes": actual_universes,
                    },
                )

            return self._result(
                "Tenant/Universe Setup",
                "PASS",
                "Tenants and universes registered.",
                start,
                {
                    "tenants": len(self.tenant_ids),
                    "universes": actual_universes,
                },
            )

        except Exception as exc:
            return self._exception("Tenant/Universe Setup", exc, start)

    # =========================================================================
    # Test 2: Scheduler Load
    # =========================================================================

    def test_scheduler_load(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            schedules_created = 0

            for tenant_id in self.tenant_ids:
                for universe_id in self.universe_ids_by_tenant.get(tenant_id, []):
                    for schedule_idx in range(self.config.schedules_per_universe):
                        self.deps.scheduler.register_schedule(
                            tenant_id=tenant_id,
                            universe_id=universe_id,
                            schedule_name=f"Stress Schedule {schedule_idx}",
                            job_type="UNIVERSE_REFRESH",
                            schedule_type="HOURLY",
                            priority="NORMAL",
                            interval_minutes=60,
                            market_hours_only=False,
                            payload={
                                "stress_test": True,
                                "schedule_index": schedule_idx,
                            },
                        )
                        schedules_created += 1

            cycle = self.deps.scheduler.run_scheduler_cycle()
            jobs_created = safe_int(cycle.get("jobs_created"), 0)

            status = "PASS"
            message = "Scheduler load cycle completed."

            if jobs_created < schedules_created:
                status = "WARN"
                message = "Scheduler completed, but fewer jobs were created than schedules."

            return self._result(
                "Scheduler Load",
                status,
                message,
                start,
                {
                    "schedules_created": schedules_created,
                    "jobs_created": jobs_created,
                    "due_schedules": cycle.get("due_schedules"),
                    "skipped": cycle.get("skipped"),
                },
            )

        except Exception as exc:
            return self._exception("Scheduler Load", exc, start)

    # =========================================================================
    # Test 3: Registry Load
    # =========================================================================

    def test_registry_load(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            created = 0

            if not self.tenant_ids:
                return self._result(
                    "Registry Load",
                    "FAIL",
                    "No tenants available.",
                    start,
                )

            for idx in range(self.config.registry_job_count):
                tenant_id = self.tenant_ids[idx % len(self.tenant_ids)]
                universes = self.universe_ids_by_tenant.get(tenant_id, [])
                universe_id = universes[idx % len(universes)] if universes else "stress_universe_default"

                job = self.deps.registry.register_job(
                    tenant_id=tenant_id,
                    universe_id=universe_id,
                    job_type="TECHNICALS",
                    priority="NORMAL",
                    provider="STRESS_PROVIDER",
                    symbol=f"SYM{idx:05d}",
                    payload={
                        "stress_test": True,
                        "index": idx,
                        "estimated_runtime_seconds": 1.0,
                    },
                    correlation_id="stress_registry_load",
                    tags=["stress", "registry"],
                )

                self.generated_job_ids.append((tenant_id, job.job_id))
                created += 1

            sample_tenant = self.tenant_ids[0]
            summary = self.deps.registry.summarize_jobs(tenant_id=sample_tenant)

            return self._result(
                "Registry Load",
                "PASS",
                "Registry bulk job creation completed.",
                start,
                {
                    "jobs_created": created,
                    "sample_tenant": sample_tenant,
                    "sample_summary": summary,
                    "jobs_per_second": self._rate(created, start),
                },
            )

        except Exception as exc:
            return self._exception("Registry Load", exc, start)

    # =========================================================================
    # Test 4: Queue Load
    # =========================================================================

    def test_queue_load(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            if not self.generated_job_ids:
                return self._result(
                    "Queue Load",
                    "FAIL",
                    "No registry jobs available for queue load test.",
                    start,
                )

            enqueued = 0

            for tenant_id, job_id in self.generated_job_ids[: self.config.queue_job_count]:
                queued = self.deps.queue.enqueue_job(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    priority="NORMAL",
                )

                if queued:
                    enqueued += 1

            metrics = self.deps.queue.queue_metrics()
            depth = safe_int(metrics.get("queue_depth"), 0)

            status = "PASS"
            message = "Queue load completed."

            if depth <= 0:
                status = "FAIL"
                message = "Queue depth did not increase."

            return self._result(
                "Queue Load",
                status,
                message,
                start,
                {
                    "attempted": min(len(self.generated_job_ids), self.config.queue_job_count),
                    "enqueued": enqueued,
                    "queue_metrics": metrics,
                    "enqueue_per_second": self._rate(enqueued, start),
                },
            )

        except Exception as exc:
            return self._exception("Queue Load", exc, start)

    # =========================================================================
    # Test 5: Balancer Load
    # =========================================================================

    def test_balancer_load(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            from modules.analytics.universe_workload_balancer import (
                AnalyticsWorker,
                AnalyticsWorkItem,
            )

            workers = [
                AnalyticsWorker(
                    worker_id=f"stress_worker_{idx:04d}",
                    capacity=self.config.worker_capacity,
                    active_jobs=0,
                    provider_affinity=["STRESS_PROVIDER"] if idx % 2 == 0 else [],
                    supported_job_types=["TECHNICALS", "UNIVERSE_REFRESH"],
                )
                for idx in range(self.config.worker_count)
            ]

            jobs: List[Any] = []
            tenant_count = max(1, len(self.tenant_ids))

            for idx in range(self.config.balancer_job_count):
                tenant_id = self.tenant_ids[idx % tenant_count] if self.tenant_ids else "stress_tenant_default"
                universes = self.universe_ids_by_tenant.get(tenant_id, ["stress_universe_default"])
                universe_id = universes[idx % len(universes)]

                jobs.append(
                    AnalyticsWorkItem(
                        job_id=f"stress_balance_job_{idx:06d}",
                        tenant_id=tenant_id,
                        universe_id=universe_id,
                        job_type="TECHNICALS",
                        priority="HIGH" if idx % 10 == 0 else "NORMAL",
                        provider="STRESS_PROVIDER",
                        symbol=f"SYM{idx:05d}",
                        estimated_runtime_seconds=1.0,
                    )
                )

            plan = self.deps.balancer.build_plan(
                workers=workers,
                queued_jobs=jobs,
            )

            total_capacity = self.config.worker_count * self.config.worker_capacity
            assignments = len(plan.assignments)
            held_jobs = len(plan.held_jobs)

            status = "PASS"
            message = "Balancer load plan generated."

            if assignments > total_capacity:
                status = "FAIL"
                message = "Balancer exceeded worker capacity."
            elif assignments == 0:
                status = "FAIL"
                message = "Balancer created no assignments."
            elif held_jobs == 0 and self.config.balancer_job_count > total_capacity:
                status = "WARN"
                message = "No held jobs detected despite jobs exceeding capacity."

            return self._result(
                "Balancer Load",
                status,
                message,
                start,
                {
                    "workers": self.config.worker_count,
                    "worker_capacity": self.config.worker_capacity,
                    "total_capacity": total_capacity,
                    "jobs": len(jobs),
                    "assignments": assignments,
                    "held_jobs": held_jobs,
                    "plan_decision": plan.decision,
                    "plan_metrics": plan.metrics,
                },
            )

        except Exception as exc:
            return self._exception("Balancer Load", exc, start)

    # =========================================================================
    # Test 6: Runtime Load
    # =========================================================================

    def test_runtime_load(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            self.deps.runtime_controller.start(metadata={"source": "stress_test"})

            registered_workers = 0
            for idx in range(self.config.worker_count):
                self.deps.runtime_controller.register_worker(
                    worker_id=f"stress_runtime_worker_{idx:04d}",
                    capacity=self.config.worker_capacity,
                    provider_affinity=["STRESS_PROVIDER"] if idx % 2 == 0 else [],
                    supported_job_types=["TECHNICALS", "UNIVERSE_REFRESH"],
                    metadata={"source": "stress_test"},
                )
                registered_workers += 1

            def execute_callback(job: Any, lease: Any) -> Dict[str, Any]:
                return {
                    "result_ref": f"stress_result_{job.job_id}",
                    "job_id": job.job_id,
                    "lease_id": lease.lease_id,
                }

            tick = self.deps.runtime_controller.tick(
                execute_callback=execute_callback,
            )

            runtime_metrics = self.deps.runtime_controller.runtime_metrics()

            status = "PASS"
            message = "Runtime load tick completed."

            if tick.leases_claimed == 0:
                status = "WARN"
                message = "Runtime tick completed but claimed no leases."

            if tick.failed_jobs > 0:
                status = "WARN"
                message = "Runtime tick completed with failed jobs."

            return self._result(
                "Runtime Load",
                status,
                message,
                start,
                {
                    "registered_workers": registered_workers,
                    "workers_seen": tick.workers_seen,
                    "queued_jobs_seen": tick.queued_jobs_seen,
                    "assignments_created": tick.assignments_created,
                    "leases_claimed": tick.leases_claimed,
                    "completed_jobs": tick.completed_jobs,
                    "failed_jobs": tick.failed_jobs,
                    "recovered_leases": tick.recovered_leases,
                    "runtime_metrics": runtime_metrics,
                },
            )

        except Exception as exc:
            return self._exception("Runtime Load", exc, start)

    # =========================================================================
    # Test 7: Governor Overload
    # =========================================================================

    def test_governor_overload(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            from modules.analytics.analytics_resource_governor import (
                ProviderBudget,
                RuntimeCapacity,
                TenantQuota,
            )

            self.deps.governor.register_provider_budget(
                ProviderBudget(
                    provider_name="STRESS_PROVIDER",
                    daily_limit=1000,
                    hourly_limit=100,
                    current_daily_usage=950,
                    current_hourly_usage=99,
                    throttle_threshold=0.90,
                    enabled=True,
                )
            )

            self.deps.governor.register_tenant_quota(
                TenantQuota(
                    tenant_id="stress_tenant_0000",
                    max_jobs=100,
                    current_jobs=100,
                    max_running_jobs=10,
                    current_running_jobs=10,
                    max_hourly_submissions=100,
                    current_hourly_submissions=100,
                )
            )

            overloaded_capacity = RuntimeCapacity(
                workers_online=1,
                workers_total=self.config.worker_count,
                queue_depth=1000000,
                active_leases=10000,
                active_jobs=10000,
                available_capacity=0,
                worker_utilization=1.0,
                failed_job_rate=0.50,
            )

            dispatch_decision = self.deps.governor.evaluate_runtime_dispatch(
                overloaded_capacity
            )
            provider_decision = self.deps.governor.evaluate_provider_consumption(
                "STRESS_PROVIDER"
            )
            tenant_decision = self.deps.governor.evaluate_tenant_consumption(
                "stress_tenant_0000"
            )
            health_decision = self.deps.governor.evaluate_system_health(
                overloaded_capacity
            )

            decisions = [
                dispatch_decision.decision,
                provider_decision.decision,
                tenant_decision.decision,
                health_decision.decision,
            ]

            status = "PASS"
            message = "Governor overload decisions generated."

            if all(d == "ALLOW" for d in decisions):
                status = "FAIL"
                message = "Governor allowed all overload conditions."

            return self._result(
                "Governor Overload",
                status,
                message,
                start,
                {
                    "dispatch": dispatch_decision.decision,
                    "provider": provider_decision.decision,
                    "tenant": tenant_decision.decision,
                    "health": health_decision.decision,
                    "metrics": self.deps.governor.governance_metrics(),
                },
            )

        except Exception as exc:
            return self._exception("Governor Overload", exc, start)

    # =========================================================================
    # Test 8: Optimizer Pressure
    # =========================================================================

    def test_optimizer_pressure(self) -> StressTestResult:
        start = time.perf_counter()

        try:
            from modules.analytics.autonomous_analytics_optimizer import (
                OptimizationTelemetry,
            )

            for idx in range(self.config.optimizer_samples):
                self.deps.optimizer.collect_telemetry(
                    OptimizationTelemetry(
                        queue_depth=5000 + (idx * 500),
                        active_leases=100 + idx,
                        workers_online=max(1, self.config.worker_count),
                        worker_utilization=min(0.99, 0.80 + (idx * 0.005)),
                        failed_jobs=25 + idx,
                        completed_jobs=max(1, 100 - idx),
                        avg_execution_time_seconds=5.0 + idx,
                        avg_queue_wait_seconds=300 + (idx * 25),
                        provider_metrics={
                            "STRESS_PROVIDER": {
                                "avg_latency_ms": 2500 + (idx * 10),
                                "failure_rate": 0.15,
                                "success_rate": 0.85,
                                "failures": 10 + idx,
                                "throttle_events": 3,
                            }
                        },
                        scheduler_metrics={
                            "due_schedules": 1000 + idx,
                            "jobs_created": 1000 + idx,
                        },
                        runtime_metrics={
                            "failed_job_rate": 0.25,
                            "completion_rate": 0.75,
                        },
                        tenant_metrics={
                            "stress_tenant_0000": {
                                "jobs_submitted": 1000,
                                "jobs_completed": 750,
                                "avg_runtime_seconds": 5.0,
                            }
                        },
                        universe_metrics={
                            "stress_universe_0000_0000": {
                                "jobs_completed": 500,
                                "avg_runtime_seconds": 4.5,
                                "refresh_interval_minutes": 60,
                            }
                        },
                    )
                )

            plan = self.deps.optimizer.generate_optimization_plan()
            executions = self.deps.optimizer.execute_safe_optimizations(plan)
            metrics = self.deps.optimizer.optimization_metrics()

            status = "PASS"
            message = "Optimizer pressure plan generated."

            if len(plan.recommendations) == 0:
                status = "FAIL"
                message = "Optimizer generated no recommendations under pressure."

            return self._result(
                "Optimizer Pressure",
                status,
                message,
                start,
                {
                    "telemetry_samples": self.config.optimizer_samples,
                    "recommendations": len(plan.recommendations),
                    "executions": len(executions),
                    "estimated_improvement_pct": getattr(plan, "estimated_improvement_pct", None),
                    "metrics": metrics,
                },
            )

        except Exception as exc:
            return self._exception("Optimizer Pressure", exc, start)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _result(
        self,
        test_name: str,
        status: str,
        message: str,
        start: float,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StressTestResult:
        return StressTestResult(
            test_name=test_name,
            status=status,
            message=message,
            duration_ms=ms_since(start),
            metrics=metrics or {},
        )

    def _exception(
        self,
        test_name: str,
        exc: Exception,
        start: float,
    ) -> StressTestResult:
        return StressTestResult(
            test_name=test_name,
            status="FAIL",
            message=str(exc),
            duration_ms=ms_since(start),
            error=repr(exc),
            traceback_text=traceback.format_exc(),
        )

    def _rate(self, count: int, start: float) -> float:
        elapsed = max(0.001, time.perf_counter() - start)
        return round(float(count) / elapsed, 2)

    def _print_result(self, result: StressTestResult) -> None:
        print(
            f"{result.status:5} | "
            f"{result.test_name:24} | "
            f"{result.duration_ms:10.2f} ms | "
            f"{result.message}"
        )
        if result.status == "FAIL" and result.traceback_text:
            print(result.traceback_text)


# =============================================================================
# Public Convenience API
# =============================================================================

def run_analytics_stress_validation(
    *,
    dependencies: Optional[AnalyticsFabricDependencies] = None,
    config: Optional[StressTestConfig] = None,
) -> StressTestSuiteResult:
    config = config or StressTestConfig()
    dependencies = dependencies or build_default_dependencies(config)

    suite = AnalyticsStressTestSuite(
        dependencies=dependencies,
        config=config,
    )

    return suite.run_all()


# =============================================================================
# CLI
# =============================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Analytics Fabric stress validation."
    )

    parser.add_argument(
        "--db-path",
        default="data/analytics_fabric_stress_test.db",
        help="SQLite DB path for the stress test.",
    )
    parser.add_argument(
        "--no-reset-db",
        action="store_true",
        help="Do not remove the stress test DB before running.",
    )
    parser.add_argument("--tenants", type=int, default=10)
    parser.add_argument("--universes-per-tenant", type=int, default=10)
    parser.add_argument("--schedules-per-universe", type=int, default=1)
    parser.add_argument("--registry-jobs", type=int, default=10000)
    parser.add_argument("--queue-jobs", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=50)
    parser.add_argument("--worker-capacity", type=int, default=25)
    parser.add_argument("--balancer-jobs", type=int, default=10000)
    parser.add_argument("--runtime-claim-limit", type=int, default=250)
    parser.add_argument("--optimizer-samples", type=int, default=25)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--quiet", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    config = StressTestConfig(
        db_path=args.db_path,
        reset_db=not args.no_reset_db,
        tenant_count=args.tenants,
        universes_per_tenant=args.universes_per_tenant,
        schedules_per_universe=args.schedules_per_universe,
        registry_job_count=args.registry_jobs,
        queue_job_count=args.queue_jobs,
        worker_count=args.workers,
        worker_capacity=args.worker_capacity,
        balancer_job_count=args.balancer_jobs,
        runtime_claim_limit=args.runtime_claim_limit,
        optimizer_samples=args.optimizer_samples,
        fail_fast=args.fail_fast,
        verbose=not args.quiet,
    )

    print("\n=== ANALYTICS FABRIC STRESS VALIDATION ===")
    print(f"Started: {utc_now_iso()}")
    print(f"DB: {config.db_path}")
    print(
        "Config: "
        f"tenants={config.tenant_count}, "
        f"universes={config.total_universes}, "
        f"schedules={config.total_schedules}, "
        f"registry_jobs={config.registry_job_count}, "
        f"queue_jobs={config.queue_job_count}, "
        f"workers={config.worker_count}, "
        f"worker_capacity={config.worker_capacity}"
    )
    print("")

    suite = run_analytics_stress_validation(config=config)

    print("\n=== STRESS VALIDATION SUMMARY ===")
    print(suite.summary())

    return 1 if suite.failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
