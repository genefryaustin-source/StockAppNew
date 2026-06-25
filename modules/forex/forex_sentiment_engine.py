# modules/forex/forex_sentiment_engine.py

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

    from modules.forex.forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from modules.forex.forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
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

    from forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


CURRENCY_SENTIMENT_BASELINE = {
    "USD": 62.0,
    "EUR": 54.0,
    "GBP": 57.0,
    "JPY": 45.0,
    "CHF": 52.0,
    "AUD": 60.0,
    "CAD": 58.0,
    "NZD": 61.0,
}


@dataclass
class ForexSentimentSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    base_currency: str
    quote_currency: str

    base_sentiment_score: float
    quote_sentiment_score: float

    net_sentiment_score: float
    news_sentiment_score: float
    policy_sentiment_score: float
    flow_sentiment_score: float
    strength_sentiment_score: float

    sentiment_momentum_score: float
    sentiment_conviction_score: float

    sentiment_regime: str
    sentiment_signal: str

    confidence_score: float

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


@dataclass
class ForexSentimentScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_count: int
    bearish_count: int
    neutral_count: int

    average_sentiment: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


class ForexSentimentEngine:

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
        currency_strength_engine: Optional[
            ForexCurrencyStrengthEngine
        ] = None,
        central_bank_engine: Optional[
            ForexCentralBankEngine
        ] = None,
        flow_engine: Optional[
            ForexFlowOfFundsEngine
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

        self.central_bank_engine = (
            central_bank_engine
            or get_forex_central_bank_engine(
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

    # =====================================================
    # Database
    # =====================================================

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS
            forex_sentiment_snapshots (

                snapshot_id VARCHAR(64)
                PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                base_currency VARCHAR(10),
                quote_currency VARCHAR(10),

                base_sentiment_score DOUBLE PRECISION,
                quote_sentiment_score DOUBLE PRECISION,

                net_sentiment_score DOUBLE PRECISION,
                news_sentiment_score DOUBLE PRECISION,
                policy_sentiment_score DOUBLE PRECISION,
                flow_sentiment_score DOUBLE PRECISION,
                strength_sentiment_score DOUBLE PRECISION,

                sentiment_momentum_score DOUBLE PRECISION,
                sentiment_conviction_score DOUBLE PRECISION,

                sentiment_regime VARCHAR(50),
                sentiment_signal VARCHAR(100),

                confidence_score DOUBLE PRECISION,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_sentiment_pair
            ON forex_sentiment_snapshots(pair)
            """
        )

        if hasattr(
            self.db,
            "commit",
        ):
            self.db.commit()

    # =====================================================
    # Helpers
    # =====================================================

    def _split_pair(
        self,
        pair: str,
    ) -> tuple[str, str]:

        clean = (
            pair.replace("/", "")
            .replace("-", "")
            .upper()
        )

        return (
            clean[:3],
            clean[3:6],
        )

    def _baseline_sentiment(
        self,
        currency: str,
    ) -> float:

        return float(
            CURRENCY_SENTIMENT_BASELINE.get(
                currency,
                50.0,
            )
        )

    def _synthetic_news_score(
        self,
        pair: str,
    ) -> float:

        seed = sum(
            ord(c)
            for c in pair.replace("/", "").upper()
        )

        return float(
            35 + (seed % 55)
        )

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> ForexSentimentSnapshot:

        base, quote = self._split_pair(
            pair
        )

        base_baseline = (
            self._baseline_sentiment(
                base
            )
        )

        quote_baseline = (
            self._baseline_sentiment(
                quote
            )
        )

        strength = (
            self.currency_strength_engine
            .analyze_currency(
                base,
                save=False,
            )
        )

        policy = (
            self.central_bank_engine
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

        strength_sentiment = float(
            strength.global_strength_score
        )

        policy_sentiment = float(
            policy.central_bank_score
        )

        flow_sentiment = min(
            100.0,
            max(
                0.0,
                50.0 + float(
                    flow.net_flow_score
                ),
            ),
        )

        news_sentiment = (
            self._synthetic_news_score(
                pair
            )
        )

        base_sentiment = (
            base_baseline * 0.25
            + strength_sentiment * 0.30
            + policy_sentiment * 0.25
            + news_sentiment * 0.20
        )

        quote_sentiment = (
            quote_baseline * 0.45
            + (100 - policy_sentiment) * 0.25
            + (100 - flow_sentiment) * 0.15
            + (100 - news_sentiment) * 0.15
        )

        net_sentiment = (
            base_sentiment
            - quote_sentiment
        )

        sentiment_momentum = (
            strength_sentiment * 0.35
            + flow_sentiment * 0.35
            + news_sentiment * 0.30
        )

        sentiment_conviction = (
            abs(net_sentiment) * 0.55
            + sentiment_momentum * 0.45
        )

        confidence = (
            sentiment_conviction
            + policy_sentiment
            + strength_sentiment
        ) / 3

        if net_sentiment >= 15:

            regime = "BULLISH_SENTIMENT"
            signal = "LONG_SENTIMENT_BIAS"

        elif net_sentiment <= -15:

            regime = "BEARISH_SENTIMENT"
            signal = "SHORT_SENTIMENT_BIAS"

        else:

            regime = "NEUTRAL_SENTIMENT"
            signal = "SENTIMENT_MONITOR"

        if (
            sentiment_conviction >= 80
            and regime == "BULLISH_SENTIMENT"
        ):

            signal = "HIGH_CONVICTION_LONG_SENTIMENT"

        elif (
            sentiment_conviction >= 80
            and regime == "BEARISH_SENTIMENT"
        ):

            signal = "HIGH_CONVICTION_SHORT_SENTIMENT"

        snapshot = ForexSentimentSnapshot(
            snapshot_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            base_currency=base,
            quote_currency=quote,

            base_sentiment_score=round(
                base_sentiment,
                2,
            ),

            quote_sentiment_score=round(
                quote_sentiment,
                2,
            ),

            net_sentiment_score=round(
                net_sentiment,
                2,
            ),

            news_sentiment_score=round(
                news_sentiment,
                2,
            ),

            policy_sentiment_score=round(
                policy_sentiment,
                2,
            ),

            flow_sentiment_score=round(
                flow_sentiment,
                2,
            ),

            strength_sentiment_score=round(
                strength_sentiment,
                2,
            ),

            sentiment_momentum_score=round(
                sentiment_momentum,
                2,
            ),

            sentiment_conviction_score=round(
                sentiment_conviction,
                2,
            ),

            sentiment_regime=regime,
            sentiment_signal=signal,

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
    ) -> ForexSentimentScan:

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
                x
                for x in snapshots
                if x.sentiment_regime
                == "BULLISH_SENTIMENT"
            ]
        )

        bearish = len(
            [
                x
                for x in snapshots
                if x.sentiment_regime
                == "BEARISH_SENTIMENT"
            ]
        )

        neutral = len(
            snapshots
        ) - bullish - bearish

        avg_sentiment = (
            sum(
                x.net_sentiment_score
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
            x.sentiment_conviction_score,
            reverse=True,
        )

        return ForexSentimentScan(
            scan_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(
                snapshots
            ),

            bullish_count=
            bullish,

            bearish_count=
            bearish,

            neutral_count=
            neutral,

            average_sentiment=round(
                avg_sentiment,
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
        snapshot: ForexSentimentSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_sentiment_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                base_currency,
                quote_currency,

                base_sentiment_score,
                quote_sentiment_score,

                net_sentiment_score,
                news_sentiment_score,
                policy_sentiment_score,
                flow_sentiment_score,
                strength_sentiment_score,

                sentiment_momentum_score,
                sentiment_conviction_score,

                sentiment_regime,
                sentiment_signal,

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

                :base_currency,
                :quote_currency,

                :base_sentiment_score,
                :quote_sentiment_score,

                :net_sentiment_score,
                :news_sentiment_score,
                :policy_sentiment_score,
                :flow_sentiment_score,
                :strength_sentiment_score,

                :sentiment_momentum_score,
                :sentiment_conviction_score,

                :sentiment_regime,
                :sentiment_signal,

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
        FROM forex_sentiment_snapshots
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


def get_forex_sentiment_engine(
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
) -> ForexSentimentEngine:

    return ForexSentimentEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )