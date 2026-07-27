"""
modules/risk_providers/base.py

Common interface for external risk-analytics vendors (PortfolioScience
RiskAPI, FactSet Open:Risk, MSCI RiskMetrics, or a custom in-house REST
risk service). Mirrors modules.portfolio.brokers.base -- same idea, same
shape: one small dataclass for the request, one for the response, one
base class every vendor adapter implements.

These vendors are supplemental, not authoritative -- the Risk Layer's own
modules.portfolio.risk_analytics_service.RiskAnalyticsService remains the
primary VaR/ES/concentration engine. A configured vendor's numbers show up
alongside it as an external cross-check (e.g. "does an independent model
agree our VaR is ~$X"), which is exactly the kind of thing a real risk
desk wants a second opinion on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class RiskProviderRequest:
    positions_df: pd.DataFrame   # Symbol, Asset Class, Quantity, Market Value, Weight
    equity: float
    confidence: float = 0.95
    horizon_days: int = 1


@dataclass
class RiskProviderResult:
    provider: str
    available: bool
    var: Optional[float] = None
    expected_shortfall: Optional[float] = None
    factor_exposures: dict = field(default_factory=dict)
    stress_scenarios: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "available": self.available,
            "var": self.var,
            "expected_shortfall": self.expected_shortfall,
            "factor_exposures": self.factor_exposures,
            "stress_scenarios": self.stress_scenarios,
            "error": self.error,
        }


class RiskProviderBase:
    name = "base"
    display_name = "Base Risk Provider"

    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.configured = False

    def fetch_portfolio_risk(self, request: RiskProviderRequest) -> RiskProviderResult:
        raise NotImplementedError

    def test_connection(self) -> dict:
        """Returns {"ok": bool, "detail": str} without raising -- same
        contract as the broker test_connection() methods."""
        raise NotImplementedError
