"""
tools/universe/smoke_test_nasdaq_sync.py

End-to-end smoke test for the NASDAQ FTP bulk symbol sync
(modules/universe/nasdaq_ftp_sync.py) and the Polygon grouped-daily bulk
price refresh (modules/market_data/updater.py::bulk_update_from_grouped_daily).

No live network calls are made -- ftp.nasdaqtrader.com and api.polygon.io
aren't reachable from every environment this might run in, so the FTP
fetch and the Polygon HTTP call are mocked with realistic sample data
matching each service's documented response format. What's under real
test is the parsing, filtering, and database-write logic -- exactly the
part most likely to have a bug, versus "can this environment reach the
internet."

Usage:
    cd <repo root>
    python3 tools/universe/smoke_test_nasdaq_sync.py
"""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import modules.universe.models          # noqa: F401
import modules.market_data.models        # noqa: F401
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

    # ── NASDAQ FTP file parsing (header-name-based, not positional) ──────
    def _check_pipe_parsing_and_test_issue_filtering():
        from modules.universe.nasdaq_ftp_sync import _parse_pipe_delimited, _is_test_issue, _is_etf

        nasdaqlisted_sample = (
            "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
            "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
            "QQQ|Invesco QQQ Trust Series 1|G|N|N|100|Y|N\n"
            "ZWZZT|Test Symbol - Test|Q|Y|N|100|N|N\n"
            "File Creation Time: 0919202606:30"
        )
        rows = _parse_pipe_delimited(nasdaqlisted_sample)
        assert len(rows) == 3, f"expected 3 data rows (footer excluded), got {len(rows)}"
        assert _is_test_issue(rows[2]) is True and _is_test_issue(rows[0]) is False
        assert _is_etf(rows[1]) is True and _is_etf(rows[0]) is False

    check("NASDAQ pipe-delimited parsing excludes footer, flags test issues/ETFs correctly",
          _check_pipe_parsing_and_test_issue_filtering)

    def _check_malformed_row_skipped_not_misaligned():
        from modules.universe.nasdaq_ftp_sync import _parse_pipe_delimited
        bad_sample = (
            "Symbol|Security Name|Test Issue\n"
            "AAPL|Apple Inc.|N\n"
            "BADROW|Missing A Field\n"  # wrong field count -- must be skipped, not misparsed
            "MSFT|Microsoft Corp.|N\n"
        )
        rows = _parse_pipe_delimited(bad_sample)
        assert len(rows) == 2, f"malformed row should be skipped, got {len(rows)} rows"
        assert {r["Symbol"] for r in rows} == {"AAPL", "MSFT"}

    check("A malformed row (wrong field count) is skipped, not silently misaligned",
          _check_malformed_row_skipped_not_misaligned)

    # ── Full sync flow: security_master + universe_symbols, with idempotency ──
    def _check_full_sync_idempotent():
        import modules.universe.nasdaq_ftp_sync as nasdaq_sync
        from modules.universe.models import SecurityMaster, UniverseSymbol

        fake_symbols = {
            "available": True,
            "symbols": [
                {"symbol": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "is_etf": False, "source": "NASDAQ_FTP"},
                {"symbol": "QQQ", "company_name": "Invesco QQQ Trust", "exchange": "NASDAQ", "is_etf": True, "source": "NASDAQ_FTP"},
                {"symbol": "A", "company_name": "Agilent Technologies", "exchange": "N", "is_etf": False, "source": "NASDAQ_FTP"},
            ],
            "nasdaq_listed_count": 2, "other_listed_count": 1,
        }

        with patch.object(nasdaq_sync, "fetch_and_parse_nasdaq_universe", return_value=fake_symbols):
            r1 = nasdaq_sync.sync_universe_from_nasdaq_ftp(db, tenant_id="smoketest-tenant", universe_id="ALL")
            assert r1.available and r1.universe_symbols_added == 3 and r1.security_master_upserted == 3

            r2 = nasdaq_sync.sync_universe_from_nasdaq_ftp(db, tenant_id="smoketest-tenant", universe_id="ALL")
            assert r2.universe_symbols_added == 0, "re-running the sync must not create duplicates"
            assert r2.universe_symbols_already_present == 3

        sm_count = db.query(SecurityMaster).count()
        us_count = (
            db.query(UniverseSymbol)
            .filter(UniverseSymbol.tenant_id == "smoketest-tenant", UniverseSymbol.universe_id == "ALL")
            .count()
        )
        assert sm_count == 3 and us_count == 3, "no duplicate rows after re-sync"

    check("Full NASDAQ sync populates security_master + universe_symbols, idempotent on re-run",
          _check_full_sync_idempotent)

    def _check_sync_degrades_gracefully_on_fetch_failure():
        import modules.universe.nasdaq_ftp_sync as nasdaq_sync
        with patch.object(nasdaq_sync, "fetch_and_parse_nasdaq_universe",
                           return_value={"available": False, "reason": "connection timed out"}):
            result = nasdaq_sync.sync_universe_from_nasdaq_ftp(db, tenant_id="t2", universe_id="ALL")
        assert result.available is False and "timed out" in result.error

    check("Sync degrades gracefully (no crash) when the FTP fetch fails",
          _check_sync_degrades_gracefully_on_fetch_failure)

    # ── Polygon grouped_daily: parsing + rate-limit + empty-response handling ──
    def _check_grouped_daily_parsing():
        from modules.market_data.providers.polygon import fetch_grouped_daily
        fake_response = {
            "status": "OK",
            "results": [
                {"T": "AAPL", "o": 188.5, "h": 191.2, "l": 187.9, "c": 190.4, "v": 52000000, "t": 1758240000000},
                {"T": "MSFT", "o": 420.1, "h": 423.0, "l": 418.5, "c": 421.8, "v": 21000000, "t": 1758240000000},
            ],
        }
        with patch("modules.market_data.providers.polygon.requests.get") as mock_get:
            mock_get.return_value = MagicMock(json=lambda: fake_response)
            df = fetch_grouped_daily("2026-09-18", api_key="fake_key")
        assert list(df.columns) == ["Symbol", "Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 2
        assert float(df[df["Symbol"] == "AAPL"]["Close"].iloc[0]) == 190.4

    check("Polygon grouped_daily correctly parses a normal response", _check_grouped_daily_parsing)

    def _check_grouped_daily_rate_limit():
        from modules.market_data.providers.polygon import fetch_grouped_daily, PolygonRateLimitException
        with patch("modules.market_data.providers.polygon.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: {"status": "ERROR", "error": "you have exceeded the maximum requests per minute"}
            )
            raised = False
            try:
                fetch_grouped_daily("2026-09-18", api_key="fake_key")
            except PolygonRateLimitException:
                raised = True
        assert raised, "rate limit response should raise PolygonRateLimitException"

    check("Polygon grouped_daily raises PolygonRateLimitException on a rate-limited response",
          _check_grouped_daily_rate_limit)

    def _check_grouped_daily_empty_response():
        from modules.market_data.providers.polygon import fetch_grouped_daily
        with patch("modules.market_data.providers.polygon.requests.get") as mock_get:
            mock_get.return_value = MagicMock(json=lambda: {"status": "OK", "resultsCount": 0})
            df = fetch_grouped_daily("2026-09-20", api_key="fake_key")  # a Sunday
        assert df.empty, "a weekend/holiday response should return an empty DataFrame, not raise"

    check("Polygon grouped_daily returns an empty DataFrame (not an error) for a weekend/holiday",
          _check_grouped_daily_empty_response)

    # ── Bulk price update: filters to tracked symbols, writes real rows ──
    def _check_bulk_update_filters_and_writes():
        import pandas as pd
        import modules.market_data.updater as updater

        fake_grouped = pd.DataFrame([
            {"Symbol": "AAPL", "Open": 188.5, "High": 191.2, "Low": 187.9, "Close": 190.4, "Volume": 52000000},
            {"Symbol": "MSFT", "Open": 420.1, "High": 423.0, "Low": 418.5, "Close": 421.8, "Volume": 21000000},
            {"Symbol": "UNTRACKED_NOISE", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1},
        ])

        with patch("modules.market_data.updater.get_secret", return_value="fake_key"), \
             patch("modules.market_data.providers.polygon.fetch_grouped_daily", return_value=fake_grouped):
            result = updater.bulk_update_from_grouped_daily(db, symbols=["AAPL", "MSFT", "GOOGL"], date="2026-09-18")

        assert result["updated"] == 2, f"expected 2 updates (AAPL, MSFT), got {result}"
        assert "UNTRACKED_NOISE" not in result["updated_symbols"], "must never write symbols outside the requested list"
        assert result["skipped"] == 1 and "GOOGL" in result["skipped_symbols"]

        from modules.market_data.models import PriceHistory
        written = {r.symbol for r in db.query(PriceHistory).filter(PriceHistory.symbol.in_(["AAPL", "MSFT"])).all()}
        assert written == {"AAPL", "MSFT"}

    check("Bulk grouped-daily price update writes only tracked symbols, reports skips honestly",
          _check_bulk_update_filters_and_writes)

    def _check_bulk_update_no_api_key():
        import modules.market_data.updater as updater
        with patch("modules.market_data.updater.get_secret", return_value=None):
            result = updater.bulk_update_from_grouped_daily(db, symbols=["AAPL"])
        assert result["updated"] == 0 and "POLYGON_API_KEY" in result["error"]

    check("Bulk price update reports a clear error (not a crash) when no Polygon key is configured",
          _check_bulk_update_no_api_key)

    print()
    print(f"{results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
