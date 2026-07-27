"""
api/services/market_api_service.py

Market API Service

Backs GET /api/v1/market/macro-dashboard, /bond-market, /commodities,
/movers.

No new logic lives here except modules.market.commodities_data
(genuinely new -- nothing under "commodities" existed anywhere in
this codebase before). Everything else wraps real, existing modules:

    macro-dashboard  modules.market.macro_dashboard._load_macro_snapshot()
                     -- real FRED (Federal Reserve) + Yahoo Finance data:
                     yield curve, credit spreads, inflation breakevens,
                     Fed funds rate, VIX term structure, market proxies.
                     Genuinely real, but was not reachable from the live
                     app at all (render_macro_dashboard has no caller in
                     app.py) before this.

    bond-market      The same _load_macro_snapshot(), narrowed to the
                     yield curve / credit spread / bond-ETF-proxy fields
                     specifically -- not a separate data source.

    commodities      modules.market.commodities_data (new) -- real Yahoo
                     Finance futures prices (gold, silver, crude oil,
                     Brent, natural gas, copper).

    movers           modules.market.dashboard's own movers functions --
                     the same ones the live "Market Overview" page uses.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """DataFrame -> list of records, NaN -> None, so this is always valid JSON."""
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []
        clean = value.replace([math.inf, -math.inf], None).where(pd.notnull(value), None)
        return clean.to_dict(orient="records")

    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_json_safe(v) for v in value]

    if isinstance(value, float) and value != value:  # NaN
        return None

    return value


class MarketAPIService:
    """API service for macro, bond, and commodity market data."""

    def __init__(self, db=None):
        # Only get_market_movers() queries the database (real price
        # history); the rest of this service calls external providers
        # (FRED, Yahoo Finance) directly. Accepted here regardless so
        # this class is consistent with module_registry._load()'s
        # cls(db) instantiation convention used for every service.
        self.db = db

    def get_macro_dashboard(self) -> dict[str, Any]:
        """
        Full macro snapshot: yield curve, credit spreads, inflation
        breakevens, Fed funds rate, VIX term structure, and market
        proxies (IEF/TIP/SPY/TLT) -- real FRED + Yahoo Finance data.
        """
        try:
            from modules.market.macro_dashboard import _load_macro_snapshot

            snapshot = _load_macro_snapshot()

            return {
                "loaded_at": snapshot["loaded_at"],
                "yield_curve": _json_safe(snapshot["yield_df"]),
                "credit_spreads": _json_safe(snapshot["credit_df"]),
                "inflation": _json_safe(snapshot["inflation_df"]),
                "inflation_yoy": snapshot["inflation_yoy"],
                "fed_funds": _json_safe(snapshot["fed_df"]),
                "vix_term_structure": _json_safe(snapshot["vix_df"]),
                "market_proxies": _json_safe(snapshot["proxy_df"]),
                "regime": snapshot["regime"],
                "sources_loaded": {
                    "fred": snapshot["fred_loaded"],
                    "yahoo": snapshot["yahoo_loaded"],
                },
            }

        except Exception:
            logger.exception("Failed to load macro dashboard.")
            return {"available": False, "reason": "This section failed to load."}

    def get_bond_market(self) -> dict[str, Any]:
        """
        Bond-specific slice of the same macro snapshot: Treasury yield
        curve, credit spreads (HY/IG option-adjusted spreads), and
        bond ETF proxies (IEF 7-10Y Treasury, TIP inflation-protected,
        TLT 20+Y Treasury).
        """
        try:
            from modules.market.macro_dashboard import _load_macro_snapshot

            snapshot = _load_macro_snapshot()

            proxy_df = snapshot["proxy_df"]
            bond_proxy_names = {"IEF", "TIP", "TLT"}
            bond_proxies = (
                proxy_df[proxy_df["Symbol"].isin(bond_proxy_names)]
                if isinstance(proxy_df, pd.DataFrame) and "Symbol" in proxy_df.columns
                else proxy_df
            )

            return {
                "loaded_at": snapshot["loaded_at"],
                "yield_curve": _json_safe(snapshot["yield_df"]),
                "credit_spreads": _json_safe(snapshot["credit_df"]),
                "bond_proxies": _json_safe(bond_proxies),
                "regime": snapshot["regime"],
            }

        except Exception:
            logger.exception("Failed to load bond market data.")
            return {"available": False, "reason": "This section failed to load."}

    def get_commodities(self, *, category: str | None = None) -> dict[str, Any]:
        """
        Real Yahoo Finance futures prices across five sectors:
        precious metals, energy, industrial metals, agriculture, and
        livestock (20 contracts total). Optionally scoped to one
        category -- see the "categories" field in an unscoped response
        for valid names.
        """
        try:
            from modules.market.commodities_data import get_commodities_snapshot

            return get_commodities_snapshot(category=category)

        except Exception:
            logger.exception("Failed to load commodities data.")
            return {"available": False, "reason": "This section failed to load."}

    def get_market_movers(self, *, tenant_id: str, universe_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        """
        Top gainers/losers -- the same data the live "Market Overview"
        page's movers table uses (stored price history for this
        tenant's universe, falling back to live quotes if no history
        exists yet).
        """
        try:
            from modules.market.dashboard import _list_universes, _list_symbols, _get_movers_from_price_history, _get_movers_live

            if self.db is None:
                return {"available": False, "reason": "No database session available."}

            if universe_id is None:
                universes = _list_universes(self.db, tenant_id)
                if not universes:
                    return {"available": False, "reason": "No universe configured for this tenant yet."}
                universe_id = universes[0]["id"]

            symbols = _list_symbols(self.db, tenant_id, universe_id)

            if not symbols:
                return {"available": False, "reason": "No symbols in this universe yet."}

            df = _get_movers_from_price_history(self.db, symbols)

            if df.empty:
                df = _get_movers_live(symbols)

            if df.empty:
                return {"available": False, "reason": "No price data available for this universe yet."}

            records = _json_safe(df)

            gainers = sorted(
                [r for r in records if r.get("Change %") is not None],
                key=lambda r: r["Change %"], reverse=True,
            )[:limit]
            losers = sorted(
                [r for r in records if r.get("Change %") is not None],
                key=lambda r: r["Change %"],
            )[:limit]

            return {
                "universe_id": universe_id,
                "symbol_count": len(symbols),
                "gainers": gainers,
                "losers": losers,
            }

        except Exception:
            logger.exception("Failed to load market movers | tenant_id=%s", tenant_id)
            return {"available": False, "reason": "This section failed to load."}

    def get_market_status(self) -> dict[str, Any]:
        """
        Current NYSE session status (Open/Pre-market/After-hours/
        Closed) and local times for New York, London, Tokyo, and Hong
        Kong. See modules.market.market_status for the one known gap
        (Good Friday isn't accounted for).
        """
        try:
            from modules.market.market_status import get_market_status

            return get_market_status()

        except Exception:
            logger.exception("Failed to compute market status.")
            return {"available": False, "reason": "This section failed to load."}

    def get_major_indices(self) -> dict[str, Any]:
        """
        Real Yahoo Finance data for major US and global indices: S&P
        500, Nasdaq-100, Dow Jones, Russell 2000, STOXX 600, Nikkei
        225, Hang Seng, FTSE 100 -- last price, 1-day % / point
        change, and a 5-day sparkline.
        """
        try:
            from modules.market.global_indices import get_major_indices

            return get_major_indices()

        except Exception:
            logger.exception("Failed to load major indices.")
            return {"available": False, "reason": "This section failed to load."}

    def get_sector_performance(self, *, tenant_id: str) -> dict[str, Any]:
        """
        Real sector-level 1-day performance for this tenant's own
        tracked universe (AnalyticsSnapshot.sector grouped against
        real price-history returns), with the top movers driving each
        sector's move. Not a guaranteed full market-wide GICS
        breakdown -- see modules.market.sector_performance's
        coverage_note.
        """
        try:
            from modules.market.sector_performance import get_sector_performance

            if self.db is None:
                return {"available": False, "reason": "No database session available."}

            return get_sector_performance(self.db, tenant_id=tenant_id)

        except Exception:
            logger.exception("Failed to load sector performance | tenant_id=%s", tenant_id)
            return {"available": False, "reason": "This section failed to load."}

    def get_breadth_sentiment(self, *, tenant_id: str) -> dict[str, Any]:
        """
        VIX (current level + 1-day change), Treasury yields (2Y/10Y/
        30Y), and breadth (% of this tenant's tracked universe with a
        positive momentum score / uptrend) -- the same real macro data
        get_macro_dashboard() uses, plus a real (tenant-scoped, not
        NYSE-wide) breadth reading. No put/call ratio is included: no
        options-market-wide volume data source exists anywhere in this
        codebase, so this doesn't fabricate one.
        """
        try:
            from modules.market.macro_dashboard import _load_macro_snapshot

            snapshot = _load_macro_snapshot()

            vix_df = snapshot.get("vix_df")
            vix_summary = None
            if isinstance(vix_df, pd.DataFrame) and not vix_df.empty and "Contract" in vix_df.columns:
                vix_rows = vix_df[vix_df["Contract"] == "VIX"]
                if not vix_rows.empty:
                    vix_summary = _json_safe(vix_rows)[0]

            breadth = self._get_breadth(tenant_id) if self.db is not None else None

            return {
                "loaded_at": snapshot.get("loaded_at"),
                "vix": vix_summary,
                "vix_term_structure": _json_safe(vix_df),
                "yield_curve": _json_safe(snapshot.get("yield_df")),
                "breadth": breadth,
                "put_call_ratio": {
                    "available": False,
                    "reason": "No options-market-wide volume data source is configured.",
                },
            }

        except Exception:
            logger.exception("Failed to load breadth/sentiment data.")
            return {"available": False, "reason": "This section failed to load."}

    def _get_breadth(self, tenant_id: str) -> dict[str, Any] | None:
        try:
            from modules.analytics.snapshot_cache import get_latest_snapshots_df
            from modules.market.regime_engine import _breadth_from_snapshots

            df = get_latest_snapshots_df(self.db, tenant_id)
            pct_up, total = _breadth_from_snapshots(df)

            if pct_up is None:
                return None

            return {
                "pct_advancing": round(pct_up, 1),
                "symbol_count": total,
                "coverage_note": "Reflects this tenant's own tracked universe, not the full NYSE.",
            }

        except Exception:
            logger.exception("Failed to compute breadth | tenant_id=%s", tenant_id)
            return None

    def get_economic_calendar(self) -> dict[str, Any]:
        """
        Real, live US macro release calendar (CPI, GDP, employment,
        retail sales, PPI) from FRED. USD-only -- see
        ForexMacroCalendarEngine's own coverage_note for why (no live
        source is wired in for ECB/BOE/BOJ calendars).
        """
        try:
            from modules.forex.forex_macro_calendar_engine import get_forex_macro_calendar_engine

            engine = get_forex_macro_calendar_engine(self.db)
            return engine.calendar()

        except Exception:
            logger.exception("Failed to load economic calendar.")
            return {"available": False, "reason": "This section failed to load."}

    def get_watchlist_highlights(self, *, tenant_id: str) -> dict[str, Any]:
        """
        This tenant's watchlists, each symbol enriched with current
        price and 1-day % change from stored price history.
        """
        try:
            from api.services.watchlist_api_service import WatchlistAPIService
            from modules.market_data.price_history_service import load_close_matrix

            if self.db is None:
                return {"available": False, "reason": "No database session available."}

            base = WatchlistAPIService(self.db).list_watchlists(tenant_id=tenant_id)

            # Every unique symbol across every watchlist, fetched in
            # ONE query -- not one query per symbol per watchlist. Same
            # fix as modules.market.sector_performance's
            # _returns_for_symbols, for the same reason: each separate
            # load_price_history() call was a real network round-trip
            # against a remote/cloud database, fetching that symbol's
            # entire stored history for a value only its last two rows
            # are actually used for.
            all_symbols = sorted({
                symbol
                for wl in base.get("watchlists", [])
                for symbol in wl.get("symbols", [])
            })

            matrix = load_close_matrix(self.db, all_symbols) if all_symbols else None

            def _symbol_summary(symbol: str) -> dict[str, Any]:
                if matrix is None or matrix.empty or symbol not in matrix.columns:
                    return {"symbol": symbol, "available": False}

                closes = matrix[symbol].dropna()
                if len(closes) < 2:
                    return {"symbol": symbol, "available": False}

                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                pct_change = round(((last / prev) - 1.0) * 100.0, 2) if prev else None

                return {
                    "symbol": symbol,
                    "available": True,
                    "last_price": round(last, 2),
                    "pct_change_1d": pct_change,
                }

            enriched_watchlists = [
                {
                    "id": wl["id"],
                    "name": wl["name"],
                    "symbols": [_symbol_summary(symbol) for symbol in wl.get("symbols", [])],
                }
                for wl in base.get("watchlists", [])
            ]

            return {
                "tenant_id": tenant_id,
                "watchlist_count": len(enriched_watchlists),
                "watchlists": enriched_watchlists,
            }

        except Exception:
            logger.exception("Failed to load watchlist highlights | tenant_id=%s", tenant_id)
            return {"available": False, "reason": "This section failed to load."}

    def search_symbols(self, *, tenant_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """
        Prefix-match search against this tenant's own tracked universe
        symbols (modules.universe.models.UniverseSymbol). Not a
        general "any ticker in the world" search -- there is no
        market-wide symbol name/description database wired in
        anywhere in this codebase, only each tenant's own tracked
        symbol list.
        """
        try:
            from modules.universe.models import UniverseSymbol

            if self.db is None:
                return {"available": False, "reason": "No database session available."}

            query_upper = query.upper().strip()

            rows = (
                self.db.query(UniverseSymbol.symbol)
                .filter(UniverseSymbol.tenant_id == tenant_id)
                .filter(UniverseSymbol.symbol.like(f"{query_upper}%"))
                .distinct()
                .limit(limit)
                .all()
            )

            return {
                "query": query,
                "result_count": len(rows),
                "symbols": sorted({r[0] for r in rows}),
                "coverage_note": "Searches this tenant's own tracked universe only, not a market-wide symbol database.",
            }

        except Exception:
            logger.exception("Failed to search symbols | tenant_id=%s query=%s", tenant_id, query)
            return {"available": False, "reason": "This section failed to load."}

    def get_market_dashboard(self, *, tenant_id: str) -> dict[str, Any]:
        """
        Every Market tab section in one response, each failing
        independently. Sections run in parallel (not sequentially).

        DB-dependent sections (breadth's own breadth calculation,
        movers, sector performance, watchlist highlights) each run
        against their own fresh database session, not self.db --
        SQLAlchemy sessions aren't thread-safe, so sharing one across
        concurrent threads would risk corrupting query state rather
        than just being slow.

        Includes a "_section_timings_ms" field: how long each section
        actually took, in milliseconds. Two real, confirmed
        bottlenecks (sequential section execution; a sequential,
        multi-call FRED calendar loop) have already been found and
        fixed here, but a reported ~150s total load time persisted
        unchanged across both fixes -- this makes whichever section is
        actually slow directly visible, rather than requiring another
        round of guessing which one it is.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _with_fresh_session(fn_name: str, **kwargs):
            from modules.db.core import new_db_session

            db = new_db_session()
            try:
                service = MarketAPIService(db)
                return getattr(service, fn_name)(**kwargs)
            finally:
                try:
                    db.close()
                except Exception:
                    pass

        def _timed(fn_name, fn):
            start = time.time()
            try:
                return fn_name, fn(), round((time.time() - start) * 1000, 1), None
            except Exception as exc:
                return fn_name, None, round((time.time() - start) * 1000, 1), str(exc)

        tasks = {
            "market_status": lambda: self.get_market_status(),
            "major_indices": lambda: self.get_major_indices(),
            "economic_calendar": lambda: self.get_economic_calendar(),
            "breadth_sentiment": lambda: _with_fresh_session("get_breadth_sentiment", tenant_id=tenant_id),
            "movers": lambda: _with_fresh_session("get_market_movers", tenant_id=tenant_id),
            "sector_performance": lambda: _with_fresh_session("get_sector_performance", tenant_id=tenant_id),
            "watchlist_highlights": lambda: _with_fresh_session("get_watchlist_highlights", tenant_id=tenant_id),
        }

        result: dict[str, Any] = {"tenant_id": tenant_id}
        timings: dict[str, float] = {}
        overall_start = time.time()

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(_timed, name, fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    section_name, value, elapsed_ms, error = future.result()
                    timings[section_name] = elapsed_ms

                    if error is not None:
                        logger.exception(
                            "Market dashboard section failed | section=%s elapsed_ms=%s error=%s",
                            section_name, elapsed_ms, error,
                        )
                        result[section_name] = {"available": False, "reason": "This section failed to load."}
                    else:
                        result[section_name] = value

                except Exception:
                    logger.exception("Market dashboard section failed | section=%s", name)
                    result[name] = {"available": False, "reason": "This section failed to load."}
                    timings[name] = None

        overall_ms = round((time.time() - overall_start) * 1000, 1)
        timings["_total"] = overall_ms

        slowest = max(
            (k for k in timings if k != "_total"),
            key=lambda k: timings[k] or 0,
            default=None,
        )
        logger.info(
            "Market dashboard timing | tenant_id=%s total_ms=%s slowest_section=%s timings=%s",
            tenant_id, overall_ms, slowest, timings,
        )

        result["_section_timings_ms"] = timings

        return result