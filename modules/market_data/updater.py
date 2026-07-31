from __future__ import annotations

import logging
import time
from typing import List

from sqlalchemy.orm import Session


from modules.market_data.price_history_service import store_price_history
from modules.market_data.provider_router import (
    get_provider_router,
    is_rate_limit_error,
)

logger = logging.getLogger(__name__)


from modules.utils.config import get_secret
from modules.market_data.providers.marketdata_provider import (
    get_history as marketdata_history,
    MarketDataCreditLimitException,
    MarketDataRateLimitException,
)

from modules.market_data.providers.finnhub_provider import (
    get_history as finnhub_history,
    FinnhubAccessException,
)

from modules.market_data.providers.alpha_vantage_provider import (
    get_history as alpha_history
)

from modules.market_data.providers.twelvedata_provider import (
    get_history as twelvedata_history,
    TwelveDataRateLimitException,
)

from modules.market_data.providers.yahoo import (
    fetch_ohlcv as yahoo_history
)

from modules.market_data.providers.polygon import (
    fetch_ohlcv as polygon_history,
    PolygonRateLimitException,
)

# ---------------------------------------
# Safe fetch with retry + backoff
# ---------------------------------------

def fetch_with_retry(symbol: str, retries: int = 2):
    router = get_provider_router()

    polygon_api_key = get_secret("POLYGON_API_KEY")

    providers = [
        (
            "POLYGON",
            lambda: polygon_history(
                symbol,
                period="5d",
                interval="1d",
                api_key=polygon_api_key,
                timeout=30,
            ),
        ),
        (
            "MARKETDATA",
            lambda: marketdata_history(symbol, period="5d", interval="1d"),
        ),
        (
            "FINNHUB",
            lambda: finnhub_history(symbol, period="5d", interval="D"),
        ),
        (
            "ALPHA_VANTAGE",
            lambda: alpha_history(symbol, period="5d", interval="1d"),
        ),
        (
            "TWELVEDATA",
            lambda: twelvedata_history(symbol, period="5d", interval="1day"),
        ),
        (
            "YAHOO",
            lambda: yahoo_history(symbol, period="5d"),
        ),
    ]

    for provider_name, provider_func in providers:
        router.register_provider(provider_name)

        # The key fix: check the SHARED router's availability, not a
        # local, per-call variable. Once this provider is cooling
        # down from a rate limit or a run of consecutive failures --
        # from THIS symbol or any earlier one in the same batch --
        # every subsequent symbol correctly skips straight past it
        # instead of hammering an already-known-bad provider again.
        if not router.is_available(provider_name):
            continue

        for attempt in range(retries):
            try:
                router.wait_for_provider(provider_name)
                start = time.time()

                df = provider_func()

                if df is not None and not df.empty:
                    router.mark_success(
                        provider_name,
                        latency_ms=(time.time() - start) * 1000,
                    )
                    return df

                # An empty result is NOT reliably "this symbol
                # genuinely has no data" -- confirmed several provider
                # functions (marketdata_history in particular) swallow
                # HTTP errors, including 429 rate limits, internally
                # and return an empty DataFrame instead of raising.
                # Treating empty as "not a failure" let an
                # already-rate-limited provider get silently retried
                # for every remaining symbol in a batch with the
                # router's cooldown never triggering. Counting it
                # toward the same consecutive-failure cooldown as a
                # real exception is the safer default: the cost of a
                # genuinely-empty symbol nudging a health score that
                # recovers on the next success is far lower than the
                # cost of hammering an exhausted provider thousands of
                # times.
                router.mark_failure(provider_name)
                break

            except PolygonRateLimitException:
                router.mark_rate_limited(provider_name, cooldown_minutes=15)
                break

            except MarketDataCreditLimitException as e:
                # Same rationale as service.py's identical handling:
                # account-level credit/quota exhaustion, not a
                # transient rate limit -- a short cooldown would just
                # mean repeated, guaranteed-to-fail retries across
                # every remaining symbol in a multi-thousand-symbol
                # batch.
                router.mark_rate_limited(provider_name, cooldown_minutes=360)
                logger.warning("MarketData credit limit reached, cooling down 6h: %s", e)
                break

            except MarketDataRateLimitException as e:
                router.mark_rate_limited(provider_name, cooldown_minutes=15)
                logger.debug("MarketData rate limited for %s: %s", symbol, e)
                break

            except FinnhubAccessException as e:
                # Same rationale as MarketData's credit-limit handling:
                # a 403 access error is a permanent plan/permission
                # issue, not a transient failure -- it will never
                # resolve on retry. Confirmed from real logs that
                # without this, the consecutive-failure counter just
                # climbed indefinitely (3, 4, 5... 40+) as the
                # provider kept getting retried roughly every 2
                # minutes for the entire remainder of a multi-hour run.
                router.mark_rate_limited(provider_name, cooldown_minutes=360)
                logger.warning("Finnhub access denied, cooling down 6h: %s", e)
                break

            except TwelveDataRateLimitException as e:
                # Short cooldown by design -- TwelveData's own docs
                # confirm this specific per-minute credit limit resets
                # at the start of the next minute.
                router.mark_rate_limited(provider_name, cooldown_minutes=2)
                logger.debug("TwelveData per-minute limit reached, cooling down 2min: %s", e)
                break

            except Exception as e:
                if is_rate_limit_error(e):
                    router.mark_rate_limited(provider_name, cooldown_minutes=15)
                    break
                router.mark_failure(provider_name)
                logger.debug("Provider %s failed for %s: %s", provider_name, symbol, e)
                continue

    return None


# ---------------------------------------
# Main updater
# ---------------------------------------

def update_latest_prices(
    db: Session,
    symbols: List[str],
    progress_callback=None,
):
    total = len(symbols)

    updated = 0
    updated_symbols = []
    failed = 0
    skipped = 0
    BATCH_COMMIT = 25
    for i, sym in enumerate(symbols):

        try:
            df = fetch_with_retry(sym)

            if df is None or df.empty:
                skipped += 1
                continue

            df = df.reset_index()

            store_price_history(db, sym, df)
            updated += 1
            updated_symbols.append(sym)

            if updated % BATCH_COMMIT == 0:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

            # Progress callback for UI
            if progress_callback:
                progress_callback(i + 1, total, sym)

        except Exception as e:

            try:

                db.rollback()

            except Exception:

                pass

            logger.warning("Price update failed for %s: %s", sym, e)

            failed += 1

        finally:
            # Throttle to avoid API bans -- applies regardless of
            # success/skip/failure. Previously this only fired on the
            # success path, meaning exactly when a provider was
            # failing or rate-limited (the case throttling matters
            # most for) there was no delay at all between symbols.
            time.sleep(0.50)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "total": total,
        "updated": updated,
        "failed": failed,
        "skipped": skipped,
        "updated_symbols": updated_symbols,
    }