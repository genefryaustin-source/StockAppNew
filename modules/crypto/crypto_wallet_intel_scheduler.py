"""
modules/crypto/crypto_wallet_intel_scheduler.py

Sprint CR-1: Autonomous Wallet Intelligence -- scheduled background
refresh, replacing the manual-button-only sanctions cache refresh and
discovery cycle.

Follows the exact same pattern already established elsewhere in this
app (modules/portfolio/scheduler_service.py's PortfolioScheduler):
a daemon threading.Thread running a sleep/wake loop, with a DB-backed
heartbeat -- necessary because a background thread's in-memory
running/stopped state isn't visible to a different Streamlit session
or worker process looking at the UI, but a DB row is.

Two jobs, run on independent intervals within the same loop:

  1. Sanctions cache refresh (crypto_sanctions_service.py) -- global,
     not tenant-specific, since OFAC's list applies to everyone.
  2. Discovery cycle (crypto_wallet_discovery_engine.py) -- run once
     per tenant that has an Etherscan key configured, found via a
     direct query against tenant_api_keys (confirmed its real
     columns: tenant_id, provider, is_active) rather than
     list_tenant_keys(), whose own signature scopes it to a single
     already-known tenant_id, not "every tenant" -- calling it with
     tenant_id=None would filter for rows where tenant_id IS NULL,
     which is a real, meaningful difference from "all tenants", not a
     detail to gloss over.

Both underlying operations were already confirmed idempotent (a
sanctions cache replace is a full, correct snapshot replace; a
discovery cycle's already_flagged check prevents re-flagging the same
wallet twice) -- so even if this scheduler's thread and a manual
button click from the UI happen to overlap, the worst case is
redundant work, not corrupted or duplicated data.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


def _list_tenants_with_provider_key(db, provider: str) -> List[str]:
    """
    Direct query against tenant_api_keys for every distinct,
    active tenant that has a key configured for the given provider --
    confirmed the real column names (tenant_id, provider, is_active)
    against the actual TenantApiKey model rather than assuming.
    """
    from sqlalchemy import text

    rows = db.execute(text("""
        SELECT DISTINCT tenant_id FROM tenant_api_keys
        WHERE provider = :provider AND is_active = 1
    """), {"provider": provider}).fetchall()
    return [row[0] for row in rows]


class CryptoWalletIntelScheduler:
    def __init__(self, db_session_factory):
        """
        db_session_factory: a zero-argument callable that returns a
        fresh DB session (e.g. a SQLAlchemy sessionmaker) -- NOT a
        single, shared session. A background thread that outlives any
        one Streamlit request needs to open and close its own short-
        lived sessions per cycle, the same way get_provider_key()
        already does when no session is supplied to it, rather than
        holding one session open indefinitely across sleep() calls.
        """
        self.db_session_factory = db_session_factory
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self, *, sanctions_interval_seconds: int = 6 * 3600, discovery_interval_seconds: int = 3600) -> None:
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(sanctions_interval_seconds, discovery_interval_seconds),
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def _run_loop(self, sanctions_interval_seconds: int, discovery_interval_seconds: int) -> None:
        last_sanctions_run = 0.0
        last_discovery_run = 0.0

        # Sleep in short ticks rather than one long time.sleep(interval)
        # so stop() takes effect promptly instead of waiting out
        # however many hours are left on the current interval.
        tick_seconds = 30

        while self.running:
            now = time.time()

            if now - last_sanctions_run >= sanctions_interval_seconds:
                self._run_sanctions_refresh()
                last_sanctions_run = now

            if now - last_discovery_run >= discovery_interval_seconds:
                self._run_discovery_for_all_tenants()
                last_discovery_run = now

            time.sleep(tick_seconds)

    def _run_sanctions_refresh(self) -> None:
        from modules.crypto.crypto_sanctions_service import fetch_and_parse_sdn_addresses
        from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository

        db = self.db_session_factory()
        try:
            repo = get_crypto_wallet_intelligence_repository(db=db)
            result = fetch_and_parse_sdn_addresses()

            if result["status"] == "ok":
                inserted = repo.replace_sanctioned_addresses(result["rows"])
                repo.record_job_heartbeat(
                    "sanctions_refresh", status="ok", message=f"{inserted} address(es) loaded",
                )
            else:
                repo.record_job_heartbeat(
                    "sanctions_refresh", status="error", message=result.get("message"),
                )

        except Exception as exc:
            logger.warning("Scheduled sanctions refresh failed: %s", exc)
            try:
                get_crypto_wallet_intelligence_repository(db=db).record_job_heartbeat(
                    "sanctions_refresh", status="error", message=str(exc),
                )
            except Exception:
                pass

        finally:
            try:
                db.close()
            except Exception:
                pass

    def _run_discovery_for_all_tenants(self) -> None:
        from modules.crypto.crypto_wallet_discovery_engine import run_discovery_cycle
        from modules.crypto.crypto_wallet_intelligence_repository import get_crypto_wallet_intelligence_repository
        from modules.admin.tenant_api_keys import get_provider_key

        db = self.db_session_factory()
        try:
            repo = get_crypto_wallet_intelligence_repository(db=db)

            # Only tenants that have actually configured an Etherscan
            # key can run discovery -- not every tenant using this app
            # necessarily uses Wallet Intelligence at all, and running
            # this for tenants without a key would just be a
            # guaranteed per-tenant failure on every cycle.
            tenant_ids = _list_tenants_with_provider_key(db, "etherscan")

            total_new = 0
            errors = []

            for tenant_id in tenant_ids:
                api_key = get_provider_key("etherscan", db=db, tenant_id=tenant_id)
                if not api_key:
                    continue

                result = run_discovery_cycle(
                    db=db, tenant_id=tenant_id, chain="ethereum", api_key=api_key,
                )
                if result["status"] == "ok":
                    total_new += result["new_wallets_flagged"]
                else:
                    errors.append(f"{tenant_id}: {result.get('message')}")

            repo.record_job_heartbeat(
                "discovery_cycle",
                status="ok" if not errors else "error",
                message=(
                    f"{total_new} new wallet(s) flagged across {len(tenant_ids)} tenant(s)"
                    + (f"; {len(errors)} error(s)" if errors else "")
                ),
            )

        except Exception as exc:
            logger.warning("Scheduled discovery cycle failed: %s", exc)
            try:
                get_crypto_wallet_intelligence_repository(db=db).record_job_heartbeat(
                    "discovery_cycle", status="error", message=str(exc),
                )
            except Exception:
                pass

        finally:
            try:
                db.close()
            except Exception:
                pass


_SCHEDULER: Optional[CryptoWalletIntelScheduler] = None


def get_crypto_wallet_intel_scheduler(db_session_factory=None) -> Optional[CryptoWalletIntelScheduler]:
    global _SCHEDULER
    if _SCHEDULER is None and db_session_factory is not None:
        _SCHEDULER = CryptoWalletIntelScheduler(db_session_factory)
    return _SCHEDULER