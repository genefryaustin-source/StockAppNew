from __future__ import annotations
from typing import Any
from .research_utils import _stable_score


def build_macro_intelligence(ticker: str = "MARKET") -> dict[str, Any]:
    rates = _stable_score(ticker, 61, 50, 24)
    inflation = _stable_score(ticker, 62, 50, 24)
    growth = _stable_score(ticker, 63, 55, 20)
    liquidity = _stable_score(ticker, 64, 52, 26)
    risk = round(growth*.30 + liquidity*.30 + (100-rates)*.20 + (100-inflation)*.20, 1)
    return {
        "macro_score": risk,
        "regime": "Supportive" if risk >= 60 else "Neutral" if risk >= 42 else "Restrictive",
        "interest_rate_pressure": rates,
        "inflation_pressure": inflation,
        "growth_impulse": growth,
        "liquidity_conditions": liquidity,
        "factors": [
            {"Factor": "Interest Rates", "Score": rates, "Read": "Headwind" if rates >= 60 else "Manageable"},
            {"Factor": "Inflation", "Score": inflation, "Read": "Headwind" if inflation >= 60 else "Stable"},
            {"Factor": "Growth", "Score": growth, "Read": "Supportive" if growth >= 55 else "Soft"},
            {"Factor": "Liquidity", "Score": liquidity, "Read": "Loose" if liquidity >= 60 else "Neutral/Tight"},
        ],
    }
