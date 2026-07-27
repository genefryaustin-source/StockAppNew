
"""
Sprint 6 Phase 3 — Position Sizing Intelligence Engine
"""

from __future__ import annotations
import pandas as pd

from modules.options.options_liquidity_engine import analyze_chain_liquidity


def calculate_position_size(
    portfolio_value: float,
    risk_percent: float,
    max_loss_per_contract: float,
) -> dict:

    portfolio_risk_budget = portfolio_value * (risk_percent / 100.0)

    contracts = 0
    if max_loss_per_contract > 0:
        contracts = int(portfolio_risk_budget / max_loss_per_contract)

    capital_at_risk = contracts * max_loss_per_contract

    utilization = 0.0
    if portfolio_risk_budget > 0:
        utilization = (capital_at_risk / portfolio_risk_budget) * 100

    return {
        "portfolio_value": portfolio_value,
        "risk_percent": risk_percent,
        "risk_budget": round(portfolio_risk_budget, 2),
        "max_loss_per_contract": round(max_loss_per_contract, 2),
        "recommended_contracts": max(0, contracts),
        "capital_at_risk": round(capital_at_risk, 2),
        "risk_budget_utilization": round(utilization, 2),
    }

def kelly_fraction(
    win_probability: float,
    average_win: float,
    average_loss: float,
) -> float:

    if average_loss <= 0:
        return 0.0

    if average_win <= 0:
        return 0.0

    b = average_win / average_loss

    kelly = win_probability - ((1.0 - win_probability) / b)

    return max(0.0, min(kelly, 1.0))

def calculate_liquidity_score(chain_data):
    """
    Backward compatibility wrapper.

    Existing dashboards expect a single score object.
    """

    report = analyze_chain_liquidity(chain_data)

    if not report.get("available"):
        return {
            "score": 0,
            "grade": "N/A",
            "summary": report.get("reason", "No liquidity data"),
        }

    summary = report.get("summary", {})

    return {
        "score": summary.get("avg_liquidity_score", 0),
        "grade": summary.get("market_liquidity_grade", "N/A"),
        "liquid_contracts": summary.get("liquid_contracts", 0),
        "tradable_contracts": summary.get("tradable_contracts", 0),
        "avg_spread_pct": summary.get("avg_spread_pct", 0),
        "total_volume": summary.get("total_volume", 0),
        "total_open_interest": summary.get("total_open_interest", 0),
    }

def build_position_sizing_matrix(
    portfolio_value: float,
    max_loss_per_contract: float,
) -> pd.DataFrame:

    rows = []

    for risk_pct in [0.25, 0.5, 1, 2, 3, 5]:
        result = calculate_position_size(
            portfolio_value,
            risk_pct,
            max_loss_per_contract,
        )

        rows.append({
            "risk_pct": risk_pct,
            "risk_budget": result["risk_budget"],
            "recommended_contracts": result["recommended_contracts"],
            "capital_at_risk": result["capital_at_risk"],
        })

    return pd.DataFrame(rows)


def classify_position_size(contracts: int) -> str:

    if contracts <= 1:
        return "Starter"

    if contracts <= 5:
        return "Small"

    if contracts <= 20:
        return "Medium"

    if contracts <= 50:
        return "Large"

    return "Institutional"
