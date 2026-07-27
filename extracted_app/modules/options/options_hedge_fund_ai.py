"""Phase 12 — Hedge fund AI commentary."""
from __future__ import annotations
import json
from typing import Any


def _call_ai(prompt: str, max_tokens: int = 900) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=max_tokens)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def hedge_fund_cio_memo(report: dict[str, Any]) -> str:
    prompt = f"""You are a hedge fund CIO. Produce a concise investment committee memo from this operating system report.

REPORT JSON:
{json.dumps(report, default=str)[:12000]}

Return sections: Executive Decision, Capital Allocation, Risk Constraints, Strategy Book, Trade Queue, Compliance Notes, Next Actions. Be specific and avoid guarantees.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans

    committee = report.get("committee", {})
    capital = report.get("capital", {})
    risk = report.get("risk", {})

    return (
        f"### CIO Operating Memo — {report.get('ticker', '')}\n\n"
        f"**Committee Decision:** {committee.get('decision', 'Pending')} with confidence {committee.get('committee_confidence', '—')}%.\n\n"
        f"**Capital:** Portfolio value ${capital.get('portfolio_value', 0):,.0f}; utilization {capital.get('capital_utilization_pct', '—')}%; liquidity score {capital.get('liquidity_score', '—')}.\n\n"
        f"**Risk:** {risk.get('status', 'Review Required')} with score {risk.get('risk_score', '—')}/100.\n\n"
        "**Next Actions:** validate live prices, confirm liquidity, apply guardrails, and route only approved risk-defined trades."
    )
