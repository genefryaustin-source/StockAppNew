# modules/forex/forex_dealer_positioning_engine.py

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from modules.forex.forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )

    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

except Exception:

    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class DealerPositioningSnapshot:
    snapshot_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str
    price: float

    dealer_long_score: float
    dealer_short_score: float
    dealer_net_positioning: float

    positioning_percentile: float
    positioning_conviction: float

    inventory_pressure: float
    hedge_pressure: float
    liquidity_pressure: float

    dealer_bias: str
    positioning_signal: str

    confidence_score: float

    provider: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class DealerPositioningScan:
    scan_id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_count: int
    bearish_count: int
    neutral_count: int

    average_positioning: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexDealerPositioningEngine:
    """
    Institutional Dealer Positioning Model

    Estimates:
    - Dealer inventory positioning
    - Dealer hedging activity
    - Liquidity provider bias
    - Market-maker exposure
    - Positioning crowding
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        order_flow_engine: Optional[
            ForexOrderFlowEngine
        ] = None,
        liquidity_engine: Optional[
            ForexLiquidityEngine
        ] = None,
    ):

        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db

        self.forex_service = (
            forex_service
            or get_forex_service(
                tenant_id=tenant_id,
                user_id=user_id,
                db=db,
            )
        )

        self.order_flow_engine = (
            order_flow_engine
            or get_forex_order_flow_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.liquidity_engine = (
            liquidity_engine
            or get_forex_liquidity_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

    # =====================================================
    # Table Management
    # =====================================================

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_dealer_positioning_snapshots (
                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                price DOUBLE PRECISION,

                dealer_long_score DOUBLE PRECISION,
                dealer_short_score DOUBLE PRECISION,
                dealer_net_positioning DOUBLE PRECISION,

                positioning_percentile DOUBLE PRECISION,
                positioning_conviction DOUBLE PRECISION,

                inventory_pressure DOUBLE PRECISION,
                hedge_pressure DOUBLE PRECISION,
                liquidity_pressure DOUBLE PRECISION,

                dealer_bias VARCHAR(40),
                positioning_signal VARCHAR(60),

                confidence_score DOUBLE PRECISION,

                provider VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_dealer_positioning_pair
            ON forex_dealer_positioning_snapshots(pair)
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> DealerPositioningSnapshot:

        quote = self.forex_service.get_quote(pair)

        flow = self.order_flow_engine.analyze_pair(
            pair,
            save=False,
        )

        liquidity = self.liquidity_engine.analyze_pair(
            pair,
            save=False,
        )

        imbalance = float(
            getattr(flow, "imbalance_score", 50)
        )

        liquidity_score = float(
            getattr(liquidity, "liquidity_score", 50)
        )

        absorption = float(
            getattr(flow, "absorption_score", 50)
        )

        sweep = float(
            getattr(flow, "sweep_score", 50)
        )

        dealer_long_score = (
            imbalance * 0.45
            + absorption * 0.35
            + liquidity_score * 0.20
        )

        dealer_short_score = (
            (100 - imbalance) * 0.45
            + absorption * 0.35
            + liquidity_score * 0.20
        )

        dealer_net_positioning = (
            dealer_long_score
            - dealer_short_score
        )

        inventory_pressure = min(
            100,
            abs(dealer_net_positioning) * 1.4,
        )

        hedge_pressure = min(
            100,
            sweep * 0.90,
        )

        liquidity_pressure = min(
            100,
            (100 - liquidity_score),
        )

        positioning_percentile = max(
            0,
            min(
                100,
                50 + dealer_net_positioning,
            ),
        )

        positioning_conviction = min(
            100,
            (
                abs(dealer_net_positioning)
                * 0.75
            )
            + (absorption * 0.25),
        )

        confidence = min(
            100,
            (
                positioning_conviction
                + liquidity_score
            )
            / 2,
        )

        if dealer_net_positioning >= 15:
            bias = "LONG"

        elif dealer_net_positioning <= -15:
            bias = "SHORT"

        else:
            bias = "NEUTRAL"

        if positioning_conviction >= 80:

            if bias == "LONG":
                signal = (
                    "DEALER_ACCUMULATION"
                )

            elif bias == "SHORT":
                signal = (
                    "DEALER_DISTRIBUTION"
                )

            else:
                signal = (
                    "DEALER_BALANCED"
                )

        elif hedge_pressure >= 70:
            signal = "HEDGE_REPOSITIONING"

        else:
            signal = "POSITIONING_MONITOR"

        snapshot = DealerPositioningSnapshot(
            snapshot_id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,
            price=float(quote.price),

            dealer_long_score=round(
                dealer_long_score,
                2,
            ),
            dealer_short_score=round(
                dealer_short_score,
                2,
            ),
            dealer_net_positioning=round(
                dealer_net_positioning,
                2,
            ),

            positioning_percentile=round(
                positioning_percentile,
                2,
            ),
            positioning_conviction=round(
                positioning_conviction,
                2,
            ),

            inventory_pressure=round(
                inventory_pressure,
                2,
            ),
            hedge_pressure=round(
                hedge_pressure,
                2,
            ),
            liquidity_pressure=round(
                liquidity_pressure,
                2,
            ),

            dealer_bias=bias,
            positioning_signal=signal,

            confidence_score=round(
                confidence,
                2,
            ),

            provider=getattr(
                quote,
                "provider",
                "unknown",
            ),

            created_at=datetime.now(
                timezone.utc
            ),
        )

        if save:
            self.save_snapshot(snapshot)

        return snapshot

    # =====================================================
    # Scan
    # =====================================================

    def scan_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
    ) -> DealerPositioningScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots: List[
            DealerPositioningSnapshot
        ] = []

        for pair in pairs:

            try:

                snapshots.append(
                    self.analyze_pair(
                        pair,
                        save=save,
                    )
                )

            except Exception:
                continue

        bullish = len(
            [
                x
                for x in snapshots
                if x.dealer_bias == "LONG"
            ]
        )

        bearish = len(
            [
                x
                for x in snapshots
                if x.dealer_bias == "SHORT"
            ]
        )

        neutral = len(
            [
                x
                for x in snapshots
                if x.dealer_bias == "NEUTRAL"
            ]
        )

        avg_positioning = (
            sum(
                x.positioning_conviction
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        avg_confidence = (
            sum(
                x.confidence_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        snapshots = sorted(
            snapshots,
            key=lambda x: (
                x.positioning_conviction
            ),
            reverse=True,
        )

        return DealerPositioningScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),

            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,

            average_positioning=round(
                avg_positioning,
                2,
            ),
            average_confidence=round(
                avg_confidence,
                2,
            ),

            snapshots=[
                x.to_dict()
                for x in snapshots
            ],

            created_at=datetime.now(
                timezone.utc
            ),
        )

    # =====================================================
    # Persistence
    # =====================================================

    def save_snapshot(
        self,
        snapshot: DealerPositioningSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_dealer_positioning_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                price,

                dealer_long_score,
                dealer_short_score,
                dealer_net_positioning,

                positioning_percentile,
                positioning_conviction,

                inventory_pressure,
                hedge_pressure,
                liquidity_pressure,

                dealer_bias,
                positioning_signal,

                confidence_score,

                provider,

                created_at
            )
            VALUES
            (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :price,

                :dealer_long_score,
                :dealer_short_score,
                :dealer_net_positioning,

                :positioning_percentile,
                :positioning_conviction,

                :inventory_pressure,
                :hedge_pressure,
                :liquidity_pressure,

                :dealer_bias,
                :positioning_signal,

                :confidence_score,

                :provider,

                :created_at
            )
            """,
            snapshot.to_dict(),
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # History
    # =====================================================

    def load_snapshots(
        self,
        *,
        pair: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_dealer_positioning_snapshots
        """

        params: Dict[str, Any] = {}

        if pair:

            sql += """
            WHERE pair = :pair
            """

            params["pair"] = pair

        sql += """
        ORDER BY created_at DESC
        LIMIT :limit
        """

        params["limit"] = limit

        rows = (
            self.db.execute(
                sql,
                params,
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]


# =========================================================
# Factory
# =========================================================

def get_forex_dealer_positioning_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexDealerPositioningEngine:

    return ForexDealerPositioningEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )