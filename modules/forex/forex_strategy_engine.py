from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import ForexService, get_forex_service, normalize_pair, MAJOR_PAIRS, CROSS_PAIRS
    from modules.forex.forex_ai import ForexAIEngine, get_forex_ai_engine
    from modules.forex.forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine
except Exception:
    from forex_service import ForexService, get_forex_service, normalize_pair, MAJOR_PAIRS, CROSS_PAIRS
    from forex_ai import ForexAIEngine, get_forex_ai_engine
    from forex_portfolio_engine import ForexPortfolioEngine, get_forex_portfolio_engine

logger = logging.getLogger(__name__)

DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS
STRATEGY_TYPES = {"TREND_FOLLOWING", "MEAN_REVERSION", "BREAKOUT", "CARRY", "MOMENTUM", "AI_COMPOSITE"}


@dataclass
class ForexStrategySignal:
    signal_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    strategy_name: str
    strategy_type: str
    pair: str
    direction: str
    recommendation: str
    confidence: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    position_size_units: float
    composite_score: float
    rationale: str
    warnings: str
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexStrategyRun:
    run_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    strategy_name: str
    pair_count: int
    signal_count: int
    top_pair: Optional[str]
    avg_confidence: float
    created_at: datetime
    signals: List[Dict[str, Any]]

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


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        return {"value": str(value)}


