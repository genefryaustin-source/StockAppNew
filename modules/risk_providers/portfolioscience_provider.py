"""
modules/risk_providers/portfolioscience_provider.py

Adapter for PortfolioScience RiskAPI (https://www.portfolioscience.com/products/riskapi-enterprise),
a hosted, API-based multi-model VaR / stress-test / valuation service.

HONESTY NOTE: PortfolioScience RiskAPI is sold as an enterprise product
with onboarding through their own team, not a fully public self-serve API
with a stable, versioned public schema this code was tested against. The
request/response shape below is a best-effort, illustrative REST client
based on how this class of "submit positions, get back VaR/stress
results" API is conventionally shaped -- verify field names against your
actual PortfolioScience contract and API documentation before relying on
it in production, and adjust _build_request_payload / _parse_response to
match exactly what your account returns.
"""

from __future__ import annotations

import requests

from modules.risk_providers.base import RiskProviderBase, RiskProviderRequest, RiskProviderResult
from modules.admin.tenant_api_keys import get_portfolioscience_credentials


class PortfolioScienceRiskProvider(RiskProviderBase):
    name = "portfolioscience"
    display_name = "PortfolioScience RiskAPI"

    def __init__(self, tenant_id=None):
        super().__init__(tenant_id)
        creds = get_portfolioscience_credentials(tenant_id=tenant_id)
        self.api_key = creds["api_key"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _build_request_payload(self, request: RiskProviderRequest) -> dict:
        positions = []
        if request.positions_df is not None and not request.positions_df.empty:
            for _, row in request.positions_df.iterrows():
                positions.append({
                    "symbol": row.get("Symbol"),
                    "quantity": row.get("Quantity"),
                    "market_value": row.get("Market Value"),
                })
        return {
            "positions": positions,
            "confidence": request.confidence,
            "horizon_days": request.horizon_days,
        }

    def fetch_portfolio_risk(self, request: RiskProviderRequest) -> RiskProviderResult:
        if not self.configured:
            return RiskProviderResult(provider=self.name, available=False,
                                       error="PortfolioScience API key not configured.")
        try:
            r = requests.post(
                f"{self.base_url}/v1/portfolio/risk",
                headers=self._headers(),
                json=self._build_request_payload(request),
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            return RiskProviderResult(
                provider=self.name, available=True,
                var=data.get("var"),
                expected_shortfall=data.get("expected_shortfall") or data.get("cvar"),
                factor_exposures=data.get("factor_exposures", {}),
                stress_scenarios=data.get("stress_scenarios", {}),
                raw=data,
            )
        except Exception as e:
            return RiskProviderResult(provider=self.name, available=False,
                                       error=f"PortfolioScience request failed: {e}")

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No PortfolioScience API key configured."}
        try:
            r = requests.get(f"{self.base_url}/v1/ping", headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return {"ok": True, "detail": "PortfolioScience RiskAPI reachable."}
            return {"ok": False, "detail": f"PortfolioScience returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
