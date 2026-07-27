"""
modules/crypto/pricing.py

Crypto Reference Pricing

Maps a ccxt-unified pair symbol (e.g. "BTC/USDT") to a current
reference price. Tries two independent sources, in order:

1. A public, unauthenticated ccxt ticker fetch against whichever
   exchange this tenant has configured (CCXT_EXCHANGE_ID, default
   "binance") -- the same library modules.portfolio.brokers.
   ccxt_broker.CCXTBroker uses for real order execution, and the
   actual price that exchange would fill against. No API credentials
   are needed for this: fetching a ticker is public market data on
   virtually every exchange ccxt supports, so this works even for a
   tenant that hasn't configured real trading credentials yet.

2. CoinGecko (modules.crypto.data_service), as a fallback if the
   first fails -- e.g. the pair isn't listed on that exchange, or the
   exchange itself is unreachable.

This two-source design exists because CoinGecko's free-tier API is
aggressively rate-limited and shared across this whole application
(every page that shows coin data uses it) -- a real, reported failure
was every crypto order getting rejected with "Unable to get reference
price" the moment CoinGecko started rate-limiting this instance, with
nothing else to fall back to. ccxt's public ticker endpoints don't
share that rate limit at all.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Curated mapping for the most commonly traded base currencies, so the
# CoinGecko fallback's common case resolves instantly without a
# network round-trip for id resolution. Anything not listed here falls
# back to modules.crypto.data_service.search_coin() (a real CoinGecko
# search), so this list doesn't need to be exhaustive -- it's a fast
# path, not the only path.
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
# of this process.
_id_cache: dict[str, Optional[str]] = {}

# Public (no credentials) ccxt exchange instances, cached by exchange
# id for the life of this process -- constructing one isn't free (it
# loads market metadata on first real use), and many price lookups in
# a row commonly target the same exchange.
_public_exchange_cache: dict[str, object] = {}

# Detailed failure reasons from the most recent lookup per symbol,
# checked by modules.portfolio.order_service._get_reference_price when
# a crypto lookup fails, so a rejected order's message can say exactly
# what was tried and why instead of a generic "unable to get reference
# price" -- populated during the normal lookup below, so consulting
# this after a failure doesn't cost a second network round-trip.
_last_errors: dict[str, list[str]] = {}


def get_last_pricing_errors(pair_symbol: str) -> list[str]:
    """
    "exchange_or_source: reason" strings from the most recent failed
    get_latest_crypto_price() call for this symbol, or [] if it hasn't
    failed (or hasn't been looked up at all) recently.
    """
    return list(_last_errors.get(pair_symbol, []))


def is_crypto_pair_symbol(symbol: str) -> bool:
    """
    True for a ccxt-unified pair symbol like "BTC/USDT" -- unambiguous,
    since no stock ticker contains a "/". Crypto symbols passed through
    this platform's order/pricing paths should always use this
    convention (the same one ccxt itself uses), not a raw exchange-
    specific symbol like "BTCUSDT".
    """
    return "/" in str(symbol or "")


# Fallback chain of public, US-accessible exchanges to try for ticker
# pricing, tried in order after the tenant's own configured exchange
# (if different). binance.com specifically blocks connections from US
# IP addresses -- a real geo-restriction, not a rate limit -- so a
# deployment whose only ccxt price source was "whatever CCXT_EXCHANGE_ID
# defaults to" (binance) would have that path fail consistently for any
# US-based deployment, leaving CoinGecko's own rate-limited API to carry
# every single price lookup alone.
_FALLBACK_EXCHANGE_IDS = ["coinbase", "kraken", "binance"]


def _get_public_exchange(exchange_id: str):
    """
    A ccxt exchange instance with no API credentials -- sufficient for
    fetching public market data (tickers) on virtually every exchange
    ccxt supports. Returns None if exchange_id isn't a real ccxt
    exchange id.
    """
    if exchange_id in _public_exchange_cache:
        return _public_exchange_cache[exchange_id]

    try:
        import ccxt

        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({"enableRateLimit": True})

    except AttributeError:
        logger.warning("Unknown ccxt exchange id for public pricing: %r", exchange_id)
        exchange = None
    except Exception:
        logger.exception("Failed to construct public ccxt exchange %r", exchange_id)
        exchange = None

    _public_exchange_cache[exchange_id] = exchange
    return exchange


def _get_ccxt_ticker_price(pair_symbol: str) -> tuple[Optional[float], list[str]]:
    """
    Current price for pair_symbol from a public ccxt ticker fetch,
    tried against this tenant's configured exchange first, then a
    fallback chain of other well-known, publicly-reachable exchanges.
    No API credentials needed for any of these -- this is public
    market data. Returns (price, errors) -- errors is a list of
    "exchange_id: reason" strings for every attempt that failed, so a
    final rejection can say exactly what was tried rather than just
    "unable to get reference price".
    """
    errors: list[str] = []

    try:
        from modules.admin.tenant_api_keys import get_ccxt_credentials

        configured_id = get_ccxt_credentials().get("exchange_id") or "binance"
    except Exception:
        configured_id = "binance"

    exchange_ids = [configured_id] + [e for e in _FALLBACK_EXCHANGE_IDS if e != configured_id]

    for exchange_id in exchange_ids:
        exchange = _get_public_exchange(exchange_id)
        if exchange is None:
            errors.append(f"{exchange_id}: not a recognized exchange")
            continue

        try:
            ticker = exchange.fetch_ticker(pair_symbol)
            price = ticker.get("last") or ticker.get("close")

            if price is not None:
                return float(price), errors

            errors.append(f"{exchange_id}: ticker had no price")

        except Exception as exc:
            # Includes ccxt.errors.BadSymbol (pair not listed there) and
            # network-level failures (including geo-blocking, which
            # typically surfaces as a connection error or 451/403 from
            # the exchange) -- logged with the exchange name so a
            # persistent, exchange-specific failure (e.g. binance from
            # a US IP) is visible rather than blended into one generic
            # "pricing failed" message.
            errors.append(f"{exchange_id}: {exc}")

    return None, errors


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


def _get_coingecko_price(pair_symbol: str) -> tuple[Optional[float], list[str]]:
    """
    CoinGecko fallback -- only USD-quoted pairs (USDT/USDC/USD) are
    supported, since CoinGecko's per-coin detail always includes a
    "usd" price and stablecoins are priced ~1:1 with USD, covering the
    overwhelming majority of real trading pairs. Returns (None,
    [reason]) on any failure (a real price is never actually zero, so
    this never returns 0.0 as a stand-in for "couldn't price this").
    """
    base, _, quote = str(pair_symbol).partition("/")
    base = base.upper().strip()
    quote = quote.upper().strip()

    if quote not in ("USDT", "USDC", "USD"):
        reason = f"unsupported quote currency {quote}"
        logger.info("CoinGecko fallback: %s for %s", reason, pair_symbol)
        return None, [f"coingecko: {reason}"]

    coin_id = _resolve_coingecko_id(base)
    if not coin_id:
        reason = f"could not resolve a coin id for base currency {base}"
        logger.warning("CoinGecko fallback: %s", reason)
        return None, [f"coingecko: {reason}"]

    try:
        from modules.crypto.data_service import get_coin_detail

        detail = get_coin_detail(coin_id)

        if not detail:
            reason = f"get_coin_detail({coin_id}) returned no data (likely rate-limited or unreachable)"
            logger.warning("CoinGecko fallback: %s for %s", reason, pair_symbol)
            return None, [f"coingecko: {reason}"]

        market_data = detail.get("market_data") or {}
        price = market_data.get("current_price", {}).get("usd")

        if price is None:
            reason = f"no usd price in market_data for {coin_id}"
            logger.warning("CoinGecko fallback: %s (%s)", reason, pair_symbol)
            return None, [f"coingecko: {reason}"]

        return float(price), []

    except Exception as exc:
        logger.exception("CoinGecko fallback failed for %s (%s)", pair_symbol, coin_id)
        return None, [f"coingecko: {exc}"]


def get_latest_crypto_price(pair_symbol: str) -> Optional[float]:
    """
    Current reference price for a ccxt-unified pair symbol (e.g.
    "BTC/USDT"). Tries a public ccxt ticker fetch (against this
    tenant's configured exchange, then a fallback chain of other
    well-known exchanges) first, then CoinGecko. Returns None (not
    0.0) if every source fails, so a caller can distinguish "genuinely
    couldn't price this" from "this happens to be worth zero".

    On failure, the detailed reason from every source tried is stored
    for get_last_pricing_errors(pair_symbol) to retrieve -- checked by
    modules.portfolio.order_service._get_reference_price so a rejected
    crypto order's message can say exactly what was tried, instead of
    a generic "unable to get reference price".
    """
    if not is_crypto_pair_symbol(pair_symbol):
        return None

    ccxt_price, ccxt_errors = _get_ccxt_ticker_price(pair_symbol)
    if ccxt_price is not None:
        _last_errors.pop(pair_symbol, None)
        return ccxt_price

    coingecko_price, coingecko_errors = _get_coingecko_price(pair_symbol)
    if coingecko_price is not None:
        _last_errors.pop(pair_symbol, None)
        return coingecko_price

    _last_errors[pair_symbol] = [f"ccxt {e}" for e in ccxt_errors] + coingecko_errors
    return None


def get_latest_crypto_price_map(pair_symbols: list[str]) -> dict[str, float]:
    """Batch version of get_latest_crypto_price(). Symbols that can't be priced are simply omitted, not zeroed."""
    out: dict[str, float] = {}
    for symbol in pair_symbols or []:
        price = get_latest_crypto_price(symbol)
        if price is not None:
            out[symbol] = price
    return out