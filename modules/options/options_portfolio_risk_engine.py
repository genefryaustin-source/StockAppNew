"""Portfolio risk scoring and risk flag engine."""
from __future__ import annotations
from typing import Any


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def score_portfolio_risk(summary: dict[str, Any], exposure: dict[str, Any]) -> dict[str, Any]:
    total = _n(summary.get("total_market_value"))
    delta = abs(_n(exposure.get("net_delta")))
    gamma = abs(_n(exposure.get("net_gamma")))
    theta = _n(exposure.get("net_theta"))
    vega = abs(_n(exposure.get("net_vega")))
    pnl_pct = abs(_n(summary.get("pnl_pct")))
    count = _n(summary.get("position_count"))

    score = 10.0
    if total > 0:
        score += min(20, delta / max(total / 100, 1) * 5)
        score += min(18, gamma / max(total / 1000, 1) * 4)
        score += min(15, vega / max(total / 100, 1) * 4)
    if theta < 0:
        score += min(12, abs(theta) / 100)
    score += min(15, pnl_pct * 100)
    score += min(10, count / 20 * 10)
    score = round(max(0, min(100, score)), 1)

    if score >= 80:
        label = "Critical"
    elif score >= 60:
        label = "High"
    elif score >= 35:
        label = "Medium"
    else:
        label = "Low"

    flags = []
    if delta > 500:
        flags.append("Portfolio is delta-heavy; large directional exposure detected.")
    if gamma > 100:
        flags.append("High gamma exposure; P&L may accelerate rapidly near strikes.")
    if vega > 1000:
        flags.append("High vega exposure; portfolio is sensitive to volatility repricing.")
    if theta < -500:
        flags.append("Large negative theta; decay risk is material.")
    if count > 20:
        flags.append("Many open positions; operational and correlation risk may be elevated.")
    if not flags:
        flags.append("No major portfolio risk concentration detected from available data.")

    return {"score": score, "label": label, "flags": flags}
