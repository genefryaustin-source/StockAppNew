"""
modules/options/options_smart_money_ai.py

AI commentary for Phase 1 Options Smart Money Center.
Falls back gracefully when ANTHROPIC_API_KEY is unavailable.
"""
from __future__ import annotations

import json
from typing import Any


def _call_ai(prompt: str, max_tokens: int = 700) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=max_tokens)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def explain_smart_money_report(report: dict[str, Any]) -> str:
    ticker = report.get("ticker", "")
    prompt = f"""
You are an institutional options-flow analyst. Explain this options smart-money report.

Report JSON:
{json.dumps(report, default=str)[:9000]}

Return:
1. One-sentence directional read
2. Three most important flow observations
3. Whale/sweep interpretation
4. Risk caveats
5. What a trader should monitor next

Be specific and concise. Do not claim trades are guaranteed.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans

    sent = report.get("sentiment", {})
    conv = report.get("conviction_score", {})
    flow = report.get("flow", {})
    wsum = report.get("whale_summary", {})
    ssum = report.get("sweep_summary", {})
    return (
        f"### Smart Money Read — {ticker}\n\n"
        f"- Institutional sentiment: **{sent.get('label', 'Neutral')}** ({sent.get('score', 50)}/100).\n"
        f"- Conviction: **{conv.get('label', 'Low')}** ({conv.get('score', 0)}/100).\n"
        f"- Net premium: **{flow.get('net_premium', 0):,.0f}** with {wsum.get('whale_count', 0)} whale/block candidates and {ssum.get('sweep_count', 0)} sweep candidates.\n"
        "- Confirm liquidity, bid/ask spreads, opening-vs-closing status, and event risk before acting."
    )
