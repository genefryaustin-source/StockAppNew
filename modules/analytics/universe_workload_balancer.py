"""
modules/analytics/universe_workload_balancer.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Enums
# =============================================================================

class WorkerState(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DRAINING = "DRAINING"


class WorkloadDecision(str, Enum):
    ASSIGN = "ASSIGN"
    HOLD = "HOLD"
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    REBALANCE = "REBALANCE"
    NO_CAPACITY = "NO_CAPACITY"


# =============================================================================
# Data Models
# =============================================================================

@dataclass(frozen=True)
class AnalyticsWorker:
    worker_id: str
    tenant_id: Optional[str] = None
    state: str = WorkerState.ONLINE.value
    capacity: int = 5
    active_jobs: int = 0
    provider_affinity: List[str] = field(default_factory=list)
    universe_affinity: List[str] = field(default_factory=list)
    supported_job_types: List[str] = field(default_factory=list)
    error_rate: float = 0.0
    avg_runtime_seconds: float = 0.0
    last_heartbeat_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def available_capacity(self) -> int:
        return max(0, int(self.capacity) - int(self.active_jobs))

    @property
    def is_available(self) -> bool:
        return (
            self.state == WorkerState.ONLINE.value
            and self.available_capacity > 0
        )


@dataclass(frozen=True)
class AnalyticsWorkItem:
    job_id: str
    tenant_id: str
    universe_id: str
    job_type: str
    priority: str = "NORMAL"
    provider: Optional[str] = None
    symbol: Optional[str] = None
    estimated_runtime_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkloadAssignment:
    decision: str
    job_id: Optional[str] = None
    worker_id: Optional[str] = None
    score: float = 0.0
    reason: str = ""
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkloadPlan:
    decision: str
    assignments: List[WorkloadAssignment] = field(default_factory=list)
    held_jobs: List[str] = field(default_factory=list)
    scale_recommendation: Optional[Dict[str, Any]] = None
    generated_at: str = field(default_factory=utc_now_iso)
    metrics: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Balancer
# =============================================================================

class UniverseWorkloadBalancer:
    """
    Stateless analytics workload balancer.

    Responsibilities:
        - Score workers for queued analytics jobs.
        - Produce deterministic assignment plans.
        - Recommend scale up / scale down actions.
        - Respect tenant, provider, universe, and job-type affinity.

    This module does not mutate queues or workers directly.
    universe_runtime_controller.py should apply the returned plan.
    """

    PRIORITY_WEIGHT = {
        "CRITICAL": 100,
        "HIGH": 75,
        "NORMAL": 50,
        "LOW": 25,
    }

    def __init__(
        self,
        *,
        target_queue_per_worker: int = 10,
        scale_up_queue_threshold: int = 25,
        scale_down_idle_threshold: int = 2,
        max_error_rate: float = 0.35,
    ) -> None:
        self.target_queue_per_worker = max(1, int(target_queue_per_worker))
        self.scale_up_queue_threshold = max(1, int(scale_up_queue_threshold))
        self.scale_down_idle_threshold = max(0, int(scale_down_idle_threshold))
        self.max_error_rate = max(0.0, min(1.0, float(max_error_rate)))

    # =========================================================================
    # Public Planning API
    # =========================================================================

    def build_plan(
        self,
        *,
        workers: Iterable[AnalyticsWorker],
        queued_jobs: Iterable[AnalyticsWorkItem],
    ) -> WorkloadPlan:
        workers_list = list(workers)
        jobs_list = self._sort_jobs(list(queued_jobs))

        available_workers = [
            worker for worker in workers_list
            if self._worker_eligible_base(worker)
        ]

        assignments: List[WorkloadAssignment] = []
        held_jobs: List[str] = []

        remaining_capacity: Dict[str, int] = {
            worker.worker_id: worker.available_capacity
            for worker in available_workers
        }

        for job in jobs_list:
            assignment = self.assign_job(
                job=job,
                workers=available_workers,
                remaining_capacity=remaining_capacity,
            )

            if assignment.decision == WorkloadDecision.ASSIGN.value:
                assignments.append(assignment)
                if assignment.worker_id:
                    remaining_capacity[assignment.worker_id] = max(
                        0,
                        remaining_capacity.get(assignment.worker_id, 0) - 1,
                    )
            else:
                held_jobs.append(job.job_id)

        metrics = self.compute_metrics(
            workers=workers_list,
            queued_jobs=jobs_list,
            assignments=assignments,
            held_jobs=held_jobs,
        )

        scale_recommendation = self.recommend_scaling(
            workers=workers_list,
            queued_jobs=jobs_list,
            assignments=assignments,
            held_jobs=held_jobs,
        )

        if assignments and held_jobs:
            decision = WorkloadDecision.REBALANCE.value
        elif assignments:
            decision = WorkloadDecision.ASSIGN.value
        elif scale_recommendation and scale_recommendation.get("action") == "SCALE_UP":
            decision = WorkloadDecision.SCALE_UP.value
        elif held_jobs:
            decision = WorkloadDecision.NO_CAPACITY.value
        else:
            decision = WorkloadDecision.HOLD.value

        return WorkloadPlan(
            decision=decision,
            assignments=assignments,
            held_jobs=held_jobs,
            scale_recommendation=scale_recommendation,
            metrics=metrics,
        )

    def assign_job(
        self,
        *,
        job: AnalyticsWorkItem,
        workers: Iterable[AnalyticsWorker],
        remaining_capacity: Optional[Dict[str, int]] = None,
    ) -> WorkloadAssignment:
        candidates: List[tuple[float, AnalyticsWorker, str]] = []

        for worker in workers:
            capacity = (
                remaining_capacity.get(worker.worker_id, worker.available_capacity)
                if remaining_capacity is not None
                else worker.available_capacity
            )

            score, reason = self.score_worker_for_job(
                worker=worker,
                job=job,
                remaining_capacity=capacity,
            )

            if score > 0:
                candidates.append((score, worker, reason))

        if not candidates:
            return WorkloadAssignment(
                decision=WorkloadDecision.NO_CAPACITY.value,
                job_id=job.job_id,
                reason="No eligible worker capacity available.",
                metadata={
                    "tenant_id": job.tenant_id,
                    "universe_id": job.universe_id,
                    "job_type": job.job_type,
                    "provider": job.provider,
                },
            )

        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1].active_jobs,
                item[1].worker_id,
            )
        )

        best_score, best_worker, reason = candidates[0]

        return WorkloadAssignment(
            decision=WorkloadDecision.ASSIGN.value,
            job_id=job.job_id,
            worker_id=best_worker.worker_id,
            score=round(best_score, 4),
            reason=reason,
            metadata={
                "tenant_id": job.tenant_id,
                "universe_id": job.universe_id,
                "job_type": job.job_type,
                "provider": job.provider,
                "worker_available_capacity": best_worker.available_capacity,
            },
        )

    # =========================================================================
    # Scoring
    # =========================================================================

    def score_worker_for_job(
        self,
        *,
        worker: AnalyticsWorker,
        job: AnalyticsWorkItem,
        remaining_capacity: Optional[int] = None,
    ) -> tuple[float, str]:
        capacity = (
            worker.available_capacity
            if remaining_capacity is None
            else max(0, int(remaining_capacity))
        )

        if worker.state != WorkerState.ONLINE.value:
            return 0.0, "Worker is not online."

        if capacity <= 0:
            return 0.0, "Worker has no remaining capacity."

        if worker.error_rate > self.max_error_rate:
            return 0.0, "Worker error rate exceeds threshold."

        if worker.tenant_id and worker.tenant_id != job.tenant_id:
            return 0.0, "Worker tenant affinity does not match job tenant."

        if worker.supported_job_types and job.job_type not in worker.supported_job_types:
            return 0.0, "Worker does not support this analytics job type."

        score = 100.0

        priority_score = self.PRIORITY_WEIGHT.get(job.priority.upper(), 50)
        score += priority_score * 0.20

        utilization = (
            float(worker.active_jobs) / float(worker.capacity)
            if worker.capacity > 0
            else 1.0
        )
        score += max(0.0, 1.0 - utilization) * 35.0

        score += min(capacity, 10) * 4.0

        if job.provider and worker.provider_affinity:
            if job.provider in worker.provider_affinity:
                score += 25.0
            else:
                score -= 20.0

        if worker.universe_affinity:
            if job.universe_id in worker.universe_affinity:
                score += 20.0
            else:
                score -= 10.0

        if worker.avg_runtime_seconds > 0 and job.estimated_runtime_seconds:
            runtime_ratio = job.estimated_runtime_seconds / worker.avg_runtime_seconds
            if runtime_ratio <= 1.0:
                score += 10.0
            elif runtime_ratio <= 2.0:
                score += 2.5
            else:
                score -= 8.0

        score -= worker.error_rate * 50.0

        score = max(0.0, score)

        return score, "Worker selected by deterministic weighted score."

    # =========================================================================
    # Scaling Recommendations
    # =========================================================================

    def recommend_scaling(
        self,
        *,
        workers: Iterable[AnalyticsWorker],
        queued_jobs: Iterable[AnalyticsWorkItem],
        assignments: Optional[Iterable[WorkloadAssignment]] = None,
        held_jobs: Optional[Iterable[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        workers_list = list(workers)
        jobs_list = list(queued_jobs)
        assignments_list = list(assignments or [])
        held_job_ids = list(held_jobs or [])

        online_workers = [
            worker for worker in workers_list
            if worker.state == WorkerState.ONLINE.value
        ]

        total_capacity = sum(worker.capacity for worker in online_workers)
        active_jobs = sum(worker.active_jobs for worker in online_workers)
        available_capacity = sum(worker.available_capacity for worker in online_workers)

        pending_after_plan = max(
            0,
            len(jobs_list) - len(assignments_list),
        )

        if held_job_ids or pending_after_plan >= self.scale_up_queue_threshold:
            desired_workers = max(
                1,
                (pending_after_plan // self.target_queue_per_worker) + 1,
            )

            return {
                "action": "SCALE_UP",
                "desired_additional_workers": desired_workers,
                "reason": "Queued analytics workload exceeds available worker capacity.",
                "pending_after_plan": pending_after_plan,
                "held_jobs": held_job_ids,
                "online_workers": len(online_workers),
                "available_capacity": available_capacity,
                "generated_at": utc_now_iso(),
            }

        idle_workers = [
            worker for worker in online_workers
            if worker.active_jobs == 0
        ]

        if (
            len(idle_workers) > self.scale_down_idle_threshold
            and len(jobs_list) == 0
            and active_jobs == 0
        ):
            removable = max(
                0,
                len(idle_workers) - self.scale_down_idle_threshold,
            )

            if removable > 0:
                return {
                    "action": "SCALE_DOWN",
                    "recommended_workers_to_drain": removable,
                    "candidate_worker_ids": [
                        worker.worker_id for worker in idle_workers[:removable]
                    ],
                    "reason": "Worker pool is idle beyond configured threshold.",
                    "online_workers": len(online_workers),
                    "total_capacity": total_capacity,
                    "generated_at": utc_now_iso(),
                }

        return {
            "action": "HOLD",
            "reason": "Worker capacity is within operating range.",
            "online_workers": len(online_workers),
            "available_capacity": available_capacity,
            "pending_after_plan": pending_after_plan,
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Metrics
    # =========================================================================

    def compute_metrics(
        self,
        *,
        workers: Iterable[AnalyticsWorker],
        queued_jobs: Iterable[AnalyticsWorkItem],
        assignments: Iterable[WorkloadAssignment],
        held_jobs: Iterable[str],
    ) -> Dict[str, Any]:
        workers_list = list(workers)
        jobs_list = list(queued_jobs)
        assignment_list = list(assignments)
        held_job_ids = list(held_jobs)

        online_workers = [
            worker for worker in workers_list
            if worker.state == WorkerState.ONLINE.value
        ]

        degraded_workers = [
            worker for worker in workers_list
            if worker.state == WorkerState.DEGRADED.value
        ]

        offline_workers = [
            worker for worker in workers_list
            if worker.state == WorkerState.OFFLINE.value
        ]

        total_capacity = sum(worker.capacity for worker in online_workers)
        active_jobs = sum(worker.active_jobs for worker in online_workers)
        available_capacity = sum(worker.available_capacity for worker in online_workers)

        return {
            "workers_total": len(workers_list),
            "workers_online": len(online_workers),
            "workers_degraded": len(degraded_workers),
            "workers_offline": len(offline_workers),
            "total_capacity": total_capacity,
            "active_jobs": active_jobs,
            "available_capacity": available_capacity,
            "queued_jobs": len(jobs_list),
            "planned_assignments": len(assignment_list),
            "held_jobs": len(held_job_ids),
            "utilization": (
                round(active_jobs / total_capacity, 4)
                if total_capacity > 0
                else 0.0
            ),
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Internal Sorting / Eligibility
    # =========================================================================

    def _sort_jobs(
        self,
        jobs: List[AnalyticsWorkItem],
    ) -> List[AnalyticsWorkItem]:
        return sorted(
            jobs,
            key=lambda job: (
                -self.PRIORITY_WEIGHT.get(job.priority.upper(), 50),
                job.tenant_id,
                job.universe_id,
                job.job_id,
            ),
        )

    def _worker_eligible_base(
        self,
        worker: AnalyticsWorker,
    ) -> bool:
        return (
            worker.state == WorkerState.ONLINE.value
            and worker.available_capacity > 0
            and worker.error_rate <= self.max_error_rate
        )


# =============================================================================
# Convenience Factory
# =============================================================================

def create_universe_workload_balancer(
    *,
    target_queue_per_worker: int = 10,
    scale_up_queue_threshold: int = 25,
    scale_down_idle_threshold: int = 2,
    max_error_rate: float = 0.35,
) -> UniverseWorkloadBalancer:
    return UniverseWorkloadBalancer(
        target_queue_per_worker=target_queue_per_worker,
        scale_up_queue_threshold=scale_up_queue_threshold,
        scale_down_idle_threshold=scale_down_idle_threshold,
        max_error_rate=max_error_rate,
    )