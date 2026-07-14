"""
modules/tokenized_assets/base.py

Tokenized real-world assets (RWA) -- tokenized Treasuries, equities/ETFs,
private credit, commodities, real estate -- traded and held exactly like
any other broker connection in this app: same BrokerBase interface as
Alpaca/Tradier/IBKR, same PortfolioPosition table, same Risk Layer.

Why extend BrokerBase rather than build a parallel system: per the
research behind this feature (SEC's Jan 28, 2026 joint statement, the
March 17 SEC/CFTC digital-asset framework, and DTCC's May 2026 tokenized
securities pilot), a tokenized security is legally the same instrument as
its traditional form -- "if it's a security off-chain, it's a security
on-chain." So a tokenized Treasury or tokenized AAPL share should trade
and report through the exact same pipes a traditional one does, not a
side system. The only genuinely new thing a tokenized asset adds is
*where* it lives (chain, contract address, custodian) -- captured in
TokenizedAssetInfo below -- not a different trading/portfolio model.

TenantBrokerSetting (enable/disable) and Admin > API Keys (credentials)
are reused as-is -- these providers are registered in
modules.portfolio.brokers.factory.BROKER_REGISTRY alongside Alpaca/Tradier/
IBKR, so a tenant admin manages them from the same Brokers tab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from modules.portfolio.brokers.base import BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition

# Re-exported for convenience so provider modules only need one import.
__all__ = [
    "BrokerOrderRequest", "BrokerOrderResponse", "BrokerPosition",
    "TokenizedAssetInfo", "TokenizedAssetBroker",
]

# Underlying asset categories seen in the current tokenized-asset market
# (per RWA.xyz / DTCC / Ondo data as of mid-2026): Treasuries are the
# largest on-chain category, followed by private credit, tokenized gold,
# tokenized equities/ETFs, and (still small but growing) real estate.
UNDERLYING_TYPES = [
    "treasury", "private_credit", "commodity", "equity", "etf", "real_estate", "fund",
]


@dataclass
class TokenizedAssetInfo:
    symbol: str
    name: str
    underlying_type: str          # one of UNDERLYING_TYPES
    chain: str                    # e.g. "Ethereum", "Solana", "Polygon"
    contract_address: Optional[str]
    custodian: str                # e.g. "Ondo Finance", "Securitize"


class TokenizedAssetBroker(BrokerBase):
    """
    Same trading/positions/buying-power contract as any other broker
    (submit_order, get_order, cancel_order, list_positions, get_buying_power),
    plus one addition specific to tokenized assets: discovering which
    tokens are available to trade and what they represent.
    """

    def list_assets(self) -> List[TokenizedAssetInfo]:
        raise NotImplementedError

    def test_connection(self) -> dict:
        raise NotImplementedError
