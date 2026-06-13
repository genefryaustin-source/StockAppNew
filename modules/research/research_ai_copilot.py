from __future__ import annotations
from typing import Any
import json


def _call_ai(prompt: str) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=900)
        if ans and "API_KEY" not in ans and not ans.startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def research_copilot_response(ticker: str, report: dict[str, Any], question: str = "") -> str:
    prompt = f"""
You are an institutional equity research analyst. Review this research report and answer the user's question.
Ticker: {ticker}
Question: {question or 'Give me the investment thesis, key risks, catalysts, and best options expression.'}
Report JSON: {json.dumps(report, default=str)[:12000]}
Return concise, actionable research notes. Do not guarantee outcomes.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    sc = report.get("scorecard", {})
    thesis = report.get("thesis", {})
    return (
        f"### Research Copilot — {ticker.upper()}\n\n"
        f"Composite score: **{sc.get('composite_research_score', 50)}/100** ({sc.get('research_label', 'Neutral')}).\n\n"
        f"**Bull thesis:** " + " ".join(thesis.get("bull_thesis", [])[:3]) + "\n\n"
        f"**Bear/Risk thesis:** " + " ".join(thesis.get("bear_thesis", [])[:3]) + "\n\n"
        f"**Options expression:** {thesis.get('options_expression', 'Use defined-risk structures until confirmation improves.')}"
    )
