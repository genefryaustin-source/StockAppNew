"""
modules/risk_providers/custom_provider.py

A generic REST risk-provider adapter for any vendor (or in-house risk
service) without a dedicated adapter above -- point it at a base URL with
an API key, and map its JSON response fields to VaR/Expected Shortfall
via the Risk Providers admin tab. This is the pragmatic answer to "we use
some other risk vendor" without needing a code change per new vendor.

Config (set per-tenant in the Risk Providers admin tab, stored as JSON on
TenantRiskProviderSetting.config_json):
    request_path        e.g. "/v1/portfolio-risk"       (appended to base_url)
    method               "POST" (default) or "GET"
    symbol_field         JSON key for a position's symbol      (default "symbol")
    qty_field            JSON key for a position's quantity     (default "quantity")
    value_field          JSON key for a position's market value (default "market_value")
    positions_field      top-level JSON key for the positions list (default "positions")
    response_var_path    dotted path to VaR in the response      (default "var")
    response_es_path     dotted path to Expected Shortfall       (default "expected_shortfall")
"""

from __future__ import annotations

import json
import requests

from modules.risk_providers.base import RiskProviderBase, RiskProviderRequest, RiskProviderResult
from modules.admin.tenant_api_keys import get_custom_risk_provider_credentials

DEFAULT_CONFIG = {
    "request_path": "/risk",
    "method": "POST",
    "symbol_field": "symbol",
    "qty_field": "quantity",
    "value_field": "market_value",
    "positions_field": "positions",
    "response_var_path": "var",
    "response_es_path": "expected_shortfall",
}


def _get_path(data: dict, dotted_path: str):
    node = data
    for part in dotted_path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


class CustomRiskProvider(RiskProviderBase):
    name = "custom"
    display_name = "Custom Risk Provider"

    def __init__(self, tenant_id=None, config: dict = None):
        super().__init__(tenant_id)
        creds = get_custom_risk_provider_credentials(tenant_id=tenant_id)
        self.api_key = creds["api_key"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _build_request_payload(self, request: RiskProviderRequest) -> dict:
        cfg = self.config
        positions = []
        if request.positions_df is not None and not request.positions_df.empty:
            for _, row in request.positions_df.iterrows():
                positions.append({
                    cfg["symbol_field"]: row.get("Symbol"),
                    cfg["qty_field"]: row.get("Quantity"),
                    cfg["value_field"]: row.get("Market Value"),
                })
        return {
            cfg["positions_field"]: positions,
            "confidence": request.confidence,
            "horizon_days": request.horizon_days,
        }

    def fetch_portfolio_risk(self, request: RiskProviderRequest) -> RiskProviderResult:
        if not self.configured:
            return RiskProviderResult(provider=self.name, available=False,
                                       error="Custom risk provider base URL/API key not configured.")
        cfg = self.config
        try:
            url = f"{self.base_url}{cfg['request_path']}"
            if cfg.get("method", "POST").upper() == "GET":
                r = requests.get(url, headers=self._headers(), timeout=20)
            else:
                r = requests.post(url, headers=self._headers(),
                                   json=self._build_request_payload(request), timeout=20)
            r.raise_for_status()
            data = r.json()
            return RiskProviderResult(
                provider=self.name, available=True,
                var=_get_path(data, cfg["response_var_path"]),
                expected_shortfall=_get_path(data, cfg["response_es_path"]),
                raw=data,
            )
        except Exception as e:
            return RiskProviderResult(provider=self.name, available=False,
                                       error=f"Custom provider request failed: {e}")

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No base URL/API key configured for the custom provider."}
        try:
            r = requests.get(self.base_url, headers=self._headers(), timeout=10)
            return {"ok": True, "detail": f"Reached {self.base_url} (HTTP {r.status_code})."}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
