from __future__ import annotations

from typing import Iterable

import pandas as pd
from sqlalchemy import func

from modules.market_data.models import PriceHistory
from modules.utils.symbol_utils import normalize_symbol, is_valid_symbol


# ---------------------------------------------------
# Period helpers
# ---------------------------------------------------

def _period_days(period: str) -> int:
    p = (period or "1y").lower().strip()

    mapping = {
        "5d": 5,
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "5y": 1825,
        "10y": 3650,
        "ytd": 370,
    }

    return mapping.get(p, 365)


# ---------------------------------------------------
# Bulk close matrix from DB
# ---------------------------------------------------

def load_close_matrix_from_db(
    db,
    symbols: Iterable[str],
    period: str = "1y",
) -> pd.DataFrame:
    syms = []
    seen = set()

    for s in symbols:
        sym = normalize_symbol(str(s))
        if is_valid_symbol(sym) and sym not in seen:
            syms.append(sym)
            seen.add(sym)

    if not syms:
        return pd.DataFrame()

    latest_date = db.query(func.max(PriceHistory.date)).scalar()
    if latest_date is None:
        return pd.DataFrame()

    cutoff = pd.Timestamp(latest_date) - pd.Timedelta(days=_period_days(period))

    rows = (
        db.query(
            PriceHistory.symbol,
            PriceHistory.date,
            PriceHistory.close,
        )
        .filter(PriceHistory.symbol.in_(syms))
        .filter(PriceHistory.date >= cutoff)
        .order_by(PriceHistory.date.asc())
        .all()
    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [(r.symbol, r.date, r.close) for r in rows],
        columns=["symbol", "date", "close"],
    )

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot(index="date", columns="symbol", values="close").sort_index()

    return pivot


# ---------------------------------------------------
# Coverage helpers
# ---------------------------------------------------

def get_symbols_with_min_history(
    db,
    symbols: Iterable[str],
    min_rows: int = 20,
    period: str = "1y",
) -> set[str]:
    matrix = load_close_matrix_from_db(db, symbols, period=period)

    if matrix.empty:
        return set()

    good = set()

    for col in matrix.columns:
        if matrix[col].dropna().shape[0] >= min_rows:
            good.add(str(col))

    return good