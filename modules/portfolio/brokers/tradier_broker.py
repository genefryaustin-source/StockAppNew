"""
modules/portfolio/brokers/tradier_broker.py

Tradier brokerage integration (https://tradier.com/products/brokerage-api).
Tradier authenticates with a single bearer access token and scopes every
call to an account id -- both are resolved the same way as every other
provider in the app (tenant key first, platform fallback second) via
modules.admin.tenant_api_keys.get_tradier_credentials.

Sandbox (paper) and production use identical endpoints on different hosts:
  sandbox:    https://sandbox.tradier.com
  production: https://api.tradier.com
"""

from __future__ import annotations

from typing import List
import requests

from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)
from modules.admin.tenant_api_keys import get_tradier_credentials


class TradierNotConfigured(RuntimeError):
    """Raised when Tradier is selected but no access token / account id is
    configured anywhere. Callers should catch this and point the user at
    Admin > API Keys, same as every other provider-gated feature."""
    pass


# Tradier's side vocabulary differs slightly from Alpaca's simple buy/sell --
# it distinguishes opening/closing and long/short for equities. We accept
# the common "buy"/"sell" from the rest of the app and map it to Tradier's
# expected values; callers that need short-selling or covering can pass
# Tradier's own side strings straight through (they're left untouched).
_SIDE_MAP = {"buy": "buy", "sell": "sell"}


class TradierBroker(BrokerBase):
    name = "tradier"

    def __init__(self, sandbox: bool = True):
        creds = get_tradier_credentials(sandbox=sandbox)
        self.access_token = creds["access_token"]
        self.account_id = creds["account_id"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _require_configured(self):
        if not self.configured:
            raise TradierNotConfigured(
                "Tradier isn't connected yet. Add your access token and account ID "
                "in Admin > API Keys (or ask your tenant admin to), then try again."
            )

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        payload = {
            "class": "equity",
            "symbol": req.symbol,
            "side": _SIDE_MAP.get(req.side, req.side),
            "quantity": str(req.qty),
            "type": req.order_type,
            "duration": req.tif if req.tif in ("day", "gtc", "pre", "post") else "day",
        }
        if req.limit_price is not None:
            payload["price"] = str(req.limit_price)
        if req.stop_price is not None:
            payload["stop"] = str(req.stop_price)

        r = requests.post(
            f"{self.base_url}/v1/accounts/{self.account_id}/orders",
            headers=self.headers,
            data=payload,  # Tradier expects form-encoded, not JSON
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("order", {})

        return BrokerOrderResponse(
            broker_order_id=str(data.get("id", "")),
            status=data.get("status", "ok"),
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            filled_qty=0.0,
            avg_fill_price=None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v1/accounts/{self.account_id}/orders/{broker_order_id}",
            headers=self.headers,
            params={"includeTags": "false"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("order", {})

        return BrokerOrderResponse(
            broker_order_id=str(data.get("id", broker_order_id)),
            status=data.get("status", "unknown"),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            qty=float(data.get("quantity") or 0.0),
            filled_qty=float(data.get("exec_quantity") or 0.0),
            avg_fill_price=float(data["avg_fill_price"]) if data.get("avg_fill_price") else None,
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        self._require_configured()
        r = requests.delete(
            f"{self.base_url}/v1/accounts/{self.account_id}/orders/{broker_order_id}",
            headers=self.headers,
            timeout=20,
        )
        return r.status_code == 200

    def list_positions(self) -> List[BrokerPosition]:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v1/accounts/{self.account_id}/positions",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json().get("positions", {})
        if raw in (None, "null", ""):
            return []
        rows = raw.get("position", [])
        if isinstance(rows, dict):
            rows = [rows]

        out = []
        for row in rows:
            qty = float(row.get("quantity") or 0.0)
            cost_basis = float(row.get("cost_basis") or 0.0)
            avg_cost = (cost_basis / qty) if qty else 0.0
            out.append(BrokerPosition(
                symbol=row.get("symbol", ""),
                qty=qty,
                avg_cost=avg_cost,
                market_price=0.0,   # Tradier's position payload has no live mark;
                market_value=0.0,   # pull quotes separately via /v1/markets/quotes if needed.
                unrealized_pnl=0.0,
            ))
        return out

    def get_buying_power(self) -> float:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v1/accounts/{self.account_id}/balances",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        bal = r.json().get("balances", {})

        margin = bal.get("margin") or {}
        cash = bal.get("cash") or {}
        for candidate in (
            margin.get("stock_buying_power"),
            margin.get("option_buying_power"),
            cash.get("cash_available"),
            bal.get("total_cash"),
        ):
            if candidate is not None:
                return float(candidate)
        return 0.0

    def test_connection(self) -> dict:
        """Lightweight connectivity check used by the API Keys admin UI."""
        if not self.configured:
            return {"ok": False, "detail": "No Tradier access token / account ID configured."}
        try:
            r = requests.get(
                f"{self.base_url}/v1/accounts/{self.account_id}/balances",
                headers=self.headers, timeout=10,
            )
            if r.status_code == 200:
                bal = r.json().get("balances", {})
                mode = "sandbox" if "sandbox" in self.base_url else "production"
                return {
                    "ok": True,
                    "detail": f"Connected ({mode}) — account type={bal.get('account_type', 'unknown')}, "
                              f"total equity=${float(bal.get('total_equity') or 0):,.2f}",
                }
            return {"ok": False, "detail": f"Tradier returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
