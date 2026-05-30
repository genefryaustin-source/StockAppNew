"""
modules/analytics/news_sentiment_engine.py

Institutional-grade news sentiment engine.

Phase 1 implementation:
- weighted heuristic NLP
- catalyst extraction
- event classification
- bullish/bearish scoring
- market tone analysis

Future:
- embeddings
- transformers
- FinBERT
- semantic clustering
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
class NewsSentimentResult:
    symbol: str

    sentiment_score: float
    bullish_score: float
    bearish_score: float

    market_tone: str
    confidence: float
    event_weight: float

    bullish_mentions: int
    bearish_mentions: int

    catalysts: List[str]
    risks: List[str]

    summary: str

    article_count: int
    analyzed_at: datetime


# ---------------------------------------------------
# BULLISH SIGNALS
# ---------------------------------------------------

BULLISH_KEYWORDS = {

    "earnings beat": 8,
    "guidance raised": 9,
    "guidance raise": 9,
    "record revenue": 8,
    "strong demand": 7,
    "accelerating growth": 8,
    "buyback": 7,
    "share repurchase": 7,
    "contract win": 6,
    "partnership": 5,
    "ai": 3,
    "acquisition": 4,
    "profit growth": 7,
    "margin expansion": 7,
    "cash flow growth": 7,
    "analyst upgrade": 6,
    "raised target": 5,
    "outperform": 6,
    "bullish": 5,
    "expansion": 5,
    "approval": 6,
    "innovation": 4,
    "market share gains": 7,
    "strong outlook": 7,
}


# ---------------------------------------------------
# BEARISH SIGNALS
# ---------------------------------------------------

BEARISH_KEYWORDS = {

    "guidance cut": 10,
    "guidance lowered": 10,
    "downgrade": 8,
    "analyst downgrade": 8,
    "missed earnings": 9,
    "declining revenue": 9,
    "liquidity concern": 10,
    "bankruptcy": 10,
    "lawsuit": 6,
    "investigation": 8,
    "fraud": 10,
    "dilution": 8,
    "share offering": 7,
    "layoffs": 5,
    "weak demand": 7,
    "margin pressure": 7,
    "macro headwinds": 5,
    "risk": 3,
    "bearish": 5,
    "volatility": 4,
    "debt concerns": 8,
    "cash burn": 8,
    "restructuring": 5,
    "regulatory pressure": 7,
    "supply chain issues": 6,
}


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.lower()

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _extract_matches(
    text: str,
    keyword_map: Dict[str, int],
) -> Dict[str, int]:

    found = {}

    for phrase, weight in keyword_map.items():

        if phrase in text:
            found[phrase] = weight

    return found


def _compute_weighted_score(
    matches: Dict[str, int],
) -> float:

    if not matches:
        return 0.0

    return float(sum(matches.values()))


def _market_tone(
    bullish: float,
    bearish: float,
) -> str:

    delta = bullish - bearish

    if delta >= 15:
        return "strongly bullish"

    if delta >= 6:
        return "bullish"

    if delta <= -15:
        return "strongly bearish"

    if delta <= -6:
        return "bearish"

    return "neutral"


def _confidence_score(
    bullish_mentions: int,
    bearish_mentions: int,
    article_count: int,
) -> float:

    total_mentions = bullish_mentions + bearish_mentions

    if article_count <= 0:
        return 0.0

    raw = (
        total_mentions * 12
    ) + (article_count * 4)

    return round(min(100.0, raw), 2)


# ---------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------

def analyze_news_sentiment(
    symbol: str,
    news_items: List[Dict[str, Any]],
) -> NewsSentimentResult:

    bullish_total = 0.0
    bearish_total = 0.0

    bullish_mentions = 0
    bearish_mentions = 0

    catalysts = set()
    risks = set()

    combined_text = []

    for item in news_items:

        title = str(item.get("headline") or "")
        summary = str(item.get("summary") or "")

        text = _clean_text(
            f"{title} {summary}"
        )

        combined_text.append(text)

        bull_matches = _extract_matches(
            text,
            BULLISH_KEYWORDS,
        )

        bear_matches = _extract_matches(
            text,
            BEARISH_KEYWORDS,
        )

        if bull_matches:
            bullish_mentions += 1

        if bear_matches:
            bearish_mentions += 1

        bullish_total += _compute_weighted_score(
            bull_matches
        )

        bearish_total += _compute_weighted_score(
            bear_matches
        )

        catalysts.update(bull_matches.keys())
        risks.update(bear_matches.keys())

    sentiment_score = bullish_total - bearish_total

    normalized = max(
        -100.0,
        min(100.0, sentiment_score),
    )

    tone = _market_tone(
        bullish_total,
        bearish_total,
    )

    confidence = _confidence_score(
        bullish_mentions,
        bearish_mentions,
        len(news_items),
    )

    event_weight = round(
        min(
            1.0,
            abs(normalized) / 40.0,
        ),
        4,
    )

    summary = (
        f"{symbol} news tone is {tone}. "
        f"Bullish score={round(bullish_total, 2)} "
        f"Bearish score={round(bearish_total, 2)}."
    )

    return NewsSentimentResult(
        symbol=symbol,

        sentiment_score=round(normalized, 2),
        bullish_score=round(bullish_total, 2),
        bearish_score=round(bearish_total, 2),

        market_tone=tone,
        confidence=confidence,
        event_weight=event_weight,

        bullish_mentions=bullish_mentions,
        bearish_mentions=bearish_mentions,

        catalysts=sorted(list(catalysts)),
        risks=sorted(list(risks)),

        summary=summary,

        article_count=len(news_items),
        analyzed_at=datetime.now(UTC),
    )


# ---------------------------------------------------
# BATCH ANALYSIS
# ---------------------------------------------------

def analyze_news_batch(
    news_map: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, NewsSentimentResult]:

    results = {}

    for symbol, items in news_map.items():

        try:

            results[symbol] = analyze_news_sentiment(
                symbol=symbol,
                news_items=items or [],
            )

        except Exception as e:

            print(
                "NEWS SENTIMENT ERROR",
                symbol,
                e,
            )

    return results


# ---------------------------------------------------
# CONVERT TO AI OVERLAY MAP
# ---------------------------------------------------

def sentiment_results_to_overlay_map(
    results: Dict[str, NewsSentimentResult],
) -> Dict[str, float]:

    overlay = {}

    for symbol, r in results.items():

        score = r.sentiment_score / 100.0

        weighted = (
            score * r.event_weight
        )

        overlay[symbol] = round(weighted, 4)

    return overlay


# ---------------------------------------------------
# DATAFRAME EXPORT
# ---------------------------------------------------

def news_sentiment_to_dataframe(
    results: Dict[str, NewsSentimentResult],
):

    import pandas as pd

    rows = []

    for symbol, r in results.items():

        rows.append({

            "Symbol": symbol,

            "Sentiment Score": r.sentiment_score,
            "Bullish Score": r.bullish_score,
            "Bearish Score": r.bearish_score,

            "Market Tone": r.market_tone,
            "Confidence": r.confidence,
            "Event Weight": r.event_weight,

            "Bullish Mentions": r.bullish_mentions,
            "Bearish Mentions": r.bearish_mentions,

            "Catalysts": ", ".join(r.catalysts),
            "Risks": ", ".join(r.risks),

            "Summary": r.summary,

            "Articles": r.article_count,

            "Analyzed At": r.analyzed_at,
        })

    return pd.DataFrame(rows)

# ---------------------------------------------------
# SENTIMENT OVERLAY MAP
# ---------------------------------------------------

def build_sentiment_overlay_map(
    ranked_rows,
) -> Dict[str, float]:

    """
    Converts news sentiment analysis results
    into a symbol -> sentiment score overlay map.

    Used by:
    - ai_ranking_engine.py
    - opportunity_detection_engine.py
    - autonomous_portfolio_runtime.py
    - ai_portfolio_ui.py
    """

    overlay: Dict[str, float] = {}

    if not ranked_rows:
        return overlay

    try:

        # -----------------------------------
        # IMPORT PROVIDER
        # -----------------------------------

        from modules.analytics.news_provider import (
            fetch_news_for_symbol,
        )

    except Exception:

        return overlay

    try:

        # -----------------------------------
        # IMPORT SENTIMENT ENGINE
        # -----------------------------------

        from modules.analytics.news_sentiment_engine import (
            analyze_news_sentiment,
        )

    except Exception:

        return overlay

    # -----------------------------------
    # BUILD OVERLAY
    # -----------------------------------

    for row in ranked_rows:

        try:

            symbol = str(
                getattr(
                    row,
                    "symbol",
                    "",
                )
            ).upper()

            if not symbol:
                continue

            # -----------------------------------
            # FETCH NEWS
            # -----------------------------------

            articles = fetch_news_for_symbol(
                symbol=symbol,
                limit=10,
            )

            if not articles:
                overlay[symbol] = 0.0
                continue

            # -----------------------------------
            # ANALYZE SENTIMENT
            # -----------------------------------

            sentiment_result = (
                analyze_news_sentiment(
                    symbol=symbol,
                    articles=articles,
                )
            )

            # -----------------------------------
            # EXTRACT SCORE
            # -----------------------------------

            sentiment_score = 0.0

            if isinstance(
                sentiment_result,
                dict,
            ):

                sentiment_score = float(
                    sentiment_result.get(
                        "sentiment_score",
                        0.0,
                    )
                )

            else:

                sentiment_score = float(
                    getattr(
                        sentiment_result,
                        "sentiment_score",
                        0.0,
                    )
                )

            # -----------------------------------
            # STORE
            # -----------------------------------

            overlay[symbol] = sentiment_score

        except Exception:

            overlay[symbol] = 0.0

    return overlay