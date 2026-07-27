from __future__ import annotations

from typing import List
import requests

from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)
from modules.admin.tenant_api_keys import get_alpaca_credentials


class AlpacaNotConfigured(RuntimeError):
    """Raised when Alpaca is selected as the broker but no key/secret is
    configured anywhere (tenant key or platform secret/env). Callers
    should catch this and point the user at Settings > API Keys, the
    same way every other provider-gated feature in the app degrades."""
    pass


class AlpacaBroker(BrokerBase):
    name = "alpaca"

    def __init__(self, live: bool = False):
        creds = get_alpaca_credentials(paper=not live)
        self.api_key = creds["api_key"]
        self.api_secret = creds["api_secret"]
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

    def _require_configured(self):
        if not self.configured:
            raise AlpacaNotConfigured(
                "Alpaca isn't connected yet. Add your API key and secret in "
                "Admin > API Keys (or ask your tenant admin to), then try again."
            )

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        payload = {
            "symbol": req.symbol,
            "qty": str(req.qty),
            "side": req.side,
            "type": req.order_type,
            "time_in_force": req.tif,
        }
        if req.limit_price is not None:
            payload["limit_price"] = str(req.limit_price)
        if req.stop_price is not None:
            payload["stop_price"] = str(req.stop_price)

        r = requests.post(
            f"{self.base_url}/v2/orders",
            headers=self.headers,
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        return BrokerOrderResponse(
            broker_order_id=data["id"],
            status=data.get("status", "accepted"),
            symbol=data["symbol"],
            side=data["side"],
            qty=float(data["qty"]),
            filled_qty=float(data.get("filled_qty") or 0.0),
            avg_fill_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v2/orders/{broker_order_id}",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        return BrokerOrderResponse(
            broker_order_id=data["id"],
            status=data.get("status", "accepted"),
            symbol=data["symbol"],
            side=data["side"],
            qty=float(data["qty"]),
            filled_qty=float(data.get("filled_qty") or 0.0),
            avg_fill_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        self._require_configured()
        r = requests.delete(
            f"{self.base_url}/v2/orders/{broker_order_id}",
            headers=self.headers,
            timeout=20,
        )
        return r.status_code in (200, 204)

    def list_positions(self) -> List[BrokerPosition]:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v2/positions",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        rows = r.json()

        return [
            BrokerPosition(
                symbol=row["symbol"],
                qty=float(row["qty"]),
                avg_cost=float(row["avg_entry_price"]),
                market_price=float(row["current_price"]),
                market_value=float(row["market_value"]),
                unrealized_pnl=float(row["unrealized_pl"]),
            )
            for row in rows
        ]

    def get_buying_power(self) -> float:
        self._require_configured()
        r = requests.get(
            f"{self.base_url}/v2/account",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return float(data.get("buying_power") or 0.0)

    def test_connection(self) -> dict:
        """Lightweight connectivity check used by the API Keys admin UI --
        returns {"ok": bool, "detail": str} without raising."""
        if not self.configured:
            return {"ok": False, "detail": "No Alpaca key/secret configured."}
        try:
            r = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "ok": True,
                    "detail": f"Connected ({'paper' if 'paper' in self.base_url else 'live'}) — "
                              f"status={data.get('status', 'unknown')}, "
                              f"buying power=${float(data.get('buying_power') or 0):,.2f}",
                }
            return {"ok": False, "detail": f"Alpaca returned HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
