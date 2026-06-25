# modules/forex/forex_execution_quality_engine.py

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
    )
    from modules.forex.forex_trading_engine import (
        ForexTradingEngine,
        ForexOrder,
        ForexExecution,
        get_forex_trading_engine,
    )
except Exception:
    from forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
    )
    from forex_trading_engine import (
        ForexTradingEngine,
        ForexOrder,
        ForexExecution,
        get_forex_trading_engine,
    )


logger = logging.getLogger(__name__)


@dataclass
class ForexExecutionQualityRecord:
    quality_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: Optional[str]
    order_id: Optional[str]
    trade_id: Optional[str]
    execution_id: Optional[str]
    pair: str
    side: str
    order_type: str
    requested_units: float
    filled_units: float
    fill_ratio: float
    expected_price: float
    fill_price: float
    benchmark_price: float
    slippage: float
    slippage_bps: float
    spread: float
    spread_bps: float
    spread_capture: float
    execution_latency_ms: int
    fill_quality_score: float
    price_improvement_score: float
    liquidity_score: float
    execution_score: float
    broker: str
    status: str
    notes: str
    measured_at: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["measured_at"] = self.measured_at.isoformat()
        return data


@dataclass
class ForexExecutionQualitySummary:
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    account_id: Optional[str]
    total_records: int
    avg_fill_ratio: float
    avg_slippage_bps: float
    avg_spread_bps: float
    avg_execution_latency_ms: float
    avg_fill_quality_score: float
    avg_price_improvement_score: float
    avg_liquidity_score: float
    avg_execution_score: float
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


