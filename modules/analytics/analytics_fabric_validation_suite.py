"""
modules/analytics/analytics_fabric_validation_suite.py
"""

from __future__ import annotations

import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValidationCheck:
    name: str
    status: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    traceback_text: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class ValidationSuiteSummary:
    suite_id: str
    passed: int
    failed: int
    warnings: int
    total: int
    status: str
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class AnalyticsFabricValidationResult:
    suite_id: str
    checks: List[ValidationCheck]
    summary: ValidationSuiteSummary
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "checks": [asdict(c) for c in self.checks],
            "summary": asdict(self.summary),
            "generated_at": self.generated_at,
        }


class AnalyticsFabricValidationSuite:
    def __init__(
        self,
        *,
        fabric: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        self.fabric = fabric
        self.config = config
        self.test_tenant_id = "VALIDATION_TENANT"
        self.test_universe_id = "VALIDATION_UNIVERSE"
        self.test_provider = "VALIDATION_PROVIDER"

    def run_all(self) -> AnalyticsFabricValidationResult:
        suite_id = f"afv_{uuid.uuid4().hex}"

        checks = [
            self.validate_bootstrap(),
            self.validate_registry(),
            self.validate_queue(),
            self.validate_scheduler(),
            self.validate_orchestrator(),
            self.validate_runtime(),
            self.validate_bulk_operations(),
            self.validate_worker_capacity_model(),
            self.validate_provider_cost_intelligence(),
            self.validate_execution_governor(),
            self.validate_global_planner(),
            self.validate_tenant_intelligence(),
            self.validate_fabric_summary(),
        ]

        passed = len([c for c in checks if c.status == "PASS"])
        failed = len([c for c in checks if c.status == "FAIL"])
        warnings = len([c for c in checks if c.status == "WARN"])

        summary = ValidationSuiteSummary(
            suite_id=suite_id,
            passed=passed,
            failed=failed,
            warnings=warnings,
            total=len(checks),
            status="PASS" if failed == 0 else "FAIL",
        )

        return AnalyticsFabricValidationResult(
            suite_id=suite_id,
            checks=checks,
            summary=summary,
        )

    def validate_bootstrap(self) -> ValidationCheck:
        try:
            if self.fabric is None:
                from modules.analytics.analytics_fabric_bootstrap import (
                    AnalyticsFabricConfig,
                    build_analytics_fabric,
                    run_fabric_health_check,
                )

                config = self.config or AnalyticsFabricConfig(
                    db_path="data/analytics_fabric_validation.db",
                    reset_db=True,
                )

                self.fabric = build_analytics_fabric(config)

                health = run_fabric_health_check(self.fabric)

                if health.status != "PASS":
                    return self._warn(
                        "Bootstrap",
                        "Fabric bootstrapped but health check reported warnings.",
                        health.as_dict(),
                    )

            required = [
                "registry",
                "execution_queue",
                "workload_balancer",
                "runtime_controller",
                "scheduler",
                "orchestrator",
                "resource_governor",
                "optimizer",
                "bulk_operations",
                "worker_capacity_model",
                "provider_cost_intelligence",
                "execution_governor",
                "global_planner",
                "tenant_universe_intelligence",
            ]

            missing = [
                name for name in required
                if getattr(self.fabric, name, None) is None
            ]

            if missing:
                return self._fail(
                    "Bootstrap",
                    "Fabric missing required components.",
                    {"missing": missing},
                )

            return self._pass(
                "Bootstrap",
                "Analytics Fabric bootstrap verified.",
                {"fabric_id": self.fabric.fabric_id},
            )

        except Exception as exc:
            return self._exception("Bootstrap", exc)

    def validate_registry(self) -> ValidationCheck:
        try:
            job = self.fabric.registry.register_job(
                tenant_id=self.test_tenant_id,
                universe_id=self.test_universe_id,
                job_type="VALIDATION",
                priority="NORMAL",
                provider=self.test_provider,
                payload={"validation": True},
            )

            retrieved = self.fabric.registry.get_job(
                tenant_id=self.test_tenant_id,
                job_id=job.job_id,
            )

            if not retrieved:
                return self._fail(
                    "Registry",
                    "Registered validation job could not be retrieved.",
                    {"job_id": job.job_id},
                )

            return self._pass(
                "Registry",
                "Registry register/get verified.",
                {"job_id": job.job_id},
            )

        except Exception as exc:
            return self._exception("Registry", exc)

    def validate_queue(self) -> ValidationCheck:
        try:
            job = self.fabric.registry.register_job(
                tenant_id=self.test_tenant_id,
                universe_id=self.test_universe_id,
                job_type="QUEUE_VALIDATION",
                priority="NORMAL",
                payload={"validation": True},
            )

            enqueued = self.fabric.execution_queue.enqueue_job(
                tenant_id=self.test_tenant_id,
                job_id=job.job_id,
                priority="NORMAL",
            )

            metrics = self.fabric.execution_queue.queue_metrics()

            if not enqueued:
                return self._warn(
                    "Queue",
                    "Queue enqueue returned False; job may already have been queued.",
                    metrics,
                )

            return self._pass(
                "Queue",
                "Queue enqueue and metrics verified.",
                metrics,
            )

        except Exception as exc:
            return self._exception("Queue", exc)

    def validate_scheduler(self) -> ValidationCheck:
        try:
            schedule = self.fabric.scheduler.register_schedule(
                tenant_id=self.test_tenant_id,
                universe_id=self.test_universe_id,
                schedule_name="Validation Schedule",
                job_type="VALIDATION_SCHEDULED_JOB",
                schedule_type="HOURLY",
                priority="NORMAL",
                interval_minutes=60,
                market_hours_only=False,
                payload={"validation": True},
            )

            result = self.fabric.scheduler.run_scheduler_cycle()

            return self._pass(
                "Scheduler",
                "Scheduler registration and cycle verified.",
                {
                    "schedule_id": getattr(schedule, "schedule_id", None),
                    "result": result,
                },
            )

        except Exception as exc:
            return self._exception("Scheduler", exc)

    def validate_orchestrator(self) -> ValidationCheck:
        try:
            metrics = self.fabric.orchestrator.analytics_metrics()

            return self._pass(
                "Orchestrator",
                "Orchestrator metrics verified.",
                metrics,
            )

        except Exception as exc:
            return self._exception("Orchestrator", exc)

    def validate_runtime(self) -> ValidationCheck:
        try:
            runtime = self.fabric.runtime_controller

            runtime.start(metadata={"source": "analytics_fabric_validation"})

            runtime.register_worker(
                worker_id="validation_worker_1",
                capacity=10,
                provider_affinity=[self.test_provider],
                supported_job_types=["VALIDATION", "QUEUE_VALIDATION", "VALIDATION_SCHEDULED_JOB"],
                metadata={"source": "validation"},
            )

            def execute_callback(job: Any, lease: Any) -> Dict[str, Any]:
                return {
                    "job_id": getattr(job, "job_id", None),
                    "lease_id": getattr(lease, "lease_id", None),
                    "result_ref": f"validation_result_{uuid.uuid4().hex}",
                }

            tick = runtime.tick(execute_callback=execute_callback)
            metrics = runtime.runtime_metrics()

            return self._pass(
                "Runtime",
                "Runtime start/register/tick verified.",
                {
                    "tick": asdict(tick) if hasattr(tick, "__dataclass_fields__") else str(tick),
                    "metrics": metrics,
                },
            )

        except Exception as exc:
            return self._exception("Runtime", exc)

    def validate_bulk_operations(self) -> ValidationCheck:
        try:
            jobs = [
                {
                    "job_type": "BULK_VALIDATION",
                    "priority": "NORMAL",
                    "payload": {"i": i},
                }
                for i in range(100)
            ]

            register_result = self.fabric.bulk_operations.bulk_register_jobs(
                tenant_id=self.test_tenant_id,
                universe_id=self.test_universe_id,
                jobs=jobs,
            )

            listed = self.fabric.registry.list_jobs(
                tenant_id=self.test_tenant_id,
                job_type="BULK_VALIDATION",
                limit=100,
            )

            job_ids = [job.job_id for job in listed]

            enqueue_result = self.fabric.bulk_operations.bulk_enqueue_jobs(
                tenant_id=self.test_tenant_id,
                job_ids=job_ids,
            )

            status_result = self.fabric.bulk_operations.bulk_update_status(
                tenant_id=self.test_tenant_id,
                job_ids=job_ids,
                status="RUNNING",
            )

            complete_result = self.fabric.bulk_operations.bulk_complete_jobs(
                tenant_id=self.test_tenant_id,
                job_ids=job_ids,
            )

            if register_result.processed <= 0:
                return self._fail(
                    "Bulk Operations",
                    "Bulk registration processed no jobs.",
                    asdict(register_result),
                )

            return self._pass(
                "Bulk Operations",
                "Bulk register/enqueue/status/complete verified.",
                {
                    "register": asdict(register_result),
                    "enqueue": asdict(enqueue_result),
                    "status": asdict(status_result),
                    "complete": asdict(complete_result),
                },
            )

        except Exception as exc:
            return self._exception("Bulk Operations", exc)

    def validate_worker_capacity_model(self) -> ValidationCheck:
        try:
            from modules.analytics.worker_capacity_model import WorkerTelemetrySample

            samples = [
                WorkerTelemetrySample(
                    worker_id="validation_worker_1",
                    tenant_id=self.test_tenant_id,
                    state="ONLINE",
                    capacity=10,
                    active_jobs=5,
                    completed_jobs=100,
                    failed_jobs=2,
                    avg_runtime_seconds=5.0,
                    queue_depth_seen=100,
                    active_leases=5,
                ),
                WorkerTelemetrySample(
                    worker_id="validation_worker_2",
                    tenant_id=self.test_tenant_id,
                    state="ONLINE",
                    capacity=10,
                    active_jobs=1,
                    completed_jobs=80,
                    failed_jobs=1,
                    avg_runtime_seconds=4.0,
                    queue_depth_seen=100,
                    active_leases=1,
                ),
            ]

            report = self.fabric.worker_capacity_model.analyze(
                samples=samples,
                queue_depth=100,
                active_leases=6,
                tenant_id=self.test_tenant_id,
            )

            if not report.worker_profiles:
                return self._fail(
                    "Worker Capacity",
                    "Worker capacity model generated no profiles.",
                )

            return self._pass(
                "Worker Capacity",
                "Worker capacity analysis verified.",
                report.as_dict(),
            )

        except Exception as exc:
            return self._exception("Worker Capacity", exc)

    def validate_provider_cost_intelligence(self) -> ValidationCheck:
        try:
            from modules.analytics.provider_cost_intelligence import ProviderUsageSample

            engine = self.fabric.provider_cost_intelligence

            engine.record_usage(
                ProviderUsageSample(
                    provider=self.test_provider,
                    requests=1000,
                    successes=970,
                    failures=20,
                    throttles=10,
                    quota_used=1000,
                    quota_limit=10000,
                    average_latency_ms=250.0,
                    total_cost_usd=5.0,
                )
            )

            profile = engine.build_provider_profile(self.test_provider)
            recommendations = engine.generate_recommendations()
            ranked = engine.rank_providers()

            if profile is None:
                return self._fail(
                    "Provider Intelligence",
                    "Provider profile was not generated.",
                )

            return self._pass(
                "Provider Intelligence",
                "Provider cost intelligence verified.",
                {
                    "profile": asdict(profile),
                    "recommendations": [asdict(r) for r in recommendations],
                    "ranked_count": len(ranked),
                },
            )

        except Exception as exc:
            return self._exception("Provider Intelligence", exc)

    def validate_execution_governor(self) -> ValidationCheck:
        try:
            queue_metrics = self.fabric.execution_queue.queue_metrics()

            worker_report = self.fabric.worker_capacity_model.analyze_from_runtime(
                workers=[
                    {
                        "worker_id": "gov_worker_1",
                        "state": "ONLINE",
                        "capacity": 10,
                        "active_jobs": 9,
                        "jobs_completed": 100,
                        "jobs_failed": 2,
                        "avg_runtime_seconds": 5.0,
                    }
                ],
                queue_metrics=queue_metrics,
                tenant_id=self.test_tenant_id,
            )

            provider_profiles = list(
                getattr(self.fabric.provider_cost_intelligence, "provider_profiles", {}).values()
            )

            evaluation = self.fabric.execution_governor.evaluate_runtime_state(
                queue_metrics=queue_metrics,
                fleet_profile=worker_report.fleet_profile,
                provider_profiles=provider_profiles,
                tenant_metrics={"pressure": 0.2},
                universe_metrics={"pressure": 0.2},
            )

            return self._pass(
                "Execution Governor",
                "Autonomous execution governor verified.",
                evaluation.as_dict(),
            )

        except Exception as exc:
            return self._exception("Execution Governor", exc)

    def validate_global_planner(self) -> ValidationCheck:
        try:
            from modules.analytics.global_analytics_planner import PlannedUniverse

            universe = PlannedUniverse(
                tenant_id=self.test_tenant_id,
                universe_id=self.test_universe_id,
                universe_name="Validation Universe",
                priority="HIGH",
                estimated_jobs=100,
                estimated_runtime_seconds=500.0,
                estimated_cost_usd=5.0,
                preferred_provider=self.test_provider,
            )

            self.fabric.global_planner.register_universe(
                tenant_id=universe.tenant_id,
                universe_id=universe.universe_id,
                universe_name=universe.universe_name,
                priority=universe.priority,
                estimated_jobs=universe.estimated_jobs,
                estimated_runtime_seconds=universe.estimated_runtime_seconds,
                estimated_cost_usd=universe.estimated_cost_usd,
                preferred_provider=universe.preferred_provider,
            )

            worker_report = self.fabric.worker_capacity_model.analyze_from_runtime(
                workers=[
                    {
                        "worker_id": "planner_worker_1",
                        "state": "ONLINE",
                        "capacity": 500,
                        "active_jobs": 50,
                        "jobs_completed": 1000,
                        "jobs_failed": 5,
                        "avg_runtime_seconds": 3.0,
                    }
                ],
                queue_metrics={"queue_depth": 50, "active_leases": 5},
                tenant_id=self.test_tenant_id,
            )

            provider_profiles = list(
                getattr(self.fabric.provider_cost_intelligence, "provider_profiles", {}).values()
            )

            plan = self.fabric.global_planner.build_execution_plan(
                universes=[universe],
                queue_metrics={"queue_depth": 50, "active_leases": 5},
                worker_report=worker_report,
                provider_profiles=provider_profiles,
                tenant_metrics={"pressure": 0.1},
                universe_metrics={},
            )

            if not plan.universe_plans:
                return self._fail(
                    "Global Planner",
                    "Global planner generated no universe plans.",
                    plan.as_dict(),
                )

            return self._pass(
                "Global Planner",
                "Global analytics planner verified.",
                plan.as_dict(),
            )

        except Exception as exc:
            return self._exception("Global Planner", exc)

    def validate_tenant_intelligence(self) -> ValidationCheck:
        try:
            from modules.analytics.tenant_universe_intelligence_engine import (
                TenantTelemetrySample,
                UniverseTelemetrySample,
            )

            report = self.fabric.tenant_universe_intelligence.analyze(
                tenant_samples=[
                    TenantTelemetrySample(
                        tenant_id=self.test_tenant_id,
                        jobs_submitted=1000,
                        jobs_completed=950,
                        jobs_failed=25,
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
                        tenant_id=self.test_tenant_id,
                        universe_id=self.test_universe_id,
                        universe_name="Validation Universe",
                        jobs_submitted=1000,
                        jobs_completed=950,
                        jobs_failed=25,
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

            if not report.tenant_profiles or not report.universe_profiles:
                return self._fail(
                    "Tenant Intelligence",
                    "Tenant/universe intelligence generated incomplete profiles.",
                    report.as_dict(),
                )

            return self._pass(
                "Tenant Intelligence",
                "Tenant and universe intelligence verified.",
                report.as_dict(),
            )

        except Exception as exc:
            return self._exception("Tenant Intelligence", exc)

    def validate_fabric_summary(self) -> ValidationCheck:
        try:
            summary = self.fabric.summary()

            if not isinstance(summary, dict):
                return self._fail(
                    "Fabric Summary",
                    "Fabric summary did not return a dictionary.",
                )

            return self._pass(
                "Fabric Summary",
                "Fabric summary verified.",
                summary,
            )

        except Exception as exc:
            return self._exception("Fabric Summary", exc)

    def _pass(
        self,
        name: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationCheck:
        return ValidationCheck(
            name=name,
            status="PASS",
            message=message,
            metadata=metadata or {},
        )

    def _warn(
        self,
        name: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationCheck:
        return ValidationCheck(
            name=name,
            status="WARN",
            message=message,
            metadata=metadata or {},
        )

    def _fail(
        self,
        name: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationCheck:
        return ValidationCheck(
            name=name,
            status="FAIL",
            message=message,
            metadata=metadata or {},
        )

    def _exception(
        self,
        name: str,
        exc: Exception,
    ) -> ValidationCheck:
        return ValidationCheck(
            name=name,
            status="FAIL",
            message=str(exc),
            error=repr(exc),
            traceback_text=traceback.format_exc(),
        )


def run_analytics_fabric_validation(
    *,
    fabric: Optional[Any] = None,
    config: Optional[Any] = None,
) -> AnalyticsFabricValidationResult:
    suite = AnalyticsFabricValidationSuite(
        fabric=fabric,
        config=config,
    )

    return suite.run_all()


def print_validation_result(
    result: AnalyticsFabricValidationResult,
) -> None:
    print()
    print("=== ANALYTICS FABRIC INTEGRATION VALIDATION ===")
    print()

    for check in result.checks:
        print(f"{check.status:5} | {check.name:28} | {check.message}")

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
    validation = run_analytics_fabric_validation()
    print_validation_result(validation)