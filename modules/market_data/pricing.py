"""
modules/crypto/pricing.py

Crypto Reference Pricing

Maps a ccxt-unified pair symbol (e.g. "BTC/USDT") to a current
reference price via CoinGecko (modules.crypto.data_service) -- free,
no API key required, so this works even for a tenant that hasn't
configured real exchange credentials yet (paper trading only needs a
reference price, not a live exchange connection; real order execution
via modules.portfolio.brokers.ccxt_broker.CCXTBroker still requires
real credentials, as designed).

This exists because modules.market_data.service.get_latest_price_map()
(the shared price lookup modules.portfolio.order_service.
StockTradingService and modules.portfolio.brokers.paper.PaperBroker
both use for reference pricing) is a stock-ticker-specific pipeline --
its own symbol validator silently filters out anything containing "/"
before it would ever reach a provider. get_latest_price_map() detects
a ccxt-style symbol and routes here instead of through that filter;
everything else (plain stock tickers) is completely unaffected.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Curated mapping for the most commonly traded base currencies, so the
# common case resolves instantly without a network round-trip.
# Anything not listed here falls back to modules.crypto.data_service.
# search_coin() (a real CoinGecko search), so this list doesn't need to
# be exhaustive -- it's a fast path, not the only path.
_KNOWN_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "TRX": "tron",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LTC": "litecoin",
    "SHIB": "shiba-inu",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "XLM": "stellar",
    "XMR": "monero",
}

# Resolved base-currency -> CoinGecko id lookups, cached for the life
# of this process -- search_coin() is a real network call, and the
# same base currency (e.g. "BTC") gets looked up repeatedly across
# many order/price requests for the same or different pairs.
_id_cache: dict[str, Optional[str]] = {}


def is_crypto_pair_symbol(symbol: str) -> bool:
    """
    True for a ccxt-unified pair symbol like "BTC/USDT" -- unambiguous,
    since no stock ticker contains a "/". Crypto symbols passed through
    this platform's order/pricing paths should always use this
    convention (the same one ccxt itself uses), not a raw exchange-
    specific symbol like "BTCUSDT".
    """
    return "/" in str(symbol or "")


def _resolve_coingecko_id(base_currency: str) -> Optional[str]:
    base_currency = base_currency.upper().strip()

    if base_currency in _id_cache:
        return _id_cache[base_currency]

    if base_currency in _KNOWN_COINGECKO_IDS:
        _id_cache[base_currency] = _KNOWN_COINGECKO_IDS[base_currency]
        return _id_cache[base_currency]

    try:
        from modules.crypto.data_service import search_coin

        matches = search_coin(base_currency)
        exact = [m for m in matches if m.get("Symbol") == base_currency]
        chosen = exact[0] if exact else (matches[0] if matches else None)

        coin_id = chosen.get("id") if chosen else None
        _id_cache[base_currency] = coin_id
        return coin_id

    except Exception:
        logger.exception("Failed to resolve CoinGecko id for %s", base_currency)
        _id_cache[base_currency] = None
        return None


def get_latest_crypto_price(pair_symbol: str) -> Optional[float]:
    """
    Current reference price for a ccxt-unified pair symbol (e.g.
    "BTC/USDT"), quoted in the pair's quote currency. Returns None
    (not 0.0 -- a real price is never actually zero, so 0.0 would look
    like a valid-but-worthless quote rather than an honest "couldn't
    price this") if the base currency can't be resolved or CoinGecko
    is unreachable.

    Only USD-quoted pairs (USDT/USDC/USD) are supported today --
    CoinGecko's per-coin detail always includes a "usd" price, and
    stablecoins are priced ~1:1 with USD, which is the overwhelming
    majority of real trading pairs. A pair quoted in something else
    (e.g. "ETH/BTC") isn't priced by this function.
    """
    if not is_crypto_pair_symbol(pair_symbol):
        return None

    base, _, quote = str(pair_symbol).partition("/")
    base = base.upper().strip()
    quote = quote.upper().strip()

    if quote not in ("USDT", "USDC", "USD"):
        logger.info(
            "get_latest_crypto_price: unsupported quote currency %s for %s",
            quote, pair_symbol,
        )
        return None

    coin_id = _resolve_coingecko_id(base)
    if not coin_id:
        return None

    try:
        from modules.crypto.data_service import get_coin_detail

        detail = get_coin_detail(coin_id)

        # get_coin_detail() returns CoinGecko's raw /coins/{id} response
        # unmodified -- the price lives at market_data.current_price.usd,
        # not a top-level field.
        market_data = detail.get("market_data") or {}
        price = market_data.get("current_price", {}).get("usd")

        return float(price) if price is not None else None

    except Exception:
        logger.exception("Failed to fetch crypto price for %s (%s)", pair_symbol, coin_id)
        return None


def get_latest_crypto_price_map(pair_symbols: list[str]) -> dict[str, float]:
    """Batch version of get_latest_crypto_price(). Symbols that can't be priced are simply omitted, not zeroed."""
    out: dict[str, float] = {}
    for symbol in pair_symbols or []:
        price = get_latest_crypto_price(symbol)
        if price is not None:
            out[symbol] = price
    return out