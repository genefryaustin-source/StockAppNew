"""AI commentary for Phase 4 Volatility & Earnings Intelligence Suite."""
from __future__ import annotations
import json
from typing import Any


def _fallback(report: dict[str, Any]) -> str:
    event = report.get("event_pricing", {})
    iv_rank = report.get("iv_rank", {})
    iv_pct = report.get("iv_percentile", {})
    earnings = report.get("earnings", {})
    term = report.get("term_structure", {})
    skew = report.get("skew", {})
    return (
        f"### Volatility Intelligence Read\n\n"
        f"- Event pricing: **{event.get('label', 'Balanced')}**.\n"
        f"- IV Rank: **{iv_rank.get('iv_rank', 'N/A')}** / IV Percentile: **{iv_pct.get('iv_percentile', 'N/A')}**.\n"
        f"- Term structure: **{term.get('regime', 'Unavailable')}**.\n"
        f"- Skew: **{skew.get('label', 'Unavailable')}**.\n"
        f"- Earnings move estimate: **{earnings.get('expected_move_pct', 0) or 0:.1%}** with **{earnings.get('vol_crush_label', 'unknown')}**.\n\n"
        f"Suggested strategy families: {', '.join(event.get('recommended_strategies', [])) or 'defined-risk spreads / wait for better setup'}."
    )


def explain_volatility_report(report: dict[str, Any]) -> str:
    try:
        from modules.options.options_ai import _claude
        prompt = f"""
You are an institutional volatility trader. Explain this options volatility and earnings report.

Report JSON:
{json.dumps(report, default=str)[:9000]}

Return:
1. Directional volatility regime read
2. Whether premium looks rich or cheap
3. Term-structure and skew interpretation
4. Earnings/event pricing read
5. Best strategy families and risk caveats

Be specific and concise. Do not claim certainty.
"""
        ans = _claude(prompt, max_tokens=800)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return _fallback(report)
