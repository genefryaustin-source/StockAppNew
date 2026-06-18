
from __future__ import annotations
import pandas as pd

DEFAULT_LIMITS = {
    "max_portfolio_delta": 5000,
    "max_portfolio_gamma": 2500,
    "max_portfolio_vega": 5000,
    "max_position_pct": 20,
    "max_underlying_pct": 35,
    "max_expiry_pct": 40,
}

def evaluate_portfolio_guardrails(risk_report: dict, limits: dict | None = None):
    limits = limits or DEFAULT_LIMITS
    breaches = []

    score = risk_report.get("score", {})
    net = risk_report.get("net", {}).get("net_greeks", {})

    if abs(net.get("delta", 0)) > limits["max_portfolio_delta"]:
        breaches.append("Portfolio Delta Limit Breach")

    if abs(net.get("gamma", 0)) > limits["max_portfolio_gamma"]:
        breaches.append("Portfolio Gamma Limit Breach")

    if abs(net.get("vega", 0)) > limits["max_portfolio_vega"]:
        breaches.append("Portfolio Vega Limit Breach")

    return {
        "breaches": breaches,
        "breach_count": len(breaches),
        "risk_level": score.get("greeks_risk_level", "UNKNOWN"),
        "passed": len(breaches) == 0,
    }
