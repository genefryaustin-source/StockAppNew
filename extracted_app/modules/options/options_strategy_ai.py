"""AI commentary for Phase 5 Strategy Command Center."""
from __future__ import annotations
from typing import Any
import json


def _call_ai(prompt: str, max_tokens: int = 800) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=max_tokens)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def explain_strategy_recommendation(ticker: str, candidate: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    payload = {"ticker": ticker, "candidate": candidate, "context": context or {}}
    prompt = f"""
You are an institutional options strategist. Explain this recommended multi-leg options strategy.

JSON:
{json.dumps(payload, default=str)[:10000]}

Return:
1. One-sentence recommendation
2. Why this strategy fits the current context
3. Key risks
4. Entry/management guidance
5. What would invalidate the setup

Do not promise profits. Be concise and specific.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    score = candidate.get("score") or {}
    metrics = candidate.get("metrics") or {}
    notes = score.get("notes") or []
    return (
        f"### Strategy Read — {candidate.get('strategy_name')}\n\n"
        f"- Overall score: **{candidate.get('overall_score')}** / 100, grade **{candidate.get('grade')}**.\n"
        f"- Category: **{candidate.get('category')}**.\n"
        f"- Expected value proxy: **${metrics.get('expected_value', 0):,.2f}**.\n"
        f"- Max profit/loss proxy: **${metrics.get('max_profit', 0):,.2f} / ${metrics.get('max_loss', 0):,.2f}**.\n"
        f"- Notes: {' '.join(notes) if notes else 'Monitor liquidity, spreads, event risk, and position sizing.'}"
    )


def summarize_strategy_command_center(ticker: str, candidates: list[dict[str, Any]]) -> str:
    top = candidates[:5]
    prompt = f"""
You are an institutional options strategy desk lead. Summarize the top options strategy candidates for {ticker}.

Top candidates:
{json.dumps(top, default=str)[:10000]}

Return:
- Best overall strategy
- Best income strategy
- Best risk-controlled strategy
- Best volatility strategy
- Key risks across the slate
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    if not top:
        return "No strategy candidates available."
    best = top[0]
    return f"Best overall candidate: **{best.get('strategy_name')}** with score **{best.get('overall_score')}** and grade **{best.get('grade')}**."
