"""AI narrative layer for Phase 11 Autonomous Portfolio Manager."""
from __future__ import annotations
from typing import Any
import json


def _call_ai(prompt: str, max_tokens: int = 700) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=max_tokens)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def explain_autonomous_pm_report(report: dict[str, Any]) -> str:
    prompt = f"""
You are an autonomous portfolio manager. Explain this options portfolio management report.

Report JSON:
{json.dumps(report, default=str)[:9000]}

Return:
1. Portfolio risk read
2. Allocation recommendation
3. Rebalance recommendation
4. Hedge recommendation
5. Trade queue recommendation
6. Governance caveats
Be concise and do not imply guaranteed returns.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    state = report.get("state", {})
    alloc = report.get("allocation", {})
    reb = report.get("rebalance", {})
    return (
        f"### Autonomous PM Read — {state.get('ticker','')}\n\n"
        f"- Portfolio heat: **{alloc.get('capital_heat_pct', 0)}%** of configured risk budget.\n"
        f"- Net Greeks: Δ {state.get('net_delta', 0)}, Γ {state.get('net_gamma', 0)}, Θ {state.get('net_theta', 0)}, V {state.get('net_vega', 0)}.\n"
        f"- Rebalance required: **{reb.get('rebalance_required', False)}**.\n"
        "- Human approval remains recommended for live execution."
    )
