"""
modules/market/dashboard.py

Market Overview — Top Movers from user-selected Universe.

Sources:
  1. User's saved Universes
  2. price_history table using the latest two bars
  3. optional live quote fallback
  4. macro dashboard loads only on demand
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from modules.market.macro_dashboard import render_macro_dashboard


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _list_universes(db, tenant_id: str) -> list[dict]:
    try:
        rows = db.execute(
            text("""
                SELECT id, name
                FROM universes
                WHERE tenant_id = :tid
                ORDER BY created_at DESC
            """),
            {"tid": tenant_id},
        ).fetchall()

        return [{"id": str(r[0]), "name": str(r[1])} for r in rows]

    except Exception as e:
        _safe_rollback(db)
        st.warning(f"Unable to load universes: {e}")
        return []


def _list_symbols(db, tenant_id: str, universe_id: str) -> list[str]:
    try:
        rows = db.execute(
            text("""
                SELECT DISTINCT symbol
                FROM universe_symbols
                WHERE tenant_id = :tid
                  AND universe_id = :uid
                  AND symbol IS NOT NULL
                ORDER BY symbol
            """),
            {"tid": tenant_id, "uid": universe_id},
        ).fetchall()

        if rows:
            return [str(r[0]).upper().strip() for r in rows if r[0]]

        rows2 = db.execute(
            text("""
                SELECT DISTINCT symbol
                FROM universe_equities
                WHERE tenant_id = :tid
                  AND symbol IS NOT NULL
                ORDER BY symbol
            """),
            {"tid": tenant_id},
        ).fetchall()

        return [str(r[0]).upper().strip() for r in rows2 if r[0]]

    except Exception as e:
        _safe_rollback(db)
        st.warning(f"Unable to load universe symbols: {e}")
        return []


def _get_movers_from_price_history(db, symbols: list[str]) -> pd.DataFrame:
    clean_symbols = sorted({
        str(sym).upper().strip()
        for sym in (symbols or [])
        if str(sym).strip()
    })

    if not clean_symbols:
        return pd.DataFrame()

    try:
        query = text("""
            WITH ranked AS (
                SELECT
                    symbol,
                    close,
                    volume,
                    date,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol
                        ORDER BY date DESC
                    ) AS rn
                FROM price_history
                WHERE close IS NOT NULL
                  AND symbol IN :symbols
            )
            SELECT
                c.symbol,
                c.close  AS current_price,
                p.close  AS prev_price,
                c.volume AS volume,
                c.date   AS as_of
            FROM ranked c
            JOIN ranked p
              ON c.symbol = p.symbol
            WHERE c.rn = 1
              AND p.rn = 2
        """).bindparams(bindparam("symbols", expanding=True))

        rows = db.execute(query, {"symbols": clean_symbols}).fetchall()

        out = []
        for r in rows:
            curr = float(r.current_price or 0)
            prev = float(r.prev_price or 0)

            if prev <= 0:
                continue

            chg_pct = (curr - prev) / prev * 100.0

            out.append({
                "Symbol": str(r.symbol).upper(),
                "Price": round(curr, 2),
                "Prev": round(prev, 2),
                "Change %": round(chg_pct, 2),
                "Volume": float(r.volume or 0),
                "As Of": str(r.as_of)[:10] if r.as_of else "",
            })

        return pd.DataFrame(out)

    except Exception as e:
        _safe_rollback(db)
        st.error(f"Market movers query failed: {e}")
        return pd.DataFrame()


def _get_movers_live(symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()

    try:
        from modules.market_data.service import get_latest_prices

        price_map = get_latest_prices(symbols[:50])
        out = []

        for sym, price in price_map.items():
            if price and float(price) > 0:
                out.append({
                    "Symbol": str(sym).upper(),
                    "Price": round(float(price), 2),
                    "Change %": None,
                    "As Of": "Live",
                })

        return pd.DataFrame(out)

    except Exception as e:
        st.warning(f"Live quote fallback unavailable: {e}")
        return pd.DataFrame()


def _render_movers_table(df: pd.DataFrame, label: str, ascending: bool, limit: int = 20) -> None:
    if df.empty or "Change %" not in df.columns:
        st.info(f"No {label} data available.")
        return

    display = (
        df.dropna(subset=["Change %"])
        .sort_values("Change %", ascending=ascending)
        .head(limit)
        .reset_index(drop=True)
    )

    if display.empty:
        st.info(f"No {label} with change data.")
        return

    def _color_change(val):
        try:
            v = float(val)
            if v > 0:
                return "color: #1D9E75; font-weight: bold"
            if v < 0:
                return "color: #E24B4A; font-weight: bold"
        except Exception:
            pass
        return ""

    cols = [c for c in ["Symbol", "Price", "Change %", "Volume", "As Of"] if c in display.columns]
    styled = display[cols].style.map(_color_change, subset=["Change %"])

    format_map = {}
    if "Change %" in cols:
        format_map["Change %"] = "{:+.2f}%"
    if "Price" in cols:
        format_map["Price"] = "${:,.2f}"
    if "Volume" in cols:
        format_map["Volume"] = "{:,.0f}"

    if format_map:
        styled = styled.format(format_map)

    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_market_dashboard(db):
    try:
        user = st.session_state.get("user") or {}
        tenant_id = user.get("tenant_id", "default_tenant")
    except Exception:
        tenant_id = "default_tenant"

    st.header("📊 Market Overview")

    universes = _list_universes(db, tenant_id)

    col_u, col_n, col_r = st.columns([3, 1, 1])

    with col_u:
        if universes:
            universe_opts = {u["id"]: u["name"] for u in universes}
            universe_ids = list(universe_opts.keys())

            last_uid = st.session_state.get("market_universe_id")
            default_idx = universe_ids.index(last_uid) if last_uid in universe_ids else 0

            selected_uid = st.selectbox(
                "Universe",
                options=universe_ids,
                format_func=lambda x: universe_opts[x],
                index=default_idx,
                key="market_universe_sel",
            )

            st.session_state["market_universe_id"] = selected_uid
            symbols = _list_symbols(db, tenant_id, selected_uid)

        else:
            st.info(
                "No universes found. Create one in the Universe page, "
                "then return here to see top movers."
            )
            selected_uid = None
            symbols = []

    with col_n:
        st.metric("Symbols", len(symbols))

    with col_r:
        st.write("")
        refresh = st.button(
            "↺ Refresh",
            key="market_refresh",
            use_container_width=True,
        )

    if not symbols:
        if universes:
            st.warning("The selected universe has no symbols. Add symbols in the Universe page.")
        return

    cache_key = f"market_movers_{selected_uid}"

    if refresh or cache_key not in st.session_state:
        with st.spinner(f"Loading prices for {len(symbols)} symbols…"):
            df = _get_movers_from_price_history(db, symbols)

            if df.empty:
                df = _get_movers_live(symbols)
                if not df.empty:
                    st.caption("⚡ Using live prices because no usable price history was found.")

            st.session_state[cache_key] = df

    df = st.session_state.get(cache_key, pd.DataFrame())

    if df.empty:
        st.warning("No price data found for this universe. Run Market Data refresh first.")
        return

    has_change = df["Change %"].notna().sum() if "Change %" in df.columns else 0
    as_of = df["As Of"].dropna().iloc[0] if "As Of" in df.columns and not df["As Of"].dropna().empty else ""

    st.caption(
        f"{len(df)} of {len(symbols)} symbols have price data · "
        f"{has_change} with daily change · As of: {as_of}"
    )

    col_g, col_l = st.columns(2)

    with col_g:
        st.markdown("### 📈 Top Gainers")
        _render_movers_table(df, "Gainers", ascending=False)

    with col_l:
        st.markdown("### 📉 Top Losers")
        _render_movers_table(df, "Losers", ascending=True)

    with st.expander(f"📋 All {len(df)} symbols", expanded=False):
        sort_options = [c for c in ["Change %", "Symbol", "Price", "Volume"] if c in df.columns]
        sort_col = st.selectbox("Sort by", sort_options, key="market_sort")
        ascending = st.checkbox("Ascending", value=False, key="market_asc")

        show_df = df.copy()
        if sort_col in show_df.columns:
            show_df = show_df.sort_values(sort_col, ascending=ascending)

        def _color_all(val):
            try:
                v = float(val)
                return "color: #1D9E75" if v > 0 else "color: #E24B4A" if v < 0 else ""
            except Exception:
                return ""

        cols = [c for c in ["Symbol", "Price", "Change %", "Volume", "As Of"] if c in show_df.columns]
        styled = show_df[cols].style

        format_map = {}
        if "Change %" in cols:
            styled = styled.map(_color_all, subset=["Change %"])
            format_map["Change %"] = "{:+.2f}%"
        if "Price" in cols:
            format_map["Price"] = "${:,.2f}"
        if "Volume" in cols:
            format_map["Volume"] = "{:,.0f}"

        if format_map:
            styled = styled.format(format_map)

        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    try:
        render_macro_dashboard(db)
    except Exception as e:
        st.warning(f"Macro dashboard unavailable: {e}")
