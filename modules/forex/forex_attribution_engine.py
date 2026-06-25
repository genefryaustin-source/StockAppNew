# modules/forex/forex_attribution_engine.py

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )
    from modules.forex.forex_trading_engine import (
        ForexTradingEngine,
        ForexOrder,
        ForexTrade,
        get_forex_trading_engine,
    )
    from modules.forex.forex_portfolio_engine import (
        ForexPortfolioEngine,
        get_forex_portfolio_engine,
    )
except Exception:
    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )
    from forex_trading_engine import (
        ForexTradingEngine,
        ForexOrder,
        ForexTrade,
        get_forex_trading_engine,
    )
    from forex_portfolio_engine import (
        ForexPortfolioEngine,
        get_forex_portfolio_engine,
    )


logger = logging.getLogger(__name__)


@dataclass
class ForexAttributionRecord:
    attribution_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    recommendation_id: Optional[str]
    order_id: Optional[str]
    trade_id: Optional[str]
    position_id: Optional[str]
    account_id: Optional[str]
    pair: str
    recommendation: Optional[str]
    conviction_score: float
    confidence_score: float
    composite_score: float
    entry_price: float
    exit_price: Optional[float]
    units: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    return_pct: float
    outcome: str
    attribution_score: float
    accuracy_score: float
    source: str
    created_at: datetime
    updated_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


@dataclass
class ForexAttributionSummary:
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: Optional[str]
    total_records: int
    win_count: int
    loss_count: int
    open_count: int
    win_rate: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_pnl: float
    avg_return_pct: float
    avg_attribution_score: float
    avg_accuracy_score: float
    best_pair: Optional[str]
    worst_pair: Optional[str]
    created_at: datetime
    records: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
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


