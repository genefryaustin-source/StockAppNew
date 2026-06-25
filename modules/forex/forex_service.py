# modules/forex/forex_service.py

from __future__ import annotations

import os
import time
import math
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 20
DEFAULT_BASE_CURRENCY = "USD"

MAJOR_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "NZD/USD",
]

CROSS_PAIRS = [
    "EUR/GBP",
    "EUR/JPY",
    "GBP/JPY",
    "AUD/JPY",
    "EUR/CHF",
    "AUD/CAD",
    "CAD/JPY",
]

SUPPORTED_CURRENCIES = sorted(
    {
        "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD",
        "SEK", "NOK", "DKK", "MXN", "BRL", "ZAR", "SGD", "HKD",
        "CNH", "CNY", "INR", "KRW", "TRY", "PLN",
    }
)


@dataclass
class ForexQuote:
    pair: str
    base: str
    quote: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None
    provider: str = "unknown"
    asof: Optional[datetime] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.asof:
            data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexSignal:
    pair: str
    action: str
    confidence: float
    trend_score: float
    carry_score: float
    volatility_score: float
    liquidity_score: float
    rationale: str
    asof: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


def normalize_currency(value: str) -> str:
    return str(value or "").strip().upper()


def normalize_pair(pair: str) -> str:
    text = str(pair or "").strip().upper()
    text = text.replace("-", "/").replace("_", "/")

    if "/" in text:
        left, right = text.split("/", 1)
        return f"{normalize_currency(left)}/{normalize_currency(right)}"

    if len(text) == 6:
        return f"{text[:3]}/{text[3:]}"

    return text


def split_pair(pair: str) -> Tuple[str, str]:
    normalized = normalize_pair(pair)
    if "/" not in normalized:
        raise ValueError(f"Invalid forex pair: {pair}")

    base, quote = normalized.split("/", 1)

    if len(base) != 3 or len(quote) != 3:
        raise ValueError(f"Invalid forex pair: {pair}")

    return base, quote


def invert_pair(pair: str) -> str:
    base, quote = split_pair(pair)
    return f"{quote}/{base}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except Exception:
        return None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


