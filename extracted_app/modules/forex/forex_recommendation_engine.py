# modules/forex/forex_recommendation_engine.py

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
    from modules.forex.forex_ai import (
        ForexAIEngine,
        ForexAISignal,
        get_forex_ai_engine,
    )
    from modules.forex.forex_portfolio_engine import (
        ForexPortfolioEngine,
        get_forex_portfolio_engine,
    )
    from modules.forex.forex_strategy_engine import (
        ForexStrategyEngine,
        get_forex_strategy_engine,
    )
except Exception:
    from forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
    from forex_ai import (
        ForexAIEngine,
        ForexAISignal,
        get_forex_ai_engine,
    )
    from forex_portfolio_engine import (
        ForexPortfolioEngine,
        get_forex_portfolio_engine,
    )
    try:
        from forex_strategy_engine import (
            ForexStrategyEngine,
            get_forex_strategy_engine,
        )
    except Exception:
        ForexStrategyEngine = Any
        get_forex_strategy_engine = None


logger = logging.getLogger(__name__)

DEFAULT_RECOMMENDATION_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

RECOMMENDATIONS = {
    "STRONG_BUY",
    "BUY",
    "WATCH",
    "SELL",
    "STRONG_SELL",
}

DEFAULT_MIN_CONFIDENCE = 55.0
DEFAULT_MIN_RISK_REWARD = 1.0


@dataclass
class ForexRecommendation:
    recommendation_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair: str
    recommendation: str
    conviction_score: float
    confidence_score: float
    composite_score: float
    current_price: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    suggested_units: float
    max_position_value: float
    estimated_risk_dollars: float
    trend_score: float
    momentum_score: float
    volatility_score: float
    carry_score: float
    liquidity_score: float
    correlation_score: float
    macro_score: float
    risk_score: float
    strategy_score: float
    signal: str
    rationale: str
    warnings: str
    status: str
    source: str
    executed: bool
    executed_order_id: Optional[str]
    created_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexRecommendationScan:
    scan_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair_count: int
    recommendation_count: int
    strong_buy_count: int
    buy_count: int
    watch_count: int
    sell_count: int
    strong_sell_count: int
    avg_confidence: float
    avg_conviction: float
    top_pair: Optional[str]
    created_at: datetime
    recommendations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


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


def _round(value: Any, places: int = 2) -> float:
    return round(_safe_float(value), places)


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return getattr(row, key)
    except Exception:
        return default


