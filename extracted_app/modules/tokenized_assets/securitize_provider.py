"""
modules/tokenized_assets/securitize_provider.py

Adapter for Securitize (https://securitize.io), the transfer-agent and
tokenization platform behind institutional products like BlackRock's
BUIDL fund -- currently the flagship example of tokenized Treasuries,
live across eight chains and $2.9B+ in assets as of mid-2026. Securitize
handles issuance, cap-table/transfer-agent services, and investor
onboarding for tokenized funds, private credit, and other securities.

HONESTY NOTE: Securitize's institutional API access is contract-based
(you become a Securitize-issued-fund investor or a platform partner, not
a self-serve API-key signup), and exact endpoint schemas aren't publicly
documented the way Alpaca's are. The client below is a best-effort,
illustrative REST structure -- verify against your actual Securitize
integration agreement and API documentation before production use.
"""

from __future__ import annotations

from typing import List
import requests
from requests.auth import HTTPBasicAuth

from modules.tokenized_assets.base import (
    TokenizedAssetBroker, TokenizedAssetInfo, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition,
)
from modules.admin.tenant_api_keys import get_securitize_credentials
from modules.risk_layer.classification import register_real_world_asset

# Real, named tokenized funds live on Securitize's platform as of mid-2026.
_KNOWN_SECURITIZE_SYMBOLS = ["BUIDL"]
for _sym in _KNOWN_SECURITIZE_SYMBOLS:
    register_real_world_asset(_sym)


class SecuritizeNotConfigured(RuntimeError):
    pass


class SecuritizeProvider(TokenizedAssetBroker):
    name = "securitize"
    display_name = "Securitize"

    def __init__(self):
        creds = get_securitize_credentials()
        self.api_key = creds["api_key"]
        self.api_secret = creds["api_secret"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]

    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(self.api_key, self.api_secret)

    def _require_configured(self):
        if not self.configured:
            raise SecuritizeNotConfigured(
                "Securitize isn't connected yet. Add your API key and secret in "
                "Admin > API Keys, then try again."
            )

    def list_assets(self) -> List[TokenizedAssetInfo]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/funds", auth=self._auth(), timeout=20)
        r.raise_for_status()
        rows = r.json().get("funds", [])
        assets = []
        for row in rows:
            symbol = row.get("ticker") or row.get("symbol")
            asset = TokenizedAssetInfo(
                symbol=symbol,
                name=row.get("name", symbol),
                underlying_type=row.get("asset_class", "fund"),
                chain=row.get("chain", "Ethereum"),
                contract_address=row.get("contract_address"),
                custodian="Securitize",
            )
            if symbol:
                register_real_world_asset(symbol)
            assets.append(asset)
        return assets

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        payload = {
            "fundTicker": req.symbol, "side": req.side, "quantity": req.qty,
            "orderType": req.order_type,
        }
        r = requests.post(f"{self.base_url}/v1/orders", auth=self._auth(), json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(data.get("orderId", "")),
            status=data.get("status", "submitted"),
            symbol=req.symbol, side=req.side, qty=req.qty,
            filled_qty=float(data.get("filledQuantity") or 0.0),
            avg_fill_price=float(data["avgFillPrice"]) if data.get("avgFillPrice") else None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/orders/{broker_order_id}", auth=self._auth(), timeout=20)
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(broker_order_id), status=data.get("status", "unknown"),
            symbol=data.get("fundTicker", ""), side=data.get("side", ""),
            qty=float(data.get("quantity") or 0.0), filled_qty=float(data.get("filledQuantity") or 0.0),
            avg_fill_price=float(data["avgFillPrice"]) if data.get("avgFillPrice") else None,
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        self._require_configured()
        r = requests.delete(f"{self.base_url}/v1/orders/{broker_order_id}", auth=self._auth(), timeout=20)
        return r.status_code in (200, 204)

    def list_positions(self) -> List[BrokerPosition]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/investor/holdings", auth=self._auth(), timeout=20)
        r.raise_for_status()
        rows = r.json().get("holdings", [])
        for row in rows:
            ticker = row.get("fundTicker")
            if ticker:
                register_real_world_asset(ticker)
        return [
            BrokerPosition(
                symbol=row.get("fundTicker", ""), qty=float(row.get("shares") or 0.0),
                avg_cost=float(row.get("avgCost") or 0.0), market_price=float(row.get("nav") or 0.0),
                market_value=float(row.get("marketValue") or 0.0),
                unrealized_pnl=float(row.get("unrealizedPnl") or 0.0),
            )
            for row in rows
        ]

    def get_buying_power(self) -> float:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/investor/account", auth=self._auth(), timeout=20)
        r.raise_for_status()
        return float(r.json().get("availableCash") or 0.0)

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No Securitize API key/secret configured."}
        try:
            r = requests.get(f"{self.base_url}/v1/investor/account", auth=self._auth(), timeout=10)
            if r.status_code == 200:
                return {"ok": True, "detail": "Securitize reachable and credentials accepted."}
            return {"ok": False, "detail": f"Securitize returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
