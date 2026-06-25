# modules/forex/forex_institutional_scanner.py

from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from modules.forex.forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )

    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from modules.forex.forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )

    from modules.forex.forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
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

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from modules.forex.forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
    )

    from modules.forex.forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )

    from modules.forex.forex_carry_trade_engine import (
        ForexCarryTradeEngine,
        get_forex_carry_trade_engine,
    )

    from modules.forex.forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from modules.forex.forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )

    from modules.forex.forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
    )

    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from forex_order_flow_engine import (
        ForexOrderFlowEngine,
        get_forex_order_flow_engine,
    )

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from forex_macro_engine import (
        ForexMacroEngine,
        get_forex_macro_engine,
    )

    from forex_dealer_positioning_engine import (
        ForexDealerPositioningEngine,
        get_forex_dealer_positioning_engine,
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

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from forex_currency_strength_engine import (
        ForexCurrencyStrengthEngine,
        get_forex_currency_strength_engine,
    )

    from forex_intermarket_engine import (
        ForexIntermarketEngine,
        get_forex_intermarket_engine,
    )

    from forex_carry_trade_engine import (
        ForexCarryTradeEngine,
        get_forex_carry_trade_engine,
    )

    from forex_central_bank_engine import (
        ForexCentralBankEngine,
        get_forex_central_bank_engine,
    )

    from forex_sentiment_engine import (
        ForexSentimentEngine,
        get_forex_sentiment_engine,
    )

    from forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexInstitutionalScannerSnapshot:
    snapshot_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    recommendation_score: float
    order_flow_score: float
    liquidity_score: float
    macro_score: float
    dealer_positioning_score: float
    market_structure_score: float
    flow_of_funds_score: float
    relative_strength_score: float
    correlation_score: float
    regime_score: float
    currency_strength_score: float
    intermarket_score: float
    carry_score: float
    central_bank_score: float
    sentiment_score: float
    macro_regime_score: float

    institutional_score: float
    conviction_score: float
    confidence_score: float

    institutional_direction: str
    institutional_signal: str
    institutional_grade: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexInstitutionalScannerRun:
    scan_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    institutional_long_count: int
    institutional_short_count: int
    watch_count: int
    no_edge_count: int

    average_institutional_score: float
    average_confidence: float

    top_pair: Optional[str]
    top_signal: Optional[str]

    snapshots: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexInstitutionalScanner:

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        recommendation_engine: Optional[ForexRecommendationEngine] = None,
        order_flow_engine: Optional[ForexOrderFlowEngine] = None,
        liquidity_engine: Optional[ForexLiquidityEngine] = None,
        macro_engine: Optional[ForexMacroEngine] = None,
        dealer_engine: Optional[ForexDealerPositioningEngine] = None,
        market_structure_engine: Optional[ForexMarketStructureEngine] = None,
        flow_of_funds_engine: Optional[ForexFlowOfFundsEngine] = None,
        relative_strength_engine: Optional[ForexRelativeStrengthEngine] = None,
        correlation_engine: Optional[ForexCorrelationEngine] = None,
        regime_engine: Optional[ForexRegimeDetectionEngine] = None,
        currency_strength_engine: Optional[ForexCurrencyStrengthEngine] = None,
        intermarket_engine: Optional[ForexIntermarketEngine] = None,
        carry_trade_engine: Optional[ForexCarryTradeEngine] = None,
        central_bank_engine: Optional[ForexCentralBankEngine] = None,
        sentiment_engine: Optional[ForexSentimentEngine] = None,
        macro_regime_engine: Optional[ForexMacroRegimeEngine] = None,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.db = db

        self.recommendation_engine = (
            recommendation_engine
            or get_forex_recommendation_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
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

        self.liquidity_engine = (
            liquidity_engine
            or get_forex_liquidity_engine(
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

        self.dealer_engine = (
            dealer_engine
            or get_forex_dealer_positioning_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
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

        self.flow_of_funds_engine = (
            flow_of_funds_engine
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

        self.regime_engine = (
            regime_engine
            or get_forex_regime_detection_engine(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
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

        self.carry_trade_engine = (
            carry_trade_engine
            or get_forex_carry_trade_engine(
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

        self.macro_regime_engine = (
            macro_regime_engine
            or get_forex_macro_regime_engine(
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
            CREATE TABLE IF NOT EXISTS forex_institutional_scanner_snapshots (
                snapshot_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                recommendation_score DOUBLE PRECISION,
                order_flow_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                macro_score DOUBLE PRECISION,
                dealer_positioning_score DOUBLE PRECISION,
                market_structure_score DOUBLE PRECISION,
                flow_of_funds_score DOUBLE PRECISION,
                relative_strength_score DOUBLE PRECISION,
                correlation_score DOUBLE PRECISION,
                regime_score DOUBLE PRECISION,
                currency_strength_score DOUBLE PRECISION,
                intermarket_score DOUBLE PRECISION,
                carry_score DOUBLE PRECISION,
                central_bank_score DOUBLE PRECISION,
                sentiment_score DOUBLE PRECISION,
                macro_regime_score DOUBLE PRECISION,

                institutional_score DOUBLE PRECISION,
                conviction_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,

                institutional_direction VARCHAR(40),
                institutional_signal VARCHAR(100),
                institutional_grade VARCHAR(10),

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_institutional_scanner_pair
            ON forex_institutional_scanner_snapshots(pair)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_institutional_scanner_tenant_created
            ON forex_institutional_scanner_snapshots(tenant_id, created_at DESC)
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # Helpers
    # =====================================================

    def _base_currency(self, pair: str) -> str:
        clean = pair.replace("/", "").replace("-", "").upper()
        return clean[:3]

    def _benchmark_pair(self, pair: str) -> str:
        return "EUR/USD" if pair != "EUR/USD" else "GBP/USD"

    def _safe(self, value: Any, default: float = 50.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _recommendation_for_pair(
        self,
        pair: str,
    ) -> float:
        try:
            scan = self.recommendation_engine.run_scan(
                pairs=[pair],
                save=False,
            )
            rows = getattr(scan, "recommendations", [])
            if not rows:
                return 50.0

            row = rows[0]

            if isinstance(row, dict):
                return self._safe(
                    row.get("conviction_score")
                    or row.get("confidence_score")
                    or row.get("score"),
                    50.0,
                )

            return self._safe(
                getattr(row, "conviction_score", None)
                or getattr(row, "confidence_score", None)
                or getattr(row, "score", None),
                50.0,
            )

        except Exception:
            return 50.0

    def _grade(
        self,
        score: float,
    ) -> str:
        if score >= 90:
            return "A+"
        if score >= 82:
            return "A"
        if score >= 74:
            return "B"
        if score >= 65:
            return "C"
        return "D"

    def _direction(
        self,
        *,
        recommendation_score: float,
        order_flow_score: float,
        macro_score: float,
        relative_strength_score: float,
        sentiment_score: float,
        central_bank_score: float,
    ) -> str:
        bullish = 0
        bearish = 0

        for score in [
            recommendation_score,
            order_flow_score,
            macro_score,
            relative_strength_score,
            sentiment_score,
            central_bank_score,
        ]:
            if score >= 58:
                bullish += 1
            elif score <= 42:
                bearish += 1

        if bullish > bearish:
            return "BULLISH"

        if bearish > bullish:
            return "BEARISH"

        return "NEUTRAL"

    def _signal(
        self,
        *,
        institutional_score: float,
        conviction_score: float,
        confidence_score: float,
        direction: str,
        regime_score: float,
        liquidity_score: float,
    ) -> str:
        if (
            institutional_score >= 85
            and conviction_score >= 75
            and confidence_score >= 70
            and direction == "BULLISH"
        ):
            return "INSTITUTIONAL_LONG_SETUP"

        if (
            institutional_score >= 85
            and conviction_score >= 75
            and confidence_score >= 70
            and direction == "BEARISH"
        ):
            return "INSTITUTIONAL_SHORT_SETUP"

        if (
            institutional_score >= 75
            and direction == "BULLISH"
        ):
            return "LONG_WATCHLIST"

        if (
            institutional_score >= 75
            and direction == "BEARISH"
        ):
            return "SHORT_WATCHLIST"

        if regime_score >= 80 and liquidity_score >= 60:
            return "REGIME_CONFIRMED_WATCH"

        if institutional_score >= 65:
            return "INSTITUTIONAL_MONITOR"

        return "NO_EDGE"

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> ForexInstitutionalScannerSnapshot:
        recommendation_score = self._recommendation_for_pair(pair)

        order_flow = self.order_flow_engine.analyze_pair(
            pair,
            save=False,
        )

        liquidity = self.liquidity_engine.analyze_pair(
            pair,
            save=False,
        )

        macro = self.macro_engine.analyze_pair(
            pair,
            save=False,
        )

        dealer = self.dealer_engine.analyze_pair(
            pair,
            save=False,
        )

        structure = self.market_structure_engine.analyze_pair(
            pair,
            save=False,
        )

        flow = self.flow_of_funds_engine.analyze_pair(
            pair,
            save=False,
        )

        relative_strength = self.relative_strength_engine.analyze_pair(
            pair,
            save=False,
        )

        correlation = self.correlation_engine.analyze_pair_correlation(
            pair,
            self._benchmark_pair(pair),
            save=False,
        )

        regime = self.regime_engine.analyze_pair(
            pair,
            save=False,
        )

        currency_strength = self.currency_strength_engine.analyze_currency(
            self._base_currency(pair),
            save=False,
        )

        intermarket = self.intermarket_engine.analyze_pair(
            pair,
            save=False,
        )

        carry = self.carry_trade_engine.analyze_pair(
            pair,
            save=False,
        )

        central_bank = self.central_bank_engine.analyze_pair(
            pair,
            save=False,
        )

        sentiment = self.sentiment_engine.analyze_pair(
            pair,
            save=False,
        )

        macro_regime = self.macro_regime_engine.analyze_pair(
            pair,
            save=False,
        )

        order_flow_score = self._safe(
            getattr(order_flow, "confidence_score", None),
        )

        liquidity_score = self._safe(
            getattr(liquidity, "liquidity_score", None),
        )

        macro_score = self._safe(
            getattr(macro, "macro_score", None),
        )

        dealer_positioning_score = self._safe(
            getattr(dealer, "positioning_conviction", None),
        )

        market_structure_score = self._safe(
            getattr(structure, "market_structure_score", None),
        )

        flow_of_funds_score = self._safe(
            abs(getattr(flow, "net_flow_score", 0)),
        )

        relative_strength_score = self._safe(
            getattr(relative_strength, "conviction_score", None),
        )

        correlation_score = self._safe(
            getattr(correlation, "correlation_score", None),
        )

        regime_score = self._safe(
            getattr(regime, "composite_regime_score", None),
        )

        currency_strength_score = self._safe(
            getattr(currency_strength, "global_strength_score", None),
        )

        intermarket_score = self._safe(
            getattr(intermarket, "intermarket_score", None),
        )

        carry_score = self._safe(
            getattr(carry, "conviction_score", None),
        )

        central_bank_score = self._safe(
            getattr(central_bank, "central_bank_score", None),
        )

        sentiment_score = min(
            100.0,
            max(
                0.0,
                50.0
                + self._safe(
                    getattr(sentiment, "net_sentiment_score", 0),
                    0.0,
                ),
            ),
        )

        macro_regime_score = self._safe(
            getattr(
                macro_regime,
                "composite_macro_regime_score",
                None,
            ),
        )

        institutional_score = (
            recommendation_score * 0.09
            + order_flow_score * 0.08
            + liquidity_score * 0.06
            + macro_score * 0.08
            + dealer_positioning_score * 0.07
            + market_structure_score * 0.08
            + flow_of_funds_score * 0.07
            + relative_strength_score * 0.07
            + correlation_score * 0.04
            + regime_score * 0.06
            + currency_strength_score * 0.06
            + intermarket_score * 0.06
            + carry_score * 0.05
            + central_bank_score * 0.06
            + sentiment_score * 0.05
            + macro_regime_score * 0.06
        )

        conviction_score = (
            abs(institutional_score - 50.0) * 1.15
            + (
                recommendation_score
                + macro_regime_score
                + regime_score
            )
            / 9.0
        )

        conviction_score = min(
            100.0,
            max(
                0.0,
                conviction_score,
            ),
        )

        confidence_score = (
            institutional_score * 0.55
            + conviction_score * 0.25
            + liquidity_score * 0.20
        )

        direction = self._direction(
            recommendation_score=recommendation_score,
            order_flow_score=order_flow_score,
            macro_score=macro_score,
            relative_strength_score=relative_strength_score,
            sentiment_score=sentiment_score,
            central_bank_score=central_bank_score,
        )

        signal = self._signal(
            institutional_score=institutional_score,
            conviction_score=conviction_score,
            confidence_score=confidence_score,
            direction=direction,
            regime_score=regime_score,
            liquidity_score=liquidity_score,
        )

        snapshot = ForexInstitutionalScannerSnapshot(
            snapshot_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            recommendation_score=round(recommendation_score, 2),
            order_flow_score=round(order_flow_score, 2),
            liquidity_score=round(liquidity_score, 2),
            macro_score=round(macro_score, 2),
            dealer_positioning_score=round(dealer_positioning_score, 2),
            market_structure_score=round(market_structure_score, 2),
            flow_of_funds_score=round(flow_of_funds_score, 2),
            relative_strength_score=round(relative_strength_score, 2),
            correlation_score=round(correlation_score, 2),
            regime_score=round(regime_score, 2),
            currency_strength_score=round(currency_strength_score, 2),
            intermarket_score=round(intermarket_score, 2),
            carry_score=round(carry_score, 2),
            central_bank_score=round(central_bank_score, 2),
            sentiment_score=round(sentiment_score, 2),
            macro_regime_score=round(macro_regime_score, 2),

            institutional_score=round(institutional_score, 2),
            conviction_score=round(conviction_score, 2),
            confidence_score=round(confidence_score, 2),

            institutional_direction=direction,
            institutional_signal=signal,
            institutional_grade=self._grade(
                institutional_score,
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
    ) -> ForexInstitutionalScannerRun:
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

        snapshots = sorted(
            snapshots,
            key=lambda item: (
                item.institutional_score,
                item.confidence_score,
            ),
            reverse=True,
        )

        long_count = len(
            [
                item
                for item in snapshots
                if item.institutional_signal
                == "INSTITUTIONAL_LONG_SETUP"
            ]
        )

        short_count = len(
            [
                item
                for item in snapshots
                if item.institutional_signal
                == "INSTITUTIONAL_SHORT_SETUP"
            ]
        )

        watch_count = len(
            [
                item
                for item in snapshots
                if item.institutional_signal
                in {
                    "LONG_WATCHLIST",
                    "SHORT_WATCHLIST",
                    "REGIME_CONFIRMED_WATCH",
                    "INSTITUTIONAL_MONITOR",
                }
            ]
        )

        no_edge_count = len(
            [
                item
                for item in snapshots
                if item.institutional_signal
                == "NO_EDGE"
            ]
        )

        average_score = (
            sum(
                item.institutional_score
                for item in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0.0
        )

        average_confidence = (
            sum(
                item.confidence_score
                for item in snapshots
            )
            / len(snapshots)
            if snapshots
            else 0.0
        )

        top_pair = (
            snapshots[0].pair
            if snapshots
            else None
        )

        top_signal = (
            snapshots[0].institutional_signal
            if snapshots
            else None
        )

        return ForexInstitutionalScannerRun(
            scan_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(snapshots),

            institutional_long_count=long_count,
            institutional_short_count=short_count,
            watch_count=watch_count,
            no_edge_count=no_edge_count,

            average_institutional_score=round(average_score, 2),
            average_confidence=round(average_confidence, 2),

            top_pair=top_pair,
            top_signal=top_signal,

            snapshots=[
                item.to_dict()
                for item in snapshots
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
        snapshot: ForexInstitutionalScannerSnapshot,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_institutional_scanner_snapshots (
                snapshot_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                recommendation_score,
                order_flow_score,
                liquidity_score,
                macro_score,
                dealer_positioning_score,
                market_structure_score,
                flow_of_funds_score,
                relative_strength_score,
                correlation_score,
                regime_score,
                currency_strength_score,
                intermarket_score,
                carry_score,
                central_bank_score,
                sentiment_score,
                macro_regime_score,

                institutional_score,
                conviction_score,
                confidence_score,

                institutional_direction,
                institutional_signal,
                institutional_grade,

                created_at
            )
            VALUES (
                :snapshot_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :recommendation_score,
                :order_flow_score,
                :liquidity_score,
                :macro_score,
                :dealer_positioning_score,
                :market_structure_score,
                :flow_of_funds_score,
                :relative_strength_score,
                :correlation_score,
                :regime_score,
                :currency_strength_score,
                :intermarket_score,
                :carry_score,
                :central_bank_score,
                :sentiment_score,
                :macro_regime_score,

                :institutional_score,
                :conviction_score,
                :confidence_score,

                :institutional_direction,
                :institutional_signal,
                :institutional_grade,

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
        signal: str = "ALL",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_institutional_scanner_snapshots
        WHERE tenant_id = :tenant_id
        """

        params: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
        }

        if pair:
            sql += """
            AND pair = :pair
            """
            params["pair"] = pair

        if signal and signal.upper() != "ALL":
            sql += """
            AND institutional_signal = :signal
            """
            params["signal"] = signal.upper()

        sql += """
        ORDER BY created_at DESC
        LIMIT :limit
        """

        params["limit"] = int(limit)

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


def get_forex_institutional_scanner(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexInstitutionalScanner:
    return ForexInstitutionalScanner(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )