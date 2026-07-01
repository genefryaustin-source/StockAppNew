# modules/forex/forex_ai.py

from __future__ import annotations

import json
import math
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from modules.forex.forex_service import (
        ForexService,
        ForexQuote,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from modules.forex.forex_common import (
        normalize_pair,
        split_pair,
    )

except Exception as e:
    print("=" * 80)
    print("FOREX_AI IMPORT FAILURE")
    print(type(e).__name__)
    print(e)
    print("=" * 80)
    raise

logger = logging.getLogger(__name__)


DEFAULT_FOREX_AI_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexAISignal:
    pair: str
    recommendation: str
    confidence: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    trend_score: float
    momentum_score: float
    volatility_score: float
    carry_score: float
    liquidity_score: float
    correlation_score: float
    macro_score: float
    composite_score: float
    rationale: str
    warnings: str
    provider: str
    asof: datetime
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexPairScore:
    pair: str
    price: float
    trend_score: float
    momentum_score: float
    volatility_score: float
    carry_score: float
    liquidity_score: float
    correlation_score: float
    macro_score: float
    composite_score: float
    confidence: float
    provider: str
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _round(value: float, places: int = 2) -> float:
    return round(_safe_float(value), places)


def _json_payload(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return payload
    try:
        return json.loads(json.dumps(payload, default=str))
    except Exception:
        return {"value": str(payload)}


class ForexTrendAnalyzer:
    def score(self, quote: ForexQuote, historical_prices: Optional[List[float]] = None) -> float:
        prices = [p for p in (historical_prices or []) if _safe_float(p) > 0]

        if len(prices) < 3:
            return 55.0 if quote.price > 0 else 50.0

        first = prices[0]
        last = prices[-1]

        if first <= 0:
            return 50.0

        pct_change = ((last - first) / first) * 100
        return _clamp(50 + pct_change * 8)


class ForexMomentumAnalyzer:
    def score(self, quote: ForexQuote, historical_prices: Optional[List[float]] = None) -> float:
        prices = [p for p in (historical_prices or []) if _safe_float(p) > 0]

        if len(prices) < 5:
            return 52.0

        short_window = prices[-3:]
        long_window = prices[-10:] if len(prices) >= 10 else prices

        short_avg = sum(short_window) / len(short_window)
        long_avg = sum(long_window) / len(long_window)

        if long_avg <= 0:
            return 50.0

        momentum = ((short_avg - long_avg) / long_avg) * 100
        return _clamp(50 + momentum * 10)


class ForexVolatilityAnalyzer:
    def score(self, quote: ForexQuote, historical_prices: Optional[List[float]] = None) -> float:
        prices = [p for p in (historical_prices or []) if _safe_float(p) > 0]

        if len(prices) < 5:
            return 65.0

        returns: List[float] = []

        for index in range(1, len(prices)):
            previous = prices[index - 1]
            current = prices[index]
            if previous > 0:
                returns.append((current - previous) / previous)

        if not returns:
            return 60.0

        avg_return = sum(returns) / len(returns)
        variance = sum((value - avg_return) ** 2 for value in returns) / len(returns)
        volatility = math.sqrt(variance) * 100

        return _clamp(100 - volatility * 18)


class ForexCarryTradeAnalyzer:
    POSITIVE_CARRY = {
        "USD": 72.0,
        "GBP": 68.0,
        "AUD": 66.0,
        "NZD": 64.0,
        "CAD": 62.0,
        "EUR": 54.0,
        "CHF": 42.0,
        "JPY": 35.0,
    }

    def score(self, pair: str) -> float:
        base, quote = split_pair(pair)

        base_score = self.POSITIVE_CARRY.get(base, 55.0)
        quote_score = self.POSITIVE_CARRY.get(quote, 55.0)

        return _clamp(50 + (base_score - quote_score) * 0.75)


class ForexCorrelationAnalyzer:
    SAFE_DIVERSIFICATION_SCORE = 74.0

    def score(
        self,
        pair: str,
        portfolio_pairs: Optional[List[str]] = None,
    ) -> float:
        if not portfolio_pairs:
            return self.SAFE_DIVERSIFICATION_SCORE

        base, quote = split_pair(pair)
        overlap_count = 0

        for existing_pair in portfolio_pairs:
            try:
                existing_base, existing_quote = split_pair(existing_pair)
                if base in {existing_base, existing_quote}:
                    overlap_count += 1
                if quote in {existing_base, existing_quote}:
                    overlap_count += 1
            except Exception:
                continue

        penalty = min(45.0, overlap_count * 7.5)
        return _clamp(85.0 - penalty)


class ForexRiskScoringEngine:
    def liquidity_score(self, quote: ForexQuote) -> float:
        spread = _safe_float(quote.spread)

        if spread <= 0 and quote.bid and quote.ask:
            spread = abs(float(quote.ask) - float(quote.bid))

        if spread <= 0:
            return 70.0

        pip_factor = 100.0 if quote.quote == "JPY" else 10000.0
        spread_pips = spread * pip_factor

        return _clamp(100.0 - spread_pips * 8.0)

    def macro_score(self, pair: str) -> float:
        base, quote = split_pair(pair)

        safe_haven = {"USD", "CHF", "JPY"}
        commodity = {"AUD", "CAD", "NZD"}
        european = {"EUR", "GBP", "CHF"}

        score = 60.0

        if base in safe_haven:
            score += 6.0
        if quote in safe_haven:
            score -= 3.0
        if base in commodity:
            score += 3.0
        if base in european and quote == "USD":
            score += 2.0

        return _clamp(score)

    def risk_warning(self, signal: ForexAISignal) -> str:
        warnings: List[str] = []

        if signal.liquidity_score < 50:
            warnings.append("Wider spread or limited liquidity detected.")

        if signal.volatility_score < 45:
            warnings.append("Elevated volatility risk detected.")

        if signal.risk_reward < 1.5:
            warnings.append("Risk/reward is below preferred threshold.")

        if signal.confidence < 65:
            warnings.append("Signal confidence is moderate or weak.")

        return " ".join(warnings)


class ForexSignalGenerator:
    def recommendation_from_score(self, composite_score: float, confidence: float) -> str:
        if composite_score >= 85 and confidence >= 80:
            return "STRONG_BUY"
        if composite_score >= 74 and confidence >= 65:
            return "BUY"
        if composite_score >= 55:
            return "WATCH"
        if composite_score >= 42:
            return "REDUCE"
        return "SELL"

    def trade_levels(self, quote: ForexQuote, composite_score: float) -> Tuple[float, float, float, float]:
        price = float(quote.price)

        if price <= 0:
            return 0.0, 0.0, 0.0, 0.0

        base_risk = 0.010
        if quote.quote == "JPY":
            base_risk = 0.008

        if composite_score >= 85:
            risk_pct = base_risk * 0.85
            reward_pct = base_risk * 2.7
        elif composite_score >= 74:
            risk_pct = base_risk
            reward_pct = base_risk * 2.2
        elif composite_score >= 55:
            risk_pct = base_risk * 0.75
            reward_pct = base_risk * 1.2
        else:
            risk_pct = base_risk * 0.7
            reward_pct = base_risk * 0.8

        entry = price
        stop = price * (1 - risk_pct)
        target = price * (1 + reward_pct)

        risk = abs(entry - stop)
        reward = abs(target - entry)

        risk_reward = reward / risk if risk > 0 else 0.0

        return (
            _round(entry, 6),
            _round(stop, 6),
            _round(target, 6),
            _round(risk_reward, 2),
        )

    def rationale(self, pair_score: ForexPairScore, recommendation: str) -> str:
        return (
            f"{pair_score.pair} generated a {recommendation} rating with a "
            f"{pair_score.composite_score:.2f} composite score and "
            f"{pair_score.confidence:.2f} confidence. "
            f"Trend={pair_score.trend_score:.2f}, Momentum={pair_score.momentum_score:.2f}, "
            f"Volatility={pair_score.volatility_score:.2f}, Carry={pair_score.carry_score:.2f}, "
            f"Liquidity={pair_score.liquidity_score:.2f}, Correlation={pair_score.correlation_score:.2f}, "
            f"Macro={pair_score.macro_score:.2f}."
        )


class ForexAIEngine:
    """
    Tenant-safe Forex AI intelligence layer.

    Rules:
    - No global runtime state.
    - All tenant/user/db context is passed explicitly.
    - Streamlit compatible.
    - Neon Postgres compatible.
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        portfolio_pairs: Optional[List[str]] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.db = db
        self.forex_service = forex_service or get_forex_service(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        self.portfolio_pairs = portfolio_pairs or []

        self.trend_analyzer = ForexTrendAnalyzer()
        self.momentum_analyzer = ForexMomentumAnalyzer()
        self.volatility_analyzer = ForexVolatilityAnalyzer()
        self.carry_analyzer = ForexCarryTradeAnalyzer()
        self.correlation_analyzer = ForexCorrelationAnalyzer()
        self.risk_engine = ForexRiskScoringEngine()
        self.signal_generator = ForexSignalGenerator()

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_ai_signals (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                pair VARCHAR(20) NOT NULL,
                recommendation VARCHAR(40) NOT NULL,
                confidence DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                risk_reward DOUBLE PRECISION,
                trend_score DOUBLE PRECISION,
                momentum_score DOUBLE PRECISION,
                volatility_score DOUBLE PRECISION,
                carry_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                correlation_score DOUBLE PRECISION,
                macro_score DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                rationale TEXT,
                warnings TEXT,
                provider VARCHAR(80),
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_ai_signals_tenant_pair_asof
            ON forex_ai_signals (tenant_id, pair, asof DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_ai_history (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                pair VARCHAR(20),
                event_type VARCHAR(80),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_model_snapshots (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                snapshot_name VARCHAR(120),
                model_version VARCHAR(80),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def score_pair(
        self,
        pair: str,
        *,
        historical_prices: Optional[List[float]] = None,
        portfolio_pairs: Optional[List[str]] = None,
    ) -> ForexPairScore:
        normalized_pair = normalize_pair(pair)
        quote = self.forex_service.get_quote(normalized_pair)

        trend_score = self.trend_analyzer.score(quote, historical_prices)
        momentum_score = self.momentum_analyzer.score(quote, historical_prices)
        volatility_score = self.volatility_analyzer.score(quote, historical_prices)
        carry_score = self.carry_analyzer.score(normalized_pair)
        liquidity_score = self.risk_engine.liquidity_score(quote)
        correlation_score = self.correlation_analyzer.score(
            normalized_pair,
            portfolio_pairs or self.portfolio_pairs,
        )
        macro_score = self.risk_engine.macro_score(normalized_pair)

        composite_score = (
            trend_score * 0.22
            + momentum_score * 0.18
            + volatility_score * 0.13
            + carry_score * 0.12
            + liquidity_score * 0.15
            + correlation_score * 0.10
            + macro_score * 0.10
        )

        confidence = (
            composite_score * 0.72
            + liquidity_score * 0.12
            + volatility_score * 0.08
            + correlation_score * 0.08
        )

        return ForexPairScore(
            pair=normalized_pair,
            price=_round(quote.price, 6),
            trend_score=_round(trend_score),
            momentum_score=_round(momentum_score),
            volatility_score=_round(volatility_score),
            carry_score=_round(carry_score),
            liquidity_score=_round(liquidity_score),
            correlation_score=_round(correlation_score),
            macro_score=_round(macro_score),
            composite_score=_round(composite_score),
            confidence=_round(confidence),
            provider=quote.provider,
            asof=quote.asof or _utc_now(),
            raw={
                "quote": quote.to_dict(),
                "historical_points": len(historical_prices or []),
            },
        )

    def generate_signal(
        self,
        pair: str,
        *,
        historical_prices: Optional[List[float]] = None,
        portfolio_pairs: Optional[List[str]] = None,
        save: bool = True,
    ) -> ForexAISignal:
        score = self.score_pair(
            pair,
            historical_prices=historical_prices,
            portfolio_pairs=portfolio_pairs,
        )

        recommendation = self.signal_generator.recommendation_from_score(
            score.composite_score,
            score.confidence,
        )

        quote = self.forex_service.get_quote(score.pair)

        entry_price, stop_price, target_price, risk_reward = self.signal_generator.trade_levels(
            quote,
            score.composite_score,
        )

        signal = ForexAISignal(
            pair=score.pair,
            recommendation=recommendation,
            confidence=score.confidence,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk_reward=risk_reward,
            trend_score=score.trend_score,
            momentum_score=score.momentum_score,
            volatility_score=score.volatility_score,
            carry_score=score.carry_score,
            liquidity_score=score.liquidity_score,
            correlation_score=score.correlation_score,
            macro_score=score.macro_score,
            composite_score=score.composite_score,
            rationale=self.signal_generator.rationale(score, recommendation),
            warnings="",
            provider=score.provider,
            asof=_utc_now(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            raw={
                "score": score.to_dict(),
            },
        )

        signal.warnings = self.risk_engine.risk_warning(signal)

        if save:
            self.save_signal(signal)

        return signal

    def generate_signals(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
    ) -> List[ForexAISignal]:
        selected_pairs = pairs or DEFAULT_FOREX_AI_PAIRS
        signals: List[ForexAISignal] = []

        for pair in selected_pairs:
            try:
                signals.append(self.generate_signal(pair, save=save))
            except Exception as exc:
                logger.warning("Failed to generate forex signal for %s: %s", pair, exc)

        return signals

    def rank_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        limit: Optional[int] = None,
    ) -> List[ForexAISignal]:
        signals = self.generate_signals(pairs, save=False)
        ranked = sorted(
            signals,
            key=lambda item: (
                item.composite_score,
                item.confidence,
                item.risk_reward,
            ),
            reverse=True,
        )

        if limit:
            return ranked[: int(limit)]

        return ranked

    def get_top_opportunities(
        self,
        pairs: Optional[List[str]] = None,
        *,
        min_confidence: float = 65.0,
        min_risk_reward: float = 1.5,
        limit: int = 10,
        save: bool = True,
    ) -> List[ForexAISignal]:
        signals = self.generate_signals(pairs, save=save)

        filtered = [
            signal
            for signal in signals
            if signal.confidence >= min_confidence
            and signal.risk_reward >= min_risk_reward
            and signal.recommendation in {"STRONG_BUY", "BUY", "WATCH"}
        ]

        return sorted(
            filtered,
            key=lambda item: (
                item.composite_score,
                item.confidence,
                item.risk_reward,
            ),
            reverse=True,
        )[: int(limit)]

    def save_signal(self, signal: ForexAISignal) -> None:
        if self.db is None:
            return

        try:
            self.ensure_tables()

            self.db.execute(
                """
                INSERT INTO forex_ai_signals (
                    tenant_id,
                    user_id,
                    pair,
                    recommendation,
                    confidence,
                    entry_price,
                    stop_price,
                    target_price,
                    risk_reward,
                    trend_score,
                    momentum_score,
                    volatility_score,
                    carry_score,
                    liquidity_score,
                    correlation_score,
                    macro_score,
                    composite_score,
                    rationale,
                    warnings,
                    provider,
                    raw_payload,
                    asof
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    :pair,
                    :recommendation,
                    :confidence,
                    :entry_price,
                    :stop_price,
                    :target_price,
                    :risk_reward,
                    :trend_score,
                    :momentum_score,
                    :volatility_score,
                    :carry_score,
                    :liquidity_score,
                    :correlation_score,
                    :macro_score,
                    :composite_score,
                    :rationale,
                    :warnings,
                    :provider,
                    :raw_payload,
                    :asof
                )
                """,
                {
                    "tenant_id": signal.tenant_id,
                    "user_id": signal.user_id,
                    "pair": signal.pair,
                    "recommendation": signal.recommendation,
                    "confidence": signal.confidence,
                    "entry_price": signal.entry_price,
                    "stop_price": signal.stop_price,
                    "target_price": signal.target_price,
                    "risk_reward": signal.risk_reward,
                    "trend_score": signal.trend_score,
                    "momentum_score": signal.momentum_score,
                    "volatility_score": signal.volatility_score,
                    "carry_score": signal.carry_score,
                    "liquidity_score": signal.liquidity_score,
                    "correlation_score": signal.correlation_score,
                    "macro_score": signal.macro_score,
                    "composite_score": signal.composite_score,
                    "rationale": signal.rationale,
                    "warnings": signal.warnings,
                    "provider": signal.provider,
                    "raw_payload": _json_payload(signal.raw),
                    "asof": signal.asof.replace(tzinfo=None),
                },
            )

            self.db.execute(
                """
                INSERT INTO forex_ai_history (
                    tenant_id,
                    user_id,
                    pair,
                    event_type,
                    payload
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    :pair,
                    :event_type,
                    :payload
                )
                """,
                {
                    "tenant_id": signal.tenant_id,
                    "user_id": signal.user_id,
                    "pair": signal.pair,
                    "event_type": "SIGNAL_GENERATED",
                    "payload": _json_payload(signal.to_dict()),
                },
            )

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to save forex AI signal: %s", exc)
            try:
                if hasattr(self.db, "rollback"):
                    self.db.rollback()
            except Exception:
                pass

    def load_signal_history(
        self,
        pair: Optional[str] = None,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        try:
            self.ensure_tables()

            params: Dict[str, Any] = {
                "tenant_id": self.tenant_id,
                "limit": int(limit),
            }

            where = "WHERE tenant_id = :tenant_id"

            if pair:
                where += " AND pair = :pair"
                params["pair"] = normalize_pair(pair)

            rows = self.db.execute(
                f"""
                SELECT
                    pair,
                    recommendation,
                    confidence,
                    entry_price,
                    stop_price,
                    target_price,
                    risk_reward,
                    trend_score,
                    momentum_score,
                    volatility_score,
                    carry_score,
                    liquidity_score,
                    correlation_score,
                    macro_score,
                    composite_score,
                    rationale,
                    warnings,
                    provider,
                    raw_payload,
                    asof,
                    created_at
                FROM forex_ai_signals
                {where}
                ORDER BY asof DESC
                LIMIT :limit
                """,
                params,
            ).fetchall()

            results: List[Dict[str, Any]] = []

            for row in rows:
                results.append(
                    {
                        "pair": row.pair,
                        "recommendation": row.recommendation,
                        "confidence": _safe_float(row.confidence),
                        "entry_price": _safe_float(row.entry_price),
                        "stop_price": _safe_float(row.stop_price),
                        "target_price": _safe_float(row.target_price),
                        "risk_reward": _safe_float(row.risk_reward),
                        "trend_score": _safe_float(row.trend_score),
                        "momentum_score": _safe_float(row.momentum_score),
                        "volatility_score": _safe_float(row.volatility_score),
                        "carry_score": _safe_float(row.carry_score),
                        "liquidity_score": _safe_float(row.liquidity_score),
                        "correlation_score": _safe_float(row.correlation_score),
                        "macro_score": _safe_float(row.macro_score),
                        "composite_score": _safe_float(row.composite_score),
                        "rationale": row.rationale,
                        "warnings": row.warnings,
                        "provider": row.provider,
                        "raw": row.raw_payload,
                        "asof": row.asof.isoformat() if row.asof else None,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )

            return results

        except Exception as exc:
            logger.warning("Failed to load forex signal history: %s", exc)
            return []

    def save_model_snapshot(
        self,
        *,
        snapshot_name: str = "forex_ai_model_snapshot",
        model_version: str = "forex-ai-v1",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.db is None:
            return

        try:
            self.ensure_tables()

            self.db.execute(
                """
                INSERT INTO forex_model_snapshots (
                    tenant_id,
                    user_id,
                    snapshot_name,
                    model_version,
                    payload
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    :snapshot_name,
                    :model_version,
                    :payload
                )
                """,
                {
                    "tenant_id": self.tenant_id,
                    "user_id": self.user_id,
                    "snapshot_name": snapshot_name,
                    "model_version": model_version,
                    "payload": _json_payload(
                        payload
                        or {
                            "weights": {
                                "trend": 0.22,
                                "momentum": 0.18,
                                "volatility": 0.13,
                                "carry": 0.12,
                                "liquidity": 0.15,
                                "correlation": 0.10,
                                "macro": 0.10,
                            },
                            "created_at": _utc_now().isoformat(),
                        }
                    ),
                },
            )

            if hasattr(self.db, "commit"):
                self.db.commit()

        except Exception as exc:
            logger.warning("Failed to save forex model snapshot: %s", exc)
            try:
                if hasattr(self.db, "rollback"):
                    self.db.rollback()
            except Exception:
                pass


def get_forex_ai_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    portfolio_pairs: Optional[List[str]] = None,
) -> ForexAIEngine:
    return ForexAIEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
        forex_service=forex_service,
        portfolio_pairs=portfolio_pairs,
    )


def generate_forex_signal(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_ai_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return engine.generate_signal(pair, save=save).to_dict()


def generate_forex_signals(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    save: bool = True,
) -> List[Dict[str, Any]]:
    engine = get_forex_ai_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return [signal.to_dict() for signal in engine.generate_signals(pairs, save=save)]


def rank_forex_pairs(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    engine = get_forex_ai_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return [signal.to_dict() for signal in engine.rank_pairs(pairs, limit=limit)]


def get_top_forex_opportunities(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    min_confidence: float = 65.0,
    min_risk_reward: float = 1.5,
    limit: int = 10,
    save: bool = True,
) -> List[Dict[str, Any]]:
    engine = get_forex_ai_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    return [
        signal.to_dict()
        for signal in engine.get_top_opportunities(
            pairs,
            min_confidence=min_confidence,
            min_risk_reward=min_risk_reward,
            limit=limit,
            save=save,
        )
    ]