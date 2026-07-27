"""
modules/options/options_strategy_recommender.py

Phase 5 strategy recommendation engine. Builds a broad candidate set across
bullish, bearish, neutral, volatility, income, and synthetic structures, then
scores each candidate using Phase 1-4 context when available.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_strategy_scoring_engine import score_strategy_list
from modules.options.options_spread_builder import build_vertical_spread, summarize_defined_risk_strategy
from modules.options.options_iron_condor_builder import build_iron_condor, build_iron_butterfly
from modules.options.options_butterfly_builder import build_long_butterfly, build_broken_wing_butterfly
from modules.options.options_calendar_builder import build_calendar_spread
from modules.options.options_diagonal_builder import build_diagonal_spread
from modules.options.options_ratio_spread_builder import build_ratio_spread


def _num(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def _expirations(chain_data: dict[str, Any]) -> list[str]:
    exps = chain_data.get("expirations") if isinstance(chain_data, dict) else []
    if isinstance(exps, list) and exps:
        return [str(x) for x in exps]
    chains = chain_data.get("chain") if isinstance(chain_data, dict) else None
    if chains is None:
        chains = chain_data.get("chains") if isinstance(chain_data, dict) else None
    if isinstance(chains, dict):
        return [str(x) for x in chains.keys()]
    return []


def _spot(chain_data: dict[str, Any]) -> float:
    if not isinstance(chain_data, dict):
        return 100.0
    return _num(chain_data.get("spot"), _num(chain_data.get("underlying_price"), _num(chain_data.get("lastTradePrice"), 100.0))) or 100.0


def _context_reports(ticker: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    smart: dict[str, Any] = {}
    dealer: dict[str, Any] = {}
    vol: dict[str, Any] = {}
    try:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        smart = build_options_smart_money_report(ticker)
    except Exception:
        smart = {}
    try:
        from modules.options.options_dealer_exposure_engine import build_dealer_exposure_report
        dealer = build_dealer_exposure_report(ticker)
    except Exception:
        dealer = {}
    try:
        from modules.options.options_volatility_dashboard import _load_report
        vol = _load_report(ticker, force_refresh=False)
    except Exception:
        vol = {}
    return smart, dealer, vol


def _basic_strategy(ticker: str, name: str, category: str, expiry: str, spot: float, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_name": name,
        "category_hint": category,
        "ticker": ticker,
        "expiry": expiry,
        "legs": [],
        "metrics": metrics,
    }


def generate_strategy_candidates(ticker: str, chain_data: dict[str, Any] | None = None, include_context: bool = True) -> list[dict[str, Any]]:
    chain_data = chain_data or {}
    spot = _spot(chain_data)
    expirations = _expirations(chain_data)
    near = expirations[0] if expirations else "30D"
    far = expirations[min(2, len(expirations) - 1)] if len(expirations) >= 2 else "60D"
    width = max(1.0, round(spot * 0.03, 0))

    candidates: list[dict[str, Any]] = []

    for bias in ["bullish", "bearish", "income_bullish", "income_bearish"]:
        c = build_vertical_spread(ticker, spot, near, bias=bias, width=width)
        c["metrics"] = summarize_defined_risk_strategy(c)
        candidates.append(c)

    candidates.append(build_iron_condor(ticker, spot, near, width=width))
    candidates.append(build_iron_butterfly(ticker, spot, near, width=width))
    candidates.append(build_long_butterfly(ticker, spot, near, width=width, option_type="call"))
    candidates.append(build_broken_wing_butterfly(ticker, spot, near, width=width, option_type="put"))
    candidates.append(build_calendar_spread(ticker, spot, near, far, strike=spot, option_type="call"))
    candidates.append(build_diagonal_spread(ticker, spot, near, far, bias="bullish", width=width))
    candidates.append(build_ratio_spread(ticker, spot, near, bias="bullish", width=width, ratio=2))

    candidates.extend([
        _basic_strategy(ticker, "Covered Call", "Income", near, spot, {"max_profit": spot * 3.0, "max_loss": spot * 100, "net_credit": spot * 1.2, "capital_required": spot * 100, "probability_profit": 0.62, "expected_value": spot * 0.22, "theta": 0.14, "vega": -0.06, "gamma": 0.02}),
        _basic_strategy(ticker, "Cash Secured Put", "Income", near, spot, {"max_profit": spot * 1.4, "max_loss": spot * 100, "net_credit": spot * 1.4, "capital_required": spot * 100, "probability_profit": 0.64, "expected_value": spot * 0.28, "theta": 0.16, "vega": -0.08, "gamma": 0.03}),
        _basic_strategy(ticker, "Wheel Strategy", "Income", near, spot, {"max_profit": spot * 2.4, "max_loss": spot * 100, "net_credit": spot * 1.2, "capital_required": spot * 100, "probability_profit": 0.66, "expected_value": spot * 0.35, "theta": 0.18, "vega": -0.08, "gamma": 0.03}),
        _basic_strategy(ticker, "Jade Lizard", "Income", near, spot, {"max_profit": spot * 1.8, "max_loss": width * 100, "net_credit": spot * 1.1, "capital_required": width * 100, "probability_profit": 0.63, "expected_value": spot * 0.20, "theta": 0.13, "vega": -0.07, "gamma": 0.05}),
        _basic_strategy(ticker, "Poor Man's Covered Call", "Bullish", far, spot, {"max_profit": spot * 5.0, "max_loss": spot * 12.0, "net_debit": spot * 12.0, "capital_required": spot * 12.0, "probability_profit": 0.52, "expected_value": spot * 0.40, "theta": 0.04, "vega": 0.12, "gamma": 0.05}),
        _basic_strategy(ticker, "Synthetic Long", "Bullish", near, spot, {"max_profit": spot * 8.0, "max_loss": spot * 8.0, "net_debit": 0, "capital_required": spot * 20.0, "probability_profit": 0.50, "expected_value": 0, "theta": 0.00, "vega": 0.00, "gamma": 0.02}),
        _basic_strategy(ticker, "Synthetic Short", "Bearish", near, spot, {"max_profit": spot * 8.0, "max_loss": spot * 8.0, "net_debit": 0, "capital_required": spot * 20.0, "probability_profit": 0.50, "expected_value": 0, "theta": 0.00, "vega": 0.00, "gamma": 0.02}),
        _basic_strategy(ticker, "Long Straddle", "Volatility", near, spot, {"max_profit": spot * 12.0, "max_loss": spot * 5.0, "net_debit": spot * 5.0, "capital_required": spot * 5.0, "probability_profit": 0.42, "expected_value": spot * 0.05, "theta": -0.16, "vega": 0.28, "gamma": 0.14}),
        _basic_strategy(ticker, "Long Strangle", "Volatility", near, spot, {"max_profit": spot * 14.0, "max_loss": spot * 3.5, "net_debit": spot * 3.5, "capital_required": spot * 3.5, "probability_profit": 0.39, "expected_value": spot * 0.02, "theta": -0.13, "vega": 0.22, "gamma": 0.10}),
    ])

    smart, dealer, vol = _context_reports(ticker) if include_context else ({}, {}, {})
    return score_strategy_list(candidates, smart_money=smart, dealer=dealer, volatility=vol)


def filter_candidates(candidates: list[dict[str, Any]], category: str = "All", min_score: float = 0.0) -> list[dict[str, Any]]:
    rows = []
    for c in candidates or []:
        if category != "All" and c.get("category") != category:
            continue
        if _num(c.get("overall_score")) < min_score:
            continue
        rows.append(c)
    return rows


def candidates_to_frame(candidates: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for c in candidates or []:
        score = c.get("score") or {}
        metrics = c.get("metrics") or {}
        rows.append({
            "Strategy": c.get("strategy_name"),
            "Category": c.get("category") or c.get("category_hint"),
            "Score": c.get("overall_score"),
            "Grade": c.get("grade"),
            "Label": c.get("label"),
            "POP": score.get("probability_score"),
            "Risk/Reward": score.get("risk_reward_score"),
            "Smart Money": score.get("smart_money_alignment_score"),
            "Dealer": score.get("dealer_alignment_score"),
            "IV Edge": score.get("iv_edge_score"),
            "Max Profit": metrics.get("max_profit"),
            "Max Loss": metrics.get("max_loss"),
            "Expected Value": metrics.get("expected_value"),
        })
    return pd.DataFrame(rows)
