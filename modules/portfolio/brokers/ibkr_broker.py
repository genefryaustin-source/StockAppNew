"""
modules/portfolio/brokers/ibkr_broker.py

Interactive Brokers integration via the IBKR Client Portal Web API
(https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/).

IMPORTANT -- how this is different from Alpaca/Tradier:
IBKR retail accounts don't issue a static API key + secret. Programmatic
access goes through IBKR's "Client Portal Gateway", a process the user
runs themselves (locally or on a small always-on host) and logs into via
a browser, including 2FA. This app talks to that *already authenticated*
gateway over its local REST API -- it cannot perform the interactive
login for you, and doesn't try to.

Practically, that means:
  - There's no secret to type in beyond the gateway's URL and (optionally)
    an account id -- see get_ibkr_credentials() in tenant_api_keys.py.
  - The session can go stale (soft timeout ~ a few minutes of inactivity;
    hard logout after ~24h or a new device login). test_connection() /
    _ensure_authenticated() surface that clearly instead of failing
    silently, and attempt a silent /iserver/reauthenticate first.
  - Orders are placed by IBKR contract id (conid), not ticker symbol, so
    submit_order() resolves the symbol via /iserver/secdef/search first.
  - IBKR frequently returns an order "reply" requiring confirmation of a
    compliance warning (e.g. price-outside-range) before it actually
    routes. submit_order() auto-confirms the first such reply once.

The exact JSON field names on IBKR's Client Portal API have shifted
across gateway versions and aren't as strictly versioned as Alpaca's or
Tradier's REST APIs. If a call here breaks against your gateway version,
check the live docs served by your own gateway at {base_url}/../doc/
and adjust field names accordingly.
"""

from __future__ import annotations

from typing import List, Optional
import requests
import urllib3

from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)
from modules.admin.tenant_api_keys import get_ibkr_credentials

# The Client Portal Gateway typically serves a self-signed cert on
# localhost. We disable the InsecureRequestWarning noise that produces,
# but still default verify=True below -- callers running a gateway with a
# self-signed cert should pass verify_ssl=False explicitly.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class IBKRNotConfigured(RuntimeError):
    pass


class IBKRNotAuthenticated(RuntimeError):
    """Raised when the gateway is reachable but the browser session isn't
    logged in (or has timed out). There is no programmatic fix for this --
    the user has to open the gateway's login page and sign in again."""
    pass


