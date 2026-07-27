"""
modules/options/options_smart_money_engine.py

Phase 1 master engine for the Options Smart Money Center.
Combines existing options flow, FINRA/proxy dark pool intelligence, whale detection,
sweep detection, premium tracking, and institutional sentiment scoring.
"""
from __future__ import annotations

from typing import Any

from modules.options.options_flow_aggregator import aggregate_premium_flow
from modules.options.options_whale_tracker import track_whales, whale_summary
from modules.options.options_sweep_detector import detect_sweeps, sweep_summary
from modules.options.options_institutional_sentiment import score_institutional_sentiment
from modules.options.options_premium_tracker import premium_by_type, premium_by_expiry, premium_by_strike


def _safe_dark_pool(ticker: str) -> dict[str, Any]:
    try:
        from modules.options_flow.flow_service import get_finra_dark_pool
        result = get_finra_dark_pool(ticker)
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        return {"error": str(exc), "source": "unavailable"}


def _safe_insiders(ticker: str) -> list[dict[str, Any]]:
    try:
        from modules.options_flow.flow_service import get_insider_transactions
        result = get_insider_transactions(ticker)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def build_options_smart_money_report(ticker: str) -> dict[str, Any]:
    flow = aggregate_premium_flow(ticker)
    if "error" in flow:
        return {
            "ticker": ticker.upper(),
            "error": flow.get("error"),
            "flow": flow,
            "whales": [],
            "sweeps": [],
            "top_contracts": [],
        }

    unusual = list(flow.get("unusual_contracts") or [])
    whales = track_whales(unusual)
    sweeps = detect_sweeps(unusual)
    wsum = whale_summary(whales)
    ssum = sweep_summary(sweeps)
    dark_pool = _safe_dark_pool(ticker)
    insiders = _safe_insiders(ticker)
    sentiment = score_institutional_sentiment(flow, dark_pool, wsum, ssum)

    premium_type = premium_by_type(unusual)
    exp_df = premium_by_expiry(unusual)
    strike_df = premium_by_strike(unusual)

    top_contracts = sorted(
        unusual,
        key=lambda r: float(r.get("premium_est") or 0),
        reverse=True,
    )[:20]

    conviction_score = calculate_conviction_score(flow, sentiment, wsum, ssum, dark_pool)

    return {
        "ticker": ticker.upper(),
        "flow": flow,
        "whales": whales,
        "whale_summary": wsum,
        "sweeps": sweeps,
        "sweep_summary": ssum,
        "dark_pool": dark_pool,
        "insiders": insiders,
        "sentiment": sentiment,
        "premium_by_type": premium_type,
        "premium_by_expiry": exp_df.to_dict("records") if hasattr(exp_df, "to_dict") else [],
        "premium_by_strike": strike_df.to_dict("records") if hasattr(strike_df, "to_dict") else [],
        "top_contracts": top_contracts,
        "conviction_score": conviction_score,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }


def calculate_conviction_score(flow: dict[str, Any], sentiment: dict[str, Any], whale_summary: dict[str, Any], sweep_summary: dict[str, Any], dark_pool: dict[str, Any]) -> dict[str, Any]:
    def n(v, d=0.0):
        try:
            return float(v or d)
        except Exception:
            return d

    total_premium = n(flow.get("total_premium"))
    net_abs_ratio = abs(n(flow.get("net_premium"))) / total_premium if total_premium else 0
    whale_count = n(whale_summary.get("whale_count"))
    sweep_count = n(sweep_summary.get("sweep_count"))
    sentiment_distance = abs(n(sentiment.get("score"), 50) - 50) / 50
    dark_z = abs(n(dark_pool.get("z_score"))) if dark_pool.get("z_score") is not None else 0

    score = 0.0
    score += min(25, total_premium / 25_000_000 * 25)
    score += min(20, net_abs_ratio * 30)
    score += min(20, whale_count * 4)
    score += min(15, sweep_count * 3)
    score += min(10, sentiment_distance * 10)
    score += min(10, dark_z * 3)
    score = round(max(0, min(100, score)), 1)

    label = "Very High" if score >= 80 else "High" if score >= 62 else "Moderate" if score >= 40 else "Low"
    return {
        "score": score,
        "label": label,
        "drivers": {
            "total_premium": round(total_premium, 2),
            "net_abs_ratio": round(net_abs_ratio, 3),
            "whale_count": int(whale_count),
            "sweep_count": int(sweep_count),
            "sentiment_distance": round(sentiment_distance, 3),
            "dark_z": round(dark_z, 2),
        },
    }
