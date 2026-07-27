"""
modules/options/options_execution_guardrails.py

Phase 7 - Autonomous Options Execution Fabric.
Deterministic guardrail checks for AI-generated options trade candidates.
No live order is placed from this module.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ExecutionGuardrails:
    max_trade_risk_pct: float = 0.02
    max_portfolio_risk_pct: float = 0.10
    max_daily_trades: int = 5
    max_contracts_per_trade: int = 10
    max_earnings_exposure_pct: float = 0.03
    require_defined_risk: bool = True
    allow_live_execution: bool = False
    min_confidence: float = 60.0


def default_guardrails() -> dict[str, Any]:
    return asdict(ExecutionGuardrails())


def evaluate_trade_guardrails(candidate: dict[str, Any], guardrails: dict[str, Any] | None = None, portfolio_context: dict[str, Any] | None = None) -> dict[str, Any]:
    g = {**default_guardrails(), **(guardrails or {})}
    portfolio_context = portfolio_context or {}

    risk = float(candidate.get("max_loss") or candidate.get("risk") or 0)
    confidence = float(candidate.get("confidence") or candidate.get("score") or 0)
    contracts = int(float(candidate.get("contracts") or candidate.get("qty") or 1))
    defined_risk = bool(candidate.get("defined_risk", True))
    earnings = bool(candidate.get("earnings_trade", False))
    equity = float(portfolio_context.get("equity") or portfolio_context.get("portfolio_value") or 100000)
    daily_trades = int(portfolio_context.get("daily_trades") or 0)

    failures: list[str] = []
    warnings: list[str] = []

    if confidence < float(g["min_confidence"]):
        failures.append(f"Confidence {confidence:.1f} is below minimum {g['min_confidence']:.1f}.")
    if contracts > int(g["max_contracts_per_trade"]):
        failures.append(f"Contracts {contracts} exceed max {g['max_contracts_per_trade']}.")
    if equity > 0 and risk / equity > float(g["max_trade_risk_pct"]):
        failures.append(f"Trade risk {risk/equity:.1%} exceeds max trade risk {g['max_trade_risk_pct']:.1%}.")
    if daily_trades >= int(g["max_daily_trades"]):
        failures.append("Daily trade limit reached.")
    if g.get("require_defined_risk") and not defined_risk:
        failures.append("Trade is not defined-risk.")
    if earnings and equity > 0 and risk / equity > float(g["max_earnings_exposure_pct"]):
        failures.append("Earnings exposure exceeds guardrail.")
    if not g.get("allow_live_execution"):
        warnings.append("Live execution disabled. Candidate can only be queued or paper routed.")

    status = "approved" if not failures else "blocked"
    return {
        "status": status,
        "approved": not failures,
        "failures": failures,
        "warnings": warnings,
        "guardrails": g,
    }


def evaluate_trade_queue(candidates: list[dict[str, Any]], guardrails: dict[str, Any] | None = None, portfolio_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in candidates or []:
        result = evaluate_trade_guardrails(c, guardrails, portfolio_context)
        row = dict(c)
        row["guardrail_status"] = result["status"]
        row["guardrail_failures"] = "; ".join(result["failures"])
        row["guardrail_warnings"] = "; ".join(result["warnings"])
        rows.append(row)
    return rows
