# modules/forex/forex_portfolio_optimizer.py

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

    from modules.forex.forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
    )

    from modules.forex.forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from modules.forex.forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
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

    from forex_correlation_engine import (
        ForexCorrelationEngine,
        get_forex_correlation_engine,
    )

    from forex_liquidity_engine import (
        ForexLiquidityEngine,
        get_forex_liquidity_engine,
    )

    from forex_regime_detection_engine import (
        ForexRegimeDetectionEngine,
        get_forex_regime_detection_engine,
    )


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


@dataclass
class ForexOptimizedAllocation:
    allocation_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair: str

    alpha_score: float
    confidence_score: float
    liquidity_score: float
    regime_score: float
    correlation_penalty: float
    risk_penalty: float

    raw_weight: float
    optimized_weight: float
    max_weight: float
    risk_budget: float

    position_bias: str
    allocation_signal: str

    rationale: str
    warnings: str

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


@dataclass
class ForexOptimizationRun:
    optimization_id: str

    tenant_id: Optional[str]
    user_id: Optional[str]
    portfolio_id: Optional[str]

    pair_count: int
    allocated_pair_count: int

    total_target_weight: float
    average_alpha_score: float
    average_confidence_score: float

    long_weight: float
    short_weight: float
    neutral_weight: float

    portfolio_risk_score: float
    concentration_score: float
    diversification_score: float

    optimization_status: str

    allocations: List[Dict[str, Any]]

    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class ForexPortfolioOptimizer:
    """
    Forex Portfolio Optimizer

    Converts alpha signals into portfolio weights using:
    - Alpha score
    - Confidence
    - Liquidity
    - Regime strength
    - Correlation penalty
    - Risk budget
    - Concentration controls

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
        correlation_engine: Optional[ForexCorrelationEngine] = None,
        liquidity_engine: Optional[ForexLiquidityEngine] = None,
        regime_engine: Optional[ForexRegimeDetectionEngine] = None,
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

        self.correlation_engine = (
            correlation_engine
            or get_forex_correlation_engine(
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
            CREATE TABLE IF NOT EXISTS forex_portfolio_optimizations (
                optimization_id VARCHAR(64) PRIMARY KEY,

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair_count INTEGER,
                allocated_pair_count INTEGER,

                total_target_weight DOUBLE PRECISION,
                average_alpha_score DOUBLE PRECISION,
                average_confidence_score DOUBLE PRECISION,

                long_weight DOUBLE PRECISION,
                short_weight DOUBLE PRECISION,
                neutral_weight DOUBLE PRECISION,

                portfolio_risk_score DOUBLE PRECISION,
                concentration_score DOUBLE PRECISION,
                diversification_score DOUBLE PRECISION,

                optimization_status VARCHAR(60),

                payload JSONB,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS forex_portfolio_allocations (
                allocation_id VARCHAR(64) PRIMARY KEY,

                optimization_id VARCHAR(64),

                tenant_id VARCHAR(100),
                user_id VARCHAR(100),
                portfolio_id VARCHAR(100),

                pair VARCHAR(20),

                alpha_score DOUBLE PRECISION,
                confidence_score DOUBLE PRECISION,
                liquidity_score DOUBLE PRECISION,
                regime_score DOUBLE PRECISION,
                correlation_penalty DOUBLE PRECISION,
                risk_penalty DOUBLE PRECISION,

                raw_weight DOUBLE PRECISION,
                optimized_weight DOUBLE PRECISION,
                max_weight DOUBLE PRECISION,
                risk_budget DOUBLE PRECISION,

                position_bias VARCHAR(40),
                allocation_signal VARCHAR(80),

                rationale TEXT,
                warnings TEXT,

                created_at TIMESTAMP
            )
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_optimizer_tenant_created
            ON forex_portfolio_optimizations(tenant_id, created_at DESC)
            """
        )

        self.db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_forex_allocations_optimization
            ON forex_portfolio_allocations(optimization_id)
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
        default: float = 0.0,
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

    def _weight_clip(
        self,
        value: float,
        max_weight: float,
    ) -> float:
        return max(0.0, min(float(value), float(max_weight)))

    def _correlation_penalty(
        self,
        pair: str,
        selected_pairs: List[str],
    ) -> float:
        if not selected_pairs:
            return 0.0

        penalties = []

        for other_pair in selected_pairs:
            if other_pair == pair:
                continue

            try:
                corr = self.correlation_engine.analyze_pair_correlation(
                    pair,
                    other_pair,
                    save=False,
                )
                penalties.append(
                    self._safe_float(
                        getattr(corr, "correlation_score", 50.0),
                        50.0,
                    )
                )
            except Exception:
                continue

        if not penalties:
            return 0.0

        avg_corr = sum(penalties) / len(penalties)

        if avg_corr <= 55:
            return 0.0

        return self._clip(
            (avg_corr - 55.0) * 0.75,
            0.0,
            35.0,
        )

    def _allocation_signal(
        self,
        *,
        weight: float,
        alpha_score: float,
        confidence_score: float,
        liquidity_score: float,
        position_bias: str,
    ) -> str:
        if weight <= 0:
            return "NO_ALLOCATION"

        if (
            weight >= 4.0
            and alpha_score >= 85
            and confidence_score >= 75
            and liquidity_score >= 60
            and position_bias == "LONG"
        ):
            return "CORE_LONG_ALLOCATION"

        if (
            weight >= 4.0
            and alpha_score >= 85
            and confidence_score >= 75
            and liquidity_score >= 60
            and position_bias == "SHORT"
        ):
            return "CORE_SHORT_ALLOCATION"

        if position_bias == "LONG":
            return "SATELLITE_LONG_ALLOCATION"

        if position_bias == "SHORT":
            return "SATELLITE_SHORT_ALLOCATION"

        return "TACTICAL_MONITOR"

    def _warnings(
        self,
        *,
        liquidity_score: float,
        correlation_penalty: float,
        risk_penalty: float,
        optimized_weight: float,
    ) -> str:
        warnings: List[str] = []

        if liquidity_score < 45:
            warnings.append(
                "Liquidity is below preferred allocation threshold."
            )

        if correlation_penalty > 20:
            warnings.append(
                "High correlation penalty reduced allocation."
            )

        if risk_penalty > 25:
            warnings.append(
                "Risk penalty materially reduced allocation."
            )

        if optimized_weight <= 0:
            warnings.append(
                "No allocation produced after optimization constraints."
            )

        return " ".join(warnings)

    def _normalize_weights(
        self,
        allocations: List[ForexOptimizedAllocation],
        *,
        max_total_weight: float,
    ) -> List[ForexOptimizedAllocation]:
        total_weight = sum(
            item.optimized_weight
            for item in allocations
        )

        if total_weight <= 0:
            return allocations

        if total_weight <= max_total_weight:
            return allocations

        scale = max_total_weight / total_weight

        normalized = []

        for item in allocations:
            data = item.to_dict()
            data["optimized_weight"] = round(
                item.optimized_weight * scale,
                4,
            )
            data["rationale"] = (
                item.rationale
                + f" Weight scaled by {round(scale, 4)} to respect total portfolio target."
            )

            normalized.append(
                ForexOptimizedAllocation(
                    allocation_id=data["allocation_id"],
                    tenant_id=data["tenant_id"],
                    user_id=data["user_id"],
                    portfolio_id=data["portfolio_id"],
                    pair=data["pair"],
                    alpha_score=data["alpha_score"],
                    confidence_score=data["confidence_score"],
                    liquidity_score=data["liquidity_score"],
                    regime_score=data["regime_score"],
                    correlation_penalty=data["correlation_penalty"],
                    risk_penalty=data["risk_penalty"],
                    raw_weight=data["raw_weight"],
                    optimized_weight=data["optimized_weight"],
                    max_weight=data["max_weight"],
                    risk_budget=data["risk_budget"],
                    position_bias=data["position_bias"],
                    allocation_signal=data["allocation_signal"],
                    rationale=data["rationale"],
                    warnings=data["warnings"],
                    created_at=item.created_at,
                )
            )

        return normalized

    # =====================================================
    # Optimization
    # =====================================================

    def optimize_portfolio(
        self,
        pairs: Optional[List[str]] = None,
        *,
        max_total_weight: float = 25.0,
        max_pair_weight: float = 5.0,
        min_alpha_score: float = 65.0,
        save: bool = True,
    ) -> ForexOptimizationRun:
        pairs = pairs or DEFAULT_PAIRS

        alpha_run = self.alpha_model.run_alpha_model(
            pairs=pairs,
            save=False,
        )

        alpha_signals = getattr(
            alpha_run,
            "signals",
            [],
        )

        allocations: List[ForexOptimizedAllocation] = []
        selected_pairs: List[str] = []

        for row in alpha_signals:
            pair = row.get("pair")

            alpha_score = self._safe_float(
                row.get("alpha_score"),
                0.0,
            )

            if alpha_score < min_alpha_score:
                continue

            confidence_score = self._safe_float(
                row.get("confidence_score"),
                0.0,
            )

            position_bias = str(
                row.get("position_bias", "FLAT")
            ).upper()

            try:
                liquidity = self.liquidity_engine.analyze_pair(
                    pair,
                    save=False,
                )
                liquidity_score = self._safe_float(
                    getattr(liquidity, "liquidity_score", None),
                    50.0,
                )
            except Exception:
                liquidity_score = self._safe_float(
                    row.get("liquidity_score"),
                    50.0,
                )

            try:
                regime = self.regime_engine.analyze_pair(
                    pair,
                    save=False,
                )
                regime_score = self._safe_float(
                    getattr(
                        regime,
                        "composite_regime_score",
                        None,
                    ),
                    50.0,
                )
            except Exception:
                regime_score = self._safe_float(
                    row.get("regime_score"),
                    50.0,
                )

            correlation_penalty = self._correlation_penalty(
                pair,
                selected_pairs,
            )

            risk_penalty = self._clip(
                max(
                    0.0,
                    60.0 - liquidity_score,
                )
                + correlation_penalty * 0.50
                + max(
                    0.0,
                    50.0 - regime_score,
                )
                * 0.20,
                0.0,
                50.0,
            )

            raw_weight = (
                alpha_score * 0.045
                + confidence_score * 0.030
                + liquidity_score * 0.015
            )

            adjusted_weight = (
                raw_weight
                - risk_penalty * 0.04
                - correlation_penalty * 0.03
            )

            adjusted_weight = max(
                0.0,
                adjusted_weight,
            )

            pair_max_weight = min(
                max_pair_weight,
                self._safe_float(
                    row.get("max_risk_weight"),
                    max_pair_weight,
                )
                or max_pair_weight,
            )

            optimized_weight = self._weight_clip(
                adjusted_weight,
                pair_max_weight,
            )

            allocation_signal = self._allocation_signal(
                weight=optimized_weight,
                alpha_score=alpha_score,
                confidence_score=confidence_score,
                liquidity_score=liquidity_score,
                position_bias=position_bias,
            )

            rationale = (
                f"Optimized weight {round(optimized_weight, 2)}% "
                f"from alpha {round(alpha_score, 2)}, "
                f"confidence {round(confidence_score, 2)}, "
                f"liquidity {round(liquidity_score, 2)}, "
                f"regime {round(regime_score, 2)}, "
                f"correlation penalty {round(correlation_penalty, 2)}, "
                f"and risk penalty {round(risk_penalty, 2)}."
            )

            warnings = self._warnings(
                liquidity_score=liquidity_score,
                correlation_penalty=correlation_penalty,
                risk_penalty=risk_penalty,
                optimized_weight=optimized_weight,
            )

            allocation = ForexOptimizedAllocation(
                allocation_id=str(uuid.uuid4()),

                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,

                pair=pair,

                alpha_score=round(alpha_score, 2),
                confidence_score=round(confidence_score, 2),
                liquidity_score=round(liquidity_score, 2),
                regime_score=round(regime_score, 2),
                correlation_penalty=round(correlation_penalty, 2),
                risk_penalty=round(risk_penalty, 2),

                raw_weight=round(raw_weight, 4),
                optimized_weight=round(optimized_weight, 4),
                max_weight=round(pair_max_weight, 4),
                risk_budget=round(
                    min(
                        100.0,
                        optimized_weight
                        / max_pair_weight
                        * 100.0
                        if max_pair_weight > 0
                        else 0.0,
                    ),
                    2,
                ),

                position_bias=position_bias,
                allocation_signal=allocation_signal,

                rationale=rationale,
                warnings=warnings,

                created_at=datetime.now(timezone.utc),
            )

            allocations.append(allocation)

            if optimized_weight > 0:
                selected_pairs.append(pair)

        allocations = sorted(
            allocations,
            key=lambda item: (
                item.optimized_weight,
                item.alpha_score,
            ),
            reverse=True,
        )

        allocations = self._normalize_weights(
            allocations,
            max_total_weight=max_total_weight,
        )

        total_weight = sum(
            item.optimized_weight
            for item in allocations
        )

        allocated_count = len(
            [
                item
                for item in allocations
                if item.optimized_weight > 0
            ]
        )

        long_weight = sum(
            item.optimized_weight
            for item in allocations
            if item.position_bias == "LONG"
        )

        short_weight = sum(
            item.optimized_weight
            for item in allocations
            if item.position_bias == "SHORT"
        )

        neutral_weight = total_weight - long_weight - short_weight

        average_alpha = (
            sum(
                item.alpha_score
                for item in allocations
            )
            / len(allocations)
            if allocations
            else 0.0
        )

        average_confidence = (
            sum(
                item.confidence_score
                for item in allocations
            )
            / len(allocations)
            if allocations
            else 0.0
        )

        concentration_score = (
            max(
                [
                    item.optimized_weight
                    for item in allocations
                ]
            )
            if allocations
            else 0.0
        )

        diversification_score = self._clip(
            allocated_count
            / max(
                1,
                len(pairs),
            )
            * 100.0
        )

        portfolio_risk_score = self._clip(
            sum(
                item.risk_penalty
                for item in allocations
            )
            / len(allocations)
            if allocations
            else 0.0
        )

        if allocated_count == 0:
            status = "NO_ALLOCATIONS"

        elif portfolio_risk_score >= 35:
            status = "HIGH_RISK_ALLOCATION"

        elif total_weight > max_total_weight:
            status = "OVER_ALLOCATED"

        else:
            status = "OPTIMIZED"

        run = ForexOptimizationRun(
            optimization_id=str(uuid.uuid4()),

            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,

            pair_count=len(pairs),
            allocated_pair_count=allocated_count,

            total_target_weight=round(total_weight, 4),
            average_alpha_score=round(average_alpha, 2),
            average_confidence_score=round(average_confidence, 2),

            long_weight=round(long_weight, 4),
            short_weight=round(short_weight, 4),
            neutral_weight=round(neutral_weight, 4),

            portfolio_risk_score=round(portfolio_risk_score, 2),
            concentration_score=round(concentration_score, 2),
            diversification_score=round(diversification_score, 2),

            optimization_status=status,

            allocations=[
                item.to_dict()
                for item in allocations
            ],

            created_at=datetime.now(timezone.utc),
        )

        if save:
            self.save_optimization(run)

        return run

    # =====================================================
    # Persistence
    # =====================================================

    def save_optimization(
        self,
        run: ForexOptimizationRun,
    ) -> None:
        if self.db is None:
            return

        self.ensure_tables()

        payload = run.to_dict()

        self.db.execute(
            """
            INSERT INTO forex_portfolio_optimizations (
                optimization_id,

                tenant_id,
                user_id,
                portfolio_id,

                pair_count,
                allocated_pair_count,

                total_target_weight,
                average_alpha_score,
                average_confidence_score,

                long_weight,
                short_weight,
                neutral_weight,

                portfolio_risk_score,
                concentration_score,
                diversification_score,

                optimization_status,

                payload,

                created_at
            )
            VALUES (
                :optimization_id,

                :tenant_id,
                :user_id,
                :portfolio_id,

                :pair_count,
                :allocated_pair_count,

                :total_target_weight,
                :average_alpha_score,
                :average_confidence_score,

                :long_weight,
                :short_weight,
                :neutral_weight,

                :portfolio_risk_score,
                :concentration_score,
                :diversification_score,

                :optimization_status,

                :payload,

                :created_at
            )
            """,
            {
                **payload,
                "payload": payload,
            },
        )

        for allocation in run.allocations:
            self.db.execute(
                """
                INSERT INTO forex_portfolio_allocations (
                    allocation_id,

                    optimization_id,

                    tenant_id,
                    user_id,
                    portfolio_id,

                    pair,

                    alpha_score,
                    confidence_score,
                    liquidity_score,
                    regime_score,
                    correlation_penalty,
                    risk_penalty,

                    raw_weight,
                    optimized_weight,
                    max_weight,
                    risk_budget,

                    position_bias,
                    allocation_signal,

                    rationale,
                    warnings,

                    created_at
                )
                VALUES (
                    :allocation_id,

                    :optimization_id,

                    :tenant_id,
                    :user_id,
                    :portfolio_id,

                    :pair,

                    :alpha_score,
                    :confidence_score,
                    :liquidity_score,
                    :regime_score,
                    :correlation_penalty,
                    :risk_penalty,

                    :raw_weight,
                    :optimized_weight,
                    :max_weight,
                    :risk_budget,

                    :position_bias,
                    :allocation_signal,

                    :rationale,
                    :warnings,

                    :created_at
                )
                """,
                {
                    **allocation,
                    "optimization_id": run.optimization_id,
                },
            )

        if hasattr(self.db, "commit"):
            self.db.commit()

    # =====================================================
    # History
    # =====================================================

    def load_optimizations(
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
                FROM forex_portfolio_optimizations
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

    def load_allocations(
        self,
        *,
        optimization_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []

        self.ensure_tables()

        sql = """
        SELECT *
        FROM forex_portfolio_allocations
        WHERE tenant_id = :tenant_id
        """

        params: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
        }

        if optimization_id:
            sql += """
            AND optimization_id = :optimization_id
            """
            params["optimization_id"] = optimization_id

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


def get_forex_portfolio_optimizer(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    db: Any = None,
) -> ForexPortfolioOptimizer:
    return ForexPortfolioOptimizer(
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        db=db,
    )