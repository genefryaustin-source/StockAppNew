"""
modules/analytics/analytics_fabric_stress_validation.py
"""

from __future__ import annotations

import os
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir(path: str) -> None:
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AnalyticsFabricStressConfig:
    db_path: str = "data/analytics_fabric_stress_validation.db"
    reset_db: bool = True

    tenant_count: int = 10
    universes_per_tenant: int = 10
    jobs_per_universe: int = 100

    worker_count: int = 50
    worker_capacity: int = 250
    provider_count: int = 5
    runtime_cycles: int = 3

    verbose: bool = True
    fail_fast: bool = False

    @property
    def total_universes(self) -> int:
        return self.tenant_count * self.universes_per_tenant

    @property
    def total_jobs(self) -> int:
        return self.total_universes * self.jobs_per_universe


@dataclass
class StressValidationCheck:
    name: str
    status: str
    message: str
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    traceback_text: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class StressValidationSummary:
    stress_id: str
    passed: int
    failed: int
    warnings: int
    total: int
    status: str
    config: Dict[str, Any]
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class AnalyticsFabricStressResult:
    stress_id: str
    checks: List[StressValidationCheck]
    summary: StressValidationSummary
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stress_id": self.stress_id,
            "checks": [asdict(c) for c in self.checks],
            "summary": asdict(self.summary),
            "generated_at": self.generated_at,
        }


