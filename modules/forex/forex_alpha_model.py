"""
modules/forex/forex_alpha_model.py

Institutional Forex Alpha Model

This module is the Forex decision layer. It consumes the centralized Forex
provider infrastructure through ForexPriceService and CurrencyStrengthEngine,
then produces ranked BUY / SELL / WATCH opportunities for the Forex Command
Center, recommendation engine, portfolio optimizer, and autonomous trader.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from sqlalchemy import text
except Exception:
    text = None

try:
    from modules.forex.forex_price_service import get_forex_price_service
except Exception:
    get_forex_price_service = None

try:
    from modules.forex.forex_currency_strength_engine import (
        get_forex_currency_strength_engine,
        MAJOR_AND_CROSS_PAIRS,
    )
except Exception:
    get_forex_currency_strength_engine = None
    MAJOR_AND_CROSS_PAIRS = [
        "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
        "USD/JPY", "USD/CHF", "USD/CAD",
        "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY",
    ]


DEFAULT_PAIRS = list(MAJOR_AND_CROSS_PAIRS)

DEFAULT_ACCOUNT_SIZE = 100000.0
DEFAULT_RISK_PER_TRADE_PCT = 0.005
DEFAULT_ATR_PROXY_BPS = 65.0


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


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


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


@dataclass
class ForexAlphaSignal:
    pair: str
    base: str
    quote: str
    direction: str
    recommendation: str
    signal: str
    alpha_score: float
    composite_score: float
    confidence_score: float
    strength_score: float
    momentum_score: float
    macro_score: float
    carry_score: float
    institutional_score: float
    sentiment_score: float
    risk_score: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    suggested_notional: float
    estimated_risk_dollars: float
    position_bias: str
    provider: Optional[str]
    rationale: str
    warnings: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexAlphaModel:
    """
    Institutional alpha model for Forex.

    Scoring layers:
    - Currency strength differential
    - Quote availability / live provider quality
    - Macro proxy
    - Carry proxy
    - Institutional proxy
    - Sentiment proxy
    - Risk penalty / reward symmetry

    The proxies are intentionally modular. If the dedicated engines exist,
    their values can be blended in later without changing the public output.
    """

    def __init__(
        self,
        pairs: Optional[List[str]] = None,
        account_size: float = DEFAULT_ACCOUNT_SIZE,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    ):
        self.pairs = [normalize_pair(p) for p in (pairs or DEFAULT_PAIRS)]
        self.account_size = float(account_size or DEFAULT_ACCOUNT_SIZE)
        self.risk_per_trade_pct = float(risk_per_trade_pct or DEFAULT_RISK_PER_TRADE_PCT)
        self.price_service = get_forex_price_service() if get_forex_price_service else None
        self.strength_engine = (
            get_forex_currency_strength_engine()
            if get_forex_currency_strength_engine
            else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_alpha_model(
        self,
        pairs: Optional[List[str]] = None,
        force_refresh: bool = False,
        save: bool = False,
        db=None,
        account_size: Optional[float] = None,
        risk_per_trade_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        pairs = [normalize_pair(p) for p in (pairs or self.pairs)]
        account_size = float(account_size or self.account_size)
        risk_per_trade_pct = float(risk_per_trade_pct or self.risk_per_trade_pct)

        quotes = self._load_quotes(pairs, force_refresh=force_refresh)
        strength_scan = self._load_strength_scan(pairs, force_refresh=force_refresh)

        rows = []
        for pair in pairs:
            rows.append(
                self._score_pair(
                    pair=pair,
                    quote=quotes.get(pair, {}),
                    strength_scan=strength_scan,
                    account_size=account_size,
                    risk_per_trade_pct=risk_per_trade_pct,
                )
            )

        rows.sort(
            key=lambda r: (
                safe_float(r["alpha_score"]),
                safe_float(r["confidence_score"]),
                safe_float(r["risk_reward"]),
            ),
            reverse=True,
        )

        payload = self._build_payload(
            pairs=pairs,
            rows=rows,
            quotes=quotes,
            strength_scan=strength_scan,
        )

        if save and db is not None:
            self.save_alpha_signals(db, payload)

        return payload

    def get_top_opportunities(
        self,
        pairs: Optional[List[str]] = None,
        limit: int = 10,
        min_alpha_score: float = 65.0,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        scan = self.run_alpha_model(
            pairs=pairs,
            force_refresh=force_refresh,
        )
        rows = [
            r for r in scan.get("signals", [])
            if safe_float(r.get("alpha_score")) >= float(min_alpha_score)
        ]
        return rows[: int(limit)]

    def command_center_payload(
        self,
        pairs: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        scan = self.run_alpha_model(
            pairs=pairs,
            force_refresh=force_refresh,
        )
        top = scan.get("top_signal")
        return {
            "status": scan.get("status"),
            "generated_at": scan.get("generated_at"),
            "best_trade": top,
            "top_opportunities": scan.get("signals", [])[:8],
            "summary": scan.get("summary", {}),
            "warnings": scan.get("warnings", []),
        }

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_quotes(self, pairs: List[str], force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
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
                for k, v in loaded.items():
                    quotes[normalize_pair(k)] = v
        except Exception as exc:
            for pair in pairs:
                quotes[pair] = {
                    "pair": pair,
                    "error": str(exc),
                }

        for pair in pairs:
            quotes.setdefault(pair, {"pair": pair, "error": "No quote returned."})

        return quotes

    def _load_strength_scan(self, pairs: List[str], force_refresh: bool = False) -> Dict[str, Any]:
        if self.strength_engine is None:
            return {
                "status": "unavailable",
                "pair_strength": [],
                "currency_strength": [],
                "warnings": ["ForexCurrencyStrengthEngine unavailable."],
            }

        try:
            return self.strength_engine.scan_currencies(
                pairs=pairs,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return {
                "status": "error",
                "pair_strength": [],
                "currency_strength": [],
                "warnings": [str(exc)],
            }

    # ------------------------------------------------------------------
    # Alpha scoring
    # ------------------------------------------------------------------

    def _score_pair(
        self,
        pair: str,
        quote: Dict[str, Any],
        strength_scan: Dict[str, Any],
        account_size: float,
        risk_per_trade_pct: float,
    ) -> Dict[str, Any]:
        base, quote_ccy = split_pair(pair)
        mid = safe_float(quote.get("mid") or quote.get("last"), 0.0)

        pair_strength = self._pair_strength_row(pair, strength_scan)
        differential = safe_float(pair_strength.get("differential"), 0.0)

        strength_score = self._score_strength(differential)
        momentum_score = self._score_momentum(pair, differential, quote)
        macro_score = self._score_macro_proxy(base, quote_ccy, strength_scan)
        carry_score = self._score_carry_proxy(base, quote_ccy)
        institutional_score = self._score_institutional_proxy(differential, quote)
        sentiment_score = self._score_sentiment_proxy(base, quote_ccy, differential)
        risk_score = self._score_risk(mid, quote)

        composite = (
            strength_score * 0.34
            + momentum_score * 0.16
            + macro_score * 0.12
            + carry_score * 0.10
            + institutional_score * 0.12
            + sentiment_score * 0.08
            + risk_score * 0.08
        )

        direction = self._direction_from_differential(differential, composite)
        confidence = self._confidence_score(
            composite=composite,
            differential=differential,
            quote=quote,
            strength_confidence=safe_float(pair_strength.get("confidence_score"), 50.0),
        )

        entry, stop, target, rr, risk_dollars, notional = self._risk_plan(
            direction=direction,
            mid=mid,
            confidence=confidence,
            account_size=account_size,
            risk_per_trade_pct=risk_per_trade_pct,
        )

        recommendation = self._recommendation(direction, composite, confidence, rr)
        signal = self._signal_label(direction, composite)
        warnings = self._warnings(pair, quote, mid, composite, confidence)
        rationale = self._rationale(
            pair=pair,
            direction=direction,
            composite=composite,
            confidence=confidence,
            differential=differential,
            strength_score=strength_score,
            macro_score=macro_score,
            carry_score=carry_score,
            institutional_score=institutional_score,
            sentiment_score=sentiment_score,
            risk_score=risk_score,
        )

        row = ForexAlphaSignal(
            pair=pair,
            base=base,
            quote=quote_ccy,
            direction=direction,
            recommendation=recommendation,
            signal=signal,
            alpha_score=round(clamp(composite), 2),
            composite_score=round(clamp(composite), 2),
            confidence_score=round(clamp(confidence), 2),
            strength_score=round(clamp(strength_score), 2),
            momentum_score=round(clamp(momentum_score), 2),
            macro_score=round(clamp(macro_score), 2),
            carry_score=round(clamp(carry_score), 2),
            institutional_score=round(clamp(institutional_score), 2),
            sentiment_score=round(clamp(sentiment_score), 2),
            risk_score=round(clamp(risk_score), 2),
            entry_price=round(entry, 6),
            stop_price=round(stop, 6),
            target_price=round(target, 6),
            risk_reward=round(rr, 2),
            suggested_notional=round(notional, 2),
            estimated_risk_dollars=round(risk_dollars, 2),
            position_bias=self._position_bias(direction),
            provider=quote.get("provider"),
            rationale=rationale,
            warnings=warnings,
            generated_at=utc_now_iso(),
        ).to_dict()

        return row

    def _pair_strength_row(self, pair: str, scan: Dict[str, Any]) -> Dict[str, Any]:
        for row in scan.get("pair_strength", []) or []:
            if normalize_pair(row.get("pair")) == pair:
                return row
        return {
            "pair": pair,
            "differential": 0.0,
            "confidence_score": 40.0,
            "signal": "WATCH",
        }

    def _score_strength(self, differential: float) -> float:
        return clamp(50.0 + abs(differential) * 0.75)

    def _score_momentum(self, pair: str, differential: float, quote: Dict[str, Any]) -> float:
        provider_bonus = 5.0 if quote.get("provider") else 0.0
        return clamp(50.0 + abs(differential) * 0.35 + provider_bonus)

    def _score_macro_proxy(self, base: str, quote: str, scan: Dict[str, Any]) -> float:
        market_bias = "NEUTRAL"
        try:
            if self.strength_engine is not None:
                market_bias = self.strength_engine._market_bias(scan)
        except Exception:
            market_bias = "NEUTRAL"

        risk_on = {"AUD", "NZD", "CAD", "GBP"}
        defensive = {"USD", "JPY", "CHF"}

        score = 50.0
        if market_bias == "RISK_ON":
            if base in risk_on:
                score += 12
            if quote in risk_on:
                score -= 6
            if base in defensive:
                score -= 6
        elif market_bias == "RISK_OFF":
            if base in defensive:
                score += 12
            if quote in defensive:
                score -= 6
            if base in risk_on:
                score -= 6

        return clamp(score)

    def _score_carry_proxy(self, base: str, quote: str) -> float:
        # Approximate current policy-rate ranking proxy until the dedicated
        # carry/central-bank engine is blended in.
        rate_rank = {
            "NZD": 5.5,
            "USD": 5.25,
            "GBP": 5.0,
            "CAD": 4.75,
            "AUD": 4.35,
            "EUR": 3.75,
            "CHF": 1.5,
            "JPY": 0.25,
        }
        diff = rate_rank.get(base, 3.0) - rate_rank.get(quote, 3.0)
        return clamp(50.0 + diff * 6.0)

    def _score_institutional_proxy(self, differential: float, quote: Dict[str, Any]) -> float:
        base = 50.0 + abs(differential) * 0.35
        if quote.get("provider") in ("polygon_fx", "twelvedata_fx", "finnhub_fx"):
            base += 5.0
        return clamp(base)

    def _score_sentiment_proxy(self, base: str, quote: str, differential: float) -> float:
        directional = 50.0 + abs(differential) * 0.20
        if base in {"USD", "JPY", "CHF"} and differential > 0:
            directional += 3.0
        return clamp(directional)

    def _score_risk(self, mid: float, quote: Dict[str, Any]) -> float:
        if mid <= 0:
            return 15.0
        spread = safe_float(quote.get("spread"), 0.0)
        if spread <= 0:
            return 70.0
        bps = (spread / mid) * 10000.0
        return clamp(85.0 - bps * 2.0)

    def _direction_from_differential(self, differential: float, composite: float) -> str:
        if composite < 55 or abs(differential) < 8:
            return "WATCH"
        if differential > 0:
            return "BUY"
        return "SELL"

    def _confidence_score(
        self,
        composite: float,
        differential: float,
        quote: Dict[str, Any],
        strength_confidence: float,
    ) -> float:
        score = (
            composite * 0.45
            + min(100.0, abs(differential) * 1.2) * 0.25
            + strength_confidence * 0.25
        )
        if quote.get("error"):
            score -= 25.0
        if quote.get("provider"):
            score += 5.0
        return clamp(score)

    def _risk_plan(
        self,
        direction: str,
        mid: float,
        confidence: float,
        account_size: float,
        risk_per_trade_pct: float,
    ) -> Tuple[float, float, float, float, float, float]:
        if mid <= 0 or direction == "WATCH":
            return mid, 0.0, 0.0, 0.0, 0.0, 0.0

        volatility_pct = DEFAULT_ATR_PROXY_BPS / 10000.0
        stop_distance = mid * volatility_pct
        reward_multiple = 2.0 + max(0.0, confidence - 60.0) / 40.0
        target_distance = stop_distance * reward_multiple

        if direction == "BUY":
            stop = mid - stop_distance
            target = mid + target_distance
        else:
            stop = mid + stop_distance
            target = mid - target_distance

        risk_dollars = account_size * risk_per_trade_pct
        notional = risk_dollars / max(volatility_pct, 0.0001)

        return mid, stop, target, reward_multiple, risk_dollars, notional

    def _recommendation(self, direction: str, composite: float, confidence: float, rr: float) -> str:
        if direction == "WATCH":
            return "WATCH"
        if composite >= 82 and confidence >= 72 and rr >= 2.0:
            return f"STRONG_{direction}"
        if composite >= 68 and confidence >= 60 and rr >= 1.5:
            return direction
        return "WATCH"

    def _signal_label(self, direction: str, composite: float) -> str:
        if direction == "WATCH":
            return "NO_TRADE"
        if composite >= 82:
            return f"HIGH_CONVICTION_{direction}"
        if composite >= 68:
            return f"TACTICAL_{direction}"
        return "WATCH"

    def _position_bias(self, direction: str) -> str:
        if direction == "BUY":
            return "LONG_BASE_SHORT_QUOTE"
        if direction == "SELL":
            return "SHORT_BASE_LONG_QUOTE"
        return "NEUTRAL"

    def _warnings(self, pair: str, quote: Dict[str, Any], mid: float, composite: float, confidence: float) -> str:
        warnings = []
        if quote.get("error"):
            warnings.append(str(quote.get("error")))
        if mid <= 0:
            warnings.append("No valid current price.")
        if confidence < 55:
            warnings.append("Low confidence signal.")
        if composite < 60:
            warnings.append("Composite alpha below preferred threshold.")
        return " | ".join(warnings)

    def _rationale(
        self,
        pair: str,
        direction: str,
        composite: float,
        confidence: float,
        differential: float,
        strength_score: float,
        macro_score: float,
        carry_score: float,
        institutional_score: float,
        sentiment_score: float,
        risk_score: float,
    ) -> str:
        if direction == "WATCH":
            lead = f"{pair} is currently a WATCH setup."
        else:
            lead = f"{pair} has a {direction} bias from currency-strength divergence."

        return (
            f"{lead} Alpha {composite:.1f}, confidence {confidence:.1f}. "
            f"Strength differential {differential:.1f}; strength score {strength_score:.1f}, "
            f"macro {macro_score:.1f}, carry {carry_score:.1f}, institutional {institutional_score:.1f}, "
            f"sentiment {sentiment_score:.1f}, risk {risk_score:.1f}."
        )

    # ------------------------------------------------------------------
    # Payload / persistence
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        pairs: List[str],
        rows: List[Dict[str, Any]],
        quotes: Dict[str, Dict[str, Any]],
        strength_scan: Dict[str, Any],
    ) -> Dict[str, Any]:
        tradable = [r for r in rows if r.get("recommendation") not in ("WATCH", "NO_TRADE")]
        buys = [r for r in rows if "BUY" in str(r.get("recommendation"))]
        sells = [r for r in rows if "SELL" in str(r.get("recommendation"))]

        failed_quotes = [
            pair for pair, quote in quotes.items()
            if quote.get("error")
        ]

        top = rows[0] if rows else None

        return {
            "status": "success" if rows else "no_data",
            "generated_at": utc_now_iso(),
            "summary": {
                "pairs_scanned": len(pairs),
                "signals": len(rows),
                "tradable": len(tradable),
                "buy_signals": len(buys),
                "sell_signals": len(sells),
                "failed_quotes": len(failed_quotes),
                "average_alpha": round(statistics.mean([safe_float(r.get("alpha_score")) for r in rows]), 2) if rows else 0.0,
                "average_confidence": round(statistics.mean([safe_float(r.get("confidence_score")) for r in rows]), 2) if rows else 0.0,
            },
            "top_signal": top,
            "signals": rows,
            "failed_quotes": failed_quotes,
            "strength_snapshot": {
                "strongest_currency": strength_scan.get("strongest_currency"),
                "weakest_currency": strength_scan.get("weakest_currency"),
                "quote_health": strength_scan.get("quote_health"),
            },
            "warnings": self._collect_warnings(rows, quotes, strength_scan),
        }

    def _collect_warnings(
        self,
        rows: List[Dict[str, Any]],
        quotes: Dict[str, Dict[str, Any]],
        strength_scan: Dict[str, Any],
    ) -> List[str]:
        warnings = []
        for pair, quote in quotes.items():
            if quote.get("error"):
                warnings.append(f"{pair}: {quote.get('error')}")
        warnings.extend(str(w) for w in strength_scan.get("warnings", []) or [])
        for row in rows:
            if row.get("warnings"):
                warnings.append(f"{row.get('pair')}: {row.get('warnings')}")
        return warnings[:50]

    def save_alpha_signals(self, db, payload: Dict[str, Any]) -> None:
        if text is None:
            return

        db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_alpha_signals (
                id SERIAL PRIMARY KEY,
                pair VARCHAR(20),
                direction VARCHAR(20),
                recommendation VARCHAR(40),
                alpha_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                risk_reward DOUBLE PRECISION,
                suggested_notional DOUBLE PRECISION,
                rationale TEXT,
                warnings TEXT,
                generated_at TIMESTAMP
            )
        """))

        generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for row in payload.get("signals", []):
            db.execute(text("""
                INSERT INTO forex_alpha_signals (
                    pair,
                    direction,
                    recommendation,
                    alpha_score,
                    confidence_score,
                    entry_price,
                    stop_price,
                    target_price,
                    risk_reward,
                    suggested_notional,
                    rationale,
                    warnings,
                    generated_at
                )
                VALUES (
                    :pair,
                    :direction,
                    :recommendation,
                    :alpha_score,
                    :confidence_score,
                    :entry_price,
                    :stop_price,
                    :target_price,
                    :risk_reward,
                    :suggested_notional,
                    :rationale,
                    :warnings,
                    :generated_at
                )
            """), {
                "pair": row.get("pair"),
                "direction": row.get("direction"),
                "recommendation": row.get("recommendation"),
                "alpha_score": row.get("alpha_score"),
                "confidence_score": row.get("confidence_score"),
                "entry_price": row.get("entry_price"),
                "stop_price": row.get("stop_price"),
                "target_price": row.get("target_price"),
                "risk_reward": row.get("risk_reward"),
                "suggested_notional": row.get("suggested_notional"),
                "rationale": row.get("rationale"),
                "warnings": row.get("warnings"),
                "generated_at": generated_at,
            })

        db.commit()


_ALPHA_MODEL: Optional[ForexAlphaModel] = None


def get_forex_alpha_model() -> ForexAlphaModel:
    global _ALPHA_MODEL
    if _ALPHA_MODEL is None:
        _ALPHA_MODEL = ForexAlphaModel()
    return _ALPHA_MODEL


def run_forex_alpha_model(
    pairs: Optional[List[str]] = None,
    force_refresh: bool = False,
    save: bool = False,
    db=None,
) -> Dict[str, Any]:
    return get_forex_alpha_model().run_alpha_model(
        pairs=pairs,
        force_refresh=force_refresh,
        save=save,
        db=db,
    )


def get_top_forex_alpha_opportunities(
    pairs: Optional[List[str]] = None,
    limit: int = 10,
    min_alpha_score: float = 65.0,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    return get_forex_alpha_model().get_top_opportunities(
        pairs=pairs,
        limit=limit,
        min_alpha_score=min_alpha_score,
        force_refresh=force_refresh,
    )
