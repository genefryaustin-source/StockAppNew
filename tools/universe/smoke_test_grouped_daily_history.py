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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unittest.mock import patch
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

    print()
    print(f"{results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