class AnalyticsFabricStressValidation:
    def __init__(
        self,
        *,
        config: Optional[AnalyticsFabricStressConfig] = None,
        fabric: Optional[Any] = None,
    ) -> None:
        self.config = config or AnalyticsFabricStressConfig()
        self.fabric = fabric

        self.tenant_ids: List[str] = []
        self.universe_ids_by_tenant: Dict[str, List[str]] = {}
        self.job_ids_by_tenant: Dict[str, List[str]] = {}
        self.provider_names: List[str] = []
        self.worker_records: List[Dict[str, Any]] = []

    def run_all(self) -> AnalyticsFabricStressResult:
        stress_id = f"afstress_{uuid.uuid4().hex}"

        checks = []
        tests = [
            self.validate_bootstrap,
            self.validate_tenant_scale,
            self.validate_universe_scale,
            self.validate_job_scale,
            self.validate_queue_scale,
            self.validate_runtime_scale,
            self.validate_worker_capacity_scale,
            self.validate_provider_scale,
            self.validate_governance_scale,
            self.validate_global_planner_scale,
            self.validate_tenant_intelligence_scale,
            self.validate_fabric_summary_scale,
        ]

        for test in tests:
            check = test()
            checks.append(check)

            if self.config.verbose:
                print(
                    f"{check.status:5} | "
                    f"{check.name:32} | "
                    f"{check.duration_ms:10.2f} ms | "
                    f"{check.message}"
                )

            if self.config.fail_fast and check.status == "FAIL":
                break

        passed = len([c for c in checks if c.status == "PASS"])
        failed = len([c for c in checks if c.status == "FAIL"])
        warnings = len([c for c in checks if c.status == "WARN"])

        summary = StressValidationSummary(
            stress_id=stress_id,
            passed=passed,
            failed=failed,
            warnings=warnings,
            total=len(checks),
            status="PASS" if failed == 0 else "FAIL",
            config=asdict(self.config),
        )

        return AnalyticsFabricStressResult(
            stress_id=stress_id,
            checks=checks,
            summary=summary,
        )

    def validate_bootstrap(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            if self.fabric is None:
                from modules.analytics.analytics_fabric_bootstrap import (
                    AnalyticsFabricConfig,
                    build_analytics_fabric,
                )

                ensure_parent_dir(self.config.db_path)

                if self.config.reset_db and os.path.exists(self.config.db_path):
                    os.remove(self.config.db_path)

                self.fabric = build_analytics_fabric(
                    AnalyticsFabricConfig(
                        db_path=self.config.db_path,
                        reset_db=False,
                        runtime_max_claims_per_tick=1000,
                    )
                )

            return self._pass(
                "Bootstrap",
                "Fabric bootstrapped for stress validation.",
                start,
                {
                    "fabric_id": getattr(self.fabric, "fabric_id", None),
                    "db_path": self.config.db_path,
                },
            )

        except Exception as exc:
            return self._exception("Bootstrap", exc, start)

    def validate_tenant_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            self.tenant_ids = [
                f"stress_tenant_{i:05d}"
                for i in range(self.config.tenant_count)
            ]

            return self._pass(
                "Tenant Scale",
                "Tenant identifiers generated.",
                start,
                {"tenants": len(self.tenant_ids)},
            )

        except Exception as exc:
            return self._exception("Tenant Scale", exc, start)

    def validate_universe_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            for tenant_id in self.tenant_ids:
                self.universe_ids_by_tenant[tenant_id] = []

                for i in range(self.config.universes_per_tenant):
                    universe_id = f"{tenant_id}_universe_{i:05d}"
                    self.universe_ids_by_tenant[tenant_id].append(universe_id)

                    self.fabric.global_planner.register_universe(
                        tenant_id=tenant_id,
                        universe_id=universe_id,
                        universe_name=f"Universe {universe_id}",
                        priority="HIGH" if i % 10 == 0 else "NORMAL",
                        estimated_jobs=self.config.jobs_per_universe,
                        estimated_runtime_seconds=float(self.config.jobs_per_universe * 2),
                        estimated_cost_usd=float(self.config.jobs_per_universe) * 0.002,
                        preferred_provider="provider_000",
                        metadata={"source": "stress_validation"},
                    )

            total = sum(len(v) for v in self.universe_ids_by_tenant.values())

            if total != self.config.total_universes:
                return self._fail(
                    "Universe Scale",
                    "Universe count mismatch.",
                    start,
                    {
                        "expected": self.config.total_universes,
                        "actual": total,
                    },
                )

            return self._pass(
                "Universe Scale",
                "Universes registered into global planner.",
                start,
                {"universes": total},
            )

        except Exception as exc:
            return self._exception("Universe Scale", exc, start)

    def validate_job_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            total_processed = 0

            for tenant_id, universe_ids in self.universe_ids_by_tenant.items():
                self.job_ids_by_tenant.setdefault(tenant_id, [])

                for universe_id in universe_ids:
                    jobs = [
                        {
                            "job_type": "STRESS_ANALYTICS",
                            "priority": "HIGH" if j % 25 == 0 else "NORMAL",
                            "payload": {
                                "tenant_id": tenant_id,
                                "universe_id": universe_id,
                                "index": j,
                            },
                        }
                        for j in range(self.config.jobs_per_universe)
                    ]

                    result = self.fabric.bulk_operations.bulk_register_jobs(
                        tenant_id=tenant_id,
                        universe_id=universe_id,
                        jobs=jobs,
                    )

                    total_processed += result.processed

                    listed = self.fabric.registry.list_jobs(
                        tenant_id=tenant_id,
                        universe_id=universe_id,
                        job_type="STRESS_ANALYTICS",
                        limit=self.config.jobs_per_universe,
                    )

                    self.job_ids_by_tenant[tenant_id].extend(
                        [job.job_id for job in listed]
                    )

            if total_processed != self.config.total_jobs:
                return self._fail(
                    "Job Scale",
                    "Bulk job registration count mismatch.",
                    start,
                    {
                        "expected": self.config.total_jobs,
                        "actual": total_processed,
                    },
                )

            return self._pass(
                "Job Scale",
                "Bulk job registration completed.",
                start,
                {
                    "jobs_registered": total_processed,
                    "jobs_per_second": self._rate(total_processed, start),
                },
            )

        except Exception as exc:
            return self._exception("Job Scale", exc, start)

    def validate_queue_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            total_enqueued = 0

            for tenant_id, job_ids in self.job_ids_by_tenant.items():
                result = self.fabric.bulk_operations.bulk_enqueue_jobs(
                    tenant_id=tenant_id,
                    job_ids=job_ids,
                )
                total_enqueued += result.processed

            metrics = self.fabric.execution_queue.queue_metrics()

            if total_enqueued <= 0:
                return self._fail(
                    "Queue Scale",
                    "No jobs were enqueued.",
                    start,
                    metrics,
                )

            return self._pass(
                "Queue Scale",
                "Bulk queue population completed.",
                start,
                {
                    "jobs_enqueued": total_enqueued,
                    "queue_metrics": metrics,
                    "enqueue_per_second": self._rate(total_enqueued, start),
                },
            )

        except Exception as exc:
            return self._exception("Queue Scale", exc, start)

    def validate_runtime_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            runtime = self.fabric.runtime_controller
            runtime.start(metadata={"source": "stress_validation"})

            self.worker_records = []

            for i in range(self.config.worker_count):
                worker_id = f"stress_worker_{i:05d}"
                self.worker_records.append(
                    {
                        "worker_id": worker_id,
                        "state": "ONLINE",
                        "capacity": self.config.worker_capacity,
                        "active_jobs": min(i % max(1, self.config.worker_capacity), self.config.worker_capacity),
                        "jobs_completed": 1000 + i,
                        "jobs_failed": i % 7,
                        "avg_runtime_seconds": 3.0 + (i % 5),
                        "heartbeat_age_seconds": 1.0,
                    }
                )

                runtime.register_worker(
                    worker_id=worker_id,
                    capacity=self.config.worker_capacity,
                    supported_job_types=["STRESS_ANALYTICS"],
                    provider_affinity=self.provider_names or [],
                    metadata={"source": "stress_validation"},
                )

            completed = 0
            failed = 0
            leases = 0

            def execute_callback(job: Any, lease: Any) -> Dict[str, Any]:
                return {
                    "result_ref": f"stress_result_{uuid.uuid4().hex}",
                    "job_id": getattr(job, "job_id", None),
                    "lease_id": getattr(lease, "lease_id", None),
                }

            for _ in range(self.config.runtime_cycles):
                tick = runtime.tick(execute_callback=execute_callback)
                completed += int(getattr(tick, "completed_jobs", 0) or 0)
                failed += int(getattr(tick, "failed_jobs", 0) or 0)
                leases += int(getattr(tick, "leases_claimed", 0) or 0)

            metrics = runtime.runtime_metrics()

            return self._pass(
                "Runtime Scale",
                "Runtime cycles completed.",
                start,
                {
                    "runtime_cycles": self.config.runtime_cycles,
                    "leases_claimed": leases,
                    "completed_jobs": completed,
                    "failed_jobs": failed,
                    "runtime_metrics": metrics,
                },
            )

        except Exception as exc:
            return self._exception("Runtime Scale", exc, start)

    def validate_worker_capacity_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            queue_metrics = self.fabric.execution_queue.queue_metrics()

            report = self.fabric.worker_capacity_model.analyze_from_runtime(
                workers=self.worker_records,
                queue_metrics=queue_metrics,
                tenant_id=None,
                target_clear_minutes=15.0,
            )

            if not report.worker_profiles:
                return self._fail(
                    "Worker Capacity Scale",
                    "Worker capacity model produced no profiles.",
                    start,
                )

            return self._pass(
                "Worker Capacity Scale",
                "Worker capacity scale analysis completed.",
                start,
                {
                    "workers": len(report.worker_profiles),
                    "fleet": asdict(report.fleet_profile),
                    "forecast": asdict(report.forecast),
                    "recommendations": len(report.recommendations),
                },
            )

        except Exception as exc:
            return self._exception("Worker Capacity Scale", exc, start)

    def validate_provider_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            from modules.analytics.provider_cost_intelligence import ProviderUsageSample

            self.provider_names = [
                f"provider_{i:03d}"
                for i in range(self.config.provider_count)
            ]

            engine = self.fabric.provider_cost_intelligence

            for i, provider in enumerate(self.provider_names):
                engine.record_usage(
                    ProviderUsageSample(
                        provider=provider,
                        requests=10000 + (i * 500),
                        successes=9700 + (i * 400),
                        failures=100 + i,
                        throttles=50 + i,
                        quota_used=5000 + (i * 500),
                        quota_limit=20000,
                        average_latency_ms=150.0 + (i * 20),
                        total_cost_usd=25.0 + i,
                    )
                )
                engine.build_provider_profile(provider)

            recommendations = engine.generate_recommendations()
            ranked = engine.rank_providers()

            if not ranked:
                return self._fail(
                    "Provider Scale",
                    "Provider rankings were not generated.",
                    start,
                )

            return self._pass(
                "Provider Scale",
                "Provider intelligence scale analysis completed.",
                start,
                {
                    "providers": len(ranked),
                    "best_provider": ranked[0].provider,
                    "recommendations": len(recommendations),
                },
            )

        except Exception as exc:
            return self._exception("Provider Scale", exc, start)

    def validate_governance_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            queue_metrics = self.fabric.execution_queue.queue_metrics()

            worker_report = self.fabric.worker_capacity_model.analyze_from_runtime(
                workers=self.worker_records,
                queue_metrics=queue_metrics,
                tenant_id=None,
            )

            provider_profiles = list(
                getattr(self.fabric.provider_cost_intelligence, "provider_profiles", {}).values()
            )

            evaluation = self.fabric.execution_governor.evaluate_runtime_state(
                queue_metrics=queue_metrics,
                fleet_profile=worker_report.fleet_profile,
                provider_profiles=provider_profiles,
                tenant_metrics={"pressure": 0.35},
                universe_metrics={"pressure": 0.25},
            )

            return self._pass(
                "Governance Scale",
                "Execution governance scale evaluation completed.",
                start,
                {
                    "risk": asdict(evaluation.risk_profile),
                    "decisions": len(evaluation.decisions),
                },
            )

        except Exception as exc:
            return self._exception("Governance Scale", exc, start)

    def validate_global_planner_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            queue_metrics = self.fabric.execution_queue.queue_metrics()

            worker_report = self.fabric.worker_capacity_model.analyze_from_runtime(
                workers=self.worker_records,
                queue_metrics=queue_metrics,
                tenant_id=None,
            )

            provider_profiles = list(
                getattr(self.fabric.provider_cost_intelligence, "provider_profiles", {}).values()
            )

            plan = self.fabric.global_planner.build_execution_plan(
                queue_metrics=queue_metrics,
                worker_report=worker_report,
                provider_profiles=provider_profiles,
                tenant_metrics={"pressure": 0.25},
                universe_metrics={},
            )

            if not plan.universe_plans:
                return self._fail(
                    "Global Planner Scale",
                    "Global planner produced no universe plans.",
                    start,
                    plan.as_dict(),
                )

            return self._pass(
                "Global Planner Scale",
                "Global planner scale plan generated.",
                start,
                {
                    "plan_id": plan.plan_id,
                    "state": plan.state,
                    "total_universes": plan.total_universes,
                    "active_universes": plan.active_universes,
                    "deferred_universes": plan.deferred_universes,
                    "blocked_universes": plan.blocked_universes,
                    "forecast": asdict(plan.forecast),
                },
            )

        except Exception as exc:
            return self._exception("Global Planner Scale", exc, start)

    def validate_tenant_intelligence_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            from modules.analytics.tenant_universe_intelligence_engine import (
                TenantTelemetrySample,
                UniverseTelemetrySample,
            )

            tenant_samples = []
            universe_samples = []

            for tenant_id in self.tenant_ids:
                job_count = len(self.job_ids_by_tenant.get(tenant_id, []))

                tenant_samples.append(
                    TenantTelemetrySample(
                        tenant_id=tenant_id,
                        jobs_submitted=job_count,
                        jobs_completed=max(0, job_count - 10),
                        jobs_failed=10,
                        queue_depth=100,
                        active_jobs=25,
                        total_cost_usd=float(job_count) * 0.002,
                        provider_calls=job_count,
                        avg_runtime_seconds=5.0,
                        sla_breaches=1,
                        universes_active=len(self.universe_ids_by_tenant.get(tenant_id, [])),
                        universes_deferred=0,
                    )
                )

                for universe_id in self.universe_ids_by_tenant.get(tenant_id, []):
                    universe_samples.append(
                        UniverseTelemetrySample(
                            tenant_id=tenant_id,
                            universe_id=universe_id,
                            universe_name=universe_id,
                            jobs_submitted=self.config.jobs_per_universe,
                            jobs_completed=max(0, self.config.jobs_per_universe - 2),
                            jobs_failed=2,
                            symbols_processed=500,
                            analytics_generated=400,
                            refresh_interval_minutes=60,
                            avg_runtime_seconds=5.0,
                            p95_runtime_seconds=10.0,
                            total_cost_usd=float(self.config.jobs_per_universe) * 0.002,
                            provider_calls=self.config.jobs_per_universe,
                            stale_symbols=25,
                            sla_breaches=0,
                        )
                    )

            report = self.fabric.tenant_universe_intelligence.analyze(
                tenant_samples=tenant_samples,
                universe_samples=universe_samples,
            )

            if not report.tenant_profiles:
                return self._fail(
                    "Tenant Intelligence Scale",
                    "Tenant intelligence produced no tenant profiles.",
                    start,
                )

            if not report.universe_profiles:
                return self._fail(
                    "Tenant Intelligence Scale",
                    "Tenant intelligence produced no universe profiles.",
                    start,
                )

            return self._pass(
                "Tenant Intelligence Scale",
                "Tenant/universe intelligence scale analysis completed.",
                start,
                {
                    "tenant_profiles": len(report.tenant_profiles),
                    "universe_profiles": len(report.universe_profiles),
                    "recommendations": len(report.recommendations),
                },
            )

        except Exception as exc:
            return self._exception("Tenant Intelligence Scale", exc, start)

    def validate_fabric_summary_scale(self) -> StressValidationCheck:
        start = time.perf_counter()

        try:
            summary = self.fabric.summary()

            return self._pass(
                "Fabric Summary Scale",
                "Fabric summary generated after scale validation.",
                start,
                summary,
            )

        except Exception as exc:
            return self._exception("Fabric Summary Scale", exc, start)

    def _pass(
        self,
        name: str,
        message: str,
        start: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StressValidationCheck:
        return StressValidationCheck(
            name=name,
            status="PASS",
            message=message,
            duration_ms=self._elapsed_ms(start),
            metadata=metadata or {},
        )

    def _warn(
        self,
        name: str,
        message: str,
        start: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StressValidationCheck:
        return StressValidationCheck(
            name=name,
            status="WARN",
            message=message,
            duration_ms=self._elapsed_ms(start),
            metadata=metadata or {},
        )

    def _fail(
        self,
        name: str,
        message: str,
        start: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StressValidationCheck:
        return StressValidationCheck(
            name=name,
            status="FAIL",
            message=message,
            duration_ms=self._elapsed_ms(start),
            metadata=metadata or {},
        )

    def _exception(
        self,
        name: str,
        exc: Exception,
        start: float,
    ) -> StressValidationCheck:
        return StressValidationCheck(
            name=name,
            status="FAIL",
            message=str(exc),
            duration_ms=self._elapsed_ms(start),
            error=repr(exc),
            traceback_text=traceback.format_exc(),
        )

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return round((time.perf_counter() - start) * 1000.0, 2)

    @staticmethod
    def _rate(count: int, start: float) -> float:
        elapsed = max(0.001, time.perf_counter() - start)
        return round(count / elapsed, 2)


def run_analytics_fabric_stress_validation(
    *,
    config: Optional[AnalyticsFabricStressConfig] = None,
    fabric: Optional[Any] = None,
) -> AnalyticsFabricStressResult:
    suite = AnalyticsFabricStressValidation(
        config=config,
        fabric=fabric,
    )
    return suite.run_all()


def print_stress_validation_result(
    result: AnalyticsFabricStressResult,
) -> None:
    print()
    print("=== ANALYTICS FABRIC STRESS VALIDATION ===")
    print()

    for check in result.checks:
        print(
            f"{check.status:5} | "
            f"{check.name:32} | "
            f"{check.duration_ms:10.2f} ms | "
            f"{check.message}"
        )

        if check.status == "FAIL" and check.traceback_text:
            print(check.traceback_text)

    print()
    print("=" * 60)
    print(f"PASSED   : {result.summary.passed}")
    print(f"FAILED   : {result.summary.failed}")
    print(f"WARNINGS : {result.summary.warnings}")
    print(f"TOTAL    : {result.summary.total}")
    print(f"STATUS   : {result.summary.status}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    validation = run_analytics_fabric_stress_validation()
    print_stress_validation_result(validation)