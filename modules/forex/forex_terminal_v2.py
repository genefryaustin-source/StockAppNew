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

try:
    import plotly.graph_objects as go
except Exception:
    go = None


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


PORTFOLIO_RESOLUTION_THROTTLE_SECONDS = 15.0


def _resolve_portfolio_id(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
) -> str | None:
    """
    Resolves a real portfolio_id to use across the whole render.

    Found via a real production screenshot: _get_position_counts
    already had its own internal fallback to manager.active_portfolio()
    when portfolio_id was None -- explaining why the KPI row's Open
    Positions tile correctly showed real data even when the app's own
    `user` object apparently doesn't carry an explicit portfolio_id.
    Every OTHER helper (Positions, Orders, Risk, Performance) lacked
    this same fallback, so they silently returned empty results with a
    misleading "no data"/"No portfolio selected" message instead of
    resolving the same way the KPI row already did.

    ROOT CAUSE, found via direct SQL inspection of the real table (not
    guessed): this never passed user_id to get_forex_portfolio_manager
    at all, silently defaulting to the literal string "default" --
    which matches NEITHER of the two real portfolios actually in the
    table (one owned by the real user's UUID, one by the literal
    string "development"). Now uses the real user_id, so this
    correctly defaults to that specific user's own portfolio rather
    than failing to match anything.

    Centralized here, resolved once at the top of render_forex_terminal_v2
    and passed through to every tab, rather than each helper
    duplicating (or forgetting to duplicate) its own fallback logic.
    Throttled the same way as everything else, since active_portfolio()
    is itself a DB call and the active portfolio rarely changes render
    to render.
    """
    if portfolio_id is not None:
        return portfolio_id

    if db is None:
        return None

    cache_key = f"fx_v2_resolved_portfolio_id:{tenant_id}:{user_id}"
    ts_key = f"fx_v2_resolved_portfolio_id_ts:{tenant_id}:{user_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and cached is not None and age_seconds < PORTFOLIO_RESOLUTION_THROTTLE_SECONDS:
        return cached

    try:
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

        manager = get_forex_portfolio_manager(db=db, tenant_id=tenant_id, user_id=user_id)
        active = manager.active_portfolio()
        resolved = active.get("id") if active else None
    except Exception:
        resolved = None

    if st is not None:
        st.session_state[cache_key] = resolved
        st.session_state[ts_key] = now_ts

    return resolved


PORTFOLIO_LIST_THROTTLE_SECONDS = 15.0


def _get_throttled_portfolio_list(db, *, tenant_id: str | None, force: bool = False) -> list[dict]:
    """
    Real list of ALL portfolios for this tenant, for the portfolio
    selector -- deliberately NOT scoped to one specific user_id.

    Direct SQL inspection of the real table found two real portfolios
    under the same tenant, owned by two DIFFERENT user_id values (one
    the real user's UUID, one the literal string "development"). If a
    user needs to work across multiple portfolios (the reason this
    selector exists at all), it needs to show every portfolio
    available to the tenant, not just ones matching one particular
    user_id -- so this queries the table directly rather than going
    through list_portfolios(), which requires a single user_id and
    would silently hide portfolios owned by anyone else.
    _resolve_portfolio_id's default/auto-resolved selection still
    correctly uses the specific signed-in user's own portfolio; this
    is only about what's available to explicitly switch to.

    Throttled the same way as everything else -- position_counts
    already taught us that a call which "looks" simple and DB-only
    still benefits from throttling under real production network
    latency, rather than assuming this one is cheap enough to skip it.
    """
    if db is None:
        return []

    cache_key = f"fx_v2_portfolio_list_cache:{tenant_id}"
    ts_key = f"fx_v2_portfolio_list_last_fetch_ts:{tenant_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < PORTFOLIO_LIST_THROTTLE_SECONDS:
        return cached

    try:
        from sqlalchemy import text as _text

        rows = db.execute(
            _text(
                "SELECT id, name, tenant_id, user_id, status, is_default, created_at "
                "FROM forex_portfolios WHERE tenant_id = :tenant "
                "ORDER BY is_default DESC, created_at"
            ),
            {"tenant": tenant_id},
        ).fetchall()
        result = [dict(row._mapping) for row in rows]
    except Exception:
        result = []

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return result


