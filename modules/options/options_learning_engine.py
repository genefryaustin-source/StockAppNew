"""Phase 8 learning engine: converts performance history into playbook lessons."""
from __future__ import annotations
from typing import Any
from modules.options.options_trade_outcome_analyzer import analyze_trade_outcomes
from modules.options.options_strategy_attribution_engine import strategy_attribution, tag_attribution


def generate_learning_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = analyze_trade_outcomes(records)
    strat = strategy_attribution(records)
    tags = tag_attribution(records)
    best_strategy = strat.head(1).to_dict("records")[0] if hasattr(strat, "empty") and not strat.empty else None
    weakest_strategy = strat.sort_values("total_pnl").head(1).to_dict("records")[0] if hasattr(strat, "empty") and not strat.empty else None
    lessons = []
    if summary.get("win_rate", 0) >= 60:
        lessons.append("Current trade selection is producing a positive hit rate; preserve entry discipline and avoid over-sizing.")
    elif summary.get("trade_count", 0) > 0:
        lessons.append("Win rate is below target; tighten filters around dealer alignment, premium concentration, and volatility regime.")
    if best_strategy:
        lessons.append(f"Best performing strategy: {best_strategy.get('strategy')} with total P/L {best_strategy.get('total_pnl')}.")
    if weakest_strategy and weakest_strategy != best_strategy:
        lessons.append(f"Weakest strategy: {weakest_strategy.get('strategy')}; review entry timing, IV regime, and exit management.")
    if summary.get("profit_factor", 0) and summary.get("profit_factor", 0) < 1:
        lessons.append("Profit factor is below 1.0; cut losing structures faster or reduce risk per trade.")
    return {
        "summary": summary,
        "strategy_attribution": strat.to_dict("records") if hasattr(strat, "to_dict") else [],
        "tag_attribution": tags.to_dict("records") if hasattr(tags, "to_dict") else [],
        "lessons": lessons,
        "best_strategy": best_strategy,
        "weakest_strategy": weakest_strategy,
    }
