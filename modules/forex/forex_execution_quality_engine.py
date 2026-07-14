"""
modules/forex/forex_execution_quality_engine.py

Sprint 27 - Phase 1B
Institutional Forex Execution Quality Engine
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass
class ForexExecutionQualityResult:
    execution_count: int = 0
    priced_execution_count: int = 0
    latency_observation_count: int = 0
    slippage_observation_count: int = 0
    spread_observation_count: int = 0
    commission_observation_count: int = 0
    average_slippage: float = 0.0
    median_slippage: float = 0.0
    minimum_slippage: float = 0.0
    maximum_slippage: float = 0.0
    average_absolute_slippage: float = 0.0
    total_slippage_cost: float = 0.0
    average_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    minimum_latency_ms: float = 0.0
    maximum_latency_ms: float = 0.0
    average_spread: float = 0.0
    median_spread: float = 0.0
    minimum_spread: float = 0.0
    maximum_spread: float = 0.0
    total_commission: float = 0.0
    average_commission: float = 0.0
    total_execution_cost: float = 0.0
    average_execution_cost: float = 0.0
    favorable_fill_count: int = 0
    adverse_fill_count: int = 0
    neutral_fill_count: int = 0
    favorable_fill_rate: float = 0.0
    adverse_fill_rate: float = 0.0
    broker_score: float = 0.0
    execution_grade: str = "N/A"
    latency_rating: str = "N/A"
    slippage_rating: str = "N/A"
    cost_rating: str = "N/A"
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexExecutionQualityEngine:
    PRICE_FIELDS: Sequence[str] = (
        "execution_price", "fill_price", "avg_fill_price", "filled_price", "price"
    )
    REQUESTED_PRICE_FIELDS: Sequence[str] = (
        "requested_price", "expected_price", "quote_price", "limit_price", "stop_price", "price"
    )
    QUANTITY_FIELDS: Sequence[str] = (
        "filled_qty", "filled_quantity", "filled_units", "quantity", "units", "size"
    )
    SUBMITTED_TIME_FIELDS: Sequence[str] = (
        "submitted_at", "created_at", "routed_at", "accepted_at"
    )
    FILLED_TIME_FIELDS: Sequence[str] = (
        "filled_at", "executed_at", "updated_at"
    )
    SLIPPAGE_FIELDS: Sequence[str] = (
        "slippage", "actual_slippage", "slippage_amount"
    )
    SPREAD_FIELDS: Sequence[str] = (
        "spread", "execution_spread", "quoted_spread"
    )
    COMMISSION_FIELDS: Sequence[str] = (
        "commission", "commission_amount", "fee", "fees"
    )

    def analyze(
        self,
        *,
        executions: Optional[Iterable[Any]] = None,
        filled_orders: Optional[Iterable[Any]] = None,
        execution_history: Optional[Iterable[Any]] = None,
    ) -> Dict[str, Any]:
        records = self._merge_records(
            executions=executions,
            filled_orders=filled_orders,
            execution_history=execution_history,
        )

        result = ForexExecutionQualityResult(
            execution_count=len(records),
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

        latencies: List[float] = []
        slippages: List[float] = []
        absolute_slippages: List[float] = []
        spreads: List[float] = []
        commissions: List[float] = []
        execution_costs: List[float] = []

        for record in records:
            side = str(self._first(record, ("side", "order_side"), "") or "").upper()
            fill_price = self._first_float(record, self.PRICE_FIELDS, default=None)
            requested_price = self._first_float(record, self.REQUESTED_PRICE_FIELDS, default=None)
            quantity = abs(self._first_float(record, self.QUANTITY_FIELDS, default=0.0) or 0.0)
            commission = self._first_float(record, self.COMMISSION_FIELDS, default=0.0) or 0.0
            spread = self._first_float(record, self.SPREAD_FIELDS, default=None)

            if fill_price is not None and fill_price > 0:
                result.priced_execution_count += 1

            slippage = self._first_float(record, self.SLIPPAGE_FIELDS, default=None)
            if slippage is None and fill_price is not None and requested_price is not None:
                slippage = self._signed_slippage(
                    side=side,
                    requested_price=requested_price,
                    fill_price=fill_price,
                )

            if slippage is not None:
                slippages.append(slippage)
                absolute_slippages.append(abs(slippage))
                if slippage < 0:
                    result.favorable_fill_count += 1
                elif slippage > 0:
                    result.adverse_fill_count += 1
                else:
                    result.neutral_fill_count += 1
                slippage_cost = abs(slippage) * quantity
            else:
                slippage_cost = 0.0

            if spread is not None:
                spreads.append(abs(spread))

            commissions.append(commission)
            latency_ms = self._latency_ms(record)
            if latency_ms is not None:
                latencies.append(latency_ms)

            execution_costs.append(slippage_cost + abs(commission))

        self._apply_distribution_metrics(
            result=result,
            slippages=slippages,
            absolute_slippages=absolute_slippages,
            latencies=latencies,
            spreads=spreads,
            commissions=commissions,
            execution_costs=execution_costs,
        )
        self._apply_ratings(result)

        return {
            **result.to_dict(),
            "quality_breakdown": {
                "favorable_fills": result.favorable_fill_count,
                "adverse_fills": result.adverse_fill_count,
                "neutral_fills": result.neutral_fill_count,
                "favorable_fill_rate": result.favorable_fill_rate,
                "adverse_fill_rate": result.adverse_fill_rate,
            },
            "latency": {
                "average_ms": result.average_latency_ms,
                "median_ms": result.median_latency_ms,
                "p95_ms": result.p95_latency_ms,
                "minimum_ms": result.minimum_latency_ms,
                "maximum_ms": result.maximum_latency_ms,
                "observations": result.latency_observation_count,
                "rating": result.latency_rating,
            },
            "slippage": {
                "average": result.average_slippage,
                "median": result.median_slippage,
                "minimum": result.minimum_slippage,
                "maximum": result.maximum_slippage,
                "average_absolute": result.average_absolute_slippage,
                "total_cost": result.total_slippage_cost,
                "observations": result.slippage_observation_count,
                "rating": result.slippage_rating,
            },
            "spread": {
                "average": result.average_spread,
                "median": result.median_spread,
                "minimum": result.minimum_spread,
                "maximum": result.maximum_spread,
                "observations": result.spread_observation_count,
            },
            "cost": {
                "total_commission": result.total_commission,
                "average_commission": result.average_commission,
                "total_execution_cost": result.total_execution_cost,
                "average_execution_cost": result.average_execution_cost,
                "observations": result.commission_observation_count,
                "rating": result.cost_rating,
            },
        }

    def _merge_records(
        self,
        *,
        executions: Optional[Iterable[Any]],
        filled_orders: Optional[Iterable[Any]],
        execution_history: Optional[Iterable[Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for source in (executions, filled_orders, execution_history):
            for raw in source or []:
                record = self._to_mapping(raw)
                if not record:
                    continue
                key = self._record_key(record)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(record)
        return merged

    @staticmethod
    def _to_mapping(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "to_dict"):
            try:
                mapped = value.to_dict()
                if isinstance(mapped, Mapping):
                    return dict(mapped)
            except Exception:
                pass
        if hasattr(value, "__dict__"):
            try:
                return {k: v for k, v in vars(value).items() if not k.startswith("_")}
            except Exception:
                pass
        return {}

    def _record_key(self, record: Mapping[str, Any]) -> str:
        for field in ("execution_id", "fill_id", "event_id", "broker_order_id", "order_id", "id"):
            value = record.get(field)
            if value not in (None, ""):
                return f"{field}:{value}"
        return repr(sorted((str(k), repr(v)) for k, v in record.items()))

    @staticmethod
    def _first(record: Mapping[str, Any], fields: Sequence[str], default: Any = None) -> Any:
        for field in fields:
            value = record.get(field)
            if value not in (None, ""):
                return value
        return default

    def _first_float(
        self,
        record: Mapping[str, Any],
        fields: Sequence[str],
        default: Optional[float] = 0.0,
    ) -> Optional[float]:
        value = self._first(record, fields, default)
        return self._safe_float(value, default)

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        if value is None:
            return default
        try:
            number = float(value)
            if math.isnan(number) or math.isinf(number):
                return default
            return number
        except Exception:
            return default

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        try:
            text = str(value).strip()
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _latency_ms(self, record: Mapping[str, Any]) -> Optional[float]:
        explicit = self._first_float(
            record,
            ("latency_ms", "execution_latency_ms", "fill_latency_ms", "round_trip_ms"),
            default=None,
        )
        if explicit is not None and explicit >= 0:
            return explicit

        submitted = self._parse_datetime(self._first(record, self.SUBMITTED_TIME_FIELDS))
        filled = self._parse_datetime(self._first(record, self.FILLED_TIME_FIELDS))
        if submitted is None or filled is None:
            return None

        delta_ms = (filled - submitted).total_seconds() * 1000.0
        return delta_ms if delta_ms >= 0 else None

    @staticmethod
    def _signed_slippage(*, side: str, requested_price: float, fill_price: float) -> float:
        if side == "SELL":
            return requested_price - fill_price
        return fill_price - requested_price

    def _apply_distribution_metrics(
        self,
        *,
        result: ForexExecutionQualityResult,
        slippages: List[float],
        absolute_slippages: List[float],
        latencies: List[float],
        spreads: List[float],
        commissions: List[float],
        execution_costs: List[float],
    ) -> None:
        result.slippage_observation_count = len(slippages)
        result.latency_observation_count = len(latencies)
        result.spread_observation_count = len(spreads)
        result.commission_observation_count = len(commissions)

        if slippages:
            result.average_slippage = statistics.fmean(slippages)
            result.median_slippage = statistics.median(slippages)
            result.minimum_slippage = min(slippages)
            result.maximum_slippage = max(slippages)
        if absolute_slippages:
            result.average_absolute_slippage = statistics.fmean(absolute_slippages)
            result.total_slippage_cost = sum(absolute_slippages)
        if latencies:
            ordered = sorted(latencies)
            result.average_latency_ms = statistics.fmean(ordered)
            result.median_latency_ms = statistics.median(ordered)
            result.p95_latency_ms = self._percentile(ordered, 95.0)
            result.minimum_latency_ms = ordered[0]
            result.maximum_latency_ms = ordered[-1]
        if spreads:
            result.average_spread = statistics.fmean(spreads)
            result.median_spread = statistics.median(spreads)
            result.minimum_spread = min(spreads)
            result.maximum_spread = max(spreads)
        if commissions:
            result.total_commission = sum(abs(v) for v in commissions)
            result.average_commission = statistics.fmean(abs(v) for v in commissions)
        if execution_costs:
            result.total_execution_cost = sum(execution_costs)
            result.average_execution_cost = statistics.fmean(execution_costs)

        classified = result.favorable_fill_count + result.adverse_fill_count + result.neutral_fill_count
        if classified:
            result.favorable_fill_rate = result.favorable_fill_count / classified * 100.0
            result.adverse_fill_rate = result.adverse_fill_count / classified * 100.0

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        rank = percentile / 100.0 * (len(values) - 1)
        lower = int(math.floor(rank))
        upper = int(math.ceil(rank))
        if lower == upper:
            return values[lower]
        weight = rank - lower
        return values[lower] * (1.0 - weight) + values[upper] * weight

    def _apply_ratings(self, result: ForexExecutionQualityResult) -> None:
        result.latency_rating = self._latency_rating(result.average_latency_ms)
        result.slippage_rating = self._slippage_rating(result.average_absolute_slippage)
        result.cost_rating = self._cost_rating(result.average_execution_cost)

        score = 100.0
        if result.latency_observation_count:
            if result.average_latency_ms > 1000:
                score -= 35
            elif result.average_latency_ms > 500:
                score -= 25
            elif result.average_latency_ms > 250:
                score -= 15
            elif result.average_latency_ms > 100:
                score -= 7
        if result.slippage_observation_count:
            if result.average_absolute_slippage > 0.001:
                score -= 35
            elif result.average_absolute_slippage > 0.0005:
                score -= 25
            elif result.average_absolute_slippage > 0.0002:
                score -= 15
            elif result.average_absolute_slippage > 0.00005:
                score -= 7
        if result.adverse_fill_rate > 75:
            score -= 15
        elif result.adverse_fill_rate > 50:
            score -= 8
        if result.execution_count == 0:
            score = 0.0
        result.broker_score = round(max(0.0, min(100.0, score)), 2)
        result.execution_grade = self._grade(result.broker_score)

    @staticmethod
    def _latency_rating(value: float) -> str:
        if value <= 0:
            return "N/A"
        if value <= 50:
            return "EXCELLENT"
        if value <= 150:
            return "GOOD"
        if value <= 350:
            return "FAIR"
        if value <= 750:
            return "SLOW"
        return "POOR"

    @staticmethod
    def _slippage_rating(value: float) -> str:
        if value <= 0.00005:
            return "EXCELLENT"
        if value <= 0.0002:
            return "GOOD"
        if value <= 0.0005:
            return "FAIR"
        if value <= 0.001:
            return "POOR"
        return "CRITICAL"

    @staticmethod
    def _cost_rating(value: float) -> str:
        if value <= 1:
            return "EXCELLENT"
        if value <= 5:
            return "GOOD"
        if value <= 15:
            return "FAIR"
        if value <= 50:
            return "POOR"
        return "CRITICAL"

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 97:
            return "A+"
        if score >= 93:
            return "A"
        if score >= 90:
            return "A-"
        if score >= 87:
            return "B+"
        if score >= 83:
            return "B"
        if score >= 80:
            return "B-"
        if score >= 77:
            return "C+"
        if score >= 73:
            return "C"
        if score >= 70:
            return "C-"
        if score >= 60:
            return "D"
        return "F"


def get_forex_execution_quality_engine() -> ForexExecutionQualityEngine:
    return ForexExecutionQualityEngine()