def _get_position_counts(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
) -> dict:
    """
    Real, DB-only position count -- no live quotes, no external
    provider calls. This is section 1 of the rebuild: something
    genuinely fast by construction, not fast because nothing has gone
    wrong with it yet.

    Equity/cash come from ForexPortfolioEngine.get_account() -- verified
    directly (not guessed) to be a pure DB read: no ensure_tables()
    call inside it, no live mark-to-market. The values returned are
    the last PERSISTED cash_balance/equity/unrealized_pnl, not live
    real-time marks -- consistent with "still DB-only, no live
    quotes." Also verified fast across repeated calls with fresh
    session objects each time, even though this specific factory
    (unlike the two already fixed) doesn't cache its engine instance
    at all -- confirmed its __init__ genuinely is cheap (flag-setting
    and already-cached sub-service lookups, no DDL), so the missing
    cache here isn't the same bug.

    Returns equity/cash as None (rendered as "--") if no account
    exists yet for this portfolio -- "portfolio" and "account" are
    separate concepts in this data model; an account isn't created
    automatically just by creating a portfolio.
    """
    if db is None:
        return {"open_positions": 0, "equity": None, "cash": None, "unrealized_pnl": None}

    try:
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        manager = get_forex_portfolio_manager(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        positions = manager.load_positions(portfolio_id=portfolio_id, tenant_id=tenant_id)

        equity = None
        cash = None
        unrealized_pnl = None

        if portfolio_id is not None:
            portfolio_engine = get_forex_portfolio_engine(
                db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
            )
            account = portfolio_engine.get_account(portfolio_id=portfolio_id)

            if account is not None:
                equity = account.equity
                cash = account.cash_balance
                unrealized_pnl = account.unrealized_pnl

        return {
            "open_positions": len(positions) if positions else 0,
            "equity": equity,
            "cash": cash,
            "unrealized_pnl": unrealized_pnl,
        }

    except Exception:
        # Deliberately fails soft here -- the skeleton's job is to
        # prove the LAYOUT is fast; a real data-access bug in an
        # early, still-being-wired-up helper shouldn't block that.
        return {"open_positions": 0, "equity": None, "cash": None, "unrealized_pnl": None}


ACCOUNT_SUMMARY_THROTTLE_SECONDS = 15.0


def _get_throttled_account_summary(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Throttled wrapper around _get_position_counts, matching the exact
    same pattern already proven for the quote fetch and currency
    strength scan. Real production logs confirmed _get_position_counts
    itself -- genuinely fixed from its original 450-600ms-EVERY-TIME
    bug (two separate caching bugs upstream, both fixed) -- still
    costs ~150-165ms per call in the real deployment. That's most
    likely two real network round trips to a remote database, not a
    caching bug this time; a session_state throttle can't make a
    single real query faster, but it CAN avoid paying that cost on
    every single Streamlit rerun for data that doesn't change that
    often. Originally set shorter than the quote/strength throttles
    (5s vs 15s), on the reasoning that a fresh trade should show up
    quickly -- but real production logs showed that window being
    "eaten" by the rest of the page: the Overview tab's own
    currency_strength fetch alone takes ~3s on a cache miss, so actual
    elapsed time between renders during normal tab-switching (that
    fetch, plus real click time) routinely exceeded 5s before the next
    render even started, making the throttle ineffective in practice.
    Matched to 15s like the other two.

    Cache key includes portfolio_id so switching portfolios doesn't
    reuse another portfolio's stale summary.
    """
    if st is None:
        return _get_position_counts(db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id)

    cache_key = f"fx_v2_account_summary_cache:{portfolio_id}"
    ts_key = f"fx_v2_account_summary_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < ACCOUNT_SUMMARY_THROTTLE_SECONDS:
        return cached

    result = _get_position_counts(db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id)

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return result


def _get_positions_for_display(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
) -> list[dict]:
    """
    Real open positions for display in the Positions tab. Reuses the
    same manager.load_positions() call already proven correct and fast
    for the KPI row above.

    list_positions()/load_positions() are TENANT-scoped, not
    portfolio-scoped (list_positions() filters by tenant_id and an
    optional account_id, but load_positions() never passes account_id)
    -- a pre-existing data-model quirk in shared code, not something
    introduced or fixed here. Client-side filtered by portfolio_id
    below instead, since each position dict does carry its own
    portfolio_id and modifying the shared, widely-used
    list_positions()/load_positions() methods themselves is out of
    scope for this skeleton.
    """
    if db is None or portfolio_id is None:
        return []

    try:
        from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager

        manager = get_forex_portfolio_manager(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        all_positions = manager.load_positions(portfolio_id=portfolio_id, tenant_id=tenant_id)

        return [p for p in all_positions if p.get("portfolio_id") == portfolio_id]

    except Exception:
        return []


def _close_position(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
    position_id: str, close_price: float | None,
) -> dict:
    """
    Closes a real open position -- a write operation. Traced the
    entire chain before wiring a button around it, not just the
    signature: close_position() itself always does one real live
    quote fetch (via the same already-fixed ForexService used
    elsewhere in this rebuild) regardless of whether close_price is
    passed in -- it's only used as a fallback if that fetch doesn't
    return something usable, but the fetch itself still happens every
    time. Confirmed the recalculate_account() call at the end is pure
    DB read/sum (get_account + list_positions, already-verified safe
    methods), not a second live fetch -- so the full chain has exactly
    one live quote fetch, not a hidden multiple.
    """
    if db is None or position_id is None:
        return {"status": "error", "message": "No position selected."}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        result = engine.close_position(position_id=position_id, close_price=close_price)

        if result is None:
            return {"status": "error", "message": "Position not found or already closed."}

        return {"status": "ok", "position": result}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _get_orders_for_display(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
) -> dict:
    """
    Real open and filled orders for the Orders tab. Unlike positions,
    load_open_orders()/load_filled_orders() take portfolio_id directly
    and are properly scoped by it at the source -- confirmed directly
    against the underlying SQL (WHERE portfolio_id = :portfolio_id) --
    so no client-side filtering workaround is needed here the way it
    was for positions.

    Pure DB read, no live quotes. Field names (pair, side, order_type,
    status, units, requested_price, avg_fill_price, filled_qty,
    created_at, filled_at) confirmed directly against the actual
    CREATE TABLE statement and the row-to-dict conversion (a plain
    dict(row._mapping), no renaming) rather than assumed.
    """
    if db is None or portfolio_id is None:
        return {"open": [], "filled": []}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        return {
            "open": engine.load_open_orders(portfolio_id=portfolio_id) or [],
            "filled": engine.load_filled_orders(portfolio_id=portfolio_id) or [],
        }

    except Exception:
        return {"open": [], "filled": []}


def _get_journal_entries(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
) -> list[dict]:
    """
    Real trade journal entries for the Journal tab (matching the old
    terminal's "Journal" tab). Reuses ForexTradeJournalEngine.list_entries()
    -- confirmed a pure, properly-parameterized DB query (portfolio_id,
    user_id, and tenant_id all taken directly, no client-side filtering
    workaround needed the way positions required). No live fetch.

    Field names (pair, side, setup, thesis, entry_price, exit_price,
    units, pnl, outcome, emotion, mistake_tags, lesson, created_at)
    confirmed directly against the real CREATE TABLE statement.
    """
    if db is None or portfolio_id is None:
        return []

    try:
        from modules.forex.forex_trade_journal_engine import get_forex_trade_journal_engine

        engine = get_forex_trade_journal_engine(db=db)
        return engine.list_entries(
            portfolio_id=portfolio_id, user_id=user_id, tenant_id=tenant_id,
        ) or []

    except Exception:
        return []


def _create_journal_entry(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
    pair: str, side: str, setup: str, thesis: str,
    entry_price: float | None, units: float | None, emotion: str | None,
) -> dict:
    """
    Creates a real journal entry -- the first WRITE operation in this
    module; everything else built so far has been read-only. Reuses
    ForexTradeJournalEngine.create_entry() directly, confirmed its
    exact signature and that it commits the transaction internally
    (self.db.commit()) before wiring a form around it, rather than
    assuming its shape from the read side alone.

    Returns {"status": "ok", "id": ...} on success or
    {"status": "error", "message": ...} on failure -- the caller
    decides how to surface that, this stays a plain data function.
    """
    if db is None or portfolio_id is None:
        return {"status": "error", "message": "No portfolio selected."}

    try:
        from modules.forex.forex_trade_journal_engine import get_forex_trade_journal_engine

        engine = get_forex_trade_journal_engine(db=db)
        result = engine.create_entry(
            pair=pair,
            side=side,
            setup=setup,
            thesis=thesis,
            entry_price=entry_price,
            units=units,
            portfolio_id=portfolio_id,
            user_id=user_id,
            tenant_id=tenant_id,
            emotion=emotion,
        )
        return {"status": "ok", "id": result.get("id")}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


RISK_THROTTLE_SECONDS = 15.0


def _get_throttled_risk_summary(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Real institutional risk summary (Daily VaR, Expected Shortfall,
    gross/net exposure -- matching the old terminal's "INSTITUTIONAL
    VAR SUMMARY" output), throttled the same way as everything else.

    Calls ForexPortfolioEngine._build_var_summary() directly -- no
    public wrapper exists for this. Its own docstring says failures
    don't block the standard snapshot, and _load_positions_into_var_engine
    (which it calls) explicitly documents doing no query/persist, only
    in-memory mapping.

    IMPORTANT, found only by testing rather than by reading alone: that
    verification was incomplete. _build_var_summary also calls
    build_portfolio_statistics() -> portfolio_standard_deviation() ->
    covariance_matrix_dataframe() -> historical_return_matrix(), which
    DOES do a real live history fetch (confirmed directly: a fresh
    first call showed a real "FOREX HISTORY DEBUG | REQUEST" for 3
    years of EUR/USD data, ~680ms even with every provider failing in
    this sandbox). Traced this down before treating the method as safe
    rather than assuming the first docstring covered every code path.

    The actual behavior turns out fine regardless: the VaR engine
    instance is a persistent cached singleton (get_forex_var_engine(),
    already found fixed for the identity-caching bug elsewhere this
    session), and covariance_matrix_dataframe() has its own internal
    cache checked before rebuilding. Confirmed directly: a second call
    even past THIS throttle's own 15s window took 2.79ms with no
    history fetch triggered at all -- the expensive fetch happens once
    per process lifetime, not on every throttle expiry, layered
    underneath this outer session_state throttle rather than
    conflicting with it.

    Needs raw ForexPosition dataclasses (list_positions()), not the
    dict-converted versions from load_positions() used elsewhere for
    Positions/KPIs -- client-side filtered by portfolio_id the same
    way, since list_positions() is tenant-scoped, not portfolio-
    scoped (same pre-existing quirk noted for _get_positions_for_display).
    """
    if db is None or portfolio_id is None:
        return {"status": "ERROR", "message": "No portfolio selected."}

    cache_key = f"fx_v2_risk_cache:{portfolio_id}"
    ts_key = f"fx_v2_risk_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < RISK_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        account = engine.get_account(portfolio_id=portfolio_id)

        if account is None:
            result = {"status": "ERROR", "message": "No account exists for this portfolio yet."}
        else:
            all_positions = engine.list_positions(status="OPEN")
            positions = [p for p in all_positions if p.portfolio_id == portfolio_id]
            result = engine._build_var_summary(account=account, positions=positions)

            # Stress testing / risk score / heat map data. Confirmed
            # ForexInstitutionalRiskEngine.analyze() and stress_tests()
            # are pure local computation over a passed-in snapshot dict
            # -- no DB access anywhere in either method despite the
            # class accepting a db param -- so constructing it directly
            # (not via its own get_forex_institutional_risk_engine()
            # factory) is both simpler and sidesteps that factory's own
            # stale-cache-on-reuse risk for free, since it's never
            # actually used here.
            from modules.forex.forex_institutional_risk_engine import ForexInstitutionalRiskEngine

            currency_exposure = engine.calculate_currency_exposure(positions=positions, account=account)
            pair_exposure = engine.calculate_pair_exposure(positions=positions, account=account)

            snapshot = {
                "account": {"equity": account.equity},
                "positions": [
                    {"unrealized_pnl": p.unrealized_pnl} for p in positions
                ],
                "currency_exposure": currency_exposure,
                "pair_exposure": pair_exposure,
            }
            institutional = ForexInstitutionalRiskEngine().analyze(snapshot)

            result["stress_tests"] = institutional.get("stress_tests") or []
            result["institutional_risk_score"] = institutional.get("risk_score")
            result["institutional_warnings"] = institutional.get("warnings") or []
            result["pair_exposure"] = pair_exposure

    except Exception as exc:
        result = {"status": "ERROR", "message": str(exc)}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


PERFORMANCE_THROTTLE_SECONDS = 15.0


def _get_throttled_performance_summary(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Real performance statistics (win rate, profit factor, realized/
    unrealized P&L, expectancy -- matching the old terminal's
    "PERFORMANCE HISTORY" output), throttled the same way as
    everything else.

    Calls ForexPortfolioEngine.calculate_performance_statistics()
    directly -- no public wrapper exists. Unlike the risk-summary
    helper's first pass, traced the ENTIRE call chain this time before
    treating it as safe, not just the first internal call: both
    calculate_performance_statistics() itself and the
    _build_performance_history() it calls are confirmed pure
    computation over already-persisted DB data (a plain SELECT against
    stored portfolio snapshots, then arithmetic over passed-in
    positions/orders/ledger rows) -- no live fetch anywhere in this
    particular chain, unlike the risk summary's covariance matrix
    dependency.

    Gathers the same account/positions already fetched elsewhere in
    this module, plus closed positions, filled orders, execution
    history, and cash ledger -- all DB-only reads, all already-
    confirmed-safe methods on the same engine.
    """
    if db is None or portfolio_id is None:
        return {"status": "ERROR", "message": "No portfolio selected."}

    cache_key = f"fx_v2_performance_cache:{portfolio_id}"
    ts_key = f"fx_v2_performance_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < PERFORMANCE_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        account = engine.get_account(portfolio_id=portfolio_id)

        if account is None:
            result = {"status": "ERROR", "message": "No account exists for this portfolio yet."}
        else:
            all_open = engine.list_positions(status="OPEN")
            all_closed = engine.list_positions(status="CLOSED")
            positions = [p for p in all_open if p.portfolio_id == portfolio_id]
            closed_positions = [p for p in all_closed if p.portfolio_id == portfolio_id]
            filled_orders = engine.load_filled_orders(portfolio_id=portfolio_id)
            execution_history = engine.load_execution_history(portfolio_id=portfolio_id)
            cash_ledger = engine.load_cash_ledger(account_id=account.id)

            stats = engine.calculate_performance_statistics(
                account=account,
                positions=positions,
                closed_positions=closed_positions,
                filled_orders=filled_orders,
                execution_history=execution_history,
                cash_ledger=cash_ledger,
            )
            result = {"status": "READY", **stats}

    except Exception as exc:
        result = {"status": "ERROR", "message": str(exc)}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


AI_BRIEFING_THROTTLE_SECONDS = 15.0


def _get_throttled_ai_briefing(*, force: bool = False) -> dict:
    """
    Real daily AI briefing (matching the old terminal's "AI Briefing"
    tab), throttled the same way as everything else.

    Calls ForexAIAssistant.daily_briefing() directly. Traced the
    ENTIRE call chain before building this, not just the first call --
    daily_briefing() -> strategy_lab.run() -> {generate_trade_plan()
    [-> alpha.run_alpha_model(), macro_regime.analyze(),
    sentiment.analyze()], performance.analyze(), journal.summarize()}
    and daily_briefing() -> optimizer.optimize() [-> alpha.run_alpha_model()
    again]. Several of these independently call run_alpha_model(), but
    that already has its own 8s internal cache on the singleton alpha
    model instance (confirmed earlier this session building AI
    Confidence) -- so multiple calls within one daily_briefing()
    invocation mostly hit that cache rather than tripling the real
    cost the call graph might suggest on paper.

    Deliberately calls the real, full chain rather than building a
    leaner substitute from pieces already throttled elsewhere in this
    module (market regime, AI confidence) -- the old terminal's
    equivalent function had a real @_cache_ttl(15.0) decorator on
    exactly this call, so matching that directly keeps this "exactly
    the same as the original" rather than an approximation of it.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_ai_briefing_cache"
    ts_key = "fx_v2_ai_briefing_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < AI_BRIEFING_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_ai_assistant import get_forex_ai_assistant

        result = get_forex_ai_assistant().daily_briefing()
    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


LIVE_MARKET_THROTTLE_SECONDS = 15.0


PRICE_CHART_THROTTLE_SECONDS = 15.0


CALENDAR_THROTTLE_SECONDS = 15.0


def _get_throttled_economic_calendar(*, force: bool = False) -> dict:
    """
    Real USD economic-release schedule (FRED-backed), matching the old
    terminal's "Economic Calendar" panel, throttled the same way as
    everything else -- calendar() already has its own internal 15s
    cache too, matching this outer one.

    Confirmed calendar() returns an honest empty list with a clear
    "coverage_note" explaining why (FRED_API_KEY not configured/
    reachable) rather than a fixed CPI/PCE/PMI sample table -- so an
    empty result here is expected, accurate behavior, not a bug, in
    any environment without FRED configured.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_calendar_cache"
    ts_key = "fx_v2_calendar_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < CALENDAR_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_macro_calendar_engine import get_forex_macro_calendar_engine

        data = get_forex_macro_calendar_engine().calendar()
        events = data.get("events") if isinstance(data, dict) else None
        events = events if isinstance(events, list) else []

        rows = [
            {
                "Time": item.get("time") or item.get("date") or "-",
                "Currency": item.get("currency") or item.get("ccy") or "-",
                "Event": item.get("event") or item.get("title") or item.get("name") or "-",
                "Actual": item.get("actual", "-"),
                "Forecast": item.get("forecast", "-"),
            }
            for item in events if isinstance(item, dict)
        ][:8]
        result = {"rows": rows, "coverage_note": data.get("coverage_note") if isinstance(data, dict) else None}

    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


CENTRAL_BANK_THROTTLE_SECONDS = 15.0


def _get_throttled_central_bank_events(*, force: bool = False) -> dict:
    """
    Real central bank policy-rate snapshot (FRED-backed), matching the
    old terminal's "Central Bank Events" panel, throttled the same way.

    Confirmed "Impact": "High" is a fixed, honest label the original
    applies to every real policy-rate row (not a fabricated per-row
    computation) -- central bank rate decisions are inherently
    high-impact news regardless of which bank or rate. Replicated
    exactly rather than inventing a variable score that doesn't exist
    in the source.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_central_bank_cache"
    ts_key = "fx_v2_central_bank_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < CENTRAL_BANK_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine

        data = get_forex_central_bank_engine().analyze()
        banks = data.get("central_banks") if isinstance(data, dict) else None
        banks = banks if isinstance(banks, list) else []

        rows = []
        for item in banks:
            if not isinstance(item, dict) or item.get("error"):
                continue
            rate = item.get("policy_rate")
            rows.append({
                "Date": item.get("policy_rate_asof", "-"),
                "Currency": item.get("currency", "-"),
                "Event": (
                    f"{item.get('central_bank', '-')} Policy Rate: {rate:.2f}%"
                    if isinstance(rate, (int, float))
                    else f"{item.get('central_bank', '-')} Policy Rate: unavailable"
                ),
                "Impact": "High",
            })
        result = {"rows": rows[:8]}

    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


def _get_throttled_price_chart(pair: str, *, force: bool = False):
    """
    Real intraday candlestick chart for a pair, with buy/sell/TP-SL
    overlay (matching the old terminal's "Live Chart" panel).

    IMPORTANT: uses the already-fixed 5-day / 1h window, not the
    original's own default. Confirmed via the original's own
    docstring: fetch_from_router() defaults to ~1,095 days of history
    when no start_date is given, which for a 1h interval can balloon
    to ~17,500 candles -- documented there as severe enough to freeze
    the browser tab on render alone (Plotly renders each candle as
    real SVG elements on the main thread), independent of how fast the
    Python/network side responds. Bounding to a real intraday window
    (5 days of 1h bars, ~120 candles) avoids that regardless of how
    this helper is called.

    compute_signals()/add_signal_overlay() confirmed pure local
    technical-analysis computation (EMA crossover, RSI, ATR-based
    TP1-4/SL levels) over the already-fetched OHLC data -- no
    additional network cost beyond the one history fetch.
    """
    if go is None:
        return {"error": "Plotly is unavailable."}

    cache_key = f"fx_v2_price_chart_cache:{pair}"
    ts_key = f"fx_v2_price_chart_last_fetch_ts:{pair}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < PRICE_CHART_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from datetime import timedelta
        from modules.forex.forex_history_service import get_forex_history_service

        chart_start = (datetime.now(timezone.utc) - timedelta(days=5)).date()
        payload = get_forex_history_service().fetch_from_router(pair, interval="1h", start_date=chart_start)

        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not rows:
            error = payload.get("error") if isinstance(payload, dict) else None
            result = {"error": error or f"No live history returned for {pair} yet."}
        else:
            x = [row.get("asof") for row in rows]
            open_ = [row.get("open") for row in rows]
            high = [row.get("high") for row in rows]
            low = [row.get("low") for row in rows]
            close = [row.get("close") for row in rows]

            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=x, open=open_, high=high, low=low, close=close, name=pair))

            try:
                import pandas as pd
                from modules.indicators.signal_suite import compute_signals, add_signal_overlay

                sig_df = compute_signals(pd.DataFrame(
                    {"Date": x, "Open": open_, "High": high, "Low": low, "Close": close}
                ))
                add_signal_overlay(fig, sig_df, row=None, col=None, show_ribbon=False)
            except Exception:
                pass

            fig.update_layout(
                template="plotly_dark", height=430, margin=dict(l=5, r=5, t=28, b=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                title=f"{pair} \u00b7 Live History", xaxis_rangeslider_visible=False,
                yaxis=dict(title="Price"), legend=dict(orientation="h"),
            )
            result = {"figure": fig, "error": None}

    except Exception as exc:
        result = {"error": f"Live chart unavailable: {exc}"}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


def _add_watchlist_pair(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, pair: str,
) -> dict:
    """
    Adds a pair to the watchlist -- a real write operation. Confirmed
    add_pair()'s exact behavior before wiring a form around it: it
    returns False (not an exception) if the pair already exists, and
    commits internally on success.
    """
    if db is None or not pair:
        return {"status": "error", "message": "No pair given."}

    try:
        from modules.forex.forex_watchlist_factory import get_forex_watchlist_service

        service = get_forex_watchlist_service(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        added = service.add_pair(pair=pair)

        if added:
            return {"status": "ok"}
        return {"status": "error", "message": f"{pair.upper()} is already on the watchlist."}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _remove_watchlist_pair(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, pair: str,
) -> dict:
    """
    Removes a pair from the watchlist -- a real write operation.
    Confirmed remove_pair()'s exact behavior: returns a bool based on
    the actual DB rowcount deleted (not just "did it try"), commits
    internally on success.
    """
    if db is None or not pair:
        return {"status": "error", "message": "No pair given."}

    try:
        from modules.forex.forex_watchlist_factory import get_forex_watchlist_service

        service = get_forex_watchlist_service(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        removed = service.remove_pair(pair=pair)

        if removed:
            return {"status": "ok"}
        return {"status": "error", "message": f"{pair.upper()} was not on the watchlist."}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _get_throttled_live_market(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Real live quotes for every pair on the watchlist (matching the old
    terminal's "Live Market" section), throttled the same way as
    everything else.

    Traced the original's approach fully before building this. Two
    real, already-fixed bugs found along the way, both directly
    relevant to why this specific section was flagged as risky:

    1. The pair list comes from get_forex_watchlist_service(...).load_watchlist()
       -- confirmed a DB-only, idempotent get-or-create (only creates a
       default watchlist if one doesn't exist yet, otherwise just loads
       it), and confirmed its own ensure_tables() bug (never actually
       called, causing a real "no such table" crash on a fresh
       database) was already found and fixed.

    2. The original then fetched watchlist pairs ONE AT A TIME,
       serially -- a documented, already-fixed bug worth ~70+ seconds
       by itself on ~19 pairs, and the dominant cause of a previously
       reported "almost 1 minute 30 seconds" Trading Desk load.

    Reuses ForexService.get_quotes() here instead of re-implementing
    the fix -- that method itself was independently found and fixed
    for the same underlying issue (its docstring documents the
    provider order used to be reversed, hitting the slow uncached path
    on every single call); it already does a parallel, cache-aware
    batch fetch through the same provider router used everywhere else
    in this rebuild.
    """
    if db is None:
        return {"quotes": [], "error": None}

    cache_key = f"fx_v2_live_market_cache:{portfolio_id}"
    ts_key = f"fx_v2_live_market_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < LIVE_MARKET_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_watchlist_factory import get_forex_watchlist_service
        from modules.forex.forex_service import get_forex_service

        watchlist_service = get_forex_watchlist_service(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        watchlist = watchlist_service.load_watchlist()
        pairs = [item.pair for item in watchlist.items]

        if not pairs:
            result = {"quotes": [], "error": None}
        else:
            service = get_forex_service(db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id)
            quote_map = service.get_quotes(pairs)

            rows = [
                {
                    "pair": q.pair,
                    "bid": q.bid,
                    "ask": q.ask,
                    "mid": q.mid,
                    "spread": q.spread,
                    "provider": q.provider,
                    "volume": q.volume,
                }
                for q in quote_map.values()
                if q is not None
            ]
            result = {"quotes": rows, "error": None}

    except Exception as exc:
        result = {"quotes": [], "error": str(exc)}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


EXPOSURE_THROTTLE_SECONDS = 15.0


def _get_throttled_exposure(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Real currency exposure, pair exposure, and cash ledger (matching
    the old terminal's "Currency Exposure"/"Pair Exposure"/"Cash
    Ledger" sections), throttled the same way as everything else.

    calculate_currency_exposure()/calculate_pair_exposure() confirmed
    pure, local computation over passed-in positions/account -- no
    live fetch, just bucketing already-persisted open positions.
    load_cash_ledger() already verified safe (DB-only) when building
    the Performance tab.

    Deliberately does NOT replicate the original's "Portfolio
    Allocation" section: traced where its "allocation" key would need
    to come from and found no method anywhere in the source ever
    populates it -- that section is silently empty in the original
    too, so there was nothing real to replicate.
    """
    if db is None or portfolio_id is None:
        return {"currency_exposure": [], "pair_exposure": [], "cash_ledger": []}

    cache_key = f"fx_v2_exposure_cache:{portfolio_id}"
    ts_key = f"fx_v2_exposure_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < EXPOSURE_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        account = engine.get_account(portfolio_id=portfolio_id)

        if account is None:
            result = {"currency_exposure": [], "pair_exposure": [], "cash_ledger": []}
        else:
            all_positions = engine.list_positions(status="OPEN")
            positions = [p for p in all_positions if p.portfolio_id == portfolio_id]

            result = {
                "currency_exposure": engine.calculate_currency_exposure(positions=positions, account=account),
                "pair_exposure": engine.calculate_pair_exposure(positions=positions, account=account),
                "cash_ledger": engine.load_cash_ledger(account_id=account.id),
            }

    except Exception as exc:
        result = {"currency_exposure": [], "pair_exposure": [], "cash_ledger": [], "error": str(exc)}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


EXECUTION_QUALITY_THROTTLE_SECONDS = 15.0


def _get_throttled_execution_quality(
    db, *, portfolio_id: str | None, account_id: str | None, force: bool = False,
) -> dict:
    """
    Real execution quality metrics (matching the old terminal's 8
    separate "Execution ..." sections, consolidated into one here --
    see the docstring on the workspace tab for why). Throttled the
    same way as everything else.

    IMPORTANT -- does NOT call repository.load_execution_quality()
    either. Confirmed via real production data: it depends on
    load_execution_history(), whose own fallback chain checks
    "execution_events" FIRST -- and that table exists in production
    with real rows, so load_execution_history() stops there and never
    reaches forex_trade_orders at all. execution_events turned out to
    be an event log (NEW_ORDER events, one or more per real order) with
    no "status" column and no "filled_qty" column whatsoever -- so
    load_execution_quality()'s counting logic (built assuming those
    fields exist) silently computed nonsense against a table it was
    never designed for: fill_rate came out 0.0% because "status"
    always defaulted to empty string, and partial_fills came out equal
    to the full row count because the "filled" side of its comparison
    always defaulted to 0 for every row. Rather than depend on that
    method's unpredictable table selection, quality metrics are
    computed directly here from the same orders list already fetched
    above for order statistics -- guaranteeing both sections agree and
    are both provably grounded in the one, confirmed-correct table.
    """
    if db is None or portfolio_id is None:
        return {"error": None, "statistics": {}, "quality": {}}

    cache_key = f"fx_v2_execution_quality_cache:{portfolio_id}"
    ts_key = f"fx_v2_execution_quality_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < EXECUTION_QUALITY_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_execution_repository import get_forex_execution_repository

        repository = get_forex_execution_repository(db=db)

        orders = repository.load_orders(account_id=account_id, portfolio_id=portfolio_id, limit=100000)

        filled = pending = cancelled = rejected = 0
        partial_fills = 0
        slippage_values = []
        latency_values = []

        for order in orders:
            status = str(order.get("status", "")).upper()
            if status in {"FILLED", "EXECUTED"}:
                filled += 1
            elif status in {"PENDING", "OPEN", "WORKING"}:
                pending += 1
            elif status in {"CANCELLED", "CANCELED"}:
                cancelled += 1
            elif status == "REJECTED":
                rejected += 1

            filled_qty = order.get("filled_qty") or 0
            order_qty = order.get("units") or order.get("quantity") or 0
            if order_qty > 0 and 0 < filled_qty < order_qty:
                partial_fills += 1

            expected_price = order.get("requested_price") or order.get("price") or order.get("limit_price")
            actual_price = order.get("avg_fill_price")
            if expected_price is not None and actual_price is not None:
                try:
                    slippage_values.append(float(actual_price) - float(expected_price))
                except (TypeError, ValueError):
                    pass

            submitted_at = order.get("submitted_at")
            filled_at = order.get("filled_at")
            if submitted_at is not None and filled_at is not None:
                try:
                    if isinstance(submitted_at, str):
                        submitted_at = datetime.fromisoformat(submitted_at)
                    if isinstance(filled_at, str):
                        filled_at = datetime.fromisoformat(filled_at)
                    latency_values.append(max(0.0, (filled_at - submitted_at).total_seconds()))
                except (TypeError, ValueError):
                    pass

        total_orders = len(orders)
        statistics = {
            "total_orders": total_orders,
            "filled_orders": filled,
            "pending_orders": pending,
            "cancelled_orders": cancelled,
            "rejected_orders": rejected,
        }
        quality = {
            "fill_rate": (filled / total_orders * 100.0) if total_orders else 0.0,
            "average_slippage": (sum(slippage_values) / len(slippage_values)) if slippage_values else None,
            "average_latency_seconds": (sum(latency_values) / len(latency_values)) if latency_values else None,
            "partial_fills": partial_fills,
        }

        result = {
            "error": None,
            "statistics": statistics,
            "quality": quality,
        }

    except Exception as exc:
        result = {"error": str(exc), "statistics": {}, "quality": {}}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


def _get_ai_trade_recommendation(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
    account_id: str | None, pair: str, risk_pct: float,
) -> dict:
    """
    Generates a fresh AI trade recommendation for a pair -- not
    throttled, since this only runs on an explicit "Analyze Trade"
    click, matching the original's own UX (the user is asking for a
    fresh read each time, not a background poll).

    Traced the full chain before wiring a button around it:
    recommend_position_from_signal() -> generate_signal() ->
    score_pair() does exactly one live quote fetch (through the
    already-fixed ForexService); every other scoring step (trend,
    momentum, volatility, carry, liquidity, correlation, macro) is
    pure local computation -- confirmed each one returns a fixed,
    neutral default when historical prices aren't supplied (as here)
    rather than trying to fetch anything itself. generate_signal()
    then does one DB write (save_signal()), matching the method's own
    save=True default -- not something this wrapper adds.
    """
    if db is None or account_id is None:
        return {"status": "error", "message": "No account available."}

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        recommendation = engine.recommend_position_from_signal(
            account_id=account_id, pair=pair, risk_pct=risk_pct,
        )
        if recommendation is None:
            return {"status": "error", "message": "The AI was unable to generate a recommendation."}
        return {"status": "ok", "recommendation": recommendation}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _execute_ai_trade(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None,
    account_id: str | None, pair: str, side: str, units: float,
    stop_price: float | None, target_price: float | None,
) -> dict:
    """
    Executes a real trade from an AI recommendation -- a write
    operation. Submits as a MARKET order (matching the original's own
    "Execute AI Trade" behavior -- immediate execution at the current
    price, not a resting limit order).

    Traced the full chain first: submit() -> ... -> the order
    pipeline's market route -> open_position(), which -- like
    close_position() traced earlier this session -- always makes one
    real live quote fetch of its own (through the same already-fixed
    ForexService), regardless of any price already supplied.

    IMPORTANT: constructs ForexOrderManagementEngine(db=db) directly
    here rather than through get_forex_order_management_engine(). That
    factory only replaces its cached instance when the cached one's db
    is None -- so once built with a real session, it keeps using that
    same session on every later call even after Streamlit closes it
    for a fresh rerun. Confirmed the class itself is trivial to
    construct (only self.db = db, nothing expensive), and confirmed
    the inner factory submit() actually delegates to
    (get_forex_terminal_execution_service()) has already been fixed
    for this exact bug -- its own docstring documents constructing a
    fresh instance every time for precisely this reason. Bypassing the
    outer, still-buggy factory avoids the risk entirely while relying
    on the inner, already-safe one.
    """
    if db is None or account_id is None:
        return {"status": "error", "message": "No account available."}

    try:
        from modules.forex.forex_order_management_engine import ForexOrderManagementEngine

        order_engine = ForexOrderManagementEngine(db=db)
        result = order_engine.submit(
            pair=pair,
            side=side,
            units=units,
            order_type="MARKET",
            limit_price=None,
            stop_price=stop_price,
            take_profit=target_price,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
            account_id=account_id,
        )

        status = (result or {}).get("status", "").upper()
        if status in {"REJECTED", "ERROR"}:
            return {"status": "error", "message": result.get("message", "Order was rejected."), "result": result}
        return {"status": "ok", "result": result}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _run_autonomous_cycle(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, account_id: str | None,
) -> dict:
    """
    Runs one autonomous trading cycle -- a real write operation,
    matching the original's exact one-click, no-preview behavior (per
    explicit user confirmation).

    IMPORTANT: does NOT call ForexAIDashboard.run_autonomous_cycle()
    for the execution step, despite it being the obvious direct
    replacement. Traced the real cause of a real, screenshotted
    failure first: the original's chain (autonomous_cycle() ->
    execute() -> run_cycle() -> execute_recommendation() ->
    submit_order()) passes through FOUR nested singleton factories
    (get_forex_ai_orchestrator, get_forex_ai_assistant,
    get_forex_autonomous_trader, get_forex_trade_execution_engine),
    every one of which caches its instance on first construction and
    never rebuilds on a later call -- confirmed directly across all
    four. That means the deeply-nested execution engine can end up
    holding a stale db session from whenever it was first constructed
    anywhere in the app's lifetime, unrelated to the real, current
    session actually containing the selected portfolio -- exactly
    matching a real rejection observed ("A portfolio must be created
    or selected...") for a portfolio that genuinely existed.

    Confirmed risk.analyze() and lab.run() are each called with zero
    portfolio-specific arguments in the original's own run_cycle(), so
    reusing them via the existing (possibly stale-db) trader is safe
    -- they were never portfolio-specific to begin with, so a stale db
    doesn't change their result. Only the actual order submission is
    routed through _execute_ai_trade() instead, which already
    constructs its own engine directly rather than through a cached
    factory.
    """
    if db is None or account_id is None:
        return {"status": "error", "message": "No account available."}

    try:
        from modules.forex.forex_autonomous_trader import get_forex_autonomous_trader

        trader = get_forex_autonomous_trader(db=db)

        risk = trader.risk.analyze()
        if risk.get("risk_level") == "HIGH":
            return {"status": "blocked", "reason": "Risk controls prevented autonomous execution.", "risk": risk}

        plan = trader.lab.run()
        trades = (plan.get("trade_plan") or {}).get("top_trades") or []
        if not trades:
            return {"status": "idle", "reason": "No qualifying trade opportunities."}

        top = trades[0]
        pair = top.get("pair")
        rec = str(top.get("recommendation") or top.get("direction") or "").upper()
        side = "BUY" if "BUY" in rec else ("SELL" if "SELL" in rec else None)

        if not pair or not side:
            return {"status": "error", "message": "Top recommendation is not executable.", "recommendation": top}

        suggested_notional = float(top.get("suggested_notional") or 0.0)
        entry = float(top.get("entry_price") or 0.0)
        units = suggested_notional / entry if suggested_notional > 0 and entry > 0 else 10000.0

        exec_result = _execute_ai_trade(
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, account_id=account_id,
            pair=pair, side=side, units=units,
            stop_price=top.get("stop_price"), target_price=top.get("target_price"),
        )

        if exec_result.get("status") == "ok":
            return {"status": "executed", "trade": exec_result.get("result"), "risk": risk}
        return {"status": "error", "message": exec_result.get("message", "Order was rejected."), "risk": risk}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


AI_EXECUTIVE_THROTTLE_SECONDS = 15.0


def _get_throttled_ai_executive(
    db, *, tenant_id: str | None, user_id: str | None, portfolio_id: str | None, force: bool = False,
) -> dict:
    """
    Real AI executive summary + consensus (matching the old terminal's
    "AI & Quant Platform" -> Executive sub-tab), throttled the same
    way as everything else -- more important here than most other
    tabs, since confirmed directly that building this payload triggers
    real, live multi-pair historical-data fetch attempts through the
    command-center engine's alpha/institutional-flow sub-loaders, not
    just one quote.

    Builds the payload the same way ForexAIDashboard._payload() does
    in the real app (reusing daily_briefing(), already used for the
    AI Briefing tab, plus the AI command center/investment
    committee/research copilot engines) -- confirmed via direct
    testing that the real production payload has no top-level
    "quant_research" or "enterprise_reporting" keys at all, so several
    of the original's 11 AI-platform sub-tabs are effectively empty in
    the real app today; not something this rebuild can or should
    silently paper over.

    Fixes one specific, confirmed bug rather than leaving it in place:
    extract_regime() checks a top-level "market_regime" key first,
    but its fallback (a generic recursive search) can land on the
    first dict anywhere in the payload that merely happens to contain
    a "regime"-shaped key, independent of whether it has a usable
    value -- confirmed directly that this caused real, correctly-
    supplied regime data to still show "Unknown". Placing the
    already-safe, already-cached macro_regime_engine.analyze() result
    at that exact top-level key guarantees the first, reliable check
    finds it instead.
    """
    if db is None:
        return {"status": "ERROR", "message": "No database available."}

    cache_key = f"fx_v2_ai_executive_cache:{portfolio_id}"
    ts_key = f"fx_v2_ai_executive_last_fetch_ts:{portfolio_id}"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0) if st is not None else 0.0
    cached = st.session_state.get(cache_key) if st is not None else None
    age_seconds = now_ts - last_fetch_ts

    if st is not None and not force and cached is not None and age_seconds < AI_EXECUTIVE_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_ai_dashboard import ForexAIDashboard
        from modules.forex.ui.forex_ai_executive_adapter import normalize_executive_ai_payload
        from modules.forex.ui.forex_ai_consensus_engine import build_consensus
        from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine

        dashboard = ForexAIDashboard(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        payload = dashboard._payload()

        try:
            payload["market_regime"] = get_forex_macro_regime_engine().analyze()
        except Exception:
            pass

        data = normalize_executive_ai_payload(payload)
        consensus = build_consensus(payload)

        result = {"status": "READY", "data": data, "consensus": consensus}

    except Exception as exc:
        result = {"status": "ERROR", "message": str(exc)}

    if st is not None:
        st.session_state[cache_key] = result
        st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


STRENGTH_THROTTLE_SECONDS = 15.0


def _get_throttled_currency_strength(*, force: bool = False) -> dict:
    """
    Real currency-strength scan (strongest/weakest currency, matching
    the old terminal's "Strongest Currency"/"Weakest Currency" tiles),
    throttled the same way as the quote fetch above -- this is the
    riskiest piece added back so far, since the underlying
    ForexCurrencyStrengthEngine.scan_currencies() call does its own
    live quote fetch across multiple pairs internally (the same class
    of work that dominated the old terminal's slowness). Built with
    the same throttle-from-day-one discipline as the quote fetch
    rather than added without one and fixed later.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_strength_cache"
    ts_key = "fx_v2_strength_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < STRENGTH_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine

        result = get_forex_currency_strength_engine().scan_currencies()
    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


REGIME_THROTTLE_SECONDS = 15.0


def _get_throttled_market_regime(*, force: bool = False) -> dict:
    """
    Real market regime (RISK_ON/RISK_OFF/BALANCED + macro score,
    matching the old terminal's "Market Regime" tile), throttled the
    same way as currency strength and quotes.

    ForexMacroRegimeEngine.analyze() internally does its own currency-
    strength scan AND a central bank analysis call -- independently
    throttled here (own 15s window) rather than threading the already-
    throttled currency-strength result through analyze()'s `runtime`
    parameter to avoid a duplicate fetch; that would need constructing
    an object with a matching `.currency_strength` attribute shape,
    adding coupling between two throttled caches for a minor
    efficiency gain. The old terminal called these independently too.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_regime_cache"
    ts_key = "fx_v2_regime_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < REGIME_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine

        result = get_forex_macro_regime_engine().analyze()
    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


AI_CONFIDENCE_THROTTLE_SECONDS = 15.0


def _get_throttled_ai_confidence(*, force: bool = False) -> dict:
    """
    Real AI confidence (matching the old terminal's "AI Confidence /
    Model consensus" tile), computed the same way the original does:
    the MAXIMUM confidence_score across all alpha-model signals, not
    an average -- confirmed directly against forex_terminal_dashboard.py's
    own computation (ai_conf = max(conf_candidates)) rather than
    guessed at.

    run_alpha_model() already has its own internal cache (8s TTL, on
    the cached singleton alpha model instance -- persists across all
    calls in this process, not just this session). That's shorter
    than the established 15s pattern here, and shorter windows already
    proved to get "eaten" by other slow operations on the same page
    (see _get_throttled_account_summary's history) -- so this still
    wraps it in the same session_state throttle as everything else,
    with the internal 8s cache as a safety net underneath even if this
    outer throttle is ever bypassed via force=True.

    This scans all 28 pairs (vs. currency strength's 12), so it's the
    most expensive of the four pieces built so far.
    """
    if st is None:
        return {"error": "streamlit_not_available"}

    cache_key = "fx_v2_ai_confidence_cache"
    ts_key = "fx_v2_ai_confidence_last_fetch_ts"

    now_ts = time.time()
    last_fetch_ts = st.session_state.get(ts_key, 0.0)
    cached = st.session_state.get(cache_key)
    age_seconds = now_ts - last_fetch_ts

    if not force and cached is not None and age_seconds < AI_CONFIDENCE_THROTTLE_SECONDS:
        return {**cached, "_cache_age_seconds": round(age_seconds, 1), "_from_cache": True}

    try:
        from modules.forex.forex_alpha_model import get_forex_alpha_model

        payload = get_forex_alpha_model().run_alpha_model()
        signals = payload.get("signals") or []
        confidences = [
            s.get("confidence_score") for s in signals
            if isinstance(s, dict) and s.get("confidence_score") is not None
        ]

        # Recommendation cards, replicating the original's own bias
        # bucketing exactly (ForexInstitutionalScanner.scan()): a pure,
        # local, deterministic bucket of alpha_score, not a separate
        # fetch -- same signals list already retrieved above.
        recommendations = []
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            score = float(signal.get("alpha_score") or 0)
            direction = str(signal.get("recommendation") or "WATCH").upper()
            is_buy = any(x in direction for x in ("BUY", "LONG", "BULL"))
            is_sell = any(x in direction for x in ("SELL", "SHORT", "BEAR"))
            side = "BUY" if is_buy else "SELL" if is_sell else "WATCH"

            if score >= 80:
                bias = "STRONG_INSTITUTIONAL_ACCUMULATION" if is_buy else "STRONG_INSTITUTIONAL_DISTRIBUTION"
            elif score >= 65:
                bias = "ACCUMULATION" if is_buy else "DISTRIBUTION"
            else:
                bias = "NEUTRAL"

            recommendations.append({
                "pair": signal.get("pair"),
                "side": side,
                "confidence": signal.get("confidence_score"),
                "entry": signal.get("entry_price"),
                "stop": signal.get("stop_price"),
                "target": signal.get("target_price"),
                "bias": bias,
                "risk_reward": signal.get("risk_reward"),
            })
        recommendations.sort(key=lambda r: r.get("confidence") or 0, reverse=True)

        result = {
            "ai_confidence": max(confidences) if confidences else None,
            "signal_count": len(signals),
            "recommendations": recommendations,
        }
    except Exception as exc:
        result = {"error": str(exc)}

    st.session_state[cache_key] = result
    st.session_state[ts_key] = now_ts

    return {**result, "_cache_age_seconds": 0.0, "_from_cache": False}


WORKSPACE_TABS = [
    "Overview",
    "Positions",
    "Orders",
    "Risk",
    "Performance",
    "Journal",
    "AI Briefing",
    "AI Trade Setup",
    "AI Command Center",
    "Live Market",
    "Exposure",
    "Execution Quality",
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


def _class_for(value) -> str:
    """
    Copied directly from forex_terminal_dashboard.py rather than
    imported -- importing just this and 3 similarly small helpers from
    that file cost 10.5 SECONDS (confirmed by measuring it directly),
    due to that file's own module-level side effects. That would have
    silently reintroduced exactly the kind of hidden first-render cost
    this rebuild exists to eliminate, just moved into an import
    statement instead of a data fetch.
    """
    v = str(value or "").upper()
    if any(x in v for x in ["BUY", "BULL", "LONG", "HEALTHY", "READY", "PASS", "HIGH"]):
        return "fx-positive"
    if any(x in v for x in ["SELL", "BEAR", "SHORT", "ERROR", "FAIL", "RISK-OFF", "RISK_OFF", "RATE", "DEGRADED"]):
        return "fx-negative"
    if any(x in v for x in ["WATCH", "WARNING", "MODERATE", "NEUTRAL"]):
        return "fx-warning"
    return "fx-muted"


def _metric_card(title: str, value, subtitle: str = "", mood="", progress: float | None = None) -> None:
    """Copied from forex_terminal_dashboard.py -- see _class_for's docstring for why."""
    bar = ""
    if progress is not None:
        pct = max(0, min(100, float(progress or 0)))
        bar = f'<div class="fx-bar"><div class="fx-fill" style="width:{pct}%"></div></div>'
    st.markdown(
        f'<div class="fx-card"><div class="fx-title">{title}</div>'
        f'<div class="fx-value {_class_for(mood)}">{value}</div>'
        f'<div class="fx-sub">{subtitle}</div>{bar}</div>',
        unsafe_allow_html=True,
    )


def _currency_flag(code: str) -> str:
    """Copied from forex_terminal_dashboard.py -- see _class_for's docstring for why."""
    return {
        "USD": "🇺🇸", "EUR": "🇪🇺", "JPY": "🇯🇵", "GBP": "🇬🇧",
        "CHF": "🇨🇭", "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿",
    }.get(str(code or "").upper(), "🌐")


def _inject_terminal_css() -> None:
    """
    Copied from forex_terminal_dashboard.py's _inject_terminal_css --
    see _class_for's docstring for why this is copied rather than
    imported. Byte-for-byte the same CSS, so this visually matches the
    original terminal exactly.
    """
    st.markdown("""
<style>
.fx-card{background:linear-gradient(180deg,rgba(14,31,49,.96),rgba(5,14,25,.98));border:1px solid rgba(0,218,255,.22);border-radius:12px;padding:14px 16px;box-shadow:0 0 0 1px rgba(255,255,255,.025) inset,0 8px 24px rgba(0,0,0,.22);min-height:96px}.fx-panel{background:linear-gradient(180deg,rgba(14,31,49,.96),rgba(5,14,25,.98));border:1px solid rgba(0,218,255,.18);border-radius:12px;padding:13px;margin-bottom:10px}.fx-title{font-size:.74rem;color:#9fb5ca;text-transform:uppercase;letter-spacing:.07em;margin-bottom:4px;font-weight:700}.fx-value{color:#f5f9ff;font-weight:850;font-size:1.42rem;line-height:1.1}.fx-sub{color:#9fb5ca;font-size:.78rem;margin-top:4px}.fx-positive{color:#2fe278!important}.fx-negative{color:#ff5264!important}.fx-warning{color:#ffb020!important}.fx-muted{color:#9fb5ca!important}.fx-bar{width:100%;height:8px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:8px}.fx-fill{height:8px;border-radius:999px;background:linear-gradient(90deg,#00d2ff,#30e07a)}.fx-section{display:flex;justify-content:space-between;align-items:center;color:#c9d7e8;font-weight:800;font-size:.88rem;margin-bottom:10px}.fx-chip{padding:2px 8px;border-radius:999px;background:rgba(0,208,255,.10);border:1px solid rgba(0,208,255,.25);color:#bfefff;font-size:.70rem;font-weight:700}div[data-testid="stMetricValue"]{font-size:1.2rem}
</style>""", unsafe_allow_html=True)


def render_forex_terminal_v2(db=None, user=None, **kwargs):
    if st is None:
        return {"status": "streamlit_not_available"}

    render_start = time.perf_counter()

    tenant_id = (user or {}).get("tenant_id") if isinstance(user, dict) else None
    user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
    portfolio_id = (user or {}).get("portfolio_id") if isinstance(user, dict) else None
    portfolio_id = _resolve_portfolio_id(db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id)

    _inject_terminal_css()

    st.markdown(
        '<div class="fx-panel">'
        '<div style="font-size:1.1rem;font-weight:800;color:#f5f9ff;">🌍 Forex Institutional Terminal (v2 rebuild)</div>'
        '<div class="fx-sub">Real-Time Market Intelligence · Portfolio Management · AI Decision Support</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Visual match to the original terminal. All 8 KPI tiles now show real, "
        "individually-verified data -- see each tile's underlying code for the caveats "
        "faithfully carried over from the original (e.g. Daily P&L is really unrealized "
        "P&L under a different label, same as the original)."
    )

    portfolios = _timed_section(
        "portfolio_list",
        _get_throttled_portfolio_list,
        db, tenant_id=tenant_id,
    )

    if portfolios:
        portfolio_ids = [p.get("id") for p in portfolios]
        portfolio_labels = {p.get("id"): p.get("name") or p.get("id") for p in portfolios}

        selected_key = f"fx_v2_selected_portfolio_id:{tenant_id}"

        # Default to the auto-resolved active portfolio on first load,
        # but only if it's actually in the list and nothing has been
        # explicitly selected yet -- otherwise fall back to the first
        # portfolio, and always let the user's own prior selection win
        # once one has been made.
        if selected_key not in st.session_state:
            st.session_state[selected_key] = (
                portfolio_id if portfolio_id in portfolio_ids else portfolio_ids[0]
            )

        selected_portfolio_id = st.selectbox(
            "Portfolio",
            options=portfolio_ids,
            format_func=lambda pid: portfolio_labels.get(pid, pid),
            key=selected_key,
        )

        portfolio_id = selected_portfolio_id
    else:
        st.info(
            "No portfolios found for this tenant -- showing whatever the system "
            "auto-resolved, if anything."
        )

    counts = _timed_section(
        "position_counts",
        _get_throttled_account_summary,
        db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
    )

    strength_for_kpis = _timed_section(
        "currency_strength_kpi",
        _get_throttled_currency_strength,
    )

    regime_data = _timed_section(
        "market_regime",
        _get_throttled_market_regime,
    )

    ai_confidence_data = _timed_section(
        "ai_confidence",
        _get_throttled_ai_confidence,
    )

    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        if regime_data.get("error"):
            _metric_card("Market Regime", "\u2014", "Not available", "", None)
        else:
            regime_label = str(regime_data.get("macro_regime", "UNKNOWN")).replace("_", "-")
            macro_score = regime_data.get("macro_score")
            _metric_card(
                "Market Regime",
                regime_label,
                f"Macro Score: {macro_score:.0f}/100" if macro_score is not None else "Macro Score: \u2014",
                regime_label,
                macro_score,
            )

    with kpi_cols[1]:
        strongest = strength_for_kpis.get("strongest_currency") if not strength_for_kpis.get("error") else None
        if strongest:
            code = strongest.get("currency", "")
            _metric_card(
                "Strongest Currency",
                f"{_currency_flag(code)} {code}",
                "Strength leader",
                "BUY",
                strongest.get("strength_score"),
            )
        else:
            _metric_card("Strongest Currency", "\u2014", "Not available", "", None)

    with kpi_cols[2]:
        weakest = strength_for_kpis.get("weakest_currency") if not strength_for_kpis.get("error") else None
        if weakest:
            code = weakest.get("currency", "")
            _metric_card(
                "Weakest Currency",
                f"{_currency_flag(code)} {code}",
                "Weakness leader",
                "SELL",
                weakest.get("strength_score"),
            )
        else:
            _metric_card("Weakest Currency", "\u2014", "Not available", "", None)

    with kpi_cols[3]:
        if ai_confidence_data.get("error") or ai_confidence_data.get("ai_confidence") is None:
            _metric_card("AI Confidence", "\u2014", "Not available", "", None)
        else:
            conf = ai_confidence_data["ai_confidence"]
            _metric_card(
                "AI Confidence",
                f"{conf:.0f}%",
                "Model consensus",
                "HIGH",
                conf,
            )

    kpi_cols_2 = st.columns(4)

    with kpi_cols_2[0]:
        _metric_card("Open Positions", counts["open_positions"], "Active exposure", "", None)

    with kpi_cols_2[1]:
        # Daily P&L: confirmed directly against forex_terminal_dashboard.py
        # that its own "daily_pnl" is really just unrealized_pnl under a
        # different label (portfolio_summary() never actually populates a
        # dedicated daily_pnl key, so the original's fallback chain --
        # daily_pnl or unrealized_pnl or pnl -- always resolves to
        # unrealized_pnl in practice). Reuses the same already-throttled
        # value from the KPI row above rather than fetching anything new.
        # daily_pnl_pct has no real source in the original either (always
        # effectively +0.00%), and its progress bar value is hardcoded to
        # 78 regardless of the actual number -- both faithfully replicated
        # as-is, since the goal here is exact parity, not a corrected
        # version of the original's own limitation.
        daily_pnl = counts.get("unrealized_pnl")
        if daily_pnl is None:
            _metric_card("Daily P&L", "\u2014", "Not available", "", None)
        else:
            sign = "+" if daily_pnl >= 0 else "-"
            _metric_card(
                "Daily P&L",
                f"{sign}${abs(daily_pnl):,.2f}",
                "+0.00%",
                "BUY" if daily_pnl >= 0 else "SELL",
                78,
            )

    with kpi_cols_2[2]:
        equity = counts["equity"]
        _metric_card("Equity", f"${equity:,.2f}" if equity is not None else "\u2014", "Portfolio value", "", None)

    with kpi_cols_2[3]:
        now = datetime.now(timezone.utc)
        _metric_card("Server Time (UTC)", now.strftime("%H:%M:%S"), now.strftime("%b %d, %Y"), "", None)

    st.divider()

    workspace = st.radio("Workspace", WORKSPACE_TABS, horizontal=True, key="fx_v2_workspace")

    if workspace == "Overview":
        st.caption(
            f"Currency strength scan, throttled to at most one real fetch "
            f"every {STRENGTH_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_strength = st.button("🔄 Refresh now", key="fx_v2_force_refresh_strength")

        strength = _timed_section(
            "currency_strength",
            _get_throttled_currency_strength,
            force=force_refresh_strength,
        )

        if strength.get("error"):
            st.error(f"Could not get currency strength: {strength['error']}")
        else:
            strongest = strength.get("strongest_currency")
            weakest = strength.get("weakest_currency")

            regime_cols = st.columns(2)

            with regime_cols[0]:
                if strongest:
                    st.metric(
                        "Strongest Currency",
                        strongest.get("currency", "—"),
                        delta=f"Score: {strongest.get('strength_score', '—')}",
                    )
                else:
                    st.metric("Strongest Currency", "—")

            with regime_cols[1]:
                if weakest:
                    st.metric(
                        "Weakest Currency",
                        weakest.get("currency", "—"),
                        delta=f"Score: {weakest.get('strength_score', '—')}",
                    )
                else:
                    st.metric("Weakest Currency", "—")

            cache_note = (
                f"cached, {strength['_cache_age_seconds']:.0f}s old"
                if strength.get("_from_cache")
                else "just fetched"
            )
            st.caption(f"Quote health: {strength.get('quote_health', {})} · {cache_note}")

    elif workspace == "Positions":
        positions = _timed_section(
            "position_list",
            _get_positions_for_display,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        if not positions:
            st.info("No open positions for this portfolio.")
        else:
            display_rows = [
                {
                    "Pair": p["pair"],
                    "Side": p["side"],
                    "Units": f"{p['units']:,.0f}",
                    "Avg Entry": f"{p['avg_price']:.5f}" if p.get("avg_price") is not None else "—",
                    "Current": f"{p['current_price']:.5f}" if p.get("current_price") is not None else "—",
                    "Unrealized P&L": f"{p['unrealized_pnl']:,.2f}" if p.get("unrealized_pnl") is not None else "—",
                }
                for p in positions
            ]
            st.dataframe(display_rows, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("**Close Position**")
            st.caption(
                "Closes at the current live market price -- this makes one real "
                "quote fetch when you click Close, separate from the throttled "
                "quotes used elsewhere on this page."
            )

            position_labels = {
                p["id"]: f"{p['pair']} | {p['side']} | {p['units']:,.0f} units"
                for p in positions
            }
            close_cols = st.columns([3, 1])
            with close_cols[0]:
                selected_close_id = st.selectbox(
                    "Position to close",
                    options=list(position_labels.keys()),
                    format_func=lambda pid: position_labels.get(pid, pid),
                    key="fx_v2_close_position_select",
                )
            with close_cols[1]:
                st.write("")
                confirm_close = st.button("Close Selected Position", key="fx_v2_close_position_btn")

            if confirm_close:
                close_result = _close_position(
                    db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                    position_id=selected_close_id, close_price=None,
                )
                if close_result.get("status") == "ok":
                    closed = close_result["position"]
                    st.success(f"Closed {closed.pair} · realized P&L: {closed.realized_pnl:,.2f}")
                else:
                    st.error(f"Could not close position: {close_result.get('message')}")
    elif workspace == "Orders":
        orders = _timed_section(
            "order_list",
            _get_orders_for_display,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        def _order_rows(order_list):
            return [
                {
                    "Pair": o.get("pair") or o.get("symbol") or "\u2014",
                    "Side": o.get("side") or "\u2014",
                    "Type": o.get("order_type") or "\u2014",
                    "Status": o.get("status") or "\u2014",
                    "Units": f"{o['units']:,.0f}" if o.get("units") is not None else "\u2014",
                    "Requested Price": f"{o['requested_price']:.5f}" if o.get("requested_price") is not None else "\u2014",
                    "Fill Price": f"{o['avg_fill_price']:.5f}" if o.get("avg_fill_price") is not None else "\u2014",
                    "Created": str(o.get("created_at") or "\u2014"),
                }
                for o in order_list
            ]

        st.markdown("**Open Orders**")
        open_orders = orders.get("open") or []
        if not open_orders:
            st.info("No open orders for this portfolio.")
        else:
            st.dataframe(_order_rows(open_orders), use_container_width=True, hide_index=True)

        st.markdown("**Filled Orders**")
        filled_orders = orders.get("filled") or []
        if not filled_orders:
            st.info("No filled orders for this portfolio.")
        else:
            st.dataframe(_order_rows(filled_orders), use_container_width=True, hide_index=True)

    elif workspace == "Risk":
        st.caption(
            f"Institutional risk summary, throttled to at most one real "
            f"computation every {RISK_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_risk = st.button("🔄 Refresh now", key="fx_v2_force_refresh_risk")

        risk = _timed_section(
            "risk_summary",
            _get_throttled_risk_summary,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, force=force_refresh_risk,
        )

        if risk.get("status") != "READY":
            st.info(risk.get("message", "Risk summary not available."))
        else:
            risk_cols = st.columns(4)

            with risk_cols[0]:
                st.metric("Daily VaR (95%)", f"${risk.get('daily_var', 0.0):,.2f}")

            with risk_cols[1]:
                st.metric("Expected Shortfall", f"${risk.get('expected_shortfall_value', 0.0):,.2f}")

            with risk_cols[2]:
                st.metric("Gross Exposure", f"${risk.get('gross_exposure', 0.0):,.2f}")

            with risk_cols[3]:
                st.metric("Net Exposure", f"${risk.get('net_exposure', 0.0):,.2f}")

            directional = risk.get("directional") or {}
            st.caption(
                f"Directional: long ${directional.get('long', 0.0):,.2f} · "
                f"short ${directional.get('short', 0.0):,.2f} · "
                f"net ${directional.get('net', 0.0):,.2f}"
            )

            inst_score = risk.get("institutional_risk_score")
            if inst_score is not None:
                st.caption(f"Institutional risk score: {inst_score:.1f}/100")
            for warning_text in risk.get("institutional_warnings") or []:
                st.warning(warning_text)

            st.divider()
            st.markdown("**Stress Testing**")
            stress_tests = risk.get("stress_tests") or []
            if stress_tests:
                st.dataframe(stress_tests, use_container_width=True, hide_index=True)
            else:
                st.info("No stress tests available.")

            st.divider()
            st.markdown("**Risk Heat Map**")
            pair_exposure = risk.get("pair_exposure") or []
            if pair_exposure:
                chart_rows = {r["pair"]: r.get("gross_notional", 0.0) for r in pair_exposure if r.get("pair")}
                st.bar_chart(chart_rows)
            else:
                st.info("No exposure data available.")

            cache_note = (
                f"cached, {risk['_cache_age_seconds']:.0f}s old"
                if risk.get("_from_cache")
                else "just computed"
            )
            st.caption(cache_note)

    elif workspace == "Performance":
        st.caption(
            f"Performance statistics, throttled to at most one real "
            f"computation every {PERFORMANCE_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_perf = st.button("🔄 Refresh now", key="fx_v2_force_refresh_performance")

        perf = _timed_section(
            "performance_summary",
            _get_throttled_performance_summary,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, force=force_refresh_perf,
        )

        if perf.get("status") != "READY":
            st.info(perf.get("message", "Performance summary not available."))
        else:
            perf_cols = st.columns(4)

            with perf_cols[0]:
                st.metric("Win Rate", f"{perf.get('win_rate', 0.0):.1f}%")

            with perf_cols[1]:
                st.metric("Profit Factor", f"{perf.get('profit_factor', 0.0):.2f}")

            with perf_cols[2]:
                st.metric("Total Realized P&L", f"${perf.get('total_realized_pnl', 0.0):,.2f}")

            with perf_cols[3]:
                st.metric("Total Unrealized P&L", f"${perf.get('total_unrealized_pnl', 0.0):,.2f}")

            perf_cols_2 = st.columns(4)

            with perf_cols_2[0]:
                st.metric("Trade Count", perf.get("trade_count", 0))

            with perf_cols_2[1]:
                st.metric("Largest Win", f"${perf.get('largest_win', 0.0):,.2f}")

            with perf_cols_2[2]:
                st.metric("Largest Loss", f"${perf.get('largest_loss', 0.0):,.2f}")

            with perf_cols_2[3]:
                st.metric("Expectancy", f"${perf.get('expectancy', 0.0):,.2f}")

            cache_note = (
                f"cached, {perf['_cache_age_seconds']:.0f}s old"
                if perf.get("_from_cache")
                else "just computed"
            )
            st.caption(cache_note)

    elif workspace == "Journal":
        with st.form("fx_v2_journal_new_entry", clear_on_submit=True):
            st.markdown("**Log New Trade**")

            form_cols = st.columns(3)
            with form_cols[0]:
                new_pair = st.text_input("Pair", value="EUR/USD")
            with form_cols[1]:
                new_side = st.selectbox("Side", options=["BUY", "SELL"])
            with form_cols[2]:
                new_setup = st.text_input("Setup", placeholder="e.g. Breakout")

            new_thesis = st.text_area("Thesis", placeholder="Why this trade?")

            form_cols_2 = st.columns(3)
            with form_cols_2[0]:
                new_entry_price = st.number_input("Entry Price", min_value=0.0, format="%.5f")
            with form_cols_2[1]:
                new_units = st.number_input("Units", min_value=0.0, step=1000.0)
            with form_cols_2[2]:
                new_emotion = st.text_input("Emotion", placeholder="e.g. Confident")

            submitted = st.form_submit_button("Log Entry")

            if submitted:
                create_result = _create_journal_entry(
                    db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                    pair=new_pair, side=new_side, setup=new_setup, thesis=new_thesis,
                    entry_price=new_entry_price or None, units=new_units or None,
                    emotion=new_emotion or None,
                )
                if create_result.get("status") == "ok":
                    st.success(f"Logged entry #{create_result.get('id')}.")
                else:
                    st.error(f"Could not log entry: {create_result.get('message')}")

        st.divider()

        entries = _timed_section(
            "journal_entries",
            _get_journal_entries,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )

        if not entries:
            st.info("No journal entries for this portfolio.")
        else:
            display_rows = [
                {
                    "Pair": e.get("pair") or "\u2014",
                    "Side": e.get("side") or "\u2014",
                    "Setup": e.get("setup") or "\u2014",
                    "Entry": f"{e['entry_price']:.5f}" if e.get("entry_price") is not None else "\u2014",
                    "Exit": f"{e['exit_price']:.5f}" if e.get("exit_price") is not None else "\u2014",
                    "P&L": f"{e['pnl']:,.2f}" if e.get("pnl") is not None else "\u2014",
                    "Outcome": e.get("outcome") or "\u2014",
                    "Created": str(e.get("created_at") or "\u2014"),
                }
                for e in entries
            ]
            st.dataframe(display_rows, use_container_width=True, hide_index=True)

            with st.expander("View thesis / lesson notes"):
                for e in entries:
                    st.markdown(f"**{e.get('pair', '—')} · {e.get('created_at', '')}**")
                    if e.get("thesis"):
                        st.caption(f"Thesis: {e['thesis']}")
                    if e.get("lesson"):
                        st.caption(f"Lesson: {e['lesson']}")
                    st.divider()

    elif workspace == "AI Briefing":
        st.caption(
            f"Full daily AI briefing (strategy, portfolio plan, sentiment), "
            f"throttled to at most one real computation every "
            f"{AI_BRIEFING_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_briefing = st.button("🔄 Refresh now", key="fx_v2_force_refresh_briefing")

        briefing = _timed_section(
            "ai_briefing",
            _get_throttled_ai_briefing,
            force=force_refresh_briefing,
        )

        if briefing.get("error"):
            st.error(f"Could not get AI briefing: {briefing['error']}")
        else:
            portfolio_plan = briefing.get("portfolio_plan") or {}
            trade_plan = (briefing.get("strategy_lab") or {}).get("trade_plan") or {}

            st.markdown("**Portfolio Plan**")
            plan_cols = st.columns(3)
            with plan_cols[0]:
                st.metric("Signals Considered", portfolio_plan.get("signals_considered", 0))
            with plan_cols[1]:
                st.metric("Selected Positions", portfolio_plan.get("selected_positions", 0))
            with plan_cols[2]:
                st.metric("Account Size", f"${portfolio_plan.get('account_size', 0):,.0f}")

            allocations = portfolio_plan.get("allocations") or []
            if allocations:
                alloc_rows = [
                    {
                        "Pair": a.get("pair") or "\u2014",
                        "Direction": a.get("direction") or "\u2014",
                        "Recommendation": a.get("recommendation") or "\u2014",
                        "Target Weight": f"{a['target_weight']:.1f}%" if a.get("target_weight") is not None else "\u2014",
                        "Target Notional": f"${a['target_notional']:,.2f}" if a.get("target_notional") is not None else "\u2014",
                        "Entry": f"{a['entry_price']:.5f}" if a.get("entry_price") is not None else "\u2014",
                        "Stop": f"{a['stop_price']:.5f}" if a.get("stop_price") is not None else "\u2014",
                        "Target": f"{a['target_price']:.5f}" if a.get("target_price") is not None else "\u2014",
                    }
                    for a in allocations
                ]
                st.dataframe(alloc_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No allocations suggested right now.")

            st.divider()
            st.markdown("**Trade Plan Summary**")
            plan_cols_2 = st.columns(2)
            with plan_cols_2[0]:
                st.metric("Macro Regime", str(trade_plan.get("macro_regime") or "\u2014").replace("_", "-"))
            with plan_cols_2[1]:
                st.metric("Sentiment", trade_plan.get("sentiment") or "\u2014")

            cache_note = (
                f"cached, {briefing['_cache_age_seconds']:.0f}s old"
                if briefing.get("_from_cache")
                else "just computed"
            )
            st.caption(cache_note)

    elif workspace == "AI Trade Setup":
        st.caption(
            "Generates a real AI trade recommendation, then lets you execute "
            "it as a market order. Each step -- Analyze and Execute -- makes "
            "its own real live quote fetch; neither is throttled, since both "
            "only run on an explicit button click."
        )

        st.markdown("**AI Trade Recommendations**")
        st.caption(
            f"Live alpha-model scan across all watched pairs, throttled to "
            f"at most one real computation every {AI_CONFIDENCE_THROTTLE_SECONDS:.0f} seconds."
        )
        ai_conf_data = _timed_section("ai_recommendations", _get_throttled_ai_confidence)
        top_recommendations = (ai_conf_data.get("recommendations") or [])[:4]

        if ai_conf_data.get("error"):
            st.info(f"Recommendations unavailable: {ai_conf_data['error']}")
        elif not top_recommendations:
            st.info("No live recommendations yet.")
        else:
            rec_cols = st.columns(len(top_recommendations))
            for i, rec in enumerate(top_recommendations):
                with rec_cols[i]:
                    side = rec.get("side", "WATCH")
                    color = "🟢" if side == "BUY" else "🔴" if side == "SELL" else "🟡"
                    st.markdown(f"{color} **{side} {rec.get('pair', '-')}**")
                    st.caption(f"Confidence: {rec.get('confidence', 0):.0f}%")
                    st.caption(f"Entry: {rec.get('entry') or '-'}")
                    st.caption(f"Target: {rec.get('target') or '-'}")
                    st.caption(f"Stop: {rec.get('stop') or '-'}")
                    st.caption(f"Bias: {rec.get('bias', '-')} | RR: {rec.get('risk_reward') or '-'}")

        st.divider()
        st.markdown(f"**Alerts** ({len(top_recommendations[:3])})")
        alerts = [
            {
                "Time": datetime.now(timezone.utc).strftime("%H:%M"),
                "Alert": f"{rec.get('pair')} {rec.get('side')} setup confidence {rec.get('confidence', 0):.0f}%",
                "Severity": "High" if (rec.get("confidence") or 0) >= 85 else "Medium",
            }
            for rec in top_recommendations[:3]
        ]
        if alerts:
            st.dataframe(alerts, use_container_width=True, hide_index=True)
        else:
            st.info("No alerts yet.")

        st.divider()

        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        from modules.forex.forex_currency_strength_engine import MAJOR_AND_CROSS_PAIRS

        engine = get_forex_portfolio_engine(
            db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
        )
        account = engine.get_account(portfolio_id=portfolio_id)

        if account is None:
            st.error("No Forex account is available for this portfolio yet.")
        else:
            acct_cols = st.columns(4)
            with acct_cols[0]:
                st.metric("Cash", f"${account.cash_balance:,.2f}")
            with acct_cols[1]:
                st.metric("Equity", f"${account.equity:,.2f}")
            with acct_cols[2]:
                st.metric("Buying Power", f"${account.margin_available:,.2f}")
            with acct_cols[3]:
                st.metric("Leverage", f"{account.leverage:.1f}x")

            st.divider()

            setup_cols = st.columns(2)
            with setup_cols[0]:
                trade_pair = st.selectbox(
                    "Currency Pair", options=MAJOR_AND_CROSS_PAIRS, key="fx_v2_ai_trade_pair",
                )
            with setup_cols[1]:
                risk_pct = st.select_slider(
                    "Risk Per Trade", options=[0.25, 0.50, 1.00, 2.00], value=1.00,
                    format_func=lambda v: f"{v:.2f}%", key="fx_v2_ai_trade_risk_pct",
                )

            analyze_clicked = st.button("Analyze Trade", key="fx_v2_ai_trade_analyze")

            if analyze_clicked:
                rec_result = _get_ai_trade_recommendation(
                    db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                    account_id=account.id, pair=trade_pair, risk_pct=float(risk_pct),
                )
                if rec_result.get("status") == "ok":
                    st.session_state["fx_v2_ai_trade_recommendation"] = rec_result["recommendation"]
                else:
                    st.session_state.pop("fx_v2_ai_trade_recommendation", None)
                    st.error(rec_result.get("message"))

            recommendation = st.session_state.get("fx_v2_ai_trade_recommendation")

            if recommendation:
                st.divider()
                st.markdown("**AI Recommendation**")

                signal = recommendation.get("signal") or {}
                sizing = recommendation.get("sizing") or {}
                recommended_side = recommendation.get("recommended_side")
                can_open = recommendation.get("can_open_position", False)

                rec_cols = st.columns(3)
                with rec_cols[0]:
                    st.metric("Recommendation", signal.get("recommendation", "-"))
                    st.metric("Recommended Side", recommended_side or "-")
                    st.metric("Confidence", f"{float(signal.get('confidence', 0) or 0):.1f}%")
                with rec_cols[1]:
                    st.metric("Entry", signal.get("entry_price", "-"))
                    st.metric("Stop", signal.get("stop_price", "-"))
                    st.metric("Risk / Reward", signal.get("risk_reward", "-"))
                with rec_cols[2]:
                    st.metric("Target", signal.get("target_price", "-"))
                    st.metric("Units", f"{float(sizing.get('suggested_units', 0) or 0):,.0f}")
                    st.metric("Margin Required", f"${float(sizing.get('margin_required', 0) or 0):,.2f}")

                rationale = signal.get("rationale")
                if rationale:
                    st.markdown("**AI Rationale**")
                    st.write(rationale)

                warnings = signal.get("warnings")
                if warnings:
                    st.warning(warnings)

                if can_open:
                    st.success("AI trade is eligible for execution.")

                    if st.button("Execute AI Trade", key="fx_v2_ai_trade_execute"):
                        exec_result = _execute_ai_trade(
                            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                            account_id=account.id, pair=signal.get("pair"), side=recommended_side,
                            units=float(sizing.get("suggested_units") or 0.0),
                            stop_price=signal.get("stop_price"), target_price=signal.get("target_price"),
                        )
                        if exec_result.get("status") == "ok":
                            st.session_state.pop("fx_v2_ai_trade_recommendation", None)
                            st.success(f"Trade executed: {exec_result['result'].get('status', 'FILLED')}.")
                        else:
                            st.error(f"Could not execute trade: {exec_result.get('message')}")
                else:
                    st.warning("AI does not recommend opening this position.")

    elif workspace == "AI Command Center":
        st.caption(
            f"AI executive summary and multi-model consensus, throttled to at "
            f"most one real computation every {AI_EXECUTIVE_THROTTLE_SECONDS:.0f} seconds. "
            f"Building this pulls in several AI/quant engines and can be slower "
            f"than other tabs."
        )

        force_refresh_exec = st.button("🔄 Refresh now", key="fx_v2_force_refresh_ai_executive")

        exec_result = _timed_section(
            "ai_executive",
            _get_throttled_ai_executive,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, force=force_refresh_exec,
        )

        if exec_result.get("status") != "READY":
            st.info(exec_result.get("message", "AI executive summary not available."))
        else:
            data = exec_result.get("data") or {}
            consensus = exec_result.get("consensus") or {}
            rec = data.get("recommendation") or {}
            regime = data.get("regime") or {}
            summary = data.get("summary") or {}

            st.markdown("**Global Market Regime**")
            regime_cols = st.columns(4)
            with regime_cols[0]:
                st.metric("Regime", regime.get("regime", "Unknown"))
            with regime_cols[1]:
                st.metric("Liquidity", regime.get("liquidity", "Unknown"))
            with regime_cols[2]:
                st.metric("Macro Score", f"{regime.get('macro_score', 0):.0f}")
            with regime_cols[3]:
                st.metric("Consensus", f"{consensus.get('weighted_confidence', 0):.0f}%")

            st.divider()
            st.markdown("**Institutional AI Recommendation**")
            rec_cols = st.columns(4)
            with rec_cols[0]:
                st.metric("Signal", f"{rec.get('signal', 'WATCH')} {rec.get('pair', 'N/A')}")
            with rec_cols[1]:
                st.metric("Confidence", f"{rec.get('confidence', 0):.0f}%")
            with rec_cols[2]:
                st.metric("Grade", rec.get("grade", "-"))
            with rec_cols[3]:
                st.metric("Risk / Reward", f"{rec.get('risk_reward', 0):.2f}")

            st.caption(
                f"Consensus: {consensus.get('active_models', 0)}/{consensus.get('total_models', 0)} "
                f"active models · agreement {consensus.get('agreement_score', 0):.0f}% · "
                f"decision {consensus.get('executive_decision', 'WATCH')} {consensus.get('top_pair', 'N/A')}"
            )

            st.divider()
            st.markdown("**Top Opportunities**")
            opportunities = data.get("opportunities") or []
            if opportunities:
                st.dataframe(opportunities[:15], use_container_width=True, hide_index=True)
            else:
                st.info("No scored opportunity rows available.")

            st.divider()
            st.markdown("**Model Votes**")
            votes = consensus.get("votes") or []
            if votes:
                st.dataframe(votes, use_container_width=True, hide_index=True)
            else:
                st.info("No model votes available.")

            st.divider()
            st.markdown("**Autonomous Trading Cycle**")
            st.warning(
                "Clicking this immediately picks the top-ranked qualifying "
                "trade and executes it as a real market order -- there is no "
                "preview step. This matches the original terminal's own "
                "behavior exactly."
            )
            if st.button("▶️ Run Autonomous Cycle", key="fx_v2_run_autonomous_cycle"):
                from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine as _get_pe

                account_for_cycle = _get_pe(
                    db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                ).get_account(portfolio_id=portfolio_id)

                if account_for_cycle is None:
                    st.error("No Forex account is available for this portfolio yet.")
                else:
                    cycle_result = _run_autonomous_cycle(
                        db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                        account_id=account_for_cycle.id,
                    )
                    cycle_status = cycle_result.get("status")
                    if cycle_status == "executed":
                        trade = cycle_result.get("trade")
                        trade_status = getattr(trade, "status", None) or (trade or {}).get("status", "FILLED")
                        st.session_state.pop(f"fx_v2_ai_executive_cache:{portfolio_id}", None)
                        st.success(f"Autonomous cycle executed a trade: {trade_status}.")
                    elif cycle_status == "blocked":
                        st.warning(f"Blocked by risk controls: {cycle_result.get('reason')}")
                    elif cycle_status == "idle":
                        st.info(cycle_result.get("reason", "No qualifying trade opportunities."))
                    else:
                        st.error(f"Autonomous cycle did not execute: {cycle_result.get('message')}")

            cache_note = (
                f"cached, {exec_result['_cache_age_seconds']:.0f}s old"
                if exec_result.get("_from_cache")
                else "just computed"
            )
            st.caption(cache_note)

    elif workspace == "Live Market":
        from modules.forex.forex_currency_strength_engine import MAJOR_AND_CROSS_PAIRS

        strength_cols = st.columns(2)
        with strength_cols[0]:
            st.markdown("**Currency Strength**")
            strength_data = _timed_section("currency_strength_live", _get_throttled_currency_strength)
            if strength_data.get("error"):
                st.info(f"Currency strength unavailable: {strength_data['error']}")
            else:
                for row in strength_data.get("currency_strength") or []:
                    score = row.get("strength_score") or 0.0
                    ccy_cols = st.columns([1, 4, 1])
                    with ccy_cols[0]:
                        st.write(f"**{row.get('currency')}**")
                    with ccy_cols[1]:
                        st.progress(min(max(score / 100.0, 0.0), 1.0))
                    with ccy_cols[2]:
                        st.write(f"{score:.0f}")

        with strength_cols[1]:
            st.markdown("**Macro Environment**")
            regime_data = _timed_section("market_regime_live", _get_throttled_market_regime)
            if regime_data.get("error"):
                st.info(f"Macro environment unavailable: {regime_data['error']}")
            else:
                regime_name = regime_data.get("macro_regime", "UNKNOWN")
                st.markdown(f"Regime: **{regime_name.replace('_', '-')}**")
                st.progress(min(max((regime_data.get("macro_score") or 0.0) / 100.0, 0.0), 1.0))
                st.caption(f"Macro Score: {regime_data.get('macro_score', 0):.0f} / 100")
                risk_appetite = (
                    "Low" if regime_name == "RISK_OFF"
                    else "High" if regime_name == "RISK_ON"
                    else "Moderate"
                )
                st.caption(f"Risk Appetite: {risk_appetite}")
                st.caption(f"Liquidity: {regime_data.get('summary', {}).get('liquidity', 'Unknown')}")

        st.divider()
        st.markdown("**Live Chart**")
        chart_pair = st.selectbox(
            "Chart Pair", options=MAJOR_AND_CROSS_PAIRS, key="fx_v2_chart_pair",
        )
        force_refresh_chart = st.button("🔄 Refresh chart", key="fx_v2_force_refresh_chart")
        chart_result = _timed_section(
            "price_chart", _get_throttled_price_chart, chart_pair, force=force_refresh_chart,
        )
        if chart_result.get("error"):
            st.info(chart_result["error"])
        elif chart_result.get("figure") is not None:
            st.plotly_chart(chart_result["figure"], use_container_width=True)
            chart_cache_note = (
                f"cached, {chart_result['_cache_age_seconds']:.0f}s old"
                if chart_result.get("_from_cache")
                else "just fetched"
            )
            st.caption(chart_cache_note)

        st.divider()
        st.markdown("**Trade Ticket**")
        st.caption("paper -- submits a real market order for the pair shown in the chart above.")

        ticket_cols = st.columns(2)
        with ticket_cols[0]:
            ticket_side = st.radio("Side", ["Buy", "Sell"], horizontal=True, key="fx_v2_ticket_side")
            ticket_lots = st.number_input(
                "Size (Lots)", min_value=0.01, value=1.00, step=0.01, key="fx_v2_ticket_lots",
            )
            ticket_risk = st.number_input(
                "Risk %", min_value=0.1, value=1.0, step=0.1, key="fx_v2_ticket_risk",
            )
        with ticket_cols[1]:
            ticket_stop = st.text_input("Stop Loss", value="", key="fx_v2_ticket_stop")
            ticket_target = st.text_input("Take Profit", value="", key="fx_v2_ticket_target")

        if st.button(f"{ticket_side} {ticket_lots:.2f} {chart_pair}", key="fx_v2_ticket_submit"):
            from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine as _get_pe_ticket

            ticket_account = _get_pe_ticket(
                db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
            ).get_account(portfolio_id=portfolio_id)

            if ticket_account is None:
                st.error("No Forex account is available for this portfolio yet.")
            else:
                try:
                    stop_val = float(ticket_stop) if ticket_stop else None
                    target_val = float(ticket_target) if ticket_target else None
                except ValueError:
                    stop_val = target_val = None
                    st.error("Stop Loss and Take Profit must be numbers, e.g. 1.06800.")
                else:
                    ticket_result = _execute_ai_trade(
                        db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
                        account_id=ticket_account.id, pair=chart_pair, side=ticket_side.upper(),
                        units=ticket_lots * 100000, stop_price=stop_val, target_price=target_val,
                    )
                    if ticket_result.get("status") == "ok":
                        order_status = getattr(ticket_result["result"], "status", None) or ticket_result["result"].get("status", "FILLED")
                        st.success(f"Order submitted: {order_status}.")
                    else:
                        st.error(f"Order failed: {ticket_result.get('message')}")

        st.caption("Estimated margin and pip value depend on broker configuration.")

        st.divider()
        calendar_cols = st.columns(2)
        with calendar_cols[0]:
            st.markdown("**Economic Calendar**")
            calendar_data = _timed_section("economic_calendar", _get_throttled_economic_calendar)
            if calendar_data.get("error"):
                st.info(f"Calendar unavailable: {calendar_data['error']}")
            elif calendar_data.get("rows"):
                st.dataframe(calendar_data["rows"], use_container_width=True, hide_index=True)
            else:
                st.info(calendar_data.get("coverage_note") or "No upcoming releases available.")

        with calendar_cols[1]:
            st.markdown("**Central Bank Events**")
            cb_data = _timed_section("central_bank_events", _get_throttled_central_bank_events)
            if cb_data.get("error"):
                st.info(f"Central bank data unavailable: {cb_data['error']}")
            elif cb_data.get("rows"):
                st.dataframe(cb_data["rows"], use_container_width=True, hide_index=True)
            else:
                st.info("No central bank data available.")

        st.divider()
        st.caption(
            f"Live quotes for every watchlist pair, throttled to at most one "
            f"real fetch every {LIVE_MARKET_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_market = st.button("🔄 Refresh now", key="fx_v2_force_refresh_live_market")

        live_market = _timed_section(
            "live_market",
            _get_throttled_live_market,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
            force=force_refresh_market,
        )

        if live_market.get("error"):
            st.error(f"Could not get live market quotes: {live_market['error']}")
        elif not live_market.get("quotes"):
            st.info("No pairs on the watchlist yet.")
        else:
            display_rows = [
                {
                    "Pair": q.get("pair") or "\u2014",
                    "Bid": f"{q['bid']:.5f}" if q.get("bid") is not None else "\u2014",
                    "Ask": f"{q['ask']:.5f}" if q.get("ask") is not None else "\u2014",
                    "Mid": f"{q['mid']:.5f}" if q.get("mid") is not None else "\u2014",
                    "Spread": f"{q['spread']:.5f}" if q.get("spread") is not None else "\u2014",
                    "Provider": q.get("provider") or "\u2014",
                    "Volume": f"{q['volume']:,.0f}" if q.get("volume") is not None else "\u2014",
                }
                for q in live_market["quotes"]
            ]
            st.dataframe(display_rows, use_container_width=True, hide_index=True)

            cache_note = (
                f"cached, {live_market['_cache_age_seconds']:.0f}s old"
                if live_market.get("_from_cache")
                else "just fetched"
            )
            st.caption(cache_note)

        st.divider()
        st.markdown("**Manage Watchlist**")

        from modules.forex.forex_currency_strength_engine import MAJOR_AND_CROSS_PAIRS

        existing_pairs = [q.get("pair") for q in (live_market.get("quotes") or [])]
        addable_pairs = [p for p in MAJOR_AND_CROSS_PAIRS if p not in existing_pairs]

        manage_cols = st.columns([3, 1, 3, 1])
        with manage_cols[0]:
            new_watch_pairs = st.multiselect(
                "Add pair(s)", options=addable_pairs, key="fx_v2_add_pair_select",
            )
        with manage_cols[1]:
            st.write("")
            add_pair_clicked = st.button("Add", key="fx_v2_add_pair_btn")
        with manage_cols[2]:
            remove_watch_pair = st.selectbox(
                "Remove pair", options=existing_pairs or ["\u2014"], key="fx_v2_remove_pair_select",
            )
        with manage_cols[3]:
            st.write("")
            remove_pair_clicked = st.button("Remove", key="fx_v2_remove_pair_btn")

        if add_pair_clicked and new_watch_pairs:
            added, failed = [], []
            for pair_to_add in new_watch_pairs:
                add_result = _add_watchlist_pair(
                    db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, pair=pair_to_add,
                )
                if add_result.get("status") == "ok":
                    added.append(pair_to_add)
                else:
                    failed.append((pair_to_add, add_result.get("message")))

            if added:
                st.session_state.pop(f"fx_v2_live_market_cache:{portfolio_id}", None)
                st.success(f"Added {', '.join(added)}.")
            for pair_name, message in failed:
                st.error(f"{pair_name}: {message}")

        if remove_pair_clicked and existing_pairs:
            remove_result = _remove_watchlist_pair(
                db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, pair=remove_watch_pair,
            )
            if remove_result.get("status") == "ok":
                st.session_state.pop(f"fx_v2_live_market_cache:{portfolio_id}", None)
                st.success(f"Removed {remove_watch_pair}.")
            else:
                st.error(remove_result.get("message"))

    elif workspace == "Exposure":
        st.caption(
            f"Currency/pair exposure and cash ledger, throttled to at most "
            f"one real computation every {EXPOSURE_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_exposure = st.button("🔄 Refresh now", key="fx_v2_force_refresh_exposure")

        exposure_data = _timed_section(
            "exposure",
            _get_throttled_exposure,
            db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id,
            force=force_refresh_exposure,
        )

        st.markdown("**Currency Exposure**")
        currency_exposure = exposure_data.get("currency_exposure") or []
        if currency_exposure:
            rows = [
                {
                    "Currency": r.get("currency"),
                    "Net Exposure": f"${r['net_exposure']:,.2f}" if r.get("net_exposure") is not None else "\u2014",
                    "Gross Exposure": f"${r['gross_exposure']:,.2f}" if r.get("gross_exposure") is not None else "\u2014",
                    "Net %": f"{r['net_exposure_pct']:.2f}%" if r.get("net_exposure_pct") is not None else "\u2014",
                    "Bias": r.get("bias"),
                }
                for r in currency_exposure
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No currency exposure.")

        st.divider()
        st.markdown("**Pair Exposure**")
        pair_exposure = exposure_data.get("pair_exposure") or []
        if pair_exposure:
            rows = [
                {
                    "Pair": r.get("pair"),
                    "Net Notional": f"${r['net_notional']:,.2f}" if r.get("net_notional") is not None else "\u2014",
                    "Gross Notional": f"${r['gross_notional']:,.2f}" if r.get("gross_notional") is not None else "\u2014",
                    "Unrealized P&L": f"${r['unrealized_pnl']:,.2f}" if r.get("unrealized_pnl") is not None else "\u2014",
                    "Positions": r.get("position_count"),
                    "Bias": r.get("bias"),
                }
                for r in pair_exposure
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No pair exposure.")

        st.divider()
        st.markdown("**Cash Ledger**")
        cash_ledger = exposure_data.get("cash_ledger") or []
        if cash_ledger:
            st.dataframe(cash_ledger, use_container_width=True, hide_index=True)
        else:
            st.info("No cash ledger activity.")

    elif workspace == "Execution Quality":
        st.caption(
            f"Order statistics, trade performance, and fill/slippage/latency "
            f"quality -- consolidated from what were 8 separate sections in "
            f"the original (all sharing the same underlying data), throttled "
            f"to at most one real computation every "
            f"{EXECUTION_QUALITY_THROTTLE_SECONDS:.0f} seconds."
        )

        force_refresh_eq = st.button("🔄 Refresh now", key="fx_v2_force_refresh_execution_quality")

        eq = _timed_section(
            "execution_quality",
            _get_throttled_execution_quality,
            db, portfolio_id=portfolio_id, account_id=None, force=force_refresh_eq,
        )

        if eq.get("error"):
            st.error(f"Could not get execution quality data: {eq['error']}")
        else:
            stats = eq.get("statistics") or {}
            quality = eq.get("quality") or {}

            st.markdown("**Order Statistics**")
            stat_cols = st.columns(5)
            with stat_cols[0]:
                st.metric("Total Orders", stats.get("total_orders", 0))
            with stat_cols[1]:
                st.metric("Filled", stats.get("filled_orders", 0))
            with stat_cols[2]:
                st.metric("Pending", stats.get("pending_orders", 0))
            with stat_cols[3]:
                st.metric("Cancelled", stats.get("cancelled_orders", 0))
            with stat_cols[4]:
                st.metric("Rejected", stats.get("rejected_orders", 0))

            st.divider()
            st.markdown("**Execution Quality**")
            quality_cols = st.columns(4)
            with quality_cols[0]:
                st.metric("Fill Rate", f"{quality.get('fill_rate', 0.0):.1f}%")
            with quality_cols[1]:
                avg_slip = quality.get("average_slippage")
                st.metric("Avg Slippage", f"{avg_slip:.5f}" if avg_slip is not None else "\u2014")
            with quality_cols[2]:
                avg_lat = quality.get("average_latency_seconds")
                st.metric("Avg Latency", f"{avg_lat:.2f}s" if avg_lat is not None else "\u2014")
            with quality_cols[3]:
                st.metric("Partial Fills", quality.get("partial_fills", 0))

            cache_note = (
                f"cached, {eq['_cache_age_seconds']:.0f}s old"
                if eq.get("_from_cache")
                else "just computed"
            )
            st.caption(cache_note)

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