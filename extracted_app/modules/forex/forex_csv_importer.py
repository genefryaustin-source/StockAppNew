"""
modules/forex/forex_csv_importer.py

Shared Forex CSV importer for testing, backfills, and proprietary datasets.
Production refresh should use forex_history_service.py, but this importer can seed
forex_price_history using the same repository.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from modules.forex.forex_history_repository import ForexHistoryRepository, normalize_pair


REQUIRED_COLUMNS = ["symbol", "asof", "close"]
OPTIONAL_COLUMNS = ["open", "high", "low", "volume", "vwap", "provider", "source"]


def import_price_history(
    uploaded_file: Any,
    *,
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    interval: str = "1day",
    provider: str = "csv_import",
    persist: bool = False,
) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    df.columns = [str(c).lower().strip() for c in df.columns]
    if "pair" in df.columns and "symbol" not in df.columns:
        df["symbol"] = df["pair"]
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Required columns are {REQUIRED_COLUMNS}.")

    repo = ForexHistoryRepository(
        db=db,
        tenant_id=tenant_id or "default",
        user_id=user_id,
        portfolio_id=portfolio_id,
    )
    clean = repo.normalize_history_frame(df, provider=provider, interval=interval)

    if persist and db is not None and not clean.empty:
        repo.upsert_history(clean, provider=provider, interval=interval)

    return clean


__all__ = ["import_price_history", "normalize_pair", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"]
