from __future__ import annotations

import streamlit as st

from modules.portfolio.brokers.paper import PaperBroker
from modules.portfolio.brokers.alpaca_broker import AlpacaBroker
from modules.portfolio.brokers.tradier_broker import TradierBroker
from modules.portfolio.brokers.ibkr_broker import IBKRBroker
from modules.tokenized_assets.ondo_provider import OndoProvider
from modules.tokenized_assets.securitize_provider import SecuritizeProvider
from modules.tokenized_assets.custom_provider import CustomTokenizedAssetProvider
from modules.portfolio.brokers.ccxt_broker import CCXTBroker

# Registry of connectable broker/execution providers. Adding a new broker
# means: build a Broker subclass in this package following base.BrokerBase,
# register its credentials in modules/admin/tenant_api_keys.KNOWN_PROVIDERS
# (so it gets the same tenant-key UI as every other provider), and add one
# line here.
BROKER_REGISTRY = {
    "paper": lambda market_data_service, live: PaperBroker(market_data_service=market_data_service),
    "alpaca": lambda market_data_service, live: AlpacaBroker(live=live),
    # Tradier's "live" flag maps to sandbox=not live, same paper/live sense
    # as Alpaca -- sandbox by default unless the caller explicitly asks
    # for live trading.
    "tradier": lambda market_data_service, live: TradierBroker(sandbox=not live),
    # IBKR has no paper/live URL split at the API level -- which account
    # (paper or live) you're trading is determined by which account is
    # logged into the gateway, not by this flag.
    "ibkr": lambda market_data_service, live: IBKRBroker(),
    # Tokenized real-world assets -- traded and held exactly like any
    # other broker; positions land in the same PortfolioPosition table
    # and get full Trading & Execution / Risk Layer parity automatically.
    "ondo": lambda market_data_service, live: OndoProvider(),
    "securitize": lambda market_data_service, live: SecuritizeProvider(),
    "tokenized_custom": lambda market_data_service, live: CustomTokenizedAssetProvider(),
    # Real crypto exchange execution (Binance/Coinbase/Kraken/etc, one
    # unified API via ccxt) -- fills the gap left by the Crypto Portfolio
    # Tracker, which only ever recorded manually-entered holdings.
    "ccxt": lambda market_data_service, live: CCXTBroker(sandbox=not live),
}


def available_brokers() -> list[str]:
    return list(BROKER_REGISTRY.keys())


def get_broker(market_data_service, broker_name: str | None = None, live: bool = False):
    broker_name = broker_name or st.secrets.get("trading", {}).get("DEFAULT_BROKER", "paper")

    factory_fn = BROKER_REGISTRY.get(broker_name)
    if factory_fn is None:
        raise ValueError(
            f"Unsupported broker: {broker_name!r}. Available: {', '.join(available_brokers())}"
        )
    return factory_fn(market_data_service, live)