class ForexStrategyEngine:
    """
    Forex Phase 2 strategy engine.
    Tenant-safe, no global state, Neon-compatible, Streamlit-compatible.
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
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db
        self.forex_service = forex_service or get_forex_service(tenant_id=tenant_id, user_id=user_id, db=db)
        self.forex_ai_engine = forex_ai_engine or get_forex_ai_engine(
            tenant_id=tenant_id, user_id=user_id, db=db, forex_service=self.forex_service
        )
        self.forex_portfolio_engine = forex_portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, db=db,
            forex_service=self.forex_service, forex_ai_engine=self.forex_ai_engine
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS forex_strategy_signals (
                signal_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                strategy_name VARCHAR(160),
                strategy_type VARCHAR(80),
                pair VARCHAR(20),
                direction VARCHAR(20),
                recommendation VARCHAR(40),
                confidence DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_price DOUBLE PRECISION,
                target_price DOUBLE PRECISION,
                risk_reward DOUBLE PRECISION,
                position_size_units DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                rationale TEXT,
                warnings TEXT,
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS forex_strategy_runs (
                run_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                strategy_name VARCHAR(160),
                pair_count INTEGER,
                signal_count INTEGER,
                top_pair VARCHAR(20),
                avg_confidence DOUBLE PRECISION,
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_forex_strategy_signals_tenant_pair ON forex_strategy_signals (tenant_id, pair, asof DESC)")
        if hasattr(self.db, "commit"):
            self.db.commit()

    def generate_strategy_signal(
        self,
        *,
        pair: str,
        strategy_type: str = "AI_COMPOSITE",
        account_id: Optional[str] = None,
        risk_pct: float = 0.02,
        save: bool = True,
    ) -> ForexStrategySignal:
        strategy_type = strategy_type.upper().strip()
        if strategy_type not in STRATEGY_TYPES:
            strategy_type = "AI_COMPOSITE"

        normalized_pair = normalize_pair(pair)
        ai_signal = self.forex_ai_engine.generate_signal(normalized_pair, save=True)
        direction = "LONG" if ai_signal.recommendation in {"STRONG_BUY", "BUY", "WATCH"} else "SHORT"

        position_size = 0.0
        if account_id:
            try:
                sizing = self.forex_portfolio_engine.position_size_from_risk(
                    account_id=account_id,
                    pair=normalized_pair,
                    entry_price=ai_signal.entry_price,
                    stop_price=ai_signal.stop_price,
                    risk_pct=risk_pct,
                )
                position_size = _safe_float(sizing.get("suggested_units"))
            except Exception as exc:
                logger.warning("Strategy sizing failed for %s: %s", normalized_pair, exc)

        confidence_adjustment = {
            "TREND_FOLLOWING": ai_signal.trend_score * 0.05,
            "MEAN_REVERSION": (100 - ai_signal.momentum_score) * 0.04,
            "BREAKOUT": ai_signal.volatility_score * 0.04,
            "CARRY": ai_signal.carry_score * 0.05,
            "MOMENTUM": ai_signal.momentum_score * 0.05,
            "AI_COMPOSITE": ai_signal.composite_score * 0.05,
        }.get(strategy_type, 0.0)

        confidence = min(100.0, max(0.0, ai_signal.confidence + confidence_adjustment - 2.5))

        signal = ForexStrategySignal(
            signal_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            strategy_name=f"{strategy_type.title().replace('_', ' ')} Strategy",
            strategy_type=strategy_type,
            pair=normalized_pair,
            direction=direction,
            recommendation=ai_signal.recommendation,
            confidence=round(confidence, 2),
            entry_price=ai_signal.entry_price,
            stop_price=ai_signal.stop_price,
            target_price=ai_signal.target_price,
            risk_reward=ai_signal.risk_reward,
            position_size_units=round(position_size, 2),
            composite_score=ai_signal.composite_score,
            rationale=f"{strategy_type} generated {ai_signal.recommendation} on {normalized_pair}. {ai_signal.rationale}",
            warnings=ai_signal.warnings,
            asof=_utc_now(),
            raw={"ai_signal": ai_signal.to_dict(), "risk_pct": risk_pct},
        )
        if save:
            self.save_strategy_signal(signal)
        return signal

    def run_strategy(
        self,
        *,
        pairs: Optional[List[str]] = None,
        strategy_type: str = "AI_COMPOSITE",
        account_id: Optional[str] = None,
        min_confidence: float = 60.0,
        save: bool = True,
    ) -> ForexStrategyRun:
        selected_pairs = pairs or DEFAULT_PAIRS
        signals: List[ForexStrategySignal] = []
        for pair in selected_pairs:
            try:
                signal = self.generate_strategy_signal(
                    pair=pair, strategy_type=strategy_type, account_id=account_id, save=save
                )
                if signal.confidence >= min_confidence:
                    signals.append(signal)
            except Exception as exc:
                logger.warning("Strategy signal failed for %s: %s", pair, exc)

        ranked = sorted(signals, key=lambda s: (s.confidence, s.composite_score, s.risk_reward), reverse=True)
        avg_confidence = sum(s.confidence for s in ranked) / len(ranked) if ranked else 0.0
        run = ForexStrategyRun(
            run_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            strategy_name=f"{strategy_type.title().replace('_', ' ')} Strategy",
            pair_count=len(selected_pairs),
            signal_count=len(ranked),
            top_pair=ranked[0].pair if ranked else None,
            avg_confidence=round(avg_confidence, 2),
            created_at=_utc_now(),
            signals=[s.to_dict() for s in ranked],
        )
        if save:
            self.save_strategy_run(run)
        return run

    def rank_strategies(
        self,
        *,
        pair: str = "EUR/USD",
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = []
        for strategy_type in sorted(STRATEGY_TYPES):
            signal = self.generate_strategy_signal(
                pair=pair, strategy_type=strategy_type, account_id=account_id, save=False
            )
            rows.append(signal.to_dict())
        return sorted(rows, key=lambda r: (r.get("confidence", 0), r.get("composite_score", 0)), reverse=True)

    def save_strategy_signal(self, signal: ForexStrategySignal) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        self.db.execute("""
            INSERT INTO forex_strategy_signals (
                signal_id, tenant_id, user_id, portfolio_id, strategy_name, strategy_type,
                pair, direction, recommendation, confidence, entry_price, stop_price,
                target_price, risk_reward, position_size_units, composite_score,
                rationale, warnings, raw_payload, asof
            )
            VALUES (
                :signal_id, :tenant_id, :user_id, :portfolio_id, :strategy_name, :strategy_type,
                :pair, :direction, :recommendation, :confidence, :entry_price, :stop_price,
                :target_price, :risk_reward, :position_size_units, :composite_score,
                :rationale, :warnings, :raw_payload, :asof
            )
            ON CONFLICT (signal_id) DO NOTHING
        """, {
            **signal.to_dict(),
            "raw_payload": _json(signal.raw),
            "asof": _naive(signal.asof),
        })
        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_strategy_run(self, run: ForexStrategyRun) -> None:
        if self.db is None:
            return
        self.ensure_tables()
        self.db.execute("""
            INSERT INTO forex_strategy_runs (
                run_id, tenant_id, user_id, portfolio_id, strategy_name,
                pair_count, signal_count, top_pair, avg_confidence, payload, created_at
            )
            VALUES (
                :run_id, :tenant_id, :user_id, :portfolio_id, :strategy_name,
                :pair_count, :signal_count, :top_pair, :avg_confidence, :payload, :created_at
            )
            ON CONFLICT (run_id) DO NOTHING
        """, {
            **run.to_dict(),
            "payload": _json(run.to_dict()),
            "created_at": _naive(run.created_at),
        })
        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_strategy_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        self.ensure_tables()
        rows = self.db.execute("""
            SELECT * FROM forex_strategy_runs
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
            LIMIT :limit
        """, {"tenant_id": self.tenant_id, "limit": int(limit)}).fetchall()
        return [
            {
                "run_id": getattr(row, "run_id", None),
                "strategy_name": getattr(row, "strategy_name", None),
                "pair_count": getattr(row, "pair_count", None),
                "signal_count": getattr(row, "signal_count", None),
                "top_pair": getattr(row, "top_pair", None),
                "avg_confidence": getattr(row, "avg_confidence", None),
                "created_at": str(getattr(row, "created_at", "")),
            }
            for row in rows
        ]


def get_forex_strategy_engine(**kwargs: Any) -> ForexStrategyEngine:
    return ForexStrategyEngine(**kwargs)
