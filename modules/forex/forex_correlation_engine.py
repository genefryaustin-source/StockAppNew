# modules/forex/forex_correlation_engine.py

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

    from modules.forex.forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

    from modules.forex.forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from modules.forex.forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
    )

except Exception:

    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from forex_market_structure_engine import (
        ForexMarketStructureEngine,
        get_forex_market_structure_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class CorrelationSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_a: str
    pair_b: str

    correlation_score: float
    inverse_correlation_score: float

    strength_score: float
    stability_score: float

    relative_strength_alignment: float
    capital_flow_alignment: float
    structure_alignment: float

    correlation_regime: str
    correlation_signal: str

    confidence_score: float

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()

        return data


@dataclass
class CorrelationScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    positive_count: int
    negative_count: int
    neutral_count: int

    average_correlation: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()

        return data


class ForexCorrelationEngine:

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        relative_strength_engine: Optional[
            ForexRelativeStrengthEngine
        ] = None,
        flow_engine: Optional[
            ForexFlowOfFundsEngine
        ] = None,
        structure_engine: Optional[
            ForexMarketStructureEngine
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

        self.relative_strength_engine = (
            relative_strength_engine
            or get_forex_relative_strength_engine(
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

        self.structure_engine = (
            structure_engine
            or get_forex_market_structure_engine(
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
            forex_correlation_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair_a VARCHAR(20),
                pair_b VARCHAR(20),

                correlation_score DOUBLE PRECISION,
                inverse_correlation_score DOUBLE PRECISION,

                strength_score DOUBLE PRECISION,
                stability_score DOUBLE PRECISION,

                relative_strength_alignment DOUBLE PRECISION,
                capital_flow_alignment DOUBLE PRECISION,
                structure_alignment DOUBLE PRECISION,

                correlation_regime VARCHAR(50),
                correlation_signal VARCHAR(60),

                confidence_score DOUBLE PRECISION,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_correlation_pairs
            ON forex_correlation_snapshots(
                pair_a,
                pair_b
            )
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair_correlation(
        self,
        pair_a: str,
        pair_b: str,
        *,
        save: bool = True,
    ) -> CorrelationSnapshot:

        rs_a = (
            self.relative_strength_engine
            .analyze_pair(
                pair_a,
                save=False,
            )
        )

        rs_b = (
            self.relative_strength_engine
            .analyze_pair(
                pair_b,
                save=False,
            )
        )

        flow_a = self.flow_engine.analyze_pair(
            pair_a,
            save=False,
        )

        flow_b = self.flow_engine.analyze_pair(
            pair_b,
            save=False,
        )

        structure_a = (
            self.structure_engine.analyze_pair(
                pair_a,
                save=False,
            )
        )

        structure_b = (
            self.structure_engine.analyze_pair(
                pair_b,
                save=False,
            )
        )

        rs_alignment = max(
            0,
            100
            - abs(
                rs_a.relative_strength_score
                - rs_b.relative_strength_score
            ),
        )

        flow_alignment = max(
            0,
            100
            - abs(
                flow_a.net_flow_score
                - flow_b.net_flow_score
            ),
        )

        structure_alignment = max(
            0,
            100
            - abs(
                structure_a.market_structure_score
                - structure_b.market_structure_score
            ),
        )

        correlation_score = (
            rs_alignment * 0.40
            + flow_alignment * 0.30
            + structure_alignment * 0.30
        )

        inverse_score = (
            100 - correlation_score
        )

        strength_score = (
            correlation_score
        )

        stability_score = (
            (
                rs_alignment
                + structure_alignment
            )
            / 2
        )

        confidence = (
            (
                strength_score
                + stability_score
            )
            / 2
        )

        if correlation_score >= 75:

            regime = "POSITIVE_CORRELATION"
            signal = "PAIR_CONFIRMATION"

        elif correlation_score <= 35:

            regime = "NEGATIVE_CORRELATION"
            signal = "DIVERGENCE_SETUP"

        else:

            regime = "NEUTRAL"
            signal = "MONITOR"

        snapshot = CorrelationSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_a=pair_a,
            pair_b=pair_b,

            correlation_score=round(
                correlation_score,
                2,
            ),

            inverse_correlation_score=round(
                inverse_score,
                2,
            ),

            strength_score=round(
                strength_score,
                2,
            ),

            stability_score=round(
                stability_score,
                2,
            ),

            relative_strength_alignment=round(
                rs_alignment,
                2,
            ),

            capital_flow_alignment=round(
                flow_alignment,
                2,
            ),

            structure_alignment=round(
                structure_alignment,
                2,
            ),

            correlation_regime=regime,
            correlation_signal=signal,

            confidence_score=round(
                confidence,
                2,
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

    def scan_correlations(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
    ) -> CorrelationScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots = []

        for i in range(len(pairs)):

            for j in range(i + 1, len(pairs)):

                try:

                    snapshots.append(
                        self.analyze_pair_correlation(
                            pairs[i],
                            pairs[j],
                            save=save,
                        )
                    )

                except Exception:
                    continue

        positive = len(
            [
                x for x in snapshots
                if x.correlation_regime
                == "POSITIVE_CORRELATION"
            ]
        )

        negative = len(
            [
                x for x in snapshots
                if x.correlation_regime
                == "NEGATIVE_CORRELATION"
            ]
        )

        neutral = len(
            [
                x for x in snapshots
                if x.correlation_regime
                == "NEUTRAL"
            ]
        )

        avg_corr = (
            sum(
                x.correlation_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        avg_conf = (
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
            x.correlation_score,
            reverse=True,
        )

        return CorrelationScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(snapshots),

            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,

            average_correlation=round(
                avg_corr,
                2,
            ),

            average_confidence=round(
                avg_conf,
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
        snapshot: CorrelationSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_correlation_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair_a,
                pair_b,

                correlation_score,
                inverse_correlation_score,

                strength_score,
                stability_score,

                relative_strength_alignment,
                capital_flow_alignment,
                structure_alignment,

                correlation_regime,
                correlation_signal,

                confidence_score,

                created_at
            )
            VALUES
            (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair_a,
                :pair_b,

                :correlation_score,
                :inverse_correlation_score,

                :strength_score,
                :stability_score,

                :relative_strength_alignment,
                :capital_flow_alignment,
                :structure_alignment,

                :correlation_regime,
                :correlation_signal,

                :confidence_score,

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
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        self.ensure_tables()

        rows = (
            self.db.execute(
                """
                SELECT *
                FROM forex_correlation_snapshots
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {
                    "limit": limit,
                },
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

def get_forex_correlation_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexCorrelationEngine:

    return ForexCorrelationEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )