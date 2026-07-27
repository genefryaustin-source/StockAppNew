# modules/forex/forex_relative_strength_engine.py

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

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
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
class RelativeStrengthSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str
    base_currency: str
    quote_currency: str

    price: float

    base_strength_score: float
    quote_strength_score: float

    relative_strength_score: float
    currency_spread_score: float

    macro_strength_score: float
    flow_strength_score: float
    structure_strength_score: float

    momentum_score: float
    conviction_score: float

    strength_direction: str
    strength_signal: str

    confidence_score: float

    provider: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class RelativeStrengthScan:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    bullish_count: int
    bearish_count: int
    neutral_count: int

    average_strength_score: float
    average_confidence: float

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexRelativeStrengthEngine:

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        macro_engine: Optional[ForexMacroEngine] = None,
        flow_engine: Optional[ForexFlowOfFundsEngine] = None,
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

        self.macro_engine = (
            macro_engine
            or get_forex_macro_engine(
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
            forex_relative_strength_snapshots (

                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                base_currency VARCHAR(10),
                quote_currency VARCHAR(10),

                price DOUBLE PRECISION,

                base_strength_score DOUBLE PRECISION,
                quote_strength_score DOUBLE PRECISION,

                relative_strength_score DOUBLE PRECISION,
                currency_spread_score DOUBLE PRECISION,

                macro_strength_score DOUBLE PRECISION,
                flow_strength_score DOUBLE PRECISION,
                structure_strength_score DOUBLE PRECISION,

                momentum_score DOUBLE PRECISION,
                conviction_score DOUBLE PRECISION,

                strength_direction VARCHAR(40),
                strength_signal VARCHAR(60),

                confidence_score DOUBLE PRECISION,

                provider VARCHAR(100),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_forex_relative_strength_pair
            ON forex_relative_strength_snapshots(pair)
            """
        )

        if hasattr(self.db, "commit"):
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

        if len(clean) >= 6:
            return clean[:3], clean[3:6]

        return "UNK", "UNK"

    def _currency_strength_seed(
        self,
        currency: str,
    ) -> float:

        value = sum(ord(c) for c in currency)

        return float(
            35 + (value % 60)
        )

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> RelativeStrengthSnapshot:

        quote = self.forex_service.get_quote(pair)

        macro = self.macro_engine.analyze_pair(
            pair,
            save=False,
        )

        flow = self.flow_engine.analyze_pair(
            pair,
            save=False,
        )

        structure = (
            self.structure_engine.analyze_pair(
                pair,
                save=False,
            )
        )

        base_currency, quote_currency = (
            self._split_pair(pair)
        )

        base_strength = (
            self._currency_strength_seed(
                base_currency
            )
        )

        quote_strength = (
            self._currency_strength_seed(
                quote_currency
            )
        )

        macro_strength = float(
            getattr(
                macro,
                "macro_score",
                50,
            )
        )

        flow_strength = float(
            abs(
                getattr(
                    flow,
                    "net_flow_score",
                    0,
                )
            )
        )

        structure_strength = float(
            getattr(
                structure,
                "market_structure_score",
                50,
            )
        )

        relative_strength = (
            base_strength
            - quote_strength
        )

        spread_score = abs(
            relative_strength
        )

        momentum_score = (
            (
                macro_strength
                + flow_strength
                + structure_strength
            )
            / 3
        )

        conviction_score = (
            spread_score * 0.40
            + momentum_score * 0.60
        )

        confidence = min(
            100,
            (
                conviction_score
                + structure_strength
            )
            / 2,
        )

        if relative_strength >= 10:

            direction = "BULLISH"

        elif relative_strength <= -10:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        if conviction_score >= 80:

            if direction == "BULLISH":
                signal = (
                    "STRONG_RELATIVE_LONG"
                )

            elif direction == "BEARISH":
                signal = (
                    "STRONG_RELATIVE_SHORT"
                )

            else:
                signal = (
                    "RELATIVE_BALANCE"
                )

        elif conviction_score >= 65:

            signal = (
                "RELATIVE_STRENGTH_SETUP"
            )

        else:

            signal = "MONITOR"

        snapshot = RelativeStrengthSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,
            base_currency=base_currency,
            quote_currency=quote_currency,

            price=float(
                quote.price
            ),

            base_strength_score=round(
                base_strength,
                2,
            ),

            quote_strength_score=round(
                quote_strength,
                2,
            ),

            relative_strength_score=round(
                relative_strength,
                2,
            ),

            currency_spread_score=round(
                spread_score,
                2,
            ),

            macro_strength_score=round(
                macro_strength,
                2,
            ),

            flow_strength_score=round(
                flow_strength,
                2,
            ),

            structure_strength_score=round(
                structure_strength,
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

            strength_direction=direction,
            strength_signal=signal,

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
    ) -> RelativeStrengthScan:

        pairs = pairs or DEFAULT_PAIRS

        snapshots: List[
            RelativeStrengthSnapshot
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
                if x.strength_direction
                == "BULLISH"
            ]
        )

        bearish = len(
            [
                x
                for x in snapshots
                if x.strength_direction
                == "BEARISH"
            ]
        )

        neutral = len(
            [
                x
                for x in snapshots
                if x.strength_direction
                == "NEUTRAL"
            ]
        )

        avg_strength = (
            sum(
                x.conviction_score
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
            x.conviction_score,
            reverse=True,
        )

        return RelativeStrengthScan(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),

            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,

            average_strength_score=round(
                avg_strength,
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
        snapshot: RelativeStrengthSnapshot,
    ) -> None:

        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO
            forex_relative_strength_snapshots
            (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                base_currency,
                quote_currency,

                price,

                base_strength_score,
                quote_strength_score,

                relative_strength_score,
                currency_spread_score,

                macro_strength_score,
                flow_strength_score,
                structure_strength_score,

                momentum_score,
                conviction_score,

                strength_direction,
                strength_signal,

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

                :base_currency,
                :quote_currency,

                :price,

                :base_strength_score,
                :quote_strength_score,

                :relative_strength_score,
                :currency_spread_score,

                :macro_strength_score,
                :flow_strength_score,
                :structure_strength_score,

                :momentum_score,
                :conviction_score,

                :strength_direction,
                :strength_signal,

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
        FROM forex_relative_strength_snapshots
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


# =====================================================
# Factory
# =====================================================

def get_forex_relative_strength_engine(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexRelativeStrengthEngine:

    return ForexRelativeStrengthEngine(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )