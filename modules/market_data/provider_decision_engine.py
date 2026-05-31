"""
modules/market_data/provider_decision_engine.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from modules.market_data.provider_router import get_provider_router
from modules.market_data.provider_intelligence_engine import (
    get_provider_intelligence_engine,
)


@dataclass
class ProviderDecision:
    request_type: str
    symbol: Optional[str]
    selected_provider: Optional[str]
    failover_chain: List[str]
    reason: str
    confidence: float
    generated_at: str


class ProviderDecisionEngine:
    def __init__(self):
        self.router = get_provider_router()
        self.intelligence = get_provider_intelligence_engine()

    def decide(
        self,
        request_type: str,
        symbol: Optional[str] = None,
        allowed_providers: Optional[List[str]] = None,
    ) -> ProviderDecision:
        print(
            "ALLOWED PROVIDERS:",
            allowed_providers,
        )

        ranked = self.router.get_ranked_providers(
            allowed=allowed_providers,
        )

        print(
            "RANKED PROVIDERS:",
            [
                p.provider
                for p in ranked
            ]
        )

        failover_chain = [
            p.provider
            for p in ranked
        ]

        if not ranked:
            return ProviderDecision(
                request_type=request_type,
                symbol=symbol,
                selected_provider=None,
                failover_chain=[],
                reason="No available providers.",
                confidence=0.0,
                generated_at=datetime.now(UTC).isoformat(),
            )

        selected = ranked[0]

        confidence = max(
            0.0,
            min(100.0, float(selected.health_score)),
        )

        return ProviderDecision(
            request_type=request_type,
            symbol=symbol,
            selected_provider=selected.provider,
            failover_chain=failover_chain,
            reason=(
                f"Selected {selected.provider} based on highest "
                f"available health score."
            ),
            confidence=confidence,
            generated_at=datetime.now(UTC).isoformat(),
        )

    def as_dict(
        self,
        decision: ProviderDecision,
    ) -> Dict[str, Any]:
        return {
            "request_type": decision.request_type,
            "symbol": decision.symbol,
            "selected_provider": decision.selected_provider,
            "failover_chain": decision.failover_chain,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "generated_at": decision.generated_at,
        }


_engine = None


def get_provider_decision_engine():
    global _engine

    if _engine is None:
        _engine = ProviderDecisionEngine()

    return _engine