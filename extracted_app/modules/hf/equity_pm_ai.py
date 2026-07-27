"""
modules/hf/equity_pm_ai.py

AI explanations for HF-4 Autonomous Equity PM.
"""
from __future__ import annotations
from typing import Any
import json


def _call_ai(prompt: str) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=900)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def explain_pm_cycle(pm_result: dict[str, Any]) -> str:
    prompt = f"""
You are a hedge fund portfolio manager. Explain this autonomous equity PM cycle.

PM result:
{json.dumps(pm_result, default=str)[:9000]}

Return:
1. Portfolio action summary
2. Highest priority adds/reductions
3. Risk and turnover concerns
4. Whether human approval is needed
5. What to monitor next
"""
    ans = _call_ai(prompt)
    if ans:
        return ans

    decisions = pm_result.get("decisions", [])
    adds = [d for d in decisions if d.get("action") in {"Add", "Increase"}]
    cuts = [d for d in decisions if d.get("action") in {"Reduce", "Trim"}]
    return (
        "### Autonomous PM Summary\\n\\n"
        f"- Portfolio action: **{pm_result.get('portfolio_action', 'NO_ACTION')}**\\n"
        f"- Adds/Increases: **{len(adds)}**\\n"
        f"- Reductions/Trims: **{len(cuts)}**\\n"
        f"- Turnover estimate: **{pm_result.get('turnover_estimate', 0):.1%}**\\n"
        f"- Guardrail status: **{pm_result.get('guardrail_status', 'UNKNOWN')}**\\n\\n"
        "Human approval is recommended before execution."
    )
