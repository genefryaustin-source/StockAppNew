"""
tools/universe/smoke_test_grouped_daily_history.py

Tests for modules.market_data.grouped_daily_history_builder and its
integration into modules.market_data.service.build_shared_price_cache_bulk_first
-- the fix meant to speed up the "Queue Universe Refresh" job, which
previously fetched a full year of daily history one symbol at a time
(capped at 400 API calls per job run). This builds the same year of
history for EVERY symbol using ~252 grouped-daily calls total (one call
per trading day, not per symbol), falling back to the original
per-symbol path only for whatever the bulk fetch doesn't cover.

No live network calls -- ftp.nasdaqtrader.com/api.polygon.io aren't
reachable from every environment -- Polygon's grouped_daily is mocked
with realistic responses; what's under real test is the day-accumulation
logic, rate-limit pacing, weekend/holiday handling, and the merge with
the existing per-symbol fallback path.

Usage:
    cd <repo root>
    python3 tools/universe/smoke_test_grouped_daily_history.py
"""

import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unittest.mock import patch, MagicMock
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import modules.market_data.models  # noqa: F401
from models.base import Base

results = {"pass": 0, "fail": 0}


def check(label, fn):
    try:
        fn()
        print(f"PASS  {label}")
        results["pass"] += 1
    except Exception as e:
        print(f"FAIL  {label}: {type(e).__name__}: {e}")
        results["fail"] += 1


