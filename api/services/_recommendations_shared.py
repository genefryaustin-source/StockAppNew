"""
api/services/_recommendations_shared.py

Shared helpers for the Portfolio Recommendations API adapters
(lifecycle, performance, targets, stops, alerts, command-center).

Re-exports _safe_rollback from _portfolio_symbol_returns rather than
duplicating it -- same Postgres failed-transaction risk applies here:
these services' sessions are cached and reused by the module registry
for the life of the process, so a caught exception that doesn't roll
back poisons every future request to that endpoint, not just this one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from api.services._portfolio_symbol_returns import _safe_rollback  # noqa: F401


def df_to_records(df: pd.DataFrame | None) -> list[dict]:
    """
    Convert an engine's DataFrame output into JSON-safe records: NaN/inf
    become None, datetime columns become ISO strings. Returns [] for
    None or an empty frame rather than raising.
    """

    if df is None or df.empty:
        return []

    clean = df.copy()

    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            clean[col] = clean[col].astype(str)

    clean = clean.replace([np.inf, -np.inf], np.nan).where(pd.notnull(clean), None)

    return clean.to_dict(orient="records")