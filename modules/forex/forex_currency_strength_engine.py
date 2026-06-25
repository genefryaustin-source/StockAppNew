# modules/forex/forex_currency_strength_engine.py

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

    from forex_relative_strength_engine import (
        ForexRelativeStrengthEngine,
        get_forex_relative_strength_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS

MAJOR_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "AUD",
    "CAD",
    "NZD",
]


@dataclass
class CurrencyStrengthSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    currency: str

    relative_strength_score: float
    macro_strength_score: float
    capital_flow_score: float

    momentum_score: float
    conviction_score: float

    global_strength_score: float
    percentile_rank: float

    strength_regime: str
    strength_signal: str

    confidence_score: float

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


@dataclass
class CurrencyStrengthScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    currency_count: int

    strongest_currency: str
    weakest_currency: str

    average_strength: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


class ForexCurrencyStrengthEngine:

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
        relative_strength_engine: Optional[
            ForexRelativeStrengthEngine
        ] = None,
        flow_engine: Optional[
            ForexFlowOfFundsEngine
        ] = None,
        macro_engine: Optional[
            ForexMacroEngine
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

    def ensure_tables(self) -> None:

        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS
            forex_currency_strength_snapshots (

                snapshot_id VARCHAR(64)
                PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                currency VARCHAR(10),

                relative_strength_score DOUBLE PRECISION,
                macro_strength_score DOUBLE PRECISION,
                capital_flow_score DOUBLE PRECISION,

                momentum_score DOUBLE PRECISION,
                conviction_score DOUBLE PRECISION,

                global_strength_score DOUBLE PRECISION,
                percentile_rank DOUBLE PRECISION,

                strength_regime VARCHAR(50),
                strength_signal VARCHAR(80),

                confidence_score DOUBLE PRECISION,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_currency_strength
            ON forex_currency_strength_snapshots(
                currency
            )
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

    def _pairs_for_currency(
        self,
        currency: str,
    ) -> List[str]:

        pairs = []

        for pair in DEFAULT_PAIRS:

            clean = (
                pair.replace("/", "")
                .upper()
            )

            if currency in clean:
                pairs.append(pair)

        return pairs

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_currency(
        self,
        currency: str,
        *,
        save: bool = True,
    ) -> CurrencyStrengthSnapshot:

        pairs = (
            self._pairs_for_currency(
                currency
            )
        )

        relative_scores = []
        flow_scores = []
        macro_scores = []

        for pair in pairs:

            try:

                rs = (
                    self.relative_strength_engine
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

                macro = (
                    self.macro_engine
                    .analyze_pair(
                        pair,
                        save=False,
                    )
                )

                relative_scores.append(
                    rs.conviction_score
                )

                flow_scores.append(
                    abs(
                        flow.net_flow_score
                    )
                )

                macro_scores.append(
                    macro.macro_score
                )

            except Exception:
                continue

        relative_strength = (
            sum(relative_scores)
            / len(relative_scores)
            if relative_scores
            else 50
        )

        capital_flow = (
            sum(flow_scores)
            / len(flow_scores)
            if flow_scores
            else 50
        )

        macro_strength = (
            sum(macro_scores)
            / len(macro_scores)
            if macro_scores
            else 50
        )

        momentum_score = (
            (
                relative_strength
                + capital_flow
            )
            / 2
        )

        conviction_score = (
            (
                relative_strength
                + macro_strength
                + capital_flow
            )
            / 3
        )

        global_strength = (
            conviction_score
        )

        percentile_rank = min(
            100,
            max(
                0,
                global_strength,
            ),
        )

        confidence = (
            (
                momentum_score
                + conviction_score
            )
            / 2
        )

        if global_strength >= 80:

            regime = "VERY_STRONG"
            signal = (
                "INSTITUTIONAL_ACCUMULATION"
            )

        elif global_strength >= 65:

            regime = "STRONG"
            signal = (
                "OUTPERFORM"
            )

        elif global_strength <= 35:

            regime = "WEAK"
            signal = (
                "UNDERPERFORM"
            )

        else:

            regime = "NEUTRAL"
            signal = (
                "BALANCED"
            )

        snapshot = CurrencyStrengthSnapshot(
            snapshot_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            currency=currency,

            relative_strength_score=round(
                relative_strength,
                2,
            ),

            macro_strength_score=round(
                macro_strength,
                2,
            ),

            capital_flow_score=round(
                capital_flow,
                2,
            ),

            momentum_score=round(
                momentum_score,
                2,
            ),

            conviction_score=round(
                conviction_score,
                2,
            ),

            global_strength_score=round(
                global_strength,
                2,
            ),

            percentile_rank=round(
                percentile_rank,
                2,
            ),

            strength_regime=regime,
            strength_signal=signal,

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

    def scan_currencies(
        self,
        currencies: Optional[
            List[str]
        ] = None,
        *,
        save: bool = True,
    ) -> CurrencyStrengthScan:

        currencies = (
            currencies
            or MAJOR_CURRENCIES
        )

        snapshots = []

        for currency in currencies:

            try:

                snapshots.append(
                    self.analyze_currency(
                        currency,
                        save=save,
                    )
                )

            except Exception:
                continue

        snapshots = sorted(
            snapshots,
            key=lambda x:
            x.global_strength_score,
            reverse=True,
        )

        strongest = (
            snapshots[0].currency
            if snapshots
            else ""
        )

        weakest = (
            snapshots[-1].currency
            if snapshots
            else ""
        )

        average_strength = (
            sum(
                x.global_strength_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        return CurrencyStrengthScan(
            scan_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            currency_count=len(
                snapshots
            ),

            strongest_currency=strongest,
            weakest_currency=weakest,

            average_strength=round(
                average_strength,
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
        snapshot: CurrencyStrengthSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_currency_strength_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                currency,

                relative_strength_score,
                macro_strength_score,
                capital_flow_score,

                momentum_score,
                conviction_score,

                global_strength_score,
                percentile_rank,

                strength_regime,
                strength_signal,

                confidence_score,

                created_at
            )
            VALUES
            (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :currency,

                :relative_strength_score,
                :macro_strength_score,
                :capital_flow_score,

                :momentum_score,
                :conviction_score,

                :global_strength_score,
                :percentile_rank,

                :strength_regime,
                :strength_signal,

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
        currency: Optional[
            str
        ] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_currency_strength_snapshots
        """

        params = {}

        if currency:

            sql += """
            WHERE currency = :currency
            """

            params[
                "currency"
            ] = currency

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

def get_forex_currency_strength_engine(
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
) -> ForexCurrencyStrengthEngine:

    return ForexCurrencyStrengthEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )