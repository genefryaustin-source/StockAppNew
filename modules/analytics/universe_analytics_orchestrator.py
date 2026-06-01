"""
modules/analytics/universe_analytics_orchestrator.py
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from modules.analytics.intelligent_analytics_scheduler import (
    IntelligentAnalyticsScheduler,
)
from modules.analytics.universe_execution_queue import (
    UniverseExecutionQueue,
)
from modules.analytics.universe_job_registry import (
    UniverseJobRegistry,
    UniverseJobStatus,
)
from modules.analytics.universe_runtime_controller import (
    UniverseRuntimeController,
)
from modules.analytics.universe_workload_balancer import (
    UniverseWorkloadBalancer,
)


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class AnalyticsUniverse:
    universe_id: str
    tenant_id: str
    universe_name: str
    active: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class AnalyticsTenant:
    tenant_id: str
    tenant_name: str
    active: bool = True
    max_jobs: int = 5000
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class OrchestratorCycleResult:
    cycle_id: str
    scheduler_jobs_created: int = 0
    retry_jobs_promoted: int = 0
    queued_jobs_created: int = 0
    runtime_assignments: int = 0
    runtime_completed: int = 0
    runtime_failed: int = 0
    recovered_leases: int = 0
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Orchestrator
# =============================================================================

class UniverseAnalyticsOrchestrator:
    """
    Master coordinator for analytics execution.

    Coordinates:

        Scheduler
            ↓
        Registry
            ↓
        Queue
            ↓
        Balancer
            ↓
        Runtime Controller

    Provides a single orchestration surface for:

        analytics operations center
        scheduler dashboard
        optimizer
        governor
        admin controls
    """

    def __init__(
        self,
        registry: UniverseJobRegistry,
        scheduler: IntelligentAnalyticsScheduler,
        execution_queue: UniverseExecutionQueue,
        workload_balancer: UniverseWorkloadBalancer,
        runtime_controller: UniverseRuntimeController,
    ):
        self.registry = registry
        self.scheduler = scheduler
        self.execution_queue = execution_queue
        self.workload_balancer = workload_balancer
        self.runtime_controller = runtime_controller

        self._universes: Dict[str, AnalyticsUniverse] = {}
        self._tenants: Dict[str, AnalyticsTenant] = {}

    # =========================================================================
    # Tenant Management
    # =========================================================================

    def register_tenant(
        self,
        tenant_id: str,
        tenant_name: str,
        max_jobs: int = 5000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsTenant:

        tenant = AnalyticsTenant(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            max_jobs=max_jobs,
            metadata=metadata or {},
        )

        self._tenants[tenant_id] = tenant

        return tenant

    def get_tenant(
        self,
        tenant_id: str,
    ) -> Optional[AnalyticsTenant]:
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> List[AnalyticsTenant]:
        return list(self._tenants.values())

    # =========================================================================
    # Universe Management
    # =========================================================================

    def register_universe(
        self,
        tenant_id: str,
        universe_name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        universe_id: Optional[str] = None,
    ) -> AnalyticsUniverse:

        universe = AnalyticsUniverse(
            universe_id=(
                universe_id
                or f"universe_{uuid.uuid4().hex}"
            ),
            tenant_id=tenant_id,
            universe_name=universe_name,
            description=description,
            metadata=metadata or {},
        )

        self._universes[universe.universe_id] = universe

        return universe

    def get_universe(
        self,
        universe_id: str,
    ) -> Optional[AnalyticsUniverse]:
        return self._universes.get(universe_id)

    def list_universes(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[AnalyticsUniverse]:

        universes = list(self._universes.values())

        if tenant_id:
            universes = [
                u for u in universes
                if u.tenant_id == tenant_id
            ]

        return universes

    def activate_universe(
        self,
        universe_id: str,
    ) -> bool:

        universe = self._universes.get(universe_id)

        if not universe:
            return False

        universe.active = True
        universe.updated_at = utc_now_iso()

        return True

    def suspend_universe(
        self,
        universe_id: str,
    ) -> bool:

        universe = self._universes.get(universe_id)

        if not universe:
            return False

        universe.active = False
        universe.updated_at = utc_now_iso()

        return True

    # =========================================================================
    # Scheduler Coordination
    # =========================================================================

    def run_scheduler_cycle(
        self,
    ) -> Dict[str, Any]:

        return self.scheduler.run_scheduler_cycle()

    # =========================================================================
    # Queue Coordination
    # =========================================================================

    def enqueue_registered_jobs(
        self,
        tenant_id: str,
        universe_id: Optional[str] = None,
        limit: int = 1000,
    ) -> int:

        return self.runtime_controller.enqueue_registered_jobs(
            tenant_id=tenant_id,
            universe_id=universe_id,
            limit=limit,
        )

    def promote_retry_jobs(
        self,
        tenant_id: str,
        universe_id: Optional[str] = None,
        limit: int = 1000,
    ) -> int:

        return self.runtime_controller.promote_retry_jobs(
            tenant_id=tenant_id,
            universe_id=universe_id,
            limit=limit,
        )

    # =========================================================================
    # Runtime Coordination
    # =========================================================================

    def run_runtime_cycle(
        self,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        execute_callback: Optional[
            Callable
        ] = None,
    ):

        return self.runtime_controller.tick(
            tenant_id=tenant_id,
            universe_id=universe_id,
            execute_callback=execute_callback,
        )

    # =========================================================================
    # Full Analytics Cycle
    # =========================================================================

    def run_full_cycle(
        self,
        execute_callback: Optional[
            Callable
        ] = None,
    ) -> OrchestratorCycleResult:

        cycle_id = f"cycle_{uuid.uuid4().hex}"

        scheduler_result = (
            self.scheduler.run_scheduler_cycle()
        )

        queued_jobs = 0
        retry_jobs = 0

        for tenant in self.list_tenants():

            queued_jobs += (
                self.runtime_controller
                .enqueue_registered_jobs(
                    tenant_id=tenant.tenant_id
                )
            )

            retry_jobs += (
                self.runtime_controller
                .promote_retry_jobs(
                    tenant_id=tenant.tenant_id
                )
            )

        runtime_result = (
            self.runtime_controller.tick(
                execute_callback=execute_callback
            )
        )

        return OrchestratorCycleResult(
            cycle_id=cycle_id,
            scheduler_jobs_created=
                scheduler_result.get(
                    "jobs_created",
                    0,
                ),
            retry_jobs_promoted=retry_jobs,
            queued_jobs_created=queued_jobs,
            runtime_assignments=
                runtime_result.assignments_created,
            runtime_completed=
                runtime_result.completed_jobs,
            runtime_failed=
                runtime_result.failed_jobs,
            recovered_leases=
                runtime_result.recovered_leases,
            metadata={
                "scheduler": scheduler_result,
                "runtime":
                    asdict(runtime_result),
            },
        )

    # =========================================================================
    # Analytics Metrics
    # =========================================================================

    def analytics_metrics(
        self,
    ) -> Dict[str, Any]:

        runtime_metrics = (
            self.runtime_controller
            .runtime_metrics()
        )

        scheduler_metrics = (
            self.scheduler
            .scheduler_metrics()
        )

        return {
            "tenants":
                len(self._tenants),

            "universes":
                len(self._universes),

            "runtime":
                runtime_metrics,

            "scheduler":
                asdict(
                    scheduler_metrics
                ),

            "generated_at":
                utc_now_iso(),
        }

    # =========================================================================
    # Tenant Analytics Metrics
    # =========================================================================

    def tenant_metrics(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:

        universes = self.list_universes(
            tenant_id=tenant_id
        )

        jobs = self.registry.list_jobs(
            tenant_id=tenant_id,
            limit=100000,
        )

        status_counts: Dict[str, int] = {}

        for job in jobs:
            status_counts[job.status] = (
                status_counts.get(
                    job.status,
                    0,
                )
                + 1
            )

        return {
            "tenant_id": tenant_id,
            "universes": len(universes),
            "jobs_total": len(jobs),
            "job_status": status_counts,
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Universe Analytics Metrics
    # =========================================================================

    def universe_metrics(
        self,
        tenant_id: str,
        universe_id: str,
    ) -> Dict[str, Any]:

        jobs = self.registry.list_jobs(
            tenant_id=tenant_id,
            universe_id=universe_id,
            limit=100000,
        )

        status_counts: Dict[str, int] = {}

        for job in jobs:
            status_counts[job.status] = (
                status_counts.get(
                    job.status,
                    0,
                )
                + 1
            )

        return {
            "tenant_id": tenant_id,
            "universe_id": universe_id,
            "jobs_total": len(jobs),
            "job_status": status_counts,
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Analytics Health
    # =========================================================================

    def health_status(
        self,
    ) -> Dict[str, Any]:

        runtime_metrics = (
            self.runtime_controller
            .runtime_metrics()
        )

        queue_metrics = (
            self.execution_queue
            .queue_metrics()
        )

        return {
            "controller_state":
                runtime_metrics.get(
                    "state"
                ),

            "workers_online":
                runtime_metrics.get(
                    "workers_online"
                ),

            "queue_depth":
                queue_metrics.get(
                    "queue_depth"
                ),

            "active_leases":
                queue_metrics.get(
                    "active_leases"
                ),

            "healthy":
                runtime_metrics.get(
                    "workers_online",
                    0,
                ) > 0,

            "generated_at":
                utc_now_iso(),
        }

    # =========================================================================
    # Recovery
    # =========================================================================

    def recover_runtime(
        self,
    ) -> Dict[str, Any]:

        recovered = (
            self.execution_queue
            .recover_expired_leases()
        )

        return {
            "recovered_leases":
                recovered,
            "generated_at":
                utc_now_iso(),
        }

    # =========================================================================
    # Job Summaries
    # =========================================================================

    def summarize_jobs(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:

        return self.registry.summarize_jobs(
            tenant_id=tenant_id
        )

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def diagnostics(
        self,
    ) -> Dict[str, Any]:

        return {
            "orchestrator":
                "online",

            "scheduler":
                self.scheduler
                .scheduler_metrics(),

            "runtime":
                self.runtime_controller
                .runtime_metrics(),

            "queue":
                self.execution_queue
                .queue_metrics(),

            "generated_at":
                utc_now_iso(),
        }