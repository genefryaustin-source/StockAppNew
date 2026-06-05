"""
modules/options/options_broker.py

Alpaca options order execution + position management.
Alpaca API v2 options endpoints:
  GET  /v2/options/contracts?underlying_symbols=AAPL
  POST /v2/orders  { class: "option", asset_class: "us_option" }
  GET  /v2/positions  (includes options)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional
import requests
import streamlit as st


@dataclass
class OptionsOrderRequest:
    option_symbol: str    # OCC format: AAPL240119C00150000
    qty:           int
    side:          str    # buy | sell
    order_type:    str = "limit"   # limit | market
    tif:           str = "day"
    limit_price:   Optional[float] = None


@dataclass
class OptionsOrderResponse:
    order_id:    str
    status:      str
    symbol:      str
    side:        str
    qty:         int
    filled_qty:  float = 0.0
    fill_price:  Optional[float] = None
    error:       Optional[str] = None


@dataclass
class OptionsPosition:
    option_symbol:  str
    underlying:     str
    qty:            float
    avg_cost:       float
    market_value:   float
    unrealized_pnl: float
    expiry:         str = ""
    strike:         float = 0.0
    option_type:    str = ""  # call | put
    dte:            int = 0
    delta:          Optional[float] = None


class AlpacaOptionsBroker:
    def __init__(self, paper: bool = True):
        try:
            cfg = st.secrets["alpaca"]
            self.key    = cfg["API_KEY"]
            self.secret = cfg["API_SECRET"]
            self.base   = cfg.get("BASE_URL_PAPER") if paper else cfg.get("BASE_URL_LIVE")
            if not self.base:
                self.base = ("https://paper-api.alpaca.markets"
                             if paper else "https://api.alpaca.markets")
        except Exception:
            self.key    = os.getenv("ALPACA_API_KEY","")
            self.secret = os.getenv("ALPACA_API_SECRET","")
            self.base   = ("https://paper-api.alpaca.markets"
                           if paper else "https://api.alpaca.markets")

        self.headers = {
            "APCA-API-KEY-ID":     self.key,
            "APCA-API-SECRET-KEY": self.secret,
            "Content-Type":        "application/json",
            "Accept":              "application/json",
        }
        self.paper = paper

    def _get(self, path: str, params: dict = None):
        r = requests.get(f"{self.base}{path}",
                         headers=self.headers, params=params or {}, timeout=15)
        return r

    def _post(self, path: str, payload: dict):
        r = requests.post(f"{self.base}{path}",
                          headers=self.headers, json=payload, timeout=15)
        return r

    # ── Account ──────────────────────────────────────────────
    def get_account(self) -> dict:
        try:
            r = self._get("/v2/account")
            return r.json() if r.status_code == 200 else {"error": r.text}
        except Exception as e:
            return {"error": str(e)}

    def get_buying_power(self) -> float:
        acc = self.get_account()
        return float(acc.get("buying_power") or acc.get("options_buying_power") or 0)

    # ── Contracts lookup ──────────────────────────────────────
    def get_contracts(self, underlying: str, expiry: str = None,
                      option_type: str = None) -> list[dict]:
        """
        Lookup available option contracts via Alpaca's contracts endpoint.
        GET /v2/options/contracts?underlying_symbols=AAPL
        """
        try:
            params = {"underlying_symbols": underlying.upper(), "limit": 1000}
            if expiry:
                params["expiration_date"] = expiry
            if option_type:
                params["type"] = option_type
            r = self._get("/v2/options/contracts", params)
            if r.status_code == 200:
                data = r.json()
                return data if isinstance(data, list) else data.get("option_contracts", [])
            return []
        except Exception:
            return []

    # ── Order submission ──────────────────────────────────────
    def submit_order(self, req: OptionsOrderRequest) -> OptionsOrderResponse:
        payload = {
            "symbol":          req.option_symbol,
            "qty":             str(req.qty),
            "side":            req.side,
            "type":            req.order_type,
            "time_in_force":   req.tif,
            "order_class":     "simple",
        }
        if req.limit_price is not None:
            payload["limit_price"] = str(round(req.limit_price, 2))

        try:
            r = self._post("/v2/orders", payload)
            data = r.json()
            if r.status_code in (200, 201):
                return OptionsOrderResponse(
                    order_id   = data["id"],
                    status     = data.get("status","submitted"),
                    symbol     = data["symbol"],
                    side       = data["side"],
                    qty        = int(float(data.get("qty",req.qty))),
                    filled_qty = float(data.get("filled_qty") or 0),
                    fill_price = float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
                )
            return OptionsOrderResponse(
                order_id="", status="error", symbol=req.option_symbol,
                side=req.side, qty=req.qty, error=data.get("message", r.text[:200])
            )
        except Exception as e:
            return OptionsOrderResponse(
                order_id="", status="error", symbol=req.option_symbol,
                side=req.side, qty=req.qty, error=str(e)
            )

    def cancel_order(self, order_id: str) -> bool:
        try:
            r = requests.delete(f"{self.base}/v2/orders/{order_id}",
                                headers=self.headers, timeout=10)
            return r.status_code in (200, 204)
        except: return False

    def list_orders(self, status: str = "open") -> list[dict]:
        try:
            r = self._get("/v2/orders", {"status": status, "limit": 100})
            return r.json() if r.status_code == 200 else []
        except: return []

    # ── Positions ─────────────────────────────────────────────
    def list_options_positions(self) -> list[OptionsPosition]:
        """
        GET /v2/positions — filter to options (asset_class == us_option).
        """
        try:
            r = self._get("/v2/positions")
            if r.status_code != 200:
                return []
            positions = []
            for p in (r.json() or []):
                if p.get("asset_class") != "us_option":
                    continue
                sym  = p.get("symbol","")
                # Parse OCC symbol: AAPL240119C00150000
                try:
                    underlying  = sym[:-(15)]
                    exp_part    = sym[-15:-9]
                    opt_type    = "call" if sym[-9] == "C" else "put"
                    strike_raw  = sym[-8:]
                    strike      = int(strike_raw) / 1000.0
                    expiry      = f"20{exp_part[:2]}-{exp_part[2:4]}-{exp_part[4:6]}"
                    from modules.options.options_data_service import _calc_dte
                    dte = _calc_dte(expiry) or 0
                except Exception:
                    underlying = sym; opt_type = ""; strike = 0.0; expiry = ""; dte = 0

                positions.append(OptionsPosition(
                    option_symbol  = sym,
                    underlying     = underlying,
                    qty            = float(p.get("qty",0)),
                    avg_cost       = float(p.get("avg_entry_price",0)),
                    market_value   = float(p.get("market_value",0)),
                    unrealized_pnl = float(p.get("unrealized_pl",0)),
                    expiry         = expiry,
                    strike         = strike,
                    option_type    = opt_type,
                    dte            = dte,
                ))
            return positions
        except Exception as e:
            print(f"[options broker] positions error: {e}")
            return []

