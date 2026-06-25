# modules/forex/forex_carry_trade_engine.py

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

    from modules.forex.forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
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

    from forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )

    from forex_flow_of_funds_engine import (
        ForexFlowOfFundsEngine,
        get_forex_flow_of_funds_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


INTEREST_RATE_MAP = {
    "USD": 5.25,
    "EUR": 3.75,
    "GBP": 5.00,
    "JPY": 0.25,
    "CHF": 1.50,
    "AUD": 4.35,
    "CAD": 4.75,
    "NZD": 5.50,
}


@dataclass
class CarryTradeSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    base_currency: str
    quote_currency: str

    base_rate: float
    quote_rate: float

    rate_differential: float

    carry_score: float
    yield_score: float
    flow_score: float
    intermarket_score: float
    currency_strength_score: float

    expected_carry_return: float

    conviction_score: float
    confidence_score: float

    carry_regime: str
    carry_signal: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


@dataclass
class CarryTradeScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    attractive_count: int
    neutral_count: int
    unattractive_count: int

    average_carry_score: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)
        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data


class ForexCarryTradeEngine:

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
        intermarket_engine: Optional[
            ForexIntermarketEngine
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

        self.intermarket_engine = (
            intermarket_engine
            or get_forex_intermarket_engine(
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
            forex_carry_trade_snapshots (

                snapshot_id VARCHAR(64)
                PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                base_currency VARCHAR(10),
                quote_currency VARCHAR(10),

                base_rate DOUBLE PRECISION,
                quote_rate DOUBLE PRECISION,

                rate_differential DOUBLE PRECISION,

                carry_score DOUBLE PRECISION,
                yield_score DOUBLE PRECISION,
                flow_score DOUBLE PRECISION,
                intermarket_score DOUBLE PRECISION,
                currency_strength_score DOUBLE PRECISION,

                expected_carry_return DOUBLE PRECISION,

                conviction_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,

                carry_regime VARCHAR(50),
                carry_signal VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_carry_pair
            ON forex_carry_trade_snapshots(pair)
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

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> CarryTradeSnapshot:

        base_ccy, quote_ccy = (
            self._split_pair(pair)
        )

        base_rate = (
            INTEREST_RATE_MAP.get(
                base_ccy,
                3.0,
            )
        )

        quote_rate = (
            INTEREST_RATE_MAP.get(
                quote_ccy,
                3.0,
            )
        )

        rate_diff = (
            base_rate
            - quote_rate
        )

        flow = (
            self.flow_engine
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

        strength = (
            self.currency_strength_engine
            .analyze_currency(
                base_ccy,
                save=False,
            )
        )

        yield_score = min(
            100,
            abs(rate_diff) * 15,
        )

        carry_score = min(
            100,
            abs(rate_diff) * 18,
        )

        flow_score = abs(
            flow.net_flow_score
        )

        intermarket_score = (
            intermarket.intermarket_score
        )

        strength_score = (
            strength.global_strength_score
        )

        expected_carry_return = (
            rate_diff
        )

        conviction_score = (
            carry_score * 0.35
            + flow_score * 0.20
            + intermarket_score * 0.20
            + strength_score * 0.25
        )

        confidence = (
            conviction_score
            + carry_score
        ) / 2

        if (
            rate_diff > 1.50
            and conviction_score >= 75
        ):

            regime = (
                "ATTRACTIVE_CARRY"
            )

            signal = (
                "LONG_HIGH_YIELD"
            )

        elif (
            rate_diff < -1.50
            and conviction_score >= 75
        ):

            regime = (
                "REVERSE_CARRY"
            )

            signal = (
                "SHORT_LOW_YIELD"
            )

        elif (
            conviction_score >= 60
        ):

            regime = (
                "MODERATE_CARRY"
            )

            signal = (
                "SELECTIVE_ENTRY"
            )

        else:

            regime = "NEUTRAL"

            signal = (
                "WAIT"
            )

        snapshot = CarryTradeSnapshot(
            snapshot_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            base_currency=base_ccy,
            quote_currency=quote_ccy,

            base_rate=round(
                base_rate,
                2,
            ),

            quote_rate=round(
                quote_rate,
                2,
            ),

            rate_differential=round(
                rate_diff,
                2,
            ),

            carry_score=round(
                carry_score,
                2,
            ),

            yield_score=round(
                yield_score,
                2,
            ),

            flow_score=round(
                flow_score,
                2,
            ),

            intermarket_score=round(
                intermarket_score,
                2,
            ),

            currency_strength_score=round(
                strength_score,
                2,
            ),

            expected_carry_return=round(
                expected_carry_return,
                2,
            ),

            conviction_score=round(
                conviction_score,
                2,
            ),

            confidence_score=round(
                confidence,
                2,
            ),

            carry_regime=regime,
            carry_signal=signal,

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
    ) -> CarryTradeScan:

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

        attractive = len(
            [
                x
                for x in snapshots
                if x.carry_regime
                in [
                    "ATTRACTIVE_CARRY",
                    "REVERSE_CARRY",
                ]
            ]
        )

        neutral = len(
            [
                x
                for x in snapshots
                if x.carry_regime
                == "NEUTRAL"
            ]
        )

        unattractive = (
            len(snapshots)
            - attractive
            - neutral
        )

        avg_score = (
            sum(
                x.carry_score
                for x in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0
        )

        snapshots = sorted(
            snapshots,
            key=lambda x:
            x.conviction_score,
            reverse=True,
        )

        return CarryTradeScan(
            scan_id=str(
                uuid.uuid4()
            ),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(
                snapshots
            ),

            attractive_count=
            attractive,

            neutral_count=
            neutral,

            unattractive_count=
            unattractive,

            average_carry_score=round(
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
        snapshot: CarryTradeSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_carry_trade_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                base_currency,
                quote_currency,

                base_rate,
                quote_rate,

                rate_differential,

                carry_score,
                yield_score,
                flow_score,
                intermarket_score,
                currency_strength_score,

                expected_carry_return,

                conviction_score,
                confidence_score,

                carry_regime,
                carry_signal,

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

                :base_rate,
                :quote_rate,

                :rate_differential,

                :carry_score,
                :yield_score,
                :flow_score,
                :intermarket_score,
                :currency_strength_score,

                :expected_carry_return,

                :conviction_score,
                :confidence_score,

                :carry_regime,
                :carry_signal,

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
        FROM forex_carry_trade_snapshots
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


def get_forex_carry_trade_engine(
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
) -> ForexCarryTradeEngine:

    return ForexCarryTradeEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )