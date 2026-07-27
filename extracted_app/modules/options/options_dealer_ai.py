"""
modules/options/options_dealer_ai.py

AI explanation helper for Phase 2 Dealer Analytics.
Uses the existing options AI Claude helper when available and falls back to deterministic commentary.
"""
from __future__ import annotations

import json
from typing import Any


def explain_dealer_exposure(report: dict[str, Any]) -> str:
    ticker = report.get("ticker", "")
    prompt = f"""
You are an institutional options dealer-positioning analyst. Explain this dealer exposure report.

Report JSON:
{json.dumps(report, default=str)[:9000]}

Return:
1. One-sentence dealer positioning read
2. What the gamma state means for intraday behavior
3. Key walls / zero gamma / pin risk levels
4. What would invalidate the read
5. Monitoring checklist

Be concise, practical, and do not imply certainty.
"""
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=750)
        if ans and "API_KEY not found" not in ans and not str(ans).startswith("AI unavailable"):
            return ans
    except Exception:
        pass

    return _fallback_commentary(ticker, report)


def _money(v: Any) -> str:
    try:
        x = float(v or 0)
        sign = "-" if x < 0 else ""
        x = abs(x)
        if x >= 1_000_000_000:
            return f"{sign}${x/1_000_000_000:.2f}B"
        if x >= 1_000_000:
            return f"{sign}${x/1_000_000:.2f}M"
        if x >= 1_000:
            return f"{sign}${x/1_000:.1f}K"
        return f"{sign}${x:,.0f}"
    except Exception:
        return "—"


def _fallback_commentary(ticker: str, report: dict[str, Any]) -> str:
    state = report.get("net_gamma_state", "Neutral Gamma")
    pressure = report.get("hedging_pressure", "Unknown")
    zero = report.get("zero_gamma")
    call_wall = report.get("gamma_wall_call")
    put_wall = report.get("gamma_wall_put")
    pin = report.get("pin_risk_strike")
    total_gex = _money(report.get("total_gex"))
    total_dex = _money(report.get("total_dex"))

    return (
        f"### Dealer Positioning Read — {ticker}\n\n"
        f"- Net gamma state: **{state}** with estimated GEX of **{total_gex}**.\n"
        f"- Hedging pressure: **{pressure}**.\n"
        f"- Estimated DEX: **{total_dex}**.\n"
        f"- Zero gamma: **${zero:,.2f}**.\n" if zero else ""
    ) + (
        f"- Call gamma wall: **${call_wall:,.2f}**.\n" if call_wall else ""
    ) + (
        f"- Put gamma wall: **${put_wall:,.2f}**.\n" if put_wall else ""
    ) + (
        f"- Pin risk strike: **${pin:,.2f}**.\n" if pin else ""
    ) + "\nDealer analytics are chain-derived estimates; confirm with live flow, event calendar, and spread/liquidity conditions."
