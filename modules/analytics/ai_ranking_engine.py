"""
modules/analytics/ai_ranking_engine.py

AI-enhanced ranking overlay.

This module does NOT replace the existing quant/factor ranking engine.
It sits on top of RankedRow outputs from modules.analytics.rankings.rank_symbols()
and adds:

- AI-adjusted score
- factor reasoning
- bull thesis
- bear thesis
- risk notes
- narrative summary
- adaptive weighting hooks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math

from modules.analytics.adaptive_factor_engine import (
    adaptive_score_adjustment,
    AdaptiveWeights,
)
from modules.analytics.research_agents import (
    evaluate_symbols_with_agents,
)
# ---------------------------------------------------
# DATA MODEL
# ---------------------------------------------------

@dataclass
class AIRankedRow:
    symbol: str
    sector: str
    base_composite: Optional[float]
    base_confidence: Optional[float]
    ai_score: Optional[float]
    ai_confidence: Optional[float]
    rating: Optional[str]

    factor_summary: str
    bull_thesis: str
    bear_thesis: str
    risk_notes: str
    ai_rationale: str

    quality: Optional[float] = None
    growth: Optional[float] = None
    value: Optional[float] = None
    momentum: Optional[float] = None
    risk: Optional[float] = None


# ---------------------------------------------------
# SAFE HELPERS
# ---------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:

    try:
        if value is None:
            return None

        if isinstance(value, float) and math.isnan(value):
            return None

        return float(value)

    except Exception:
        return None


def _score_or_zero(value: Any) -> float:

    val = _safe_float(value)

    if val is None:
        return 0.0

    return val


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(low, min(high, value))


# ---------------------------------------------------
# FACTOR INTERPRETATION
# ---------------------------------------------------

def _factor_label(
    name: str,
    value: Optional[float],
    high_is_good: bool = True,
) -> str:

    if value is None:
        return f"{name}: unavailable"

    if high_is_good:

        if value >= 70:
            return f"{name}: strong"
        if value >= 55:
            return f"{name}: constructive"
        if value >= 40:
            return f"{name}: neutral"

        return f"{name}: weak"

    else:

        if value <= 30:
            return f"{name}: low"
        if value <= 45:
            return f"{name}: controlled"
        if value <= 60:
            return f"{name}: moderate"

        return f"{name}: elevated"


def build_factor_summary(row: Any) -> str:

    quality = _safe_float(getattr(row, "quality", None))
    growth = _safe_float(getattr(row, "growth", None))
    value = _safe_float(getattr(row, "value", None))
    momentum = _safe_float(getattr(row, "momentum", None))
    risk = _safe_float(getattr(row, "risk", None))

    parts = [
        _factor_label("Quality", quality),
        _factor_label("Growth", growth),
        _factor_label("Value", value),
        _factor_label("Momentum", momentum),
        _factor_label("Risk", risk, high_is_good=False),
    ]

    return "; ".join(parts)


# ---------------------------------------------------
# AI FACTOR WEIGHTING
# ---------------------------------------------------

def compute_ai_adjusted_score(row: Any) -> Optional[float]:

    base = _safe_float(getattr(row, "composite", None))

    if base is None:
        return None

    quality = _score_or_zero(getattr(row, "quality", None))
    growth = _score_or_zero(getattr(row, "growth", None))
    value = _score_or_zero(getattr(row, "value", None))
    momentum = _score_or_zero(getattr(row, "momentum", None))
    risk = _score_or_zero(getattr(row, "risk", None))
    confidence = _safe_float(getattr(row, "confidence", None))

    # Conservative first-pass AI overlay.
    # This does not overpower the quant score.
    quality_adj = (quality - 50.0) * 0.08
    growth_adj = (growth - 50.0) * 0.07
    value_adj = (value - 50.0) * 0.05
    momentum_adj = (momentum - 50.0) * 0.08
    risk_adj = (50.0 - risk) * 0.06

    confidence_adj = 0.0
    if confidence is not None:
        confidence_adj = (confidence - 50.0) * 0.03

    adjusted = (
        base
        + quality_adj
        + growth_adj
        + value_adj
        + momentum_adj
        + risk_adj
        + confidence_adj
    )

    return round(_clamp(adjusted), 4)


def compute_ai_confidence(row: Any) -> Optional[float]:

    base_conf = _safe_float(getattr(row, "confidence", None))

    if base_conf is None:
        base_conf = 50.0

    available = 0

    for field in [
        "quality",
        "growth",
        "value",
        "momentum",
        "risk",
        "composite",
    ]:
        if _safe_float(getattr(row, field, None)) is not None:
            available += 1

    completeness_bonus = available * 3.0

    return round(
        _clamp(base_conf + completeness_bonus - 9.0),
        2,
    )


# ---------------------------------------------------
# NARRATIVE SYNTHESIS
# ---------------------------------------------------

def build_bull_thesis(row: Any) -> str:

    symbol = getattr(row, "symbol", "Unknown")
    sector = getattr(row, "sector", "Unknown")

    quality = _safe_float(getattr(row, "quality", None))
    growth = _safe_float(getattr(row, "growth", None))
    momentum = _safe_float(getattr(row, "momentum", None))
    composite = _safe_float(getattr(row, "composite", None))

    points = []

    if composite is not None and composite >= 60:
        points.append("overall composite score is above average")

    if quality is not None and quality >= 60:
        points.append("quality profile is supportive")

    if growth is not None and growth >= 60:
        points.append("growth profile is favorable")

    if momentum is not None and momentum >= 60:
        points.append("momentum is constructive")

    if not points:
        points.append("current factor profile is mixed but monitorable")

    return (
        f"{symbol} shows a {', '.join(points)} within the "
        f"{sector or 'Unknown'} sector."
    )


def build_bear_thesis(row: Any) -> str:

    symbol = getattr(row, "symbol", "Unknown")

    value = _safe_float(getattr(row, "value", None))
    momentum = _safe_float(getattr(row, "momentum", None))
    risk = _safe_float(getattr(row, "risk", None))
    composite = _safe_float(getattr(row, "composite", None))

    concerns = []

    if composite is not None and composite < 45:
        concerns.append("below-average composite score")

    if value is not None and value < 40:
        concerns.append("valuation support appears weak")

    if momentum is not None and momentum < 40:
        concerns.append("momentum is soft")

    if risk is not None and risk > 60:
        concerns.append("risk score is elevated")

    if not concerns:
        concerns.append("main downside risk is factor deterioration or market regime change")

    return f"{symbol} bear case: {', '.join(concerns)}."


def build_risk_notes(row: Any) -> str:

    risk = _safe_float(getattr(row, "risk", None))
    confidence = _safe_float(getattr(row, "confidence", None))

    notes = []

    if risk is None:
        notes.append("risk score unavailable")
    elif risk > 70:
        notes.append("high model risk")
    elif risk > 55:
        notes.append("moderate risk profile")
    else:
        notes.append("risk appears controlled")

    if confidence is None:
        notes.append("confidence unavailable")
    elif confidence < 40:
        notes.append("low confidence score")
    elif confidence < 55:
        notes.append("moderate confidence score")
    else:
        notes.append("acceptable confidence score")

    return "; ".join(notes)


def build_ai_rationale(row: Any, ai_score: Optional[float]) -> str:

    symbol = getattr(row, "symbol", "Unknown")
    base = _safe_float(getattr(row, "composite", None))

    if ai_score is None:
        return f"{symbol} could not be AI-adjusted because composite data is unavailable."

    if base is None:
        return f"{symbol} AI score is based on incomplete factor data."

    delta = ai_score - base

    if delta > 2:
        direction = "upward"
    elif delta < -2:
        direction = "downward"
    else:
        direction = "neutral"

    return (
        f"{symbol} received a {direction} AI adjustment. "
        f"Base composite was {round(base, 2)} and AI-adjusted score is "
        f"{round(ai_score, 2)}. Adjustment reflects quality, growth, "
        f"value, momentum, risk, and confidence balance."
    )


# ---------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------

def enhance_rankings_with_ai(

    ranked_rows: List[Any],

    limit: Optional[int] = None,

    sentiment_overlay: Optional[Dict[str, float]] = None,

    earnings_overlay: Optional[Dict[str, float]] = None,

    adaptive_weights: Optional[AdaptiveWeights] = None,

    consensus_overlay: Optional[Dict[str, float]] = None,

) -> List[AIRankedRow]:

    if not ranked_rows:
        return []

    output: List[AIRankedRow] = []

    rows = ranked_rows[:limit] if limit else ranked_rows

    for row in rows:

        ai_score = compute_ai_adjusted_score(row)

        symbol = getattr(row, "symbol", "")

        # -----------------------------------
        # NEWS SENTIMENT OVERLAY
        # -----------------------------------

        if (
                ai_score is not None
                and sentiment_overlay
        ):
            sent_adj = sentiment_overlay.get(
                symbol,
                0.0,
            )

            ai_score = round(
                _clamp(
                    ai_score + (sent_adj * 12.0)
                ),
                4,
            )
        ai_confidence = compute_ai_confidence(row)

        output.append(
            AIRankedRow(
                symbol=getattr(row, "symbol", ""),
                sector=getattr(row, "sector", "Unknown"),
                base_composite=_safe_float(getattr(row, "composite", None)),
                base_confidence=_safe_float(getattr(row, "confidence", None)),
                ai_score=ai_score,
                ai_confidence=ai_confidence,
                rating=getattr(row, "rating", None),

                factor_summary=build_factor_summary(row),
                bull_thesis=build_bull_thesis(row),
                bear_thesis=build_bear_thesis(row),
                risk_notes=build_risk_notes(row),
                ai_rationale=build_ai_rationale(
                    row,
                    ai_score,
                ),

                quality=_safe_float(getattr(row, "quality", None)),
                growth=_safe_float(getattr(row, "growth", None)),
                value=_safe_float(getattr(row, "value", None)),
                momentum=_safe_float(getattr(row, "momentum", None)),
                risk=_safe_float(getattr(row, "risk", None)),
            )
        )
    if sentiment_overlay:

        sent_adj = sentiment_overlay.get(
            symbol,
            0.0,
        )

        if abs(sent_adj) > 0.05:
            direction = (
                "positive"
                if sent_adj > 0
                else "negative"
            )

            output[-1].ai_rationale += (
                f" News sentiment overlay "
                f"provided a {direction} "
                f"adjustment."
            )
    output.sort(
        key=lambda r: (
            r.ai_score if r.ai_score is not None else -9999,
            r.ai_confidence if r.ai_confidence is not None else -9999,
        ),
        reverse=True,
    )
    # -----------------------------------
    # EARNINGS NLP OVERLAY
    # -----------------------------------

    if (
            ai_score is not None
            and earnings_overlay
    ):
        earn_adj = earnings_overlay.get(
            symbol,
            0.0,
        )

        ai_score = round(
            _clamp(
                ai_score + (earn_adj * 10.0)
            ),
            4,
        )

        if earnings_overlay:

            earn_adj = earnings_overlay.get(
                symbol,
                0.0,
            )

            if abs(earn_adj) > 0.05:
                direction = (
                    "positive"
                    if earn_adj > 0
                    else "negative"
                )

                output[-1].ai_rationale += (
                    f" Earnings NLP provided a "
                    f"{direction} executive-language "
                    f"adjustment."
                )
        # -----------------------------------
        # ADAPTIVE FACTOR INTELLIGENCE
        # -----------------------------------

        if (
                ai_score is not None
                and adaptive_weights is not None
        ):
            ai_score = adaptive_score_adjustment(

                base_ai_score=ai_score,

                factor_values={

                    "quality":
                        getattr(
                            row,
                            "quality",
                            None,
                        ),

                    "growth":
                        getattr(
                            row,
                            "growth",
                            None,
                        ),

                    "value":
                        getattr(
                            row,
                            "value",
                            None,
                        ),

                    "momentum":
                        getattr(
                            row,
                            "momentum",
                            None,
                        ),

                    "risk":
                        getattr(
                            row,
                            "risk",
                            None,
                        ),

                    "sentiment":
                        sentiment_overlay.get(
                            symbol,
                            0.0,
                        ) if sentiment_overlay else 0.0,

                    "earnings_nlp":
                        earnings_overlay.get(
                            symbol,
                            0.0,
                        ) if earnings_overlay else 0.0,

                    "confidence":
                        getattr(
                            row,
                            "confidence",
                            None,
                        ),
                },

                weights=adaptive_weights,
            )

        if adaptive_weights is not None:
            output[-1].ai_rationale += (
                f" Adaptive intelligence adjusted "
                f"weights for the "
                f"{adaptive_weights.regime} "
                f"market regime."
            )
        # -----------------------------------
        # MULTI-AGENT CONSENSUS
        # -----------------------------------

        if (
                ai_score is not None
                and consensus_overlay
        ):
            consensus_adj = (
                consensus_overlay.get(
                    symbol,
                    0.0,
                )
            )

            ai_score = round(

                _clamp(
                    ai_score + (
                            consensus_adj * 15.0
                    )
                ),

                4,
            )

        if consensus_overlay:

            consensus_adj = (
                consensus_overlay.get(
                    symbol,
                    0.0,
                )
            )

            if abs(consensus_adj) > 0.05:
                output[-1].ai_rationale += (
                    f" Multi-agent research "
                    f"consensus influenced the "
                    f"final AI ranking."
                )


    return output



# ---------------------------------------------------
# DATAFRAME EXPORT
# ---------------------------------------------------

def ai_rankings_to_dataframe(
    rows: List[AIRankedRow],
):

    import pandas as pd

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "Symbol": r.symbol,
            "Sector": r.sector,
            "Base Composite": r.base_composite,
            "AI Score": r.ai_score,
            "AI Confidence": r.ai_confidence,
            "Rating": r.rating,
            "Quality": r.quality,
            "Growth": r.growth,
            "Value": r.value,
            "Momentum": r.momentum,
            "Risk": r.risk,
            "Factor Summary": r.factor_summary,
            "Bull Thesis": r.bull_thesis,
            "Bear Thesis": r.bear_thesis,
            "Risk Notes": r.risk_notes,
            "AI Rationale": r.ai_rationale,
        }
        for r in rows
    ])


# ---------------------------------------------------
# FUTURE EXTENSION HOOKS
# ---------------------------------------------------

def attach_news_sentiment(
    ai_rows: List[AIRankedRow],
    sentiment_map: Optional[Dict[str, float]] = None,
) -> List[AIRankedRow]:

    """
    Future hook for news embeddings / transformer sentiment.

    sentiment_map example:
        {
            "AAPL": 0.72,
            "MSFT": -0.15,
        }
    """

    if not ai_rows or not sentiment_map:
        return ai_rows

    for row in ai_rows:

        sent = sentiment_map.get(row.symbol)

        if sent is None or row.ai_score is None:
            continue

        adjustment = float(sent) * 3.0

        row.ai_score = round(
            _clamp(row.ai_score + adjustment),
            4,
        )

        row.ai_rationale += (
            f" News sentiment overlay adjusted score by "
            f"{round(adjustment, 2)}."
        )

    ai_rows.sort(
        key=lambda r: (
            r.ai_score if r.ai_score is not None else -9999,
            r.ai_confidence if r.ai_confidence is not None else -9999,
        ),
        reverse=True,
    )

    return ai_rows


def adapt_factor_weights_from_feedback(
    feedback_events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:

    """
    Placeholder for autonomous ranking adaptation.

    Later this can learn from:
    - analyst overrides
    - portfolio outcomes
    - realized returns
    - failed signals
    - market regime changes
    """

    return {
        "quality": 0.08,
        "growth": 0.07,
        "value": 0.05,
        "momentum": 0.08,
        "risk": 0.06,
        "confidence": 0.03,
    }