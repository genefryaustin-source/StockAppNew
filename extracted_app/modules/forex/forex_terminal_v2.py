"""
modules/forex/forex_terminal_v2.py

Forex Terminal v2 -- Skeleton Rebuild

The existing Forex Institutional Terminal (forex_master_workspace.py ->
forex_system_manager.py -> forex_workspace.py -> forex_terminal_dashboard.py
-> ...) accumulated a lot of complexity across many sprints: several
layers of delegation, a byte-for-byte duplicate normalization block,
unthrottled live refreshes, and 60+ related files (most orphaned).
Real, severe bottlenecks were found and fixed there, but each fix
required real production timing data to isolate from a lot of
incidental complexity.

This is a deliberate restart: a genuinely minimal skeleton, added back
to piece by piece, with two rules carried over from everything learned
fixing the old one:

    1. Every section that could plausibly do real work (DB query, live
       fetch) gets its own named timing block from the moment it's
       added -- not retrofitted after something turns out slow.

    2. Nothing fetches live data more than once per render, and
       anything that touches an external provider is throttled by
       default, not "throttled after someone notices it's slow."

Currently implemented: skeleton layout only (header, KPI row with real
but cheap DB-backed numbers, workspace tab selector). No live quote
fetches, no macro regime, no central bank data yet -- those get added
back one at a time, each verified fast on its own before the next one
goes in.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

try:
    import streamlit as st
except Exception:
    st = None


def _timed_section(label: str, fn, *args, **kwargs):
    """
    Runs fn(*args, **kwargs), prints how long it took labeled by
    `label`, and returns its result. Every section in this rebuild
    goes through this from the start, rather than waiting for a
    reported slowdown to add instrumentation after the fact.
    """
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(f"FOREX_V2 TIMING | {label}: {elapsed_ms:.2f} ms")
        return result
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(f"FOREX_V2 TIMING | {label}: FAILED after {elapsed_ms:.2f} ms | {exc}")
        raise


def _get_position_counts(db, *, tenant_id: str | None, portfolio_id: str | None) -> dict:
    """
    Real, DB-only position count -- no live quotes, no external
    provider calls. This is section 1 of the rebuild: something
    genuinely fast by construction, not fast because nothing has gone
    wrong with it yet.

    Equity/cash are intentionally left unwired for now (reported as
    None, rendered as "--") rather than guessing at another method on
    ForexPortfolioManager and risking the exact kind of silent-wrong-
    value bug load_positions()'s own docstring already documents
    happening once in this codebase (avg_price/unrealized_pnl/
    market_value silently computing as 0.0 from an assumed column name
    that didn't actually exist). Those get wired in as their own,
    separately-verified step.
    """
    if db is None:
        return {"open_positions": 0, "equity": None, "cash": None}

    try:
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

        manager = get_forex_portfolio_manager(db=db, tenant_id=tenant_id, portfolio_id=portfolio_id)

        resolved_portfolio_id = portfolio_id
        if resolved_portfolio_id is None:
            active = manager.active_portfolio()
            resolved_portfolio_id = active.get("id") if active else None

        positions = manager.load_positions(portfolio_id=resolved_portfolio_id, tenant_id=tenant_id)

        return {
            "open_positions": len(positions) if positions else 0,
            "equity": None,
            "cash": None,
        }

    except Exception:
        # Deliberately fails soft here -- the skeleton's job is to
        # prove the LAYOUT is fast; a real data-access bug in an
        # early, still-being-wired-up helper shouldn't block that.
        return {"open_positions": 0, "equity": None, "cash": None}


WORKSPACE_TABS = [
    "Overview",
    "Positions",
    "Quotes",
]

QUOTE_THROTTLE_SECONDS = 15.0
DEFAULT_QUOTE_PAIR = "EUR/USD"


def _get_throttled_quote(pair: str, *, force: bool = False) -> dict:
    """
    Real live quote for one pair, throttled to at most one real fetch
    per QUOTE_THROTTLE_SECONDS -- built in from the start here, not
    retrofitted after a reported slowdown like it was on the old
    terminal. Reuses the same real, provider-fallback-chained
    ForexPriceService the old terminal already used (polygon_fx ->
    frankfurter -> ecb -> yahoo_fx); that fetch mechanism itself was
    never the bug anywhere in the old code, only how often it got
    called with no throttle at all.

    Caches the result (and the timestamp of the last REAL fetch) in
    st.session_state, keyed by pair -- so adding more pairs later
    won't have them share one stale cache slot. force=True (from an
    explicit "Refresh now" button) bypasses the throttle for exactly
    one call, then resets the clock.
    """
    if st is None:
        return {"pair": pair, "error": "streamlit_not_available"}

    cache_key = f"fx_v2_quote_cache:{pair}"
    ts_key = f"fx_v2_quote_last_fetch_ts:{pair}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached_quote = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached_quote is not None and age_seconds < QUOTE_THROTTLE_SECONDS:
        return {**cached_quote, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_price_service import get_forex_price_service

        quote = get_forex_price_service().get_quote(pair)
    except Exception as exc:
        quote = {"pair": pair, "error": str(exc)}

    st.session_state[cache_key] = quote
    st.session_state[ts_key] = now_ts

    return {**quote, "_cache_age_seconds": 0.0, "_from_cache": False}


def render_forex_terminal_v2(db=None, user=None, **kwargs):
    if st is None:
        return {"status": "streamlit_not_available"}

    render_start = time.perf_counter()

    tenant_id = (user or {}).get("tenant_id") if isinstance(user, dict) else None
    portfolio_id = (user or {}).get("portfolio_id") if isinstance(user, dict) else None

    st.markdown("### 🌍 Forex Terminal v2 *(rebuild in progress)*")
    st.caption(
        "Minimal skeleton -- live quotes, macro regime, and central bank data "
        "are being added back one at a time, each verified fast before the next."
    )

    counts = _timed_section(
        "position_counts",
        _get_position_counts,
        db, tenant_id=tenant_id, portfolio_id=portfolio_id,
    )

    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        st.metric("Open Positions", counts["open_positions"])

    with kpi_cols[1]:
        equity = counts["equity"]
        st.metric("Equity", f"${equity:,.2f}" if equity is not None else "—")

    with kpi_cols[2]:
        cash = counts["cash"]
        st.metric("Cash", f"${cash:,.2f}" if cash is not None else "—")

    with kpi_cols[3]:
        now = datetime.now(timezone.utc)
        st.metric("Server Time (UTC)", now.strftime("%H:%M:%S"))

    st.divider()

    workspace = st.radio("Workspace", WORKSPACE_TABS, horizontal=True, key="fx_v2_workspace")

    if workspace == "Overview":
        st.info(
            "Overview tab -- placeholder. Real content (market regime, "
            "currency strength) gets added back here next, once this "
            "skeleton is confirmed fast."
        )
    elif workspace == "Positions":
        st.info(
            "Positions tab -- placeholder. Real position list (from the "
            "same DB-backed helper the KPI row above already uses) gets "
            "added back here next."
        )
    elif workspace == "Quotes":
        st.caption(
            f"Live quote for {DEFAULT_QUOTE_PAIR}, throttled to at most one real fetch "
            f"every {QUOTE_THROTTLE_SECONDS:.0f} seconds -- switching tabs or clicking "
            f"elsewhere reuses the cached quote instead of refetching."
        )

        force_refresh = st.button("🔄 Refresh now", key="fx_v2_force_refresh_quote")

        quote = _timed_section(
            "quote_eurusd",
            _get_throttled_quote,
            DEFAULT_QUOTE_PAIR, force=force_refresh,
        )

        if quote.get("error"):
            st.error(f"Could not get a quote for {DEFAULT_QUOTE_PAIR}: {quote['error']}")
        else:
            quote_cols = st.columns(4)

            with quote_cols[0]:
                mid = quote.get("mid") or quote.get("last")
                st.metric(DEFAULT_QUOTE_PAIR, f"{mid:.5f}" if mid is not None else "—")

            with quote_cols[1]:
                st.metric("Provider", quote.get("provider") or quote.get("source") or "—")

            with quote_cols[2]:
                if quote.get("_from_cache"):
                    st.metric("Cache Age", f"{quote['_cache_age_seconds']:.0f}s")
                else:
                    st.metric("Cache Age", "just fetched")

            with quote_cols[3]:
                next_refresh_in = max(0.0, QUOTE_THROTTLE_SECONDS - quote.get("_cache_age_seconds", 0.0))
                st.metric("Next Auto-Refresh", f"{next_refresh_in:.0f}s")

    total_elapsed_ms = (time.perf_counter() - render_start) * 1000.0
    print(f"FOREX_V2 TIMING | TOTAL_RENDER: {total_elapsed_ms:.2f} ms")

    return {"status": "ok", "workspace": workspace, "elapsed_ms": round(total_elapsed_ms, 2)}