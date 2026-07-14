"""
modules/tokenized_assets/ondo_provider.py

Adapter for Ondo Finance / Ondo Global Markets (https://ondo.finance),
which as of mid-2026 holds roughly 60% of the ~$2.2B tokenized-equity
market -- 430+ tokenized US stocks, ETFs, and commodities, plus its own
tokenized Treasury products (OUSG, USDY).

HONESTY NOTE: Ondo Global Markets' primary consumer access model in 2026
is self-custodial (MetaMask wallet, on-chain), not a traditional
brokerage REST API with API-key auth -- institutional/programmatic access
exists but isn't a fully public, self-serve developer portal the way
Alpaca's is. The request/response shape below is a best-effort REST
client structured the way a custodial trading API for this asset class
conventionally looks; verify field names against your actual Ondo
institutional access agreement and API documentation before relying on
it in production.
"""

from __future__ import annotations

from typing import List
import requests

from modules.tokenized_assets.base import (
    TokenizedAssetBroker, TokenizedAssetInfo, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition,
)
from modules.admin.tenant_api_keys import get_ondo_credentials
from modules.risk_layer.classification import register_real_world_asset

# Ondo's own tokenized Treasury/yield products (real, named tickers as of
# mid-2026) -- registered so the Risk Layer classifies them correctly
# without guessing from the symbol shape.
_KNOWN_ONDO_SYMBOLS = ["OUSG", "USDY"]
for _sym in _KNOWN_ONDO_SYMBOLS:
    register_real_world_asset(_sym)


class OndoNotConfigured(RuntimeError):
    pass


class OndoProvider(TokenizedAssetBroker):
    name = "ondo"
    display_name = "Ondo Finance (Global Markets)"

    def __init__(self):
        creds = get_ondo_credentials()
        self.api_key = creds["api_key"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _require_configured(self):
        if not self.configured:
            raise OndoNotConfigured(
                "Ondo Finance isn't connected yet. Add your API key in Admin > API Keys, "
                "then try again."
            )

    def list_assets(self) -> List[TokenizedAssetInfo]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/markets/assets", headers=self._headers(), timeout=20)
        r.raise_for_status()
        rows = r.json().get("assets", [])
        assets = []
        for row in rows:
            symbol = row.get("symbol")
            asset = TokenizedAssetInfo(
                symbol=symbol,
                name=row.get("name", symbol),
                underlying_type=row.get("underlying_type", "equity"),
                chain=row.get("chain", "Ethereum"),
                contract_address=row.get("contract_address"),
                custodian="Ondo Finance",
            )
            if symbol:
                register_real_world_asset(symbol)
            assets.append(asset)
        return assets

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        payload = {
            "symbol": req.symbol, "side": req.side, "quantity": req.qty,
            "order_type": req.order_type, "time_in_force": req.tif,
        }
        if req.limit_price is not None:
            payload["limit_price"] = req.limit_price
        r = requests.post(f"{self.base_url}/v1/orders", headers=self._headers(), json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(data.get("order_id", "")),
            status=data.get("status", "submitted"),
            symbol=req.symbol, side=req.side, qty=req.qty,
            filled_qty=float(data.get("filled_quantity") or 0.0),
            avg_fill_price=float(data["avg_fill_price"]) if data.get("avg_fill_price") else None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/orders/{broker_order_id}", headers=self._headers(), timeout=20)
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
        r = requests.delete(f"{self.base_url}/v1/orders/{broker_order_id}", headers=self._headers(), timeout=20)
        return r.status_code in (200, 204)

    def list_positions(self) -> List[BrokerPosition]:
        self._require_configured()
        r = requests.get(f"{self.base_url}/v1/portfolio/positions", headers=self._headers(), timeout=20)
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
        r = requests.get(f"{self.base_url}/v1/portfolio/account", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return float(r.json().get("available_balance") or 0.0)

    def test_connection(self) -> dict:
        if not self.configured:
            return {"ok": False, "detail": "No Ondo Finance API key configured."}
        try:
            r = requests.get(f"{self.base_url}/v1/portfolio/account", headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return {"ok": True, "detail": "Ondo Finance reachable and credentials accepted."}
            return {"ok": False, "detail": f"Ondo returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
