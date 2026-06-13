from __future__ import annotations
from typing import Any
from .research_utils import _stable_score, _clamp


def build_fundamental_signal(ticker: str) -> dict[str, Any]:
    quality = _stable_score(ticker, 11, 62, 18)
    growth = _stable_score(ticker, 12, 58, 22)
    margin = _stable_score(ticker, 13, 55, 20)
    fcf = _stable_score(ticker, 14, 57, 19)
    roic = _stable_score(ticker, 15, 60, 18)
    balance = _stable_score(ticker, 16, 64, 16)
    valuation = _stable_score(ticker, 17, 52, 24)
    score = round(_clamp(quality*.18 + growth*.18 + margin*.14 + fcf*.14 + roic*.14 + balance*.12 + valuation*.10), 1)
    return {
        "ticker": ticker.upper(),
        "fundamental_score": score,
        "quality_score": quality,
        "growth_score": growth,
        "margin_score": margin,
        "fcf_score": fcf,
        "roic_score": roic,
        "balance_sheet_score": balance,
        "valuation_score": valuation,
        "signals": [
            {"Metric": "Revenue Growth", "Signal": "Positive" if growth >= 55 else "Neutral", "Score": growth},
            {"Metric": "EPS Growth", "Signal": "Positive" if quality >= 55 else "Watch", "Score": quality},
            {"Metric": "Margin Expansion", "Signal": "Improving" if margin >= 55 else "Mixed", "Score": margin},
            {"Metric": "FCF Growth", "Signal": "Strong" if fcf >= 65 else "Developing", "Score": fcf},
            {"Metric": "ROIC Trend", "Signal": "High Quality" if roic >= 65 else "Average", "Score": roic},
        ],
        "summary": "Fundamental profile is strong" if score >= 70 else "Fundamental profile is constructive" if score >= 55 else "Fundamental profile requires monitoring",
    }
