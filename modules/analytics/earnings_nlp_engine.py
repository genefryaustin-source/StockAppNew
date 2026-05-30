"""
modules/analytics/earnings_nlp_engine.py

Institutional earnings call NLP engine.

Phase 1:
- heuristic NLP
- guidance analysis
- CEO confidence scoring
- risk phrase extraction
- analyst tone interpretation
- executive language analysis

Future:
- embeddings
- transformers
- FinBERT
- semantic executive profiling
- longitudinal management behavior tracking
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
import re


# ---------------------------------------------------
# DATA MODEL
# ---------------------------------------------------

@dataclass
class EarningsNLPResult:

    symbol: str

    guidance_score: float
    ceo_confidence: float
    risk_pressure: float

    tone_shift: str
    analyst_sentiment: str
    guidance_direction: str

    bullish_phrases: List[str]
    bearish_phrases: List[str]
    risk_phrases: List[str]

    executive_summary: str

    transcript_length: int

    analyzed_at: datetime


# ---------------------------------------------------
# BULLISH EXECUTIVE LANGUAGE
# ---------------------------------------------------

BULLISH_EXECUTIVE_PHRASES = {

    "strong demand": 8,
    "accelerating growth": 9,
    "record revenue": 9,
    "record margins": 8,
    "margin expansion": 8,
    "improving visibility": 8,
    "confidence in outlook": 9,
    "strong pipeline": 7,
    "raised guidance": 10,
    "market share gains": 8,
    "robust demand": 8,
    "healthy balance sheet": 7,
    "strong execution": 8,
    "operational leverage": 7,
    "positive momentum": 7,
    "cash flow strength": 8,
    "customer expansion": 7,
    "long-term opportunity": 6,
    "strong bookings": 8,
    "favorable trends": 7,
}


# ---------------------------------------------------
# BEARISH EXECUTIVE LANGUAGE
# ---------------------------------------------------

BEARISH_EXECUTIVE_PHRASES = {

    "macro uncertainty": 9,
    "headwinds": 8,
    "challenging environment": 8,
    "softening demand": 9,
    "margin pressure": 8,
    "cost pressures": 7,
    "supply chain issues": 7,
    "visibility remains limited": 9,
    "lowered guidance": 10,
    "restructuring": 6,
    "volatile environment": 6,
    "demand weakness": 9,
    "cautious outlook": 8,
    "currency pressure": 6,
    "declining demand": 9,
    "pricing pressure": 7,
    "liquidity concerns": 10,
    "cost inflation": 7,
    "slowing growth": 8,
    "customer caution": 8,
}


# ---------------------------------------------------
# CEO CONFIDENCE LANGUAGE
# ---------------------------------------------------

CONFIDENT_LANGUAGE = {

    "we are confident": 10,
    "strong conviction": 10,
    "high confidence": 10,
    "very optimistic": 9,
    "extremely pleased": 8,
    "well positioned": 8,
    "significant opportunity": 8,
    "continued momentum": 8,
    "clear visibility": 9,
    "encouraged by trends": 7,
}


HESITATION_LANGUAGE = {

    "we remain cautious": 10,
    "uncertain environment": 9,
    "limited visibility": 10,
    "difficult to predict": 9,
    "monitoring closely": 6,
    "we are being careful": 8,
    "potential weakness": 8,
    "could impact results": 7,
    "challenging conditions": 8,
}


# ---------------------------------------------------
# ANALYST PRESSURE PHRASES
# ---------------------------------------------------

ANALYST_PRESSURE_PHRASES = {

    "can you explain": 4,
    "why did margins decline": 8,
    "what caused the weakness": 8,
    "are you concerned": 7,
    "how sustainable": 6,
    "what risks remain": 7,
    "why should investors": 7,
    "how do you respond": 5,
    "why was guidance lowered": 10,
}


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _clean_text(
    text: str,
) -> str:

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _extract_matches(
    text: str,
    phrase_map: Dict[str, int],
) -> Dict[str, int]:

    found = {}

    for phrase, weight in phrase_map.items():

        if phrase in text:

            found[phrase] = weight

    return found


def _weighted_score(
    matches: Dict[str, int],
) -> float:

    if not matches:
        return 0.0

    return float(sum(matches.values()))


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
# TONE ANALYSIS
# ---------------------------------------------------

def _compute_guidance_score(
    bullish: float,
    bearish: float,
) -> float:

    base = 50.0

    adjustment = (
        bullish * 0.9
    ) - (
        bearish * 1.1
    )

    return round(
        _clamp(base + adjustment),
        2,
    )


def _compute_ceo_confidence(
    confident: float,
    hesitant: float,
) -> float:

    base = 50.0

    adjustment = (
        confident * 1.2
    ) - (
        hesitant * 1.3
    )

    return round(
        _clamp(base + adjustment),
        2,
    )


def _compute_risk_pressure(
    bearish: float,
    analyst_pressure: float,
) -> float:

    pressure = (
        bearish * 0.9
    ) + (
        analyst_pressure * 1.0
    )

    return round(
        _clamp(pressure),
        2,
    )


def _tone_shift(
    bullish: float,
    bearish: float,
) -> str:

    delta = bullish - bearish

    if delta >= 15:
        return "strongly improving"

    if delta >= 5:
        return "improving"

    if delta <= -15:
        return "strongly deteriorating"

    if delta <= -5:
        return "deteriorating"

    return "stable"


def _guidance_direction(
    bullish_matches: Dict[str, int],
    bearish_matches: Dict[str, int],
) -> str:

    if (
        "raised guidance" in bullish_matches
    ):
        return "raised"

    if (
        "lowered guidance" in bearish_matches
    ):
        return "lowered"

    return "unchanged"


def _analyst_sentiment(
    analyst_pressure_score: float,
) -> str:

    if analyst_pressure_score >= 25:
        return "aggressive"

    if analyst_pressure_score >= 12:
        return "skeptical"

    if analyst_pressure_score >= 5:
        return "neutral"

    return "constructive"


# ---------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------

def analyze_earnings_transcript(
    symbol: str,
    transcript: str,
) -> EarningsNLPResult:

    cleaned = _clean_text(
        transcript
    )

    bullish_matches = _extract_matches(
        cleaned,
        BULLISH_EXECUTIVE_PHRASES,
    )

    bearish_matches = _extract_matches(
        cleaned,
        BEARISH_EXECUTIVE_PHRASES,
    )

    confident_matches = _extract_matches(
        cleaned,
        CONFIDENT_LANGUAGE,
    )

    hesitation_matches = _extract_matches(
        cleaned,
        HESITATION_LANGUAGE,
    )

    analyst_matches = _extract_matches(
        cleaned,
        ANALYST_PRESSURE_PHRASES,
    )

    bullish_score = _weighted_score(
        bullish_matches
    )

    bearish_score = _weighted_score(
        bearish_matches
    )

    confident_score = _weighted_score(
        confident_matches
    )

    hesitation_score = _weighted_score(
        hesitation_matches
    )

    analyst_pressure = _weighted_score(
        analyst_matches
    )

    guidance_score = _compute_guidance_score(
        bullish_score,
        bearish_score,
    )

    ceo_confidence = _compute_ceo_confidence(
        confident_score,
        hesitation_score,
    )

    risk_pressure = _compute_risk_pressure(
        bearish_score,
        analyst_pressure,
    )

    tone_shift = _tone_shift(
        bullish_score,
        bearish_score,
    )

    guidance_direction = _guidance_direction(
        bullish_matches,
        bearish_matches,
    )

    analyst_sentiment = _analyst_sentiment(
        analyst_pressure,
    )

    summary = (
        f"{symbol} earnings tone is "
        f"{tone_shift}. "
        f"CEO confidence={ceo_confidence}, "
        f"guidance score={guidance_score}, "
        f"risk pressure={risk_pressure}."
    )

    return EarningsNLPResult(

        symbol=symbol,

        guidance_score=guidance_score,

        ceo_confidence=ceo_confidence,

        risk_pressure=risk_pressure,

        tone_shift=tone_shift,

        analyst_sentiment=analyst_sentiment,

        guidance_direction=guidance_direction,

        bullish_phrases=sorted(
            list(
                bullish_matches.keys()
            )
        ),

        bearish_phrases=sorted(
            list(
                bearish_matches.keys()
            )
        ),

        risk_phrases=sorted(
            list(
                set(
                    list(
                        bearish_matches.keys()
                    ) + list(
                        analyst_matches.keys()
                    )
                )
            )
        ),

        executive_summary=summary,

        transcript_length=len(cleaned),

        analyzed_at=datetime.now(UTC),
    )


# ---------------------------------------------------
# BATCH ANALYSIS
# ---------------------------------------------------

def analyze_earnings_batch(
    transcripts: Dict[str, str],
) -> Dict[str, EarningsNLPResult]:

    results = {}

    for symbol, transcript in transcripts.items():

        try:

            results[symbol] = (
                analyze_earnings_transcript(
                    symbol=symbol,
                    transcript=transcript or "",
                )
            )

        except Exception as e:

            print(
                "EARNINGS NLP ERROR",
                symbol,
                e,
            )

    return results


# ---------------------------------------------------
# AI OVERLAY MAP
# ---------------------------------------------------

def earnings_results_to_overlay_map(
    results: Dict[str, EarningsNLPResult],
) -> Dict[str, float]:

    overlay = {}

    for symbol, r in results.items():

        score = (
            (
                r.guidance_score * 0.45
            ) + (
                r.ceo_confidence * 0.35
            ) - (
                r.risk_pressure * 0.30
            )
        )

        normalized = (
            (score - 50.0) / 50.0
        )

        overlay[symbol] = round(
            normalized,
            4,
        )

    return overlay


# ---------------------------------------------------
# DATAFRAME EXPORT
# ---------------------------------------------------

def earnings_results_to_dataframe(
    results: Dict[str, EarningsNLPResult],
):

    import pandas as pd

    rows = []

    for symbol, r in results.items():

        rows.append({

            "Symbol": symbol,

            "Guidance Score": r.guidance_score,

            "CEO Confidence": r.ceo_confidence,

            "Risk Pressure": r.risk_pressure,

            "Tone Shift": r.tone_shift,

            "Analyst Sentiment": r.analyst_sentiment,

            "Guidance Direction": r.guidance_direction,

            "Bullish Phrases":
                ", ".join(
                    r.bullish_phrases
                ),

            "Bearish Phrases":
                ", ".join(
                    r.bearish_phrases
                ),

            "Risk Phrases":
                ", ".join(
                    r.risk_phrases
                ),

            "Executive Summary":
                r.executive_summary,

            "Transcript Length":
                r.transcript_length,

            "Analyzed At":
                r.analyzed_at,
        })

    return pd.DataFrame(rows)