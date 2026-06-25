# modules/forex/forex_alpha_model.py

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from modules.forex.forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
        ForexService,
        get_forex_service,
    )

    from modules.forex.forex_institutional_scanner import (
        ForexInstitutionalScanner,
        get_forex_institutional_scanner,
    )

    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from modules.forex.forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )

    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
        ForexService,
        get_forex_service,
    )

    from forex_institutional_scanner import (
        ForexInstitutionalScanner,
        get_forex_institutional_scanner,
    )

    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from forex_macro_regime_engine import (
        ForexMacroRegimeEngine,
        get_forex_macro_regime_engine,
    )

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexAlphaSignal:
    signal_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    alpha_score: float
    expected_return_score: float
    risk_adjusted_score: float

    institutional_score: float
    recommendation_score: float
    regime_score: float
    macro_regime_score: float
    liquidity_score: float

    volatility_penalty: float
    drawdown_penalty: float
    crowding_penalty: float

    confidence_score: float
    conviction_score: float

    alpha_direction: str
    alpha_signal: str
    alpha_grade: str

    position_bias: str
    suggested_weight: float
    max_risk_weight: float

    rationale: str
    warnings: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexAlphaRun:
    run_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int

    long_count: int
    short_count: int
    watch_count: int
    avoid_count: int

    average_alpha_score: float
    average_confidence: float

    top_pair: Optional[str]
    top_signal: Optional[str]

    signals: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexAlphaModel:
    """
    Forex Alpha Model

    Combines institutional scanner output, recommendation conviction,
    market regime, macro regime, and liquidity into a normalized alpha
    score suitable for portfolio construction and autonomous trading.

    Architecture rules:
    - Explicit state passing
    - Tenant-safe
    - Neon Postgres compatible
    - Streamlit-safe
    - No global runtime state
    """

    def __init__(
        self,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        db: Any = None,
        forex_service: Optional[ForexService] = None,
        institutional_scanner: Optional[ForexInstitutionalScanner] = None,
        recommendation_engine: Optional[ForexRecommendationEngine] = None,
        regime_engine: Optional[ForexRegimeDetectionEngine] = None,
        macro_regime_engine: Optional[ForexMacroRegimeEngine] = None,
        liquidity_engine: Optional[ForexLiquidityEngine] = None,
    ) -> None:
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

        self.institutional_scanner = (
            institutional_scanner
            or get_forex_institutional_scanner(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.recommendation_engine = (
            recommendation_engine
            or get_forex_recommendation_engine(
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

        self.macro_regime_engine = (
            macro_regime_engine
            or get_forex_macro_regime_engine(
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

    # =====================================================
    # Database
    # =====================================================

    def ensure_tables(self) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_alpha_signals (
                signal_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                alpha_score DOUBLE PRECISION,
                expected_return_score DOUBLE PRECISION,
                risk_adjusted_score DOUBLE PRECISION,

                institutional_score DOUBLE PRECISION,
                recommendation_score DOUBLE PRECISION,
                regime_score DOUBLE PRECISION,
                macro_regime_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,

                volatility_penalty DOUBLE PRECISION,
                drawdown_penalty DOUBLE PRECISION,
                crowding_penalty DOUBLE PRECISION,

                confidence_score DOUBLE PRECISION,
                conviction_score DOUBLE PRECISION,

                alpha_direction VARCHAR(40),
                alpha_signal VARCHAR(80),
                alpha_grade VARCHAR(10),

                position_bias VARCHAR(40),
                suggested_weight DOUBLE PRECISION,
                max_risk_weight DOUBLE PRECISION,

                rationale TEXT,
                warnings TEXT,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_alpha_signals_tenant_pair
            ON forex_alpha_signals(tenant_id, pair, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_alpha_signals_signal
            ON forex_alpha_signals(alpha_signal, created_at DESC)
            """
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # Helpers
    # =====================================================

    def _safe_float(
        self,
        value: Any,
        default: float = 50.0,
    ) -> float:
        try:
            if value is None:
                return default

            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return default

            return result

        except Exception:
            return default

    def _clip(
        self,
        value: float,
        low: float = 0.0,
        high: float = 100.0,
    ) -> float:
        return max(low, min(high, float(value)))

    def _recommendation_score(
        self,
        pair: str,
    ) -> float:
        try:
            scan = self.recommendation_engine.run_scan(
                pairs=[pair],
                save=False,
            )

            rows = getattr(
                scan,
                "recommendations",
                [],
            )

            if not rows:
                return 50.0

            row = rows[0]

            if isinstance(row, dict):
                return self._safe_float(
                    row.get("conviction_score")
                    or row.get("confidence_score")
                    or row.get("score"),
                    50.0,
                )

            return self._safe_float(
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
        if score >= 92:
            return "A+"
        if score >= 84:
            return "A"
        if score >= 76:
            return "B"
        if score >= 66:
            return "C"
        return "D"

    def _direction(
        self,
        *,
        institutional_direction: str,
        regime_score: float,
        macro_regime_score: float,
        recommendation_score: float,
    ) -> str:
        direction = str(
            institutional_direction
            or ""
        ).upper()

        if direction in {
            "BULLISH",
            "BEARISH",
        }:
            return direction

        bullish = 0
        bearish = 0

        for score in [
            regime_score,
            macro_regime_score,
            recommendation_score,
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
        alpha_score: float,
        confidence_score: float,
        conviction_score: float,
        direction: str,
        liquidity_score: float,
    ) -> str:
        if (
            alpha_score >= 85
            and confidence_score >= 75
            and conviction_score >= 70
            and liquidity_score >= 55
            and direction == "BULLISH"
        ):
            return "ALPHA_LONG"

        if (
            alpha_score >= 85
            and confidence_score >= 75
            and conviction_score >= 70
            and liquidity_score >= 55
            and direction == "BEARISH"
        ):
            return "ALPHA_SHORT"

        if (
            alpha_score >= 75
            and direction == "BULLISH"
        ):
            return "LONG_WATCH"

        if (
            alpha_score >= 75
            and direction == "BEARISH"
        ):
            return "SHORT_WATCH"

        if alpha_score >= 65:
            return "ALPHA_MONITOR"

        return "AVOID"

    def _position_bias(
        self,
        signal: str,
        direction: str,
    ) -> str:
        if signal in {
            "ALPHA_LONG",
            "LONG_WATCH",
        } or direction == "BULLISH":
            return "LONG"

        if signal in {
            "ALPHA_SHORT",
            "SHORT_WATCH",
        } or direction == "BEARISH":
            return "SHORT"

        return "FLAT"

    def _suggested_weight(
        self,
        *,
        alpha_score: float,
        confidence_score: float,
        liquidity_score: float,
    ) -> float:
        raw = (
            alpha_score * 0.45
            + confidence_score * 0.35
            + liquidity_score * 0.20
        )

        if raw >= 90:
            return 6.0

        if raw >= 82:
            return 4.5

        if raw >= 74:
            return 3.0

        if raw >= 65:
            return 1.5

        return 0.0

    def _warnings(
        self,
        *,
        liquidity_score: float,
        volatility_penalty: float,
        drawdown_penalty: float,
        crowding_penalty: float,
    ) -> str:
        warnings: List[str] = []

        if liquidity_score < 45:
            warnings.append(
                "Liquidity below preferred threshold."
            )

        if volatility_penalty > 35:
            warnings.append(
                "Elevated volatility penalty."
            )

        if drawdown_penalty > 30:
            warnings.append(
                "Drawdown risk is elevated."
            )

        if crowding_penalty > 35:
            warnings.append(
                "Crowding risk is elevated."
            )

        return " ".join(warnings)

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_pair(
        self,
        pair: str,
        *,
        save: bool = True,
    ) -> ForexAlphaSignal:
        institutional = self.institutional_scanner.analyze_pair(
            pair,
            save=False,
        )

        regime = self.regime_engine.analyze_pair(
            pair,
            save=False,
        )

        macro_regime = self.macro_regime_engine.analyze_pair(
            pair,
            save=False,
        )

        liquidity = self.liquidity_engine.analyze_pair(
            pair,
            save=False,
        )

        institutional_score = self._safe_float(
            getattr(
                institutional,
                "institutional_score",
                None,
            ),
            50.0,
        )

        recommendation_score = self._recommendation_score(
            pair,
        )

        regime_score = self._safe_float(
            getattr(
                regime,
                "composite_regime_score",
                None,
            ),
            50.0,
        )

        macro_regime_score = self._safe_float(
            getattr(
                macro_regime,
                "composite_macro_regime_score",
                None,
            ),
            50.0,
        )

        liquidity_score = self._safe_float(
            getattr(
                liquidity,
                "liquidity_score",
                None,
            ),
            50.0,
        )

        volatility_penalty = self._clip(
            100.0
            - self._safe_float(
                getattr(
                    regime,
                    "volatility_regime_score",
                    None,
                ),
                50.0,
            )
        )

        drawdown_penalty = self._clip(
            max(
                0.0,
                60.0
                - liquidity_score,
            )
        )

        crowding_penalty = self._clip(
            abs(
                institutional_score
                - 50.0
            )
            * 0.35
        )

        expected_return_score = self._clip(
            institutional_score * 0.35
            + recommendation_score * 0.25
            + regime_score * 0.20
            + macro_regime_score * 0.20
        )

        risk_adjusted_score = self._clip(
            expected_return_score
            - volatility_penalty * 0.15
            - drawdown_penalty * 0.20
            - crowding_penalty * 0.10
            + liquidity_score * 0.15
        )

        alpha_score = self._clip(
            risk_adjusted_score * 0.60
            + institutional_score * 0.20
            + recommendation_score * 0.20
        )

        conviction_score = self._clip(
            abs(
                alpha_score
                - 50.0
            )
            * 1.25
            + (
                institutional_score
                + recommendation_score
                + macro_regime_score
            )
            / 12.0
        )

        confidence_score = self._clip(
            alpha_score * 0.45
            + conviction_score * 0.25
            + liquidity_score * 0.30
        )

        direction = self._direction(
            institutional_direction=getattr(
                institutional,
                "institutional_direction",
                "NEUTRAL",
            ),
            regime_score=regime_score,
            macro_regime_score=macro_regime_score,
            recommendation_score=recommendation_score,
        )

        signal = self._signal(
            alpha_score=alpha_score,
            confidence_score=confidence_score,
            conviction_score=conviction_score,
            direction=direction,
            liquidity_score=liquidity_score,
        )

        bias = self._position_bias(
            signal,
            direction,
        )

        suggested_weight = self._suggested_weight(
            alpha_score=alpha_score,
            confidence_score=confidence_score,
            liquidity_score=liquidity_score,
        )

        max_risk_weight = min(
            suggested_weight,
            5.0
            if liquidity_score >= 65
            else 2.5,
        )

        warnings = self._warnings(
            liquidity_score=liquidity_score,
            volatility_penalty=volatility_penalty,
            drawdown_penalty=drawdown_penalty,
            crowding_penalty=crowding_penalty,
        )

        rationale = (
            f"Alpha score {round(alpha_score, 2)} derived from "
            f"institutional score {round(institutional_score, 2)}, "
            f"recommendation score {round(recommendation_score, 2)}, "
            f"regime score {round(regime_score, 2)}, "
            f"macro regime score {round(macro_regime_score, 2)}, "
            f"and liquidity score {round(liquidity_score, 2)}."
        )

        alpha = ForexAlphaSignal(
            signal_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair=pair,

            alpha_score=round(alpha_score, 2),
            expected_return_score=round(expected_return_score, 2),
            risk_adjusted_score=round(risk_adjusted_score, 2),

            institutional_score=round(institutional_score, 2),
            recommendation_score=round(recommendation_score, 2),
            regime_score=round(regime_score, 2),
            macro_regime_score=round(macro_regime_score, 2),
            liquidity_score=round(liquidity_score, 2),

            volatility_penalty=round(volatility_penalty, 2),
            drawdown_penalty=round(drawdown_penalty, 2),
            crowding_penalty=round(crowding_penalty, 2),

            confidence_score=round(confidence_score, 2),
            conviction_score=round(conviction_score, 2),

            alpha_direction=direction,
            alpha_signal=signal,
            alpha_grade=self._grade(alpha_score),

            position_bias=bias,
            suggested_weight=round(suggested_weight, 2),
            max_risk_weight=round(max_risk_weight, 2),

            rationale=rationale,
            warnings=warnings,

            created_at=datetime.now(timezone.utc),
        )

        if save:
            self.save_signal(alpha)

        return alpha

    # =====================================================
    # Run
    # =====================================================

    def run_alpha_model(
        self,
        pairs: Optional[List[str]] = None,
        *,
        save: bool = True,
    ) -> ForexAlphaRun:
        pairs = pairs or DEFAULT_PAIRS

        signals: List[ForexAlphaSignal] = []

        for pair in pairs:
            try:
                signals.append(
                    self.analyze_pair(
                        pair,
                        save=save,
                    )
                )
            except Exception:
                continue

        signals = sorted(
            signals,
            key=lambda item: (
                item.alpha_score,
                item.confidence_score,
                item.conviction_score,
            ),
            reverse=True,
        )

        long_count = len(
            [
                signal
                for signal in signals
                if signal.alpha_signal == "ALPHA_LONG"
            ]
        )

        short_count = len(
            [
                signal
                for signal in signals
                if signal.alpha_signal == "ALPHA_SHORT"
            ]
        )

        watch_count = len(
            [
                signal
                for signal in signals
                if signal.alpha_signal
                in {
                    "LONG_WATCH",
                    "SHORT_WATCH",
                    "ALPHA_MONITOR",
                }
            ]
        )

        avoid_count = len(
            [
                signal
                for signal in signals
                if signal.alpha_signal == "AVOID"
            ]
        )

        average_alpha = (
            sum(
                signal.alpha_score
                for signal in signals
            )
            / len(signals)
            if signals
            else 0.0
        )

        average_confidence = (
            sum(
                signal.confidence_score
                for signal in signals
            )
            / len(signals)
            if signals
            else 0.0
        )

        return ForexAlphaRun(
            run_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(signals),

            long_count=long_count,
            short_count=short_count,
            watch_count=watch_count,
            avoid_count=avoid_count,

            average_alpha_score=round(average_alpha, 2),
            average_confidence=round(average_confidence, 2),

            top_pair=signals[0].pair if signals else None,
            top_signal=signals[0].alpha_signal if signals else None,

            signals=[
                signal.to_dict()
                for signal in signals
            ],

            created_at=datetime.now(timezone.utc),
        )

    # =====================================================
    # Persistence
    # =====================================================

    def save_signal(
        self,
        signal: ForexAlphaSignal,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_alpha_signals (
                signal_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair,

                alpha_score,
                expected_return_score,
                risk_adjusted_score,

                institutional_score,
                recommendation_score,
                regime_score,
                macro_regime_score,
                liquidity_score,

                volatility_penalty,
                drawdown_penalty,
                crowding_penalty,

                confidence_score,
                conviction_score,

                alpha_direction,
                alpha_signal,
                alpha_grade,

                position_bias,
                suggested_weight,
                max_risk_weight,

                rationale,
                warnings,

                created_at
            )
            VALUES (
                :signal_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair,

                :alpha_score,
                :expected_return_score,
                :risk_adjusted_score,

                :institutional_score,
                :recommendation_score,
                :regime_score,
                :macro_regime_score,
                :liquidity_score,

                :volatility_penalty,
                :drawdown_penalty,
                :crowding_penalty,

                :confidence_score,
                :conviction_score,

                :alpha_direction,
                :alpha_signal,
                :alpha_grade,

                :position_bias,
                :suggested_weight,
                :max_risk_weight,

                :rationale,
                :warnings,

                :created_at
            )
            """,
            signal.to_dict(),
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # History
    # =====================================================

    def load_signals(
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
        FROM forex_alpha_signals
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
            AND alpha_signal = :signal
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


def get_forex_alpha_model(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexAlphaModel:
    return ForexAlphaModel(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )