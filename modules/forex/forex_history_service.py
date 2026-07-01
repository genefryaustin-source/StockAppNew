"""
modules/forex/forex_history_service.py

Service facade for historical Forex market data.
Consumes the existing Forex provider router, persists normalized history to Postgres,
and returns DataFrames to Quant Research, Factor Models, Regime Intelligence, Alpha, and reports.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import pandas as pd

from modules.forex.forex_history_repository import ForexHistoryRepository, normalize_pair


DEFAULT_HISTORY_DAYS = 365 * 3
DEFAULT_INTERVAL = "1day"


class ForexHistoryService:
    def __init__(
        self,
        db: Any = None,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        router: Any = None,
    ):
        self.db = db
        self.tenant_id = tenant_id or "default"
        self.user_id = user_id
        self.portfolio_id = portfolio_id
        self.repository = ForexHistoryRepository(
            db=db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )
        if router is None:
            try:
                from modules.forex.providers.forex_provider_router import get_forex_provider_router
                router = get_forex_provider_router()
            except Exception:
                router = None
        self.router = router
        self._tables_ready = False

    def ensure_tables(self) -> None:
        if self._tables_ready:
            return

        self.repository.ensure_tables()
        self._tables_ready = True

    @staticmethod
    def default_start(days: int = DEFAULT_HISTORY_DAYS) -> date:
        return (datetime.now(timezone.utc) - timedelta(days=int(days))).date()

    @staticmethod
    def default_end() -> date:
        return datetime.now(timezone.utc).date()

    def fetch_from_router(
        self,
        pair: str,
        *,
        start_date: Any = None,
        end_date: Any = None,
        interval: str = DEFAULT_INTERVAL,
        force_refresh: bool = False,
        allowed_providers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if self.router is None:
            return {"status": "ERROR", "pair": pair, "error": "Forex provider router unavailable", "rows": []}
        if hasattr(self.router, "get_history"):
            return self.router.get_history(
                pair,
                start_date=start_date or self.default_start(),
                end_date=end_date or self.default_end(),
                interval=interval,
                force_refresh=force_refresh,
                allowed_providers=allowed_providers,
            )
        return {"status": "ERROR", "pair": pair, "error": "Forex provider router does not expose get_history(). Apply the updated router file from Phase 4.5.", "rows": []}

    def get_market_data(
            self,
            *,
            source: str,
            pairs: list[str],
            uploaded_file=None,
            interval: str = DEFAULT_INTERVAL,
            backfill_days: int = DEFAULT_HISTORY_DAYS,
            stale_after_hours: int = 24,
    ) -> pd.DataFrame:
        """
        Centralized historical market data loader.

        This is the ONLY method dashboards should call.
        """

        source = str(source or "PostgreSQL").strip()

        #
        # CSV Upload
        #
        if source == "Upload CSV":

            if uploaded_file is None:
                return pd.DataFrame()

            from modules.forex.forex_csv_importer import (
                import_price_history,
            )

            df = import_price_history(uploaded_file)

            #
            # Optional persistence
            #
            if not df.empty:
                try:
                    self.ensure_tables()
                    self.repository.upsert_history(
                        df.to_dict("records")
                    )
                except Exception:
                    pass

            return df

        #
        # Live Providers
        #
        elif source == "Live Providers":

            self.ensure_fresh_history(
                pairs=pairs,
                interval=interval,
                backfill_days=backfill_days,
            )

            return self.load_history(
                pairs,
                interval=interval,
            )

        #
        # PostgreSQL
        #
        history = self.load_history(
            pairs=pairs,
            interval=interval,
        )

        #
        # Existing history found
        #
        if not history.empty:
            return history

        #
        # Database empty (or missing requested history)
        # Refresh providers and persist into PostgreSQL
        #
        self.ensure_fresh_history(
            pairs=pairs,
            interval=interval,
            stale_after_hours=stale_after_hours,
            backfill_days=backfill_days,
        )

        #
        # Reload from PostgreSQL after refresh
        #
        history = self.load_history(
            pairs=pairs,
            interval=interval,
        )

        if not history.empty:
            return history

        #
        # Final fallback
        #
        return pd.DataFrame(
            columns=[
                "pair",
                "symbol",
                "asof",
                "interval",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "provider",
            ]
        )
    def refresh_pair(
        self,
        pair: str,
        *,
        start_date: Any = None,
        end_date: Any = None,
        interval: str = DEFAULT_INTERVAL,
        force_refresh: bool = False,
        allowed_providers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if not self._tables_ready:
            self.ensure_tables()
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        pair = normalize_pair(pair)
        start_date = start_date or self.default_start()
        end_date = end_date or self.default_end()
        payload = self.fetch_from_router(
            pair,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            force_refresh=force_refresh,
            allowed_providers=allowed_providers,
        )
        rows = payload.get("rows") or payload.get("history") or payload.get("data") or []
        provider = payload.get("provider")
        inserted = 0
        status = "completed"
        message = payload.get("error") or ""
        try:

            inserted = self.repository.upsert_history(rows, provider=provider, interval=interval)
            if payload.get("error"):
                status = "warning"
            elif not rows:
                status = "empty"
        except Exception as exc:
            status = "error"
            message = str(exc)
        self.repository.log_refresh(
            pair=pair,
            interval=interval,
            provider=provider,
            requested_start=start_date,
            requested_end=end_date,
            rows_received=len(rows),
            rows_inserted=inserted,
            status=status,
            message=message,
            started_at=started,
        )
        return {
            "status": status,
            "pair": pair,
            "provider": provider,
            "interval": interval,
            "requested_start": str(start_date),
            "requested_end": str(end_date),
            "rows_received": len(rows),
            "rows_inserted": inserted,
            "message": message,
            "failover_errors": payload.get("failover_errors") or [],
        }

    def refresh_universe(
        self,
        pairs: Iterable[str],
        *,
        start_date: Any = None,
        end_date: Any = None,
        interval: str = DEFAULT_INTERVAL,
        force_refresh: bool = False,
        allowed_providers: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        results = []
        for pair in pairs:
            results.append(self.refresh_pair(
                pair,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                force_refresh=force_refresh,
                allowed_providers=allowed_providers,
            ))
        return {
            "status": "completed",
            "pairs": len(results),
            "rows_inserted": sum(int(r.get("rows_inserted") or 0) for r in results),
            "rows_received": sum(int(r.get("rows_received") or 0) for r in results),
            "results": results,
        }

    def load_history(
        self,
        pairs: Optional[Iterable[str]] = None,
        *,
        start: Any = None,
        end: Any = None,
        interval: str = DEFAULT_INTERVAL,
        limit: int = 20000,
    ) -> pd.DataFrame:
        return self.repository.load_history(pairs, start=start, end=end, interval=interval, limit=limit)

    def ensure_fresh_history(
        self,
        pairs: Iterable[str],
        *,
        interval: str = DEFAULT_INTERVAL,
        stale_after_hours: int = 24,
        backfill_days: int = DEFAULT_HISTORY_DAYS,
    ) -> dict[str, Any]:
        self.ensure_tables()
        end_date = self.default_end()
        refreshed = []
        skipped = []
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=int(stale_after_hours))
        for pair in pairs:
            latest = self.repository.latest_asof(pair, interval=interval)
            latest_dt = latest if isinstance(latest, datetime) else None
            if latest_dt is not None and latest_dt >= cutoff:
                skipped.append({"pair": normalize_pair(pair), "latest_asof": str(latest_dt)})
                continue
            start_date = latest_dt.date() if isinstance(latest_dt, datetime) else None
            if start_date is None:
                start_date = (datetime.now(timezone.utc) - timedelta(days=int(backfill_days))).date()
            refreshed.append(self.refresh_pair(pair, start_date=start_date, end_date=end_date, interval=interval, force_refresh=True))
        return {
            "status": "completed",
            "refreshed": len(refreshed),
            "skipped": len(skipped),
            "rows_inserted": sum(int(r.get("rows_inserted") or 0) for r in refreshed),
            "refreshed_rows": refreshed,
            "skipped_rows": skipped,
        }

    def coverage(self) -> list[dict[str, Any]]:
        return self.repository.coverage()


def get_forex_history_service(
    db: Any = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    router: Any = None,
) -> ForexHistoryService:
    return ForexHistoryService(db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id, router=router)
