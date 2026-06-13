"""AI commentary for Phase 6 Options Portfolio Command Center."""
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


def explain_portfolio_risk(report: dict[str, Any]) -> str:
    prompt = f"""
You are an institutional options portfolio risk manager. Review this options portfolio report.

Report JSON:
{json.dumps(report, default=str)[:9000]}

Return:
1. One-sentence portfolio risk read
2. Top three risks
3. Greeks imbalance assessment
4. Stress scenario concern
5. Specific hedge or risk-reduction suggestions
6. Income optimization idea if appropriate

Be direct and do not imply guaranteed outcomes.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    summary = report.get("summary", {})
    risk = report.get("risk", {})
    exposure = report.get("exposure", {})
    return (
        f"### Portfolio AI Read\n\n"
        f"- Risk level: **{risk.get('label', 'Unknown')}** ({risk.get('score', 0)}/100).\n"
        f"- Net Greeks: Delta {exposure.get('net_delta', 0):,.1f}, Gamma {exposure.get('net_gamma', 0):,.1f}, "
        f"Theta {exposure.get('net_theta', 0):,.1f}, Vega {exposure.get('net_vega', 0):,.1f}.\n"
        f"- Total options exposure: ${summary.get('total_market_value', 0):,.0f}.\n"
        "- Review largest-risk positions and stress-test downside/volatility shock scenarios before adding new risk."
    )
