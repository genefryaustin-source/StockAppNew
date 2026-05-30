"""
modules/portfolio/ai_portfolio_orchestrator.py

Autonomous institutional AI portfolio intelligence.

Phase 1:
- AI portfolio candidates
- dynamic target weighting
- conviction-aware sizing
- risk-aware allocation
- portfolio construction primitives

Future:
- autonomous rebalancing
- hedge overlays
- exposure balancing
- sector optimization
- macro-aware allocation
- volatility targeting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import math


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:
            return default

        value = float(value)

        if math.isnan(value):
            return default

        if math.isinf(value):
            return default

        return value

    except Exception:

        return default


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


# ---------------------------------------------------
# AI PORTFOLIO CANDIDATE
# ---------------------------------------------------

@dataclass
class AIPortfolioCandidate:

    symbol: str

    sector: str = "Unknown"

    ai_score: float = 50.0

    consensus_score: float = 50.0

    confidence: float = 50.0

    risk_score: float = 50.0

    volatility: float = 25.0

    target_weight: float = 0.0

    current_weight: float = 0.0

    expected_return: float = 0.0

    expected_alpha: float = 0.0

    downside_risk: float = 0.0

    conviction_label: str = "Neutral"

    thesis: str = ""

    bullish_factors: List[str] = field(
        default_factory=list
    )

    bearish_factors: List[str] = field(
        default_factory=list
    )

    risk_flags: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    # ---------------------------------------------------
    # COMPOSITE CONVICTION
    # ---------------------------------------------------

    @property
    def composite_conviction(
        self,
    ) -> float:

        score = (
            (
                self.ai_score * 0.45
            )
            + (
                self.consensus_score * 0.30
            )
            + (
                self.confidence * 0.25
            )
        )

        score -= (
            self.risk_score * 0.20
        )

        return round(
            _clamp(score),
            4,
        )

    # ---------------------------------------------------
    # RISK-ADJUSTED SCORE
    # ---------------------------------------------------

    @property
    def risk_adjusted_score(
        self,
    ) -> float:

        score = (
            self.composite_conviction
            - (
                self.volatility * 0.15
            )
        )

        return round(
            _clamp(score),
            4,
        )

    # ---------------------------------------------------
    # POSITION SIZING SCORE
    # ---------------------------------------------------

    @property
    def sizing_score(
        self,
    ) -> float:

        score = (
            (
                self.risk_adjusted_score
                * 0.60
            )
            + (
                self.confidence
                * 0.25
            )
            + (
                self.expected_alpha
                * 100.0
                * 0.15
            )
        )

        return round(
            _clamp(score),
            4,
        )

    # ---------------------------------------------------
    # RISK CLASSIFICATION
    # ---------------------------------------------------

    @property
    def risk_classification(
        self,
    ) -> str:

        if self.risk_score >= 80:
            return "Extreme Risk"

        if self.risk_score >= 65:
            return "High Risk"

        if self.risk_score >= 45:
            return "Moderate Risk"

        return "Controlled Risk"

    # ---------------------------------------------------
    # CONVICTION CLASSIFICATION
    # ---------------------------------------------------

    @property
    def conviction_classification(
        self,
    ) -> str:

        score = self.composite_conviction

        if score >= 85:
            return "Elite AI Conviction"

        if score >= 75:
            return "High Conviction"

        if score >= 65:
            return "Institutional Conviction"

        if score >= 55:
            return "Constructive"

        if score >= 45:
            return "Neutral"

        return "Weak Conviction"

    # ---------------------------------------------------
    # POSITION ACTION
    # ---------------------------------------------------

    @property
    def recommended_action(
        self,
    ) -> str:

        delta = (
            self.target_weight
            - self.current_weight
        )

        if delta >= 3:
            return "Increase Position"

        if delta >= 1:
            return "Accumulate"

        if delta <= -3:
            return "Reduce Position"

        if delta <= -1:
            return "Trim Exposure"

        return "Hold Position"

    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {

            "symbol":
                self.symbol,

            "sector":
                self.sector,

            "ai_score":
                round(
                    self.ai_score,
                    4,
                ),

            "consensus_score":
                round(
                    self.consensus_score,
                    4,
                ),

            "confidence":
                round(
                    self.confidence,
                    4,
                ),

            "risk_score":
                round(
                    self.risk_score,
                    4,
                ),

            "volatility":
                round(
                    self.volatility,
                    4,
                ),

            "target_weight":
                round(
                    self.target_weight,
                    4,
                ),

            "current_weight":
                round(
                    self.current_weight,
                    4,
                ),

            "expected_return":
                round(
                    self.expected_return,
                    4,
                ),

            "expected_alpha":
                round(
                    self.expected_alpha,
                    4,
                ),

            "downside_risk":
                round(
                    self.downside_risk,
                    4,
                ),

            "conviction_label":
                self.conviction_label,

            "composite_conviction":
                self.composite_conviction,

            "risk_adjusted_score":
                self.risk_adjusted_score,

            "sizing_score":
                self.sizing_score,

            "risk_classification":
                self.risk_classification,

            "conviction_classification":
                self.conviction_classification,

            "recommended_action":
                self.recommended_action,

            "bullish_factors":
                self.bullish_factors,

            "bearish_factors":
                self.bearish_factors,

            "risk_flags":
                self.risk_flags,

            "thesis":
                self.thesis,

            "created_at":
                self.created_at,
        }

    # ---------------------------------------------------
    # AI PORTFOLIO CONSTRUCTION
    # ---------------------------------------------------

    def construct_ai_portfolio(

            candidates: List[AIPortfolioCandidate],

            max_positions: int = 20,

            max_position_weight: float = 12.0,

            min_position_weight: float = 1.0,

            sector_max_weight: float = 30.0,

            cash_buffer: float = 5.0,

    ) -> List[AIPortfolioCandidate]:

        if not candidates:
            return []

        # -----------------------------------
        # SORT BY SIZING SCORE
        # -----------------------------------

        ranked = sorted(

            candidates,

            key=lambda x: (
                x.sizing_score,
                x.composite_conviction,
            ),

            reverse=True,
        )

        ranked = ranked[:max_positions]

        if not ranked:
            return []

        # -----------------------------------
        # RAW SCORE TOTAL
        # -----------------------------------

        total_score = sum(

            max(
                c.sizing_score,
                0.01,
            )

            for c in ranked
        )

        if total_score <= 0:
            return ranked

        # -----------------------------------
        # INITIAL WEIGHTS
        # -----------------------------------

        for c in ranked:
            raw_weight = (
                                 c.sizing_score
                                 / total_score
                         ) * (
                                 100.0 - cash_buffer
                         )

            c.target_weight = round(

                _clamp(
                    raw_weight,
                    min_position_weight,
                    max_position_weight,
                ),

                4,
            )

        # -----------------------------------
        # SECTOR EXPOSURE CONTROL
        # -----------------------------------

        sector_totals = {}

        for c in ranked:
            sector = c.sector or "Unknown"

            sector_totals.setdefault(
                sector,
                0.0,
            )

            sector_totals[
                sector
            ] += c.target_weight

        # -----------------------------------
        # REDUCE OVER-CONCENTRATION
        # -----------------------------------

        for c in ranked:

            sector = c.sector or "Unknown"

            sector_weight = sector_totals.get(
                sector,
                0.0,
            )

            if sector_weight <= sector_max_weight:
                continue

            reduction_ratio = (
                    sector_max_weight
                    / sector_weight
            )

            c.target_weight *= reduction_ratio

        # -----------------------------------
        # RENORMALIZE
        # -----------------------------------

        total_alloc = sum(
            c.target_weight
            for c in ranked
        )

        if total_alloc > 0:

            scale = (
                    (100.0 - cash_buffer)
                    / total_alloc
            )

            for c in ranked:
                c.target_weight *= scale

                c.target_weight = round(
                    c.target_weight,
                    4,
                )

        # -----------------------------------
        # FINAL CLEANUP
        # -----------------------------------

        ranked = [

            c for c in ranked

            if c.target_weight
               >= min_position_weight
        ]

        ranked = sorted(

            ranked,

            key=lambda x: x.target_weight,

            reverse=True,
        )

        return ranked

    # ---------------------------------------------------
    # PORTFOLIO RISK SUMMARY
    # ---------------------------------------------------

    def portfolio_risk_summary(
            portfolio: List[AIPortfolioCandidate],
    ) -> Dict[str, Any]:

        if not portfolio:
            return {
                "total_positions": 0,
                "total_weight": 0.0,
                "cash_buffer": 100.0,
                "sector_exposure": {},
                "risk_distribution": {},
                "top_positions": [],
                "portfolio_volatility": 0.0,
                "portfolio_risk_score": 0.0,
                "concentration_risk": "Unknown",
                "macro_sensitivity": "Unknown",
                "conviction_strength": "Unknown",
            }

        # -----------------------------------
        # BASIC METRICS
        # -----------------------------------

        total_weight = sum(
            c.target_weight
            for c in portfolio
        )

        cash_buffer = max(
            0.0,
            100.0 - total_weight,
        )

        # -----------------------------------
        # SECTOR EXPOSURE
        # -----------------------------------

        sector_exposure = {}

        for c in portfolio:
            sector = c.sector or "Unknown"

            sector_exposure.setdefault(
                sector,
                0.0,
            )

            sector_exposure[
                sector
            ] += c.target_weight

        sector_exposure = {

            k: round(v, 4)

            for k, v in sorted(

                sector_exposure.items(),

                key=lambda x: x[1],

                reverse=True,
            )
        }

        # -----------------------------------
        # RISK DISTRIBUTION
        # -----------------------------------

        risk_distribution = {

            "Controlled Risk": 0,

            "Moderate Risk": 0,

            "High Risk": 0,

            "Extreme Risk": 0,
        }

        for c in portfolio:
            risk_distribution[
                c.risk_classification
            ] += 1

        # -----------------------------------
        # TOP POSITIONS
        # -----------------------------------

        top_positions = sorted(

            portfolio,

            key=lambda x: x.target_weight,

            reverse=True,
        )[:5]

        top_positions = [

            {
                "symbol": p.symbol,
                "weight": round(
                    p.target_weight,
                    4,
                ),
                "conviction":
                    p.conviction_classification,
            }

            for p in top_positions
        ]

        # -----------------------------------
        # PORTFOLIO VOLATILITY
        # -----------------------------------

        weighted_volatility = 0.0

        for c in portfolio:
            weighted_volatility += (

                    c.volatility
                    * (
                            c.target_weight
                            / 100.0
                    )
            )

        portfolio_volatility = round(
            weighted_volatility,
            4,
        )

        # -----------------------------------
        # PORTFOLIO RISK SCORE
        # -----------------------------------

        weighted_risk = 0.0

        for c in portfolio:
            weighted_risk += (

                    c.risk_score
                    * (
                            c.target_weight
                            / 100.0
                    )
            )

        portfolio_risk_score = round(
            weighted_risk,
            4,
        )

        # -----------------------------------
        # CONCENTRATION RISK
        # -----------------------------------

        largest_position = max(

            (
                c.target_weight
                for c in portfolio
            ),

            default=0.0,
        )

        largest_sector = max(

            sector_exposure.values(),

            default=0.0,
        )

        if (
                largest_position >= 15
                or largest_sector >= 40
        ):

            concentration_risk = "High"

        elif (
                largest_position >= 10
                or largest_sector >= 30
        ):

            concentration_risk = "Moderate"

        else:

            concentration_risk = "Controlled"

        # -----------------------------------
        # MACRO SENSITIVITY
        # -----------------------------------

        tech_weight = sum(

            c.target_weight

            for c in portfolio

            if (
                    c.sector
                    and str(c.sector).lower()
                    in {
                        "technology",
                        "semiconductors",
                        "communication services",
                    }
            )
        )

        defensive_weight = sum(

            c.target_weight

            for c in portfolio

            if (
                    c.sector
                    and str(c.sector).lower()
                    in {
                        "utilities",
                        "consumer defensive",
                        "healthcare",
                    }
            )
        )

        if tech_weight >= 35:

            macro_sensitivity = (
                "Growth / Risk-On Sensitive"
            )

        elif defensive_weight >= 35:

            macro_sensitivity = (
                "Defensive / Risk-Off Sensitive"
            )

        else:

            macro_sensitivity = "Balanced"

        # -----------------------------------
        # CONVICTION STRENGTH
        # -----------------------------------

        avg_conviction = sum(

            c.composite_conviction

            for c in portfolio

        ) / len(portfolio)

        if avg_conviction >= 80:

            conviction_strength = (
                "Elite Institutional Conviction"
            )

        elif avg_conviction >= 70:

            conviction_strength = (
                "High Institutional Conviction"
            )

        elif avg_conviction >= 60:

            conviction_strength = (
                "Constructive Institutional Conviction"
            )

        else:

            conviction_strength = (
                "Moderate Institutional Conviction"
            )

        # -----------------------------------
        # OUTPUT
        # -----------------------------------

        return {

            "total_positions":
                len(portfolio),

            "total_weight":
                round(
                    total_weight,
                    4,
                ),

            "cash_buffer":
                round(
                    cash_buffer,
                    4,
                ),

            "sector_exposure":
                sector_exposure,

            "risk_distribution":
                risk_distribution,

            "top_positions":
                top_positions,

            "portfolio_volatility":
                portfolio_volatility,

            "portfolio_risk_score":
                portfolio_risk_score,

            "concentration_risk":
                concentration_risk,

            "macro_sensitivity":
                macro_sensitivity,

            "conviction_strength":
                conviction_strength,
        }

    # ---------------------------------------------------
    # REBALANCE RECOMMENDATIONS
    # ---------------------------------------------------

    def rebalance_recommendations(
            portfolio: List[AIPortfolioCandidate],
            market_regime: str = "neutral",
    ) -> List[Dict[str, Any]]:

        recommendations = []

        if not portfolio:
            return recommendations

        for c in portfolio:

            action = "Hold"

            rationale = []

            # -----------------------------------
            # CONVICTION DETERIORATION
            # -----------------------------------

            if c.composite_conviction < 45:

                action = "Reduce Exposure"

                rationale.append(
                    "weak AI conviction"
                )

            elif c.composite_conviction > 80:

                action = "Increase Position"

                rationale.append(
                    "high institutional conviction"
                )

            # -----------------------------------
            # RISK ESCALATION
            # -----------------------------------

            if c.risk_score >= 75:
                action = "Trim Risk"

                rationale.append(
                    "elevated risk profile"
                )

            # -----------------------------------
            # VOLATILITY CONTROL
            # -----------------------------------

            if c.volatility >= 70:
                action = "Reduce Volatility"

                rationale.append(
                    "extreme volatility detected"
                )

            # -----------------------------------
            # MACRO REGIME
            # -----------------------------------

            if (
                    market_regime in {
                "bear",
                "panic",
            }
                    and c.sector.lower()
                    in {
                "technology",
                "semiconductors",
            }
            ):
                action = "Reduce Macro Exposure"

                rationale.append(
                    "risk-off macro regime"
                )

            # -----------------------------------
            # POSITION SIZING DELTA
            # -----------------------------------

            delta = (
                    c.target_weight
                    - c.current_weight
            )

            if delta >= 3:

                rationale.append(
                    "target allocation materially higher"
                )

            elif delta <= -3:

                rationale.append(
                    "target allocation materially lower"
                )

            # -----------------------------------
            # BUILD RECORD
            # -----------------------------------

            recommendations.append({

                "symbol":
                    c.symbol,

                "sector":
                    c.sector,

                "action":
                    action,

                "current_weight":
                    round(
                        c.current_weight,
                        4,
                    ),

                "target_weight":
                    round(
                        c.target_weight,
                        4,
                    ),

                "conviction":
                    round(
                        c.composite_conviction,
                        4,
                    ),

                "risk_score":
                    round(
                        c.risk_score,
                        4,
                    ),

                "volatility":
                    round(
                        c.volatility,
                        4,
                    ),

                "rationale":
                    ", ".join(rationale)
                    if rationale
                    else "no major rebalance signals",
            })

        # -----------------------------------
        # PRIORITIZE
        # -----------------------------------

        recommendations = sorted(

            recommendations,

            key=lambda x: (

                abs(
                    x["target_weight"]
                    - x["current_weight"]
                ),

                x["conviction"],
            ),

            reverse=True,
        )

        return recommendations
    