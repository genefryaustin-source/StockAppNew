"""
modules/analytics/provider_cost_intelligence.py

Provider Cost Intelligence Engine

Purpose
-------
Tracks:

    provider API usage
    quota consumption
    request cost
    latency cost
    error cost
    failover cost
    provider efficiency
    provider ranking

Provides:

    provider scoring
    cost-aware routing
    quota forecasting
    provider recommendations
    optimizer inputs

Used By
-------

    autonomous_analytics_optimizer.py
    analytics_resource_governor.py
    global_analytics_planner.py
    provider routing engines

Architecture Rules
------------------

- No global mutable state
- Tenant aware
- Provider aware
- Deterministic calculations
- Runtime-safe
"""

from __future__ import annotations

import statistics
import uuid

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value))
    )


# =============================================================================
# Enums
# =============================================================================

class ProviderStatus(str, Enum):

    ACTIVE = "ACTIVE"

    DEGRADED = "DEGRADED"

    THROTTLED = "THROTTLED"

    EXHAUSTED = "EXHAUSTED"

    DISABLED = "DISABLED"


class ProviderRecommendationType(str, Enum):

    INCREASE_USAGE = "INCREASE_USAGE"

    REDUCE_USAGE = "REDUCE_USAGE"

    FAILOVER = "FAILOVER"

    DISABLE_PROVIDER = "DISABLE_PROVIDER"

    INCREASE_QUOTA = "INCREASE_QUOTA"


# =============================================================================
# Models
# =============================================================================

@dataclass
class ProviderUsageSample:

    provider: str

    requests: int = 0

    successes: int = 0

    failures: int = 0

    throttles: int = 0

    quota_used: int = 0

    quota_limit: int = 0

    average_latency_ms: float = 0.0

    total_cost_usd: float = 0.0

    recorded_at: str = field(
        default_factory=utc_now_iso
    )


@dataclass
class ProviderProfile:

    provider: str

    status: str

    requests: int

    success_rate: float

    failure_rate: float

    throttle_rate: float

    quota_utilization: float

    average_latency_ms: float

    total_cost_usd: float

    cost_per_request: float

    efficiency_score: float

    reliability_score: float

    routing_score: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )


@dataclass
class ProviderRecommendation:

    recommendation_id: str

    provider: str

    recommendation_type: str

    confidence: float

    reason: str

    generated_at: str = field(
        default_factory=utc_now_iso
    )


# =============================================================================
# Engine
# =============================================================================

