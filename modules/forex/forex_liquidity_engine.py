# modules/forex/forex_liquidity_engine.py

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
        ForexQuote,
        get_forex_service,
        normalize_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )
except Exception:
    from forex_service import (
        ForexService,
        ForexQuote,
        get_forex_service,
        normalize_pair,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )


logger = logging.getLogger(__name__)

DEFAULT_LIQUIDITY_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexLiquiditySnapshot:
    liquidity_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair: str
    price: float
    bid: Optional[float]
    ask: Optional[float]
    spread: float
    spread_bps: float
    relative_spread: float
    estimated_depth_score: float
    volume_proxy: float
    volatility_penalty: float
    liquidity_score: float
    tradability_score: float
    liquidity_tier: str
    provider: str
    notes: str
    asof: datetime
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["asof"] = self.asof.isoformat()
        return data


@dataclass
class ForexLiquidityScan:
    scan_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]
    pair_count: int
    avg_liquidity_score: float
    avg_tradability_score: float
    best_pair: Optional[str]
    worst_pair: Optional[str]
    excellent_count: int
    good_count: int
    average_count: int
    weak_count: int
    poor_count: int
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


class ForexLiquidityEngine:
    """
    Institutional Forex liquidity intelligence.

    Measures:
    - Bid / ask spread
    - Spread bps
    - Relative spread
    - Estimated depth score
    - Volume proxy
    - Volatility penalty
    - Liquidity score
    - Tradability score
    - Liquidity tier

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

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_liquidity_snapshots (
                liquidity_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair VARCHAR(20),
                price DOUBLE PRECISION,
                bid DOUBLE PRECISION,
                ask DOUBLE PRECISION,
                spread DOUBLE PRECISION,
                spread_bps DOUBLE PRECISION,
                relative_spread DOUBLE PRECISION,
                estimated_depth_score DOUBLE PRECISION,
                volume_proxy DOUBLE PRECISION,
                volatility_penalty DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                tradability_score DOUBLE PRECISION,
                liquidity_tier VARCHAR(40),
                provider VARCHAR(80),
                notes TEXT,
                raw_payload JSONB,
                asof TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_liquidity_snapshots_tenant_pair_asof
            ON forex_liquidity_snapshots (tenant_id, pair, asof DESC)
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_liquidity_scans (
                scan_id VARCHAR(80) PRIMARY KEY,
                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),
                pair_count INTEGER,
                avg_liquidity_score DOUBLE PRECISION,
                avg_tradability_score DOUBLE PRECISION,
                best_pair VARCHAR(20),
                worst_pair VARCHAR(20),
                excellent_count INTEGER,
                good_count INTEGER,
                average_count INTEGER,
                weak_count INTEGER,
                poor_count INTEGER,
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
        save: bool = True,
    ) -> ForexLiquiditySnapshot:
        normalized_pair = normalize_pair(pair)
        quote = self.forex_service.get_quote(normalized_pair)

        snapshot = self._build_snapshot(quote)

        if save:
            self.save_snapshot(snapshot)

        return snapshot

    def scan_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        min_tradability_score: float = 0.0,
        save: bool = True,
    ) -> ForexLiquidityScan:
        selected_pairs = pairs or DEFAULT_LIQUIDITY_PAIRS
        snapshots: List[ForexLiquiditySnapshot] = []

        for pair in selected_pairs:
            try:
                snapshot = self.analyze_pair(pair, save=save)
                if snapshot.tradability_score >= min_tradability_score:
                    snapshots.append(snapshot)
            except Exception as exc:
                logger.warning("Failed to analyze Forex liquidity for %s: %s", pair, exc)

        scan = self._build_scan(
            pair_count=len(selected_pairs),
            snapshots=snapshots,
        )

        if save:
            self.save_scan(scan)

        return scan

    def rank_liquidity(
        self,
        pairs: Optional[List[str]] = None,
        *,
        limit: Optional[int] = None,
        save: bool = False,
    ) -> List[ForexLiquiditySnapshot]:
        scan = self.scan_pairs(
            pairs=pairs,
            save=save,
        )

        ranked = sorted(
            [
                self._snapshot_from_dict(row)
                for row in scan.snapshots
            ],
            key=lambda item: (
                item.tradability_score,
                item.liquidity_score,
                -item.spread_bps,
            ),
            reverse=True,
        )

        if limit:
            return ranked[: int(limit)]

        return ranked

    def get_best_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        min_liquidity_score: float = 70.0,
        limit: int = 10,
        save: bool = False,
    ) -> List[ForexLiquiditySnapshot]:
        ranked = self.rank_liquidity(
            pairs=pairs,
            limit=None,
            save=save,
        )

        filtered = [
            item
            for item in ranked
            if item.liquidity_score >= min_liquidity_score
        ]

        return filtered[: int(limit)]

    def save_snapshot(
        self,
        snapshot: ForexLiquiditySnapshot,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_liquidity_snapshots (
                liquidity_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair,
                price,
                bid,
                ask,
                spread,
                spread_bps,
                relative_spread,
                estimated_depth_score,
                volume_proxy,
                volatility_penalty,
                liquidity_score,
                tradability_score,
                liquidity_tier,
                provider,
                notes,
                raw_payload,
                asof
            )
            VALUES (
                :liquidity_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair,
                :price,
                :bid,
                :ask,
                :spread,
                :spread_bps,
                :relative_spread,
                :estimated_depth_score,
                :volume_proxy,
                :volatility_penalty,
                :liquidity_score,
                :tradability_score,
                :liquidity_tier,
                :provider,
                :notes,
                :raw_payload,
                :asof
            )
            ON CONFLICT (liquidity_id)
            DO UPDATE SET
                price = EXCLUDED.price,
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                spread = EXCLUDED.spread,
                spread_bps = EXCLUDED.spread_bps,
                relative_spread = EXCLUDED.relative_spread,
                estimated_depth_score = EXCLUDED.estimated_depth_score,
                volume_proxy = EXCLUDED.volume_proxy,
                volatility_penalty = EXCLUDED.volatility_penalty,
                liquidity_score = EXCLUDED.liquidity_score,
                tradability_score = EXCLUDED.tradability_score,
                liquidity_tier = EXCLUDED.liquidity_tier,
                provider = EXCLUDED.provider,
                notes = EXCLUDED.notes,
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
        scan: ForexLiquidityScan,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_liquidity_scans (
                scan_id,
                tenant_id,
                user_id,
                portfolio_id,
                pair_count,
                avg_liquidity_score,
                avg_tradability_score,
                best_pair,
                worst_pair,
                excellent_count,
                good_count,
                average_count,
                weak_count,
                poor_count,
                payload,
                created_at
            )
            VALUES (
                :scan_id,
                :tenant_id,
                :user_id,
                :portfolio_id,
                :pair_count,
                :avg_liquidity_score,
                :avg_tradability_score,
                :best_pair,
                :worst_pair,
                :excellent_count,
                :good_count,
                :average_count,
                :weak_count,
                :poor_count,
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
        liquidity_tier: str = "ALL",
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

        if liquidity_tier and liquidity_tier.upper() != "ALL":
            where += " AND liquidity_tier = :liquidity_tier"
            params["liquidity_tier"] = liquidity_tier.upper()

        rows = self.db.execute(
            f"""
            SELECT *
            FROM forex_liquidity_snapshots
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
            FROM forex_liquidity_scans
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
                "avg_liquidity_score": _row_get(row, "avg_liquidity_score"),
                "avg_tradability_score": _row_get(row, "avg_tradability_score"),
                "best_pair": _row_get(row, "best_pair"),
                "worst_pair": _row_get(row, "worst_pair"),
                "excellent_count": _row_get(row, "excellent_count"),
                "good_count": _row_get(row, "good_count"),
                "average_count": _row_get(row, "average_count"),
                "weak_count": _row_get(row, "weak_count"),
                "poor_count": _row_get(row, "poor_count"),
                "created_at": str(_row_get(row, "created_at", "")),
            }
            for row in rows
        ]

    def _build_snapshot(
        self,
        quote: ForexQuote,
    ) -> ForexLiquiditySnapshot:
        price = _safe_float(quote.price)
        bid = _safe_float(quote.bid) if quote.bid is not None else None
        ask = _safe_float(quote.ask) if quote.ask is not None else None

        spread = _safe_float(quote.spread)

        if spread <= 0 and bid is not None and ask is not None:
            spread = abs(ask - bid)

        if spread <= 0 and price > 0:
            spread = max(price * 0.00008, 0.00001)

        spread_bps = (spread / price) * 10000.0 if price > 0 else 0.0
        relative_spread = spread / price if price > 0 else 0.0

        estimated_depth_score = self._estimated_depth_score(quote.pair)
        volume_proxy = self._volume_proxy(quote.pair)
        volatility_penalty = self._volatility_penalty(quote.pair, spread_bps)

        liquidity_score = self._liquidity_score(
            spread_bps=spread_bps,
            estimated_depth_score=estimated_depth_score,
            volume_proxy=volume_proxy,
            volatility_penalty=volatility_penalty,
        )

        tradability_score = self._tradability_score(
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            relative_spread=relative_spread,
        )

        tier = self._liquidity_tier(tradability_score)

        notes = self._notes(
            spread_bps=spread_bps,
            liquidity_score=liquidity_score,
            tradability_score=tradability_score,
            tier=tier,
        )

        return ForexLiquiditySnapshot(
            liquidity_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair=quote.pair,
            price=_round(price, 6),
            bid=_round(bid, 6) if bid is not None else None,
            ask=_round(ask, 6) if ask is not None else None,
            spread=_round(spread, 8),
            spread_bps=_round(spread_bps, 4),
            relative_spread=_round(relative_spread, 8),
            estimated_depth_score=_round(estimated_depth_score),
            volume_proxy=_round(volume_proxy),
            volatility_penalty=_round(volatility_penalty),
            liquidity_score=_round(liquidity_score),
            tradability_score=_round(tradability_score),
            liquidity_tier=tier,
            provider=quote.provider,
            notes=notes,
            asof=quote.asof or _utc_now(),
            raw={"quote": quote.to_dict()},
        )

    def _build_scan(
        self,
        *,
        pair_count: int,
        snapshots: List[ForexLiquiditySnapshot],
    ) -> ForexLiquidityScan:
        avg_liquidity = (
            sum(s.liquidity_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )
        avg_tradability = (
            sum(s.tradability_score for s in snapshots) / len(snapshots)
            if snapshots
            else 0.0
        )

        ranked = sorted(
            snapshots,
            key=lambda s: (
                s.tradability_score,
                s.liquidity_score,
                -s.spread_bps,
            ),
            reverse=True,
        )

        return ForexLiquidityScan(
            scan_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            pair_count=pair_count,
            avg_liquidity_score=_round(avg_liquidity),
            avg_tradability_score=_round(avg_tradability),
            best_pair=ranked[0].pair if ranked else None,
            worst_pair=ranked[-1].pair if ranked else None,
            excellent_count=len([s for s in snapshots if s.liquidity_tier == "EXCELLENT"]),
            good_count=len([s for s in snapshots if s.liquidity_tier == "GOOD"]),
            average_count=len([s for s in snapshots if s.liquidity_tier == "AVERAGE"]),
            weak_count=len([s for s in snapshots if s.liquidity_tier == "WEAK"]),
            poor_count=len([s for s in snapshots if s.liquidity_tier == "POOR"]),
            created_at=_utc_now(),
            snapshots=[s.to_dict() for s in ranked],
        )

    def _estimated_depth_score(
        self,
        pair: str,
    ) -> float:
        pair = normalize_pair(pair)

        major_scores = {
            "EUR/USD": 98.0,
            "USD/JPY": 96.0,
            "GBP/USD": 94.0,
            "USD/CHF": 90.0,
            "AUD/USD": 88.0,
            "USD/CAD": 87.0,
            "NZD/USD": 82.0,
        }

        cross_scores = {
            "EUR/GBP": 86.0,
            "EUR/JPY": 88.0,
            "GBP/JPY": 82.0,
            "AUD/JPY": 78.0,
            "EUR/CHF": 80.0,
            "AUD/CAD": 74.0,
            "CAD/JPY": 76.0,
        }

        if pair in major_scores:
            return major_scores[pair]

        if pair in cross_scores:
            return cross_scores[pair]

        if "USD" in pair:
            return 72.0

        return 58.0

    def _volume_proxy(
        self,
        pair: str,
    ) -> float:
        pair = normalize_pair(pair)

        if pair in {"EUR/USD", "USD/JPY"}:
            return 100.0

        if pair in {"GBP/USD", "AUD/USD", "USD/CAD", "USD/CHF"}:
            return 90.0

        if pair in MAJOR_PAIRS:
            return 85.0

        if pair in CROSS_PAIRS:
            return 70.0

        return 50.0

    def _volatility_penalty(
        self,
        pair: str,
        spread_bps: float,
    ) -> float:
        pair = normalize_pair(pair)

        high_vol_pairs = {
            "GBP/JPY",
            "AUD/JPY",
            "NZD/JPY",
            "GBP/AUD",
            "EUR/NZD",
        }

        penalty = 0.0

        if pair in high_vol_pairs:
            penalty += 10.0

        if spread_bps > 5:
            penalty += min(20.0, spread_bps * 1.5)

        return max(0.0, min(40.0, penalty))

    def _liquidity_score(
        self,
        *,
        spread_bps: float,
        estimated_depth_score: float,
        volume_proxy: float,
        volatility_penalty: float,
    ) -> float:
        spread_score = max(0.0, 100.0 - spread_bps * 8.0)

        score = (
            spread_score * 0.35
            + estimated_depth_score * 0.30
            + volume_proxy * 0.25
            + max(0.0, 100.0 - volatility_penalty) * 0.10
        )

        return max(0.0, min(100.0, score))

    def _tradability_score(
        self,
        *,
        liquidity_score: float,
        spread_bps: float,
        relative_spread: float,
    ) -> float:
        spread_penalty = min(45.0, spread_bps * 4.0)
        relative_penalty = min(30.0, relative_spread * 10000.0)

        score = liquidity_score - spread_penalty * 0.45 - relative_penalty * 0.25

        return max(0.0, min(100.0, score))

    def _liquidity_tier(
        self,
        tradability_score: float,
    ) -> str:
        if tradability_score >= 85:
            return "EXCELLENT"

        if tradability_score >= 72:
            return "GOOD"

        if tradability_score >= 55:
            return "AVERAGE"

        if tradability_score >= 40:
            return "WEAK"

        return "POOR"

    def _notes(
        self,
        *,
        spread_bps: float,
        liquidity_score: float,
        tradability_score: float,
        tier: str,
    ) -> str:
        notes: List[str] = []

        if tier in {"EXCELLENT", "GOOD"}:
            notes.append("Pair is tradable under normal market conditions.")

        if spread_bps > 5:
            notes.append("Spread is elevated.")

        if liquidity_score < 55:
            notes.append("Liquidity score is below preferred threshold.")

        if tradability_score < 55:
            notes.append("Tradability is limited; reduce size or avoid market orders.")

        if not notes:
            notes.append("Liquidity profile is within expected range.")

        return " ".join(notes)

    def _snapshot_from_dict(
        self,
        row: Dict[str, Any],
    ) -> ForexLiquiditySnapshot:
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

        return ForexLiquiditySnapshot(
            liquidity_id=row.get("liquidity_id") or str(uuid.uuid4()),
            tenant_id=row.get("tenant_id"),
            user_id=row.get("user_id"),
            portfolio_id=row.get("portfolio_id"),
            pair=row.get("pair"),
            price=_safe_float(row.get("price")),
            bid=row.get("bid"),
            ask=row.get("ask"),
            spread=_safe_float(row.get("spread")),
            spread_bps=_safe_float(row.get("spread_bps")),
            relative_spread=_safe_float(row.get("relative_spread")),
            estimated_depth_score=_safe_float(row.get("estimated_depth_score")),
            volume_proxy=_safe_float(row.get("volume_proxy")),
            volatility_penalty=_safe_float(row.get("volatility_penalty")),
            liquidity_score=_safe_float(row.get("liquidity_score")),
            tradability_score=_safe_float(row.get("tradability_score")),
            liquidity_tier=row.get("liquidity_tier") or "UNKNOWN",
            provider=row.get("provider") or "unknown",
            notes=row.get("notes") or "",
            asof=asof,
            raw=row.get("raw"),
        )

    def _row_to_snapshot_dict(
        self,
        row: Any,
    ) -> Dict[str, Any]:
        return {
            "liquidity_id": _row_get(row, "liquidity_id"),
            "tenant_id": _row_get(row, "tenant_id"),
            "user_id": _row_get(row, "user_id"),
            "portfolio_id": _row_get(row, "portfolio_id"),
            "pair": _row_get(row, "pair"),
            "price": _row_get(row, "price"),
            "bid": _row_get(row, "bid"),
            "ask": _row_get(row, "ask"),
            "spread": _row_get(row, "spread"),
            "spread_bps": _row_get(row, "spread_bps"),
            "relative_spread": _row_get(row, "relative_spread"),
            "estimated_depth_score": _row_get(row, "estimated_depth_score"),
            "volume_proxy": _row_get(row, "volume_proxy"),
            "volatility_penalty": _row_get(row, "volatility_penalty"),
            "liquidity_score": _row_get(row, "liquidity_score"),
            "tradability_score": _row_get(row, "tradability_score"),
            "liquidity_tier": _row_get(row, "liquidity_tier"),
            "provider": _row_get(row, "provider"),
            "notes": _row_get(row, "notes"),
            "asof": str(_row_get(row, "asof", "")),
            "raw": _row_get(row, "raw_payload"),
        }


def get_forex_liquidity_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
) -> ForexLiquidityEngine:
    return ForexLiquidityEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
        forex_service=forex_service,
    )


def analyze_forex_liquidity(
    pair: str,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_liquidity_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.analyze_pair(
        pair,
        save=save,
    ).to_dict()


def run_forex_liquidity_scan(
    pairs: Optional[List[str]] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
    min_tradability_score: float = 0.0,
    save: bool = True,
) -> Dict[str, Any]:
    engine = get_forex_liquidity_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )
    return engine.scan_pairs(
        pairs=pairs,
        min_tradability_score=min_tradability_score,
        save=save,
    ).to_dict()