class ForexAttributionEngine:
    """
    Forex recommendation attribution engine.

    Tracks:
    - recommendation -> order
    - recommendation -> trade
    - recommendation -> position
    - recommendation -> PnL
    - recommendation accuracy and attribution quality

    Architecture:
    - Explicit state passing
    - Tenant-safe
    - Neon Postgres compatible
    - No global runtime state
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        recommendation_engine: Optional[ForexRecommendationEngine] = None,
        trading_engine: Optional[ForexTradingEngine] = None,
        portfolio_engine: Optional[ForexPortfolioEngine] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db

        self.recommendation_engine = recommendation_engine or get_forex_recommendation_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
        self.trading_engine = trading_engine or get_forex_trading_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )
        self.portfolio_engine = portfolio_engine or get_forex_portfolio_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_recommendation_attribution (
                attribution_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                recommendation_id VARCHAR(80),
                order_id VARCHAR(80),
                trade_id VARCHAR(80),
                position_id VARCHAR(80),
                account_id VARCHAR(80),
                pair VARCHAR(20),
                recommendation VARCHAR(40),
                conviction_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                composite_score DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                exit_price DOUBLE PRECISION,
                units DOUBLE PRECISION,
                realized_pnl DOUBLE PRECISION,
                unrealized_pnl DOUBLE PRECISION,
                total_pnl DOUBLE PRECISION,
                return_pct DOUBLE PRECISION,
                outcome VARCHAR(40),
                attribution_score DOUBLE PRECISION,
                accuracy_score DOUBLE PRECISION,
                source VARCHAR(80),
                raw_payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_recommendation_attribution_tenant_pair
            ON forex_recommendation_attribution (tenant_id, pair, updated_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_recommendation_attribution_rec
            ON forex_recommendation_attribution (tenant_id, recommendation_id)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_attribution_snapshots (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                total_records INTEGER,
                win_count INTEGER,
                loss_count INTEGER,
                open_count INTEGER,
                win_rate DOUBLE PRECISION,
                total_realized_pnl DOUBLE PRECISION,
                total_unrealized_pnl DOUBLE PRECISION,
                total_pnl DOUBLE PRECISION,
                avg_return_pct DOUBLE PRECISION,
                avg_attribution_score DOUBLE PRECISION,
                avg_accuracy_score DOUBLE PRECISION,
                best_pair VARCHAR(20),
                worst_pair VARCHAR(20),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def attribute_recommendation(
        self,
        *,
        recommendation_id: str,
        order_id: Optional[str] = None,
        trade_id: Optional[str] = None,
        position_id: Optional[str] = None,
        account_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexAttributionRecord:
        recommendation = self._load_recommendation(recommendation_id)

        if not recommendation:
            raise ValueError(f"Forex recommendation not found: {recommendation_id}")

        order = self.trading_engine.get_order(order_id) if order_id else None
        trade = self.trading_engine.get_trade(trade_id) if trade_id else None
        position = self.portfolio_engine.get_position(position_id=position_id) if position_id else None

        if position is None and trade and getattr(trade, "position_id", None):
            position = self.portfolio_engine.get_position(position_id=trade.position_id)

        pair = recommendation.get("pair") or (getattr(order, "pair", None) if order else None) or (getattr(trade, "pair", None) if trade else "")
        entry_price = _safe_float(
            recommendation.get("entry_price")
            or (getattr(trade, "entry_price", None) if trade else None)
            or (getattr(order, "avg_fill_price", None) if order else None)
        )

        exit_price = None
        if position:
            exit_price = _safe_float(getattr(position, "current_price", None))
        elif trade and getattr(trade, "closed_at", None):
            exit_price = _safe_float(getattr(trade, "entry_price", None))

        units = _safe_float(
            (getattr(position, "units", None) if position else None)
            or (getattr(trade, "units", None) if trade else None)
            or (getattr(order, "filled_units", None) if order else None)
            or recommendation.get("suggested_units")
        )

        realized_pnl = _safe_float(
            (getattr(position, "realized_pnl", None) if position else None)
            or (getattr(trade, "realized_pnl", None) if trade else None)
        )
        unrealized_pnl = _safe_float(
            (getattr(position, "unrealized_pnl", None) if position else None)
            or (getattr(trade, "unrealized_pnl", None) if trade else None)
        )
        total_pnl = realized_pnl + unrealized_pnl

        notional = abs(entry_price * units) if entry_price and units else _safe_float(recommendation.get("max_position_value"))
        return_pct = (total_pnl / notional) * 100.0 if notional else 0.0

        outcome = self._classify_outcome(
            total_pnl=total_pnl,
            trade=trade,
            position=position,
        )

        attribution_score = self._attribution_score(
            recommendation=recommendation,
            total_pnl=total_pnl,
            return_pct=return_pct,
            outcome=outcome,
        )

        accuracy_score = self._accuracy_score(
            recommendation=recommendation,
            total_pnl=total_pnl,
            outcome=outcome,
        )

        now = _utc_now()

        record = ForexAttributionRecord(
            attribution_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            recommendation_id=recommendation_id,
            order_id=order_id or (getattr(order, "order_id", None) if order else None),
            trade_id=trade_id or (getattr(trade, "trade_id", None) if trade else None),
            position_id=position_id or (getattr(position, "id", None) if position else None),
            account_id=account_id
            or (getattr(position, "account_id", None) if position else None)
            or (getattr(trade, "account_id", None) if trade else None)
            or (getattr(order, "account_id", None) if order else None),
            pair=pair,
            recommendation=recommendation.get("recommendation"),
            conviction_score=_safe_float(recommendation.get("conviction_score")),
            confidence_score=_safe_float(recommendation.get("confidence_score")),
            composite_score=_safe_float(recommendation.get("composite_score")),
            entry_price=entry_price,
            exit_price=exit_price,
            units=units,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            return_pct=_round(return_pct, 4),
            outcome=outcome,
            attribution_score=_round(attribution_score),
            accuracy_score=_round(accuracy_score),
            source="FOREX_ATTRIBUTION_ENGINE",
            created_at=now,
            updated_at=now,
            raw={
                "recommendation": recommendation,
                "order": order.to_dict() if order else None,
                "trade": trade.to_dict() if trade else None,
                "position": position.to_dict() if position else None,
            },
        )

        if save:
            self.save_attribution(record)

        return record

    def attribute_order(
        self,
        *,
        order_id: str,
        recommendation_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexAttributionRecord:
        order = self.trading_engine.get_order(order_id)
        if not order:
            raise ValueError(f"Forex order not found: {order_id}")

        rec_id = recommendation_id or self._find_recommendation_for_order(order)

        if not rec_id:
            raise ValueError(f"No Forex recommendation found for order: {order_id}")

        return self.attribute_recommendation(
            recommendation_id=rec_id,
            order_id=order_id,
            account_id=order.account_id,
            save=save,
        )

    def attribute_trade(
        self,
        *,
        trade_id: str,
        recommendation_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexAttributionRecord:
        trade = self.trading_engine.get_trade(trade_id)
        if not trade:
            raise ValueError(f"Forex trade not found: {trade_id}")

        rec_id = recommendation_id or self._find_recommendation_for_trade(trade)

        if not rec_id:
            raise ValueError(f"No Forex recommendation found for trade: {trade_id}")

        return self.attribute_recommendation(
            recommendation_id=rec_id,
            trade_id=trade_id,
            position_id=trade.position_id,
            account_id=trade.account_id,
            save=save,
        )

    def run_attribution_scan(
        self,
        *,
        account_id: Optional[str] = None,
        status: str = "ALL",
        limit: int = 250,
        save: bool = True,
    ) -> ForexAttributionSummary:
        recommendations = self.recommendation_engine.load_recommendations(
            status=status,
            limit=limit,
        )

        records: List[ForexAttributionRecord] = []

        for rec in recommendations:
            try:
                if account_id and rec.get("executed") is not True:
                    continue

                record = self.attribute_recommendation(
                    recommendation_id=rec["recommendation_id"],
                    order_id=rec.get("executed_order_id"),
                    account_id=account_id,
                    save=save,
                )
                records.append(record)

            except Exception as exc:
                logger.warning("Forex attribution failed for recommendation %s: %s", rec.get("recommendation_id"), exc)

        summary = self.build_summary(
            records=records,
            account_id=account_id,
            save=save,
        )

        return summary

    def build_summary(
        self,
        *,
        records: List[ForexAttributionRecord],
        account_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexAttributionSummary:
        win_records = [r for r in records if r.outcome == "WIN"]
        loss_records = [r for r in records if r.outcome == "LOSS"]
        open_records = [r for r in records if r.outcome == "OPEN"]

        total_realized = sum(r.realized_pnl for r in records)
        total_unrealized = sum(r.unrealized_pnl for r in records)
        total_pnl = sum(r.total_pnl for r in records)

        avg_return = sum(r.return_pct for r in records) / len(records) if records else 0.0
        avg_attr = sum(r.attribution_score for r in records) / len(records) if records else 0.0
        avg_accuracy = sum(r.accuracy_score for r in records) / len(records) if records else 0.0

        sorted_by_pnl = sorted(records, key=lambda r: r.total_pnl)
        best_pair = sorted_by_pnl[-1].pair if sorted_by_pnl else None
        worst_pair = sorted_by_pnl[0].pair if sorted_by_pnl else None

        summary = ForexAttributionSummary(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=account_id,
            total_records=len(records),
            win_count=len(win_records),
            loss_count=len(loss_records),
            open_count=len(open_records),
            win_rate=_round((len(win_records) / max(1, len(win_records) + len(loss_records))) * 100.0),
            total_realized_pnl=_round(total_realized),
            total_unrealized_pnl=_round(total_unrealized),
            total_pnl=_round(total_pnl),
            avg_return_pct=_round(avg_return, 4),
            avg_attribution_score=_round(avg_attr),
            avg_accuracy_score=_round(avg_accuracy),
            best_pair=best_pair,
            worst_pair=worst_pair,
            created_at=_utc_now(),
            records=[r.to_dict() for r in records],
        )

        if save:
            self.save_summary(summary)

        return summary

    def save_attribution(self, record: ForexAttributionRecord) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_recommendation_attribution (
                attribution_id,
                tenant_id,
                user_id,
                portfolio_id,
                recommendation_id,
                order_id,
                trade_id,
                position_id,
                account_id,
                pair,
                recommendation,
                conviction_score,
                confidence_score,
                composite_score,
                entry_price,
                exit_price,
                units,
                realized_pnl,
                unrealized_pnl,
                total_pnl,
                return_pct,
                outcome,
                attribution_score,
                accuracy_score,
                source,
                raw_payload,
                created_at,
                updated_at
            )
            VALUES (
                :attribution_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :recommendation_id,
                :order_id,
                :trade_id,
                :position_id,
                :account_id,
                :pair,
                :recommendation,
                :conviction_score,
                :confidence_score,
                :composite_score,
                :entry_price,
                :exit_price,
                :units,
                :realized_pnl,
                :unrealized_pnl,
                :total_pnl,
                :return_pct,
                :outcome,
                :attribution_score,
                :accuracy_score,
                :source,
                :raw_payload,
                :created_at,
                :updated_at
            )
            ON CONFLICT (attribution_id)
            DO UPDATE SET
                order_id = EXCLUDED.order_id,
                trade_id = EXCLUDED.trade_id,
                position_id = EXCLUDED.position_id,
                account_id = EXCLUDED.account_id,
                exit_price = EXCLUDED.exit_price,
                units = EXCLUDED.units,
                realized_pnl = EXCLUDED.realized_pnl,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                total_pnl = EXCLUDED.total_pnl,
                return_pct = EXCLUDED.return_pct,
                outcome = EXCLUDED.outcome,
                attribution_score = EXCLUDED.attribution_score,
                accuracy_score = EXCLUDED.accuracy_score,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = EXCLUDED.updated_at
            """,
            {
                **record.to_dict(),
                "raw_payload": _json(record.raw),
                "created_at": _naive(record.created_at),
                "updated_at": _naive(record.updated_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_summary(self, summary: ForexAttributionSummary) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_attribution_snapshots (
                tenant_id,
                user_id,
                portfolio_id,
                account_id,
                total_records,
                win_count,
                loss_count,
                open_count,
                win_rate,
                total_realized_pnl,
                total_unrealized_pnl,
                total_pnl,
                avg_return_pct,
                avg_attribution_score,
                avg_accuracy_score,
                best_pair,
                worst_pair,
                payload,
                created_at
            )
            VALUES (
                :tenant_id,
                :user_id,
                :portfolio_id,
                :account_id,
                :total_records,
                :win_count,
                :loss_count,
                :open_count,
                :win_rate,
                :total_realized_pnl,
                :total_unrealized_pnl,
                :total_pnl,
                :avg_return_pct,
                :avg_attribution_score,
                :avg_accuracy_score,
                :best_pair,
                :worst_pair,
                :payload,
                :created_at
            )
            """,
            {
                **summary.to_dict(),
                "payload": _json(summary.to_dict()),
                "created_at": _naive(summary.created_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def load_attribution_records(
        self,
        *,
        pair: Optional[str] = None,
        account_id: Optional[str] = None,
        outcome: str = "ALL",
        limit: int = 250,
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
            params["pair"] = pair.upper().replace("-", "/")

        if account_id:
            where += " AND account_id = :account_id"
            params["account_id"] = account_id

        if outcome and outcome.upper() != "ALL":
            where += " AND outcome = :outcome"
            params["outcome"] = outcome.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_recommendation_attribution
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [self._row_to_record_dict(row) for row in rows]

    def load_summary_history(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = self.db.execute(
            """
            SELECT *
            FROM forex_attribution_snapshots
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
                "account_id": _row_get(row, "account_id"),
                "total_records": _row_get(row, "total_records"),
                "win_count": _row_get(row, "win_count"),
                "loss_count": _row_get(row, "loss_count"),
                "open_count": _row_get(row, "open_count"),
                "win_rate": _row_get(row, "win_rate"),
                "total_realized_pnl": _row_get(row, "total_realized_pnl"),
                "total_unrealized_pnl": _row_get(row, "total_unrealized_pnl"),
                "total_pnl": _row_get(row, "total_pnl"),
                "avg_return_pct": _row_get(row, "avg_return_pct"),
                "avg_attribution_score": _row_get(row, "avg_attribution_score"),
                "avg_accuracy_score": _row_get(row, "avg_accuracy_score"),
                "best_pair": _row_get(row, "best_pair"),
                "worst_pair": _row_get(row, "worst_pair"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _load_recommendation(
        self,
        recommendation_id: str,
    ) -> Optional[Dict[str, Any]]:
        rows = self.recommendation_engine.load_recommendations(
            status="ALL",
            limit=1000,
        )

        for row in rows:
            if row.get("recommendation_id") == recommendation_id:
                return row

        if self.db is None:
            return None

        self.recommendation_engine.ensure_tables()

        db_row = self.db.execute(
            """
            SELECT *
            FROM forex_recommendations
            WHERE tenant_id = :tenant_id
              AND recommendation_id = :recommendation_id
            LIMIT 1
            """,
            {
                "tenant_id": self.tenant_id,
                "recommendation_id": recommendation_id,
            },
        ).fetchone()

        if not db_row:
            return None

        return self.recommendation_engine._row_to_recommendation_dict(db_row)

    def _find_recommendation_for_order(
        self,
        order: ForexOrder,
    ) -> Optional[str]:
        if not order:
            return None

        if getattr(order, "signal_id", None):
            rows = self.recommendation_engine.load_recommendations(
                pair=order.pair,
                status="ALL",
                limit=100,
            )
            for row in rows:
                if row.get("executed_order_id") == order.order_id:
                    return row.get("recommendation_id")

        rows = self.recommendation_engine.load_recommendations(
            pair=order.pair,
            status="ALL",
            limit=25,
        )

        for row in rows:
            if row.get("executed_order_id") == order.order_id:
                return row.get("recommendation_id")

        return rows[0].get("recommendation_id") if rows else None

    def _find_recommendation_for_trade(
        self,
        trade: ForexTrade,
    ) -> Optional[str]:
        if not trade:
            return None

        rows = self.recommendation_engine.load_recommendations(
            pair=trade.pair,
            status="ALL",
            limit=25,
        )

        for row in rows:
            if row.get("executed_order_id") == trade.order_id:
                return row.get("recommendation_id")

        return rows[0].get("recommendation_id") if rows else None

    def _classify_outcome(
        self,
        *,
        total_pnl: float,
        trade: Optional[ForexTrade],
        position: Any,
    ) -> str:
        if position is not None and getattr(position, "status", "OPEN") == "OPEN":
            if total_pnl > 0:
                return "OPEN_GAIN"
            if total_pnl < 0:
                return "OPEN_LOSS"
            return "OPEN"

        if trade is not None and getattr(trade, "status", "OPEN") == "OPEN":
            if total_pnl > 0:
                return "OPEN_GAIN"
            if total_pnl < 0:
                return "OPEN_LOSS"
            return "OPEN"

        if total_pnl > 0:
            return "WIN"

        if total_pnl < 0:
            return "LOSS"

        return "FLAT"

    def _attribution_score(
        self,
        *,
        recommendation: Dict[str, Any],
        total_pnl: float,
        return_pct: float,
        outcome: str,
    ) -> float:
        conviction = _safe_float(recommendation.get("conviction_score"))
        confidence = _safe_float(recommendation.get("confidence_score"))

        pnl_component = max(0.0, min(100.0, 50.0 + return_pct * 10.0))

        if outcome in {"WIN", "OPEN_GAIN"}:
            outcome_component = 85.0
        elif outcome in {"LOSS", "OPEN_LOSS"}:
            outcome_component = 25.0
        else:
            outcome_component = 55.0

        return (
            conviction * 0.30
            + confidence * 0.25
            + pnl_component * 0.25
            + outcome_component * 0.20
        )

    def _accuracy_score(
        self,
        *,
        recommendation: Dict[str, Any],
        total_pnl: float,
        outcome: str,
    ) -> float:
        rec = str(recommendation.get("recommendation") or "").upper()

        bullish = rec in {"STRONG_BUY", "BUY", "WATCH"}
        bearish = rec in {"SELL", "STRONG_SELL"}

        if total_pnl > 0 and bullish:
            return 100.0
        if total_pnl < 0 and bearish:
            return 100.0
        if total_pnl == 0:
            return 50.0
        if outcome in {"OPEN", "OPEN_GAIN", "OPEN_LOSS"}:
            return 65.0
        return 0.0

    def _row_to_record_dict(
        self,
        row: Any,
    ) -> Dict[str, Any]:
        return {
            "attribution_id": _row_get(row, "attribution_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "recommendation_id": _row_get(row, "recommendation_id"),
            "order_id": _row_get(row, "order_id"),
            "trade_id": _row_get(row, "trade_id"),
            "position_id": _row_get(row, "position_id"),
            "account_id": _row_get(row, "account_id"),
            "pair": _row_get(row, "pair"),
            "recommendation": _row_get(row, "recommendation"),
            "conviction_score": _row_get(row, "conviction_score"),
            "confidence_score": _row_get(row, "confidence_score"),
            "composite_score": _row_get(row, "composite_score"),
            "entry_price": _row_get(row, "entry_price"),
            "exit_price": _row_get(row, "exit_price"),
            "units": _row_get(row, "units"),
            "realized_pnl": _row_get(row, "realized_pnl"),
            "unrealized_pnl": _row_get(row, "unrealized_pnl"),
            "total_pnl": _row_get(row, "total_pnl"),
            "return_pct": _row_get(row, "return_pct"),
            "outcome": _row_get(row, "outcome"),
            "attribution_score": _row_get(row, "attribution_score"),
            "accuracy_score": _row_get(row, "accuracy_score"),
            "source": _row_get(row, "source"),
            "created_at": str(_row_get(row, "created_at", "")),
            "updated_at": str(_row_get(row, "updated_at", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_attribution_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    recommendation_engine: Optional[ForexRecommendationEngine] = None,
    trading_engine: Optional[ForexTradingEngine] = None,
    portfolio_engine: Optional[ForexPortfolioEngine] = None,
) -> ForexAttributionEngine:
    return ForexAttributionEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        recommendation_engine=recommendation_engine,
        trading_engine=trading_engine,
        portfolio_engine=portfolio_engine,
    )


def attribute_forex_recommendation(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    recommendation_id: str,
    order_id: Optional[str] = None,
    trade_id: Optional[str] = None,
    position_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    engine = get_forex_attribution_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.attribute_recommendation(
        recommendation_id=recommendation_id,
        order_id=order_id,
        trade_id=trade_id,
        position_id=position_id,
        account_id=account_id,
    ).to_dict()


def run_forex_attribution_scan(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    status: str = "ALL",
    limit: int = 250,
) -> Dict[str, Any]:
    engine = get_forex_attribution_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.run_attribution_scan(
        account_id=account_id,
        status=status,
        limit=limit,
    ).to_dict()