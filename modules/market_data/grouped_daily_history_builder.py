"""
modules/market_data/grouped_daily_history_builder.py

Builds a full price HISTORY (many days) for MANY symbols using Polygon's
grouped-daily endpoint -- the inverse access pattern from
modules.market_data.updater.bulk_update_from_grouped_daily, which builds
ONE day for MANY symbols (for a daily price refresh).

Why this exists: modules.market_data.service.build_shared_price_cache --
what the Universe Refresh job's analytics step (run_vectorized_price_analytics)
uses to get a year of daily history per symbol -- fetches that history ONE
SYMBOL AT A TIME (one provider API call per symbol), capped at
max_api_calls (default 400) per job run. For an 11,000+ symbol universe,
that means ~28 separate manual "Run Next Job" clicks just to cover
everyone once, each call going through the full multi-provider failover
chain.

This builds the same shape of data (a full year of OHLCV per symbol) a
completely different way: loop over trading DAYS (not symbols), call
grouped_daily once per day (one call = the whole market's close that
day), and accumulate ~252 days into a per-symbol price history. That's
roughly 252 API calls total to cover EVERY symbol in the universe with a
full year of history, instead of one call per symbol.

Trade-off to know: this only covers whatever Polygon's grouped-daily
endpoint includes (US equities). Symbols it has no data for (some OTC/
delisted/very new tickers) come back with no rows here and should fall
back to the existing per-symbol build_shared_price_cache path -- this
module is meant to run FIRST and cover the bulk of the universe fast,
not to fully replace the per-symbol path.

Returns the same shape as build_shared_price_cache() -- (price_cache,
meta) where price_cache = {symbol: DataFrame[Date,Open,High,Low,Close,Volume]}
-- so it's a drop-in data source, not a new interface callers need to
learn.
"""

from __future__ import annotations

import time
import logging
from collections import deque
from datetime import date, timedelta
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

ProgressFn = Optional[Callable[[int, int, str], None]]


