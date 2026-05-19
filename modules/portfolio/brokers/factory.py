from __future__ import annotations

import streamlit as st

from modules.portfolio.brokers.paper import PaperBroker
from modules.portfolio.brokers.alpaca_broker import AlpacaBroker


def get_broker(market_data_service, broker_name: str | None = None, live: bool = False):
    broker_name = broker_name or st.secrets["trading"].get("DEFAULT_BROKER", "paper")

    if broker_name == "paper":
        return PaperBroker()

    if broker_name == "alpaca":
        return AlpacaBroker(live=live)

    raise ValueError(f"Unsupported broker: {broker_name}")