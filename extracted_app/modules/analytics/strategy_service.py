import json
from sqlalchemy.orm import Session

from modules.analytics.strategy_models import DiscoveredStrategy


def save_discovered_strategies(db: Session, tenant_id: str, df):

    if df is None or df.empty:
        return 0

    inserted = 0

    for _, row in df.iterrows():

        strat = DiscoveredStrategy(
            tenant_id=tenant_id,
            name=row.get("Strategy"),
            factors=row.get("Factors"),
            holdings=row.get("Holdings"),
            return_pct=row.get("Return"),
            spy_return=row.get("SPY Return"),
            alpha=row.get("Alpha"),
            sharpe=row.get("Sharpe"),
            max_drawdown=row.get("Max Drawdown"),
        )

        db.add(strat)
        inserted += 1

    db.commit()

    return inserted


def list_discovered_strategies(db: Session, tenant_id: str):

    return (
        db.query(DiscoveredStrategy)
        .filter(DiscoveredStrategy.tenant_id == tenant_id)
        .order_by(DiscoveredStrategy.sharpe.desc())
        .all()
    )