class _RateLimiter:
    """Rolling-window limiter: at most `calls_per_minute` calls in any
    60-second window. Paces calls proactively rather than firing as fast
    as possible and hoping -- gentler on a shared free-tier API key than
    reacting only after a 429 comes back."""

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = max(1, calls_per_minute)
        self._call_times: deque = deque()

    def wait_if_needed(self) -> None:
        now = time.monotonic()
        while self._call_times and now - self._call_times[0] > 60:
            self._call_times.popleft()
        if len(self._call_times) >= self.calls_per_minute:
            sleep_for = 60 - (now - self._call_times[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._call_times.append(time.monotonic())


def _trading_day_candidates(start: date, count: int) -> list[date]:
    """Weekdays going backward from `start` -- a cheap pre-filter for
    weekends. Holidays aren't filtered here (no holiday calendar) --
    grouped_daily's empty response on a holiday is treated the same as a
    weekend by the caller (skipped, doesn't count toward the target)."""
    days = []
    d = start
    while len(days) < count:
        if d.weekday() < 5:  # Monday=0 .. Friday=4
            days.append(d)
        d -= timedelta(days=1)
    return days


def build_price_cache_from_grouped_daily(
    db,
    symbols: list[str],
    lookback_days: int = 252,
    calls_per_minute: int = 5,
    persist: bool = True,
    progress: ProgressFn = None,
) -> tuple[dict, dict]:
    """
    symbols: the universe to build history for.
    lookback_days: target number of TRADING days of history (252 ≈ 1 year).
    calls_per_minute: paces grouped_daily calls -- default 5 matches
        Polygon's free tier; raise this if you're on a paid plan.
    persist: also bulk-upsert each day's fetched rows into price_history
        (via the same bulk_upsert_price_history used by the daily price
        refresh) so the database benefits permanently, not just this
        one in-memory cache.
    progress: optional callback(trading_days_done, trading_days_target, date_str) --
        called once per TRADING DAY (not per symbol), since a whole
        day's fetch covers every symbol at once. Deliberately not
        per-symbol: a per-symbol progress callback here (11,000+ calls)
        would reintroduce exactly the kind of database-round-trip-per-item
        overhead already found and fixed elsewhere in this pipeline.

    Returns (price_cache, meta) -- same shape as
    modules.market_data.service.build_shared_price_cache: price_cache is
    {symbol: DataFrame[Date, Open, High, Low, Close, Volume]}, meta is
    {symbol: {"rows": int}}. Symbols Polygon never returned data for are
    simply absent from both dicts -- callers should treat that the same
    way build_shared_price_cache's silent per-symbol skip already works,
    and fall back to the per-symbol path for anything missing.
    """
    from modules.utils.config import get_secret
    from modules.market_data.providers.polygon import fetch_grouped_daily, PolygonRateLimitException

    api_key = get_secret("POLYGON_API_KEY")
    if not api_key:
        return {}, {"_error": "POLYGON_API_KEY not configured"}

    wanted = {s.strip().upper() for s in symbols if s and s.strip()}
    if not wanted:
        return {}, {}

    # IMPORTANT: earlier versions of this function accumulated every
    # symbol's every fetched day as a Python dict in memory for the
    # ENTIRE run (accumulator[sym].append(...)), on top of ALSO
    # persisting to the database. For an 11,000-symbol universe over a
    # year of history (~2.7 million small dict objects), this bloated
    # memory usage badly -- on a production box with well under 1GB of
    # RAM, it drove the process into heavy swapping (and likely an OOM
    # kill/restart) while appearing to make zero progress, since nearly
    # all its "CPU time" was actually the kernel swapping memory in and
    # out rather than useful work. Since every fetched row is already
    # being persisted to price_history as we go, there's no need to also
    # hold it all in memory during the fetch -- this version only tracks
    # which symbols were actually touched, then reads the result back
    # from Postgres in bounded chunks afterward. A single columnar bulk
    # read (via pandas) for a batch of symbols is dramatically cheaper
    # than millions of small Python dict objects accumulated one at a
    # time, and chunking the read-back keeps peak memory bounded
    # regardless of universe size, rather than pulling everything back
    # in one giant query.
    limiter = _RateLimiter(calls_per_minute)
    candidates = _trading_day_candidates(date.today() - timedelta(days=1), lookback_days * 2)

    trading_days_found = 0
    touched_symbols: set[str] = set()
    no_persist_accumulator: dict[str, list[dict]] = {}
    fetched_dates: list[date] = []
    bulk_upsert_price_history = None
    if persist:
        from modules.market_data.price_history_service import bulk_upsert_price_history as _buph
        bulk_upsert_price_history = _buph

    for day in candidates:
        if trading_days_found >= lookback_days:
            break

        limiter.wait_if_needed()
        date_str = day.isoformat()

        try:
            grouped = fetch_grouped_daily(date_str, api_key=api_key)
        except PolygonRateLimitException:
            print(f"⚠️ [grouped_daily_history] Rate limited fetching {date_str} -- backing off 60s and retrying once.")
            time.sleep(60)
            try:
                grouped = fetch_grouped_daily(date_str, api_key=api_key)
            except Exception as e:
                print(f"⚠️ [grouped_daily_history] Retry after rate limit failed for {date_str}: {e}")
                continue
        except Exception as e:
            print(f"⚠️ [grouped_daily_history] grouped_daily fetch failed for {date_str}: {e}")
            continue

        if grouped.empty:
            continue  # weekend/holiday -- doesn't count toward the trading-day target

        trading_days_found += 1
        fetched_dates.append(day)
        matched = grouped[grouped["Symbol"].str.upper().isin(wanted)]

        if not persist:
            # Without persistence there is nowhere to read the data back
            # from afterward, so this (rare) case keeps the old, fully
            # in-memory behavior -- a caller explicitly opting out of
            # persistence is choosing a lighter-weight, presumably
            # smaller-scale, use where this doesn't matter.
            for _, row in matched.iterrows():
                sym = row["Symbol"].upper()
                touched_symbols.add(sym)
                no_persist_accumulator.setdefault(sym, []).append({
                    "Date": day, "Open": row["Open"], "High": row["High"],
                    "Low": row["Low"], "Close": row["Close"], "Volume": row["Volume"],
                })
            continue

        persist_rows = [
            {
                "symbol": row["Symbol"].upper(), "date": day, "open": row["Open"], "high": row["High"],
                "low": row["Low"], "close": row["Close"], "volume": row["Volume"],
            }
            for _, row in matched.iterrows()
        ]
        touched_symbols.update(r["symbol"] for r in persist_rows)

        if persist_rows and bulk_upsert_price_history is not None:
            try:
                bulk_upsert_price_history(db, persist_rows)
            except Exception as e:
                print(f"🚨 [grouped_daily_history] Persisting grouped-daily rows for {date_str} failed: {e}")

        if progress:
            try:
                progress(trading_days_found, lookback_days, date_str)
            except Exception:
                pass  # a broken progress callback should never abort the actual fetch

    if not persist:
        price_cache, meta = {}, {}
        for sym, day_rows in no_persist_accumulator.items():
            if not day_rows:
                continue
            df = pd.DataFrame(day_rows).sort_values("Date").reset_index(drop=True)
            price_cache[sym] = df
            meta[sym] = {"rows": len(df)}
        return price_cache, meta

    if not touched_symbols or not fetched_dates:
        return {}, {}

    return _read_back_price_cache(db, touched_symbols, min(fetched_dates), max(fetched_dates))


def _read_back_price_cache(
    db, symbols: set[str], start_date: date, end_date: date, chunk_size: int = 500,
) -> tuple[dict, dict]:
    """
    Rebuilds the {symbol: DataFrame} price cache from price_history AFTER
    the fetch loop has already persisted everything -- one bounded, mostly
    columnar bulk read per chunk of symbols, instead of holding the whole
    universe's history in memory throughout the fetch itself. Reads are
    chunked (default 500 symbols at a time) so peak memory for the
    read-back step stays roughly constant regardless of how large the
    total universe is.
    """
    from modules.market_data.models import PriceHistory

    price_cache: dict[str, pd.DataFrame] = {}
    meta: dict[str, dict] = {}
    symbol_list = sorted(symbols)

    for chunk_start in range(0, len(symbol_list), chunk_size):
        chunk = symbol_list[chunk_start:chunk_start + chunk_size]
        try:
            rows = (
                db.query(
                    PriceHistory.symbol, PriceHistory.date, PriceHistory.open,
                    PriceHistory.high, PriceHistory.low, PriceHistory.close, PriceHistory.volume,
                )
                .filter(
                    PriceHistory.symbol.in_(chunk),
                    PriceHistory.date >= start_date,
                    PriceHistory.date <= end_date,
                )
                .order_by(PriceHistory.symbol, PriceHistory.date)
                .all()
            )
        except Exception as e:
            print(f"🚨 [grouped_daily_history] Read-back query failed for a chunk of {len(chunk)} symbols: {e}")
            continue

        if not rows:
            continue

        chunk_df = pd.DataFrame(
            rows, columns=["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"],
        )
        for sym, group in chunk_df.groupby("Symbol", sort=False):
            df = group.drop(columns=["Symbol"]).reset_index(drop=True)
            price_cache[sym] = df
            meta[sym] = {"rows": len(df)}
        del chunk_df, rows  # let this chunk's memory go before starting the next one

    return price_cache, meta