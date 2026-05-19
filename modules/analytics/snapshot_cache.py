from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text


@st.cache_data(ttl=120)
def get_latest_snapshots_df(_db, tenant_id: str) -> pd.DataFrame:
    """
    Fast cached dataframe of the latest analytics snapshot per symbol.
    Uses SQL to return only one row per symbol.
    """
    sql = text(
        """
        SELECT a.*
        FROM analytics_snapshots a
        INNER JOIN (
            SELECT symbol, MAX(asof) AS max_asof
            FROM analytics_snapshots
            WHERE tenant_id = :tenant_id
            GROUP BY symbol
        ) latest
            ON a.symbol = latest.symbol
           AND a.asof = latest.max_asof
        WHERE a.tenant_id = :tenant_id
        """
    )

    rows = _db.execute(sql, {"tenant_id": tenant_id}).mappings().all()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def clear_latest_snapshots_cache():
    get_latest_snapshots_df.clear()