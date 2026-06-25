# modules/forex/forex_regime_detection_engine.py

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

    from modules.forex.forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
    )

    from modules.forex.forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from modules.forex.forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

    from modules.forex.forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
    )

except Exception:

    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

    from forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class RegimeSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str
    price: float

    trend_score: float
    flow_score: float
    strength_score: float
    correlation_score: float

    volatility_regime_score: float
    liquidity_regime_score: float
    momentum_regime_score: float

    composite_regime_score: float

    market_regime: str
    regime_signal: str

    confidence_score: float

    provider: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()

        return data


@dataclass
class RegimeScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    trending_count: int
    range_count: int
    breakout_count: int
    risk_off_count: int

    average_regime_score: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()

        return data


class ForexRegimeDetectionEngine:

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[
            ForexService
        ] = None,
        market_structure_engine: Optional[
            ForexMarketStructureEngine
        ] = None,
        flow_engine: Optional[
            ForexFlowOfFundsEngine
        ] = None,
        relative_strength_engine: Optional[
            ForexRelativeStrengthEngine
        ] = None,
        correlation_engine: Optional[
            ForexCorrelationEngine
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

        self.market_structure_engine = (
            market_structure_engine
            or get_forex_market_structure_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.flow_engine = (
            flow_engine
            or get_forex_flow_of_funds_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.relative_strength_engine = (
            relative_strength_engine
            or get_forex_relative_strength_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.correlation_engine = (
            correlation_engine
            or get_forex_correlation_engine(
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
            forex_regime_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                price DOUBLE PRECISION,

                trend_score DOUBLE PRECISION,
                flow_score DOUBLE PRECISION,
                strength_score DOUBLE PRECISION,
                correlation_score DOUBLE PRECISION,

                volatility_regime_score DOUBLE PRECISION,
                liquidity_regime_score DOUBLE PRECISION,
                momentum_regime_score DOUBLE PRECISION,

                composite_regime_score DOUBLE PRECISION,

                market_regime VARCHAR(50),
                regime_signal VARCHAR(80),

                confidence_score DOUBLE PRECISION,

                provider VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_regime_pair
            ON forex_regime_snapshots(pair)
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
    ) -> RegimeSnapshot:

        quote = self.forex_service.get_quote(pair)

        structure = (
            self.market_structure_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        flow = (
            self.flow_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        strength = (
            self.relative_strength_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        benchmark_pair = (
            "EUR/USD"
            if pair != "EUR/USD"
            else "GBP/USD"
        )

        correlation = (
            self.correlation_engine
            .analyze_pair_correlation(
                pair,
                benchmark_pair,
                save=False,
            )
        )

        trend_score = float(
            structure.market_structure_score
        )

        flow_score = abs(
            float(
                flow.net_flow_score
            )
        )

        strength_score = float(
            strength.conviction_score
        )

        correlation_score = float(
            correlation.correlation_score
        )

        volatility_regime_score = (
            abs(
                float(
                    structure.breakout_probability
                )
                - float(
                    structure.reversal_probability
                )
            )
        )

        liquidity_regime_score = float(
            structure.liquidity_score
        )

        momentum_regime_score = (
            (
                flow_score
                + strength_score
            )
            / 2
        )

        composite_score = (
            trend_score * 0.30
            + flow_score * 0.20
            + strength_score * 0.20
            + correlation_score * 0.10
            + volatility_regime_score * 0.10
            + liquidity_regime_score * 0.10
        )

        confidence = (
            (
                composite_score
                + momentum_regime_score
            )
            / 2
        )

        if (
            trend_score >= 70
            and momentum_regime_score >= 65
        ):

            market_regime = "TRENDING"
            signal = "TREND_FOLLOWING"

        elif (
            structure.breakout_probability
            >= 80
        ):

            market_regime = "BREAKOUT"

            signal = (
                "VOLATILITY_EXPANSION"
            )

        elif (
            structure.reversal_probability
            >= 80
        ):

            market_regime = "REVERSAL"

            signal = (
                "MEAN_REVERSION"
            )

        elif (
            liquidity_regime_score
            < 40
        ):

            market_regime = "RISK_OFF"

            signal = (
                "DEFENSIVE_POSITIONING"
            )

        else:

            market_regime = "RANGE_BOUND"

            signal = (
                "RANGE_TRADING"
            )

        snapshot = RegimeSnapshot(
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

            flow_score=round(
                flow_score,
                2,
            ),

            strength_score=round(
                strength_score,
                2,
            ),

            correlation_score=round(
                correlation_score,
                2,
            ),

            volatility_regime_score=round(
                volatility_regime_score,
                2,
            ),

            liquidity_regime_score=round(
                liquidity_regime_score,
                2,
            ),

            momentum_regime_score=round(
                momentum_regime_score,
                2,
            ),

            composite_regime_score=round(
                composite_score,
                2,
            ),

            market_regime=market_regime,
            regime_signal=signal,

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
            self.save_snapshot(
                snapshot
            )

        return snapshot

    # =====================================================
    # Scan
    # =====================================================

    def scan_pairs(
        self,
        pairs: Optional[
            List[str]
        ] = None,
        *,
        save: bool = True,
    ) -> RegimeScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots = []

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

        trending = len(
            [
                x for x in snapshots
                if x.market_regime
                == "TRENDING"
            ]
        )

        range_bound = len(
            [
                x for x in snapshots
                if x.market_regime
                == "RANGE_BOUND"
            ]
        )

        breakout = len(
            [
                x for x in snapshots
                if x.market_regime
                == "BREAKOUT"
            ]
        )

        risk_off = len(
            [
                x for x in snapshots
                if x.market_regime
                == "RISK_OFF"
            ]
        )

        avg_score = (
            sum(
                x.composite_regime_score
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
            x.composite_regime_score,
            reverse=True,
        )

        return RegimeScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),

            trending_count=trending,
            range_count=range_bound,
            breakout_count=breakout,
            risk_off_count=risk_off,

            average_regime_score=round(
                avg_score,
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
        snapshot: RegimeSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_regime_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,
                price,

                trend_score,
                flow_score,
                strength_score,
                correlation_score,

                volatility_regime_score,
                liquidity_regime_score,
                momentum_regime_score,

                composite_regime_score,

                market_regime,
                regime_signal,

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
                :flow_score,
                :strength_score,
                :correlation_score,

                :volatility_regime_score,
                :liquidity_regime_score,
                :momentum_regime_score,

                :composite_regime_score,

                :market_regime,
                :regime_signal,

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
        pair: Optional[
            str
        ] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_regime_snapshots
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

def get_forex_regime_detection_engine(
    *,
    tenant_id: Optional[
        str
    ] = None,
    user_id: Optional[
        str
    ] = None,
    portfolio_id: Optional[
        str
    ] = None,
    db: Any = None,
) -> ForexRegimeDetectionEngine:

    return ForexRegimeDetectionEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )