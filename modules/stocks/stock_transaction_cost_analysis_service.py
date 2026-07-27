"""
modules/stocks/stock_transaction_cost_analysis_service.py

Stock Transaction Cost Analysis Service

Decomposes and aggregates the actual dollar cost of trading -- slippage
plus commission -- from the same persisted execution-quality records
StockExecutionQualityService and StockBrokerAnalyticsService already use.

This deliberately overlaps those two services in data source but not in
purpose or math:

  - StockExecutionQualityService grades a single order.
  - StockBrokerAnalyticsService compares brokers to each other.
  - This service answers "what is trading actually costing this
    portfolio in dollars, and where is that cost concentrated" --
    by symbol, by side, by trade size, and by time.

One real methodological difference from the other two: this service
uses notional-weighted ("dollar-weighted") aggregation, not a simple
average of per-order bps. A $2 slippage on a $200 trade and a $2,000
slippage on a $200,000 trade are both "1 bps" if you average trade by
trade, but they are not remotely the same in dollar impact on the
portfolio. TCA conventionally weights by notional for exactly this
reason; StockExecutionQualityService and StockBrokerAnalyticsService
intentionally do not, because they're answering "how did a typical
trade go," not "how much capital-weighted cost did trading incur."

benchmark_vs_close() is a separate, clearly-scoped, best-effort feature:
it compares each fill against that trading day's closing price, fetched
via modules.market_data.service.get_price_history. This is a real but
simple TCA technique (a close-price benchmark), not VWAP, not arrival
price, and not a full implementation-shortfall decomposition -- those
need intraday tick/bar data and a tracked "decision time" separate from
order-submission time, neither of which this platform currently has.
Network-dependent and best-effort: any symbol/date combination without
available history is skipped, not estimated.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from modules.stocks.stock_execution_quality_service import (
    get_stock_execution_quality_service,
)

logger = logging.getLogger(__name__)


SIZE_BUCKETS = (
    ("under_1k", 0, 1_000),
    ("1k_to_10k", 1_000, 10_000),
    ("10k_to_100k", 10_000, 100_000),
    ("over_100k", 100_000, float("inf")),
)


@dataclass(slots=True)
class TransactionCostSummary:
    portfolio_id: Optional[str]
    symbol: Optional[str]

    order_count: int
    total_notional: float

    total_slippage_cost: float
    total_commission_cost: float
    total_cost: float

    blended_slippage_bps: float
    blended_commission_bps: float
    blended_total_cost_bps: float

    cost_by_symbol: Dict[str, float] = field(default_factory=dict)
    cost_by_side: Dict[str, float] = field(default_factory=dict)
    cost_by_size_bucket: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class StockTransactionCostAnalysisService:

    def __init__(self, db):
        self.db = db
        self.quality_service = get_stock_execution_quality_service(db)
        self._ensure_tables()

    # ======================================================
    # Bootstrap
    # ======================================================

    def _ensure_tables(self) -> None:
        if self.db is None:
            return

        try:
            self.db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS stock_transaction_cost_analysis (

                        id BIGSERIAL PRIMARY KEY,

                        portfolio_id VARCHAR(36),
                        symbol VARCHAR(20),

                        order_count INTEGER,
                        total_notional DOUBLE PRECISION,

                        total_slippage_cost DOUBLE PRECISION,
                        total_commission_cost DOUBLE PRECISION,
                        total_cost DOUBLE PRECISION,

                        blended_slippage_bps DOUBLE PRECISION,
                        blended_commission_bps DOUBLE PRECISION,
                        blended_total_cost_bps DOUBLE PRECISION,

                        cost_by_symbol TEXT,
                        cost_by_side TEXT,
                        cost_by_size_bucket TEXT,

                        generated_at TIMESTAMP
                    )
                    """
                )
            )
            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to initialize stock_transaction_cost_analysis table.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Analysis
    # ======================================================

    def analyze_costs(
        self,
        *,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> TransactionCostSummary:
        """
        Pure computation over currently-persisted execution-quality
        records. Does not write anything.
        """

        records = self.quality_service.get_quality_records(
            portfolio_id=portfolio_id,
            symbol=symbol,
            limit=100000,
        )

        order_count = len(records)

        if order_count == 0:
            return TransactionCostSummary(
                portfolio_id=portfolio_id,
                symbol=symbol,
                order_count=0,
                total_notional=0.0,
                total_slippage_cost=0.0,
                total_commission_cost=0.0,
                total_cost=0.0,
                blended_slippage_bps=0.0,
                blended_commission_bps=0.0,
                blended_total_cost_bps=0.0,
            )

        total_notional = 0.0
        total_slippage_cost = 0.0
        total_commission_cost = 0.0

        cost_by_symbol: Dict[str, float] = defaultdict(float)
        cost_by_side: Dict[str, float] = defaultdict(float)
        bucket_stats: Dict[str, Dict[str, Any]] = {
            name: {"order_count": 0, "total_cost": 0.0, "total_notional": 0.0}
            for name, _, _ in SIZE_BUCKETS
        }

        for r in records:
            notional = float(r["filled_qty"] or 0.0) * float(r["avg_fill_price"] or 0.0)
            slippage_cost = abs(float(r["slippage_amount"] or 0.0))
            commission_cost = abs(float(r["commission_amount"] or 0.0))
            row_cost = slippage_cost + commission_cost

            total_notional += notional
            total_slippage_cost += slippage_cost
            total_commission_cost += commission_cost

            cost_by_symbol[r["symbol"]] += row_cost
            cost_by_side[r["side"]] += row_cost

            bucket_name = self._size_bucket(notional)
            bucket_stats[bucket_name]["order_count"] += 1
            bucket_stats[bucket_name]["total_cost"] += row_cost
            bucket_stats[bucket_name]["total_notional"] += notional

        total_cost = total_slippage_cost + total_commission_cost

        blended_slippage_bps = (
            (total_slippage_cost / total_notional) * 10000.0 if total_notional > 0 else 0.0
        )
        blended_commission_bps = (
            (total_commission_cost / total_notional) * 10000.0 if total_notional > 0 else 0.0
        )
        blended_total_cost_bps = blended_slippage_bps + blended_commission_bps

        cost_by_size_bucket = {}
        for name, stats in bucket_stats.items():
            avg_bps = (
                (stats["total_cost"] / stats["total_notional"]) * 10000.0
                if stats["total_notional"] > 0
                else 0.0
            )
            cost_by_size_bucket[name] = {
                "order_count": stats["order_count"],
                "total_cost": round(stats["total_cost"], 2),
                "average_cost_bps": round(avg_bps, 2),
            }

        return TransactionCostSummary(
            portfolio_id=portfolio_id,
            symbol=symbol,
            order_count=order_count,
            total_notional=round(total_notional, 2),
            total_slippage_cost=round(total_slippage_cost, 2),
            total_commission_cost=round(total_commission_cost, 2),
            total_cost=round(total_cost, 2),
            blended_slippage_bps=round(blended_slippage_bps, 2),
            blended_commission_bps=round(blended_commission_bps, 2),
            blended_total_cost_bps=round(blended_total_cost_bps, 2),
            cost_by_symbol={k: round(v, 2) for k, v in cost_by_symbol.items()},
            cost_by_side={k: round(v, 2) for k, v in cost_by_side.items()},
            cost_by_size_bucket=cost_by_size_bucket,
        )

    @staticmethod
    def _size_bucket(notional: float) -> str:
        for name, low, high in SIZE_BUCKETS:
            if low <= notional < high:
                return name
        return SIZE_BUCKETS[-1][0]

    def cost_trend(
        self,
        *,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit_periods: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Daily-bucketed blended cost trend, most recent day last (chart-
        ready order). Each bucket is computed with the same notional-
        weighted math as analyze_costs(), just scoped to that day.
        """

        records = self.quality_service.get_quality_records(
            portfolio_id=portfolio_id,
            symbol=symbol,
            limit=100000,
        )

        by_day: Dict[str, list] = defaultdict(list)
        for r in records:
            generated_at = r.get("generated_at")
            day_key = str(generated_at)[:10] if generated_at else "unknown"
            by_day[day_key].append(r)

        periods = []
        for day_key in sorted(by_day.keys())[-limit_periods:]:
            day_records = by_day[day_key]

            notional = sum(
                float(r["filled_qty"] or 0.0) * float(r["avg_fill_price"] or 0.0)
                for r in day_records
            )
            cost = sum(
                abs(float(r["slippage_amount"] or 0.0)) + abs(float(r["commission_amount"] or 0.0))
                for r in day_records
            )
            blended_bps = (cost / notional * 10000.0) if notional > 0 else 0.0

            periods.append({
                "period": day_key,
                "order_count": len(day_records),
                "total_notional": round(notional, 2),
                "total_cost": round(cost, 2),
                "blended_cost_bps": round(blended_bps, 2),
            })

        return periods

    # ======================================================
    # Benchmark (best-effort, network-dependent)
    # ======================================================

    def benchmark_vs_close(
        self,
        *,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Compares each of the most recent fills against that trading
        day's closing price. A simple, real benchmark -- not VWAP, not
        arrival price. Best-effort: any fill whose day's history isn't
        available is skipped, never estimated or defaulted to zero.
        """

        records = self.quality_service.get_quality_records(
            portfolio_id=portfolio_id,
            symbol=symbol,
            limit=limit,
        )

        close_cache: Dict[tuple, Optional[float]] = {}
        results: List[Dict[str, Any]] = []

        for r in records:
            sym = r.get("symbol")
            generated_at = r.get("generated_at")
            day_key = str(generated_at)[:10] if generated_at else None

            if not sym or not day_key:
                continue

            cache_key = (sym, day_key)
            if cache_key not in close_cache:
                close_cache[cache_key] = self._closing_price(sym, day_key)

            close_price = close_cache[cache_key]
            if close_price is None or close_price <= 0:
                continue

            fill_price = float(r.get("avg_fill_price") or 0.0)
            if fill_price <= 0:
                continue

            side = str(r.get("side") or "").lower()
            # Favorable = paid less than close on a buy, received more
            # than close on a sell.
            if side == "sell":
                vs_close_bps = ((fill_price - close_price) / close_price) * 10000.0
            else:
                vs_close_bps = ((close_price - fill_price) / close_price) * 10000.0

            results.append({
                "order_id": r.get("order_id"),
                "symbol": sym,
                "side": side,
                "date": day_key,
                "fill_price": fill_price,
                "close_price": close_price,
                "vs_close_bps": round(vs_close_bps, 2),
                "favorable": vs_close_bps > 0,
            })

        return results

    @staticmethod
    def _closing_price(symbol: str, day_key: str) -> Optional[float]:
        try:
            from modules.market_data.service import get_price_history

            df = get_price_history(None, symbol, period="5d", interval="1d")
            if df is None or df.empty:
                return None

            df = df.copy()
            df.index = df.index.astype(str).str[:10]

            if day_key not in df.index:
                return None

            close_col = "Close" if "Close" in df.columns else "close"
            if close_col not in df.columns:
                return None

            return float(df.loc[day_key, close_col])

        except Exception:
            logger.exception(
                "Closing-price benchmark lookup failed | %s | %s",
                symbol,
                day_key,
            )
            return None

    # ======================================================
    # Persistence
    # ======================================================

    def record_snapshot(
        self,
        *,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> TransactionCostSummary:
        """
        Compute and persist a timestamped snapshot. Intended to be called
        periodically, not after every order -- this is a rollup over
        potentially many orders, not a per-order fact.
        """

        result = self.analyze_costs(portfolio_id=portfolio_id, symbol=symbol)
        self._persist_snapshot(result)
        return result

    def _persist_snapshot(self, result: TransactionCostSummary) -> None:
        if self.db is None:
            return

        try:
            import json

            self.db.execute(
                text(
                    """
                    INSERT INTO stock_transaction_cost_analysis (

                        portfolio_id,
                        symbol,

                        order_count,
                        total_notional,

                        total_slippage_cost,
                        total_commission_cost,
                        total_cost,

                        blended_slippage_bps,
                        blended_commission_bps,
                        blended_total_cost_bps,

                        cost_by_symbol,
                        cost_by_side,
                        cost_by_size_bucket,

                        generated_at

                    )
                    VALUES (

                        :portfolio_id,
                        :symbol,

                        :order_count,
                        :total_notional,

                        :total_slippage_cost,
                        :total_commission_cost,
                        :total_cost,

                        :blended_slippage_bps,
                        :blended_commission_bps,
                        :blended_total_cost_bps,

                        :cost_by_symbol,
                        :cost_by_side,
                        :cost_by_size_bucket,

                        :generated_at
                    )
                    """
                ),
                {
                    "portfolio_id": result.portfolio_id,
                    "symbol": result.symbol,
                    "order_count": result.order_count,
                    "total_notional": result.total_notional,
                    "total_slippage_cost": result.total_slippage_cost,
                    "total_commission_cost": result.total_commission_cost,
                    "total_cost": result.total_cost,
                    "blended_slippage_bps": result.blended_slippage_bps,
                    "blended_commission_bps": result.blended_commission_bps,
                    "blended_total_cost_bps": result.blended_total_cost_bps,
                    "cost_by_symbol": json.dumps(result.cost_by_symbol),
                    "cost_by_side": json.dumps(result.cost_by_side),
                    "cost_by_size_bucket": json.dumps(result.cost_by_size_bucket),
                    "generated_at": result.generated_at,
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to persist transaction cost analysis snapshot.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Query API
    # ======================================================

    def get_snapshots(
        self,
        *,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_transaction_cost_analysis
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if portfolio_id:
            sql += " AND portfolio_id=:portfolio_id"
            params["portfolio_id"] = portfolio_id

        if symbol:
            sql += " AND UPPER(symbol)=:symbol"
            params["symbol"] = symbol.upper()

        sql += """
            ORDER BY generated_at DESC
            LIMIT :limit
        """

        params["limit"] = limit

        try:
            rows = (
                self.db.execute(text(sql), params)
                .mappings()
                .all()
            )

            return [dict(row) for row in rows]

        except SQLAlchemyError:
            logger.exception("Unable to load transaction cost analysis snapshots.")
            return []

    # ======================================================
    # Dashboard Summary
    # ======================================================

    def summary(self, *, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        result = self.analyze_costs(portfolio_id=portfolio_id)

        cost_as_pct_of_equity = None
        if portfolio_id:
            try:
                from modules.risk_layer.positions import portfolio_equity

                equity = portfolio_equity(self.db, portfolio_id=portfolio_id)
                if equity:
                    cost_as_pct_of_equity = round(result.total_cost / equity * 100.0, 4)
            except Exception:
                logger.exception(
                    "Unable to compute cost-as-pct-of-equity | %s",
                    portfolio_id,
                )

        top_symbols = sorted(
            result.cost_by_symbol.items(), key=lambda kv: kv[1], reverse=True
        )[:5]

        return {
            "order_count": result.order_count,
            "total_notional": result.total_notional,
            "total_cost": result.total_cost,
            "blended_total_cost_bps": result.blended_total_cost_bps,
            "cost_as_pct_of_equity": cost_as_pct_of_equity,
            "top_cost_symbols": dict(top_symbols),
            "cost_by_side": result.cost_by_side,
        }


_transaction_cost_analysis_service = None


def get_stock_transaction_cost_analysis_service(db) -> StockTransactionCostAnalysisService:
    global _transaction_cost_analysis_service

    if (
        _transaction_cost_analysis_service is None
        or _transaction_cost_analysis_service.db is not db
    ):
        _transaction_cost_analysis_service = StockTransactionCostAnalysisService(db)

    return _transaction_cost_analysis_service