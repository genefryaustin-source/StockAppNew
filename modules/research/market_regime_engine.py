from __future__ import annotations
from typing import Any
from .research_utils import _stable_score


def build_market_regime(ticker: str = "MARKET") -> dict[str, Any]:
    trend = _stable_score(ticker, 81, 55, 30)
    vol = _stable_score(ticker, 82, 45, 30)
    breadth = _stable_score(ticker, 83, 52, 28)
    credit = _stable_score(ticker, 84, 50, 24)
    score = round(trend*.35 + breadth*.25 + (100-vol)*.25 + credit*.15, 1)
    regime = "Risk-On" if score >= 62 else "Risk-Off" if score <= 38 else "Neutral"
    return {"market_regime_score": score, "regime": regime, "trend_score": trend, "volatility_pressure": vol, "breadth_score": breadth, "credit_score": credit,
            "conditions": "Bull Market / Expansion" if score >= 65 else "Bear Market / Contraction" if score <= 35 else "Transitional"}