class IBKRBroker(BrokerBase):
    name = "ibkr"

    def __init__(self, verify_ssl: bool = True):
        creds = get_ibkr_credentials()
        self.account_id: Optional[str] = creds["account_id"] or None
        self.base_url = creds["base_url"]
        self.configured = creds["configured"]
        self.verify_ssl = verify_ssl

    # ── Session plumbing ────────────────────────────────────────

    def _get(self, path: str, **kw):
        return requests.get(f"{self.base_url}{path}", timeout=kw.pop("timeout", 15),
                             verify=self.verify_ssl, **kw)

    def _post(self, path: str, **kw):
        return requests.post(f"{self.base_url}{path}", timeout=kw.pop("timeout", 15),
                              verify=self.verify_ssl, **kw)

    def _delete(self, path: str, **kw):
        return requests.delete(f"{self.base_url}{path}", timeout=kw.pop("timeout", 15),
                                verify=self.verify_ssl, **kw)

    def _require_configured(self):
        if not self.configured:
            raise IBKRNotConfigured(
                "Interactive Brokers isn't set up yet. Add your Client Portal Gateway URL "
                "(and optionally account ID) in Admin > API Keys."
            )

    def _ensure_authenticated(self) -> dict:
        """Checks /iserver/auth/status, attempts one silent reauth if the
        session is just soft-timed-out, and raises IBKRNotAuthenticated
        with a clear, actionable message if the user needs to log back in."""
        self._require_configured()
        try:
            r = self._get("/iserver/auth/status")
            r.raise_for_status()
            status = r.json()
        except Exception as e:
            raise IBKRNotAuthenticated(
                f"Could not reach the IBKR Client Portal Gateway at {self.base_url}: {e}. "
                "Make sure the gateway is running."
            )

        if status.get("authenticated"):
            return status

        # Soft timeout -- try one silent reauth before giving up.
        try:
            self._post("/iserver/reauthenticate")
            r = self._get("/iserver/auth/status")
            status = r.json()
        except Exception:
            pass

        if not status.get("authenticated"):
            raise IBKRNotAuthenticated(
                "Your IBKR gateway session isn't logged in. Open the gateway's login "
                f"page (usually {self.base_url.replace('/v1/api', '')}) in a browser, "
                "sign in (including 2FA), then try again."
            )
        return status

    def _ensure_account_id(self) -> str:
        if self.account_id:
            return self.account_id
        r = self._get("/iserver/accounts")
        r.raise_for_status()
        data = r.json()
        accounts = data.get("accounts") or []
        if not accounts:
            raise IBKRNotAuthenticated("No IBKR accounts visible on this session.")
        self.account_id = data.get("selectedAccount") or accounts[0]
        return self.account_id

    def _resolve_conid(self, symbol: str) -> str:
        """IBKR orders are placed by numeric contract id, not ticker symbol."""
        r = self._get("/iserver/secdef/search", params={"symbol": symbol})
        r.raise_for_status()
        results = r.json()
        if not results:
            raise ValueError(f"IBKR couldn't resolve a contract for symbol {symbol!r}.")
        # Prefer an exact, primary-exchange stock match if present.
        for row in results:
            if row.get("symbol") == symbol.upper() and row.get("secType", "STK") == "STK":
                return str(row["conid"])
        return str(results[0]["conid"])

    # ── BrokerBase interface ────────────────────────────────────

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._ensure_authenticated()
        account_id = self._ensure_account_id()
        conid = self._resolve_conid(req.symbol)

        order_type_map = {"market": "MKT", "limit": "LMT", "stop": "STP", "stop_limit": "STP_LMT"}
        order = {
            "conid": int(conid),
            "orderType": order_type_map.get(req.order_type, "MKT"),
            "side": req.side.upper(),
            "quantity": req.qty,
            "tif": "GTC" if req.tif == "gtc" else "DAY",
        }
        if req.limit_price is not None:
            order["price"] = req.limit_price
        if req.stop_price is not None:
            order["auxPrice"] = req.stop_price

        r = self._post(f"/iserver/account/{account_id}/orders", json={"orders": [order]})
        r.raise_for_status()
        data = r.json()

        # IBKR may respond with a confirmation prompt (list of {id, message})
        # instead of an order id -- auto-confirm it once.
        if isinstance(data, list) and data and "id" in data[0] and "orderId" not in data[0]:
            reply_id = data[0]["id"]
            r2 = self._post(f"/iserver/reply/{reply_id}", json={"confirmed": True})
            r2.raise_for_status()
            data = r2.json()

        row = data[0] if isinstance(data, list) and data else data
        return BrokerOrderResponse(
            broker_order_id=str(row.get("order_id") or row.get("orderId") or ""),
            status=row.get("order_status") or row.get("status", "submitted"),
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            filled_qty=0.0,
            avg_fill_price=None,
        )

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        self._ensure_authenticated()
        r = self._get(f"/iserver/account/order/status/{broker_order_id}")
        r.raise_for_status()
        data = r.json()
        return BrokerOrderResponse(
            broker_order_id=str(broker_order_id),
            status=data.get("order_status", "unknown"),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            qty=float(data.get("size") or data.get("totalSize") or 0.0),
            filled_qty=float(data.get("filledQuantity") or 0.0),
            avg_fill_price=float(data["avgPrice"]) if data.get("avgPrice") else None,
        )

    def cancel_order(self, broker_order_id: str) -> bool:
        self._ensure_authenticated()
        account_id = self._ensure_account_id()
        r = self._delete(f"/iserver/account/{account_id}/order/{broker_order_id}")
        return r.status_code == 200

    def list_positions(self) -> List[BrokerPosition]:
        self._ensure_authenticated()
        account_id = self._ensure_account_id()
        r = self._get(f"/portfolio/{account_id}/positions/0")
        r.raise_for_status()
        rows = r.json() or []
        return [
            BrokerPosition(
                symbol=row.get("contractDesc") or row.get("ticker") or "",
                qty=float(row.get("position") or 0.0),
                avg_cost=float(row.get("avgCost") or 0.0),
                market_price=float(row.get("mktPrice") or 0.0),
                market_value=float(row.get("mktValue") or 0.0),
                unrealized_pnl=float(row.get("unrealizedPnl") or 0.0),
            )
            for row in rows
        ]

    def get_buying_power(self) -> float:
        self._ensure_authenticated()
        account_id = self._ensure_account_id()
        r = self._get(f"/portfolio/{account_id}/summary")
        r.raise_for_status()
        data = r.json() or {}
        for key in ("buyingpower", "buyingPower", "availablefunds", "availableFunds"):
            entry = data.get(key)
            if isinstance(entry, dict) and entry.get("amount") is not None:
                return float(entry["amount"])
        return 0.0

    def test_connection(self) -> dict:
        """Live connectivity + session check used by the API Keys admin UI."""
        if not self.configured:
            return {"ok": False, "detail": "No IBKR gateway URL configured."}
        try:
            status = self._ensure_authenticated()
            account_id = self._ensure_account_id()
            return {
                "ok": True,
                "detail": f"Gateway reachable and logged in — account {account_id} "
                          f"(connected={status.get('connected')}).",
            }
        except IBKRNotAuthenticated as e:
            return {"ok": False, "detail": str(e)}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
