from __future__ import annotations

from typing import List
import requests
import streamlit as st

from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)


class AlpacaBroker(BrokerBase):
    name = "alpaca"

    def __init__(self, live: bool = False):
        cfg = st.secrets["alpaca"]
        self.api_key = cfg["API_KEY"]
        self.api_secret = cfg["API_SECRET"]
        self.base_url = cfg["BASE_URL_LIVE"] if live else cfg["BASE_URL_PAPER"]
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
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
        r = requests.delete(
            f"{self.base_url}/v2/orders/{broker_order_id}",
            headers=self.headers,
            timeout=20,
        )
        return r.status_code in (200, 204)

    def list_positions(self) -> List[BrokerPosition]:
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
        r = requests.get(
            f"{self.base_url}/v2/account",
            headers=self.headers,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return float(data.get("buying_power") or 0.0)