"""
modules/risk_providers/factset_provider.py

Adapter for FactSet's Open:Risk API (https://developer.factset.com/api-catalog/openrisk-api),
which computes portfolio risk (VaR, sensitivities, factor exposures) from
a holdings list submitted via REST, authenticated with HTTP Basic auth
using a FactSet username-serial + API key pair.

HONESTY NOTE: FactSet's APIs are enterprise-contract products with formal
onboarding and versioned request/response schemas documented in FactSet's
own developer portal (which requires a FactSet account to view in full).
The payload shape below is a best-effort, illustrative REST client, not
verified against a live FactSet contract -- check developer.factset.com
for your subscription's exact Open:Risk request/response schema (their
own SDKs, e.g. fds.sdk.OpenRisk for Python, are the more robust way to
integrate if you have access to them) and adjust this adapter to match.
"""

from __future__ import annotations

import requests
from requests.auth import HTTPBasicAuth

from modules.risk_providers.base import RiskProviderBase, RiskProviderRequest, RiskProviderResult
from modules.admin.tenant_api_keys import get_factset_credentials


class FactSetRiskProvider(RiskProviderBase):
    name = "factset"
    display_name = "FactSet Open:Risk API"

    def __init__(self, tenant_id=None):
        super().__init__(tenant_id)
        creds = get_factset_credentials(tenant_id=tenant_id)
        self.username = creds["username"]
        self.api_key = creds["api_key"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]

    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(self.username, self.api_key)

    def _build_request_payload(self, request: RiskProviderRequest) -> dict:
        ids, market_values = [], []
        if request.positions_df is not None and not request.positions_df.empty:
            for _, row in request.positions_df.iterrows():
                ids.append(row.get("Symbol"))
                market_values.append(row.get("Market Value"))
        return {
            "data": {
                "holdings": {
                    "portfolio": {"ids": ids, "marketValues": market_values},
                },
                "confidenceLevel": request.confidence,
                "horizonDays": request.horizon_days,
            }
        }

    def fetch_portfolio_risk(self, request: RiskProviderRequest) -> RiskProviderResult:
        if not self.configured:
            return RiskProviderResult(provider=self.name, available=False,
                                       error="FactSet username/API key not configured.")
        try:
            r = requests.post(
                f"{self.base_url}/analytics/engines/risk/v3/holdings",
                auth=self._auth(),
                json=self._build_request_payload(request),
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            result = data.get("data", data)
            return RiskProviderResult(
                provider=self.name, available=True,
                var=result.get("var") or result.get("valueAtRisk"),
                expected_shortfall=result.get("expectedShortfall"),
                factor_exposures=result.get("factorExposures", {}),
                stress_scenarios=result.get("stressScenarios", {}),
                raw=data,
            )
        except Exception as e:
            return RiskProviderResult(provider=self.name, available=False,
                                       error=f"FactSet request failed: {e}")

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No FactSet username/API key configured."}
        try:
            r = requests.get(f"{self.base_url}/analytics/lookups/v3/currencies",
                              auth=self._auth(), timeout=10)
            if r.status_code == 200:
                return {"ok": True, "detail": "FactSet API reachable and credentials accepted."}
            return {"ok": False, "detail": f"FactSet returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
