"""
===============================================================================
forex_runtime_history_models.py
Sprint 30 - Phase 2 (Part 1)
Runtime History Models
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


# =============================================================================
# Provider History
# =============================================================================

@dataclass(slots=True)
class ProviderRuntimeHistory:

    provider: str

    success: bool = True

    latency_ms: float = 0.0

    quote_count: int = 0

    failure_reason: Optional[str] = None

    health_score: float = 100.0

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()
        return d


# =============================================================================
# Currency Strength
# =============================================================================

@dataclass(slots=True)
class CurrencyStrengthHistory:

    currency: str

    strength: float

    rank: int

    momentum: float = 0.0

    confidence: float = 0.0

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()

        return d


# =============================================================================
# Regime History
# =============================================================================

@dataclass(slots=True)
class RegimeHistory:

    regime: str

    confidence: float

    volatility: float

    trend_score: float

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()

        return d


# =============================================================================
# AI History
# =============================================================================

@dataclass(slots=True)
class RuntimeAIHistory:

    recommendation: str

    confidence: float

    score: float

    explanation: str = ""

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()

        return d


# =============================================================================
# Risk History
# =============================================================================

@dataclass(slots=True)
class RuntimeRiskHistory:

    risk_score: float

    exposure: float

    leverage: float

    margin_used: float

    warnings: List[str] = field(default_factory=list)

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()

        return d


# =============================================================================
# Portfolio History
# =============================================================================

@dataclass(slots=True)
class RuntimePortfolioHistory:

    equity: float

    cash: float

    unrealized_pnl: float

    realized_pnl: float

    exposure: float

    positions: int

    captured_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()

        return d


# =============================================================================
# Runtime Snapshot
# =============================================================================

@dataclass(slots=True)
class ForexRuntimeSnapshot:

    runtime_id: str

    tenant_id: Optional[str]

    user_id: Optional[str]

    portfolio_id: Optional[str]

    build_number: int

    build_started_at: str

    build_completed_at: str

    provider_history: List[ProviderRuntimeHistory] = field(default_factory=list)

    currency_strength: List[CurrencyStrengthHistory] = field(default_factory=list)

    regime_history: List[RegimeHistory] = field(default_factory=list)

    ai_history: List[RuntimeAIHistory] = field(default_factory=list)

    risk_history: Optional[RuntimeRiskHistory] = None

    portfolio_history: Optional[RuntimePortfolioHistory] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self):

        return {

            "runtime_id": self.runtime_id,

            "tenant_id": self.tenant_id,

            "user_id": self.user_id,

            "portfolio_id": self.portfolio_id,

            "build_number": self.build_number,

            "build_started_at": self.build_started_at,

            "build_completed_at": self.build_completed_at,

            "provider_history": [
                x.to_dict()
                for x in self.provider_history
            ],

            "currency_strength": [
                x.to_dict()
                for x in self.currency_strength
            ],

            "regime_history": [
                x.to_dict()
                for x in self.regime_history
            ],

            "ai_history": [
                x.to_dict()
                for x in self.ai_history
            ],

            "risk_history": (
                self.risk_history.to_dict()
                if self.risk_history
                else None
            ),

            "portfolio_history": (
                self.portfolio_history.to_dict()
                if self.portfolio_history
                else None
            ),

            "metadata": dict(self.metadata),

            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Runtime Timeline
# =============================================================================

@dataclass(slots=True)
class RuntimeTimeline:

    snapshots: List[ForexRuntimeSnapshot] = field(default_factory=list)

    def add(
        self,
        snapshot: ForexRuntimeSnapshot,
    ):

        self.snapshots.append(snapshot)

        self.snapshots.sort(
            key=lambda s: s.created_at
        )

    @property
    def first(self):

        return self.snapshots[0] if self.snapshots else None

    @property
    def last(self):

        return self.snapshots[-1] if self.snapshots else None

    def to_dict(self):

        return {
            "count": len(self.snapshots),
            "snapshots": [
                s.to_dict()
                for s in self.snapshots
            ],
        }