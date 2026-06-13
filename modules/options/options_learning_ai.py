"""AI commentary for Phase 8 learning center."""
from __future__ import annotations
from typing import Any
import json


def explain_learning_report(report: dict[str, Any]) -> str:
    try:
        from modules.options.options_ai import _claude
        prompt = f"""
You are an options performance coach. Explain this learning report and produce concise improvement guidance.

Report JSON:
{json.dumps(report, default=str)[:8000]}

Return:
1. What is working
2. What is hurting performance
3. What to change in strategy selection
4. What to change in risk management
5. One concrete next rule to implement
"""
        ans = _claude(prompt, max_tokens=700)
        if ans and "API_KEY not found" not in ans and not ans.startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    summary = report.get("summary", {})
    lessons = report.get("lessons", [])
    return "### Learning Summary\n\n" + "\n".join([f"- {x}" for x in lessons]) + f"\n\nWin rate: {summary.get('win_rate', 0)}%, Total P/L: {summary.get('total_pnl', 0)}."
