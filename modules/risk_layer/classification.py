"""
modules/risk_layer/classification.py

Infers asset class from a symbol so the Risk Layer can segment cross-asset
positions without needing a schema change to PortfolioPosition. This is a
best-effort read-side classifier, not a source of truth -- if a future
asset class (e.g. real-world assets) needs a hard guarantee rather than a
guess, tag it explicitly via the `known_asset_class` override map below or
extend the regexes as new symbol conventions show up (e.g. a specific RWA
token/CUSIP format).
"""

from __future__ import annotations

import re

ASSET_CLASSES = ["equity", "option", "crypto", "forex", "real_world_asset"]

# OCC option symbol: root (1-6 letters) + YYMMDD + C/P + 8-digit strike.
_OPTION_RE = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")

# Common forex pair conventions: EURUSD, EUR/USD, EUR-USD.
_FOREX_RE = re.compile(r"^[A-Z]{3}[/\-]?[A-Z]{3}$")
_FOREX_CCY = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNH", "SEK",
    "NOK", "MXN", "ZAR", "TRY", "SGD", "HKD",
}

# Crypto tickers/quote-currency suffixes as used by Alpaca/most crypto venues.
_CRYPTO_SUFFIXES = ("USD", "USDT", "USDC", "BTC", "ETH")
_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "DOGE", "LTC", "BCH", "AVAX", "LINK", "UNI", "AAVE",
    "MATIC", "AVAX", "AAVE", "AVAX", "DOT", "AVAX", "SHIB", "AVAX", "XRP",
}

# Manual overrides for symbols the regexes can't distinguish (e.g. a real
# world asset's on-chain ticker, or a broker-specific format). Populate as
# real-world-asset support is added.
known_asset_class: dict[str, str] = {}


def classify_asset_class(symbol: str) -> str:
    if not symbol:
        return "equity"
    sym = str(symbol).strip().upper()

    if sym in known_asset_class:
        return known_asset_class[sym]

    if _OPTION_RE.match(sym):
        return "option"

    compact = sym.replace("/", "").replace("-", "")
    if len(compact) == 6 and compact.isalpha():
        left, right = compact[:3], compact[3:]
        if left in _FOREX_CCY and right in _FOREX_CCY:
            return "forex"

    for suffix in _CRYPTO_SUFFIXES:
        if compact.endswith(suffix) and compact[:-len(suffix)] in _CRYPTO_BASES:
            return "crypto"
    if compact in _CRYPTO_BASES:
        return "crypto"

    return "equity"


def register_real_world_asset(symbol: str) -> None:
    """Call this once RWA support lands so the classifier can tag it
    correctly without guessing -- e.g. register_real_world_asset("TBILL-3M")."""
    known_asset_class[str(symbol).strip().upper()] = "real_world_asset"
