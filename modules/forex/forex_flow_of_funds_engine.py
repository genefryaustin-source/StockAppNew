# modules/forex/forex_flow_of_funds_engine.py

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

    from modules.forex.forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
    )

    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
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

    from forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
    )

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class FlowOfFundsSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str
    price: float

    institutional_inflow_score: float
    institutional_outflow_score: float
    net_flow_score: float

    dealer_flow_score: float
    macro_flow_score: float
    liquidity_flow_score: float
    speculative_flow_score: float

    capital_rotation_score: float
    capital_momentum_score: float

    flow_direction: str
    flow_signal: str

    confidence_score: float

    provider: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class FlowOfFundsScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    inflow_count: int
    outflow_count: int
    neutral_count: int

    average_net_flow: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexFlowOfFundsEngine:
    """
    Institutional Flow Of Funds Intelligence

    Models:

    - Institutional capital rotation
    - Dealer capital movement
    - Macro capital allocation
    - Speculative flow activity
    - Liquidity migration
    - Net capital flow direction
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
        dealer_engine: Optional[
            ForexDealerPositioningEngine
        ] = None,
        macro_engine: Optional[
            ForexMacroEngine
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

        self.dealer_engine = (
            dealer_engine
            or get_forex_dealer_positioning_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.macro_engine = (
            macro_engine
            or get_forex_macro_engine(
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
    # Database
    # =====================================================

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS
            forex_flow_of_funds_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                price DOUBLE PRECISION,

                institutional_inflow_score DOUBLE PRECISION,
                institutional_outflow_score DOUBLE PRECISION,
                net_flow_score DOUBLE PRECISION,

                dealer_flow_score DOUBLE PRECISION,
                macro_flow_score DOUBLE PRECISION,
                liquidity_flow_score DOUBLE PRECISION,
                speculative_flow_score DOUBLE PRECISION,

                capital_rotation_score DOUBLE PRECISION,
                capital_momentum_score DOUBLE PRECISION,

                flow_direction VARCHAR(40),
                flow_signal VARCHAR(60),

                confidence_score DOUBLE PRECISION,

                provider VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_flow_of_funds_pair
            ON forex_flow_of_funds_snapshots(pair)
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
    ) -> FlowOfFundsSnapshot:

        quote = self.forex_service.get_quote(pair)

        flow = self.order_flow_engine.analyze_pair(
            pair,
            save=False,
        )

        dealer = self.dealer_engine.analyze_pair(
            pair,
            save=False,
        )

        macro = self.macro_engine.analyze_pair(
            pair,
            save=False,
        )

        liquidity = self.liquidity_engine.analyze_pair(
            pair,
            save=False,
        )

        dealer_flow_score = (
            float(
                dealer.positioning_conviction
            )
        )

        macro_flow_score = (
            float(
                macro.macro_score
            )
        )

        liquidity_flow_score = (
            float(
                liquidity.liquidity_score
            )
        )

        speculative_flow_score = (
            float(
                flow.imbalance_score
            )
        )

        institutional_inflow_score = (
            dealer_flow_score * 0.35
            + macro_flow_score * 0.30
            + liquidity_flow_score * 0.15
            + speculative_flow_score * 0.20
        )

        institutional_outflow_score = (
            (100 - dealer_flow_score)
            * 0.35
            + (100 - macro_flow_score)
            * 0.30
            + (100 - liquidity_flow_score)
            * 0.15
            + (100 - speculative_flow_score)
            * 0.20
        )

        net_flow_score = (
            institutional_inflow_score
            - institutional_outflow_score
        )

        capital_rotation_score = (
            abs(net_flow_score)
        )

        capital_momentum_score = (
            (
                speculative_flow_score
                + dealer_flow_score
            )
            / 2
        )

        confidence = (
            (
                dealer_flow_score
                + macro_flow_score
                + liquidity_flow_score
            )
            / 3
        )

        if net_flow_score >= 15:

            direction = "INFLOW"

        elif net_flow_score <= -15:

            direction = "OUTFLOW"

        else:

            direction = "NEUTRAL"

        if capital_rotation_score >= 70:

            if direction == "INFLOW":
                signal = (
                    "INSTITUTIONAL_ACCUMULATION"
                )

            elif direction == "OUTFLOW":
                signal = (
                    "INSTITUTIONAL_DISTRIBUTION"
                )

            else:
                signal = (
                    "FLOW_TRANSITION"
                )

        elif capital_momentum_score >= 75:

            signal = (
                "MOMENTUM_CAPITAL_ROTATION"
            )

        else:

            signal = "FLOW_MONITOR"

        snapshot = FlowOfFundsSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,
            price=float(quote.price),

            institutional_inflow_score=round(
                institutional_inflow_score,
                2,
            ),

            institutional_outflow_score=round(
                institutional_outflow_score,
                2,
            ),

            net_flow_score=round(
                net_flow_score,
                2,
            ),

            dealer_flow_score=round(
                dealer_flow_score,
                2,
            ),

            macro_flow_score=round(
                macro_flow_score,
                2,
            ),

            liquidity_flow_score=round(
                liquidity_flow_score,
                2,
            ),

            speculative_flow_score=round(
                speculative_flow_score,
                2,
            ),

            capital_rotation_score=round(
                capital_rotation_score,
                2,
            ),

            capital_momentum_score=round(
                capital_momentum_score,
                2,
            ),

            flow_direction=direction,
            flow_signal=signal,

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
    ) -> FlowOfFundsScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots: List[
            FlowOfFundsSnapshot
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

        inflow = len(
            [
                x
                for x in snapshots
                if x.flow_direction
                == "INFLOW"
            ]
        )

        outflow = len(
            [
                x
                for x in snapshots
                if x.flow_direction
                == "OUTFLOW"
            ]
        )

        neutral = len(
            [
                x
                for x in snapshots
                if x.flow_direction
                == "NEUTRAL"
            ]
        )

        avg_flow = (
            sum(
                x.net_flow_score
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
            abs(
                x.net_flow_score
            ),
            reverse=True,
        )

        return FlowOfFundsScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),

            inflow_count=inflow,
            outflow_count=outflow,
            neutral_count=neutral,

            average_net_flow=round(
                avg_flow,
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
        snapshot: FlowOfFundsSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_flow_of_funds_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,
                price,

                institutional_inflow_score,
                institutional_outflow_score,
                net_flow_score,

                dealer_flow_score,
                macro_flow_score,
                liquidity_flow_score,
                speculative_flow_score,

                capital_rotation_score,
                capital_momentum_score,

                flow_direction,
                flow_signal,

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

                :institutional_inflow_score,
                :institutional_outflow_score,
                :net_flow_score,

                :dealer_flow_score,
                :macro_flow_score,
                :liquidity_flow_score,
                :speculative_flow_score,

                :capital_rotation_score,
                :capital_momentum_score,

                :flow_direction,
                :flow_signal,

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
        FROM forex_flow_of_funds_snapshots
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


# =====================================================
# Factory
# =====================================================

def get_forex_flow_of_funds_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexFlowOfFundsEngine:

    return ForexFlowOfFundsEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )