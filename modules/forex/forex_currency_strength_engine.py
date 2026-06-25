"""
modules/forex/forex_currency_strength_engine.py

Institutional Forex Currency Strength Engine

This engine uses the centralized ForexPriceService / provider router rather than
calling any external provider directly.

Primary outputs:
- G8 currency strength rankings
- pair-level strength differentials
- directional trade bias
- strength matrix
- opportunity candidates
- Command Center-ready summary payload
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from modules.forex.forex_price_service import get_forex_price_service
except Exception:
    get_forex_price_service = None


G8_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "AUD",
    "CAD",
    "NZD",
]

MAJOR_AND_CROSS_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "AUD/USD",
    "NZD/USD",
    "USD/JPY",
    "USD/CHF",
    "USD/CAD",
    "EUR/GBP",
    "EUR/JPY",
    "EUR/CHF",
    "EUR/AUD",
    "EUR/CAD",
    "EUR/NZD",
    "GBP/JPY",
    "GBP/CHF",
    "GBP/AUD",
    "GBP/CAD",
    "GBP/NZD",
    "AUD/JPY",
    "AUD/CHF",
    "AUD/CAD",
    "AUD/NZD",
    "CAD/JPY",
    "CAD/CHF",
    "NZD/JPY",
    "NZD/CHF",
    "NZD/CAD",
    "CHF/JPY",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def normalize_pair(pair: str) -> str:
    text = str(pair or "").upper().replace("-", "/").replace("_", "/").replace(" ", "")
    if "/" in text:
        left, right = text.split("/", 1)
        return f"{left[:3]}/{right[:3]}"
    if len(text) >= 6:
        return f"{text[:3]}/{text[3:6]}"
    return text


def split_pair(pair: str) -> Tuple[str, str]:
    pair = normalize_pair(pair)
    if "/" in pair:
        left, right = pair.split("/", 1)
        return left[:3], right[:3]
    if len(pair) >= 6:
        return pair[:3], pair[3:6]
    return pair[:3], ""


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class CurrencyStrengthRow:
    currency: str
    strength_score: float
    normalized_score: float
    rank: int
    signal: str
    regime: str
    confidence_score: float
    pair_count: int
    positive_edges: int
    negative_edges: int
    average_edge: float
    strongest_against: Optional[str] = None
    weakest_against: Optional[str] = None
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PairStrengthRow:
    pair: str
    base: str
    quote: str
    base_score: float
    quote_score: float
    differential: float
    signal: str
    confidence_score: float
    provider: Optional[str]
    mid: Optional[float]
    timestamp: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexCurrencyStrengthEngine:
    """
    Institutional-grade currency strength engine.

    Design:
    - Loads all required FX quotes once through ForexPriceService.
    - Builds a pair graph where base currency gains positive strength when the
      pair level is structurally above its synthetic neutral anchor.
    - Uses cross-sectional scoring so missing pairs degrade gracefully.
    - Produces currency rankings and pair differentials for alpha models,
      portfolio construction, and the Forex Command Center.
    """

    def __init__(
        self,
        currencies: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None,
    ):
        self.currencies = currencies or list(G8_CURRENCIES)
        self.pairs = [normalize_pair(p) for p in (pairs or MAJOR_AND_CROSS_PAIRS)]
        self.price_service = get_forex_price_service() if get_forex_price_service else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_currencies(
        self,
        currencies: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None,
        force_refresh: bool = False,
        save: bool = False,
        db=None,
    ) -> Dict[str, Any]:
        currencies = [str(c).upper()[:3] for c in (currencies or self.currencies)]
        pairs = [normalize_pair(p) for p in (pairs or self.pairs)]

        quotes = self._load_quotes(pairs, force_refresh=force_refresh)
        currency_rows, pair_rows, matrix = self._calculate_strength(
            currencies=currencies,
            pairs=pairs,
            quotes=quotes,
        )

        payload = self._build_payload(
            currencies=currencies,
            pairs=pairs,
            quotes=quotes,
            currency_rows=currency_rows,
            pair_rows=pair_rows,
            matrix=matrix,
        )

        if save and db is not None:
            self.save_snapshot(db, payload)

        return payload

    def get_currency_strength(
        self,
        currency: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        scan = self.scan_currencies(force_refresh=force_refresh)
        target = str(currency or "").upper()[:3]
        for row in scan["currency_strength"]:
            if row["currency"] == target:
                return row
        return {
            "currency": target,
            "error": "Currency not found in strength universe.",
        }

    def get_pair_bias(
        self,
        pair: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        pair = normalize_pair(pair)
        scan = self.scan_currencies(
            pairs=list(dict.fromkeys(self.pairs + [pair])),
            force_refresh=force_refresh,
        )
        for row in scan["pair_strength"]:
            if row["pair"] == pair:
                return row
        return {
            "pair": pair,
            "error": "Pair not found in strength scan.",
        }

    def top_opportunities(
        self,
        limit: int = 10,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        scan = self.scan_currencies(force_refresh=force_refresh)
        rows = list(scan.get("pair_strength", []))
        rows.sort(
            key=lambda r: (
                abs(safe_float(r.get("differential"))),
                safe_float(r.get("confidence_score")),
            ),
            reverse=True,
        )
        return rows[: int(limit)]

    def command_center_payload(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        scan = self.scan_currencies(force_refresh=force_refresh)
        strongest = scan.get("strongest_currency")
        weakest = scan.get("weakest_currency")
        opportunities = self.top_opportunities(limit=5, force_refresh=False)

        return {
            "status": scan.get("status"),
            "generated_at": scan.get("generated_at"),
            "strongest_currency": strongest,
            "weakest_currency": weakest,
            "market_bias": self._market_bias(scan),
            "currency_strength": scan.get("currency_strength", []),
            "top_strength_opportunities": opportunities,
            "matrix": scan.get("matrix", {}),
            "warnings": scan.get("warnings", []),
        }

    # ------------------------------------------------------------------
    # Quote loading
    # ------------------------------------------------------------------

    def _load_quotes(
        self,
        pairs: List[str],
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        quotes: Dict[str, Dict[str, Any]] = {}

        if self.price_service is None:
            for pair in pairs:
                quotes[pair] = {
                    "pair": pair,
                    "error": "ForexPriceService unavailable.",
                }
            return quotes

        try:
            loaded = self.price_service.get_quotes(
                pairs,
                force_refresh=force_refresh,
            )
            if isinstance(loaded, dict):
                for key, value in loaded.items():
                    quotes[normalize_pair(key)] = value
        except Exception as exc:
            for pair in pairs:
                quotes[pair] = {
                    "pair": pair,
                    "error": str(exc),
                }

        for pair in pairs:
            quotes.setdefault(
                pair,
                {
                    "pair": pair,
                    "error": "No quote returned.",
                },
            )

        return quotes

    # ------------------------------------------------------------------
    # Strength model
    # ------------------------------------------------------------------

    def _calculate_strength(
        self,
        currencies: List[str],
        pairs: List[str],
        quotes: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, float]]]:

        edges: Dict[str, List[float]] = {c: [] for c in currencies}
        pair_raw_edges: Dict[str, float] = {}
        matrix: Dict[str, Dict[str, float]] = {
            c: {d: 0.0 for d in currencies if d != c}
            for c in currencies
        }

        usable_prices: List[float] = []
        for pair in pairs:
            quote = quotes.get(pair, {})
            mid = safe_float(quote.get("mid") or quote.get("last"), 0.0)
            if mid > 0:
                usable_prices.append(mid)

        median_price = statistics.median(usable_prices) if usable_prices else 1.0

        for pair in pairs:
            base, quote_ccy = split_pair(pair)
            if base not in currencies or quote_ccy not in currencies:
                continue

            quote = quotes.get(pair, {})
            mid = safe_float(quote.get("mid") or quote.get("last"), 0.0)
            if mid <= 0:
                continue

            # Cross-sectional log edge. This does not pretend to be a full
            # historical return model; it provides a stable current strength
            # estimate until historical FX time series are plugged in.
            raw_edge = math.log(mid / median_price) * 100.0
            raw_edge = max(-25.0, min(25.0, raw_edge))

            # Positive edge favors base; negative favors quote.
            edges[base].append(raw_edge)
            edges[quote_ccy].append(-raw_edge)
            pair_raw_edges[pair] = raw_edge
            matrix.setdefault(base, {})[quote_ccy] = round(raw_edge, 4)
            matrix.setdefault(quote_ccy, {})[base] = round(-raw_edge, 4)

        raw_scores: Dict[str, float] = {}
        for currency in currencies:
            vals = edges.get(currency, [])
            raw_scores[currency] = statistics.mean(vals) if vals else 0.0

        if raw_scores:
            low = min(raw_scores.values())
            high = max(raw_scores.values())
        else:
            low = high = 0.0

        normalized: Dict[str, float] = {}
        for currency, score in raw_scores.items():
            if high == low:
                normalized[currency] = 50.0
            else:
                normalized[currency] = ((score - low) / (high - low)) * 100.0

        sorted_currencies = sorted(
            currencies,
            key=lambda c: normalized.get(c, 50.0),
            reverse=True,
        )

        currency_rows: List[Dict[str, Any]] = []
        for rank, currency in enumerate(sorted_currencies, start=1):
            vals = edges.get(currency, [])
            avg_edge = statistics.mean(vals) if vals else 0.0
            positive = len([v for v in vals if v > 0])
            negative = len([v for v in vals if v < 0])
            score = clamp(normalized.get(currency, 50.0))
            confidence = self._confidence_from_score(score, len(vals))

            strongest_against = None
            weakest_against = None
            if matrix.get(currency):
                strongest_against = max(matrix[currency], key=lambda x: matrix[currency][x])
                weakest_against = min(matrix[currency], key=lambda x: matrix[currency][x])

            row = CurrencyStrengthRow(
                currency=currency,
                strength_score=round(score, 2),
                normalized_score=round(score, 2),
                rank=rank,
                signal=self._currency_signal(score),
                regime=self._currency_regime(score),
                confidence_score=round(confidence, 2),
                pair_count=len(vals),
                positive_edges=positive,
                negative_edges=negative,
                average_edge=round(avg_edge, 4),
                strongest_against=strongest_against,
                weakest_against=weakest_against,
                generated_at=utc_now_iso(),
            ).to_dict()
            currency_rows.append(row)

        pair_rows: List[Dict[str, Any]] = []
        for pair in pairs:
            base, quote_ccy = split_pair(pair)
            if base not in normalized or quote_ccy not in normalized:
                continue

            quote = quotes.get(pair, {})
            base_score = clamp(normalized.get(base, 50.0))
            quote_score = clamp(normalized.get(quote_ccy, 50.0))
            differential = base_score - quote_score
            confidence = min(100.0, 50.0 + abs(differential) * 0.5)

            pair_rows.append(
                PairStrengthRow(
                    pair=pair,
                    base=base,
                    quote=quote_ccy,
                    base_score=round(base_score, 2),
                    quote_score=round(quote_score, 2),
                    differential=round(differential, 2),
                    signal=self._pair_signal(differential),
                    confidence_score=round(confidence, 2),
                    provider=quote.get("provider"),
                    mid=quote.get("mid") or quote.get("last"),
                    timestamp=quote.get("timestamp"),
                ).to_dict()
            )

        pair_rows.sort(
            key=lambda r: abs(safe_float(r.get("differential"))),
            reverse=True,
        )

        return currency_rows, pair_rows, matrix

    # ------------------------------------------------------------------
    # Payload / persistence
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        currencies: List[str],
        pairs: List[str],
        quotes: Dict[str, Dict[str, Any]],
        currency_rows: List[Dict[str, Any]],
        pair_rows: List[Dict[str, Any]],
        matrix: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        warnings = []
        failed_quotes = []
        for pair, quote in quotes.items():
            if quote.get("error"):
                failed_quotes.append(pair)
                warnings.append(f"{pair}: {quote.get('error')}")

        strongest = currency_rows[0] if currency_rows else None
        weakest = currency_rows[-1] if currency_rows else None

        return {
            "status": "success" if currency_rows else "no_data",
            "generated_at": utc_now_iso(),
            "universe": {
                "currencies": currencies,
                "pairs": pairs,
                "pair_count": len(pairs),
                "currency_count": len(currencies),
            },
            "quote_health": {
                "requested": len(pairs),
                "successful": len(pairs) - len(failed_quotes),
                "failed": len(failed_quotes),
                "failed_pairs": failed_quotes,
            },
            "strongest_currency": strongest,
            "weakest_currency": weakest,
            "currency_strength": currency_rows,
            "pair_strength": pair_rows,
            "matrix": matrix,
            "warnings": warnings[:25],
        }

    def save_snapshot(self, db, payload: Dict[str, Any]) -> None:
        """
        Optional persistence hook. Creates a compact table for latest strength
        rows if a SQLAlchemy session/connection is supplied.
        """
        try:
            from sqlalchemy import text
        except Exception:
            return

        db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_currency_strength_snapshots (
                id SERIAL PRIMARY KEY,
                currency VARCHAR(10),
                strength_score DOUBLE PRECISION,
                rank INTEGER,
                signal VARCHAR(50),
                regime VARCHAR(50),
                confidence_score DOUBLE PRECISION,
                generated_at TIMESTAMP
            )
        """))

        generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for row in payload.get("currency_strength", []):
            db.execute(text("""
                INSERT INTO forex_currency_strength_snapshots (
                    currency,
                    strength_score,
                    rank,
                    signal,
                    regime,
                    confidence_score,
                    generated_at
                )
                VALUES (
                    :currency,
                    :strength_score,
                    :rank,
                    :signal,
                    :regime,
                    :confidence_score,
                    :generated_at
                )
            """), {
                "currency": row.get("currency"),
                "strength_score": row.get("strength_score"),
                "rank": row.get("rank"),
                "signal": row.get("signal"),
                "regime": row.get("regime"),
                "confidence_score": row.get("confidence_score"),
                "generated_at": generated_at,
            })

        db.commit()

    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------

    def _currency_signal(self, score: float) -> str:
        if score >= 80:
            return "STRONG_BUY_BIAS"
        if score >= 65:
            return "BUY_BIAS"
        if score <= 20:
            return "STRONG_SELL_BIAS"
        if score <= 35:
            return "SELL_BIAS"
        return "NEUTRAL"

    def _currency_regime(self, score: float) -> str:
        if score >= 75:
            return "VERY_STRONG"
        if score >= 60:
            return "STRONG"
        if score <= 25:
            return "VERY_WEAK"
        if score <= 40:
            return "WEAK"
        return "BALANCED"

    def _pair_signal(self, differential: float) -> str:
        if differential >= 35:
            return "STRONG_BUY"
        if differential >= 18:
            return "BUY"
        if differential <= -35:
            return "STRONG_SELL"
        if differential <= -18:
            return "SELL"
        return "WATCH"

    def _confidence_from_score(self, score: float, observations: int) -> float:
        distance = abs(score - 50.0)
        observation_bonus = min(20.0, observations * 2.5)
        return clamp(45.0 + distance * 0.7 + observation_bonus)

    def _market_bias(self, scan: Dict[str, Any]) -> str:
        rows = scan.get("currency_strength", [])
        if not rows:
            return "NEUTRAL"

        usd = next((r for r in rows if r.get("currency") == "USD"), None)
        jpy = next((r for r in rows if r.get("currency") == "JPY"), None)
        aud = next((r for r in rows if r.get("currency") == "AUD"), None)
        nzd = next((r for r in rows if r.get("currency") == "NZD"), None)

        usd_score = safe_float((usd or {}).get("strength_score"), 50.0)
        jpy_score = safe_float((jpy or {}).get("strength_score"), 50.0)
        aud_score = safe_float((aud or {}).get("strength_score"), 50.0)
        nzd_score = safe_float((nzd or {}).get("strength_score"), 50.0)

        risk_score = ((aud_score + nzd_score) / 2.0) - ((usd_score + jpy_score) / 2.0)

        if risk_score >= 15:
            return "RISK_ON"
        if risk_score <= -15:
            return "RISK_OFF"
        return "NEUTRAL"


_ENGINE: Optional[ForexCurrencyStrengthEngine] = None


def get_forex_currency_strength_engine() -> ForexCurrencyStrengthEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ForexCurrencyStrengthEngine()
    return _ENGINE


def scan_currency_strength(
    currencies: Optional[List[str]] = None,
    pairs: Optional[List[str]] = None,
    force_refresh: bool = False,
    save: bool = False,
    db=None,
) -> Dict[str, Any]:
    return get_forex_currency_strength_engine().scan_currencies(
        currencies=currencies,
        pairs=pairs,
        force_refresh=force_refresh,
        save=save,
        db=db,
    )


def get_currency_strength(currency: str, force_refresh: bool = False) -> Dict[str, Any]:
    return get_forex_currency_strength_engine().get_currency_strength(
        currency,
        force_refresh=force_refresh,
    )


def get_pair_strength_bias(pair: str, force_refresh: bool = False) -> Dict[str, Any]:
    return get_forex_currency_strength_engine().get_pair_bias(
        pair,
        force_refresh=force_refresh,
    )
