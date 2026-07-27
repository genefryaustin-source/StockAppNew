"""
modules/analytics/tenant_universe_intelligence_engine.py
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence


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


def mean_or_zero(values: Sequence[float]) -> float:
    cleaned = [float(v) for v in values if v is not None]
    return statistics.mean(cleaned) if cleaned else 0.0


class IntelligenceSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TenantBehaviorState(str, Enum):
    NORMAL = "NORMAL"
    HIGH_CONSUMPTION = "HIGH_CONSUMPTION"
    COST_HEAVY = "COST_HEAVY"
    QUEUE_PRESSURED = "QUEUE_PRESSURED"
    DEGRADED = "DEGRADED"
    SLA_RISK = "SLA_RISK"


class UniverseBehaviorState(str, Enum):
    NORMAL = "NORMAL"
    OVER_REFRESHED = "OVER_REFRESHED"
    UNDER_REFRESHED = "UNDER_REFRESHED"
    HIGH_COST = "HIGH_COST"
    LOW_YIELD = "LOW_YIELD"
    SLOW_EXECUTION = "SLOW_EXECUTION"
    SLA_RISK = "SLA_RISK"


class IntelligenceRecommendationType(str, Enum):
    INCREASE_REFRESH = "INCREASE_REFRESH"
    DECREASE_REFRESH = "DECREASE_REFRESH"
    SPLIT_UNIVERSE = "SPLIT_UNIVERSE"
    MERGE_UNIVERSES = "MERGE_UNIVERSES"
    PRIORITIZE_TENANT = "PRIORITIZE_TENANT"
    THROTTLE_TENANT = "THROTTLE_TENANT"
    REDUCE_COST = "REDUCE_COST"
    PROTECT_SLA = "PROTECT_SLA"
    REBALANCE_UNIVERSES = "REBALANCE_UNIVERSES"
    REVIEW_POLICY = "REVIEW_POLICY"


@dataclass(frozen=True)
class TenantTelemetrySample:
    tenant_id: str
    jobs_submitted: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    queue_depth: int = 0
    active_jobs: int = 0
    total_cost_usd: float = 0.0
    provider_calls: int = 0
    avg_runtime_seconds: float = 0.0
    sla_breaches: int = 0
    universes_active: int = 0
    universes_deferred: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class UniverseTelemetrySample:
    tenant_id: str
    universe_id: str
    universe_name: str = ""
    jobs_submitted: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    symbols_processed: int = 0
    analytics_generated: int = 0
    refresh_interval_minutes: int = 60
    avg_runtime_seconds: float = 0.0
    p95_runtime_seconds: float = 0.0
    total_cost_usd: float = 0.0
    provider_calls: int = 0
    stale_symbols: int = 0
    sla_breaches: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class TenantIntelligenceProfile:
    tenant_id: str
    state: str
    jobs_submitted: int
    jobs_completed: int
    jobs_failed: int
    completion_rate: float
    failure_rate: float
    queue_pressure: float
    cost_per_job: float
    provider_calls_per_job: float
    avg_runtime_seconds: float
    sla_breach_rate: float
    universes_active: int
    universes_deferred: int
    consumption_score: float
    efficiency_score: float
    reliability_score: float
    risk_score: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UniverseIntelligenceProfile:
    tenant_id: str
    universe_id: str
    universe_name: str
    state: str
    jobs_submitted: int
    jobs_completed: int
    jobs_failed: int
    completion_rate: float
    failure_rate: float
    symbols_processed: int
    analytics_generated: int
    analytics_yield: float
    refresh_interval_minutes: int
    avg_runtime_seconds: float
    p95_runtime_seconds: float
    total_cost_usd: float
    cost_per_analytic: float
    provider_calls_per_analytic: float
    stale_symbol_rate: float
    sla_breach_rate: float
    refresh_efficiency_score: float
    execution_efficiency_score: float
    cost_efficiency_score: float
    risk_score: float
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TenantUniverseRecommendation:
    recommendation_id: str
    recommendation_type: str
    severity: str
    title: str
    description: str
    tenant_id: Optional[str] = None
    universe_id: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class TenantUniverseIntelligenceReport:
    report_id: str
    tenant_profiles: List[TenantIntelligenceProfile]
    universe_profiles: List[UniverseIntelligenceProfile]
    recommendations: List[TenantUniverseRecommendation]
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "tenant_profiles": [asdict(p) for p in self.tenant_profiles],
            "universe_profiles": [asdict(p) for p in self.universe_profiles],
            "recommendations": [asdict(r) for r in self.recommendations],
            "generated_at": self.generated_at,
        }


class TenantUniverseIntelligenceEngine:
    """
    Learns tenant and universe behavior patterns.

    Outputs:
        - tenant consumption profiles
        - universe efficiency profiles
        - SLA/cost/risk recommendations
        - refresh cadence intelligence
        - split/merge universe recommendations
    """

    def __init__(
        self,
        *,
        high_queue_pressure_threshold: float = 0.75,
        high_failure_rate_threshold: float = 0.10,
        high_cost_per_job_threshold: float = 1.00,
        low_analytics_yield_threshold: float = 0.25,
        high_stale_symbol_rate_threshold: float = 0.30,
        sla_breach_rate_threshold: float = 0.05,
        slow_runtime_seconds_threshold: float = 300.0,
    ) -> None:
        self.high_queue_pressure_threshold = clamp(high_queue_pressure_threshold)
        self.high_failure_rate_threshold = clamp(high_failure_rate_threshold)
        self.high_cost_per_job_threshold = max(0.0, float(high_cost_per_job_threshold))
        self.low_analytics_yield_threshold = clamp(low_analytics_yield_threshold)
        self.high_stale_symbol_rate_threshold = clamp(high_stale_symbol_rate_threshold)
        self.sla_breach_rate_threshold = clamp(sla_breach_rate_threshold)
        self.slow_runtime_seconds_threshold = max(1.0, float(slow_runtime_seconds_threshold))

        self.tenant_samples: List[TenantTelemetrySample] = []
        self.universe_samples: List[UniverseTelemetrySample] = []

        self.tenant_profiles: Dict[str, TenantIntelligenceProfile] = {}
        self.universe_profiles: Dict[str, UniverseIntelligenceProfile] = {}
        self.recommendation_history: List[TenantUniverseRecommendation] = []
        self.report_history: List[TenantUniverseIntelligenceReport] = []

    def collect_tenant_samples(
        self,
        samples: Iterable[TenantTelemetrySample],
        *,
        max_history: int = 50000,
    ) -> List[TenantTelemetrySample]:
        collected = list(samples)
        self.tenant_samples.extend(collected)
        if len(self.tenant_samples) > max_history:
            self.tenant_samples = self.tenant_samples[-max_history:]
        return collected

    def collect_universe_samples(
        self,
        samples: Iterable[UniverseTelemetrySample],
        *,
        max_history: int = 100000,
    ) -> List[UniverseTelemetrySample]:
        collected = list(samples)
        self.universe_samples.extend(collected)
        if len(self.universe_samples) > max_history:
            self.universe_samples = self.universe_samples[-max_history:]
        return collected

    def build_tenant_profile(
        self,
        tenant_id: str,
        samples: Optional[Iterable[TenantTelemetrySample]] = None,
    ) -> Optional[TenantIntelligenceProfile]:
        source = list(samples) if samples is not None else self.tenant_samples
        tenant_samples = [s for s in source if s.tenant_id == tenant_id]

        if not tenant_samples:
            return None

        jobs_submitted = sum(s.jobs_submitted for s in tenant_samples)
        jobs_completed = sum(s.jobs_completed for s in tenant_samples)
        jobs_failed = sum(s.jobs_failed for s in tenant_samples)
        queue_depth = sum(s.queue_depth for s in tenant_samples)
        active_jobs = sum(s.active_jobs for s in tenant_samples)
        total_cost = sum(s.total_cost_usd for s in tenant_samples)
        provider_calls = sum(s.provider_calls for s in tenant_samples)
        sla_breaches = sum(s.sla_breaches for s in tenant_samples)

        avg_runtime = mean_or_zero([s.avg_runtime_seconds for s in tenant_samples])
        universes_active = max([s.universes_active for s in tenant_samples] or [0])
        universes_deferred = max([s.universes_deferred for s in tenant_samples] or [0])

        finished = jobs_completed + jobs_failed
        completion_rate = clamp(safe_divide(jobs_completed, finished, 1.0))
        failure_rate = clamp(safe_divide(jobs_failed, finished, 0.0))
        queue_pressure = clamp(safe_divide(queue_depth, max(1, jobs_submitted + active_jobs)))
        cost_per_job = safe_divide(total_cost, max(1, jobs_submitted))
        provider_calls_per_job = safe_divide(provider_calls, max(1, jobs_submitted))
        sla_breach_rate = clamp(safe_divide(sla_breaches, max(1, jobs_submitted)))

        consumption_score = clamp(
            safe_divide(jobs_submitted + active_jobs + queue_depth, max(1, jobs_submitted + active_jobs + queue_depth + 1000))
        )
        reliability_score = clamp(completion_rate - failure_rate)
        cost_efficiency = clamp(1.0 - safe_divide(cost_per_job, max(0.0001, self.high_cost_per_job_threshold)))
        runtime_efficiency = clamp(1.0 - safe_divide(avg_runtime, max(avg_runtime, self.slow_runtime_seconds_threshold)))
        efficiency_score = clamp((reliability_score * 0.45) + (cost_efficiency * 0.30) + (runtime_efficiency * 0.25))

        risk_score = clamp(
            (queue_pressure * 0.30)
            + (failure_rate * 0.25)
            + (sla_breach_rate * 0.25)
            + ((1.0 - efficiency_score) * 0.20)
        )

        state = self._classify_tenant_state(
            queue_pressure=queue_pressure,
            failure_rate=failure_rate,
            cost_per_job=cost_per_job,
            sla_breach_rate=sla_breach_rate,
        )

        profile = TenantIntelligenceProfile(
            tenant_id=tenant_id,
            state=state,
            jobs_submitted=jobs_submitted,
            jobs_completed=jobs_completed,
            jobs_failed=jobs_failed,
            completion_rate=round(completion_rate, 4),
            failure_rate=round(failure_rate, 4),
            queue_pressure=round(queue_pressure, 4),
            cost_per_job=round(cost_per_job, 6),
            provider_calls_per_job=round(provider_calls_per_job, 4),
            avg_runtime_seconds=round(avg_runtime, 4),
            sla_breach_rate=round(sla_breach_rate, 4),
            universes_active=universes_active,
            universes_deferred=universes_deferred,
            consumption_score=round(consumption_score, 4),
            efficiency_score=round(efficiency_score, 4),
            reliability_score=round(reliability_score, 4),
            risk_score=round(risk_score, 4),
            metadata={"sample_count": len(tenant_samples)},
        )

        self.tenant_profiles[tenant_id] = profile
        return profile

    def build_universe_profile(
        self,
        tenant_id: str,
        universe_id: str,
        samples: Optional[Iterable[UniverseTelemetrySample]] = None,
    ) -> Optional[UniverseIntelligenceProfile]:
        source = list(samples) if samples is not None else self.universe_samples
        universe_samples = [
            s for s in source
            if s.tenant_id == tenant_id and s.universe_id == universe_id
        ]

        if not universe_samples:
            return None

        universe_name = universe_samples[-1].universe_name or universe_id
        jobs_submitted = sum(s.jobs_submitted for s in universe_samples)
        jobs_completed = sum(s.jobs_completed for s in universe_samples)
        jobs_failed = sum(s.jobs_failed for s in universe_samples)
        symbols_processed = sum(s.symbols_processed for s in universe_samples)
        analytics_generated = sum(s.analytics_generated for s in universe_samples)
        stale_symbols = sum(s.stale_symbols for s in universe_samples)
        sla_breaches = sum(s.sla_breaches for s in universe_samples)
        total_cost = sum(s.total_cost_usd for s in universe_samples)
        provider_calls = sum(s.provider_calls for s in universe_samples)

        refresh_interval = int(mean_or_zero([s.refresh_interval_minutes for s in universe_samples]) or 60)
        avg_runtime = mean_or_zero([s.avg_runtime_seconds for s in universe_samples])
        p95_runtime = max([s.p95_runtime_seconds for s in universe_samples] or [0.0])

        finished = jobs_completed + jobs_failed
        completion_rate = clamp(safe_divide(jobs_completed, finished, 1.0))
        failure_rate = clamp(safe_divide(jobs_failed, finished, 0.0))
        analytics_yield = clamp(safe_divide(analytics_generated, max(1, symbols_processed)))
        cost_per_analytic = safe_divide(total_cost, max(1, analytics_generated))
        provider_calls_per_analytic = safe_divide(provider_calls, max(1, analytics_generated))
        stale_symbol_rate = clamp(safe_divide(stale_symbols, max(1, symbols_processed)))
        sla_breach_rate = clamp(safe_divide(sla_breaches, max(1, jobs_submitted)))

        refresh_efficiency = clamp(
            (analytics_yield * 0.50)
            + ((1.0 - stale_symbol_rate) * 0.30)
            + (completion_rate * 0.20)
        )
        execution_efficiency = clamp(
            (completion_rate * 0.45)
            + ((1.0 - failure_rate) * 0.30)
            + ((1.0 - clamp(safe_divide(avg_runtime, self.slow_runtime_seconds_threshold))) * 0.25)
        )
        cost_efficiency = clamp(1.0 - safe_divide(cost_per_analytic, max(0.0001, self.high_cost_per_job_threshold)))
        risk_score = clamp(
            (failure_rate * 0.25)
            + (sla_breach_rate * 0.30)
            + (stale_symbol_rate * 0.20)
            + ((1.0 - refresh_efficiency) * 0.15)
            + ((1.0 - cost_efficiency) * 0.10)
        )

        state = self._classify_universe_state(
            analytics_yield=analytics_yield,
            stale_symbol_rate=stale_symbol_rate,
            cost_per_analytic=cost_per_analytic,
            avg_runtime_seconds=avg_runtime,
            sla_breach_rate=sla_breach_rate,
            refresh_interval_minutes=refresh_interval,
        )

        profile = UniverseIntelligenceProfile(
            tenant_id=tenant_id,
            universe_id=universe_id,
            universe_name=universe_name,
            state=state,
            jobs_submitted=jobs_submitted,
            jobs_completed=jobs_completed,
            jobs_failed=jobs_failed,
            completion_rate=round(completion_rate, 4),
            failure_rate=round(failure_rate, 4),
            symbols_processed=symbols_processed,
            analytics_generated=analytics_generated,
            analytics_yield=round(analytics_yield, 4),
            refresh_interval_minutes=refresh_interval,
            avg_runtime_seconds=round(avg_runtime, 4),
            p95_runtime_seconds=round(p95_runtime, 4),
            total_cost_usd=round(total_cost, 6),
            cost_per_analytic=round(cost_per_analytic, 6),
            provider_calls_per_analytic=round(provider_calls_per_analytic, 4),
            stale_symbol_rate=round(stale_symbol_rate, 4),
            sla_breach_rate=round(sla_breach_rate, 4),
            refresh_efficiency_score=round(refresh_efficiency, 4),
            execution_efficiency_score=round(execution_efficiency, 4),
            cost_efficiency_score=round(cost_efficiency, 4),
            risk_score=round(risk_score, 4),
            metadata={"sample_count": len(universe_samples)},
        )

        self.universe_profiles[self._universe_key(tenant_id, universe_id)] = profile
        return profile

    def analyze(
        self,
        *,
        tenant_samples: Optional[Iterable[TenantTelemetrySample]] = None,
        universe_samples: Optional[Iterable[UniverseTelemetrySample]] = None,
    ) -> TenantUniverseIntelligenceReport:
        if tenant_samples is not None:
            self.collect_tenant_samples(tenant_samples)

        if universe_samples is not None:
            self.collect_universe_samples(universe_samples)

        tenant_ids = sorted({s.tenant_id for s in self.tenant_samples})
        universe_keys = sorted({self._universe_key(s.tenant_id, s.universe_id) for s in self.universe_samples})

        tenant_profiles = [
            profile
            for tenant_id in tenant_ids
            for profile in [self.build_tenant_profile(tenant_id)]
            if profile is not None
        ]

        universe_profiles = []
        for key in universe_keys:
            tenant_id, universe_id = key.split("::", 1)
            profile = self.build_universe_profile(tenant_id, universe_id)
            if profile:
                universe_profiles.append(profile)

        recommendations = self.generate_recommendations(
            tenant_profiles=tenant_profiles,
            universe_profiles=universe_profiles,
        )

        report = TenantUniverseIntelligenceReport(
            report_id=f"tuintel_{uuid.uuid4().hex}",
            tenant_profiles=tenant_profiles,
            universe_profiles=universe_profiles,
            recommendations=recommendations,
        )

        self.report_history.append(report)
        if len(self.report_history) > 1000:
            self.report_history = self.report_history[-1000:]

        return report

    def generate_recommendations(
        self,
        *,
        tenant_profiles: Iterable[TenantIntelligenceProfile],
        universe_profiles: Iterable[UniverseIntelligenceProfile],
    ) -> List[TenantUniverseRecommendation]:
        recommendations: List[TenantUniverseRecommendation] = []

        for tenant in tenant_profiles:
            if tenant.sla_breach_rate >= self.sla_breach_rate_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.PROTECT_SLA,
                        severity=IntelligenceSeverity.HIGH,
                        title="Protect tenant SLA",
                        description="Tenant SLA breach rate exceeds threshold.",
                        tenant_id=tenant.tenant_id,
                        confidence=0.92,
                        metadata={"sla_breach_rate": tenant.sla_breach_rate},
                    )
                )

            if tenant.queue_pressure >= self.high_queue_pressure_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.PRIORITIZE_TENANT,
                        severity=IntelligenceSeverity.MEDIUM,
                        title="Prioritize tenant workload",
                        description="Tenant queue pressure is elevated.",
                        tenant_id=tenant.tenant_id,
                        confidence=0.84,
                        metadata={"queue_pressure": tenant.queue_pressure},
                    )
                )

            if tenant.cost_per_job >= self.high_cost_per_job_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.REDUCE_COST,
                        severity=IntelligenceSeverity.MEDIUM,
                        title="Reduce tenant analytics cost",
                        description="Tenant cost per job exceeds configured threshold.",
                        tenant_id=tenant.tenant_id,
                        confidence=0.80,
                        metadata={"cost_per_job": tenant.cost_per_job},
                    )
                )

        for universe in universe_profiles:
            if universe.analytics_yield <= self.low_analytics_yield_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.DECREASE_REFRESH,
                        severity=IntelligenceSeverity.MEDIUM,
                        title="Decrease refresh cadence",
                        description="Universe analytics yield is low relative to symbols processed.",
                        tenant_id=universe.tenant_id,
                        universe_id=universe.universe_id,
                        confidence=0.82,
                        metadata={"analytics_yield": universe.analytics_yield},
                    )
                )

            if universe.stale_symbol_rate >= self.high_stale_symbol_rate_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.INCREASE_REFRESH,
                        severity=IntelligenceSeverity.MEDIUM,
                        title="Increase refresh cadence",
                        description="Universe stale-symbol rate is elevated.",
                        tenant_id=universe.tenant_id,
                        universe_id=universe.universe_id,
                        confidence=0.78,
                        metadata={"stale_symbol_rate": universe.stale_symbol_rate},
                    )
                )

            if universe.cost_per_analytic >= self.high_cost_per_job_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.REDUCE_COST,
                        severity=IntelligenceSeverity.MEDIUM,
                        title="Reduce universe analytics cost",
                        description="Universe cost per analytic exceeds configured threshold.",
                        tenant_id=universe.tenant_id,
                        universe_id=universe.universe_id,
                        confidence=0.80,
                        metadata={"cost_per_analytic": universe.cost_per_analytic},
                    )
                )

            if universe.avg_runtime_seconds >= self.slow_runtime_seconds_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.SPLIT_UNIVERSE,
                        severity=IntelligenceSeverity.HIGH,
                        title="Split slow universe",
                        description="Universe runtime exceeds slow-execution threshold.",
                        tenant_id=universe.tenant_id,
                        universe_id=universe.universe_id,
                        confidence=0.86,
                        metadata={"avg_runtime_seconds": universe.avg_runtime_seconds},
                    )
                )

            if universe.sla_breach_rate >= self.sla_breach_rate_threshold:
                recommendations.append(
                    self._recommendation(
                        recommendation_type=IntelligenceRecommendationType.PROTECT_SLA,
                        severity=IntelligenceSeverity.HIGH,
                        title="Protect universe SLA",
                        description="Universe SLA breach rate exceeds threshold.",
                        tenant_id=universe.tenant_id,
                        universe_id=universe.universe_id,
                        confidence=0.90,
                        metadata={"sla_breach_rate": universe.sla_breach_rate},
                    )
                )

        self.recommendation_history.extend(recommendations)
        if len(self.recommendation_history) > 10000:
            self.recommendation_history = self.recommendation_history[-10000:]

        return recommendations

    def tenant_rankings(
        self,
        profiles: Optional[Iterable[TenantIntelligenceProfile]] = None,
    ) -> List[TenantIntelligenceProfile]:
        source = list(profiles) if profiles is not None else list(self.tenant_profiles.values())
        return sorted(
            source,
            key=lambda p: (
                p.risk_score,
                p.consumption_score,
                -p.efficiency_score,
            ),
            reverse=True,
        )

    def universe_rankings(
        self,
        profiles: Optional[Iterable[UniverseIntelligenceProfile]] = None,
    ) -> List[UniverseIntelligenceProfile]:
        source = list(profiles) if profiles is not None else list(self.universe_profiles.values())
        return sorted(
            source,
            key=lambda p: (
                p.risk_score,
                -p.refresh_efficiency_score,
                -p.execution_efficiency_score,
                p.cost_per_analytic,
            ),
            reverse=True,
        )

    def intelligence_summary(self) -> Dict[str, Any]:
        latest = self.report_history[-1] if self.report_history else None
        return {
            "tenant_samples": len(self.tenant_samples),
            "universe_samples": len(self.universe_samples),
            "tenant_profiles": len(self.tenant_profiles),
            "universe_profiles": len(self.universe_profiles),
            "recommendations": len(self.recommendation_history),
            "reports": len(self.report_history),
            "latest_report_id": latest.report_id if latest else None,
            "generated_at": utc_now_iso(),
        }

    def export_state(self) -> Dict[str, Any]:
        return {
            "summary": self.intelligence_summary(),
            "tenant_profiles": {k: asdict(v) for k, v in self.tenant_profiles.items()},
            "universe_profiles": {k: asdict(v) for k, v in self.universe_profiles.items()},
            "recent_recommendations": [asdict(r) for r in self.recommendation_history[-100:]],
            "recent_reports": [r.as_dict() for r in self.report_history[-10:]],
        }

    def _classify_tenant_state(
        self,
        *,
        queue_pressure: float,
        failure_rate: float,
        cost_per_job: float,
        sla_breach_rate: float,
    ) -> str:
        if sla_breach_rate >= self.sla_breach_rate_threshold:
            return TenantBehaviorState.SLA_RISK.value
        if failure_rate >= self.high_failure_rate_threshold:
            return TenantBehaviorState.DEGRADED.value
        if queue_pressure >= self.high_queue_pressure_threshold:
            return TenantBehaviorState.QUEUE_PRESSURED.value
        if cost_per_job >= self.high_cost_per_job_threshold:
            return TenantBehaviorState.COST_HEAVY.value
        return TenantBehaviorState.NORMAL.value

    def _classify_universe_state(
        self,
        *,
        analytics_yield: float,
        stale_symbol_rate: float,
        cost_per_analytic: float,
        avg_runtime_seconds: float,
        sla_breach_rate: float,
        refresh_interval_minutes: int,
    ) -> str:
        if sla_breach_rate >= self.sla_breach_rate_threshold:
            return UniverseBehaviorState.SLA_RISK.value
        if avg_runtime_seconds >= self.slow_runtime_seconds_threshold:
            return UniverseBehaviorState.SLOW_EXECUTION.value
        if cost_per_analytic >= self.high_cost_per_job_threshold:
            return UniverseBehaviorState.HIGH_COST.value
        if analytics_yield <= self.low_analytics_yield_threshold:
            return UniverseBehaviorState.LOW_YIELD.value
        if stale_symbol_rate >= self.high_stale_symbol_rate_threshold:
            return UniverseBehaviorState.UNDER_REFRESHED.value
        if analytics_yield <= self.low_analytics_yield_threshold and refresh_interval_minutes <= 15:
            return UniverseBehaviorState.OVER_REFRESHED.value
        return UniverseBehaviorState.NORMAL.value

    def _recommendation(
        self,
        *,
        recommendation_type: IntelligenceRecommendationType,
        severity: IntelligenceSeverity,
        title: str,
        description: str,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TenantUniverseRecommendation:
        return TenantUniverseRecommendation(
            recommendation_id=f"turec_{uuid.uuid4().hex}",
            recommendation_type=recommendation_type.value,
            severity=severity.value,
            title=title,
            description=description,
            tenant_id=tenant_id,
            universe_id=universe_id,
            confidence=round(clamp(confidence), 4),
            metadata=metadata or {},
        )

    @staticmethod
    def _universe_key(tenant_id: str, universe_id: str) -> str:
        return f"{tenant_id}::{universe_id}"


def create_tenant_universe_intelligence_engine(
    *,
    high_queue_pressure_threshold: float = 0.75,
    high_failure_rate_threshold: float = 0.10,
    high_cost_per_job_threshold: float = 1.00,
    low_analytics_yield_threshold: float = 0.25,
    high_stale_symbol_rate_threshold: float = 0.30,
    sla_breach_rate_threshold: float = 0.05,
    slow_runtime_seconds_threshold: float = 300.0,
) -> TenantUniverseIntelligenceEngine:
    return TenantUniverseIntelligenceEngine(
        high_queue_pressure_threshold=high_queue_pressure_threshold,
        high_failure_rate_threshold=high_failure_rate_threshold,
        high_cost_per_job_threshold=high_cost_per_job_threshold,
        low_analytics_yield_threshold=low_analytics_yield_threshold,
        high_stale_symbol_rate_threshold=high_stale_symbol_rate_threshold,
        sla_breach_rate_threshold=sla_breach_rate_threshold,
        slow_runtime_seconds_threshold=slow_runtime_seconds_threshold,
    )