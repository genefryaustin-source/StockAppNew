# modules/smart_money/smart_money_ui.py

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.smart_money.smart_money_service import (
    ensure_smart_money_tables,
    refresh_symbol_smart_money,
    refresh_smart_money_universe,
)


def _safe_rollback(db):
    try:
        db.rollback()
    except Exception:
        pass


def _read_sql(db, sql: str, params: dict | None = None) -> pd.DataFrame:
    try:
        return pd.DataFrame(db.execute(text(sql), params or {}).mappings().all())
    except Exception as exc:
        _safe_rollback(db)
        st.warning(f"Smart Money query failed: {exc}")
        return pd.DataFrame()


def _metric(label, value):
    st.metric(label, value if value not in (None, "") else "0")


def render_smart_money_admin(db, user):
    """
    Admin/operations panel for refreshing Smart Money data.
    Add this wherever your admin or Smart Money workspace renders operations.
    """
    st.subheader("Smart Money Data Refresh")
    st.caption("Populates insider_transactions, institutional_holdings, sec_form4_filings, and smart_money_signals.")

    try:
        ensure_smart_money_tables(db)
    except Exception as exc:
        st.error(f"Could not initialize Smart Money tables: {exc}")
        return

    tab_symbol, tab_universe, tab_data = st.tabs(
        ["Single Symbol", "Universe Refresh", "Data Preview"]
    )

    with tab_symbol:
        symbol = st.text_input("Symbol", value="NVDA", key="sm_refresh_symbol").upper().strip()
        c1, c2 = st.columns(2)
        fetch_sec = c1.checkbox("Fetch SEC Form 4", value=True, key="sm_fetch_sec_one")
        fetch_finnhub = c2.checkbox("Fetch Finnhub Insider/Institutional", value=True, key="sm_fetch_finnhub_one")

        if st.button("Refresh Symbol Smart Money", type="primary", key="sm_refresh_one"):
            if not symbol:
                st.warning("Enter a symbol.")
            else:
                with st.spinner(f"Refreshing Smart Money data for {symbol}..."):
                    result = refresh_symbol_smart_money(
                        db,
                        symbol,
                        fetch_sec=fetch_sec,
                        fetch_finnhub=fetch_finnhub,
                    )
                st.success("Smart Money refresh complete.")
                st.json(result)

    with tab_universe:
        tenant_id = (user or {}).get("tenant_id")
        universe_id = st.text_input("Universe ID optional", value="", key="sm_universe_id").strip() or None
        limit = st.number_input("Limit symbols", min_value=1, max_value=5000, value=50, step=10, key="sm_limit")
        c1, c2 = st.columns(2)
        fetch_sec_u = c1.checkbox("Fetch SEC Form 4", value=True, key="sm_fetch_sec_uni")
        fetch_finnhub_u = c2.checkbox("Fetch Finnhub Insider/Institutional", value=True, key="sm_fetch_finnhub_uni")

        if st.button("Refresh Universe Smart Money", type="primary", key="sm_refresh_universe"):
            progress_bar = st.progress(0)
            status = st.empty()

            def progress(done, total, sym):
                pct = int((done / max(total, 1)) * 100)
                progress_bar.progress(min(100, pct))
                status.write(f"{done}/{total}: {sym}")

            with st.spinner("Refreshing Smart Money universe..."):
                result = refresh_smart_money_universe(
                    db,
                    tenant_id=tenant_id,
                    universe_id=universe_id,
                    limit=int(limit),
                    fetch_sec=fetch_sec_u,
                    fetch_finnhub=fetch_finnhub_u,
                    progress=progress,
                )

            st.success("Universe Smart Money refresh complete.")
            st.json(result)

    with tab_data:
        c1, c2, c3, c4 = st.columns(4)

        counts = {}
        for table in [
            "insider_transactions",
            "institutional_holdings",
            "sec_form4_filings",
            "smart_money_signals",
        ]:
            try:
                counts[table] = int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
            except Exception:
                _safe_rollback(db)
                counts[table] = 0

        c1.metric("Insider Tx", counts["insider_transactions"])
        c2.metric("Institutional Rows", counts["institutional_holdings"])
        c3.metric("Form 4 Filings", counts["sec_form4_filings"])
        c4.metric("Signals", counts["smart_money_signals"])

        preview_table = st.selectbox(
            "Preview table",
            [
                "smart_money_signals",
                "insider_transactions",
                "institutional_holdings",
                "sec_form4_filings",
            ],
            key="sm_preview_table",
        )

        df = _read_sql(
            db,
            f"""
            SELECT
                symbol,
                smart_money_score,
                accumulation_score,
                distribution_score,
                insider_score,
                institutional_score,
                options_score,
                created_at
            FROM smart_money_signals
            ORDER BY smart_money_score DESC
            LIMIT 100
            """,
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
