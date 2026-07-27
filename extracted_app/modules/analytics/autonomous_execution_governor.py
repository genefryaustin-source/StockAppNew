"""
modules/analytics/autonomous_execution_governor.py
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    try:
        if denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except Exception:
        return default


# =============================================================================
# Enums
# =============================================================================

class ExecutionGovernanceDecisionType(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    DEFER = "DEFER"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    THROTTLE = "THROTTLE"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    FAILOVER_PROVIDER = "FAILOVER_PROVIDER"
    DISABLE_PROVIDER = "DISABLE_PROVIDER"
    QUARANTINE_WORKER = "QUARANTINE_WORKER"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class ExecutionGovernanceSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionRiskLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutionGovernanceScope(str, Enum):
    SYSTEM = "SYSTEM"
    TENANT = "TENANT"
    UNIVERSE = "UNIVERSE"
    PROVIDER = "PROVIDER"
    WORKER = "WORKER"
    QUEUE = "QUEUE"
    RUNTIME = "RUNTIME"


# =============================================================================
# Data Models
# =============================================================================

@dataclass(frozen=True)
class GovernancePolicy:
    policy_id: str = field(default_factory=lambda: f"egpol_{uuid.uuid4().hex}")
    name: str = "Default Analytics Execution Governance Policy"
    enabled: bool = True

    max_queue_depth: int = 100000
    max_queue_pressure: float = 0.85
    max_worker_utilization: float = 0.90
    max_worker_failure_rate: float = 0.10
    max_provider_failure_rate: float = 0.15
    max_provider_throttle_rate: float = 0.20
    max_provider_quota_utilization: float = 0.90

    min_worker_health_score: float = 0.50
    min_provider_routing_score: float = 0.50
    min_fleet_health_score: float = 0.55

    allow_autonomous_scale_up: bool = True
    allow_autonomous_scale_down: bool = False
    allow_autonomous_provider_failover: bool = True
    allow_autonomous_provider_disable: bool = False
    allow_autonomous_worker_quarantine: bool = True
    allow_autonomous_universe_pause: bool = False
    allow_emergency_stop: bool = True

    low_priority_throttle_threshold: float = 0.75
    high_priority_protection_enabled: bool = True

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPressureProfile:
    queue_depth: int = 0
    active_leases: int = 0
    workers_online: int = 0
    total_capacity: int = 0
    active_jobs: int = 0
    available_capacity: int = 0
    worker_utilization: float = 0.0
    queue_pressure: float = 0.0
    provider_pressure: float = 0.0
    tenant_pressure: float = 0.0
    universe_pressure: float = 0.0
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ExecutionRiskProfile:
    risk_id: str
    risk_level: str
    risk_score: float
    queue_risk: float = 0.0
    worker_risk: float = 0.0
    provider_risk: float = 0.0
    tenant_risk: float = 0.0
    universe_risk: float = 0.0
    runtime_risk: float = 0.0
    reasons: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class GovernanceAction:
    action_id: str
    action_type: str
    scope: str
    severity: str
    title: str
    description: str
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    priority: str = "NORMAL"
    autonomous_allowed: bool = False
    requires_approval: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class GovernanceDecision:
    decision_id: str
    decision: str
    approved: bool
    severity: str
    reason: str
    risk_profile: Optional[ExecutionRiskProfile] = None
    actions: List[GovernanceAction] = field(default_factory=list)
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernanceEvaluation:
    evaluation_id: str
    policy_id: str
    pressure_profile: ExecutionPressureProfile
    risk_profile: ExecutionRiskProfile
    decisions: List[GovernanceDecision]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "policy_id": self.policy_id,
            "pressure_profile": asdict(self.pressure_profile),
            "risk_profile": asdict(self.risk_profile),
            "decisions": [asdict(d) for d in self.decisions],
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class ExecutionApprovalRequest:
    request_id: str
    requested_action: str
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    provider: Optional[str] = None
    worker_id: Optional[str] = None
    risk_score: float = 0.0
    priority: str = "NORMAL"
    metadata: Dict[str, Any] = field(default_factory=dict)
    requested_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ExecutionApprovalResult:
    request_id: str
    approved: bool
    decision: str
    reason: str
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Governor
# =============================================================================

class AutonomousExecutionGovernor:
    """
    Autonomous governance authority for Analytics Fabric execution.

    It consumes:
        - worker capacity reports
        - provider profiles
        - queue/runtime metrics
        - tenant/universe pressure metrics
        - resource governor outputs

    It produces:
        - approve / deny / defer decisions
        - pause / throttle / reroute recommendations
        - provider failover decisions
        - worker quarantine decisions
        - emergency-stop decisions
    """

    def __init__(
        self,
        *,
        policy: Optional[GovernancePolicy] = None,
    ) -> None:
        self.policy = policy or GovernancePolicy()

        self.evaluation_history: List[GovernanceEvaluation] = []
        self.decision_history: List[GovernanceDecision] = []
        self.action_history: List[GovernanceAction] = []
        self.approval_history: List[ExecutionApprovalResult] = []

        self.paused_universes: Dict[str, GovernanceAction] = {}
        self.throttled_universes: Dict[str, GovernanceAction] = {}
        self.disabled_providers: Dict[str, GovernanceAction] = {}
        self.quarantined_workers: Dict[str, GovernanceAction] = {}

    # =========================================================================
    # Runtime / Pressure Evaluation
    # =========================================================================

    def evaluate_runtime_state(
        self,
        *,
        queue_metrics: Optional[Dict[str, Any]] = None,
        fleet_profile: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Any]] = None,
    ) -> GovernanceEvaluation:
        pressure = self.build_pressure_profile(
            queue_metrics=queue_metrics or {},
            fleet_profile=fleet_profile,
            provider_profiles=list(provider_profiles or []),
            tenant_metrics=tenant_metrics or {},
            universe_metrics=universe_metrics or {},
        )

        risk = self.evaluate_execution_risk(
            pressure_profile=pressure,
            fleet_profile=fleet_profile,
            provider_profiles=list(provider_profiles or []),
            tenant_metrics=tenant_metrics or {},
            universe_metrics=universe_metrics or {},
        )

        decisions = self.generate_governance_decisions(
            pressure_profile=pressure,
            risk_profile=risk,
            fleet_profile=fleet_profile,
            provider_profiles=list(provider_profiles or []),
            tenant_metrics=tenant_metrics or {},
            universe_metrics=universe_metrics or {},
        )

        evaluation = GovernanceEvaluation(
            evaluation_id=f"egeval_{uuid.uuid4().hex}",
            policy_id=self.policy.policy_id,
            pressure_profile=pressure,
            risk_profile=risk,
            decisions=decisions,
        )

        self.evaluation_history.append(evaluation)
        self.decision_history.extend(decisions)
        for decision in decisions:
            self.action_history.extend(decision.actions)

        self._trim_history()

        return evaluation

    def build_pressure_profile(
        self,
        *,
        queue_metrics: Dict[str, Any],
        fleet_profile: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPressureProfile:
        queue_depth = int(queue_metrics.get("queue_depth", 0))
        active_leases = int(queue_metrics.get("active_leases", 0))

        workers_online = int(getattr(fleet_profile, "workers_online", 0) or 0)
        total_capacity = int(getattr(fleet_profile, "total_capacity", 0) or 0)
        active_jobs = int(getattr(fleet_profile, "active_jobs", 0) or 0)
        available_capacity = int(getattr(fleet_profile, "available_capacity", 0) or 0)

        worker_utilization = float(getattr(fleet_profile, "avg_utilization", 0.0) or 0.0)
        queue_pressure = clamp(safe_divide(queue_depth, max(1, total_capacity)))

        providers = list(provider_profiles or [])
        provider_pressure_values = []
        for provider in providers:
            quota = float(getattr(provider, "quota_utilization", 0.0) or 0.0)
            failure = float(getattr(provider, "failure_rate", 0.0) or 0.0)
            throttle = float(getattr(provider, "throttle_rate", 0.0) or 0.0)
            provider_pressure_values.append(clamp((quota * 0.45) + (failure * 0.35) + (throttle * 0.20)))

        provider_pressure = max(provider_pressure_values) if provider_pressure_values else 0.0

        tenant_metrics = tenant_metrics or {}
        universe_metrics = universe_metrics or {}

        tenant_pressure = clamp(float(tenant_metrics.get("pressure", tenant_metrics.get("queue_pressure", 0.0)) or 0.0))
        universe_pressure = clamp(float(universe_metrics.get("pressure", universe_metrics.get("queue_pressure", 0.0)) or 0.0))

        return ExecutionPressureProfile(
            queue_depth=queue_depth,
            active_leases=active_leases,
            workers_online=workers_online,
            total_capacity=total_capacity,
            active_jobs=active_jobs,
            available_capacity=available_capacity,
            worker_utilization=round(worker_utilization, 4),
            queue_pressure=round(queue_pressure, 4),
            provider_pressure=round(provider_pressure, 4),
            tenant_pressure=round(tenant_pressure, 4),
            universe_pressure=round(universe_pressure, 4),
        )

    def evaluate_execution_risk(
        self,
        *,
        pressure_profile: ExecutionPressureProfile,
        fleet_profile: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Any]] = None,
    ) -> ExecutionRiskProfile:
        reasons: List[str] = []

        queue_risk = pressure_profile.queue_pressure
        if pressure_profile.queue_depth >= self.policy.max_queue_depth:
            queue_risk = max(queue_risk, 1.0)
            reasons.append("Queue depth exceeds policy threshold.")
        elif pressure_profile.queue_pressure >= self.policy.max_queue_pressure:
            reasons.append("Queue pressure is elevated.")

        worker_risk = clamp(pressure_profile.worker_utilization)
        fleet_health = float(getattr(fleet_profile, "health_score", 1.0) or 1.0) if fleet_profile is not None else 1.0
        fleet_failure = float(getattr(fleet_profile, "avg_failure_rate", 0.0) or 0.0) if fleet_profile is not None else 0.0

        if pressure_profile.workers_online == 0 and pressure_profile.queue_depth > 0:
            worker_risk = 1.0
            reasons.append("No workers online while queue has work.")
        if pressure_profile.worker_utilization >= self.policy.max_worker_utilization:
            reasons.append("Worker utilization exceeds policy threshold.")
        if fleet_failure >= self.policy.max_worker_failure_rate:
            worker_risk = max(worker_risk, fleet_failure)
            reasons.append("Worker failure rate exceeds policy threshold.")
        if fleet_health < self.policy.min_fleet_health_score:
            worker_risk = max(worker_risk, 1.0 - fleet_health)
            reasons.append("Fleet health is below minimum threshold.")

        provider_risk = 0.0
        for provider in provider_profiles or []:
            provider_name = str(getattr(provider, "provider", getattr(provider, "provider_name", "UNKNOWN")))
            quota = float(getattr(provider, "quota_utilization", 0.0) or 0.0)
            failure = float(getattr(provider, "failure_rate", 0.0) or 0.0)
            throttle = float(getattr(provider, "throttle_rate", 0.0) or 0.0)
            routing_score = float(getattr(provider, "routing_score", 1.0) or 1.0)

            current = clamp((quota * 0.40) + (failure * 0.35) + (throttle * 0.25))
            provider_risk = max(provider_risk, current)

            if quota >= self.policy.max_provider_quota_utilization:
                reasons.append(f"{provider_name} quota utilization exceeds policy threshold.")
            if failure >= self.policy.max_provider_failure_rate:
                reasons.append(f"{provider_name} failure rate exceeds policy threshold.")
            if throttle >= self.policy.max_provider_throttle_rate:
                reasons.append(f"{provider_name} throttle rate exceeds policy threshold.")
            if routing_score < self.policy.min_provider_routing_score:
                reasons.append(f"{provider_name} routing score is below policy threshold.")

        tenant_metrics = tenant_metrics or {}
        universe_metrics = universe_metrics or {}

        tenant_risk = clamp(float(tenant_metrics.get("risk", tenant_metrics.get("pressure", 0.0)) or 0.0))
        universe_risk = clamp(float(universe_metrics.get("risk", universe_metrics.get("pressure", 0.0)) or 0.0))

        runtime_risk = clamp(
            (queue_risk * 0.30)
            + (worker_risk * 0.30)
            + (provider_risk * 0.20)
            + (tenant_risk * 0.10)
            + (universe_risk * 0.10)
        )

        level = self._risk_level(runtime_risk)

        if not reasons and runtime_risk <= 0.05:
            reasons.append("Runtime state is within policy limits.")

        return ExecutionRiskProfile(
            risk_id=f"egrisk_{uuid.uuid4().hex}",
            risk_level=level,
            risk_score=round(runtime_risk, 4),
            queue_risk=round(queue_risk, 4),
            worker_risk=round(worker_risk, 4),
            provider_risk=round(provider_risk, 4),
            tenant_risk=round(tenant_risk, 4),
            universe_risk=round(universe_risk, 4),
            runtime_risk=round(runtime_risk, 4),
            reasons=reasons,
        )

    # =========================================================================
    # Focused Evaluators
    # =========================================================================

    def evaluate_provider_state(
        self,
        provider_profile: Any,
    ) -> GovernanceDecision:
        provider_name = str(getattr(provider_profile, "provider", getattr(provider_profile, "provider_name", "UNKNOWN")))
        quota = float(getattr(provider_profile, "quota_utilization", 0.0) or 0.0)
        failure = float(getattr(provider_profile, "failure_rate", 0.0) or 0.0)
        throttle = float(getattr(provider_profile, "throttle_rate", 0.0) or 0.0)
        routing_score = float(getattr(provider_profile, "routing_score", 1.0) or 1.0)

        actions: List[GovernanceAction] = []

        if quota >= 1.0:
            actions.append(
                self._action(
                    action_type=ExecutionGovernanceDecisionType.FAILOVER_PROVIDER,
                    scope=ExecutionGovernanceScope.PROVIDER,
                    severity=ExecutionGovernanceSeverity.CRITICAL,
                    title="Fail over exhausted analytics provider",
                    description=f"{provider_name} quota is exhausted.",
                    provider=provider_name,
                    autonomous_allowed=self.policy.allow_autonomous_provider_failover,
                    requires_approval=not self.policy.allow_autonomous_provider_failover,
                    metadata={"quota_utilization": quota},
                )
            )
            return self._decision(
                decision=ExecutionGovernanceDecisionType.FAILOVER_PROVIDER,
                approved=self.policy.allow_autonomous_provider_failover,
                severity=ExecutionGovernanceSeverity.CRITICAL,
                reason=f"{provider_name} quota exhausted.",
                actions=actions,
                provider=provider_name,
            )

        if throttle >= self.policy.max_provider_throttle_rate or failure >= self.policy.max_provider_failure_rate:
            actions.append(
                self._action(
                    action_type=ExecutionGovernanceDecisionType.REROUTE,
                    scope=ExecutionGovernanceScope.PROVIDER,
                    severity=ExecutionGovernanceSeverity.HIGH,
                    title="Reroute provider workload",
                    description=f"{provider_name} is degraded or throttling.",
                    provider=provider_name,
                    autonomous_allowed=True,
                    requires_approval=False,
                    metadata={
                        "failure_rate": failure,
                        "throttle_rate": throttle,
                    },
                )
            )
            return self._decision(
                decision=ExecutionGovernanceDecisionType.REROUTE,
                approved=True,
                severity=ExecutionGovernanceSeverity.HIGH,
                reason=f"{provider_name} degraded.",
                actions=actions,
                provider=provider_name,
            )

        if routing_score < self.policy.min_provider_routing_score:
            return self._decision(
                decision=ExecutionGovernanceDecisionType.DEFER,
                approved=False,
                severity=ExecutionGovernanceSeverity.MEDIUM,
                reason=f"{provider_name} routing score below threshold.",
                provider=provider_name,
            )

        return self._decision(
            decision=ExecutionGovernanceDecisionType.APPROVE,
            approved=True,
            severity=ExecutionGovernanceSeverity.INFO,
            reason=f"{provider_name} provider state approved.",
            provider=provider_name,
        )

    def evaluate_worker_capacity(
        self,
        worker_profile: Any,
    ) -> GovernanceDecision:
        worker_id = str(getattr(worker_profile, "worker_id", "UNKNOWN"))
        state = str(getattr(worker_profile, "state", "UNKNOWN")).upper()
        failure = float(getattr(worker_profile, "failure_rate", 0.0) or 0.0)
        health = float(getattr(worker_profile, "health_score", 1.0) or 1.0)
        utilization = float(getattr(worker_profile, "utilization", 0.0) or 0.0)

        if state in {"OFFLINE", "DEAD", "LOST"}:
            action = self._action(
                action_type=ExecutionGovernanceDecisionType.QUARANTINE_WORKER,
                scope=ExecutionGovernanceScope.WORKER,
                severity=ExecutionGovernanceSeverity.HIGH,
                title="Quarantine offline worker",
                description="Worker is offline and should not receive analytics jobs.",
                worker_id=worker_id,
                autonomous_allowed=self.policy.allow_autonomous_worker_quarantine,
                requires_approval=not self.policy.allow_autonomous_worker_quarantine,
            )
            return self._decision(
                decision=ExecutionGovernanceDecisionType.QUARANTINE_WORKER,
                approved=self.policy.allow_autonomous_worker_quarantine,
                severity=ExecutionGovernanceSeverity.HIGH,
                reason="Worker offline.",
                actions=[action],
                worker_id=worker_id,
            )

        if failure >= self.policy.max_worker_failure_rate or health < self.policy.min_worker_health_score:
            action = self._action(
                action_type=ExecutionGovernanceDecisionType.QUARANTINE_WORKER,
                scope=ExecutionGovernanceScope.WORKER,
                severity=ExecutionGovernanceSeverity.HIGH,
                title="Quarantine degraded worker",
                description="Worker failure or health metrics breach policy.",
                worker_id=worker_id,
                autonomous_allowed=self.policy.allow_autonomous_worker_quarantine,
                requires_approval=not self.policy.allow_autonomous_worker_quarantine,
                metadata={"failure_rate": failure, "health_score": health},
            )
            return self._decision(
                decision=ExecutionGovernanceDecisionType.QUARANTINE_WORKER,
                approved=self.policy.allow_autonomous_worker_quarantine,
                severity=ExecutionGovernanceSeverity.HIGH,
                reason="Worker degraded.",
                actions=[action],
                worker_id=worker_id,
            )

        if utilization >= self.policy.max_worker_utilization:
            return self._decision(
                decision=ExecutionGovernanceDecisionType.THROTTLE,
                approved=True,
                severity=ExecutionGovernanceSeverity.MEDIUM,
                reason="Worker utilization above threshold.",
                worker_id=worker_id,
            )

        return self._decision(
            decision=ExecutionGovernanceDecisionType.APPROVE,
            approved=True,
            severity=ExecutionGovernanceSeverity.INFO,
            reason="Worker capacity approved.",
            worker_id=worker_id,
        )

    def evaluate_queue_pressure(
        self,
        pressure_profile: ExecutionPressureProfile,
    ) -> GovernanceDecision:
        actions: List[GovernanceAction] = []

        if pressure_profile.queue_depth >= self.policy.max_queue_depth:
            actions.append(
                self._action(
                    action_type=ExecutionGovernanceDecisionType.THROTTLE,
                    scope=ExecutionGovernanceScope.QUEUE,
                    severity=ExecutionGovernanceSeverity.CRITICAL,
                    title="Throttle analytics queue intake",
                    description="Queue depth exceeds policy maximum.",
                    autonomous_allowed=True,
                    requires_approval=False,
                    metadata={"queue_depth": pressure_profile.queue_depth},
                )
            )

            if self.policy.allow_autonomous_scale_up:
                actions.append(
                    self._action(
                        action_type=ExecutionGovernanceDecisionType.SCALE_UP,
                        scope=ExecutionGovernanceScope.RUNTIME,
                        severity=ExecutionGovernanceSeverity.HIGH,
                        title="Scale up analytics workers",
                        description="Queue pressure requires additional worker capacity.",
                        autonomous_allowed=True,
                        requires_approval=False,
                    )
                )

            return self._decision(
                decision=ExecutionGovernanceDecisionType.THROTTLE,
                approved=True,
                severity=ExecutionGovernanceSeverity.CRITICAL,
                reason="Queue depth exceeds maximum.",
                actions=actions,
            )

        if pressure_profile.queue_pressure >= self.policy.max_queue_pressure:
            return self._decision(
                decision=ExecutionGovernanceDecisionType.SCALE_UP,
                approved=self.policy.allow_autonomous_scale_up,
                severity=ExecutionGovernanceSeverity.HIGH,
                reason="Queue pressure exceeds threshold.",
                actions=[
                    self._action(
                        action_type=ExecutionGovernanceDecisionType.SCALE_UP,
                        scope=ExecutionGovernanceScope.RUNTIME,
                        severity=ExecutionGovernanceSeverity.HIGH,
                        title="Scale up analytics worker pool",
                        description="Queue pressure is high relative to available worker capacity.",
                        autonomous_allowed=self.policy.allow_autonomous_scale_up,
                        requires_approval=not self.policy.allow_autonomous_scale_up,
                    )
                ],
            )

        return self._decision(
            decision=ExecutionGovernanceDecisionType.APPROVE,
            approved=True,
            severity=ExecutionGovernanceSeverity.INFO,
            reason="Queue pressure approved.",
        )

    # =========================================================================
    # Decision Generation
    # =========================================================================

    def generate_governance_decisions(
        self,
        *,
        pressure_profile: ExecutionPressureProfile,
        risk_profile: ExecutionRiskProfile,
        fleet_profile: Optional[Any] = None,
        provider_profiles: Optional[Iterable[Any]] = None,
        tenant_metrics: Optional[Dict[str, Any]] = None,
        universe_metrics: Optional[Dict[str, Any]] = None,
    ) -> List[GovernanceDecision]:
        decisions: List[GovernanceDecision] = []

        if not self.policy.enabled:
            return [
                self._decision(
                    decision=ExecutionGovernanceDecisionType.APPROVE,
                    approved=True,
                    severity=ExecutionGovernanceSeverity.INFO,
                    reason="Governance policy disabled.",
                    risk_profile=risk_profile,
                )
            ]

        if risk_profile.risk_level == ExecutionRiskLevel.CRITICAL.value and self.policy.allow_emergency_stop:
            decisions.append(
                self._decision(
                    decision=ExecutionGovernanceDecisionType.EMERGENCY_STOP,
                    approved=True,
                    severity=ExecutionGovernanceSeverity.CRITICAL,
                    reason="Critical execution risk detected.",
                    risk_profile=risk_profile,
                    actions=[
                        self._action(
                            action_type=ExecutionGovernanceDecisionType.EMERGENCY_STOP,
                            scope=ExecutionGovernanceScope.SYSTEM,
                            severity=ExecutionGovernanceSeverity.CRITICAL,
                            title="Emergency stop analytics execution",
                            description="Critical execution risk detected by autonomous governor.",
                            autonomous_allowed=True,
                            requires_approval=False,
                        )
                    ],
                )
            )
            return decisions

        decisions.append(
            self.evaluate_queue_pressure(pressure_profile)
        )

        for provider in provider_profiles or []:
            decisions.append(self.evaluate_provider_state(provider))

        worker_profiles = list(getattr(fleet_profile, "worker_profiles", []) or [])
        for worker_profile in worker_profiles:
            decisions.append(self.evaluate_worker_capacity(worker_profile))

        if risk_profile.risk_level in {ExecutionRiskLevel.HIGH.value, ExecutionRiskLevel.CRITICAL.value}:
            decisions.append(
                self._decision(
                    decision=ExecutionGovernanceDecisionType.ESCALATE,
                    approved=True,
                    severity=ExecutionGovernanceSeverity.HIGH,
                    reason="Execution risk requires escalation.",
                    risk_profile=risk_profile,
                    actions=[
                        self._action(
                            action_type=ExecutionGovernanceDecisionType.ESCALATE,
                            scope=ExecutionGovernanceScope.SYSTEM,
                            severity=ExecutionGovernanceSeverity.HIGH,
                            title="Escalate analytics execution risk",
                            description="Autonomous governor detected elevated execution risk.",
                            autonomous_allowed=True,
                            requires_approval=False,
                        )
                    ],
                )
            )

        if not decisions:
            decisions.append(
                self._decision(
                    decision=ExecutionGovernanceDecisionType.APPROVE,
                    approved=True,
                    severity=ExecutionGovernanceSeverity.INFO,
                    reason="Runtime execution approved.",
                    risk_profile=risk_profile,
                )
            )

        return decisions

    # =========================================================================
    # Approval API
    # =========================================================================

    def approve_execution(
        self,
        request: ExecutionApprovalRequest,
    ) -> ExecutionApprovalResult:
        if request.risk_score >= 0.90:
            result = ExecutionApprovalResult(
                request_id=request.request_id,
                approved=False,
                decision=ExecutionGovernanceDecisionType.DENY.value,
                reason="Execution risk score exceeds approval threshold.",
                metadata={"risk_score": request.risk_score},
            )
        elif request.priority.upper() == "CRITICAL":
            result = ExecutionApprovalResult(
                request_id=request.request_id,
                approved=True,
                decision=ExecutionGovernanceDecisionType.APPROVE.value,
                reason="Critical-priority execution approved.",
                metadata={"risk_score": request.risk_score},
            )
        elif request.risk_score >= 0.70:
            result = ExecutionApprovalResult(
                request_id=request.request_id,
                approved=False,
                decision=ExecutionGovernanceDecisionType.DEFER.value,
                reason="Execution requires human approval due to elevated risk.",
                metadata={"risk_score": request.risk_score},
            )
        else:
            result = ExecutionApprovalResult(
                request_id=request.request_id,
                approved=True,
                decision=ExecutionGovernanceDecisionType.APPROVE.value,
                reason="Execution approved by autonomous governor.",
                metadata={"risk_score": request.risk_score},
            )

        self.approval_history.append(result)
        return result

    def deny_execution(
        self,
        request: ExecutionApprovalRequest,
        reason: str = "Execution denied by governance policy.",
    ) -> ExecutionApprovalResult:
        result = ExecutionApprovalResult(
            request_id=request.request_id,
            approved=False,
            decision=ExecutionGovernanceDecisionType.DENY.value,
            reason=reason,
            metadata={"requested_action": request.requested_action},
        )
        self.approval_history.append(result)
        return result

    # =========================================================================
    # Control Actions
    # =========================================================================

    def pause_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Paused by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.PAUSE,
            scope=ExecutionGovernanceScope.UNIVERSE,
            severity=ExecutionGovernanceSeverity.MEDIUM,
            title="Pause analytics universe",
            description=reason,
            tenant_id=tenant_id,
            universe_id=universe_id,
            autonomous_allowed=self.policy.allow_autonomous_universe_pause,
            requires_approval=not self.policy.allow_autonomous_universe_pause,
        )
        self.paused_universes[universe_id] = action
        self.action_history.append(action)
        return action

    def resume_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Resumed by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.RESUME,
            scope=ExecutionGovernanceScope.UNIVERSE,
            severity=ExecutionGovernanceSeverity.INFO,
            title="Resume analytics universe",
            description=reason,
            tenant_id=tenant_id,
            universe_id=universe_id,
            autonomous_allowed=True,
            requires_approval=False,
        )
        self.paused_universes.pop(universe_id, None)
        self.action_history.append(action)
        return action

    def throttle_universe(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        reason: str = "Throttled by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.THROTTLE,
            scope=ExecutionGovernanceScope.UNIVERSE,
            severity=ExecutionGovernanceSeverity.MEDIUM,
            title="Throttle analytics universe",
            description=reason,
            tenant_id=tenant_id,
            universe_id=universe_id,
            autonomous_allowed=True,
            requires_approval=False,
        )
        self.throttled_universes[universe_id] = action
        self.action_history.append(action)
        return action

    def reroute_execution(
        self,
        *,
        provider: str,
        reason: str = "Provider rerouted by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.REROUTE,
            scope=ExecutionGovernanceScope.PROVIDER,
            severity=ExecutionGovernanceSeverity.MEDIUM,
            title="Reroute analytics provider execution",
            description=reason,
            provider=provider,
            autonomous_allowed=True,
            requires_approval=False,
        )
        self.action_history.append(action)
        return action

    def disable_provider(
        self,
        *,
        provider: str,
        reason: str = "Provider disabled by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.DISABLE_PROVIDER,
            scope=ExecutionGovernanceScope.PROVIDER,
            severity=ExecutionGovernanceSeverity.HIGH,
            title="Disable analytics provider",
            description=reason,
            provider=provider,
            autonomous_allowed=self.policy.allow_autonomous_provider_disable,
            requires_approval=not self.policy.allow_autonomous_provider_disable,
        )
        self.disabled_providers[provider] = action
        self.action_history.append(action)
        return action

    def quarantine_worker(
        self,
        *,
        worker_id: str,
        reason: str = "Worker quarantined by autonomous execution governor.",
    ) -> GovernanceAction:
        action = self._action(
            action_type=ExecutionGovernanceDecisionType.QUARANTINE_WORKER,
            scope=ExecutionGovernanceScope.WORKER,
            severity=ExecutionGovernanceSeverity.HIGH,
            title="Quarantine analytics worker",
            description=reason,
            worker_id=worker_id,
            autonomous_allowed=self.policy.allow_autonomous_worker_quarantine,
            requires_approval=not self.policy.allow_autonomous_worker_quarantine,
        )
        self.quarantined_workers[worker_id] = action
        self.action_history.append(action)
        return action

    # =========================================================================
    # Summary / State
    # =========================================================================

    def governance_summary(self) -> Dict[str, Any]:
        decision_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}

        for decision in self.decision_history:
            decision_counts[decision.decision] = decision_counts.get(decision.decision, 0) + 1
            severity_counts[decision.severity] = severity_counts.get(decision.severity, 0) + 1

        return {
            "policy_id": self.policy.policy_id,
            "policy_enabled": self.policy.enabled,
            "evaluations": len(self.evaluation_history),
            "decisions": len(self.decision_history),
            "actions": len(self.action_history),
            "approvals": len(self.approval_history),
            "paused_universes": len(self.paused_universes),
            "throttled_universes": len(self.throttled_universes),
            "disabled_providers": len(self.disabled_providers),
            "quarantined_workers": len(self.quarantined_workers),
            "decision_counts": decision_counts,
            "severity_counts": severity_counts,
            "generated_at": utc_now_iso(),
        }

    def export_state(self) -> Dict[str, Any]:
        return {
            "policy": asdict(self.policy),
            "summary": self.governance_summary(),
            "paused_universes": {k: asdict(v) for k, v in self.paused_universes.items()},
            "throttled_universes": {k: asdict(v) for k, v in self.throttled_universes.items()},
            "disabled_providers": {k: asdict(v) for k, v in self.disabled_providers.items()},
            "quarantined_workers": {k: asdict(v) for k, v in self.quarantined_workers.items()},
            "recent_decisions": [asdict(d) for d in self.decision_history[-100:]],
            "recent_actions": [asdict(a) for a in self.action_history[-100:]],
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _risk_level(self, risk_score: float) -> str:
        risk_score = clamp(risk_score)

        if risk_score >= 0.90:
            return ExecutionRiskLevel.CRITICAL.value
        if risk_score >= 0.70:
            return ExecutionRiskLevel.HIGH.value
        if risk_score >= 0.40:
            return ExecutionRiskLevel.MEDIUM.value
        if risk_score >= 0.10:
            return ExecutionRiskLevel.LOW.value
        return ExecutionRiskLevel.NONE.value

    def _decision(
        self,
        *,
        decision: ExecutionGovernanceDecisionType,
        approved: bool,
        severity: ExecutionGovernanceSeverity,
        reason: str,
        risk_profile: Optional[ExecutionRiskProfile] = None,
        actions: Optional[List[GovernanceAction]] = None,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        provider: Optional[str] = None,
        worker_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GovernanceDecision:
        return GovernanceDecision(
            decision_id=f"egdec_{uuid.uuid4().hex}",
            decision=decision.value,
            approved=approved,
            severity=severity.value,
            reason=reason,
            risk_profile=risk_profile,
            actions=actions or [],
            tenant_id=tenant_id,
            universe_id=universe_id,
            provider=provider,
            worker_id=worker_id,
            metadata=metadata or {},
        )

    def _action(
        self,
        *,
        action_type: ExecutionGovernanceDecisionType,
        scope: ExecutionGovernanceScope,
        severity: ExecutionGovernanceSeverity,
        title: str,
        description: str,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        provider: Optional[str] = None,
        worker_id: Optional[str] = None,
        priority: str = "NORMAL",
        autonomous_allowed: bool = False,
        requires_approval: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GovernanceAction:
        return GovernanceAction(
            action_id=f"egact_{uuid.uuid4().hex}",
            action_type=action_type.value,
            scope=scope.value,
            severity=severity.value,
            title=title,
            description=description,
            tenant_id=tenant_id,
            universe_id=universe_id,
            provider=provider,
            worker_id=worker_id,
            priority=priority,
            autonomous_allowed=autonomous_allowed,
            requires_approval=requires_approval,
            metadata=metadata or {},
        )

    def _trim_history(self, max_items: int = 5000) -> None:
        if len(self.evaluation_history) > max_items:
            self.evaluation_history = self.evaluation_history[-max_items:]
        if len(self.decision_history) > max_items:
            self.decision_history = self.decision_history[-max_items:]
        if len(self.action_history) > max_items:
            self.action_history = self.action_history[-max_items:]


def create_autonomous_execution_governor(
    *,
    policy: Optional[GovernancePolicy] = None,
) -> AutonomousExecutionGovernor:
    return AutonomousExecutionGovernor(policy=policy)