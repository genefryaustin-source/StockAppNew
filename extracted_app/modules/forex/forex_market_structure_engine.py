# modules/forex/forex_market_structure_engine.py

from __future__ import annotations

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

    from modules.forex.forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
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

    from forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class MarketStructureSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str
    price: float

    trend_score: float
    liquidity_score: float
    positioning_score: float

    market_structure_score: float
    structure_strength: float

    breakout_probability: float
    reversal_probability: float

    support_strength: float
    resistance_strength: float

    structure_regime: str
    structure_signal: str

    confidence_score: float

    provider: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class MarketStructureScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_count: int
    bearish_count: int
    range_count: int

    average_structure_score: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = data["created_at"].isoformat()
        return data


class ForexMarketStructureEngine:
    """
    Institutional Forex Market Structure Engine

    Analyzes:

    - Trend state
    - Liquidity state
    - Dealer positioning state
    - Breakout risk
    - Reversal risk
    - Support / resistance quality
    - Regime classification
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
        dealer_engine: Optional[
            ForexDealerPositioningEngine
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

        self.dealer_engine = (
            dealer_engine
            or get_forex_dealer_positioning_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

    # =========================================================
    # Database
    # =========================================================

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS
            forex_market_structure_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                price DOUBLE PRECISION,

                trend_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                positioning_score DOUBLE PRECISION,

                market_structure_score DOUBLE PRECISION,
                structure_strength DOUBLE PRECISION,

                breakout_probability DOUBLE PRECISION,
                reversal_probability DOUBLE PRECISION,

                support_strength DOUBLE PRECISION,
                resistance_strength DOUBLE PRECISION,

                structure_regime VARCHAR(50),
                structure_signal VARCHAR(60),

                confidence_score DOUBLE PRECISION,

                provider VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_market_structure_pair
            ON forex_market_structure_snapshots(pair)
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =========================================================
    # Pair Analysis
    # =========================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> MarketStructureSnapshot:

        quote = self.forex_service.get_quote(pair)

        flow = self.order_flow_engine.analyze_pair(
            pair,
            save=False,
        )

        liquidity = self.liquidity_engine.analyze_pair(
            pair,
            save=False,
        )

        positioning = self.dealer_engine.analyze_pair(
            pair,
            save=False,
        )

        trend_score = (
            float(flow.imbalance_score)
        )

        liquidity_score = (
            float(liquidity.liquidity_score)
        )

        positioning_score = (
            float(
                positioning.positioning_conviction
            )
        )

        market_structure_score = (
            trend_score * 0.40
            + liquidity_score * 0.30
            + positioning_score * 0.30
        )

        structure_strength = (
            market_structure_score
        )

        breakout_probability = min(
            100,
            (
                float(flow.sweep_score)
                * 0.60
            )
            + (
                liquidity_score
                * 0.40
            ),
        )

        reversal_probability = min(
            100,
            (
                float(
                    flow.absorption_score
                )
                * 0.70
            )
            + (
                abs(
                    positioning.dealer_net_positioning
                )
                * 0.30
            ),
        )

        support_strength = (
            liquidity_score * 0.60
            + float(
                flow.absorption_score
            ) * 0.40
        )

        resistance_strength = (
            liquidity_score * 0.50
            + float(
                flow.sweep_score
            ) * 0.50
        )

        if market_structure_score >= 70:

            if trend_score >= 55:
                regime = "BULL_TREND"
                signal = "TREND_CONTINUATION"

            else:
                regime = "BEAR_TREND"
                signal = "TREND_CONTINUATION"

        elif breakout_probability >= 75:

            regime = "BREAKOUT_SETUP"
            signal = "BREAKOUT_RISK"

        elif reversal_probability >= 75:

            regime = "REVERSAL_SETUP"
            signal = "REVERSAL_RISK"

        else:

            regime = "RANGE_BOUND"
            signal = "MEAN_REVERSION"

        confidence = min(
            100,
            (
                structure_strength
                + breakout_probability
                + reversal_probability
            )
            / 3,
        )

        snapshot = MarketStructureSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            price=float(
                quote.price
            ),

            trend_score=round(
                trend_score,
                2,
            ),

            liquidity_score=round(
                liquidity_score,
                2,
            ),

            positioning_score=round(
                positioning_score,
                2,
            ),

            market_structure_score=round(
                market_structure_score,
                2,
            ),

            structure_strength=round(
                structure_strength,
                2,
            ),

            breakout_probability=round(
                breakout_probability,
                2,
            ),

            reversal_probability=round(
                reversal_probability,
                2,
            ),

            support_strength=round(
                support_strength,
                2,
            ),

            resistance_strength=round(
                resistance_strength,
                2,
            ),

            structure_regime=regime,
            structure_signal=signal,

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

    # =========================================================
    # Scan
    # =========================================================

    def scan_pairs(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
    ) -> MarketStructureScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots: List[
            MarketStructureSnapshot
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
                if x.structure_regime
                == "BULL_TREND"
            ]
        )

        bearish = len(
            [
                x
                for x in snapshots
                if x.structure_regime
                == "BEAR_TREND"
            ]
        )

        range_count = len(
            [
                x
                for x in snapshots
                if x.structure_regime
                == "RANGE_BOUND"
            ]
        )

        avg_structure = (
            sum(
                x.market_structure_score
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
            key=lambda x:
            x.market_structure_score,
            reverse=True,
        )

        return MarketStructureScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),

            bullish_count=bullish,
            bearish_count=bearish,
            range_count=range_count,

            average_structure_score=round(
                avg_structure,
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

    # =========================================================
    # Persistence
    # =========================================================

    def save_snapshot(
        self,
        snapshot: MarketStructureSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_market_structure_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,
                price,

                trend_score,
                liquidity_score,
                positioning_score,

                market_structure_score,
                structure_strength,

                breakout_probability,
                reversal_probability,

                support_strength,
                resistance_strength,

                structure_regime,
                structure_signal,

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

                :trend_score,
                :liquidity_score,
                :positioning_score,

                :market_structure_score,
                :structure_strength,

                :breakout_probability,
                :reversal_probability,

                :support_strength,
                :resistance_strength,

                :structure_regime,
                :structure_signal,

                :confidence_score,

                :provider,

                :created_at
            )
            """,
            snapshot.to_dict(),
        )

        if hasattr(
            self.db,
            "commit",
        ):
            self.db.commit()

    # =========================================================
    # History
    # =========================================================

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
        FROM forex_market_structure_snapshots
        """

        params: Dict[
            str,
            Any,
        ] = {}

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

def get_forex_market_structure_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexMarketStructureEngine:

    return ForexMarketStructureEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )