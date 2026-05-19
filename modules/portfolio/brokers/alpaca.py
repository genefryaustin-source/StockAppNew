import requests
import streamlit as st
from modules.portfolio.brokers.base import BrokerOrderRequest, BrokerOrderResponse


class AlpacaBroker:
    name = "alpaca"

    def __init__(self, market_data_service, live=False):
        self.market_data_service = market_data_service

        cfg = st.secrets["alpaca"]

        self.base_url = cfg["BASE_URL_LIVE"] if live else cfg["BASE_URL_PAPER"]
        self.headers = {
            "APCA-API-KEY-ID": cfg["API_KEY"],
            "APCA-API-SECRET-KEY": cfg["API_SECRET"],
        }

    def submit_order(self, req: BrokerOrderRequest):
        payload = {
            "symbol": req.symbol,
            "qty": req.qty,
            "side": req.side,
            "type": req.order_type,
            "time_in_force": req.tif,
        }

        if req.limit_price:
            payload["limit_price"] = req.limit_price

        if req.stop_price:
            payload["stop_price"] = req.stop_price

        r = requests.post(
            f"{self.base_url}/v2/orders",
            json=payload,
            headers=self.headers,
            timeout=10
        )

        data = r.json()

        return BrokerOrderResponse(
            broker_order_id=data.get("id"),
            symbol=data.get("symbol"),
            side=data.get("side"),
            qty=float(data.get("qty", 0)),
            filled_qty=float(data.get("filled_qty", 0)),
            avg_fill_price=float(data.get("filled_avg_price") or 0),
            status=data.get("status"),
        )

    def get_buying_power(self):
        r = requests.get(
            f"{self.base_url}/v2/account",
            headers=self.headers,
            timeout=5
        )
        return float(r.json().get("buying_power", 0))