"""
modules/market/dashboard.py

Market Overview — Top Movers from user-selected Universe.

Sources (in priority order):
  1. User's saved Universes (universe_symbols table)
  2. price_history table (latest two bars → % change)
  3. get_latest_prices() for live quote fallback
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from sqlalchemy import text

from modules.market.macro_dashboard import render_macro_dashboard


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _list_universes(db, tenant_id: str) -> list[dict]:
    """Return all universes for this tenant."""
    try:
        rows = db.execute(text("""
            SELECT id, name
            FROM universes
            WHERE tenant_id = :tid
            ORDER BY created_at DESC
        """), {"tid": tenant_id}).fetchall()
        return [{"id": str(r[0]), "name": str(r[1])} for r in rows]
    except Exception:
        return []


def _list_symbols(db, tenant_id: str, universe_id: str) -> list[str]:
    """Return symbols in a universe."""
    try:
        rows = db.execute(text("""
            SELECT DISTINCT symbol
            FROM universe_symbols
            WHERE tenant_id = :tid AND universe_id = :uid
            ORDER BY symbol
        """), {"tid": tenant_id, "uid": universe_id}).fetchall()
        if rows:
            return [str(r[0]).upper() for r in rows]
        # Fallback: universe_equities table
        rows2 = db.execute(text("""
            SELECT DISTINCT symbol
            FROM universe_equities
            WHERE tenant_id = :tid
            ORDER BY symbol
        """), {"tid": tenant_id}).fetchall()
        return [str(r[0]).upper() for r in rows2]
    except Exception:
        return []


def _get_movers_from_price_history(db, symbols: list[str]) -> pd.DataFrame:
    """
    Compute % change for each symbol using the two most recent bars
    in price_history. Fast — single DB query, no external API calls.
    """
    if not symbols:
        return pd.DataFrame()

    # Build placeholders for IN clause
    placeholders = ",".join(f":s{i}" for i in range(len(symbols)))
    params = {"s" + str(i): sym for i, sym in enumerate(symbols)}

    try:
        rows = db.execute(text(f"""
            WITH ranked AS (
                SELECT
                    symbol,
                    close,
                    date,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol ORDER BY date DESC
                    ) AS rn
                FROM price_history
                WHERE symbol IN ({placeholders})
            )
            SELECT
                c.symbol,
                c.close  AS current_price,
                p.close  AS prev_price,
                c.date   AS as_of
            FROM ranked c
            JOIN ranked p
              ON c.symbol = p.symbol AND c.rn = 1 AND p.rn = 2
        """), params).fetchall()

        if not rows:
            return pd.DataFrame()

        out = []
        for r in rows:
            curr = float(r[1] or 0)
            prev = float(r[2] or 0)
            if prev <= 0:
                continue
            chg_pct = (curr - prev) / prev * 100
            out.append({
                "Symbol":    r[0],
                "Price":     round(curr, 2),
                "Prev":      round(prev, 2),
                "Change %":  round(chg_pct, 2),
                "As Of":     str(r[3])[:10] if r[3] else "",
            })
        return pd.DataFrame(out)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return pd.DataFrame()


def _get_movers_live(symbols: list[str]) -> pd.DataFrame:
    """
    Live quote fallback using get_latest_prices().
    Computes day change % via (price - prev_close) / prev_close.
    """
    if not symbols:
        return pd.DataFrame()
    try:
        from modules.market_data.service import get_latest_prices
        price_map = get_latest_prices(symbols[:50])  # cap at 50 for speed
        out = []
        for sym, price in price_map.items():
            if price and price > 0:
                out.append({
                    "Symbol":   sym,
                    "Price":    round(float(price), 2),
                    "Change %": None,  # live price only, no prev close
                    "As Of":    "Live",
                })
        return pd.DataFrame(out)
    except Exception:
        return pd.DataFrame()


def _render_movers_table(df: pd.DataFrame, label: str, ascending: bool):
    """Render a styled top/bottom movers table."""
    if df.empty or "Change %" not in df.columns:
        st.info(f"No {label} data available.")
        return

    display = (
        df.dropna(subset=["Change %"])
        .sort_values("Change %", ascending=ascending)
        .head(20)
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
            elif v < 0:
                return "color: #E24B4A; font-weight: bold"
        except Exception:
            pass
        return ""

    cols = [c for c in ["Symbol", "Price", "Change %", "As Of"] if c in display.columns]
    styled = display[cols].style.applymap(_color_change, subset=["Change %"])
    if "Change %" in display.columns:
        styled = styled.format({"Change %": "{:+.2f}%", "Price": "${:,.2f}"})

    st.dataframe(styled, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────

def render_market_dashboard(db):
    tenant_id = None
    try:
        from streamlit import session_state as _ss
        user = _ss.get("user") or {}
        tenant_id = user.get("tenant_id", "default_tenant")
    except Exception:
        tenant_id = "default_tenant"

    st.header("📊 Market Overview")

    # ── Universe selector ─────────────────────────────────────
    universes = _list_universes(db, tenant_id)

    col_u, col_n, col_r = st.columns([3, 1, 1])

    with col_u:
        if universes:
            universe_opts = {u["id"]: u["name"] for u in universes}
            # Remember last selection
            last_uid = st.session_state.get("market_universe_id")
            default_idx = 0
            if last_uid and last_uid in universe_opts:
                default_idx = list(universe_opts.keys()).index(last_uid)

            selected_uid = st.selectbox(
                "Universe",
                options=list(universe_opts.keys()),
                format_func=lambda x: universe_opts[x],
                index=default_idx,
                key="market_universe_sel",
            )
            st.session_state["market_universe_id"] = selected_uid
            symbols = _list_symbols(db, tenant_id, selected_uid)
        else:
            st.info(
                "No universes found. Create one in the **Universe** page, "
                "then return here to see top movers from your stocks."
            )
            selected_uid = None
            symbols = []

    with col_n:
        st.metric("Symbols", len(symbols))

    with col_r:
        st.write("")
        refresh = st.button("↺ Refresh", key="market_refresh",
                            use_container_width=True)

    if not symbols:
        if universes:
            st.warning("The selected universe has no symbols. Add symbols in the Universe page.")
        return

    # ── Load price data ────────────────────────────────────────
    cache_key = f"market_movers_{selected_uid}"
    if refresh or cache_key not in st.session_state:
        with st.spinner(f"Loading prices for {len(symbols)} symbols…"):
            df = _get_movers_from_price_history(db, symbols)
            if df.empty:
                # Fallback to live prices
                df = _get_movers_live(symbols)
                if not df.empty:
                    st.caption("⚡ Using live prices (no price history in DB for this universe)")
            st.session_state[cache_key] = df

    df = st.session_state.get(cache_key, pd.DataFrame())

    if df.empty:
        st.warning(
            "No price data found for this universe. "
            "Run **Market Data** to fetch prices for your symbols, "
            "or the app will use live quotes on next refresh."
        )
        return

    # ── Coverage info ─────────────────────────────────────────
    has_change = df["Change %"].notna().sum() if "Change %" in df.columns else 0
    as_of = df["As Of"].iloc[0] if "As Of" in df.columns and not df.empty else ""
    st.caption(
        f"{len(df)} of {len(symbols)} symbols have price data · "
        f"{has_change} with daily change · As of: {as_of}"
    )

    # ── Top Movers ────────────────────────────────────────────
    col_g, col_l = st.columns(2)
    with col_g:
        st.markdown("### 📈 Top Gainers")
        _render_movers_table(df, "Gainers", ascending=False)
    with col_l:
        st.markdown("### 📉 Top Losers")
        _render_movers_table(df, "Losers", ascending=True)

    # ── All symbols (scrollable) ───────────────────────────────
    with st.expander(f"📋 All {len(df)} symbols", expanded=False):
        sort_col = st.selectbox(
            "Sort by",
            ["Change %", "Symbol", "Price"],
            key="market_sort",
        )
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

        cols = [c for c in ["Symbol", "Price", "Change %", "As Of"] if c in show_df.columns]
        styled = show_df[cols].style
        if "Change %" in show_df.columns:
            styled = styled.applymap(_color_all, subset=["Change %"])
            styled = styled.format({"Change %": "{:+.2f}%", "Price": "${:,.2f}"})
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Macro Dashboard ───────────────────────────────────────
    st.divider()
    try:
        render_macro_dashboard(db)
    except Exception as e:
        st.warning(f"Macro dashboard unavailable: {e}")