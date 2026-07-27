"""
modules/market_data/provider_intelligence_engine.py
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Dict, Any

from modules.market_data.provider_router import (
    get_provider_router,
)

from modules.market_data.adaptive_rate_limit_manager import (
    get_rate_limit_manager,
)


class ProviderIntelligenceEngine:

    def __init__(self):
        self.router = get_provider_router()
        self.rate_manager = (
            get_rate_limit_manager()
        )

    def analyze_provider(
        self,
        provider_name: str,
    ) -> Dict[str, Any]:

        provider = self.router.get_provider(
            provider_name,
        )

        if not provider:
            return {
                "provider": provider_name,
                "status": "UNKNOWN",
            }

        requests = (
            provider.success_count
            + provider.failure_count
        )

        success_rate = 100.0

        if requests > 0:
            success_rate = (
                provider.success_count
                / requests
            ) * 100.0

        recommendation = "HEALTHY"

        if provider.rate_limit_count > 10:
            recommendation = (
                "REDUCE_TRAFFIC"
            )

        elif provider.health_score < 50:
            recommendation = (
                "FAILOVER"
            )

        elif provider.health_score < 75:
            recommendation = (
                "DEGRADED"
            )

        return {
            "provider": provider.provider,
            "health_score": provider.health_score,
            "success_rate": success_rate,
            "requests": requests,
            "failures": provider.failure_count,
            "rate_limits": provider.rate_limit_count,
            "avg_latency_ms": provider.avg_latency_ms,
            "recommendation": recommendation,
            "cooldown_until": provider.cooldown_until,
        }

    def analyze_all_providers(self):

        results = []

        for provider in self.router.all_providers():

            results.append(
                self.analyze_provider(
                    provider.provider,
                )
            )

        results.sort(
            key=lambda x: x["health_score"],
            reverse=True,
        )

        return results

    def best_provider(self):

        ranked = self.router.get_ranked_providers()

        if not ranked:
            return None

        provider = ranked[0]

        return self.analyze_provider(
            provider.provider,
        )

    def worst_provider(self):

        providers = (
            self.router.all_providers()
        )

        if not providers:
            return None

        providers.sort(
            key=lambda x: x.health_score
        )

        provider = providers[0]

        return self.analyze_provider(
            provider.provider,
        )

    def generate_routing_recommendations(self):

        recommendations = []

        for result in (
            self.analyze_all_providers()
        ):

            if (
                result["recommendation"]
                != "HEALTHY"
            ):
                recommendations.append(
                    result
                )

        return recommendations


_intelligence = None


def get_provider_intelligence_engine():

    global _intelligence

    if _intelligence is None:

        _intelligence = (
            ProviderIntelligenceEngine()
        )

    return _intelligence