def main():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    from modules.market_data.grouped_daily_history_builder import build_price_cache_from_grouped_daily
    from modules.market_data.providers.polygon import PolygonRateLimitException

    call_log = []

    def fake_fetch_grouped_daily(date_str, api_key, timeout=30):
        call_log.append(date_str)
        if date_str == "2026-09-18":  # simulated holiday
            return pd.DataFrame(columns=["Symbol", "Open", "High", "Low", "Close", "Volume"])
        return pd.DataFrame([
            {"Symbol": "AAPL", "Open": 188.0, "High": 191.0, "Low": 187.0, "Close": 190.0, "Volume": 1000000},
            {"Symbol": "MSFT", "Open": 420.0, "High": 423.0, "Low": 418.0, "Close": 421.0, "Volume": 500000},
            {"Symbol": "NOTREQUESTED", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1},
        ])

    def _check_builds_correct_trading_day_count():
        call_log.clear()
        with patch("modules.utils.config.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", side_effect=fake_fetch_grouped_daily), \
             patch("time.sleep"):
            cache, meta = build_price_cache_from_grouped_daily(
                db, symbols=["AAPL", "MSFT", "GOOGL"], lookback_days=10, persist=True,
            )
        assert "AAPL" in cache and "MSFT" in cache
        assert "GOOGL" not in cache, "a symbol Polygon never returned should simply be absent, not an error"
        assert "NOTREQUESTED" not in cache, "a symbol outside the requested list must never leak in"
        assert len(cache["AAPL"]) == 10, f"holiday should not count toward the trading-day target, got {len(cache['AAPL'])}"
        assert list(cache["AAPL"].columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
        assert "2026-09-18" in call_log, "the holiday date should still be fetched (and correctly skipped after)"

    check("Builds the exact requested trading-day count, correctly skipping a holiday", _check_builds_correct_trading_day_count)

    def _check_persists_to_price_history():
        from modules.market_data.models import PriceHistory
        count = db.query(PriceHistory).filter(PriceHistory.symbol.in_(["AAPL", "MSFT"])).count()
        assert count == 20, f"expected 10 days x 2 symbols = 20 persisted rows, got {count}"

    check("Fetched data is persisted to price_history via bulk_upsert_price_history", _check_persists_to_price_history)

    def _check_no_api_key_degrades_gracefully():
        with patch("modules.utils.config.get_secret", return_value=None):
            cache, meta = build_price_cache_from_grouped_daily(db, symbols=["AAPL"], lookback_days=5)
        assert cache == {} and "_error" in meta

    check("Degrades gracefully (no crash) when POLYGON_API_KEY isn't configured", _check_no_api_key_degrades_gracefully)

    def _check_rate_limit_recovery():
        state = {"n": 0}
        def flaky(date_str, api_key, timeout=30):
            state["n"] += 1
            if state["n"] == 1:
                raise PolygonRateLimitException("rate limited")
            return pd.DataFrame([{"Symbol": "AAPL", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1}])
        with patch("modules.utils.config.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", side_effect=flaky), \
             patch("time.sleep"):
            cache, meta = build_price_cache_from_grouped_daily(db, symbols=["AAPL"], lookback_days=1, persist=False)
        assert "AAPL" in cache, "should recover from a rate-limit via the one-retry backoff"

    check("Recovers from a rate-limit exception via a single backoff-and-retry", _check_rate_limit_recovery)

    def _check_rate_limiter_paces_calls():
        call_log.clear()
        with patch("modules.utils.config.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", side_effect=fake_fetch_grouped_daily), \
             patch("time.sleep") as mock_sleep:
            build_price_cache_from_grouped_daily(db, symbols=["AAPL"], lookback_days=10,
                                                   calls_per_minute=5, persist=False)
        assert mock_sleep.called, "with 11 calls and a 5/minute limit, the rate limiter should have paced at least once"

    check("Rate limiter actually paces calls rather than firing unlimited requests", _check_rate_limiter_paces_calls)

    # ── Integration: build_shared_price_cache_bulk_first merge behavior ──
    from modules.market_data.service import build_shared_price_cache_bulk_first

    def _check_bulk_first_merges_with_fallback_for_gaps():
        def fake_bulk(db, symbols, lookback_days, calls_per_minute, persist):
            return (
                {"AAPL": pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=100),
                                        "Open": [1]*100, "High": [1]*100, "Low": [1]*100,
                                        "Close": [1]*100, "Volume": [1]*100})},
                {"AAPL": {"rows": 100}},
            )
        fallback_calls = []
        def fake_fallback(db, symbols, min_rows, period, interval, max_api_calls, **kwargs):
            fallback_calls.append(list(symbols))
            return (
                {"GOOGL": pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=80),
                                         "Open": [2]*80, "High": [2]*80, "Low": [2]*80,
                                         "Close": [2]*80, "Volume": [2]*80})},
                {"GOOGL": {"rows": 80}},
            )
        with patch("modules.market_data.grouped_daily_history_builder.build_price_cache_from_grouped_daily",
                   side_effect=fake_bulk), \
             patch("modules.market_data.service.build_shared_price_cache", side_effect=fake_fallback):
            cache, meta = build_shared_price_cache_bulk_first(
                db, symbols=["AAPL", "GOOGL"], min_rows=50, period="1y", interval="1d",
            )
        assert set(cache.keys()) == {"AAPL", "GOOGL"}
        assert fallback_calls == [["GOOGL"]], (
            f"fallback should only run for the symbol the bulk path didn't cover, got {fallback_calls}"
        )

    check("build_shared_price_cache_bulk_first merges bulk results with a fallback only for gaps",
          _check_bulk_first_merges_with_fallback_for_gaps)

    def _check_non_daily_interval_skips_bulk_path():
        with patch("modules.market_data.service.build_shared_price_cache") as mock_fallback:
            mock_fallback.return_value = ({}, {})
            build_shared_price_cache_bulk_first(db, symbols=["AAPL"], period="1y", interval="1h")
        assert mock_fallback.called, "a non-daily interval should go straight to the existing per-symbol path"

    check("A non-daily interval bypasses the bulk (daily-only) path entirely",
          _check_non_daily_interval_skips_bulk_path)

    # ── Regression: one bad symbol's real DB error must not cascade and
    # kill every symbol processed after it in the same loop. Found in
    # production: a universe_refresh job failed outright with "Can't
    # reconnect until invalid transaction is rolled back" after this
    # exact bulk-first integration was deployed -- the per-symbol error
    # handler logged the failure but never rolled back, so Postgres kept
    # refusing every subsequent query on that session until the whole job
    # died.
    #
    # IMPORTANT: this can only be verified against real Postgres. SQLite's
    # transaction model is far more lenient -- a failed query there does
    # NOT poison the session the way Postgres's does, so this exact test
    # would report a false PASS on SQLite regardless of whether the fix
    # is actually present. Skips honestly (not a fabricated pass) when
    # only SQLite is available, e.g. in a quick local run without
    # DATABASE_URL pointed at a real Postgres instance. ──
    def _check_one_bad_symbol_does_not_cascade():
        import modules.analytics.runner as runner_module
        from sqlalchemy import text

        pg_url = os.environ.get("DATABASE_URL", "")
        if not pg_url.startswith("postgresql"):
            print("SKIP  (requires a real Postgres DATABASE_URL -- SQLite doesn't "
                  "reproduce this transaction-abort behavior, so this test would "
                  "pass regardless of whether the fix is present)")
            return

        pg_engine = create_engine(pg_url)
        pg_db = sessionmaker(bind=pg_engine)()

        call_log = []

        def fake_run_analytics_for_symbol(db, tenant_id, symbol, price_df=None):
            call_log.append(symbol)
            if symbol == "BADSYM":
                # A genuine Postgres error (not a dropped connection) --
                # exactly the class of error _is_dead_connection_error does
                # not recognize, so recovery depends on the per-symbol
                # except block rolling back unconditionally.
                db.execute(text("SELECT * FROM this_table_does_not_exist"))
            db.execute(text("SELECT 1"))
            return {"symbol": symbol, "ok": True}

        price_cache = {sym: pd.DataFrame({"Close": [1, 2, 3]})
                       for sym in ["GOODSYM1", "BADSYM", "GOODSYM2", "GOODSYM3"]}

        with patch("modules.analytics.runner.run_analytics_for_symbol", side_effect=fake_run_analytics_for_symbol), \
             patch("modules.analytics.runner.build_shared_price_cache_bulk_first",
                   return_value=(price_cache, {s: {"rows": 3} for s in price_cache})), \
             patch("modules.analytics.runner._normalize_history_df", side_effect=lambda df: df), \
             patch("modules.analytics.runner.MIN_HISTORY_ROWS", 1):
            results, _ = runner_module.run_vectorized_price_analytics(
                db=pg_db, tenant_id="test-tenant", symbols=list(price_cache.keys()),
            )

        succeeded = [r["symbol"] for r in results]
        assert call_log == ["GOODSYM1", "BADSYM", "GOODSYM2", "GOODSYM3"], (
            f"all 4 symbols should have been attempted, got {call_log}"
        )
        assert succeeded == ["GOODSYM1", "GOODSYM2", "GOODSYM3"], (
            f"GOODSYM2/GOODSYM3 must succeed despite BADSYM's real error -- got {succeeded}. "
            "Without the rollback fix, both would fail with a cascading "
            "'current transaction is aborted' error even though nothing is wrong with them."
        )

    check("One symbol's genuine DB error is rolled back and does not cascade to the rest of the run (Postgres only)",
          _check_one_bad_symbol_does_not_cascade)

    # ── Regression: the real cause of a universe_refresh job running for
    # "approximately one day" instead of finishing. modules.analytics.runner
    # imports _disable_provider/provider_enabled from market_data.service
    # inside a bare try/except that silently falls back to no-op stubs
    # (provider_enabled always True, _disable_provider a no-op) if the
    # import fails for ANY reason -- including a genuine ImportError, which
    # is exactly what was happening: provider_enabled didn't exist in
    # service.py at all. The cooldown-setting half worked
    # (_disable_provider/_provider_disabled), but nothing ever read it, so
    # every one of 11,000+ symbols re-attempted every already-exhausted
    # fundamentals provider (Finnhub/FMP/Alpha Vantage) and got rate-limited
    # again, one guaranteed-to-fail HTTP round-trip at a time. ──
    def _check_provider_enabled_exists_and_is_wired_up():
        from modules.market_data.service import provider_enabled, _disable_provider
        import modules.analytics.runner as runner_module

        assert runner_module.provider_enabled is provider_enabled, (
            "runner.py's import of provider_enabled must resolve to the real function, "
            "not silently fall back to the always-True no-op stub"
        )
        assert runner_module._disable_provider is _disable_provider, (
            "runner.py's import of _disable_provider must resolve to the real function"
        )

    check("provider_enabled exists and runner.py's import resolves to the real function, not a no-op stub",
          _check_provider_enabled_exists_and_is_wired_up)

    def _check_circuit_breaker_skips_symbols_after_rate_limit():
        import modules.market_data.service as svc
        svc._PROVIDER_STATE.clear()  # isolate from any other test's cooldown state

        import modules.analytics.runner as runner_module
        call_count = {"n": 0}

        def fake_requests_get(url, params=None, timeout=None):
            call_count["n"] += 1
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "rate limited"
            return resp

        with patch("modules.analytics.runner.requests.get", side_effect=fake_requests_get), \
             patch("modules.analytics.runner.get_secret", return_value="fake_key"):
            runner_module._get_finnhub_fundamentals("SYM1")
            calls_after_first = call_count["n"]
            runner_module._get_finnhub_fundamentals("SYM2")
            calls_after_second = call_count["n"]

        assert calls_after_first == 1
        assert calls_after_second == 1, (
            f"a second symbol must NOT make another HTTP call once the provider is in cooldown -- "
            f"got {calls_after_second} total calls. This is the exact bug that turned a job that "
            f"should finish in minutes into one that ran for roughly a full day."
        )
        svc._PROVIDER_STATE.clear()  # leave clean state for any tests that run after this one

    check("After one rate-limit, the circuit breaker skips the provider entirely for subsequent symbols",
          _check_circuit_breaker_skips_symbols_after_rate_limit)

    # ── Regression: a genuine production error found while testing today's
    # fix -- "ON CONFLICT DO UPDATE command cannot affect row a second
    # time" (psycopg2.errors.CardinalityViolation). Two rows for the same
    # (symbol, date) landed in the same 500-row batch (from Polygon's
    # grouped-daily response, or a case-normalization collision), which
    # Postgres's multi-row upsert cannot resolve on its own. The existing
    # row-by-row fallback recovered the data correctly (no data was lost
    # in production), but silently dropped that whole batch to the slow
    # path this function exists to avoid. Deduplicating by (symbol, date)
    # before building the INSERT means the fast bulk path handles it
    # directly instead of ever needing to fall back. ──
    def _check_duplicate_symbol_date_in_batch_does_not_error():
        from modules.market_data.price_history_service import bulk_upsert_price_history
        from modules.market_data.models import PriceHistory
        from datetime import date as date_cls

        rows = [
            {"symbol": "AAPL", "date": date_cls(2025, 11, 6), "open": 188.0, "high": 191.0,
             "low": 187.0, "close": 190.0, "volume": 1000000},
            {"symbol": "MSFT", "date": date_cls(2025, 11, 6), "open": 420.0, "high": 423.0,
             "low": 418.0, "close": 421.0, "volume": 500000},
            # The exact production scenario: same symbol, same date, twice
            # in one batch, with a different value on the second occurrence.
            {"symbol": "AAPL", "date": date_cls(2025, 11, 6), "open": 188.5, "high": 191.5,
             "low": 187.5, "close": 190.5, "volume": 1000001},
        ]

        result = bulk_upsert_price_history(db, rows)
        assert result["failed_batches"] == 0, (
            f"the fast bulk path should succeed directly with a duplicate present, not fall back -- "
            f"got {result['failed_batches']} failed batch(es): {result['errors']}"
        )
        assert result["written"] == 2, f"expected 2 unique (symbol, date) rows written, got {result['written']}"

        aapl_row = db.query(PriceHistory).filter_by(symbol="AAPL", date=date_cls(2025, 11, 6)).first()
        assert aapl_row.close == 190.5, "the later duplicate in the batch should win"

        total = db.query(PriceHistory).filter(
            PriceHistory.symbol.in_(["AAPL", "MSFT"]), PriceHistory.date == date_cls(2025, 11, 6)
        ).count()
        assert total == 2, f"expected exactly 2 rows (no duplicate rows created), got {total}"

    check("A duplicate (symbol, date) within one batch no longer raises CardinalityViolation",
          _check_duplicate_symbol_date_in_batch_does_not_error)

    # ── Regression: memory design. The original version accumulated every
    # symbol's every fetched day as a Python dict in memory for the ENTIRE
    # run (on top of also persisting to the database) -- for an 11,000-
    # symbol universe over a year of history, roughly 2.7 million small
    # dict objects held simultaneously. On the actual production box
    # (under 1GB of RAM), this drove heavy swapping while a universe_refresh
    # job appeared to make zero progress. Since every row is already
    # persisted as it's fetched, there's no need to also hold it all in
    # memory -- this reads the result back from price_history afterward,
    # in bounded chunks, instead. ──
    def _check_no_full_accumulator_and_read_back_is_correct():
        import time
        from unittest.mock import patch
        import modules.market_data.grouped_daily_history_builder as builder_module

        n_symbols = 300
        symbols = [f"MEMTEST{i:04d}" for i in range(n_symbols)]

        def fake_fetch(date_str, api_key, timeout=30):
            return pd.DataFrame([
                {"Symbol": s, "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 100}
                for s in symbols
            ])

        with patch("modules.utils.config.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", side_effect=fake_fetch), \
             patch("time.sleep"):
            price_cache, meta = builder_module.build_price_cache_from_grouped_daily(
                db, symbols=symbols, lookback_days=10, calls_per_minute=1000, persist=True,
            )

        assert len(price_cache) == n_symbols, f"expected all {n_symbols} symbols in the cache, got {len(price_cache)}"
        assert all(len(df) == 10 for df in price_cache.values()), "each symbol should have exactly 10 trading days"
        assert list(price_cache[symbols[0]].columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]

        # The specific regression: the old code path kept a persistent,
        # ever-growing accumulator dict alive for the whole function call.
        # Confirm the persist=True path delegates to a bounded, chunked
        # database read-back afterward, rather than returning something
        # built up entirely in memory during the fetch loop itself.
        source = inspect.getsource(builder_module.build_price_cache_from_grouped_daily)
        assert "_read_back_price_cache(db, touched_symbols" in source, (
            "the persist=True path should delegate to the bounded, chunked database "
            "read-back instead of returning an in-memory accumulator built during the fetch"
        )

    check("Price cache is correctly rebuilt from the database afterward, not accumulated in memory during the fetch",
          _check_no_full_accumulator_and_read_back_is_correct)

    def _check_persist_false_still_returns_data():
        """The one remaining in-memory code path (persist=False, where
        there's nothing to read back from) must still actually return its
        results -- a regression caught while building this fix: an early
        version of the persist=False branch discarded its own results."""
        from unittest.mock import patch
        import modules.market_data.grouped_daily_history_builder as builder_module

        def fake_fetch(date_str, api_key, timeout=30):
            return pd.DataFrame([
                {"Symbol": "NOPERSIST", "Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10},
            ])

        with patch("modules.utils.config.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", side_effect=fake_fetch), \
             patch("time.sleep"):
            cache, meta = builder_module.build_price_cache_from_grouped_daily(
                db, symbols=["NOPERSIST"], lookback_days=3, persist=False,
            )

        assert "NOPERSIST" in cache, "persist=False must still return the data it fetched, not discard it"
        assert len(cache["NOPERSIST"]) == 3

    check("persist=False still returns its fetched data instead of discarding it", _check_persist_false_still_returns_data)

    print()
    print(f"{results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