class ForexService:
    """
    Tenant-safe Forex data service.

    Design rules:
    - No global runtime state.
    - Explicit tenant/user/portfolio passing.
    - Provider failover support.
    - Neon Postgres compatible when db session/connection is supplied.
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Any = None,
        timeout: int = DEFAULT_TIMEOUT,
        providers: Optional[List[str]] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.db = db
        self.timeout = timeout
        self.providers = providers or [
            "exchangerate_host",
            "frankfurter",
            "open_er_api",
        ]

    def get_quote(self, pair: str) -> ForexQuote:
        normalized = normalize_pair(pair)
        base, quote = split_pair(normalized)

        errors: List[str] = []

        for provider in self.providers:
            try:
                if provider == "exchangerate_host":
                    result = self._quote_from_exchangerate_host(base, quote)
                elif provider == "frankfurter":
                    result = self._quote_from_frankfurter(base, quote)
                elif provider == "open_er_api":
                    result = self._quote_from_open_er_api(base, quote)
                else:
                    continue

                if result and result.price > 0:
                    self._persist_quote(result)
                    return result

            except Exception as exc:
                errors.append(f"{provider}: {exc}")
                logger.warning("Forex provider failed: %s", errors[-1])

        cached = self.get_cached_quote(normalized)
        if cached:
            return cached

        raise RuntimeError(f"No forex quote available for {normalized}. Errors: {errors}")

    def get_quotes(self, pairs: List[str]) -> List[ForexQuote]:
        quotes: List[ForexQuote] = []

        for pair in pairs:
            try:
                quotes.append(self.get_quote(pair))
            except Exception as exc:
                logger.warning("Failed to fetch forex quote for %s: %s", pair, exc)

        return quotes

    def convert(self, amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
        source = normalize_currency(from_currency)
        target = normalize_currency(to_currency)

        if source == target:
            return {
                "amount": float(amount),
                "from_currency": source,
                "to_currency": target,
                "rate": 1.0,
                "converted_amount": float(amount),
                "asof": _utc_now().isoformat(),
            }

        pair = f"{source}/{target}"
        quote = self.get_quote(pair)

        converted = float(amount) * quote.price

        return {
            "amount": float(amount),
            "from_currency": source,
            "to_currency": target,
            "rate": quote.price,
            "converted_amount": converted,
            "provider": quote.provider,
            "asof": quote.asof.isoformat() if quote.asof else _utc_now().isoformat(),
        }

    def get_market_snapshot(self, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
        selected_pairs = pairs or MAJOR_PAIRS
        quotes = self.get_quotes(selected_pairs)

        return {
            "tenant_id": self.tenant_id,
            "asof": _utc_now().isoformat(),
            "pairs": [quote.to_dict() for quote in quotes],
            "count": len(quotes),
        }

    def get_supported_pairs(self) -> List[str]:
        pairs: List[str] = []

        for base in SUPPORTED_CURRENCIES:
            for quote in SUPPORTED_CURRENCIES:
                if base != quote:
                    pairs.append(f"{base}/{quote}")

        return sorted(pairs)

    def get_watchlist_pairs(self) -> List[str]:
        return MAJOR_PAIRS + CROSS_PAIRS

    def generate_basic_signal(self, pair: str) -> ForexSignal:
        quote = self.get_quote(pair)

        spread = quote.spread or 0.0
        liquidity_score = max(0.0, min(100.0, 100.0 - spread * 10000))

        trend_score = 50.0
        carry_score = 50.0
        volatility_score = 50.0

        confidence = round(
            (trend_score * 0.35)
            + (carry_score * 0.20)
            + (volatility_score * 0.20)
            + (liquidity_score * 0.25),
            2,
        )

        action = "WATCH"
        if confidence >= 75:
            action = "BUY"
        elif confidence <= 35:
            action = "AVOID"

        return ForexSignal(
            pair=quote.pair,
            action=action,
            confidence=confidence,
            trend_score=trend_score,
            carry_score=carry_score,
            volatility_score=volatility_score,
            liquidity_score=round(liquidity_score, 2),
            rationale=(
                f"{quote.pair} currently priced at {quote.price:.6f}. "
                f"Signal is liquidity-first until historical trend and macro models are connected."
            ),
            asof=_utc_now(),
        )

    def get_cached_quote(self, pair: str) -> Optional[ForexQuote]:
        if self.db is None:
            return None

        try:
            sql = """
                SELECT pair, base_currency, quote_currency, price, bid, ask, spread,
                       provider, asof, raw_payload
                FROM forex_quotes
                WHERE tenant_id = :tenant_id
                  AND pair = :pair
                ORDER BY asof DESC
                LIMIT 1
            """

            row = self.db.execute(
                sql,
                {
                    "tenant_id": self.tenant_id,
                    "pair": normalize_pair(pair),
                },
            ).fetchone()

            if not row:
                return None

            return ForexQuote(
                pair=row.pair,
                base=row.base_currency,
                quote=row.quote_currency,
                price=float(row.price),
                bid=_safe_float(row.bid),
                ask=_safe_float(row.ask),
                spread=_safe_float(row.spread),
                provider=row.provider or "cache",
                asof=row.asof,
                raw=row.raw_payload,
            )

        except Exception as exc:
            logger.warning("Failed to read cached forex quote: %s", exc)
            return None

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_quotes (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                pair VARCHAR(20) NOT NULL,
                base_currency VARCHAR(3) NOT NULL,
                quote_currency VARCHAR(3) NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                bid DOUBLE PRECISION,
                ask DOUBLE PRECISION,
                spread DOUBLE PRECISION,
                provider VARCHAR(80),
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_quotes_tenant_pair_asof
            ON forex_quotes (tenant_id, pair, asof DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_market_snapshots (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                snapshot_name VARCHAR(120),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def _persist_quote(self, quote: ForexQuote) -> None:
        if self.db is None:
            return

        try:
            self.ensure_tables()

            self.db.execute(
                """
                INSERT INTO forex_quotes (
                    tenant_id,
                    pair,
                    base_currency,
                    quote_currency,
                    price,
                    bid,
                    ask,
                    spread,
                    provider,
                    raw_payload,
                    asof
                )
                VALUES (
                    :tenant_id,
                    :pair,
                    :base_currency,
                    :quote_currency,
                    :price,
                    :bid,
                    :ask,
                    :spread,
                    :provider,
                    :raw_payload,
                    :asof
                )
                """,
                {
                    "tenant_id": self.tenant_id,
                    "pair": quote.pair,
                    "base_currency": quote.base,
                    "quote_currency": quote.quote,
                    "price": quote.price,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "spread": quote.spread,
                    "provider": quote.provider,
                    "raw_payload": quote.raw,
                    "asof": quote.asof.replace(tzinfo=None) if quote.asof else _utc_now().replace(tzinfo=None),
                },
            )

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to persist forex quote: %s", exc)
            try:
                if hasattr(self.db, "rollback"):
                    self.db.rollback()
            except Exception:
                pass

    def _quote_from_exchangerate_host(self, base: str, quote: str) -> ForexQuote:
        api_key = _env("EXCHANGERATE_HOST_API_KEY") or _env("EXCHANGE_RATE_API_KEY")

        url = "https://api.exchangerate.host/convert"
        params = {
            "from": base,
            "to": quote,
            "amount": 1,
        }

        if api_key:
            params["access_key"] = api_key

        payload = self._get_json(url, params=params)

        price = _safe_float(payload.get("result"))

        info = payload.get("info") or {}
        if price is None:
            price = _safe_float(info.get("rate"))

        if price is None or price <= 0:
            raise RuntimeError("exchangerate.host returned no usable rate")

        bid, ask, spread = self._synthetic_bid_ask(price)

        return ForexQuote(
            pair=f"{base}/{quote}",
            base=base,
            quote=quote,
            price=price,
            bid=bid,
            ask=ask,
            spread=spread,
            provider="exchangerate_host",
            asof=_utc_now(),
            raw=payload,
        )

    def _quote_from_frankfurter(self, base: str, quote: str) -> ForexQuote:
        url = "https://api.frankfurter.app/latest"
        payload = self._get_json(url, params={"from": base, "to": quote})

        rates = payload.get("rates") or {}
        price = _safe_float(rates.get(quote))

        if price is None or price <= 0:
            raise RuntimeError("Frankfurter returned no usable rate")

        bid, ask, spread = self._synthetic_bid_ask(price)

        return ForexQuote(
            pair=f"{base}/{quote}",
            base=base,
            quote=quote,
            price=price,
            bid=bid,
            ask=ask,
            spread=spread,
            provider="frankfurter",
            asof=_utc_now(),
            raw=payload,
        )

    def _quote_from_open_er_api(self, base: str, quote: str) -> ForexQuote:
        url = f"https://open.er-api.com/v6/latest/{base}"
        payload = self._get_json(url)

        rates = payload.get("rates") or {}
        price = _safe_float(rates.get(quote))

        if price is None or price <= 0:
            raise RuntimeError("open.er-api returned no usable rate")

        bid, ask, spread = self._synthetic_bid_ask(price)

        return ForexQuote(
            pair=f"{base}/{quote}",
            base=base,
            quote=quote,
            price=price,
            bid=bid,
            ask=ask,
            spread=spread,
            provider="open_er_api",
            asof=_utc_now(),
            raw=payload,
        )

    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 2,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(retries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, dict):
                    raise RuntimeError("Provider returned non-dict JSON payload")

                return payload

            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(0.35 * (attempt + 1))

        raise RuntimeError(str(last_error))

    @staticmethod
    def _synthetic_bid_ask(price: float) -> Tuple[float, float, float]:
        spread = max(abs(price) * 0.00008, 0.00001)
        bid = price - spread / 2
        ask = price + spread / 2
        return round(bid, 8), round(ask, 8), round(spread, 8)


def get_forex_service(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> ForexService:
    return ForexService(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
        timeout=timeout,
    )


def get_forex_quote(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
) -> Dict[str, Any]:
    service = get_forex_service(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return service.get_quote(pair).to_dict()


def get_forex_quotes(
    pairs: List[str],
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
) -> List[Dict[str, Any]]:
    service = get_forex_service(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return [quote.to_dict() for quote in service.get_quotes(pairs)]


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
) -> Dict[str, Any]:
    service = get_forex_service(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return service.convert(amount, from_currency, to_currency)


def get_forex_market_snapshot(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
) -> Dict[str, Any]:
    service = get_forex_service(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return service.get_market_snapshot(pairs)