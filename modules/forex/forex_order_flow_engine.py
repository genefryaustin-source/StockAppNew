# modules/forex/forex_order_flow_engine.py

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
    from modules.forex.forex_trading_engine import (
        ForexTradingEngine,
        get_forex_trading_engine,
    )
    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )
except Exception:
    from forex_service import (
        ForexService,
        get_forex_service,
        normalize_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
    from forex_trading_engine import (
        ForexTradingEngine,
        get_forex_trading_engine,
    )
    try:
        from forex_liquidity_engine import (
            ForexLiquidityEngine,
            get_forex_liquidity_engine,
        )
    except Exception:
        ForexLiquidityEngine = Any
        get_forex_liquidity_engine = None


logger = logging.getLogger(__name__)

DEFAULT_ORDER_FLOW_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexOrderFlowSnapshot:
    flow_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair: str
    price: float
    bid: Optional[float]
    ask: Optional[float]
    spread: float
    spread_bps: float
    buy_pressure: float
    sell_pressure: float
    net_pressure: float
    imbalance_score: float
    liquidity_score: float
    absorption_score: float
    sweep_score: float
    flow_direction: str
    flow_signal: str
    confidence_score: float
    notes: str
    provider: str
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexOrderFlowScan:
    scan_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_imbalance_score: float
    avg_confidence_score: float
    top_bullish_pair: Optional[str]
    top_bearish_pair: Optional[str]
    created_at: datetime
    snapshots: List[Dict[str, Any]]

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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


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


class ForexOrderFlowEngine:
    """
    Institutional Forex order-flow intelligence.

    Retail FX providers rarely expose true Level 2 order books.
    This engine uses a provider-safe synthetic order-flow model from:
    - bid / ask / spread
    - internal paper order flow
    - liquidity score
    - quote microstructure pressure proxy
    - absorption / sweep proxy

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
        liquidity_engine: Optional[ForexLiquidityEngine] = None,
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

        if liquidity_engine is not None:
            self.liquidity_engine = liquidity_engine
        elif get_forex_liquidity_engine is not None:
            self.liquidity_engine = get_forex_liquidity_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
                forex_service=self.forex_service,
            )
        else:
            self.liquidity_engine = None

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_order_flow_snapshots (
                flow_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair VARCHAR(20),
                price DOUBLE PRECISION,
                bid DOUBLE PRECISION,
                ask DOUBLE PRECISION,
                spread DOUBLE PRECISION,
                spread_bps DOUBLE PRECISION,
                buy_pressure DOUBLE PRECISION,
                sell_pressure DOUBLE PRECISION,
                net_pressure DOUBLE PRECISION,
                imbalance_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                absorption_score DOUBLE PRECISION,
                sweep_score DOUBLE PRECISION,
                flow_direction VARCHAR(40),
                flow_signal VARCHAR(40),
                confidence_score DOUBLE PRECISION,
                notes TEXT,
                provider VARCHAR(80),
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_order_flow_tenant_pair_asof
            ON forex_order_flow_snapshots (tenant_id, pair, asof DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_order_flow_scans (
                scan_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair_count INTEGER,
                bullish_count INTEGER,
                bearish_count INTEGER,
                neutral_count INTEGER,
                avg_imbalance_score DOUBLE PRECISION,
                avg_confidence_score DOUBLE PRECISION,
                top_bullish_pair VARCHAR(20),
                top_bearish_pair VARCHAR(20),
                payload JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def analyze_pair(
        self,
        pair: str,
        *,
        account_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexOrderFlowSnapshot:
        normalized_pair = normalize_pair(pair)
        quote = self.forex_service.get_quote(normalized_pair)

        internal_flow = self._internal_order_flow(
            pair=normalized_pair,
            account_id=account_id,
        )

        liquidity_score = self._liquidity_score(normalized_pair)

        snapshot = self._build_snapshot(
            pair=normalized_pair,
            quote=quote,
            internal_flow=internal_flow,
            liquidity_score=liquidity_score,
        )

        if save:
            self.save_snapshot(snapshot)

        return snapshot

    def scan_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        account_id: Optional[str] = None,
        save: bool = True,
    ) -> ForexOrderFlowScan:
        selected_pairs = pairs or DEFAULT_ORDER_FLOW_PAIRS
        snapshots: List[ForexOrderFlowSnapshot] = []

        for pair in selected_pairs:
            try:
                snapshots.append(
                    self.analyze_pair(
                        pair,
                        account_id=account_id,
                        save=save,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to analyze Forex order flow for %s: %s", pair, exc)

        scan = self._build_scan(
            pair_count=len(selected_pairs),
            snapshots=snapshots,
        )

        if save:
            self.save_scan(scan)

        return scan

    def rank_flow(
        self,
        pairs: Optional[List[str]] = None,
        *,
        direction: str = "BULLISH",
        limit: Optional[int] = None,
        save: bool = False,
    ) -> List[ForexOrderFlowSnapshot]:
        scan = self.scan_pairs(
            pairs=pairs,
            save=save,
        )

        snapshots = [
            self._snapshot_from_dict(row)
            for row in scan.snapshots
        ]

        if direction.upper() == "BEARISH":
            ranked = sorted(
                snapshots,
                key=lambda item: (
                    item.imbalance_score,
                    item.confidence_score,
                    item.liquidity_score,
                ),
            )
        else:
            ranked = sorted(
                snapshots,
                key=lambda item: (
                    item.imbalance_score,
                    item.confidence_score,
                    item.liquidity_score,
                ),
                reverse=True,
            )

        if limit:
            return ranked[: int(limit)]

        return ranked

    def save_snapshot(
        self,
        snapshot: ForexOrderFlowSnapshot,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_order_flow_snapshots (
                flow_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair,
                price,
                bid,
                ask,
                spread,
                spread_bps,
                buy_pressure,
                sell_pressure,
                net_pressure,
                imbalance_score,
                liquidity_score,
                absorption_score,
                sweep_score,
                flow_direction,
                flow_signal,
                confidence_score,
                notes,
                provider,
                raw_payload,
                asof
            )
            VALUES (
                :flow_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair,
                :price,
                :bid,
                :ask,
                :spread,
                :spread_bps,
                :buy_pressure,
                :sell_pressure,
                :net_pressure,
                :imbalance_score,
                :liquidity_score,
                :absorption_score,
                :sweep_score,
                :flow_direction,
                :flow_signal,
                :confidence_score,
                :notes,
                :provider,
                :raw_payload,
                :asof
            )
            ON CONFLICT (flow_id)
            DO UPDATE SET
                price = EXCLUDED.price,
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                spread = EXCLUDED.spread,
                spread_bps = EXCLUDED.spread_bps,
                buy_pressure = EXCLUDED.buy_pressure,
                sell_pressure = EXCLUDED.sell_pressure,
                net_pressure = EXCLUDED.net_pressure,
                imbalance_score = EXCLUDED.imbalance_score,
                liquidity_score = EXCLUDED.liquidity_score,
                absorption_score = EXCLUDED.absorption_score,
                sweep_score = EXCLUDED.sweep_score,
                flow_direction = EXCLUDED.flow_direction,
                flow_signal = EXCLUDED.flow_signal,
                confidence_score = EXCLUDED.confidence_score,
                notes = EXCLUDED.notes,
                provider = EXCLUDED.provider,
                raw_payload = EXCLUDED.raw_payload,
                asof = EXCLUDED.asof
            """,
            {
                **snapshot.to_dict(),
                "raw_payload": _json(snapshot.raw),
                "asof": _naive(snapshot.asof),
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_scan(
        self,
        scan: ForexOrderFlowScan,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_order_flow_scans (
                scan_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair_count,
                bullish_count,
                bearish_count,
                neutral_count,
                avg_imbalance_score,
                avg_confidence_score,
                top_bullish_pair,
                top_bearish_pair,
                payload,
                created_at
            )
            VALUES (
                :scan_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair_count,
                :bullish_count,
                :bearish_count,
                :neutral_count,
                :avg_imbalance_score,
                :avg_confidence_score,
                :top_bullish_pair,
                :top_bearish_pair,
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

    def load_snapshots(
        self,
        *,
        pair: Optional[str] = None,
        direction: str = "ALL",
        signal: str = "ALL",
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

        if direction and direction.upper() != "ALL":
            where += " AND flow_direction = :direction"
            params["direction"] = direction.upper()

        if signal and signal.upper() != "ALL":
            where += " AND flow_signal = :signal"
            params["signal"] = signal.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_order_flow_snapshots
            WHERE {where}
            ORDER BY asof DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()

        return [self._row_to_snapshot_dict(row) for row in rows]

    def load_scans(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = self.db.execute(
            """
            SELECT *
            FROM forex_order_flow_scans
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
                "bullish_count": _row_get(row, "bullish_count"),
                "bearish_count": _row_get(row, "bearish_count"),
                "neutral_count": _row_get(row, "neutral_count"),
                "avg_imbalance_score": _row_get(row, "avg_imbalance_score"),
                "avg_confidence_score": _row_get(row, "avg_confidence_score"),
                "top_bullish_pair": _row_get(row, "top_bullish_pair"),
                "top_bearish_pair": _row_get(row, "top_bearish_pair"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _build_snapshot(
        self,
        *,
        pair: str,
        quote: Any,
        internal_flow: Dict[str, Any],
        liquidity_score: float,
    ) -> ForexOrderFlowSnapshot:
        price = _safe_float(quote.price)
        bid = _safe_float(quote.bid) if quote.bid is not None else None
        ask = _safe_float(quote.ask) if quote.ask is not None else None

        spread = _safe_float(quote.spread)
        if spread <= 0 and bid is not None and ask is not None:
            spread = abs(ask - bid)
        if spread <= 0 and price > 0:
            spread = max(price * 0.00008, 0.00001)

        spread_bps = (spread / price) * 10000.0 if price > 0 else 0.0

        buy_pressure = _safe_float(internal_flow.get("buy_pressure"), 50.0)
        sell_pressure = _safe_float(internal_flow.get("sell_pressure"), 50.0)

        microstructure_bias = self._microstructure_bias(
            price=price,
            bid=bid,
            ask=ask,
            spread_bps=spread_bps,
        )

        buy_pressure = _clamp(buy_pressure + microstructure_bias)
        sell_pressure = _clamp(sell_pressure - microstructure_bias)

        net_pressure = buy_pressure - sell_pressure
        imbalance_score = _clamp(50.0 + net_pressure * 0.5)

        absorption_score = self._absorption_score(
            spread_bps=spread_bps,
            liquidity_score=liquidity_score,
            net_pressure=net_pressure,
        )

        sweep_score = self._sweep_score(
            spread_bps=spread_bps,
            net_pressure=net_pressure,
            liquidity_score=liquidity_score,
        )

        direction = self._flow_direction(imbalance_score)
        signal = self._flow_signal(
            imbalance_score=imbalance_score,
            absorption_score=absorption_score,
            sweep_score=sweep_score,
        )

        confidence = self._confidence_score(
            imbalance_score=imbalance_score,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            sweep_score=sweep_score,
            absorption_score=absorption_score,
        )

        notes = self._notes(
            direction=direction,
            signal=signal,
            imbalance_score=imbalance_score,
            spread_bps=spread_bps,
            liquidity_score=liquidity_score,
        )

        return ForexOrderFlowSnapshot(
            flow_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair=pair,
            price=_round(price, 6),
            bid=_round(bid, 6) if bid is not None else None,
            ask=_round(ask, 6) if ask is not None else None,
            spread=_round(spread, 8),
            spread_bps=_round(spread_bps, 4),
            buy_pressure=_round(buy_pressure),
            sell_pressure=_round(sell_pressure),
            net_pressure=_round(net_pressure),
            imbalance_score=_round(imbalance_score),
            liquidity_score=_round(liquidity_score),
            absorption_score=_round(absorption_score),
            sweep_score=_round(sweep_score),
            flow_direction=direction,
            flow_signal=signal,
            confidence_score=_round(confidence),
            notes=notes,
            provider=getattr(quote, "provider", "unknown"),
            asof=getattr(quote, "asof", None) or _utc_now(),
            raw={
                "quote": quote.to_dict() if hasattr(quote, "to_dict") else None,
                "internal_flow": internal_flow,
            },
        )

    def _build_scan(
        self,
        *,
        pair_count: int,
        snapshots: List[ForexOrderFlowSnapshot],
    ) -> ForexOrderFlowScan:
        bullish = [s for s in snapshots if s.flow_direction == "BULLISH"]
        bearish = [s for s in snapshots if s.flow_direction == "BEARISH"]
        neutral = [s for s in snapshots if s.flow_direction == "NEUTRAL"]

        avg_imbalance = (
            sum(s.imbalance_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )
        avg_confidence = (
            sum(s.confidence_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )

        top_bullish = (
            sorted(
                bullish,
                key=lambda s: (s.imbalance_score, s.confidence_score),
                reverse=True,
            )[0].pair
            if bullish
            else None
        )

        top_bearish = (
            sorted(
                bearish,
                key=lambda s: (s.imbalance_score, s.confidence_score),
            )[0].pair
            if bearish
            else None
        )

        ranked = sorted(
            snapshots,
            key=lambda s: (
                abs(s.imbalance_score - 50.0),
                s.confidence_score,
                s.liquidity_score,
            ),
            reverse=True,
        )

        return ForexOrderFlowScan(
            scan_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair_count=pair_count,
            bullish_count=len(bullish),
            bearish_count=len(bearish),
            neutral_count=len(neutral),
            avg_imbalance_score=_round(avg_imbalance),
            avg_confidence_score=_round(avg_confidence),
            top_bullish_pair=top_bullish,
            top_bearish_pair=top_bearish,
            created_at=_utc_now(),
            snapshots=[s.to_dict() for s in ranked],
        )

    def _internal_order_flow(
        self,
        *,
        pair: str,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            orders = self.trading_engine.list_orders(
                account_id=account_id,
                status="ALL",
                limit=250,
            )
        except Exception:
            orders = []

        pair_orders = [
            order
            for order in orders
            if normalize_pair(getattr(order, "pair", "")) == pair
        ]

        buy_units = sum(
            _safe_float(getattr(order, "units", 0.0))
            for order in pair_orders
            if getattr(order, "side", "") == "BUY"
        )

        sell_units = sum(
            _safe_float(getattr(order, "units", 0.0))
            for order in pair_orders
            if getattr(order, "side", "") == "SELL"
        )

        total_units = buy_units + sell_units

        if total_units <= 0:
            return {
                "buy_units": 0.0,
                "sell_units": 0.0,
                "buy_pressure": 50.0,
                "sell_pressure": 50.0,
                "order_count": len(pair_orders),
            }

        buy_pressure = (buy_units / total_units) * 100.0
        sell_pressure = (sell_units / total_units) * 100.0

        return {
            "buy_units": buy_units,
            "sell_units": sell_units,
            "buy_pressure": buy_pressure,
            "sell_pressure": sell_pressure,
            "order_count": len(pair_orders),
        }

    def _liquidity_score(
        self,
        pair: str,
    ) -> float:
        if self.liquidity_engine is None:
            return 70.0

        try:
            snapshot = self.liquidity_engine.analyze_pair(
                pair,
                save=False,
            )
            return _safe_float(snapshot.liquidity_score, 70.0)
        except Exception:
            return 70.0

    def _microstructure_bias(
        self,
        *,
        price: float,
        bid: Optional[float],
        ask: Optional[float],
        spread_bps: float,
    ) -> float:
        if price <= 0 or bid is None or ask is None:
            return 0.0

        midpoint = (bid + ask) / 2.0
        if midpoint <= 0:
            return 0.0

        distance = (price - midpoint) / midpoint
        bias = distance * 10000.0

        if spread_bps > 5:
            bias *= 0.65

        return max(-12.0, min(12.0, bias))

    def _absorption_score(
        self,
        *,
        spread_bps: float,
        liquidity_score: float,
        net_pressure: float,
    ) -> float:
        pressure_strength = abs(net_pressure)

        score = (
            liquidity_score * 0.55
            + max(0.0, 100.0 - spread_bps * 8.0) * 0.25
            + max(0.0, 100.0 - pressure_strength) * 0.20
        )

        return _clamp(score)

    def _sweep_score(
        self,
        *,
        spread_bps: float,
        net_pressure: float,
        liquidity_score: float,
    ) -> float:
        pressure_strength = abs(net_pressure)

        score = (
            pressure_strength * 1.35
            + max(0.0, 100.0 - liquidity_score) * 0.30
            + spread_bps * 2.5
        )

        return _clamp(score)

    def _flow_direction(
        self,
        imbalance_score: float,
    ) -> str:
        if imbalance_score >= 58:
            return "BULLISH"

        if imbalance_score <= 42:
            return "BEARISH"

        return "NEUTRAL"

    def _flow_signal(
        self,
        *,
        imbalance_score: float,
        absorption_score: float,
        sweep_score: float,
    ) -> str:
        if imbalance_score >= 70 and sweep_score >= 60:
            return "AGGRESSIVE_BUY_FLOW"

        if imbalance_score <= 30 and sweep_score >= 60:
            return "AGGRESSIVE_SELL_FLOW"

        if imbalance_score >= 58 and absorption_score >= 65:
            return "BUY_ABSORPTION"

        if imbalance_score <= 42 and absorption_score >= 65:
            return "SELL_ABSORPTION"

        return "BALANCED_FLOW"

    def _confidence_score(
        self,
        *,
        imbalance_score: float,
        liquidity_score: float,
        spread_bps: float,
        sweep_score: float,
        absorption_score: float,
    ) -> float:
        imbalance_strength = abs(imbalance_score - 50.0) * 1.7
        liquidity_component = liquidity_score * 0.35
        spread_component = max(0.0, 100.0 - spread_bps * 10.0) * 0.20
        event_component = max(sweep_score, absorption_score) * 0.20

        confidence = (
            25.0
            + imbalance_strength
            + liquidity_component
            + spread_component
            + event_component
        )

        return _clamp(confidence)

    def _notes(
        self,
        *,
        direction: str,
        signal: str,
        imbalance_score: float,
        spread_bps: float,
        liquidity_score: float,
    ) -> str:
        notes: List[str] = []

        notes.append(f"Order-flow direction is {direction} with signal {signal}.")

        if abs(imbalance_score - 50.0) >= 20:
            notes.append("Material order-flow imbalance detected.")

        if spread_bps > 5:
            notes.append("Spread is elevated; use caution with market orders.")

        if liquidity_score < 55:
            notes.append("Liquidity is below preferred threshold.")

        return " ".join(notes)

    def _snapshot_from_dict(
        self,
        row: Dict[str, Any],
    ) -> ForexOrderFlowSnapshot:
        asof_raw = row.get("asof")
        if isinstance(asof_raw, datetime):
            asof = asof_raw
        else:
            try:
                asof = datetime.fromisoformat(str(asof_raw))
            except Exception:
                asof = _utc_now()

        if asof.tzinfo is None:
            asof = asof.replace(tzinfo=timezone.utc)

        return ForexOrderFlowSnapshot(
            flow_id=row.get("flow_id") or str(uuid.uuid4()),
            tenant_id=row.get("tenant_id"),
            user_id=row.get("user_id"),
            portfolio_id=row.get("portfolio_id"),
            pair=row.get("pair"),
            price=_safe_float(row.get("price")),
            bid=row.get("bid"),
            ask=row.get("ask"),
            spread=_safe_float(row.get("spread")),
            spread_bps=_safe_float(row.get("spread_bps")),
            buy_pressure=_safe_float(row.get("buy_pressure")),
            sell_pressure=_safe_float(row.get("sell_pressure")),
            net_pressure=_safe_float(row.get("net_pressure")),
            imbalance_score=_safe_float(row.get("imbalance_score")),
            liquidity_score=_safe_float(row.get("liquidity_score")),
            absorption_score=_safe_float(row.get("absorption_score")),
            sweep_score=_safe_float(row.get("sweep_score")),
            flow_direction=row.get("flow_direction"),
            flow_signal=row.get("flow_signal"),
            confidence_score=_safe_float(row.get("confidence_score")),
            notes=row.get("notes", ""),
            provider=row.get("provider", "unknown"),
            asof=asof,
            raw=row.get("raw"),
        )

    def _row_to_snapshot_dict(
        self,
        row: Any,
    ) -> Dict[str, Any]:
        return {
            "flow_id": _row_get(row, "flow_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "pair": _row_get(row, "pair"),
            "price": _row_get(row, "price"),
            "bid": _row_get(row, "bid"),
            "ask": _row_get(row, "ask"),
            "spread": _row_get(row, "spread"),
            "spread_bps": _row_get(row, "spread_bps"),
            "buy_pressure": _row_get(row, "buy_pressure"),
            "sell_pressure": _row_get(row, "sell_pressure"),
            "net_pressure": _row_get(row, "net_pressure"),
            "imbalance_score": _row_get(row, "imbalance_score"),
            "liquidity_score": _row_get(row, "liquidity_score"),
            "absorption_score": _row_get(row, "absorption_score"),
            "sweep_score": _row_get(row, "sweep_score"),
            "flow_direction": _row_get(row, "flow_direction"),
            "flow_signal": _row_get(row, "flow_signal"),
            "confidence_score": _row_get(row, "confidence_score"),
            "notes": _row_get(row, "notes"),
            "provider": _row_get(row, "provider"),
            "asof": str(_row_get(row, "asof", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_order_flow_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    trading_engine: Optional[ForexTradingEngine] = None,
    liquidity_engine: Optional[ForexLiquidityEngine] = None,
) -> ForexOrderFlowEngine:
    return ForexOrderFlowEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
        trading_engine=trading_engine,
        liquidity_engine=liquidity_engine,
    )


def analyze_forex_order_flow(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_order_flow_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.analyze_pair(
        pair,
        account_id=account_id,
        save=save,
    ).to_dict()


def run_forex_order_flow_scan(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    account_id: Optional[str] = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_order_flow_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.scan_pairs(
        pairs=pairs,
        account_id=account_id,
        save=save,
    ).to_dict()