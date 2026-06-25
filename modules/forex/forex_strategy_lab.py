# modules/forex/forex_strategy_lab.py

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

    from modules.forex.forex_alpha_model import (
        ForexAlphaModel,
        get_forex_alpha_model,
    )

    from modules.forex.forex_portfolio_optimizer import (
        ForexPortfolioOptimizer,
        get_forex_portfolio_optimizer,
    )

    from modules.forex.forex_strategy_engine import (
        ForexStrategyEngine,
        get_forex_strategy_engine,
    )

    from modules.forex.forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from modules.forex.forex_execution_quality_engine import (
        ForexExecutionQualityEngine,
        get_forex_execution_quality_engine,
    )

except Exception:

    from forex_service import (
        MAJOR_PAIRS,
        CROSS_PAIRS,
        ForexService,
        get_forex_service,
    )

    from forex_alpha_model import (
        ForexAlphaModel,
        get_forex_alpha_model,
    )

    from forex_portfolio_optimizer import (
        ForexPortfolioOptimizer,
        get_forex_portfolio_optimizer,
    )

    from forex_strategy_engine import (
        ForexStrategyEngine,
        get_forex_strategy_engine,
    )

    from forex_recommendation_engine import (
        ForexRecommendationEngine,
        get_forex_recommendation_engine,
    )

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )

    from forex_execution_quality_engine import (
        ForexExecutionQualityEngine,
        get_forex_execution_quality_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexStrategyLabResult:
    result_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    strategy_name: str
    pair: str

    alpha_score: float
    recommendation_score: float
    strategy_score: float
    regime_score: float
    execution_quality_score: float
    optimizer_weight: float

    expected_return_score: float
    risk_score: float
    risk_adjusted_score: float

    win_probability: float
    payoff_ratio: float
    expectancy_score: float

    strategy_direction: str
    strategy_signal: str
    strategy_grade: str

    suggested_action: str
    suggested_weight: float

    rationale: str
    warnings: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexStrategyLabRun:
    run_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    strategy_name: str
    pair_count: int

    deploy_count: int
    watch_count: int
    avoid_count: int

    average_strategy_score: float
    average_expectancy_score: float
    average_risk_adjusted_score: float

    top_pair: Optional[str]
    top_signal: Optional[str]

    results: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexStrategyLab:
    """
    Forex Strategy Lab

    Research layer for testing Forex strategy ideas against:
    - Alpha model
    - Recommendations
    - Strategy engine
    - Regime detection
    - Execution quality
    - Portfolio optimizer

    Architecture:
    - Explicit state passing
    - Tenant-safe
    - Neon Postgres compatible
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
        alpha_model: Optional[ForexAlphaModel] = None,
        portfolio_optimizer: Optional[ForexPortfolioOptimizer] = None,
        strategy_engine: Optional[ForexStrategyEngine] = None,
        recommendation_engine: Optional[ForexRecommendationEngine] = None,
        regime_engine: Optional[ForexRegimeDetectionEngine] = None,
        execution_quality_engine: Optional[ForexExecutionQualityEngine] = None,
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

        self.alpha_model = (
            alpha_model
            or get_forex_alpha_model(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.portfolio_optimizer = (
            portfolio_optimizer
            or get_forex_portfolio_optimizer(
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
                db=db,
            )
        )

        self.strategy_engine = (
            strategy_engine
            or get_forex_strategy_engine(
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

        self.execution_quality_engine = (
            execution_quality_engine
            or get_forex_execution_quality_engine(
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
            CREATE TABLE IF NOT EXISTS forex_strategy_lab_results (
                result_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                strategy_name VARCHAR(120),
                pair VARCHAR(20),

                alpha_score DOUBLE PRECISION,
                recommendation_score DOUBLE PRECISION,
                strategy_score DOUBLE PRECISION,
                regime_score DOUBLE PRECISION,
                execution_quality_score DOUBLE PRECISION,
                optimizer_weight DOUBLE PRECISION,

                expected_return_score DOUBLE PRECISION,
                risk_score DOUBLE PRECISION,
                risk_adjusted_score DOUBLE PRECISION,

                win_probability DOUBLE PRECISION,
                payoff_ratio DOUBLE PRECISION,
                expectancy_score DOUBLE PRECISION,

                strategy_direction VARCHAR(40),
                strategy_signal VARCHAR(80),
                strategy_grade VARCHAR(10),

                suggested_action VARCHAR(80),
                suggested_weight DOUBLE PRECISION,

                rationale TEXT,
                warnings TEXT,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_strategy_lab_runs (
                run_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                strategy_name VARCHAR(120),
                pair_count INTEGER,

                deploy_count INTEGER,
                watch_count INTEGER,
                avoid_count INTEGER,

                average_strategy_score DOUBLE PRECISION,
                average_expectancy_score DOUBLE PRECISION,
                average_risk_adjusted_score DOUBLE PRECISION,

                top_pair VARCHAR(20),
                top_signal VARCHAR(80),

                payload JSONB,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_strategy_lab_tenant_pair
            ON forex_strategy_lab_results(tenant_id, pair, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_strategy_lab_strategy
            ON forex_strategy_lab_results(strategy_name, strategy_signal, created_at DESC)
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

            rows = getattr(scan, "recommendations", [])

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

    def _strategy_score(
        self,
        pair: str,
        strategy_name: str,
    ) -> float:
        try:
            if hasattr(self.strategy_engine, "evaluate_strategy"):
                result = self.strategy_engine.evaluate_strategy(
                    pair=pair,
                    strategy_name=strategy_name,
                    save=False,
                )

                if isinstance(result, dict):
                    return self._safe_float(
                        result.get("strategy_score")
                        or result.get("conviction_score")
                        or result.get("score"),
                        50.0,
                    )

                return self._safe_float(
                    getattr(result, "strategy_score", None)
                    or getattr(result, "conviction_score", None)
                    or getattr(result, "score", None),
                    50.0,
                )

            if hasattr(self.strategy_engine, "analyze_pair"):
                result = self.strategy_engine.analyze_pair(
                    pair,
                    save=False,
                )

                return self._safe_float(
                    getattr(result, "strategy_score", None)
                    or getattr(result, "confidence_score", None),
                    50.0,
                )

            return 50.0

        except Exception:
            return 50.0

    def _execution_quality_score(
        self,
        pair: str,
    ) -> float:
        try:
            if hasattr(
                self.execution_quality_engine,
                "analyze_pair",
            ):
                result = self.execution_quality_engine.analyze_pair(
                    pair,
                    save=False,
                )

                return self._safe_float(
                    getattr(result, "execution_quality_score", None)
                    or getattr(result, "quality_score", None)
                    or getattr(result, "confidence_score", None),
                    50.0,
                )

            return 50.0

        except Exception:
            return 50.0

    def _optimized_weight(
        self,
        pair: str,
    ) -> float:
        try:
            run = self.portfolio_optimizer.optimize_portfolio(
                pairs=[pair],
                save=False,
            )

            allocations = getattr(run, "allocations", [])

            if not allocations:
                return 0.0

            row = allocations[0]

            if isinstance(row, dict):
                return self._safe_float(
                    row.get("optimized_weight"),
                    0.0,
                )

            return self._safe_float(
                getattr(row, "optimized_weight", None),
                0.0,
            )

        except Exception:
            return 0.0

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
        alpha_direction: str,
        alpha_score: float,
        recommendation_score: float,
        regime_score: float,
    ) -> str:
        direction = str(
            alpha_direction or ""
        ).upper()

        if direction in {
            "BULLISH",
            "BEARISH",
        }:
            return direction

        bullish = 0
        bearish = 0

        for score in [
            alpha_score,
            recommendation_score,
            regime_score,
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
        risk_adjusted_score: float,
        expectancy_score: float,
        win_probability: float,
        direction: str,
    ) -> str:
        if (
            risk_adjusted_score >= 82
            and expectancy_score >= 70
            and win_probability >= 58
            and direction == "BULLISH"
        ):
            return "DEPLOY_LONG_STRATEGY"

        if (
            risk_adjusted_score >= 82
            and expectancy_score >= 70
            and win_probability >= 58
            and direction == "BEARISH"
        ):
            return "DEPLOY_SHORT_STRATEGY"

        if (
            risk_adjusted_score >= 72
            and direction == "BULLISH"
        ):
            return "LONG_STRATEGY_WATCH"

        if (
            risk_adjusted_score >= 72
            and direction == "BEARISH"
        ):
            return "SHORT_STRATEGY_WATCH"

        if risk_adjusted_score >= 62:
            return "STRATEGY_MONITOR"

        return "AVOID_STRATEGY"

    def _suggested_action(
        self,
        signal: str,
    ) -> str:
        if signal == "DEPLOY_LONG_STRATEGY":
            return "DEPLOY_LONG"

        if signal == "DEPLOY_SHORT_STRATEGY":
            return "DEPLOY_SHORT"

        if signal in {
            "LONG_STRATEGY_WATCH",
            "SHORT_STRATEGY_WATCH",
            "STRATEGY_MONITOR",
        }:
            return "WATCH"

        return "AVOID"

    def _warnings(
        self,
        *,
        risk_score: float,
        execution_quality_score: float,
        optimizer_weight: float,
        win_probability: float,
    ) -> str:
        warnings: List[str] = []

        if risk_score > 55:
            warnings.append(
                "Risk score is elevated."
            )

        if execution_quality_score < 50:
            warnings.append(
                "Execution quality is below preferred threshold."
            )

        if optimizer_weight <= 0:
            warnings.append(
                "Portfolio optimizer assigned no weight."
            )

        if win_probability < 50:
            warnings.append(
                "Win probability is below 50%."
            )

        return " ".join(warnings)

    # =====================================================
    # Analysis
    # =====================================================

    def analyze_strategy(
        self,
        pair: str,
        *,
        strategy_name: str = "Institutional Alpha Strategy",
        save: bool = True,
    ) -> ForexStrategyLabResult:
        alpha = self.alpha_model.analyze_pair(
            pair,
            save=False,
        )

        regime = self.regime_engine.analyze_pair(
            pair,
            save=False,
        )

        alpha_score = self._safe_float(
            getattr(alpha, "alpha_score", None),
            50.0,
        )

        recommendation_score = self._recommendation_score(
            pair,
        )

        strategy_score = self._strategy_score(
            pair,
            strategy_name,
        )

        regime_score = self._safe_float(
            getattr(
                regime,
                "composite_regime_score",
                None,
            ),
            50.0,
        )

        execution_quality_score = self._execution_quality_score(
            pair,
        )

        optimizer_weight = self._optimized_weight(
            pair,
        )

        expected_return_score = self._clip(
            alpha_score * 0.35
            + recommendation_score * 0.20
            + strategy_score * 0.20
            + regime_score * 0.15
            + optimizer_weight * 2.0
        )

        risk_score = self._clip(
            max(
                0.0,
                70.0 - execution_quality_score,
            )
            + max(
                0.0,
                55.0 - regime_score,
            )
            * 0.35
            + max(
                0.0,
                60.0 - alpha_score,
            )
            * 0.25
        )

        risk_adjusted_score = self._clip(
            expected_return_score
            - risk_score * 0.35
            + execution_quality_score * 0.20
        )

        win_probability = self._clip(
            45.0
            + (
                risk_adjusted_score
                - 50.0
            )
            * 0.35
            + (
                alpha_score
                - 50.0
            )
            * 0.15
        )

        payoff_ratio = round(
            max(
                0.5,
                min(
                    4.0,
                    1.0
                    + (
                        risk_adjusted_score
                        - 50.0
                    )
                    / 40.0,
                ),
            ),
            2,
        )

        expectancy_score = self._clip(
            win_probability * payoff_ratio
            - (
                100.0
                - win_probability
            )
            * 0.65
        )

        direction = self._direction(
            alpha_direction=getattr(
                alpha,
                "alpha_direction",
                "NEUTRAL",
            ),
            alpha_score=alpha_score,
            recommendation_score=recommendation_score,
            regime_score=regime_score,
        )

        signal = self._signal(
            risk_adjusted_score=risk_adjusted_score,
            expectancy_score=expectancy_score,
            win_probability=win_probability,
            direction=direction,
        )

        suggested_action = self._suggested_action(
            signal,
        )

        suggested_weight = (
            optimizer_weight
            if suggested_action
            in {
                "DEPLOY_LONG",
                "DEPLOY_SHORT",
            }
            else min(
                optimizer_weight,
                1.0,
            )
        )

        warnings = self._warnings(
            risk_score=risk_score,
            execution_quality_score=execution_quality_score,
            optimizer_weight=optimizer_weight,
            win_probability=win_probability,
        )

        rationale = (
            f"{strategy_name} generated {signal} for {pair}. "
            f"Risk-adjusted score {round(risk_adjusted_score, 2)}, "
            f"alpha {round(alpha_score, 2)}, strategy score {round(strategy_score, 2)}, "
            f"regime {round(regime_score, 2)}, execution quality {round(execution_quality_score, 2)}, "
            f"and optimizer weight {round(optimizer_weight, 2)}%."
        )

        result = ForexStrategyLabResult(
            result_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            strategy_name=strategy_name,
            pair=pair,

            alpha_score=round(alpha_score, 2),
            recommendation_score=round(recommendation_score, 2),
            strategy_score=round(strategy_score, 2),
            regime_score=round(regime_score, 2),
            execution_quality_score=round(execution_quality_score, 2),
            optimizer_weight=round(optimizer_weight, 4),

            expected_return_score=round(expected_return_score, 2),
            risk_score=round(risk_score, 2),
            risk_adjusted_score=round(risk_adjusted_score, 2),

            win_probability=round(win_probability, 2),
            payoff_ratio=payoff_ratio,
            expectancy_score=round(expectancy_score, 2),

            strategy_direction=direction,
            strategy_signal=signal,
            strategy_grade=self._grade(
                risk_adjusted_score,
            ),

            suggested_action=suggested_action,
            suggested_weight=round(
                suggested_weight,
                4,
            ),

            rationale=rationale,
            warnings=warnings,

            created_at=datetime.now(
                timezone.utc
            ),
        )

        if save:
            self.save_result(result)

        return result

    # =====================================================
    # Run Lab
    # =====================================================

    def run_lab(
        self,
        pairs: Optional[List[str]] = None,
        *,
        strategy_name: str = "Institutional Alpha Strategy",
        save: bool = True,
    ) -> ForexStrategyLabRun:
        pairs = pairs or DEFAULT_PAIRS

        results: List[ForexStrategyLabResult] = []

        for pair in pairs:
            try:
                results.append(
                    self.analyze_strategy(
                        pair,
                        strategy_name=strategy_name,
                        save=save,
                    )
                )
            except Exception:
                continue

        results = sorted(
            results,
            key=lambda item: (
                item.risk_adjusted_score,
                item.expectancy_score,
                item.win_probability,
            ),
            reverse=True,
        )

        deploy_count = len(
            [
                item
                for item in results
                if item.strategy_signal
                in {
                    "DEPLOY_LONG_STRATEGY",
                    "DEPLOY_SHORT_STRATEGY",
                }
            ]
        )

        watch_count = len(
            [
                item
                for item in results
                if item.strategy_signal
                in {
                    "LONG_STRATEGY_WATCH",
                    "SHORT_STRATEGY_WATCH",
                    "STRATEGY_MONITOR",
                }
            ]
        )

        avoid_count = len(
            [
                item
                for item in results
                if item.strategy_signal
                == "AVOID_STRATEGY"
            ]
        )

        average_strategy = (
            sum(
                item.strategy_score
                for item in results
            )
            / len(results)
            if results
            else 0.0
        )

        average_expectancy = (
            sum(
                item.expectancy_score
                for item in results
            )
            / len(results)
            if results
            else 0.0
        )

        average_risk_adjusted = (
            sum(
                item.risk_adjusted_score
                for item in results
            )
            / len(results)
            if results
            else 0.0
        )

        run = ForexStrategyLabRun(
            run_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            strategy_name=strategy_name,
            pair_count=len(results),

            deploy_count=deploy_count,
            watch_count=watch_count,
            avoid_count=avoid_count,

            average_strategy_score=round(
                average_strategy,
                2,
            ),

            average_expectancy_score=round(
                average_expectancy,
                2,
            ),

            average_risk_adjusted_score=round(
                average_risk_adjusted,
                2,
            ),

            top_pair=results[0].pair if results else None,
            top_signal=results[0].strategy_signal if results else None,

            results=[
                item.to_dict()
                for item in results
            ],

            created_at=datetime.now(
                timezone.utc
            ),
        )

        if save:
            self.save_run(run)

        return run

    # =====================================================
    # Persistence
    # =====================================================

    def save_result(
        self,
        result: ForexStrategyLabResult,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        self.db.execute(
            """
            INSERT INTO forex_strategy_lab_results (
                result_id,

                tenant_id,
                user_id,
                portfolio_id,

                strategy_name,
                pair,

                alpha_score,
                recommendation_score,
                strategy_score,
                regime_score,
                execution_quality_score,
                optimizer_weight,

                expected_return_score,
                risk_score,
                risk_adjusted_score,

                win_probability,
                payoff_ratio,
                expectancy_score,

                strategy_direction,
                strategy_signal,
                strategy_grade,

                suggested_action,
                suggested_weight,

                rationale,
                warnings,

                created_at
            )
            VALUES (
                :result_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :strategy_name,
                :pair,

                :alpha_score,
                :recommendation_score,
                :strategy_score,
                :regime_score,
                :execution_quality_score,
                :optimizer_weight,

                :expected_return_score,
                :risk_score,
                :risk_adjusted_score,

                :win_probability,
                :payoff_ratio,
                :expectancy_score,

                :strategy_direction,
                :strategy_signal,
                :strategy_grade,

                :suggested_action,
                :suggested_weight,

                :rationale,
                :warnings,

                :created_at
            )
            """,
            result.to_dict(),
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    def save_run(
        self,
        run: ForexStrategyLabRun,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        payload = run.to_dict()

        self.db.execute(
            """
            INSERT INTO forex_strategy_lab_runs (
                run_id,

                tenant_id,
                user_id,
                portfolio_id,

                strategy_name,
                pair_count,

                deploy_count,
                watch_count,
                avoid_count,

                average_strategy_score,
                average_expectancy_score,
                average_risk_adjusted_score,

                top_pair,
                top_signal,

                payload,

                created_at
            )
            VALUES (
                :run_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :strategy_name,
                :pair_count,

                :deploy_count,
                :watch_count,
                :avoid_count,

                :average_strategy_score,
                :average_expectancy_score,
                :average_risk_adjusted_score,

                :top_pair,
                :top_signal,

                :payload,

                :created_at
            )
            """,
            {
                **payload,
                "payload": payload,
            },
        )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # History
    # =====================================================

    def load_results(
        self,
        *,
        pair: Optional[str] = None,
        strategy_name: Optional[str] = None,
        signal: str = "ALL",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_strategy_lab_results
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

        if strategy_name:
            sql += """
            AND strategy_name = :strategy_name
            """
            params["strategy_name"] = strategy_name

        if signal and signal.upper() != "ALL":
            sql += """
            AND strategy_signal = :signal
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

    def load_runs(
        self,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        rows = (
            self.db.execute(
                """
                SELECT *
                FROM forex_strategy_lab_runs
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {
                    "tenant_id": self.tenant_id,
                    "limit": int(limit),
                },
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]


def get_forex_strategy_lab(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexStrategyLab:
    return ForexStrategyLab(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )