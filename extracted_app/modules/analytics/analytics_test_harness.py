"""
modules/analytics/analytics_test_harness.py

Phase 1 Analytics Fabric Validation Harness

Purpose
-------
Provides end-to-end validation of the Analytics Fabric:

    UniverseJobRegistry
    UniverseExecutionQueue
    IntelligentAnalyticsScheduler
    UniverseWorkloadBalancer
    UniverseRuntimeController
    UniverseAnalyticsOrchestrator
    AnalyticsResourceGovernor
    AutonomousAnalyticsOptimizer

This harness is intentionally independent from UI code and can be
executed from:

    pytest
    CLI
    admin tools
    startup validation
    CI/CD validation

Outputs:

    PASS
    FAIL
    WARN

for each subsystem.
"""

from __future__ import annotations

import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Results
# =============================================================================

@dataclass
class ValidationResult:
    test_name: str
    status: str
    message: str
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationSuite:
    suite_name: str
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return len(
            [
                r
                for r in self.results
                if r.status == "PASS"
            ]
        )

    @property
    def failed(self) -> int:
        return len(
            [
                r
                for r in self.results
                if r.status == "FAIL"
            ]
        )

    @property
    def warnings(self) -> int:
        return len(
            [
                r
                for r in self.results
                if r.status == "WARN"
            ]
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "suite": self.suite_name,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "total": len(self.results),
        }


# =============================================================================
# Harness
# =============================================================================