class ForexExecutionQualityEngine:
    """
    Institutional Forex execution quality analytics.

    Measures:
    - Slippage
    - Slippage bps
    - Spread capture
    - Fill ratio
    - Execution latency
    - Fill quality score
    - Price improvement score
    - Liquidity score
    - Composite execution score

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
        forex_service: Optional[ForexService] = None,
        trading_engine: Optional[ForexTradingEngine] = None,
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
        self.trading_engine = trading_engine or get_forex_trading_engine(
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            db=db,
            forex_service=self.forex_service,
        )

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_execution_quality (
                quality_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                order_id VARCHAR(80),
                trade_id VARCHAR(80),
                execution_id VARCHAR(80),
                pair VARCHAR(20),
                side VARCHAR(10),
                order_type VARCHAR(40),
                requested_units DOUBLE PRECISION,
                filled_units DOUBLE PRECISION,
                fill_ratio DOUBLE PRECISION,
                expected_price DOUBLE PRECISION,
                fill_price DOUBLE PRECISION,
                benchmark_price DOUBLE PRECISION,
                slippage DOUBLE PRECISION,
                slippage_bps DOUBLE PRECISION,
                spread DOUBLE PRECISION,
                spread_bps DOUBLE PRECISION,
                spread_capture DOUBLE PRECISION,
                execution_latency_ms INTEGER,
                fill_quality_score DOUBLE PRECISION,
                price_improvement_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                execution_score DOUBLE PRECISION,
                broker VARCHAR(80),
                status VARCHAR(40),
                notes TEXT,
                raw_payload JSONB,
                measured_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_execution_quality_tenant_pair
            ON forex_execution_quality (tenant_id, pair, measured_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_execution_quality_order
            ON forex_execution_quality (tenant_id, order_id)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_execution_quality_snapshots (
                id SERIAL PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                account_id VARCHAR(80),
                total_records INTEGER,
                avg_fill_ratio DOUBLE PRECISION,
                avg_slippage_bps DOUBLE PRECISION,
                avg_spread_bps DOUBLE PRECISION,
                avg_execution_latency_ms DOUBLE PRECISION,
                avg_fill_quality_score DOUBLE PRECISION,
                avg_price_improvement_score DOUBLE PRECISION,
                avg_liquidity_score DOUBLE PRECISION,
                avg_execution_score DOUBLE PRECISION,
                best_pair VARCHAR(20),
                worst_pair VARCHAR(20),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def analyze_order(
        self,
        *,
        order_id: str,
        save: bool = True,
    ) -> ForexExecutionQualityRecord:
        order = self.trading_engine.get_order(order_id)

        if not order:
            raise ValueError(f"Forex order not found: {order_id}")

        executions = self._load_executions(
            order_id=order_id,
            limit=1,
        )
        execution = executions[0] if executions else None

        trade = None
        trade_id = None

        if execution and execution.get("trade_id"):
            trade_id = execution.get("trade_id")
            trade = self.trading_engine.get_trade(trade_id)

        record = self._build_quality_record(
            order=order,
            execution_row=execution,
            trade_id=trade_id,
            trade=trade,
        )

        if save:
            self.save_quality_record(record)

        return record

    def analyze_orders(
        self,
        *,
        account_id: Optional[str] = None,
        status: str = "ALL",
        limit: int = 250,
        save: bool = True,
    ) -> List[ForexExecutionQualityRecord]:
        orders = self.trading_engine.list_orders(
            account_id=account_id,
            status=status,
            limit=limit,
        )

        records: List[ForexExecutionQualityRecord] = []

        for order in orders:
            try:
                record = self.analyze_order(
                    order_id=order.order_id,
                    save=save,
                )
                records.append(record)
            except Exception as exc:
                logger.warning("Failed to analyze Forex execution quality for %s: %s", order.order_id, exc)

        return records

    def run_quality_scan(
        self,
        *,
        account_id: Optional[str] = None,
        status: str = "ALL",
        limit: int = 250,
        save: bool = True,
    ) -> ForexExecutionQualitySummary:
        records = self.analyze_orders(
            account_id=account_id,
            status=status,
            limit=limit,
            save=save,
        )

        summary = self.build_summary(
            records=records,
            account_id=account_id,
            save=save,
        )

        return summary

    def build_summary(
        self,
        *,
        records: List[ForexExecutionQualityRecord],
        account_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexExecutionQualitySummary:
        total = len(records)

        def avg(field: str) -> float:
            if not records:
                return 0.0
            return sum(_safe_float(getattr(r, field)) for r in records) / len(records)

        pair_scores: Dict[str, List[float]] = {}
        for record in records:
            pair_scores.setdefault(record.pair, []).append(record.execution_score)

        pair_avg = {
            pair: sum(scores) / len(scores)
            for pair, scores in pair_scores.items()
            if scores
        }

        best_pair = None
        worst_pair = None

        if pair_avg:
            best_pair = max(pair_avg.items(), key=lambda item: item[1])[0]
            worst_pair = min(pair_avg.items(), key=lambda item: item[1])[0]

        summary = ForexExecutionQualitySummary(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=account_id,
            total_records=total,
            avg_fill_ratio=_round(avg("fill_ratio"), 4),
            avg_slippage_bps=_round(avg("slippage_bps"), 4),
            avg_spread_bps=_round(avg("spread_bps"), 4),
            avg_execution_latency_ms=_round(avg("execution_latency_ms"), 2),
            avg_fill_quality_score=_round(avg("fill_quality_score")),
            avg_price_improvement_score=_round(avg("price_improvement_score")),
            avg_liquidity_score=_round(avg("liquidity_score")),
            avg_execution_score=_round(avg("execution_score")),
            best_pair=best_pair,
            worst_pair=worst_pair,
            created_at=_utc_now(),
            records=[r.to_dict() for r in records],
        )

        if save:
            self.save_summary(summary)

        return summary

    def save_quality_record(
        self,
        record: ForexExecutionQualityRecord,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_execution_quality (
                quality_id,
                tenant_id,
                user_id,
                portfolio_id,
                account_id,
                order_id,
                trade_id,
                execution_id,
                pair,
                side,
                order_type,
                requested_units,
                filled_units,
                fill_ratio,
                expected_price,
                fill_price,
                benchmark_price,
                slippage,
                slippage_bps,
                spread,
                spread_bps,
                spread_capture,
                execution_latency_ms,
                fill_quality_score,
                price_improvement_score,
                liquidity_score,
                execution_score,
                broker,
                status,
                notes,
                raw_payload,
                measured_at
            )
            VALUES (
                :quality_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :account_id,
                :order_id,
                :trade_id,
                :execution_id,
                :pair,
                :side,
                :order_type,
                :requested_units,
                :filled_units,
                :fill_ratio,
                :expected_price,
                :fill_price,
                :benchmark_price,
                :slippage,
                :slippage_bps,
                :spread,
                :spread_bps,
                :spread_capture,
                :execution_latency_ms,
                :fill_quality_score,
                :price_improvement_score,
                :liquidity_score,
                :execution_score,
                :broker,
                :status,
                :notes,
                :raw_payload,
                :measured_at
            )
            ON CONFLICT (quality_id)
            DO UPDATE SET
                trade_id = EXCLUDED.trade_id,
                execution_id = EXCLUDED.execution_id,
                filled_units = EXCLUDED.filled_units,
                fill_ratio = EXCLUDED.fill_ratio,
                expected_price = EXCLUDED.expected_price,
                fill_price = EXCLUDED.fill_price,
                benchmark_price = EXCLUDED.benchmark_price,
                slippage = EXCLUDED.slippage,
                slippage_bps = EXCLUDED.slippage_bps,
                spread = EXCLUDED.spread,
                spread_bps = EXCLUDED.spread_bps,
                spread_capture = EXCLUDED.spread_capture,
                execution_latency_ms = EXCLUDED.execution_latency_ms,
                fill_quality_score = EXCLUDED.fill_quality_score,
                price_improvement_score = EXCLUDED.price_improvement_score,
                liquidity_score = EXCLUDED.liquidity_score,
                execution_score = EXCLUDED.execution_score,
                status = EXCLUDED.status,
                notes = EXCLUDED.notes,
                raw_payload = EXCLUDED.raw_payload,
                measured_at = EXCLUDED.measured_at
            """,
            {
                **record.to_dict(),
                "raw_payload": _json(record.raw),
                "measured_at": _naive(record.measured_at),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_summary(
        self,
        summary: ForexExecutionQualitySummary,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_execution_quality_snapshots (
                tenant_id,
                user_id,
                portfolio_id,
                account_id,
                total_records,
                avg_fill_ratio,
                avg_slippage_bps,
                avg_spread_bps,
                avg_execution_latency_ms,
                avg_fill_quality_score,
                avg_price_improvement_score,
                avg_liquidity_score,
                avg_execution_score,
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
                :avg_fill_ratio,
                :avg_slippage_bps,
                :avg_spread_bps,
                :avg_execution_latency_ms,
                :avg_fill_quality_score,
                :avg_price_improvement_score,
                :avg_liquidity_score,
                :avg_execution_score,
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

    def load_quality_records(
        self,
        *,
        pair: Optional[str] = None,
        account_id: Optional[str] = None,
        status: str = "ALL",
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
            params["pair"] = normalize_pair(pair)

        if account_id:
            where += " AND account_id = :account_id"
            params["account_id"] = account_id

        if status and status.upper() != "ALL":
            where += " AND status = :status"
            params["status"] = status.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_execution_quality
            WHERE {where}
            ORDER BY measured_at DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [self._row_to_quality_dict(row) for row in rows]

    def load_summary_history(
        self,
        *,
        account_id: Optional[str] = None,
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

        if account_id:
            where += " AND account_id = :account_id"
            params["account_id"] = account_id

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_execution_quality_snapshots
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [
            {
                "account_id": _row_get(row, "account_id"),
                "total_records": _row_get(row, "total_records"),
                "avg_fill_ratio": _row_get(row, "avg_fill_ratio"),
                "avg_slippage_bps": _row_get(row, "avg_slippage_bps"),
                "avg_spread_bps": _row_get(row, "avg_spread_bps"),
                "avg_execution_latency_ms": _row_get(row, "avg_execution_latency_ms"),
                "avg_fill_quality_score": _row_get(row, "avg_fill_quality_score"),
                "avg_price_improvement_score": _row_get(row, "avg_price_improvement_score"),
                "avg_liquidity_score": _row_get(row, "avg_liquidity_score"),
                "avg_execution_score": _row_get(row, "avg_execution_score"),
                "best_pair": _row_get(row, "best_pair"),
                "worst_pair": _row_get(row, "worst_pair"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _build_quality_record(
        self,
        *,
        order: ForexOrder,
        execution_row: Optional[Dict[str, Any]],
        trade_id: Optional[str],
        trade: Any,
    ) -> ForexExecutionQualityRecord:
        quote = self.forex_service.get_quote(order.pair)

        expected_price = _safe_float(
            order.limit_price
            or order.stop_price
            or order.avg_fill_price
            or quote.price
        )

        fill_price = _safe_float(
            (execution_row or {}).get("price")
            or order.avg_fill_price
            or quote.price
        )

        requested_units = _safe_float(order.units)
        filled_units = _safe_float(
            (execution_row or {}).get("units")
            or order.filled_units
        )

        fill_ratio = filled_units / requested_units if requested_units > 0 else 0.0

        benchmark_price = _safe_float(quote.price)
        slippage = fill_price - expected_price

        if order.side == "SELL":
            slippage = expected_price - fill_price

        slippage_bps = (slippage / expected_price) * 10000.0 if expected_price else 0.0

        spread = _safe_float(quote.spread)

        if spread <= 0 and quote.ask and quote.bid:
            spread = abs(_safe_float(quote.ask) - _safe_float(quote.bid))

        spread_bps = (spread / benchmark_price) * 10000.0 if benchmark_price else 0.0

        spread_capture = self._spread_capture(
            side=order.side,
            expected_price=expected_price,
            fill_price=fill_price,
            bid=_safe_float(quote.bid),
            ask=_safe_float(quote.ask),
            spread=spread,
        )

        latency_ms = self._execution_latency_ms(order, execution_row)

        fill_quality_score = self._fill_quality_score(
            fill_ratio=fill_ratio,
            status=order.status,
        )

        price_improvement_score = self._price_improvement_score(
            slippage_bps=slippage_bps,
        )

        liquidity_score = self._liquidity_score(
            spread_bps=spread_bps,
            fill_ratio=fill_ratio,
        )

        execution_score = (
            fill_quality_score * 0.35
            + price_improvement_score * 0.30
            + liquidity_score * 0.20
            + self._latency_score(latency_ms) * 0.15
        )

        notes = self._quality_notes(
            fill_ratio=fill_ratio,
            slippage_bps=slippage_bps,
            spread_bps=spread_bps,
            latency_ms=latency_ms,
            status=order.status,
        )

        return ForexExecutionQualityRecord(
            quality_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            account_id=order.account_id,
            order_id=order.order_id,
            trade_id=trade_id or getattr(trade, "trade_id", None),
            execution_id=(execution_row or {}).get("execution_id"),
            pair=order.pair,
            side=order.side,
            order_type=order.order_type,
            requested_units=_round(requested_units, 4),
            filled_units=_round(filled_units, 4),
            fill_ratio=_round(fill_ratio, 4),
            expected_price=_round(expected_price, 6),
            fill_price=_round(fill_price, 6),
            benchmark_price=_round(benchmark_price, 6),
            slippage=_round(slippage, 8),
            slippage_bps=_round(slippage_bps, 4),
            spread=_round(spread, 8),
            spread_bps=_round(spread_bps, 4),
            spread_capture=_round(spread_capture, 4),
            execution_latency_ms=int(latency_ms),
            fill_quality_score=_round(fill_quality_score),
            price_improvement_score=_round(price_improvement_score),
            liquidity_score=_round(liquidity_score),
            execution_score=_round(execution_score),
            broker=order.broker,
            status=order.status,
            notes=notes,
            measured_at=_utc_now(),
            raw={
                "order": order.to_dict(),
                "execution": execution_row,
                "trade": trade.to_dict() if trade else None,
                "quote": quote.to_dict(),
            },
        )

    def _load_executions(
        self,
        *,
        order_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        try:
            self.trading_engine.ensure_tables()

            rows = self.db.execute(
                """
                SELECT *
                FROM forex_trade_executions
                WHERE order_id = :order_id
                ORDER BY executed_at DESC
                LIMIT :limit
                """,
                {
                    "order_id": order_id,
                    "limit": int(limit),
                },
            ).fetchall()

            return [
                {
                    "execution_id": _row_get(row, "execution_id"),
                    "order_id": _row_get(row, "order_id"),
                    "trade_id": _row_get(row, "trade_id"),
                    "pair": _row_get(row, "pair"),
                    "side": _row_get(row, "side"),
                    "units": _row_get(row, "units"),
                    "price": _row_get(row, "price"),
                    "broker": _row_get(row, "broker"),
                    "slippage": _row_get(row, "slippage"),
                    "executed_at": _row_get(row, "executed_at"),
                    "raw": _row_get(row, "raw_payload"),
                }
                for row in rows
            ]

        except Exception as exc:
            logger.warning("Failed to load Forex executions for %s: %s", order_id, exc)
            return []

    def _execution_latency_ms(
        self,
        order: ForexOrder,
        execution_row: Optional[Dict[str, Any]],
    ) -> int:
        submitted = order.submitted_at or order.created_at
        executed = (execution_row or {}).get("executed_at") or order.filled_at

        if submitted is None or executed is None:
            return 0

        try:
            if submitted.tzinfo is None:
                submitted = submitted.replace(tzinfo=timezone.utc)
            if executed.tzinfo is None:
                executed = executed.replace(tzinfo=timezone.utc)

            return max(0, int((executed - submitted).total_seconds() * 1000))
        except Exception:
            return 0

    def _spread_capture(
        self,
        *,
        side: str,
        expected_price: float,
        fill_price: float,
        bid: float,
        ask: float,
        spread: float,
    ) -> float:
        if spread <= 0:
            return 0.0

        if bid <= 0 or ask <= 0:
            return 0.0

        midpoint = (bid + ask) / 2.0

        if side == "BUY":
            capture = (ask - fill_price) / spread
        else:
            capture = (fill_price - bid) / spread

        return max(-1.0, min(1.0, capture))

    def _fill_quality_score(
        self,
        *,
        fill_ratio: float,
        status: str,
    ) -> float:
        base = max(0.0, min(100.0, fill_ratio * 100.0))

        if status == "FILLED":
            base += 5.0
        elif status == "PARTIALLY_FILLED":
            base -= 10.0
        elif status in {"REJECTED", "CANCELLED", "EXPIRED"}:
            base -= 35.0

        return max(0.0, min(100.0, base))

    def _price_improvement_score(
        self,
        *,
        slippage_bps: float,
    ) -> float:
        if slippage_bps <= 0:
            return min(100.0, 85.0 + abs(slippage_bps))

        return max(0.0, 85.0 - slippage_bps * 4.0)

    def _liquidity_score(
        self,
        *,
        spread_bps: float,
        fill_ratio: float,
    ) -> float:
        spread_score = max(0.0, 100.0 - spread_bps * 8.0)
        fill_score = max(0.0, min(100.0, fill_ratio * 100.0))

        return spread_score * 0.65 + fill_score * 0.35

    def _latency_score(
        self,
        latency_ms: int,
    ) -> float:
        if latency_ms <= 0:
            return 75.0

        if latency_ms <= 250:
            return 100.0

        if latency_ms <= 1000:
            return 85.0

        if latency_ms <= 3000:
            return 65.0

        if latency_ms <= 10000:
            return 45.0

        return 25.0

    def _quality_notes(
        self,
        *,
        fill_ratio: float,
        slippage_bps: float,
        spread_bps: float,
        latency_ms: int,
        status: str,
    ) -> str:
        notes: List[str] = []

        if status != "FILLED":
            notes.append(f"Order status is {status}.")

        if fill_ratio < 1.0:
            notes.append("Order was not fully filled.")

        if slippage_bps > 2.5:
            notes.append("Elevated slippage detected.")

        if spread_bps > 5.0:
            notes.append("Wide spread detected.")

        if latency_ms > 3000:
            notes.append("Execution latency is elevated.")

        if not notes:
            notes.append("Execution quality is within expected range.")

        return " ".join(notes)

    def _row_to_quality_dict(
        self,
        row: Any,
    ) -> Dict[str, Any]:
        return {
            "quality_id": _row_get(row, "quality_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "account_id": _row_get(row, "account_id"),
            "order_id": _row_get(row, "order_id"),
            "trade_id": _row_get(row, "trade_id"),
            "execution_id": _row_get(row, "execution_id"),
            "pair": _row_get(row, "pair"),
            "side": _row_get(row, "side"),
            "order_type": _row_get(row, "order_type"),
            "requested_units": _row_get(row, "requested_units"),
            "filled_units": _row_get(row, "filled_units"),
            "fill_ratio": _row_get(row, "fill_ratio"),
            "expected_price": _row_get(row, "expected_price"),
            "fill_price": _row_get(row, "fill_price"),
            "benchmark_price": _row_get(row, "benchmark_price"),
            "slippage": _row_get(row, "slippage"),
            "slippage_bps": _row_get(row, "slippage_bps"),
            "spread": _row_get(row, "spread"),
            "spread_bps": _row_get(row, "spread_bps"),
            "spread_capture": _row_get(row, "spread_capture"),
            "execution_latency_ms": _row_get(row, "execution_latency_ms"),
            "fill_quality_score": _row_get(row, "fill_quality_score"),
            "price_improvement_score": _row_get(row, "price_improvement_score"),
            "liquidity_score": _row_get(row, "liquidity_score"),
            "execution_score": _row_get(row, "execution_score"),
            "broker": _row_get(row, "broker"),
            "status": _row_get(row, "status"),
            "notes": _row_get(row, "notes"),
            "measured_at": str(_row_get(row, "measured_at", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_execution_quality_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    trading_engine: Optional[ForexTradingEngine] = None,
) -> ForexExecutionQualityEngine:
    return ForexExecutionQualityEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
        trading_engine=trading_engine,
    )


def analyze_forex_execution_quality(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    order_id: str,
) -> Dict[str, Any]:
    engine = get_forex_execution_quality_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.analyze_order(order_id=order_id).to_dict()


def run_forex_execution_quality_scan(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    status: str = "ALL",
    limit: int = 250,
) -> Dict[str, Any]:
    engine = get_forex_execution_quality_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.run_quality_scan(
        account_id=account_id,
        status=status,
        limit=limit,
    ).to_dict()