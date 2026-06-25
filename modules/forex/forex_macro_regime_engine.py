# modules/forex/forex_macro_regime_engine.py

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

    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )

    from modules.forex.forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from modules.forex.forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )

    from modules.forex.forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )

except Exception:

    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )

    from forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )

    from forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexMacroRegimeSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    macro_score: float
    central_bank_score: float
    sentiment_score: float
    intermarket_score: float

    growth_regime_score: float
    inflation_regime_score: float
    policy_regime_score: float
    risk_regime_score: float

    composite_macro_regime_score: float
    macro_conviction_score: float

    macro_regime: str
    macro_regime_signal: str

    confidence_score: float

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


@dataclass
class ForexMacroRegimeScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    expansion_count: int
    contraction_count: int
    inflationary_count: int
    disinflationary_count: int
    neutral_count: int

    average_regime_score: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


class ForexMacroRegimeEngine:

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
        macro_engine: Optional[
            ForexMacroEngine
        ] = None,
        central_bank_engine: Optional[
            ForexCentralBankEngine
        ] = None,
        sentiment_engine: Optional[
            ForexSentimentEngine
        ] = None,
        intermarket_engine: Optional[
            ForexIntermarketEngine
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

        self.macro_engine = (
            macro_engine
            or get_forex_macro_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.central_bank_engine = (
            central_bank_engine
            or get_forex_central_bank_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.sentiment_engine = (
            sentiment_engine
            or get_forex_sentiment_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.intermarket_engine = (
            intermarket_engine
            or get_forex_intermarket_engine(
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
            forex_macro_regime_snapshots (

                snapshot_id VARCHAR(64)
                PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                macro_score DOUBLE PRECISION,
                central_bank_score DOUBLE PRECISION,
                sentiment_score DOUBLE PRECISION,
                intermarket_score DOUBLE PRECISION,

                growth_regime_score DOUBLE PRECISION,
                inflation_regime_score DOUBLE PRECISION,
                policy_regime_score DOUBLE PRECISION,
                risk_regime_score DOUBLE PRECISION,

                composite_macro_regime_score DOUBLE PRECISION,
                macro_conviction_score DOUBLE PRECISION,

                macro_regime VARCHAR(60),
                macro_regime_signal VARCHAR(100),

                confidence_score DOUBLE PRECISION,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_macro_regime_pair
            ON forex_macro_regime_snapshots(pair)
            """
        )

        if hasattr(
            self.db,
            "commit",
        ):
            self.db.commit()

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> ForexMacroRegimeSnapshot:

        macro = (
            self.macro_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        central_bank = (
            self.central_bank_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        sentiment = (
            self.sentiment_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        intermarket = (
            self.intermarket_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        macro_score = float(
            getattr(
                macro,
                "macro_score",
                50,
            )
        )

        central_bank_score = float(
            getattr(
                central_bank,
                "central_bank_score",
                50,
            )
        )

        sentiment_score = min(
            100.0,
            max(
                0.0,
                50.0
                + float(
                    getattr(
                        sentiment,
                        "net_sentiment_score",
                        0,
                    )
                ),
            ),
        )

        intermarket_score = float(
            getattr(
                intermarket,
                "intermarket_score",
                50,
            )
        )

        growth_regime_score = float(
            getattr(
                macro,
                "growth_differential",
                0,
            )
        )

        growth_regime_score = min(
            100.0,
            max(
                0.0,
                50.0 + growth_regime_score,
            ),
        )

        inflation_regime_score = float(
            getattr(
                macro,
                "inflation_signal",
                50,
            )
        )

        policy_regime_score = (
            central_bank_score
        )

        risk_regime_score = float(
            getattr(
                macro,
                "risk_on_score",
                50,
            )
        )

        composite_score = (
            macro_score * 0.25
            + central_bank_score * 0.25
            + sentiment_score * 0.20
            + intermarket_score * 0.15
            + risk_regime_score * 0.15
        )

        macro_conviction = (
            abs(
                composite_score - 50
            )
            * 1.25
            + (
                policy_regime_score
                * 0.25
            )
        )

        macro_conviction = min(
            100.0,
            max(
                0.0,
                macro_conviction,
            ),
        )

        confidence = (
            composite_score
            + macro_conviction
        ) / 2

        if (
            composite_score >= 75
            and growth_regime_score >= 60
        ):

            regime = "EXPANSIONARY_MACRO"
            signal = "RISK_ON_LONG_BIAS"

        elif (
            composite_score <= 35
            and risk_regime_score <= 45
        ):

            regime = "CONTRACTIONARY_MACRO"
            signal = "RISK_OFF_DEFENSIVE_BIAS"

        elif inflation_regime_score >= 70:

            regime = "INFLATIONARY_MACRO"
            signal = "RATE_SENSITIVE_POSITIONING"

        elif inflation_regime_score <= 35:

            regime = "DISINFLATIONARY_MACRO"
            signal = "LOWER_RATE_EXPECTATION_BIAS"

        else:

            regime = "MIXED_MACRO"
            signal = "MACRO_MONITOR"

        snapshot = ForexMacroRegimeSnapshot(
            snapshot_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            macro_score=round(
                macro_score,
                2,
            ),

            central_bank_score=round(
                central_bank_score,
                2,
            ),

            sentiment_score=round(
                sentiment_score,
                2,
            ),

            intermarket_score=round(
                intermarket_score,
                2,
            ),

            growth_regime_score=round(
                growth_regime_score,
                2,
            ),

            inflation_regime_score=round(
                inflation_regime_score,
                2,
            ),

            policy_regime_score=round(
                policy_regime_score,
                2,
            ),

            risk_regime_score=round(
                risk_regime_score,
                2,
            ),

            composite_macro_regime_score=round(
                composite_score,
                2,
            ),

            macro_conviction_score=round(
                macro_conviction,
                2,
            ),

            macro_regime=regime,
            macro_regime_signal=signal,

            confidence_score=round(
                confidence,
                2,
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
    ) -> ForexMacroRegimeScan:

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

        expansion = len(
            [
                x
                for x in snapshots
                if x.macro_regime
                == "EXPANSIONARY_MACRO"
            ]
        )

        contraction = len(
            [
                x
                for x in snapshots
                if x.macro_regime
                == "CONTRACTIONARY_MACRO"
            ]
        )

        inflationary = len(
            [
                x
                for x in snapshots
                if x.macro_regime
                == "INFLATIONARY_MACRO"
            ]
        )

        disinflationary = len(
            [
                x
                for x in snapshots
                if x.macro_regime
                == "DISINFLATIONARY_MACRO"
            ]
        )

        neutral = len(
            snapshots
        ) - (
            expansion
            + contraction
            + inflationary
            + disinflationary
        )

        avg_regime = (
            sum(
                x.composite_macro_regime_score
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
            x.macro_conviction_score,
            reverse=True,
        )

        return ForexMacroRegimeScan(
            scan_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(
                snapshots
            ),

            expansion_count=
            expansion,

            contraction_count=
            contraction,

            inflationary_count=
            inflationary,

            disinflationary_count=
            disinflationary,

            neutral_count=
            neutral,

            average_regime_score=round(
                avg_regime,
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
        snapshot: ForexMacroRegimeSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_macro_regime_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                macro_score,
                central_bank_score,
                sentiment_score,
                intermarket_score,

                growth_regime_score,
                inflation_regime_score,
                policy_regime_score,
                risk_regime_score,

                composite_macro_regime_score,
                macro_conviction_score,

                macro_regime,
                macro_regime_signal,

                confidence_score,

                created_at
            )
            VALUES
            (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :macro_score,
                :central_bank_score,
                :sentiment_score,
                :intermarket_score,

                :growth_regime_score,
                :inflation_regime_score,
                :policy_regime_score,
                :risk_regime_score,

                :composite_macro_regime_score,
                :macro_conviction_score,

                :macro_regime,
                :macro_regime_signal,

                :confidence_score,

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
        FROM forex_macro_regime_snapshots
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


def get_forex_macro_regime_engine(
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
) -> ForexMacroRegimeEngine:

    return ForexMacroRegimeEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )