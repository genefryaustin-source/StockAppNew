# modules/forex/forex_central_bank_engine.py

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

    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
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

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

CENTRAL_BANKS = {
    "USD": {
        "bank": "Federal Reserve",
        "rate": 5.25,
        "hawkish": 75,
    },
    "EUR": {
        "bank": "European Central Bank",
        "rate": 3.75,
        "hawkish": 55,
    },
    "GBP": {
        "bank": "Bank of England",
        "rate": 5.00,
        "hawkish": 70,
    },
    "JPY": {
        "bank": "Bank of Japan",
        "rate": 0.25,
        "hawkish": 20,
    },
    "CHF": {
        "bank": "Swiss National Bank",
        "rate": 1.50,
        "hawkish": 45,
    },
    "AUD": {
        "bank": "Reserve Bank of Australia",
        "rate": 4.35,
        "hawkish": 65,
    },
    "CAD": {
        "bank": "Bank of Canada",
        "rate": 4.75,
        "hawkish": 68,
    },
    "NZD": {
        "bank": "Reserve Bank of New Zealand",
        "rate": 5.50,
        "hawkish": 80,
    },
}


@dataclass
class CentralBankSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    base_currency: str
    quote_currency: str

    base_bank: str
    quote_bank: str

    base_rate: float
    quote_rate: float

    base_hawkish_score: float
    quote_hawkish_score: float

    policy_divergence_score: float
    rate_differential_score: float
    currency_strength_score: float
    macro_score: float

    central_bank_score: float
    confidence_score: float

    policy_regime: str
    policy_signal: str

    created_at: datetime

    def to_dict(self):

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


@dataclass
class CentralBankScan:

    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_policy_count: int
    bearish_policy_count: int
    neutral_policy_count: int

    average_score: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self):

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