class ProviderCostIntelligence:

    def __init__(self):

        self.samples: List[
            ProviderUsageSample
        ] = []

        self.provider_profiles: Dict[
            str,
            ProviderProfile
        ] = {}

        self.recommendations: List[
            ProviderRecommendation
        ] = []

    # =========================================================================
    # Collection
    # =========================================================================

    def record_usage(
        self,
        sample: ProviderUsageSample,
    ) -> None:

        self.samples.append(
            sample
        )

    # =========================================================================
    # Analysis
    # =========================================================================

    def build_provider_profile(
        self,
        provider: str,
    ) -> Optional[ProviderProfile]:

        provider_samples = [

            s

            for s in self.samples

            if s.provider == provider

        ]

        if not provider_samples:

            return None

        requests = sum(
            s.requests
            for s in provider_samples
        )

        successes = sum(
            s.successes
            for s in provider_samples
        )

        failures = sum(
            s.failures
            for s in provider_samples
        )

        throttles = sum(
            s.throttles
            for s in provider_samples
        )

        quota_used = sum(
            s.quota_used
            for s in provider_samples
        )

        quota_limit = max(
            [
                s.quota_limit
                for s in provider_samples
            ] or [0]
        )

        total_cost = sum(
            s.total_cost_usd
            for s in provider_samples
        )

        avg_latency = statistics.mean(
            [
                s.average_latency_ms
                for s in provider_samples
            ]
        )

        success_rate = (
            successes / requests
            if requests
            else 0.0
        )

        failure_rate = (
            failures / requests
            if requests
            else 0.0
        )

        throttle_rate = (
            throttles / requests
            if requests
            else 0.0
        )

        quota_utilization = (
            quota_used / quota_limit
            if quota_limit
            else 0.0
        )

        cost_per_request = (
            total_cost / requests
            if requests
            else 0.0
        )

        reliability_score = clamp(
            success_rate
            -
            failure_rate
        )

        latency_score = clamp(
            1.0
            -
            (
                avg_latency
                / 5000.0
            )
        )

        cost_score = clamp(
            1.0
            -
            (
                cost_per_request
                / 1.0
            )
        )

        efficiency_score = round(
            (
                reliability_score * 0.50
                +
                latency_score * 0.25
                +
                cost_score * 0.25
            ),
            4,
        )

        routing_score = round(
            (
                efficiency_score * 0.60
                +
                (
                    1.0
                    -
                    quota_utilization
                )
                * 0.40
            ),
            4,
        )

        status = ProviderStatus.ACTIVE.value

        if quota_utilization >= 1.0:

            status = (
                ProviderStatus.EXHAUSTED.value
            )

        elif throttle_rate >= 0.25:

            status = (
                ProviderStatus.THROTTLED.value
            )

        elif failure_rate >= 0.20:

            status = (
                ProviderStatus.DEGRADED.value
            )

        profile = ProviderProfile(

            provider=provider,

            status=status,

            requests=requests,

            success_rate=round(
                success_rate,
                4,
            ),

            failure_rate=round(
                failure_rate,
                4,
            ),

            throttle_rate=round(
                throttle_rate,
                4,
            ),

            quota_utilization=round(
                quota_utilization,
                4,
            ),

            average_latency_ms=round(
                avg_latency,
                4,
            ),

            total_cost_usd=round(
                total_cost,
                4,
            ),

            cost_per_request=round(
                cost_per_request,
                8,
            ),

            efficiency_score=efficiency_score,

            reliability_score=round(
                reliability_score,
                4,
            ),

            routing_score=routing_score,
        )

        self.provider_profiles[
            provider
        ] = profile

        return profile

    # =========================================================================
    # Recommendations
    # =========================================================================

    def generate_recommendations(
        self,
    ) -> List[
        ProviderRecommendation
    ]:

        recommendations = []

        for profile in (
            self.provider_profiles.values()
        ):

            if (
                profile.status
                ==
                ProviderStatus.EXHAUSTED.value
            ):

                recommendations.append(
                    ProviderRecommendation(
                        recommendation_id=
                        f"REC_{uuid.uuid4().hex}",

                        provider=
                        profile.provider,

                        recommendation_type=
                        ProviderRecommendationType.FAILOVER.value,

                        confidence=0.99,

                        reason=
                        "Provider quota exhausted.",
                    )
                )

            elif (
                profile.status
                ==
                ProviderStatus.THROTTLED.value
            ):

                recommendations.append(
                    ProviderRecommendation(
                        recommendation_id=
                        f"REC_{uuid.uuid4().hex}",

                        provider=
                        profile.provider,

                        recommendation_type=
                        ProviderRecommendationType.REDUCE_USAGE.value,

                        confidence=0.90,

                        reason=
                        "Provider experiencing throttling.",
                    )
                )

            elif (
                profile.routing_score
                >= 0.80
            ):

                recommendations.append(
                    ProviderRecommendation(
                        recommendation_id=
                        f"REC_{uuid.uuid4().hex}",

                        provider=
                        profile.provider,

                        recommendation_type=
                        ProviderRecommendationType.INCREASE_USAGE.value,

                        confidence=0.85,

                        reason=
                        "Provider is highly efficient.",
                    )
                )

        self.recommendations = (
            recommendations
        )

        return recommendations

    # =========================================================================
    # Rankings
    # =========================================================================

    def rank_providers(
        self,
    ) -> List[
        ProviderProfile
    ]:

        return sorted(

            self.provider_profiles.values(),

            key=lambda p:
            (
                p.routing_score,
                p.efficiency_score,
                p.reliability_score,
            ),

            reverse=True,
        )

    def best_provider(
        self,
    ) -> Optional[
        ProviderProfile
    ]:

        ranked = self.rank_providers()

        return (
            ranked[0]
            if ranked
            else None
        )

    # =========================================================================
    # Forecasting
    # =========================================================================

    def forecast_quota_exhaustion(
        self,
        provider: str,
        projected_requests: int,
    ) -> Dict[str, Any]:

        profile = (
            self.provider_profiles.get(
                provider
            )
        )

        if not profile:

            return {}

        projected_quota = (
            profile.quota_utilization
        )

        return {

            "provider":
            provider,

            "current_quota_utilization":
            profile.quota_utilization,

            "projected_requests":
            projected_requests,

            "projected_exhaustion_risk":
            round(
                min(
                    1.0,
                    projected_quota
                    +
                    (
                        projected_requests
                        /
                        max(
                            profile.requests,
                            1,
                        )
                    ),
                ),
                4,
            ),

            "generated_at":
            utc_now_iso(),
        }

    # =========================================================================
    # Reporting
    # =========================================================================

    def summary(
        self,
    ) -> Dict[str, Any]:

        return {

            "providers":
            len(
                self.provider_profiles
            ),

            "samples":
            len(
                self.samples
            ),

            "recommendations":
            len(
                self.recommendations
            ),

            "best_provider":
            (
                self.best_provider().provider
                if self.best_provider()
                else None
            ),

            "generated_at":
            utc_now_iso(),
        }

    def export_state(
        self,
    ) -> Dict[str, Any]:

        return {

            "profiles": {

                name: asdict(profile)

                for (
                    name,
                    profile
                )

                in self.provider_profiles.items()

            },

            "recommendations": [

                asdict(r)

                for r

                in self.recommendations

            ],

            "summary":
            self.summary(),
        }