"""
modules/analytics/global_analytics_planner.py

Global Analytics Planner

Purpose
-------
Master planning layer for the Analytics Fabric.

This module coordinates:

    Universe prioritization
    Cross-tenant scheduling
    Provider assignment
    Worker assignment
    Capacity reservation
    Quota protection
    SLA protection
    Deferred workload management
    Cost-aware execution planning
    Governance-aware execution decisions

Consumes:

    WorkerCapacityModel
    ProviderCostIntelligence
    AutonomousExecutionGovernor
    AnalyticsResourceGovernor
    AutonomousAnalyticsOptimizer
    UniverseRuntimeController
    UniverseAnalyticsOrchestrator

Produces:

    GlobalExecutionPlan
    UniverseExecutionPlan
    ProviderAssignment
    WorkerAssignment
    CapacityReservation
    AnalyticsExecutionForecast
    PlanningDecision
    PlanningRecommendation
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    try:
        if denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except Exception:
        return default


def normalize_priority(priority: str) -> str:
    return str(priority or "NORMAL").upper()


def priority_rank(priority: str) -> int:
    mapping = {
        "CRITICAL": 100,
        "HIGH": 75,
        "NORMAL": 50,
        "LOW": 25,
        "DEFERRED": 10,
    }
    return mapping.get(normalize_priority(priority), 50)


# =============================================================================
# Enums
# =============================================================================

class PlannerDecisionType(str, Enum):
    APPROVE = "APPROVE"
    DEFER = "DEFER"
    PAUSE = "PAUSE"
    THROTTLE = "THROTTLE"
    PRIORITIZE = "PRIORITIZE"
    RESERVE_CAPACITY = "RESERVE_CAPACITY"
    RELEASE_CAPACITY = "RELEASE_CAPACITY"
    ASSIGN_PROVIDER = "ASSIGN_PROVIDER"
    ASSIGN_WORKER = "ASSIGN_WORKER"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"


class PlannerRecommendationType(str, Enum):
    RUN_NOW = "RUN_NOW"
    RUN_LATER = "RUN_LATER"
    SCALE_WORKERS = "SCALE_WORKERS"
    FAILOVER_PROVIDER = "FAILOVER_PROVIDER"
    REDUCE_CADENCE = "REDUCE_CADENCE"
    INCREASE_CADENCE = "INCREASE_CADENCE"
    SPLIT_UNIVERSE = "SPLIT_UNIVERSE"
    MERGE_UNIVERSES = "MERGE_UNIVERSES"
    PROTECT_SLA = "PROTECT_SLA"
    DEFER_LOW_PRIORITY = "DEFER_LOW_PRIORITY"


class PlannerSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UniversePlanState(str, Enum):
    ACTIVE = "ACTIVE"
    DEFERRED = "DEFERRED"
    PAUSED = "PAUSED"
    THROTTLED = "THROTTLED"
    BLOCKED = "BLOCKED"
    READY = "READY"


# =============================================================================
# Planning Models
# =============================================================================

@dataclass(frozen=True)
class PlannedUniverse:
    tenant_id: str
    universe_id: str
    universe_name: str = ""
    priority: str = "NORMAL"
    estimated_jobs: int = 0
    estimated_runtime_seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    sla_deadline_at: Optional[str] = None
    preferred_provider: Optional[str] = None
    required_job_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderAssignment:
    assignment_id: str
    tenant_id: str
    universe_id: str
    provider: str
    routing_score: float
    estimated_cost_usd: float = 0.0
    quota_utilization: float = 0.0
    status: str = "ACTIVE"
    reason: str = ""
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class WorkerAssignment:
    assignment_id: str
    tenant_id: str
    universe_id: str
    worker_id: str
    capacity_reserved: int
    utilization: float = 0.0
    health_score: float = 1.0
    reason: str = ""
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class CapacityReservation:
    reservation_id: str
    tenant_id: str
    universe_id: str
    requested_capacity: int
    reserved_capacity: int
    reservation_state: str
    reason: str = ""
    expires_at: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class AnalyticsExecutionForecast:
    forecast_id: str
    tenant_id: Optional[str]
    total_universes: int
    total_estimated_jobs: int
    total_estimated_runtime_seconds: float
    total_estimated_cost_usd: float
    projected_worker_capacity_needed: int
    projected_provider_pressure: float
    projected_queue_pressure: float
    projected_completion_minutes: float
    confidence: float
    generated_at: str = field(default_factory=utc_now_iso)
    assumptions: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanningDecision:
    decision_id: str
    decision_type: str
    approved: bool
    severity: str
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class PlanningRecommendation:
    recommendation_id: str
    recommendation_type: str
    severity: str
    title: str
    description: str
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class UniverseExecutionPlan:
    plan_id: str
    tenant_id: str
    universe_id: str
    universe_name: str
    state: str
    priority: str
    priority_score: float
    estimated_jobs: int
    estimated_runtime_seconds: float
    estimated_cost_usd: float
    provider_assignment: Optional[ProviderAssignment] = None
    worker_assignments: List[WorkerAssignment] = field(default_factory=list)
    capacity_reservation: Optional[CapacityReservation] = None
    decisions: List[PlanningDecision] = field(default_factory=list)
    recommendations: List[PlanningRecommendation] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class GlobalExecutionPlan:
    plan_id: str
    state: str
    total_universes: int
    active_universes: int
    deferred_universes: int
    blocked_universes: int
    universe_plans: List[UniverseExecutionPlan]
    forecast: AnalyticsExecutionForecast
    decisions: List[PlanningDecision] = field(default_factory=list)
    recommendations: List[PlanningRecommendation] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "state": self.state,
            "total_universes": self.total_universes,
            "active_universes": self.active_universes,
            "deferred_universes": self.deferred_universes,
            "blocked_universes": self.blocked_universes,
            "universe_plans": [asdict(p) for p in self.universe_plans],
            "forecast": asdict(self.forecast),
            "decisions": [asdict(d) for d in self.decisions],
            "recommendations": [asdict(r) for r in self.recommendations],
            "generated_at": self.generated_at,
        }


# =============================================================================
# Planner
# =============================================================================

class GlobalAnalyticsPlanner:
    """
    Master control-plane planner for the Analytics Fabric.

    It does not execute jobs directly. It creates execution plans that can be
    consumed by orchestrator, scheduler, governor, optimizer, and UI dashboards.
    """

    def __init__(
        self,
        *,
        worker_capacity_model: Optional[Any] = None,
        provider_cost_intelligence: Optional[Any] = None,
        execution_governor: Optional[Any] = None,
        resource_governor: Optional[Any] = None,
        optimizer: Optional[Any] = None,
        runtime_controller: Optional[Any] = None,
        target_queue_clear_minutes: float = 15.0,
        max_provider_quota_utilization: float = 0.90,
        max_queue_pressure: float = 0.85,
        min_provider_routing_score: float = 0.50,
        min_worker_health_score: float = 0.50,
    ) -> None:
        self.worker_capacity_model = worker_capacity_model
        self.provider_cost_intelligence = provider_cost_intelligence
        self.execution_governor = execution_governor
        self.resource_governor = resource_governor
        self.optimizer = optimizer
        self.runtime_controller = runtime_controller

        self.target_queue_clear_minutes = max(1.0, float(target_queue_clear_minutes))
        self.max_provider_quota_utilization = clamp(max_provider_quota_utilization)
        self.max_queue_pressure = clamp(max_queue_pressure)
        self.min_provider_routing_score = clamp(min_provider_routing_score)
        self.min_worker_health_score = clamp(min_worker_health_score)

        self.universes: Dict[str, PlannedUniverse] = {}
        self.deferred_universes: Dict[str, PlanningDecision] = {}
        self.paused_universes: Dict[str, PlanningDecision] = {}
        self.capacity_reservations: Dict[str, CapacityReservation] = {}
        self.plan_history: List[GlobalExecutionPlan] = []
        self.decision_history: List[PlanningDecision] = []
        self.recommendation_history: List[PlanningRecommendation] = []

    # =========================================================================
    # Universe Registry
    # =========================================================================

    def register_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        universe_name: str = "",
        priority: str = "NORMAL",
        estimated_jobs: int = 0,
        estimated_runtime_seconds: float = 0.0,
        estimated_cost_usd: float = 0.0,
        sla_deadline_at: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        required_job_types: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PlannedUniverse:
        universe = PlannedUniverse(
            tenant_id=tenant_id,
            universe_id=universe_id,
            universe_name=universe_name or universe_id,
            priority=normalize_priority(priority),
            estimated_jobs=max(0, int(estimated_jobs)),
            estimated_runtime_seconds=max(0.0, float(estimated_runtime_seconds)),
            estimated_cost_usd=max(0.0, float(estimated_cost_usd)),
            sla_deadline_at=sla_deadline_at,
            preferred_provider=preferred_provider,
            required_job_types=required_job_types or [],
            metadata=metadata or {},
        )
        self.universes[self._universe_key(tenant_id, universe_id)] = universe
        return universe

    def activate_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Universe activated by global analytics planner.",
    ) -> PlanningDecision:
        key = self._universe_key(tenant_id, universe_id)
        self.deferred_universes.pop(key, None)
        self.paused_universes.pop(key, None)

        decision = self._decision(
            decision_type=PlannerDecisionType.APPROVE,
            approved=True,
            severity=PlannerSeverity.INFO,
            tenant_id=tenant_id,
            universe_id=universe_id,
            reason=reason,
        )
        self.decision_history.append(decision)
        return decision

    def defer_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Universe deferred by global analytics planner.",
    ) -> PlanningDecision:
        key = self._universe_key(tenant_id, universe_id)
        decision = self._decision(
            decision_type=PlannerDecisionType.DEFER,
            approved=True,
            severity=PlannerSeverity.MEDIUM,
            tenant_id=tenant_id,
            universe_id=universe_id,
            reason=reason,
        )
        self.deferred_universes[key] = decision
        self.decision_history.append(decision)
        return decision

    def pause_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Universe paused by global analytics planner.",
    ) -> PlanningDecision:
        key = self._universe_key(tenant_id, universe_id)
        decision = self._decision(
            decision_type=PlannerDecisionType.PAUSE,
            approved=True,
            severity=PlannerSeverity.HIGH,
            tenant_id=tenant_id,
            universe_id=universe_id,
            reason=reason,
        )
        self.paused_universes[key] = decision
        self.decision_history.append(decision)
        return decision

    # =========================================================================
    # Plan Builders
    # =========================================================================

    def build_execution_plan(
        self,
        *,
        universes: Optional[Iterable[PlannedUniverse]] = None,
        queue_metrics: Optional[Dict[str, Any]] = None,
        worker_report: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> GlobalExecutionPlan:
        queue_metrics = queue_metrics or {}
        tenant_metrics = tenant_metrics or {}
        universe_metrics = universe_metrics or {}

        planned_universes = list(universes) if universes is not None else list(self.universes.values())
        provider_profiles_list = list(provider_profiles or self._provider_profiles_from_intelligence())

        prioritized = self.prioritize_universes(
            planned_universes,
            queue_metrics=queue_metrics,
            tenant_metrics=tenant_metrics,
            universe_metrics=universe_metrics,
        )

        forecast = self.forecast_execution_load(
            universes=prioritized,
            queue_metrics=queue_metrics,
            worker_report=worker_report,
            provider_profiles=provider_profiles_list,
            tenant_metrics=tenant_metrics,
        )

        universe_plans: List[UniverseExecutionPlan] = []
        global_decisions: List[PlanningDecision] = []
        global_recommendations: List[PlanningRecommendation] = []

        for universe in prioritized:
            universe_plan = self._build_universe_plan(
                universe=universe,
                forecast=forecast,
                queue_metrics=queue_metrics,
                worker_report=worker_report,
                provider_profiles=provider_profiles_list,
                tenant_metrics=tenant_metrics,
                universe_metrics=universe_metrics.get(self._universe_key(universe.tenant_id, universe.universe_id), {}),
            )
            universe_plans.append(universe_plan)
            global_decisions.extend(universe_plan.decisions)
            global_recommendations.extend(universe_plan.recommendations)

        active = len([p for p in universe_plans if p.state in {UniversePlanState.ACTIVE.value, UniversePlanState.READY.value}])
        deferred = len([p for p in universe_plans if p.state == UniversePlanState.DEFERRED.value])
        blocked = len([p for p in universe_plans if p.state in {UniversePlanState.BLOCKED.value, UniversePlanState.PAUSED.value}])

        state = "READY"
        if blocked > 0:
            state = "DEGRADED"
        if active == 0 and universe_plans:
            state = "BLOCKED"
        if forecast.projected_queue_pressure >= self.max_queue_pressure:
            state = "PRESSURED"

        plan = GlobalExecutionPlan(
            plan_id=f"gplan_{uuid.uuid4().hex}",
            state=state,
            total_universes=len(universe_plans),
            active_universes=active,
            deferred_universes=deferred,
            blocked_universes=blocked,
            universe_plans=universe_plans,
            forecast=forecast,
            decisions=global_decisions,
            recommendations=global_recommendations,
        )

        self.plan_history.append(plan)
        self.decision_history.extend(global_decisions)
        self.recommendation_history.extend(global_recommendations)
        self._trim_history()

        return plan

    def _build_universe_plan(
        self,
        *,
        universe: PlannedUniverse,
        forecast: AnalyticsExecutionForecast,
        queue_metrics: Dict[str, Any],
        worker_report: Optional[Any],
        provider_profiles: List[Any],
        tenant_metrics: Dict[str, Any],
        universe_metrics: Dict[str, Any],
    ) -> UniverseExecutionPlan:
        key = self._universe_key(universe.tenant_id, universe.universe_id)

        decisions: List[PlanningDecision] = []
        recommendations: List[PlanningRecommendation] = []

        state = UniversePlanState.READY.value
        priority_score = self._score_universe_priority(
            universe,
            queue_metrics=queue_metrics,
            tenant_metrics=tenant_metrics,
            universe_metrics=universe_metrics,
        )

        if key in self.paused_universes:
            state = UniversePlanState.PAUSED.value
            decisions.append(self.paused_universes[key])

        elif key in self.deferred_universes:
            state = UniversePlanState.DEFERRED.value
            decisions.append(self.deferred_universes[key])

        provider_assignment = self.build_provider_plan(
            universe=universe,
            provider_profiles=provider_profiles,
        )

        if provider_assignment is None:
            state = UniversePlanState.BLOCKED.value
            decisions.append(
                self._decision(
                    decision_type=PlannerDecisionType.DEFER,
                    approved=True,
                    severity=PlannerSeverity.HIGH,
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    reason="No suitable provider available.",
                )
            )
            recommendations.append(
                self._recommendation(
                    recommendation_type=PlannerRecommendationType.FAILOVER_PROVIDER,
                    severity=PlannerSeverity.HIGH,
                    title="Provider assignment unavailable",
                    description="No provider met routing, quota, or health thresholds.",
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    confidence=0.90,
                )
            )

        worker_assignments = self.build_worker_plan(
            universe=universe,
            worker_report=worker_report,
        )

        reservation = self.reserve_capacity(
            tenant_id=universe.tenant_id,
            universe_id=universe.universe_id,
            requested_capacity=max(1, min(universe.estimated_jobs or 1, 1000)),
            worker_report=worker_report,
        )

        if reservation.reservation_state == "DENIED":
            state = UniversePlanState.DEFERRED.value
            decisions.append(
                self._decision(
                    decision_type=PlannerDecisionType.DEFER,
                    approved=True,
                    severity=PlannerSeverity.MEDIUM,
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    reason=reservation.reason,
                )
            )

        if forecast.projected_queue_pressure >= self.max_queue_pressure and universe.priority in {"LOW", "NORMAL"}:
            state = UniversePlanState.THROTTLED.value
            decisions.append(
                self._decision(
                    decision_type=PlannerDecisionType.THROTTLE,
                    approved=True,
                    severity=PlannerSeverity.MEDIUM,
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    reason="Queue pressure requires throttling non-critical workloads.",
                    metadata={"projected_queue_pressure": forecast.projected_queue_pressure},
                )
            )
            recommendations.append(
                self._recommendation(
                    recommendation_type=PlannerRecommendationType.DEFER_LOW_PRIORITY,
                    severity=PlannerSeverity.MEDIUM,
                    title="Defer or throttle lower-priority universe",
                    description="Projected queue pressure is high and this universe is not critical.",
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    confidence=0.85,
                )
            )

        if state == UniversePlanState.READY.value:
            state = UniversePlanState.ACTIVE.value
            decisions.append(
                self._decision(
                    decision_type=PlannerDecisionType.APPROVE,
                    approved=True,
                    severity=PlannerSeverity.INFO,
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    provider=provider_assignment.provider if provider_assignment else None,
                    reason="Universe execution approved by global analytics planner.",
                )
            )
            recommendations.append(
                self._recommendation(
                    recommendation_type=PlannerRecommendationType.RUN_NOW,
                    severity=PlannerSeverity.INFO,
                    title="Run universe analytics",
                    description="Universe is ready for execution.",
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    provider=provider_assignment.provider if provider_assignment else None,
                    confidence=0.90,
                )
            )

        return UniverseExecutionPlan(
            plan_id=f"uplan_{uuid.uuid4().hex}",
            tenant_id=universe.tenant_id,
            universe_id=universe.universe_id,
            universe_name=universe.universe_name,
            state=state,
            priority=universe.priority,
            priority_score=round(priority_score, 4),
            estimated_jobs=universe.estimated_jobs,
            estimated_runtime_seconds=universe.estimated_runtime_seconds,
            estimated_cost_usd=universe.estimated_cost_usd,
            provider_assignment=provider_assignment,
            worker_assignments=worker_assignments,
            capacity_reservation=reservation,
            decisions=decisions,
            recommendations=recommendations,
        )

    # =========================================================================
    # Capacity / Provider / Worker Planning
    # =========================================================================

    def build_capacity_plan(
        self,
        *,
        universes: Iterable[PlannedUniverse],
        worker_report: Optional[Any] = None,
    ) -> Dict[str, Any]:
        universes_list = list(universes)
        total_requested = sum(max(1, int(u.estimated_jobs or 1)) for u in universes_list)
        fleet = getattr(worker_report, "fleet_profile", None) if worker_report is not None else None
        available_capacity = int(getattr(fleet, "available_capacity", 0) or 0)

        return {
            "requested_capacity": total_requested,
            "available_capacity": available_capacity,
            "capacity_gap": max(0, total_requested - available_capacity),
            "sufficient_capacity": available_capacity >= total_requested,
            "generated_at": utc_now_iso(),
        }

    def build_provider_plan(
        self,
        *,
        universe: PlannedUniverse,
        provider_profiles: Iterable[Any],
    ) -> Optional[ProviderAssignment]:
        providers = list(provider_profiles)

        if universe.preferred_provider:
            preferred = [
                p for p in providers
                if str(getattr(p, "provider", getattr(p, "provider_name", ""))).upper()
                == universe.preferred_provider.upper()
            ]
            if preferred:
                providers = preferred + [p for p in providers if p not in preferred]

        candidates: List[Any] = []
        for provider in providers:
            status = str(getattr(provider, "status", "ACTIVE")).upper()
            routing_score = float(getattr(provider, "routing_score", 0.0) or 0.0)
            quota = float(getattr(provider, "quota_utilization", 0.0) or 0.0)

            if status in {"DISABLED", "EXHAUSTED"}:
                continue

            if routing_score < self.min_provider_routing_score:
                continue

            if quota >= self.max_provider_quota_utilization:
                continue

            candidates.append(provider)

        if not candidates:
            return None

        selected = sorted(
            candidates,
            key=lambda p: (
                float(getattr(p, "routing_score", 0.0) or 0.0),
                float(getattr(p, "efficiency_score", 0.0) or 0.0),
                -float(getattr(p, "quota_utilization", 0.0) or 0.0),
            ),
            reverse=True,
        )[0]

        provider_name = str(getattr(selected, "provider", getattr(selected, "provider_name", "UNKNOWN")))
        routing_score = float(getattr(selected, "routing_score", 0.0) or 0.0)
        quota = float(getattr(selected, "quota_utilization", 0.0) or 0.0)
        status = str(getattr(selected, "status", "ACTIVE"))
        cost_per_request = float(getattr(selected, "cost_per_request", 0.0) or 0.0)

        return ProviderAssignment(
            assignment_id=f"passign_{uuid.uuid4().hex}",
            tenant_id=universe.tenant_id,
            universe_id=universe.universe_id,
            provider=provider_name,
            routing_score=round(routing_score, 4),
            estimated_cost_usd=round(cost_per_request * max(1, universe.estimated_jobs), 6),
            quota_utilization=round(quota, 4),
            status=status,
            reason="Selected highest scoring eligible provider.",
        )

    def build_worker_plan(
        self,
        *,
        universe: PlannedUniverse,
        worker_report: Optional[Any] = None,
    ) -> List[WorkerAssignment]:
        if worker_report is None:
            return []

        profiles = list(getattr(worker_report, "worker_profiles", []) or [])
        if not profiles:
            return []

        eligible = [
            p for p in profiles
            if str(getattr(p, "state", "")).upper() not in {"OFFLINE", "DEGRADED"}
            and float(getattr(p, "health_score", 0.0) or 0.0) >= self.min_worker_health_score
            and int(getattr(p, "available_capacity", 0) or 0) > 0
        ]

        if not eligible:
            return []

        requested = max(1, int(universe.estimated_jobs or 1))
        remaining = requested
        assignments: List[WorkerAssignment] = []

        ranked = sorted(
            eligible,
            key=lambda p: (
                float(getattr(p, "health_score", 0.0) or 0.0),
                float(getattr(p, "efficiency_score", 0.0) or 0.0),
                int(getattr(p, "available_capacity", 0) or 0),
            ),
            reverse=True,
        )

        for worker in ranked:
            if remaining <= 0:
                break

            available = int(getattr(worker, "available_capacity", 0) or 0)
            reserve = min(available, remaining)

            if reserve <= 0:
                continue

            assignments.append(
                WorkerAssignment(
                    assignment_id=f"wasign_{uuid.uuid4().hex}",
                    tenant_id=universe.tenant_id,
                    universe_id=universe.universe_id,
                    worker_id=str(getattr(worker, "worker_id", "UNKNOWN")),
                    capacity_reserved=reserve,
                    utilization=float(getattr(worker, "utilization", 0.0) or 0.0),
                    health_score=float(getattr(worker, "health_score", 0.0) or 0.0),
                    reason="Assigned by global analytics planner capacity ranking.",
                )
            )

            remaining -= reserve

        return assignments

    def reserve_capacity(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        requested_capacity: int,
        worker_report: Optional[Any] = None,
        expires_at: Optional[str] = None,
    ) -> CapacityReservation:
        requested_capacity = max(1, int(requested_capacity))

        fleet = getattr(worker_report, "fleet_profile", None) if worker_report is not None else None
        available = int(getattr(fleet, "available_capacity", requested_capacity) or 0)

        reserved = min(requested_capacity, max(0, available))
        state = "RESERVED" if reserved >= requested_capacity else "PARTIAL"
        reason = "Capacity reserved."

        if reserved <= 0:
            state = "DENIED"
            reason = "No worker capacity available."

        reservation = CapacityReservation(
            reservation_id=f"cres_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            universe_id=universe_id,
            requested_capacity=requested_capacity,
            reserved_capacity=reserved,
            reservation_state=state,
            reason=reason,
            expires_at=expires_at,
        )

        self.capacity_reservations[self._universe_key(tenant_id, universe_id)] = reservation
        return reservation

    def release_capacity(
        self,
        *,
        tenant_id: str,
        universe_id: str,
    ) -> PlanningDecision:
        key = self._universe_key(tenant_id, universe_id)
        self.capacity_reservations.pop(key, None)

        decision = self._decision(
            decision_type=PlannerDecisionType.RELEASE_CAPACITY,
            approved=True,
            severity=PlannerSeverity.INFO,
            tenant_id=tenant_id,
            universe_id=universe_id,
            reason="Capacity reservation released.",
        )
        self.decision_history.append(decision)
        return decision

    # =========================================================================
    # Forecasting / Prioritization
    # =========================================================================

    def forecast_execution_load(
        self,
        *,
        universes: Iterable[PlannedUniverse],
        queue_metrics: Optional[Dict[str, Any]] = None,
        worker_report: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsExecutionForecast:
        universes_list = list(universes)
        queue_metrics = queue_metrics or {}

        total_jobs = sum(max(0, u.estimated_jobs) for u in universes_list)
        total_runtime = sum(max(0.0, u.estimated_runtime_seconds) for u in universes_list)
        total_cost = sum(max(0.0, u.estimated_cost_usd) for u in universes_list)

        fleet = getattr(worker_report, "fleet_profile", None) if worker_report is not None else None
        total_capacity = int(getattr(fleet, "total_capacity", 0) or 0)
        avg_throughput = float(getattr(fleet, "avg_throughput_per_minute", 0.0) or 0.0)
        queue_depth = int(queue_metrics.get("queue_depth", 0))

        projected_capacity_needed = max(
            total_capacity,
            math.ceil(safe_divide(total_jobs + queue_depth, self.target_queue_clear_minutes, 0.0)),
        )

        projected_queue_pressure = clamp(
            safe_divide(queue_depth + total_jobs, max(1, total_capacity))
        )

        provider_pressure = 0.0
        for provider in provider_profiles or []:
            quota = float(getattr(provider, "quota_utilization", 0.0) or 0.0)
            failure = float(getattr(provider, "failure_rate", 0.0) or 0.0)
            throttle = float(getattr(provider, "throttle_rate", 0.0) or 0.0)
            provider_pressure = max(provider_pressure, clamp((quota * 0.50) + (failure * 0.30) + (throttle * 0.20)))

        completion_minutes = safe_divide(total_jobs + queue_depth, max(0.001, avg_throughput), 0.0)

        confidence = 0.75
        if worker_report is not None:
            confidence += 0.10
        if provider_profiles:
            confidence += 0.10
        if total_jobs == 0:
            confidence -= 0.10

        return AnalyticsExecutionForecast(
            forecast_id=f"efc_{uuid.uuid4().hex}",
            tenant_id=None,
            total_universes=len(universes_list),
            total_estimated_jobs=total_jobs,
            total_estimated_runtime_seconds=round(total_runtime, 4),
            total_estimated_cost_usd=round(total_cost, 6),
            projected_worker_capacity_needed=projected_capacity_needed,
            projected_provider_pressure=round(provider_pressure, 4),
            projected_queue_pressure=round(projected_queue_pressure, 4),
            projected_completion_minutes=round(completion_minutes, 4),
            confidence=round(clamp(confidence), 4),
            assumptions={
                "target_queue_clear_minutes": self.target_queue_clear_minutes,
                "queue_depth": queue_depth,
                "total_capacity": total_capacity,
                "avg_throughput_per_minute": avg_throughput,
            },
        )

    def prioritize_universes(
        self,
        universes: Iterable[PlannedUniverse],
        *,
        queue_metrics: Optional[Dict[str, Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[PlannedUniverse]:
        queue_metrics = queue_metrics or {}
        tenant_metrics = tenant_metrics or {}
        universe_metrics = universe_metrics or {}

        return sorted(
            list(universes),
            key=lambda u: self._score_universe_priority(
                u,
                queue_metrics=queue_metrics,
                tenant_metrics=tenant_metrics,
                universe_metrics=universe_metrics.get(self._universe_key(u.tenant_id, u.universe_id), {}),
            ),
            reverse=True,
        )

    def _score_universe_priority(
        self,
        universe: PlannedUniverse,
        *,
        queue_metrics: Dict[str, Any],
        tenant_metrics: Dict[str, Any],
        universe_metrics: Dict[str, Any],
    ) -> float:
        base = priority_rank(universe.priority) / 100.0

        sla_bonus = 0.0
        if universe.sla_deadline_at:
            sla_bonus = 0.15

        universe_pressure = clamp(float(universe_metrics.get("pressure", universe_metrics.get("risk", 0.0)) or 0.0))
        tenant_pressure = clamp(float(tenant_metrics.get("pressure", tenant_metrics.get("risk", 0.0)) or 0.0))

        size_penalty = clamp(safe_divide(universe.estimated_jobs, 100000.0)) * 0.10
        cost_penalty = clamp(safe_divide(universe.estimated_cost_usd, 1000.0)) * 0.10

        score = clamp(
            base
            + sla_bonus
            + (universe_pressure * 0.10)
            + (tenant_pressure * 0.05)
            - size_penalty
            - cost_penalty
        )

        return score

    # =========================================================================
    # Decision / Recommendation APIs
    # =========================================================================

    def generate_planning_decisions(
        self,
        plan: GlobalExecutionPlan,
    ) -> List[PlanningDecision]:
        decisions: List[PlanningDecision] = []

        for universe_plan in plan.universe_plans:
            decisions.extend(universe_plan.decisions)

        self.decision_history.extend(decisions)
        self._trim_history()
        return decisions

    def _decision(
        self,
        *,
        decision_type: PlannerDecisionType,
        approved: bool,
        severity: PlannerSeverity,
        reason: str,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        provider: Optional[str] = None,
        worker_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PlanningDecision:
        return PlanningDecision(
            decision_id=f"pdec_{uuid.uuid4().hex}",
            decision_type=decision_type.value,
            approved=approved,
            severity=severity.value,
            tenant_id=tenant_id,
            universe_id=universe_id,
            provider=provider,
            worker_id=worker_id,
            reason=reason,
            metadata=metadata or {},
        )

    def _recommendation(
        self,
        *,
        recommendation_type: PlannerRecommendationType,
        severity: PlannerSeverity,
        title: str,
        description: str,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        provider: Optional[str] = None,
        worker_id: Optional[str] = None,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PlanningRecommendation:
        return PlanningRecommendation(
            recommendation_id=f"prec_{uuid.uuid4().hex}",
            recommendation_type=recommendation_type.value,
            severity=severity.value,
            title=title,
            description=description,
            tenant_id=tenant_id,
            universe_id=universe_id,
            provider=provider,
            worker_id=worker_id,
            confidence=round(clamp(confidence), 4),
            metadata=metadata or {},
        )

    # =========================================================================
    # Summary / State
    # =========================================================================

    def planner_summary(self) -> Dict[str, Any]:
        latest_plan = self.plan_history[-1] if self.plan_history else None

        return {
            "registered_universes": len(self.universes),
            "deferred_universes": len(self.deferred_universes),
            "paused_universes": len(self.paused_universes),
            "capacity_reservations": len(self.capacity_reservations),
            "plans_generated": len(self.plan_history),
            "decisions": len(self.decision_history),
            "recommendations": len(self.recommendation_history),
            "latest_plan_state": latest_plan.state if latest_plan else None,
            "latest_active_universes": latest_plan.active_universes if latest_plan else 0,
            "latest_deferred_universes": latest_plan.deferred_universes if latest_plan else 0,
            "latest_blocked_universes": latest_plan.blocked_universes if latest_plan else 0,
            "generated_at": utc_now_iso(),
        }

    def export_state(self) -> Dict[str, Any]:
        return {
            "summary": self.planner_summary(),
            "universes": {k: asdict(v) for k, v in self.universes.items()},
            "deferred_universes": {k: asdict(v) for k, v in self.deferred_universes.items()},
            "paused_universes": {k: asdict(v) for k, v in self.paused_universes.items()},
            "capacity_reservations": {k: asdict(v) for k, v in self.capacity_reservations.items()},
            "recent_plans": [p.as_dict() for p in self.plan_history[-10:]],
            "recent_decisions": [asdict(d) for d in self.decision_history[-100:]],
            "recent_recommendations": [asdict(r) for r in self.recommendation_history[-100:]],
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _provider_profiles_from_intelligence(self) -> List[Any]:
        if self.provider_cost_intelligence is None:
            return []

        rank = getattr(self.provider_cost_intelligence, "rank_providers", None)
        if callable(rank):
            try:
                return list(rank())
            except Exception:
                return []

        profiles = getattr(self.provider_cost_intelligence, "provider_profiles", None)
        if isinstance(profiles, dict):
            return list(profiles.values())

        return []

    @staticmethod
    def _universe_key(tenant_id: str, universe_id: str) -> str:
        return f"{tenant_id}::{universe_id}"

    def _trim_history(self, max_items: int = 5000) -> None:
        if len(self.plan_history) > 1000:
            self.plan_history = self.plan_history[-1000:]
        if len(self.decision_history) > max_items:
            self.decision_history = self.decision_history[-max_items:]
        if len(self.recommendation_history) > max_items:
            self.recommendation_history = self.recommendation_history[-max_items:]


# =============================================================================
# Factory
# =============================================================================

def create_global_analytics_planner(
    *,
    worker_capacity_model: Optional[Any] = None,
    provider_cost_intelligence: Optional[Any] = None,
    execution_governor: Optional[Any] = None,
    resource_governor: Optional[Any] = None,
    optimizer: Optional[Any] = None,
    runtime_controller: Optional[Any] = None,
    target_queue_clear_minutes: float = 15.0,
    max_provider_quota_utilization: float = 0.90,
    max_queue_pressure: float = 0.85,
    min_provider_routing_score: float = 0.50,
    min_worker_health_score: float = 0.50,
) -> GlobalAnalyticsPlanner:
    return GlobalAnalyticsPlanner(
        worker_capacity_model=worker_capacity_model,
        provider_cost_intelligence=provider_cost_intelligence,
        execution_governor=execution_governor,
        resource_governor=resource_governor,
        optimizer=optimizer,
        runtime_controller=runtime_controller,
        target_queue_clear_minutes=target_queue_clear_minutes,
        max_provider_quota_utilization=max_provider_quota_utilization,
        max_queue_pressure=max_queue_pressure,
        min_provider_routing_score=min_provider_routing_score,
        min_worker_health_score=min_worker_health_score,
    )