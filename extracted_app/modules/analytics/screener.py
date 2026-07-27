from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from modules.analytics.models import AnalyticsSnapshot


@dataclass
class ScreenerRow:
    symbol: str
    sector: Optional[str]
    rating: Optional[str]

    composite: Optional[float]
    confidence: Optional[float]

    quality: Optional[float]
    growth: Optional[float]
    value: Optional[float]
    momentum: Optional[float]
    risk: Optional[float]


def _to_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def run_screener(
    db: Session,
    tenant_id: str,
    sector: Optional[str] = None,
    min_composite: Optional[float] = None,
    min_confidence: Optional[float] = None,
    rating_in: Optional[List[str]] = None,
    min_quality: Optional[float] = None,
    min_growth: Optional[float] = None,
    min_value: Optional[float] = None,
    min_momentum: Optional[float] = None,
    max_risk: Optional[float] = None,
) -> List[ScreenerRow]:

    # ------------------------------------------------
    # Fetch snapshots ordered newest first per symbol
    # ------------------------------------------------

    rows = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.asof != None,
        )
        .order_by(
            AnalyticsSnapshot.symbol,
            AnalyticsSnapshot.asof.desc(),
        )
        .all()
    )

    if not rows:
        return []

    # ------------------------------------------------
    # Deduplicate → latest snapshot per symbol
    # ------------------------------------------------

    latest = {}
    for r in rows:
        if r.symbol not in latest:
            latest[r.symbol] = r

    rows = list(latest.values())

    results: List[ScreenerRow] = []

    for r in rows:

        composite = _to_float(getattr(r, "composite_score", None))
        confidence = _to_float(getattr(r, "confidence_score", None))

        quality = _to_float(getattr(r, "quality_score", None))
        growth = _to_float(getattr(r, "growth_score", None))
        value = _to_float(getattr(r, "value_score", None))
        momentum = _to_float(getattr(r, "momentum_score", None))
        risk = _to_float(getattr(r, "risk_score", None))

        rating = getattr(r, "rating", None)
        sector_val = getattr(r, "sector", None)

        # ------------------------------------------------
        # Filters
        # ------------------------------------------------

        if sector and sector_val != sector:
            continue

        if min_composite is not None and (composite is None or composite < min_composite):
            continue

        if min_confidence is not None and (confidence is None or confidence < min_confidence):
            continue

        if rating_in and rating not in rating_in:
            continue

        if min_quality is not None and (quality is None or quality < min_quality):
            continue

        if min_growth is not None and (growth is None or growth < min_growth):
            continue

        if min_value is not None and (value is None or value < min_value):
            continue

        if min_momentum is not None and (momentum is None or momentum < min_momentum):
            continue

        if max_risk is not None and (risk is not None and risk > max_risk):
            continue

        results.append(
            ScreenerRow(
                symbol=r.symbol,
                sector=sector_val,
                rating=rating,
                composite=composite,
                confidence=confidence,
                quality=quality,
                growth=growth,
                value=value,
                momentum=momentum,
                risk=risk,
            )
        )

    # ------------------------------------------------
    # Sort results
    # ------------------------------------------------

    results.sort(
        key=lambda x: (
            x.composite if x.composite is not None else -1e18,
            x.confidence if x.confidence is not None else -1e18,
        ),
        reverse=True,
    )

    return results