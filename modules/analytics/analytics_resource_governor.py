"""
modules/analytics/analytics_resource_governor.py
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Enums
# =============================================================================

class GovernanceDecisionType(str, Enum):
    ALLOW = "ALLOW"
    DEFER = "DEFER"
    THROTTLE = "THROTTLE"
    REJECT = "REJECT"
    PAUSE = "PAUSE"
    ESCALATE = "ESCALATE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class GovernanceSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GovernanceViolationType(str, Enum):
    TENANT_QUOTA = "TENANT_QUOTA"
    PROVIDER_BUDGET = "PROVIDER_BUDGET"
    QUEUE_DEPTH = "QUEUE_DEPTH"
    WORKER_CAPACITY = "WORKER_CAPACITY"
    SYSTEM_HEALTH = "SYSTEM_HEALTH"
    COST_LIMIT = "COST_LIMIT"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    UNIVERSE_LIMIT = "UNIVERSE_LIMIT"


# =============================================================================
# Models
# =============================================================================

@dataclass
class ResourceBudget:
    max_queue_depth: int = 50000
    max_running_jobs: int = 10000
    max_worker_utilization: float = 0.90
    max_failed_job_rate: float = 0.25
    max_cost_per_hour: float = 1000.0
    emergency_stop_enabled: bool = True


@dataclass
class ProviderBudget:
    provider_name: str
    daily_limit: int
    hourly_limit: int
    current_daily_usage: int = 0
    current_hourly_usage: int = 0
    throttle_threshold: float = 0.90
    enabled: bool = True


@dataclass
class TenantQuota:
    tenant_id: str
    max_jobs: int = 5000
    max_running_jobs: int = 500
    max_universes: int = 100
    max_hourly_submissions: int = 1000
    current_jobs: int = 0
    current_running_jobs: int = 0
    current_hourly_submissions: int = 0
    enabled: bool = True


@dataclass
class RuntimeCapacity:
    workers_online: int = 0
    workers_total: int = 0
    queue_depth: int = 0
    active_leases: int = 0
    active_jobs: int = 0
    available_capacity: int = 0
    worker_utilization: float = 0.0
    failed_job_rate: float = 0.0


@dataclass
class GovernanceViolation:
    violation_id: str
    violation_type: str
    severity: str
    message: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceDecision:
    decision: str
    approved: bool
    reason: str
    generated_at: str = field(default_factory=utc_now_iso)
    violations: List[GovernanceViolation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceMetrics:
    total_decisions: int = 0
    allow_count: int = 0
    defer_count: int = 0
    throttle_count: int = 0
    reject_count: int = 0
    pause_count: int = 0
    escalate_count: int = 0
    emergency_stop_count: int = 0
    violations_detected: int = 0
    generated_at: str = field(default_factory=utc_now_iso)


# =============================================================================
# Governor
# =============================================================================

class AnalyticsResourceGovernor:
    """
    Analytics governance and admission-control layer.

    Responsibilities:
        - Tenant quotas
        - Provider limits
        - Runtime saturation protection
        - Queue governance
        - Cost governance
        - Emergency stop controls
        - Analytics admission decisions
        - Multi-tenant fairness
    """

    def __init__(
        self,
        resource_budget: Optional[ResourceBudget] = None,
    ):
        self.resource_budget = (
            resource_budget
            or ResourceBudget()
        )

        self.provider_budgets: Dict[
            str,
            ProviderBudget,
        ] = {}

        self.tenant_quotas: Dict[
            str,
            TenantQuota,
        ] = {}

        self.metrics = GovernanceMetrics()

        self.circuit_breaker_enabled = False

    # =========================================================================
    # Configuration
    # =========================================================================

    def register_provider_budget(
        self,
        provider_budget: ProviderBudget,
    ) -> None:
        self.provider_budgets[
            provider_budget.provider_name
        ] = provider_budget

    def register_tenant_quota(
        self,
        tenant_quota: TenantQuota,
    ) -> None:
        self.tenant_quotas[
            tenant_quota.tenant_id
        ] = tenant_quota

    # =========================================================================
    # Job Submission Governance
    # =========================================================================

    def evaluate_job_submission(
        self,
        tenant_id: str,
        provider: Optional[str],
        runtime_capacity: RuntimeCapacity,
    ) -> GovernanceDecision:

        violations: List[
            GovernanceViolation
        ] = []

        quota = self.tenant_quotas.get(
            tenant_id
        )

        if quota:

            if not quota.enabled:

                violations.append(
                    self._violation(
                        GovernanceViolationType.TENANT_QUOTA,
                        GovernanceSeverity.HIGH,
                        "Tenant quota disabled.",
                    )
                )

            if (
                quota.current_jobs
                >= quota.max_jobs
            ):
                violations.append(
                    self._violation(
                        GovernanceViolationType.TENANT_QUOTA,
                        GovernanceSeverity.HIGH,
                        "Tenant job quota exceeded.",
                    )
                )

        provider_violation = (
            self._check_provider(
                provider
            )
        )

        if provider_violation:
            violations.append(
                provider_violation
            )

        capacity_violation = (
            self._check_runtime_capacity(
                runtime_capacity
            )
        )

        if capacity_violation:
            violations.append(
                capacity_violation
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Schedule Governance
    # =========================================================================

    def evaluate_schedule_execution(
        self,
        tenant_id: str,
        runtime_capacity: RuntimeCapacity,
    ) -> GovernanceDecision:

        violations = []

        capacity_violation = (
            self._check_runtime_capacity(
                runtime_capacity
            )
        )

        if capacity_violation:
            violations.append(
                capacity_violation
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Runtime Dispatch Governance
    # =========================================================================

    def evaluate_runtime_dispatch(
        self,
        runtime_capacity: RuntimeCapacity,
    ) -> GovernanceDecision:

        violations = []

        if (
            runtime_capacity.worker_utilization
            >= self.resource_budget.max_worker_utilization
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.WORKER_CAPACITY,
                    GovernanceSeverity.MEDIUM,
                    "Worker utilization threshold exceeded.",
                )
            )

        if (
            runtime_capacity.queue_depth
            >= self.resource_budget.max_queue_depth
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.QUEUE_DEPTH,
                    GovernanceSeverity.HIGH,
                    "Queue depth threshold exceeded.",
                )
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Universe Refresh Governance
    # =========================================================================

    def evaluate_universe_refresh(
        self,
        tenant_id: str,
        universe_count: int,
    ) -> GovernanceDecision:

        violations = []

        quota = self.tenant_quotas.get(
            tenant_id
        )

        if quota:

            if (
                universe_count
                > quota.max_universes
            ):
                violations.append(
                    self._violation(
                        GovernanceViolationType.UNIVERSE_LIMIT,
                        GovernanceSeverity.MEDIUM,
                        "Universe quota exceeded.",
                    )
                )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Provider Governance
    # =========================================================================

    def evaluate_provider_consumption(
        self,
        provider_name: str,
    ) -> GovernanceDecision:

        violations = []

        provider = (
            self.provider_budgets.get(
                provider_name
            )
        )

        if not provider:
            return GovernanceDecision(
                decision=GovernanceDecisionType.ALLOW.value,
                approved=True,
                reason="No provider governance configured.",
            )

        daily_pct = (
            provider.current_daily_usage
            / provider.daily_limit
        )

        hourly_pct = (
            provider.current_hourly_usage
            / provider.hourly_limit
        )

        if (
            daily_pct
            >= provider.throttle_threshold
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.PROVIDER_BUDGET,
                    GovernanceSeverity.MEDIUM,
                    "Daily provider budget approaching limit.",
                )
            )

        if (
            hourly_pct
            >= provider.throttle_threshold
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.PROVIDER_BUDGET,
                    GovernanceSeverity.MEDIUM,
                    "Hourly provider budget approaching limit.",
                )
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Tenant Governance
    # =========================================================================

    def evaluate_tenant_consumption(
        self,
        tenant_id: str,
    ) -> GovernanceDecision:

        quota = self.tenant_quotas.get(
            tenant_id
        )

        if not quota:
            return GovernanceDecision(
                decision=GovernanceDecisionType.ALLOW.value,
                approved=True,
                reason="No quota configured.",
            )

        violations = []

        if (
            quota.current_hourly_submissions
            >= quota.max_hourly_submissions
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.TENANT_QUOTA,
                    GovernanceSeverity.MEDIUM,
                    "Hourly submission limit exceeded.",
                )
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # System Health Governance
    # =========================================================================

    def evaluate_system_health(
        self,
        runtime_capacity: RuntimeCapacity,
    ) -> GovernanceDecision:

        violations = []

        if (
            runtime_capacity.failed_job_rate
            >= self.resource_budget.max_failed_job_rate
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.SYSTEM_HEALTH,
                    GovernanceSeverity.HIGH,
                    "Failed job rate exceeded threshold.",
                )
            )

        if (
            runtime_capacity.workers_online
            == 0
        ):
            violations.append(
                self._violation(
                    GovernanceViolationType.SYSTEM_HEALTH,
                    GovernanceSeverity.CRITICAL,
                    "No workers online.",
                )
            )

        return self._build_decision(
            violations
        )

    # =========================================================================
    # Emergency Controls
    # =========================================================================

    def enable_emergency_stop(
        self,
    ) -> None:
        self.circuit_breaker_enabled = True

    def disable_emergency_stop(
        self,
    ) -> None:
        self.circuit_breaker_enabled = False

    def emergency_stop_decision(
        self,
    ) -> GovernanceDecision:

        self.metrics.emergency_stop_count += 1

        return GovernanceDecision(
            decision=GovernanceDecisionType.EMERGENCY_STOP.value,
            approved=False,
            reason="Emergency stop activated.",
        )

    # =========================================================================
    # Scaling Recommendations
    # =========================================================================

    def scaling_recommendation(
        self,
        runtime_capacity: RuntimeCapacity,
    ) -> Dict[str, Any]:

        recommendation = "HOLD"

        if (
            runtime_capacity.worker_utilization
            > 0.85
        ):
            recommendation = "SCALE_UP"

        elif (
            runtime_capacity.worker_utilization
            < 0.25
        ):
            recommendation = "SCALE_DOWN"

        return {
            "recommendation":
                recommendation,
            "worker_utilization":
                runtime_capacity.worker_utilization,
            "queue_depth":
                runtime_capacity.queue_depth,
            "generated_at":
                utc_now_iso(),
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _check_provider(
        self,
        provider_name: Optional[str],
    ) -> Optional[
        GovernanceViolation
    ]:

        if not provider_name:
            return None

        provider = (
            self.provider_budgets.get(
                provider_name
            )
        )

        if not provider:
            return None

        if not provider.enabled:
            return self._violation(
                GovernanceViolationType.PROVIDER_BUDGET,
                GovernanceSeverity.HIGH,
                f"{provider_name} disabled.",
            )

        if (
            provider.current_hourly_usage
            >= provider.hourly_limit
        ):
            return self._violation(
                GovernanceViolationType.PROVIDER_BUDGET,
                GovernanceSeverity.HIGH,
                "Hourly provider limit exceeded.",
            )

        return None

    def _check_runtime_capacity(
        self,
        runtime_capacity: RuntimeCapacity,
    ) -> Optional[
        GovernanceViolation
    ]:

        if (
            runtime_capacity.queue_depth
            >= self.resource_budget.max_queue_depth
        ):
            return self._violation(
                GovernanceViolationType.QUEUE_DEPTH,
                GovernanceSeverity.HIGH,
                "Queue depth exceeded.",
            )

        return None

    def _build_decision(
        self,
        violations: List[
            GovernanceViolation
        ],
    ) -> GovernanceDecision:

        self.metrics.total_decisions += 1

        if self.circuit_breaker_enabled:

            self.metrics.emergency_stop_count += 1

            return GovernanceDecision(
                decision=
                    GovernanceDecisionType
                    .EMERGENCY_STOP.value,
                approved=False,
                reason="Circuit breaker enabled.",
                violations=violations,
            )

        if not violations:

            self.metrics.allow_count += 1

            return GovernanceDecision(
                decision=
                    GovernanceDecisionType
                    .ALLOW.value,
                approved=True,
                reason="Approved.",
            )

        highest = max(
            violations,
            key=lambda v: {
                GovernanceSeverity.INFO.value: 1,
                GovernanceSeverity.LOW.value: 2,
                GovernanceSeverity.MEDIUM.value: 3,
                GovernanceSeverity.HIGH.value: 4,
                GovernanceSeverity.CRITICAL.value: 5,
            }[v.severity],
        )

        self.metrics.violations_detected += (
            len(violations)
        )

        if (
            highest.severity
            == GovernanceSeverity.CRITICAL.value
        ):
            self.metrics.reject_count += 1

            return GovernanceDecision(
                decision=
                    GovernanceDecisionType
                    .REJECT.value,
                approved=False,
                reason=highest.message,
                violations=violations,
            )

        if (
            highest.severity
            == GovernanceSeverity.HIGH.value
        ):
            self.metrics.throttle_count += 1

            return GovernanceDecision(
                decision=
                    GovernanceDecisionType
                    .THROTTLE.value,
                approved=False,
                reason=highest.message,
                violations=violations,
            )

        self.metrics.defer_count += 1

        return GovernanceDecision(
            decision=
                GovernanceDecisionType
                .DEFER.value,
            approved=False,
            reason=highest.message,
            violations=violations,
        )

    def _violation(
        self,
        violation_type: str,
        severity: str,
        message: str,
    ) -> GovernanceViolation:

        return GovernanceViolation(
            violation_id=f"gov_{hash((violation_type, message, utc_now_iso()))}",
            violation_type=violation_type,
            severity=severity,
            message=message,
        )

    # =========================================================================
    # Metrics
    # =========================================================================

    def governance_metrics(
        self,
    ) -> Dict[str, Any]:

        return asdict(self.metrics)