"""AI commentary for execution decisions with deterministic fallback."""
from __future__ import annotations
from typing import Any
import json


def explain_execution_report(report: dict[str, Any]) -> str:
    try:
        from modules.options.options_ai import _claude
        prompt = """
You are an institutional options execution supervisor. Explain this execution report in concise operational language.
Return: directional read, best candidate, guardrail issues, and next action.
Report JSON:
""" + json.dumps(report, default=str)[:9000]
        ans = _claude(prompt, max_tokens=700)
        if ans and "API_KEY" not in ans and not ans.startswith("AI unavailable"):
            return ans
    except Exception:
        pass

    signals = report.get("signals", {})
    queue = report.get("trade_queue", [])
    best = queue[0] if queue else {}
    return (
        f"### Execution Read — {report.get('ticker','')}\n\n"
        f"- Direction: **{signals.get('direction','Neutral')}** with combined score **{signals.get('combined_signal_score',50)}**.\n"
        f"- Best candidate: **{best.get('strategy','No candidate')}**.\n"
        f"- Guardrail status: **{best.get('guardrail_status','N/A')}**.\n"
        "- Next action: review risk, liquidity, and approval requirements before routing."
    )
