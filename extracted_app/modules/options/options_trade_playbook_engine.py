"""Options execution playbooks for Phase 7."""
from __future__ import annotations
from typing import Any

PLAYBOOKS = [
    {"name": "Smart Money Following", "goal": "Follow high-conviction call/put premium when dealer/volatility context agrees.", "risk": "Defined-risk debit or credit spreads only."},
    {"name": "Dealer Alignment", "goal": "Use gamma walls, pin risk, and dealer hedging pressure to select strikes.", "risk": "Avoid open-ended gamma exposure."},
    {"name": "Volatility Expansion", "goal": "Use long straddles/strangles or calendars when IV is underpriced ahead of event risk.", "risk": "Cap debit at predefined portfolio heat."},
    {"name": "Volatility Crush", "goal": "Use iron condors or credit spreads when event premium is rich.", "risk": "Defined-risk spreads only."},
    {"name": "Income Generation", "goal": "Use covered calls, cash-secured puts, and high-probability spreads.", "risk": "Avoid earnings concentration."},
    {"name": "Portfolio Hedging", "goal": "Add index or underlying put spreads to offset portfolio delta/gamma risk.", "risk": "Size hedge against portfolio loss budget."},
    {"name": "Wheel Strategy", "goal": "Generate recurring income with CSP to assignment then covered calls.", "risk": "Only symbols approved for ownership."},
]


def list_playbooks() -> list[dict[str, Any]]:
    return list(PLAYBOOKS)


def choose_playbook(signals: dict[str, Any]) -> dict[str, Any]:
    direction = str(signals.get("direction") or "Neutral")
    vol = str(signals.get("volatility_regime") or "")
    dealer = str(signals.get("dealer_state") or "")
    score = float(signals.get("combined_signal_score") or 50)

    if "High" in vol or "Expansion" in vol:
        name = "Volatility Expansion"
    elif "Low" in vol or "Contraction" in vol:
        name = "Volatility Crush"
    elif "Negative" in dealer or "Short" in dealer:
        name = "Dealer Alignment"
    elif score >= 65 or score <= 35:
        name = "Smart Money Following"
    elif direction == "Neutral":
        name = "Income Generation"
    else:
        name = "Smart Money Following"

    for pb in PLAYBOOKS:
        if pb["name"] == name:
            result = dict(pb)
            result["reason"] = f"Selected from direction={direction}, score={score:.1f}, volatility={vol}, dealer={dealer}."
            return result
    return PLAYBOOKS[0]
