# ============================================================
# modules/preipo/scoring.py
# Pre-IPO probability and readiness scoring
# ============================================================

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, Optional


def _months_since(dt: Optional[datetime]) -> Optional[float]:
    if not dt:
        return None
    if dt.tzinfo is None:
        now = datetime.utcnow()
    else:
        now = datetime.now(UTC)
    return max(0.0, (now - dt).days / 30.4375)


def score_preipo_company(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic scoring engine. Uses public signals only.
    Score is intentionally explainable and can be replaced later by ML.
    """

    score = 0.0
    readiness = 0.0
    reasons = []

    valuation = profile.get("last_known_valuation")
    funding_amount = profile.get("last_funding_amount")
    funding_date = profile.get("last_funding_date")
    sec_status = (profile.get("sec_filing_status") or "").lower()
    filing_type = (profile.get("latest_sec_filing_type") or "").upper()

    if valuation:
        if valuation >= 10_000_000_000:
            score += 22
            readiness += 20
            reasons.append("Large private valuation")
        elif valuation >= 2_000_000_000:
            score += 14
            readiness += 12
            reasons.append("IPO-scale valuation")
        elif valuation >= 500_000_000:
            score += 7
            readiness += 6
            reasons.append("Growth-stage valuation")

    if funding_amount:
        if funding_amount >= 250_000_000:
            score += 12
            readiness += 8
            reasons.append("Large late-stage funding round")
        elif funding_amount >= 50_000_000:
            score += 7
            readiness += 5
            reasons.append("Meaningful institutional funding")

    months = _months_since(funding_date)
    if months is not None:
        if months <= 12:
            score += 9
            readiness += 7
            reasons.append("Recent funding activity")
        elif months <= 36:
            score += 5
            readiness += 4
            reasons.append("Recent enough private-market activity")

    if filing_type in {"S-1", "S-1/A", "F-1", "F-1/A", "424B4"}:
        score += 35
        readiness += 40
        reasons.append("IPO registration filing detected")
    elif "filed" in sec_status:
        score += 20
        readiness += 25
        reasons.append("SEC filing status indicates IPO activity")

    if profile.get("source"):
        score += 4
        readiness += 3
        reasons.append("External source data available")

    score = min(100.0, round(score, 2))
    readiness = min(100.0, round(readiness, 2))

    if score >= 75:
        window = "0-12 months"
        confidence = "High"
    elif score >= 50:
        window = "12-24 months"
        confidence = "Medium"
    elif score >= 25:
        window = "24+ months"
        confidence = "Low"
    else:
        window = "Unknown"
        confidence = "Low"

    return {
        "ipo_probability_score": score,
        "ipo_readiness_score": readiness,
        "expected_ipo_window": window,
        "confidence": confidence,
        "reasons": reasons,
    }