class ForexRecommendationEngine:
    """
    Institutional Forex Recommendation Engine.

    Responsibilities:
    - Convert Forex AI/strategy outputs into actionable recommendations.
    - Persist recommendations in Neon Postgres.
    - Rank opportunities across currency pairs.
    - Produce position sizing metadata when an account is available.
    - Maintain tenant-safe, explicit-state architecture.
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        forex_ai_engine: Optional[ForexAIEngine] = None,
        forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
        forex_strategy_engine: Optional[ForexStrategyEngine] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db

        self.forex_service = forex_service or get_forex_service(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
        )
        self.forex_ai_engine = forex_ai_engine or get_forex_ai_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
            forex_service=self.forex_service,
        )
        self.forex_portfolio_engine = forex_portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
            forex_service=self.forex_service,
            forex_ai_engine=self.forex_ai_engine,
        )

        if forex_strategy_engine is not None:
            self.forex_strategy_engine = forex_strategy_engine
        elif get_forex_strategy_engine is not None:
            self.forex_strategy_engine = get_forex_strategy_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
                forex_service=self.forex_service,
                forex_ai_engine=self.forex_ai_engine,
                forex_portfolio_engine=self.forex_portfolio_engine,
            )
        else:
            self.forex_strategy_engine = None

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_recommendations (
                recommendation_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair VARCHAR(20) NOT NULL,
                recommendation VARCHAR(40),
                conviction_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                current_price DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                risk_reward DOUBLE PRECISION,
                suggested_units DOUBLE PRECISION,
                max_position_value DOUBLE PRECISION,
                estimated_risk_dollars DOUBLE PRECISION,
                trend_score DOUBLE PRECISION,
                momentum_score DOUBLE PRECISION,
                volatility_score DOUBLE PRECISION,
                carry_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                correlation_score DOUBLE PRECISION,
                macro_score DOUBLE PRECISION,
                risk_score DOUBLE PRECISION,
                strategy_score DOUBLE PRECISION,
                signal VARCHAR(60),
                rationale TEXT,
                warnings TEXT,
                status VARCHAR(40),
                source VARCHAR(80),
                executed BOOLEAN DEFAULT FALSE,
                executed_order_id VARCHAR(100),
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_recommendations_tenant_pair_created
            ON forex_recommendations (tenant_id, pair, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_recommendations_tenant_status
            ON forex_recommendations (tenant_id, status, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_recommendation_scans (
                scan_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair_count INTEGER,
                recommendation_count INTEGER,
                strong_buy_count INTEGER,
                buy_count INTEGER,
                watch_count INTEGER,
                sell_count INTEGER,
                strong_sell_count INTEGER,
                avg_confidence DOUBLE PRECISION,
                avg_conviction DOUBLE PRECISION,
                top_pair VARCHAR(20),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def generate_recommendation(
        self,
        pair: str,
        *,
        account_id: Optional[str] = None,
        risk_pct: float = 0.02,
        save: bool = True,
    ) -> ForexRecommendation:
        normalized_pair = normalize_pair(pair)
        ai_signal = self.forex_ai_engine.generate_signal(normalized_pair, save=True)

        strategy_score = self._strategy_score(
            pair=normalized_pair,
            account_id=account_id,
        )

        risk_score = self._risk_score(ai_signal)
        conviction_score = self._conviction_score(
            ai_signal=ai_signal,
            strategy_score=strategy_score,
            risk_score=risk_score,
        )

        recommendation = self._recommendation_from_scores(
            conviction_score=conviction_score,
            confidence_score=ai_signal.confidence,
            risk_reward=ai_signal.risk_reward,
        )

        sizing = self._position_sizing(
            account_id=account_id,
            pair=normalized_pair,
            entry_price=ai_signal.entry_price,
            stop_price=ai_signal.stop_price,
            risk_pct=risk_pct,
        )

        quote = self.forex_service.get_quote(normalized_pair)

        rec = ForexRecommendation(
            recommendation_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair=normalized_pair,
            recommendation=recommendation,
            conviction_score=_round(conviction_score),
            confidence_score=_round(ai_signal.confidence),
            composite_score=_round(ai_signal.composite_score),
            current_price=_round(quote.price, 6),
            entry_price=_round(ai_signal.entry_price, 6),
            stop_price=_round(ai_signal.stop_price, 6),
            target_price=_round(ai_signal.target_price, 6),
            risk_reward=_round(ai_signal.risk_reward),
            suggested_units=_round(sizing.get("suggested_units", 0.0), 2),
            max_position_value=_round(sizing.get("notional_value", 0.0), 2),
            estimated_risk_dollars=_round(sizing.get("max_risk_dollars", 0.0), 2),
            trend_score=_round(ai_signal.trend_score),
            momentum_score=_round(ai_signal.momentum_score),
            volatility_score=_round(ai_signal.volatility_score),
            carry_score=_round(ai_signal.carry_score),
            liquidity_score=_round(ai_signal.liquidity_score),
            correlation_score=_round(ai_signal.correlation_score),
            macro_score=_round(ai_signal.macro_score),
            risk_score=_round(risk_score),
            strategy_score=_round(strategy_score),
            signal=self._signal_label(recommendation),
            rationale=self._build_rationale(
                pair=normalized_pair,
                recommendation=recommendation,
                conviction_score=conviction_score,
                ai_signal=ai_signal,
                strategy_score=strategy_score,
                risk_score=risk_score,
            ),
            warnings=self._build_warnings(ai_signal, sizing),
            status="ACTIVE",
            source="FOREX_RECOMMENDATION_ENGINE",
            executed=False,
            executed_order_id=None,
            created_at=_utc_now(),
            raw={
                "ai_signal": ai_signal.to_dict(),
                "sizing": sizing,
                "strategy_score": strategy_score,
                "risk_score": risk_score,
            },
        )

        if save:
            self.save_recommendation(rec)

        return rec

    def generate_recommendations(
        self,
        pairs: Optional[List[str]] = None,
        *,
        account_id: Optional[str] = None,
        risk_pct: float = 0.02,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_risk_reward: float = DEFAULT_MIN_RISK_REWARD,
        save: bool = True,
    ) -> List[ForexRecommendation]:
        selected_pairs = pairs or DEFAULT_RECOMMENDATION_PAIRS
        recommendations: List[ForexRecommendation] = []

        for pair in selected_pairs:
            try:
                rec = self.generate_recommendation(
                    pair,
                    account_id=account_id,
                    risk_pct=risk_pct,
                    save=save,
                )

                if (
                    rec.confidence_score >= min_confidence
                    and rec.risk_reward >= min_risk_reward
                ):
                    recommendations.append(rec)

            except Exception as exc:
                logger.warning("Failed to generate Forex recommendation for %s: %s", pair, exc)

        return self.rank_recommendations(recommendations)

    def run_scan(
        self,
        pairs: Optional[List[str]] = None,
        *,
        account_id: Optional[str] = None,
        risk_pct: float = 0.02,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_risk_reward: float = DEFAULT_MIN_RISK_REWARD,
        limit: Optional[int] = None,
        save: bool = True,
    ) -> ForexRecommendationScan:
        selected_pairs = pairs or DEFAULT_RECOMMENDATION_PAIRS

        recommendations = self.generate_recommendations(
            selected_pairs,
            account_id=account_id,
            risk_pct=risk_pct,
            min_confidence=min_confidence,
            min_risk_reward=min_risk_reward,
            save=save,
        )

        if limit:
            recommendations = recommendations[: int(limit)]

        strong_buy_count = len([r for r in recommendations if r.recommendation == "STRONG_BUY"])
        buy_count = len([r for r in recommendations if r.recommendation == "BUY"])
        watch_count = len([r for r in recommendations if r.recommendation == "WATCH"])
        sell_count = len([r for r in recommendations if r.recommendation == "SELL"])
        strong_sell_count = len([r for r in recommendations if r.recommendation == "STRONG_SELL"])

        avg_confidence = (
            sum(r.confidence_score for r in recommendations) / len(recommendations)
            if recommendations
            else 0.0
        )
        avg_conviction = (
            sum(r.conviction_score for r in recommendations) / len(recommendations)
            if recommendations
            else 0.0
        )

        scan = ForexRecommendationScan(
            scan_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair_count=len(selected_pairs),
            recommendation_count=len(recommendations),
            strong_buy_count=strong_buy_count,
            buy_count=buy_count,
            watch_count=watch_count,
            sell_count=sell_count,
            strong_sell_count=strong_sell_count,
            avg_confidence=_round(avg_confidence),
            avg_conviction=_round(avg_conviction),
            top_pair=recommendations[0].pair if recommendations else None,
            created_at=_utc_now(),
            recommendations=[r.to_dict() for r in recommendations],
        )

        if save:
            self.save_scan(scan)

        return scan

    def rank_recommendations(
        self,
        recommendations: List[ForexRecommendation],
    ) -> List[ForexRecommendation]:
        return sorted(
            recommendations,
            key=lambda r: (
                r.conviction_score,
                r.confidence_score,
                r.risk_reward,
                r.liquidity_score,
            ),
            reverse=True,
        )

    def get_top_recommendations(
        self,
        *,
        pairs: Optional[List[str]] = None,
        account_id: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        min_risk_reward: float = DEFAULT_MIN_RISK_REWARD,
        save: bool = True,
    ) -> List[ForexRecommendation]:
        scan = self.run_scan(
            pairs=pairs,
            account_id=account_id,
            min_confidence=min_confidence,
            min_risk_reward=min_risk_reward,
            limit=limit,
            save=save,
        )
        return [
            self._recommendation_from_dict(row)
            for row in scan.recommendations
        ]

    def mark_executed(
        self,
        *,
        recommendation_id: str,
        executed_order_id: str,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()
        self.db.execute(
            """
            UPDATE forex_recommendations
            SET executed = TRUE,
                executed_order_id = :executed_order_id,
                status = 'EXECUTED'
            WHERE tenant_id = :tenant_id
              AND recommendation_id = :recommendation_id
            """,
            {
                "tenant_id": self.tenant_id,
                "recommendation_id": recommendation_id,
                "executed_order_id": executed_order_id,
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_recommendation(self, rec: ForexRecommendation) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_recommendations (
                recommendation_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair,
                recommendation,
                conviction_score,
                confidence_score,
                composite_score,
                current_price,
                entry_price,
                stop_price,
                target_price,
                risk_reward,
                suggested_units,
                max_position_value,
                estimated_risk_dollars,
                trend_score,
                momentum_score,
                volatility_score,
                carry_score,
                liquidity_score,
                correlation_score,
                macro_score,
                risk_score,
                strategy_score,
                signal,
                rationale,
                warnings,
                status,
                source,
                executed,
                executed_order_id,
                raw_payload,
                created_at
            )
            VALUES (
                :recommendation_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair,
                :recommendation,
                :conviction_score,
                :confidence_score,
                :composite_score,
                :current_price,
                :entry_price,
                :stop_price,
                :target_price,
                :risk_reward,
                :suggested_units,
                :max_position_value,
                :estimated_risk_dollars,
                :trend_score,
                :momentum_score,
                :volatility_score,
                :carry_score,
                :liquidity_score,
                :correlation_score,
                :macro_score,
                :risk_score,
                :strategy_score,
                :signal,
                :rationale,
                :warnings,
                :status,
                :source,
                :executed,
                :executed_order_id,
                :raw_payload,
                :created_at
            )
            ON CONFLICT (recommendation_id)
            DO UPDATE SET
                recommendation = EXCLUDED.recommendation,
                conviction_score = EXCLUDED.conviction_score,
                confidence_score = EXCLUDED.confidence_score,
                composite_score = EXCLUDED.composite_score,
                current_price = EXCLUDED.current_price,
                entry_price = EXCLUDED.entry_price,
                stop_price = EXCLUDED.stop_price,
                target_price = EXCLUDED.target_price,
                risk_reward = EXCLUDED.risk_reward,
                suggested_units = EXCLUDED.suggested_units,
                max_position_value = EXCLUDED.max_position_value,
                estimated_risk_dollars = EXCLUDED.estimated_risk_dollars,
                trend_score = EXCLUDED.trend_score,
                momentum_score = EXCLUDED.momentum_score,
                volatility_score = EXCLUDED.volatility_score,
                carry_score = EXCLUDED.carry_score,
                liquidity_score = EXCLUDED.liquidity_score,
                correlation_score = EXCLUDED.correlation_score,
                macro_score = EXCLUDED.macro_score,
                risk_score = EXCLUDED.risk_score,
                strategy_score = EXCLUDED.strategy_score,
                signal = EXCLUDED.signal,
                rationale = EXCLUDED.rationale,
                warnings = EXCLUDED.warnings,
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                executed = EXCLUDED.executed,
                executed_order_id = EXCLUDED.executed_order_id,
                raw_payload = EXCLUDED.raw_payload
            """,
            {
                **rec.to_dict(),
                "raw_payload": _json(rec.raw),
                "created_at": _naive(rec.created_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_scan(self, scan: ForexRecommendationScan) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_recommendation_scans (
                scan_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair_count,
                recommendation_count,
                strong_buy_count,
                buy_count,
                watch_count,
                sell_count,
                strong_sell_count,
                avg_confidence,
                avg_conviction,
                top_pair,
                payload,
                created_at
            )
            VALUES (
                :scan_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair_count,
                :recommendation_count,
                :strong_buy_count,
                :buy_count,
                :watch_count,
                :sell_count,
                :strong_sell_count,
                :avg_confidence,
                :avg_conviction,
                :top_pair,
                :payload,
                :created_at
            )
            ON CONFLICT (scan_id) DO NOTHING
            """,
            {
                **scan.to_dict(),
                "payload": _json(scan.to_dict()),
                "created_at": _naive(scan.created_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_recommendations(
        self,
        *,
        pair: Optional[str] = None,
        status: str = "ACTIVE",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        params: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "limit": int(limit),
        }

        where = "tenant_id = :tenant_id"

        if pair:
            where += " AND pair = :pair"
            params["pair"] = normalize_pair(pair)

        if status and status.upper() != "ALL":
            where += " AND status = :status"
            params["status"] = status.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_recommendations
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [self._row_to_recommendation_dict(row) for row in rows]

    def load_scans(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = self.db.execute(
            """
            SELECT *
            FROM forex_recommendation_scans
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {
                "tenant_id": self.tenant_id,
                "limit": int(limit),
            },
        ).fetchall()

        return [
            {
                "scan_id": _row_get(row, "scan_id"),
                "pair_count": _row_get(row, "pair_count"),
                "recommendation_count": _row_get(row, "recommendation_count"),
                "strong_buy_count": _row_get(row, "strong_buy_count"),
                "buy_count": _row_get(row, "buy_count"),
                "watch_count": _row_get(row, "watch_count"),
                "sell_count": _row_get(row, "sell_count"),
                "strong_sell_count": _row_get(row, "strong_sell_count"),
                "avg_confidence": _row_get(row, "avg_confidence"),
                "avg_conviction": _row_get(row, "avg_conviction"),
                "top_pair": _row_get(row, "top_pair"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _strategy_score(
        self,
        *,
        pair: str,
        account_id: Optional[str] = None,
    ) -> float:
        if self.forex_strategy_engine is None:
            return 65.0

        try:
            rows = self.forex_strategy_engine.rank_strategies(
                pair=pair,
                account_id=account_id,
            )
            if not rows:
                return 65.0

            top = rows[0]
            return _safe_float(top.get("confidence"), 65.0)

        except Exception as exc:
            logger.warning("Strategy score failed for %s: %s", pair, exc)
            return 65.0

    def _risk_score(self, ai_signal: ForexAISignal) -> float:
        liquidity = _safe_float(ai_signal.liquidity_score)
        volatility = _safe_float(ai_signal.volatility_score)
        risk_reward = _safe_float(ai_signal.risk_reward)

        rr_score = min(100.0, risk_reward * 35.0)

        score = (
            liquidity * 0.35
            + volatility * 0.30
            + rr_score * 0.25
            + _safe_float(ai_signal.correlation_score) * 0.10
        )

        return max(0.0, min(100.0, score))

    def _conviction_score(
        self,
        *,
        ai_signal: ForexAISignal,
        strategy_score: float,
        risk_score: float,
    ) -> float:
        score = (
            _safe_float(ai_signal.composite_score) * 0.35
            + _safe_float(ai_signal.confidence) * 0.25
            + strategy_score * 0.20
            + risk_score * 0.20
        )

        return max(0.0, min(100.0, score))

    def _recommendation_from_scores(
        self,
        *,
        conviction_score: float,
        confidence_score: float,
        risk_reward: float,
    ) -> str:
        if conviction_score >= 88 and confidence_score >= 80 and risk_reward >= 2.0:
            return "STRONG_BUY"

        if conviction_score >= 74 and confidence_score >= 65 and risk_reward >= 1.4:
            return "BUY"

        if conviction_score >= 55:
            return "WATCH"

        if conviction_score >= 42:
            return "SELL"

        return "STRONG_SELL"

    def _signal_label(self, recommendation: str) -> str:
        return {
            "STRONG_BUY": "HIGH_CONVICTION_LONG",
            "BUY": "LONG",
            "WATCH": "NEUTRAL_MONITOR",
            "SELL": "SHORT_OR_REDUCE",
            "STRONG_SELL": "HIGH_CONVICTION_SHORT",
        }.get(recommendation, "NEUTRAL_MONITOR")

    def _position_sizing(
        self,
        *,
        account_id: Optional[str],
        pair: str,
        entry_price: float,
        stop_price: float,
        risk_pct: float,
    ) -> Dict[str, Any]:
        if not account_id:
            return {
                "suggested_units": 0.0,
                "notional_value": 0.0,
                "max_risk_dollars": 0.0,
                "is_affordable": False,
                "reason": "No account_id supplied.",
            }

        try:
            return self.forex_portfolio_engine.position_size_from_risk(
                account_id=account_id,
                pair=pair,
                entry_price=entry_price,
                stop_price=stop_price,
                risk_pct=risk_pct,
            )
        except Exception as exc:
            return {
                "suggested_units": 0.0,
                "notional_value": 0.0,
                "max_risk_dollars": 0.0,
                "is_affordable": False,
                "reason": str(exc),
            }

    def _build_rationale(
        self,
        *,
        pair: str,
        recommendation: str,
        conviction_score: float,
        ai_signal: ForexAISignal,
        strategy_score: float,
        risk_score: float,
    ) -> str:
        return (
            f"{pair} is rated {recommendation} with conviction "
            f"{conviction_score:.2f}. AI composite is {ai_signal.composite_score:.2f}, "
            f"confidence is {ai_signal.confidence:.2f}, strategy score is "
            f"{strategy_score:.2f}, and risk score is {risk_score:.2f}. "
            f"Trade setup uses entry {ai_signal.entry_price:.6f}, stop "
            f"{ai_signal.stop_price:.6f}, target {ai_signal.target_price:.6f}, "
            f"and risk/reward {ai_signal.risk_reward:.2f}."
        )

    def _build_warnings(
        self,
        ai_signal: ForexAISignal,
        sizing: Dict[str, Any],
    ) -> str:
        warnings: List[str] = []

        if ai_signal.warnings:
            warnings.append(ai_signal.warnings)

        if ai_signal.risk_reward < 1.5:
            warnings.append("Risk/reward is below preferred trading threshold.")

        if ai_signal.liquidity_score < 60:
            warnings.append("Liquidity score is below preferred threshold.")

        if sizing and sizing.get("is_affordable") is False:
            reason = sizing.get("reason") or "Position may not be affordable under current risk settings."
            warnings.append(str(reason))

        return " ".join(warnings)

    def _recommendation_from_dict(self, row: Dict[str, Any]) -> ForexRecommendation:
        created_at_raw = row.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        else:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
            except Exception:
                created_at = _utc_now()

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        return ForexRecommendation(
            recommendation_id=row.get("recommendation_id") or str(uuid.uuid4()),
            tenant_id=row.get("tenant_id"),
            user_id=row.get("user_id"),
            portfolio_id=row.get("portfolio_id"),
            pair=row.get("pair"),
            recommendation=row.get("recommendation"),
            conviction_score=_safe_float(row.get("conviction_score")),
            confidence_score=_safe_float(row.get("confidence_score")),
            composite_score=_safe_float(row.get("composite_score")),
            current_price=_safe_float(row.get("current_price")),
            entry_price=_safe_float(row.get("entry_price")),
            stop_price=_safe_float(row.get("stop_price")),
            target_price=_safe_float(row.get("target_price")),
            risk_reward=_safe_float(row.get("risk_reward")),
            suggested_units=_safe_float(row.get("suggested_units")),
            max_position_value=_safe_float(row.get("max_position_value")),
            estimated_risk_dollars=_safe_float(row.get("estimated_risk_dollars")),
            trend_score=_safe_float(row.get("trend_score")),
            momentum_score=_safe_float(row.get("momentum_score")),
            volatility_score=_safe_float(row.get("volatility_score")),
            carry_score=_safe_float(row.get("carry_score")),
            liquidity_score=_safe_float(row.get("liquidity_score")),
            correlation_score=_safe_float(row.get("correlation_score")),
            macro_score=_safe_float(row.get("macro_score")),
            risk_score=_safe_float(row.get("risk_score")),
            strategy_score=_safe_float(row.get("strategy_score")),
            signal=row.get("signal", ""),
            rationale=row.get("rationale", ""),
            warnings=row.get("warnings", ""),
            status=row.get("status", "ACTIVE"),
            source=row.get("source", "FOREX_RECOMMENDATION_ENGINE"),
            executed=bool(row.get("executed", False)),
            executed_order_id=row.get("executed_order_id"),
            created_at=created_at,
            raw=row.get("raw"),
        )

    def _row_to_recommendation_dict(self, row: Any) -> Dict[str, Any]:
        return {
            "recommendation_id": _row_get(row, "recommendation_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "pair": _row_get(row, "pair"),
            "recommendation": _row_get(row, "recommendation"),
            "conviction_score": _row_get(row, "conviction_score"),
            "confidence_score": _row_get(row, "confidence_score"),
            "composite_score": _row_get(row, "composite_score"),
            "current_price": _row_get(row, "current_price"),
            "entry_price": _row_get(row, "entry_price"),
            "stop_price": _row_get(row, "stop_price"),
            "target_price": _row_get(row, "target_price"),
            "risk_reward": _row_get(row, "risk_reward"),
            "suggested_units": _row_get(row, "suggested_units"),
            "max_position_value": _row_get(row, "max_position_value"),
            "estimated_risk_dollars": _row_get(row, "estimated_risk_dollars"),
            "trend_score": _row_get(row, "trend_score"),
            "momentum_score": _row_get(row, "momentum_score"),
            "volatility_score": _row_get(row, "volatility_score"),
            "carry_score": _row_get(row, "carry_score"),
            "liquidity_score": _row_get(row, "liquidity_score"),
            "correlation_score": _row_get(row, "correlation_score"),
            "macro_score": _row_get(row, "macro_score"),
            "risk_score": _row_get(row, "risk_score"),
            "strategy_score": _row_get(row, "strategy_score"),
            "signal": _row_get(row, "signal"),
            "rationale": _row_get(row, "rationale"),
            "warnings": _row_get(row, "warnings"),
            "status": _row_get(row, "status"),
            "source": _row_get(row, "source"),
            "executed": _row_get(row, "executed"),
            "executed_order_id": _row_get(row, "executed_order_id"),
            "created_at": str(_row_get(row, "created_at", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_recommendation_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    forex_ai_engine: Optional[ForexAIEngine] = None,
    forex_portfolio_engine: Optional[ForexPortfolioEngine] = None,
    forex_strategy_engine: Optional[ForexStrategyEngine] = None,
) -> ForexRecommendationEngine:
    return ForexRecommendationEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
        forex_ai_engine=forex_ai_engine,
        forex_portfolio_engine=forex_portfolio_engine,
        forex_strategy_engine=forex_strategy_engine,
    )


def generate_forex_recommendation(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_recommendation_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.generate_recommendation(
        pair,
        account_id=account_id,
        save=save,
    ).to_dict()


def run_forex_recommendation_scan(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    limit: Optional[int] = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_recommendation_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.run_scan(
        pairs=pairs,
        account_id=account_id,
        limit=limit,
        save=save,
    ).to_dict()