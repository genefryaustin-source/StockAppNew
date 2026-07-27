"""
modules/tokenized_assets/custom_provider.py

A generic REST adapter for any tokenized-asset venue without a dedicated
integration -- real estate platforms (RealT, Lofty), private credit
platforms (Maple, Stokr), security-token exchanges (tZERO), or an
in-house custodian. Point it at a base URL with an API key; no field
mapping is needed beyond what BrokerOrderRequest/BrokerPosition already
expect, since order/position shape is fairly standardized across this
class of API. If a venue's schema differs meaningfully, this is the
adapter to fork into a dedicated one.
"""

from __future__ import annotations

from typing import List
import requests

from modules.tokenized_assets.base import (
    TokenizedAssetBroker, TokenizedAssetInfo, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition,
)
from modules.admin.tenant_api_keys import get_custom_tokenized_asset_credentials
from modules.risk_layer.classification import register_real_world_asset


class CustomTokenizedAssetNotConfigured(RuntimeError):
    pass


class CustomTokenizedAssetProvider(TokenizedAssetBroker):
    name = "tokenized_custom"
    display_name = "Custom Tokenized Asset Provider"

    def __init__(self):
        creds = get_custom_tokenized_asset_credentials()
        self.api_key = creds["api_key"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _require_configured(self):
        if not self.configured:
            raise CustomTokenizedAssetNotConfigured(
                "No custom tokenized asset provider configured. Add a base URL and API key "
                "in Admin > API Keys, then try again."
            )

    def list_assets(self) -> List[TokenizedAssetInfo]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/assets", headers=self._headers(), timeout=20)
        r.raise_for_status()
        rows = r.json().get("assets", [])
        assets = []
        for row in rows:
            symbol = row.get("symbol")
            if symbol:
                register_real_world_asset(symbol)
            assets.append(TokenizedAssetInfo(
                symbol=symbol, name=row.get("name", symbol),
                underlying_type=row.get("underlying_type", "equity"),
                chain=row.get("chain", "unknown"), contract_address=row.get("contract_address"),
                custodian=row.get("custodian", "Custom"),
            ))
        return assets

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        payload = {"symbol": req.symbol, "side": req.side, "quantity": req.qty, "order_type": req.order_type}
        if req.limit_price is not None:
            payload["limit_price"] = req.limit_price
        r = requests.post(f"{self.base_url}/orders", headers=self._headers(), json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(data.get("order_id", "")), status=data.get("status", "submitted"),
            symbol=req.symbol, side=req.side, qty=req.qty,
            filled_qty=float(data.get("filled_quantity") or 0.0),
            avg_fill_price=float(data["avg_fill_price"]) if data.get("avg_fill_price") else None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._require_configured()
        r = requests.get(f"{self.base_url}/orders/{broker_order_id}", headers=self._headers(), timeout=20)
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(broker_order_id), status=data.get("status", "unknown"),
            symbol=data.get("symbol", ""), side=data.get("side", ""),
            qty=float(data.get("quantity") or 0.0), filled_qty=float(data.get("filled_quantity") or 0.0),
            avg_fill_price=float(data["avg_fill_price"]) if data.get("avg_fill_price") else None,
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        self._require_configured()
        r = requests.delete(f"{self.base_url}/orders/{broker_order_id}", headers=self._headers(), timeout=20)
        return r.status_code in (200, 204)

    def list_positions(self) -> List[BrokerPosition]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/positions", headers=self._headers(), timeout=20)
        r.raise_for_status()
        rows = r.json().get("positions", [])
        for row in rows:
            if row.get("symbol"):
                register_real_world_asset(row["symbol"])
        return [
            BrokerPosition(
                symbol=row["symbol"], qty=float(row.get("quantity") or 0.0),
                avg_cost=float(row.get("avg_cost") or 0.0), market_price=float(row.get("price") or 0.0),
                market_value=float(row.get("market_value") or 0.0),
                unrealized_pnl=float(row.get("unrealized_pnl") or 0.0),
            )
            for row in rows
        ]

    def get_buying_power(self) -> float:
        self._require_configured()
        r = requests.get(f"{self.base_url}/account", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return float(r.json().get("available_balance") or 0.0)

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No custom tokenized asset provider configured."}
        try:
            r = requests.get(f"{self.base_url}/account", headers=self._headers(), timeout=10)
            return {"ok": True, "detail": f"Reached {self.base_url} (HTTP {r.status_code})."}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
