"""
modules/options/options_institutional_sentiment.py

Institutional options sentiment scoring for Options Smart Money Center.
"""
from __future__ import annotations

from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def score_institutional_sentiment(flow: dict[str, Any], dark_pool: dict[str, Any] | None = None, whale_summary: dict[str, Any] | None = None, sweep_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    dark_pool = dark_pool or {}
    whale_summary = whale_summary or {}
    sweep_summary = sweep_summary or {}

    total_prem = _num(flow.get("total_premium"))
    net_prem = _num(flow.get("net_premium"))
    pc_vol = _num(flow.get("pc_vol"), 1.0)
    pc_oi = _num(flow.get("pc_oi"), 1.0)
    iv_rank = _num(flow.get("iv_rank"), 50.0)

    premium_component = 0.0
    if total_prem > 0:
        premium_component = max(-30.0, min(30.0, (net_prem / total_prem) * 45.0))

    pc_component = 0.0
    # lower put/call = bullish, higher = bearish
    if pc_vol:
        pc_component += max(-15.0, min(15.0, (1.0 - pc_vol) * 12.0))
    if pc_oi:
        pc_component += max(-10.0, min(10.0, (1.0 - pc_oi) * 8.0))

    whale_component = 0.0
    wc = _num(whale_summary.get("call_whales"))
    wp = _num(whale_summary.get("put_whales"))
    wt = wc + wp
    if wt > 0:
        whale_component = ((wc - wp) / wt) * 20.0

    sweep_component = 0.0
    sc = _num(sweep_summary.get("call_sweeps"))
    sp = _num(sweep_summary.get("put_sweeps"))
    st = sc + sp
    if st > 0:
        sweep_component = ((sc - sp) / st) * 15.0

    dark_component = 0.0
    inst_score = dark_pool.get("inst_score")
    z = dark_pool.get("z_score")
    signal = str(dark_pool.get("signal") or "")
    if inst_score is not None:
        dark_component = max(-8.0, min(8.0, (_num(inst_score) - 50.0) / 50.0 * 8.0))
    if z is not None:
        dark_component += max(-5.0, min(5.0, _num(z) * 2.0))
    if "High" in signal or "Unusual" in signal:
        dark_component += 4.0

    iv_component = max(-5.0, min(5.0, (iv_rank - 50.0) / 50.0 * 5.0))

    raw = 50.0 + premium_component + pc_component + whale_component + sweep_component + dark_component + iv_component
    score = round(max(0.0, min(100.0, raw)), 1)

    if score >= 80:
        label = "Very Bullish"
    elif score >= 62:
        label = "Bullish"
    elif score <= 20:
        label = "Very Bearish"
    elif score <= 38:
        label = "Bearish"
    else:
        label = "Neutral"

    confidence = min(100.0, 35.0 + min(30.0, total_prem / 10_000_000 * 30.0) + min(20.0, _num(whale_summary.get("whale_count")) * 3.0) + min(15.0, _num(sweep_summary.get("sweep_count")) * 2.0))

    return {
        "score": score,
        "label": label,
        "confidence": round(confidence, 1),
        "components": {
            "premium": round(premium_component, 1),
            "put_call": round(pc_component, 1),
            "whales": round(whale_component, 1),
            "sweeps": round(sweep_component, 1),
            "dark_pool": round(dark_component, 1),
            "iv": round(iv_component, 1),
        },
        "explanation": build_sentiment_explanation(label, score, flow, dark_pool, whale_summary, sweep_summary),
    }


def build_sentiment_explanation(label: str, score: float, flow: dict[str, Any], dark_pool: dict[str, Any], whale_summary: dict[str, Any], sweep_summary: dict[str, Any]) -> str:
    parts = [f"Institutional options sentiment is {label} with a score of {score:.1f}/100."]
    net = _num(flow.get("net_premium"))
    if net > 0:
        parts.append("Net premium is call-skewed.")
    elif net < 0:
        parts.append("Net premium is put-skewed.")
    if whale_summary.get("whale_count"):
        parts.append(f"Detected {whale_summary.get('whale_count')} whale/block-style contracts.")
    if sweep_summary.get("sweep_count"):
        parts.append(f"Detected {sweep_summary.get('sweep_count')} sweep/opening-flow candidates.")
    if dark_pool.get("signal"):
        parts.append(f"Dark-pool/institutional proxy signal: {dark_pool.get('signal')}.")
    return " ".join(parts)
