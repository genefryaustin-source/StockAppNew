# modules/forex/forex_intermarket_engine.py

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

    from modules.forex.forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
    )

    from modules.forex.forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

except Exception:

    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

INTERMARKET_ASSETS = [
    "DXY",
    "US10Y",
    "SPX",
    "NDX",
    "GOLD",
    "SILVER",
    "WTI",
    "BRENT",
    "BTC",
]


@dataclass
class IntermarketSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    dollar_alignment_score: float
    rates_alignment_score: float
    equity_alignment_score: float
    commodity_alignment_score: float
    crypto_alignment_score: float

    capital_flow_score: float
    regime_score: float
    currency_strength_score: float

    intermarket_score: float
    confidence_score: float

    intermarket_regime: str
    intermarket_signal: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class IntermarketScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_count: int
    bearish_count: int
    neutral_count: int

    average_score: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexIntermarketEngine:

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        currency_strength_engine: Optional[
            ForexCurrencyStrengthEngine
        ] = None,
        flow_engine: Optional[
            ForexFlowOfFundsEngine
        ] = None,
        regime_engine: Optional[
            ForexRegimeDetectionEngine
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

        self.currency_strength_engine = (
            currency_strength_engine
            or get_forex_currency_strength_engine(
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

        self.regime_engine = (
            regime_engine
            or get_forex_regime_detection_engine(
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
            forex_intermarket_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                dollar_alignment_score DOUBLE PRECISION,
                rates_alignment_score DOUBLE PRECISION,
                equity_alignment_score DOUBLE PRECISION,
                commodity_alignment_score DOUBLE PRECISION,
                crypto_alignment_score DOUBLE PRECISION,

                capital_flow_score DOUBLE PRECISION,
                regime_score DOUBLE PRECISION,
                currency_strength_score DOUBLE PRECISION,

                intermarket_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,

                intermarket_regime VARCHAR(50),
                intermarket_signal VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_intermarket_pair
            ON forex_intermarket_snapshots(pair)
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
    ) -> IntermarketSnapshot:

        flow = self.flow_engine.analyze_pair(
            pair,
            save=False,
        )

        regime = self.regime_engine.analyze_pair(
            pair,
            save=False,
        )

        base_currency = (
            pair.replace("/", "")[:3]
        )

        currency_strength = (
            self.currency_strength_engine
            .analyze_currency(
                base_currency,
                save=False,
            )
        )

        seed = sum(
            ord(c)
            for c in pair.replace("/", "")
        )

        dollar_alignment = (
            40 + (seed % 55)
        )

        rates_alignment = (
            35 + ((seed * 3) % 60)
        )

        equity_alignment = (
            30 + ((seed * 5) % 65)
        )

        commodity_alignment = (
            25 + ((seed * 7) % 70)
        )

        crypto_alignment = (
            20 + ((seed * 11) % 75)
        )

        capital_flow_score = abs(
            flow.net_flow_score
        )

        regime_score = (
            regime.composite_regime_score
        )

        currency_strength_score = (
            currency_strength.global_strength_score
        )

        intermarket_score = (
            dollar_alignment * 0.15
            + rates_alignment * 0.15
            + equity_alignment * 0.10
            + commodity_alignment * 0.10
            + crypto_alignment * 0.05
            + capital_flow_score * 0.15
            + regime_score * 0.15
            + currency_strength_score * 0.15
        )

        confidence = (
            intermarket_score
            + regime_score
        ) / 2

        if intermarket_score >= 80:

            intermarket_regime = (
                "STRONG_ALIGNMENT"
            )

            signal = (
                "HIGH_CONVICTION_SETUP"
            )

        elif intermarket_score >= 65:

            intermarket_regime = (
                "POSITIVE_ALIGNMENT"
            )

            signal = (
                "TREND_CONFIRMATION"
            )

        elif intermarket_score <= 35:

            intermarket_regime = (
                "NEGATIVE_ALIGNMENT"
            )

            signal = (
                "RISK_WARNING"
            )

        else:

            intermarket_regime = (
                "MIXED"
            )

            signal = (
                "MONITOR"
            )

        snapshot = IntermarketSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            dollar_alignment_score=round(
                dollar_alignment,
                2,
            ),

            rates_alignment_score=round(
                rates_alignment,
                2,
            ),

            equity_alignment_score=round(
                equity_alignment,
                2,
            ),

            commodity_alignment_score=round(
                commodity_alignment,
                2,
            ),

            crypto_alignment_score=round(
                crypto_alignment,
                2,
            ),

            capital_flow_score=round(
                capital_flow_score,
                2,
            ),

            regime_score=round(
                regime_score,
                2,
            ),

            currency_strength_score=round(
                currency_strength_score,
                2,
            ),

            intermarket_score=round(
                intermarket_score,
                2,
            ),

            confidence_score=round(
                confidence,
                2,
            ),

            intermarket_regime=
            intermarket_regime,

            intermarket_signal=
            signal,

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
    ) -> IntermarketScan:

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

        bullish = len(
            [
                x for x in snapshots
                if x.intermarket_score >= 65
            ]
        )

        bearish = len(
            [
                x for x in snapshots
                if x.intermarket_score <= 35
            ]
        )

        neutral = len(snapshots) - (
            bullish + bearish
        )

        avg_score = (
            sum(
                x.intermarket_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        snapshots = sorted(
            snapshots,
            key=lambda x:
            x.intermarket_score,
            reverse=True,
        )

        return IntermarketScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(snapshots),

            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,

            average_score=round(
                avg_score,
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
        snapshot: IntermarketSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_intermarket_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                dollar_alignment_score,
                rates_alignment_score,
                equity_alignment_score,
                commodity_alignment_score,
                crypto_alignment_score,

                capital_flow_score,
                regime_score,
                currency_strength_score,

                intermarket_score,
                confidence_score,

                intermarket_regime,
                intermarket_signal,

                created_at
            )
            VALUES
            (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :dollar_alignment_score,
                :rates_alignment_score,
                :equity_alignment_score,
                :commodity_alignment_score,
                :crypto_alignment_score,

                :capital_flow_score,
                :regime_score,
                :currency_strength_score,

                :intermarket_score,
                :confidence_score,

                :intermarket_regime,
                :intermarket_signal,

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
        FROM forex_intermarket_snapshots
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


def get_forex_intermarket_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexIntermarketEngine:

    return ForexIntermarketEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )