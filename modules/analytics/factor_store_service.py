from __future__ import annotations

from datetime import datetime, UTC
from sqlalchemy.orm import Session

from modules.analytics.factor_store_models import FactorStore


def upsert_factor_store(db: Session, snapshot) -> FactorStore:
    """
    Upsert latest factor values from an AnalyticsSnapshot-like object
    into FactorStore.
    """

    row = (
        db.query(FactorStore)
        .filter(
            FactorStore.tenant_id == snapshot.tenant_id,
            FactorStore.symbol == snapshot.symbol,
        )
        .first()
    )

    payload = dict(
        tenant_id=snapshot.tenant_id,
        symbol=snapshot.symbol,
        updated_at=datetime.now(UTC),

        sector=getattr(snapshot, "sector", None),
        rating=getattr(snapshot, "rating", None),

        composite=getattr(snapshot, "composite_score", None),
        confidence=getattr(snapshot, "confidence_score", None),

        quality=getattr(snapshot, "quality_score", None),
        growth=getattr(snapshot, "growth_score", None),
        value=getattr(snapshot, "value_score", None),
        momentum=getattr(snapshot, "momentum_score", None),
        risk=getattr(snapshot, "risk_score", None),

        rsi=getattr(snapshot, "rsi_14", None),
        sma50=getattr(snapshot, "sma_50", None),
        sma200=getattr(snapshot, "sma_200", None),
        support=getattr(snapshot, "support", None),
        resistance=getattr(snapshot, "resistance", None),
        volatility=getattr(snapshot, "vol_20d", None),
        drawdown=getattr(snapshot, "max_drawdown_1y", None),
        trend=getattr(snapshot, "trend", None),

        revenue_cagr=getattr(snapshot, "revenue_cagr_3y", None),
        gross_margin=getattr(snapshot, "gross_margin", None),
        op_margin=getattr(snapshot, "op_margin", None),
        fcf_margin=getattr(snapshot, "fcf_margin", None),

        pe=getattr(snapshot, "pe_ttm", None),
        ps=getattr(snapshot, "ps_ttm", None),
        ev_ebitda=getattr(snapshot, "ev_ebitda", None),
    )

    if row:
        for k, v in payload.items():
            setattr(row, k, v)
    else:
        row = FactorStore(**payload)
        db.add(row)

    db.commit()
    return row