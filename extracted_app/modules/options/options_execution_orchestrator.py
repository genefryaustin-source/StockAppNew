"""Phase 7 master orchestrator for autonomous options execution intelligence."""
from __future__ import annotations
from typing import Any

from modules.options.options_signal_engine import collect_execution_signals
from modules.options.options_trade_playbook_engine import choose_playbook
from modules.options.options_execution_guardrails import evaluate_trade_queue, default_guardrails
from modules.options.options_order_intelligence import recommend_order_ticket, score_order_quality
from modules.options.options_trade_router import route_trade_queue
from modules.options.options_alert_engine import generate_execution_alerts
from modules.options.options_watchtower import build_watchtower_snapshot
from modules.options.options_autonomous_optimizer import optimize_trade_queue


def build_trade_candidates(ticker: str, signals: dict[str, Any], playbook: dict[str, Any]) -> list[dict[str, Any]]:
    direction = str(signals.get("direction") or "Neutral")
    score = float(signals.get("combined_signal_score") or 50)
    dealer = str(signals.get("dealer_state") or "")
    vol = str(signals.get("volatility_regime") or "")

    if direction == "Bullish":
        base = [
            {"strategy": "Bull Put Spread", "debit_credit": "credit", "defined_risk": True, "confidence": score, "max_loss": 1500, "contracts": 1},
            {"strategy": "Bull Call Spread", "debit_credit": "debit", "defined_risk": True, "confidence": score - 3, "max_loss": 1200, "contracts": 1},
        ]
    elif direction == "Bearish":
        base = [
            {"strategy": "Bear Call Spread", "debit_credit": "credit", "defined_risk": True, "confidence": 100 - score, "max_loss": 1500, "contracts": 1},
            {"strategy": "Bear Put Spread", "debit_credit": "debit", "defined_risk": True, "confidence": 100 - score - 3, "max_loss": 1200, "contracts": 1},
        ]
    else:
        base = [
            {"strategy": "Iron Condor", "debit_credit": "credit", "defined_risk": True, "confidence": 58, "max_loss": 2000, "contracts": 1},
            {"strategy": "Calendar Spread", "debit_credit": "debit", "defined_risk": True, "confidence": 55, "max_loss": 1000, "contracts": 1},
        ]

    if "Expansion" in vol or "High" in vol:
        base.insert(0, {"strategy": "Long Strangle", "debit_credit": "debit", "defined_risk": True, "confidence": max(score, 62), "max_loss": 900, "contracts": 1, "volatility_trade": True})
    if "Negative" in dealer or "Short" in dealer:
        for b in base:
            b["dealer_alignment"] = "Hedging pressure may amplify movement."
            b["confidence"] = min(100, float(b.get("confidence", 50)) + 4)

    for b in base:
        b["ticker"] = ticker.upper()
        b["playbook"] = playbook.get("name")
        b["risk_score"] = min(100, float(b.get("max_loss", 0)) / 50)
        b["liquidity_score"] = 65
        b["earnings_trade"] = "Earnings" in playbook.get("name", "")
    return optimize_trade_queue(base)


def build_execution_report(ticker: str, paper: bool = True, guardrails: dict[str, Any] | None = None, portfolio_context: dict[str, Any] | None = None) -> dict[str, Any]:
    signal_bundle = collect_execution_signals(ticker)
    signals = signal_bundle.get("signals", {})
    playbook = choose_playbook(signals)
    candidates = build_trade_candidates(ticker, signals, playbook)
    checked = evaluate_trade_queue(candidates, guardrails or default_guardrails(), portfolio_context or {})
    for c in checked:
        c["order_quality"] = score_order_quality(c)
        c["order_ticket"] = recommend_order_ticket(c, paper=paper)
    routes = route_trade_queue(checked, paper=paper)
    report = {
        "ticker": ticker.upper(),
        "paper": paper,
        "signals": signals,
        "signal_bundle": signal_bundle,
        "playbook": playbook,
        "trade_queue": checked,
        "routes": routes,
        "guardrails": guardrails or default_guardrails(),
    }
    report["alerts"] = generate_execution_alerts(report)
    report["watchtower"] = build_watchtower_snapshot(report)
    return report