class ForexCentralBankEngine:

    def __init__(
        self,
        *,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
        db=None,
        forex_service=None,
        currency_strength_engine=None,
        macro_engine=None,
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

        self.macro_engine = (
            macro_engine
            or get_forex_macro_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

    # =====================================================
    # Database
    # =====================================================

    def ensure_tables(self):

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS
            forex_central_bank_snapshots (

                snapshot_id VARCHAR(64)
                PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                base_currency VARCHAR(10),
                quote_currency VARCHAR(10),

                base_bank VARCHAR(100),
                quote_bank VARCHAR(100),

                base_rate DOUBLE PRECISION,
                quote_rate DOUBLE PRECISION,

                base_hawkish_score DOUBLE PRECISION,
                quote_hawkish_score DOUBLE PRECISION,

                policy_divergence_score DOUBLE PRECISION,
                rate_differential_score DOUBLE PRECISION,

                currency_strength_score DOUBLE PRECISION,
                macro_score DOUBLE PRECISION,

                central_bank_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,

                policy_regime VARCHAR(50),
                policy_signal VARCHAR(100),

                created_at TIMESTAMP
            )
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
    ) -> CentralBankSnapshot:

        clean = (
            pair.replace("/", "")
            .upper()
        )

        base = clean[:3]
        quote = clean[3:6]

        base_data = CENTRAL_BANKS.get(
            base,
            {},
        )

        quote_data = CENTRAL_BANKS.get(
            quote,
            {},
        )

        base_rate = float(
            base_data.get(
                "rate",
                3.0,
            )
        )

        quote_rate = float(
            quote_data.get(
                "rate",
                3.0,
            )
        )

        base_hawkish = float(
            base_data.get(
                "hawkish",
                50,
            )
        )

        quote_hawkish = float(
            quote_data.get(
                "hawkish",
                50,
            )
        )

        policy_divergence = min(
            100,
            abs(
                base_hawkish
                - quote_hawkish
            ),
        )

        rate_diff_score = min(
            100,
            abs(
                base_rate
                - quote_rate
            ) * 15,
        )

        currency_strength = (
            self.currency_strength_engine
            .analyze_currency(
                base,
                save=False,
            )
        )

        macro = (
            self.macro_engine
            .analyze_pair(
                pair,
                save=False,
            )
        )

        strength_score = (
            currency_strength
            .global_strength_score
        )

        macro_score = (
            macro.macro_score
        )

        cb_score = (
            policy_divergence * 0.30
            + rate_diff_score * 0.30
            + strength_score * 0.20
            + macro_score * 0.20
        )

        confidence = (
            cb_score
            + policy_divergence
        ) / 2

        if (
            base_hawkish
            > quote_hawkish + 15
        ):

            regime = "HAWKISH_BASE"

            signal = (
                "LONG_BASE_CURRENCY"
            )

        elif (
            quote_hawkish
            > base_hawkish + 15
        ):

            regime = "HAWKISH_QUOTE"

            signal = (
                "SHORT_BASE_CURRENCY"
            )

        else:

            regime = (
                "POLICY_CONVERGENCE"
            )

            signal = (
                "NEUTRAL"
            )

        snapshot = (
            CentralBankSnapshot(
                snapshot_id=str(
                    uuid.uuid4()
                ),

                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,

                pair=pair,

                base_currency=base,
                quote_currency=quote,

                base_bank=base_data.get(
                    "bank",
                    "Unknown",
                ),

                quote_bank=quote_data.get(
                    "bank",
                    "Unknown",
                ),

                base_rate=round(
                    base_rate,
                    2,
                ),

                quote_rate=round(
                    quote_rate,
                    2,
                ),

                base_hawkish_score=round(
                    base_hawkish,
                    2,
                ),

                quote_hawkish_score=round(
                    quote_hawkish,
                    2,
                ),

                policy_divergence_score=round(
                    policy_divergence,
                    2,
                ),

                rate_differential_score=round(
                    rate_diff_score,
                    2,
                ),

                currency_strength_score=round(
                    strength_score,
                    2,
                ),

                macro_score=round(
                    macro_score,
                    2,
                ),

                central_bank_score=round(
                    cb_score,
                    2,
                ),

                confidence_score=round(
                    confidence,
                    2,
                ),

                policy_regime=regime,
                policy_signal=signal,

                created_at=datetime.now(
                    timezone.utc
                ),
            )
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
        pairs=None,
        *,
        save=True,
    ):

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
                if x.policy_regime
                == "HAWKISH_BASE"
            ]
        )

        bearish = len(
            [
                x
                for x in snapshots
                if x.policy_regime
                == "HAWKISH_QUOTE"
            ]
        )

        neutral = len(
            snapshots
        ) - bullish - bearish

        avg_score = (
            sum(
                x.central_bank_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        snapshots = sorted(
            snapshots,
            key=lambda x:
            x.central_bank_score,
            reverse=True,
        )

        return CentralBankScan(
            scan_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(
                snapshots
            ),

            bullish_policy_count=
            bullish,

            bearish_policy_count=
            bearish,

            neutral_policy_count=
            neutral,

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
        snapshot,
    ):

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_central_bank_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                base_currency,
                quote_currency,

                base_bank,
                quote_bank,

                base_rate,
                quote_rate,

                base_hawkish_score,
                quote_hawkish_score,

                policy_divergence_score,
                rate_differential_score,

                currency_strength_score,
                macro_score,

                central_bank_score,
                confidence_score,

                policy_regime,
                policy_signal,

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

                :base_bank,
                :quote_bank,

                :base_rate,
                :quote_rate,

                :base_hawkish_score,
                :quote_hawkish_score,

                :policy_divergence_score,
                :rate_differential_score,

                :currency_strength_score,
                :macro_score,

                :central_bank_score,
                :confidence_score,

                :policy_regime,
                :policy_signal,

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
        pair=None,
        limit=1000,
    ):

        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_central_bank_snapshots
        """

        params = {}

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


def get_forex_central_bank_engine(
    *,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
    db=None,
):

    return ForexCentralBankEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )