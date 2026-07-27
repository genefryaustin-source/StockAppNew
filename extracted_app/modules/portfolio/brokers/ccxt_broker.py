"""
modules/portfolio/brokers/ccxt_broker.py

Real crypto exchange execution via ccxt (https://github.com/ccxt/ccxt,
MIT license) -- one unified API across 100+ exchanges (Binance, Coinbase,
Kraken, and so on). This is the missing piece for crypto: every other
asset class (equities via Alpaca/Tradier/IBKR, tokenized assets via
Ondo/Securitize) now has real broker execution, but crypto only had the
manual Portfolio Tracker. This closes that gap using the same BrokerBase
contract as everything else.

Which exchange a tenant trades is configurable (CCXT_EXCHANGE_ID, default
"binance") -- ccxt's unified API means switching exchanges is a config
change, not a code change. API key/secret are resolved the same way as
every other provider (tenant key first, platform fallback second).
"""

from __future__ import annotations

from typing import List
import ccxt

from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)
from modules.admin.tenant_api_keys import get_ccxt_credentials


class CCXTNotConfigured(RuntimeError):
    pass


class CCXTBroker(BrokerBase):
    name = "ccxt"

    def __init__(self, sandbox: bool = True):
        creds = get_ccxt_credentials()
        self.exchange_id = creds["exchange_id"]
        self.api_key = creds["api_key"]
        self.api_secret = creds["api_secret"]
        self.configured = creds["configured"]
        self.exchange = None

        if self.configured:
            try:
                exchange_class = getattr(ccxt, self.exchange_id)
                self.exchange = exchange_class({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,
                })
                if sandbox and self.exchange.has.get("sandbox"):
                    self.exchange.set_sandbox_mode(True)
            except AttributeError:
                self.configured = False
                self._config_error = f"Unknown exchange id: {self.exchange_id!r}"

    def _require_configured(self):
        if not self.configured or self.exchange is None:
            raise CCXTNotConfigured(
                f"No crypto exchange connected (exchange={self.exchange_id!r}). Add your API "
                "key/secret in Admin > API Keys, then try again."
            )

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        self._require_configured()
        order_type = "limit" if req.order_type == "limit" else "market"
        data = self.exchange.create_order(
            symbol=req.symbol, type=order_type, side=req.side,
            amount=req.qty, price=req.limit_price,
        )
        return BrokerOrderResponse(
            broker_order_id=str(data.get("id", "")),
            status=data.get("status") or "submitted",
            symbol=req.symbol, side=req.side, qty=req.qty,
            filled_qty=float(data.get("filled") or 0.0),
            avg_fill_price=float(data["average"]) if data.get("average") else None,
        )

    def get_order(self, broker_order_id: str, symbol: str = None) -> BrokerOrderResponse:
        self._require_configured()
        data = self.exchange.fetch_order(broker_order_id, symbol)
        return BrokerOrderResponse(
            broker_order_id=str(broker_order_id), status=data.get("status") or "unknown",
            symbol=data.get("symbol", symbol or ""), side=data.get("side", ""),
            qty=float(data.get("amount") or 0.0), filled_qty=float(data.get("filled") or 0.0),
            avg_fill_price=float(data["average"]) if data.get("average") else None,
        )

    def cancel_order(self, broker_order_id: str, symbol: str = None) -> bool:
        self._require_configured()
        try:
            self.exchange.cancel_order(broker_order_id, symbol)
            return True
        except Exception:
            return False

    def list_positions(self) -> List[BrokerPosition]:
        """
        Most centralized exchanges are spot-balance based, not
        position-based like a margin broker -- this reports each
        non-zero balance as a "position" at its current market price
        against the exchange's configured quote currency (default USDT).
        """
        self._require_configured()
        balance = self.exchange.fetch_balance()
        totals = balance.get("total", {})
        quote = "USDT"
        positions = []
        for asset, qty in totals.items():
            qty = float(qty or 0.0)
            if qty <= 0 or asset == quote:
                continue
            symbol = f"{asset}/{quote}"
            price = 0.0
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                price = float(ticker.get("last") or 0.0)
            except Exception:
                continue  # pair not listed against this quote currency -- skip rather than guess
            positions.append(BrokerPosition(
                symbol=asset, qty=qty, avg_cost=price, market_price=price,
                market_value=qty * price, unrealized_pnl=0.0,
            ))
        return positions

    def get_buying_power(self) -> float:
        self._require_configured()
        balance = self.exchange.fetch_balance()
        free = balance.get("free", {})
        return float(free.get("USDT") or free.get("USD") or 0.0)

    def test_connection(self) -> dict:
        if not self.configured or self.exchange is None:
            return {"ok": False, "detail": getattr(self, "_config_error",
                     "No crypto exchange API key/secret configured.")}
        try:
            balance = self.exchange.fetch_balance()
            n_assets = len([a for a, q in balance.get("total", {}).items() if float(q or 0) > 0])
            return {"ok": True, "detail": f"Connected to {self.exchange_id} — {n_assets} non-zero balance(s)."}
        except Exception as e:
            return {"ok": False, "detail": f"Connection failed: {e}"}