class AnalyticsTestHarness:

    def __init__(
        self,
        *,
        registry=None,
        queue=None,
        scheduler=None,
        balancer=None,
        runtime_controller=None,
        orchestrator=None,
        governor=None,
        optimizer=None,
    ):
        self.registry = registry
        self.queue = queue
        self.scheduler = scheduler
        self.balancer = balancer
        self.runtime_controller = runtime_controller
        self.orchestrator = orchestrator
        self.governor = governor
        self.optimizer = optimizer

    # =========================================================================
    # Public
    # =========================================================================

    def run_all(self) -> ValidationSuite:

        suite = ValidationSuite(
            suite_name="Analytics Fabric Validation"
        )

        suite.results.append(
            self.validate_registry()
        )

        suite.results.append(
            self.validate_queue()
        )

        suite.results.append(
            self.validate_scheduler()
        )

        suite.results.append(
            self.validate_balancer()
        )

        suite.results.append(
            self.validate_runtime_controller()
        )

        suite.results.append(
            self.validate_orchestrator()
        )

        suite.results.append(
            self.validate_governor()
        )

        suite.results.append(
            self.validate_optimizer()
        )

        return suite

    # =========================================================================
    # Registry
    # =========================================================================

    def validate_registry(
        self,
    ) -> ValidationResult:

        if self.registry is None:
            return self._warn(
                "Registry",
                "Registry not configured."
            )

        try:

            tenant_id = "TEST"
            universe_id = "TEST_UNIVERSE"

            job = self.registry.register_job(
                tenant_id=tenant_id,
                universe_id=universe_id,
                job_type="TEST_JOB",
                priority="NORMAL",
                payload={"test": True},
            )

            retrieved = self.registry.get_job(
                tenant_id=tenant_id,
                job_id=job.job_id,
            )

            if not retrieved:
                return self._fail(
                    "Registry",
                    "Registered job not found."
                )

            return self._pass(
                "Registry",
                "Job registration verified.",
                {
                    "job_id":
                        job.job_id
                },
            )

        except Exception as exc:

            return self._exception(
                "Registry",
                exc
            )

    # =========================================================================
    # Queue
    # =========================================================================

    def validate_queue(
        self,
    ) -> ValidationResult:

        if self.queue is None:
            return self._warn(
                "Queue",
                "Queue not configured."
            )

        try:

            job_id = (
                f"job_{uuid.uuid4().hex}"
            )

            self.queue.enqueue_job(
                tenant_id="TEST",
                job_id=job_id,
                priority="NORMAL",
            )

            metrics = (
                self.queue.queue_metrics()
            )

            return self._pass(
                "Queue",
                "Queue enqueue verified.",
                metrics,
            )

        except Exception as exc:

            return self._exception(
                "Queue",
                exc
            )

    # =========================================================================
    # Scheduler
    # =========================================================================

    def validate_scheduler(
        self,
    ) -> ValidationResult:

        if self.scheduler is None:
            return self._warn(
                "Scheduler",
                "Scheduler not configured."
            )

        try:

            schedule = (
                self.scheduler
                .register_schedule(
                    tenant_id="TEST",
                    universe_id="TEST_UNIVERSE",
                    schedule_name="Harness Test",
                    job_type="TEST_JOB",
                )
            )

            result = (
                self.scheduler
                .run_scheduler_cycle()
            )

            return self._pass(
                "Scheduler",
                "Scheduler cycle executed.",
                {
                    "schedule_id":
                        schedule.schedule_id,
                    "jobs_created":
                        result.get(
                            "jobs_created",
                            0,
                        ),
                },
            )

        except Exception as exc:

            return self._exception(
                "Scheduler",
                exc
            )

    # =========================================================================
    # Balancer
    # =========================================================================

    def validate_balancer(
        self,
    ) -> ValidationResult:

        if self.balancer is None:
            return self._warn(
                "Balancer",
                "Balancer not configured."
            )

        try:

            from modules.analytics.universe_workload_balancer import (
                AnalyticsWorker,
                AnalyticsWorkItem,
            )

            workers = []

            for i in range(3):

                workers.append(
                    AnalyticsWorker(
                        worker_id=f"W{i}",
                        capacity=10,
                        active_jobs=0,
                    )
                )

            jobs = []

            for i in range(100):

                jobs.append(
                    AnalyticsWorkItem(
                        job_id=f"J{i}",
                        tenant_id="TEST",
                        universe_id="TEST",
                        job_type="TEST",
                    )
                )

            plan = (
                self.balancer
                .build_plan(
                    workers=workers,
                    queued_jobs=jobs,
                )
            )

            return self._pass(
                "Balancer",
                "Balancer plan generated.",
                {
                    "assignments":
                        len(plan.assignments),
                    "held_jobs":
                        len(plan.held_jobs),
                },
            )

        except Exception as exc:

            return self._exception(
                "Balancer",
                exc
            )

    # =========================================================================
    # Runtime
    # =========================================================================

    def validate_runtime_controller(
        self,
    ) -> ValidationResult:

        if self.runtime_controller is None:
            return self._warn(
                "Runtime",
                "Runtime controller not configured."
            )

        try:

            metrics = (
                self.runtime_controller
                .runtime_metrics()
            )

            return self._pass(
                "Runtime",
                "Runtime metrics available.",
                metrics,
            )

        except Exception as exc:

            return self._exception(
                "Runtime",
                exc
            )

    # =========================================================================
    # Orchestrator
    # =========================================================================

    def validate_orchestrator(
        self,
    ) -> ValidationResult:

        if self.orchestrator is None:
            return self._warn(
                "Orchestrator",
                "Orchestrator not configured."
            )

        try:

            metrics = (
                self.orchestrator
                .analytics_metrics()
            )

            return self._pass(
                "Orchestrator",
                "Analytics metrics available.",
                metrics,
            )

        except Exception as exc:

            return self._exception(
                "Orchestrator",
                exc
            )

    # =========================================================================
    # Governor
    # =========================================================================

    def validate_governor(
        self,
    ) -> ValidationResult:

        if self.governor is None:
            return self._warn(
                "Governor",
                "Governor not configured."
            )

        try:

            from modules.analytics.analytics_resource_governor import (
                RuntimeCapacity,
            )

            decision = (
                self.governor
                .evaluate_runtime_dispatch(
                    RuntimeCapacity(
                        workers_online=5,
                        workers_total=5,
                        queue_depth=10,
                        active_jobs=5,
                        available_capacity=20,
                        worker_utilization=0.25,
                    )
                )
            )

            return self._pass(
                "Governor",
                "Governance decision generated.",
                {
                    "decision":
                        decision.decision
                },
            )

        except Exception as exc:

            return self._exception(
                "Governor",
                exc
            )

    # =========================================================================
    # Optimizer
    # =========================================================================

    def validate_optimizer(
        self,
    ) -> ValidationResult:

        if self.optimizer is None:
            return self._warn(
                "Optimizer",
                "Optimizer not configured."
            )

        try:

            from modules.analytics.autonomous_analytics_optimizer import (
                OptimizationTelemetry,
            )

            self.optimizer.collect_telemetry(
                OptimizationTelemetry(
                    queue_depth=100,
                    workers_online=5,
                    worker_utilization=0.40,
                    completed_jobs=100,
                    failed_jobs=1,
                )
            )

            plan = (
                self.optimizer
                .generate_optimization_plan()
            )

            return self._pass(
                "Optimizer",
                "Optimization plan generated.",
                {
                    "recommendations":
                        len(
                            plan.recommendations
                        )
                },
            )

        except Exception as exc:

            return self._exception(
                "Optimizer",
                exc
            )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _pass(
        self,
        name,
        message,
        metadata=None,
    ):

        return ValidationResult(
            test_name=name,
            status="PASS",
            message=message,
            metadata=metadata or {},
        )

    def _warn(
        self,
        name,
        message,
    ):

        return ValidationResult(
            test_name=name,
            status="WARN",
            message=message,
        )

    def _fail(
        self,
        name,
        message,
    ):

        return ValidationResult(
            test_name=name,
            status="FAIL",
            message=message,
        )

    def _exception(
        self,
        name,
        exc,
    ):

        return ValidationResult(
            test_name=name,
            status="FAIL",
            message=str(exc),
            metadata={
                "traceback":
                    traceback.format_exc()
            },
        )


# =============================================================================
# Convenience
# =============================================================================

def run_analytics_validation(
    *,
    registry=None,
    queue=None,
    scheduler=None,
    balancer=None,
    runtime_controller=None,
    orchestrator=None,
    governor=None,
    optimizer=None,
):

    harness = AnalyticsTestHarness(
        registry=registry,
        queue=queue,
        scheduler=scheduler,
        balancer=balancer,
        runtime_controller=runtime_controller,
        orchestrator=orchestrator,
        governor=governor,
        optimizer=optimizer,
    )

    return harness.run_all()