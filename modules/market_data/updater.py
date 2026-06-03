from __future__ import annotations

import time
import random
from typing import List

from sqlalchemy.orm import Session


from modules.market_data.price_history_service import store_price_history



from modules.utils.config import get_secret
from modules.market_data.providers.marketdata_provider import (
    get_history as marketdata_history
)

from modules.market_data.providers.finnhub_provider import (
    get_history as finnhub_history
)

from modules.market_data.providers.alpha_vantage_provider import (
    get_history as alpha_history
)

from modules.market_data.providers.twelvedata_provider import (
    get_history as twelvedata_history
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
    POLYGON_AVAILABLE = True

    POLYGON_API_KEY = get_secret("POLYGON_API_KEY")

    providers = []

    if POLYGON_AVAILABLE:
        providers.append(
            (
                "POLYGON",
                lambda: polygon_history(
                    symbol,
                    period="5d",
                    interval="1d",
                    api_key=POLYGON_API_KEY,
                    timeout=30,
                ),
            )
        )

    providers.extend([
        (
            "MARKETDATA",
            lambda: marketdata_history(
                symbol,
                period="5d",
                interval="1d",
            ),
        ),
        (
            "FINNHUB",
            lambda: finnhub_history(
                symbol,
                period="5d",
                interval="D",
            ),
        ),
        (
            "ALPHAVANTAGE",
            lambda: alpha_history(
                symbol,
                period="5d",
                interval="1d",
            ),
        ),
        (
            "TWELVEDATA",
            lambda: twelvedata_history(
                symbol,
                period="5d",
                interval="1day",
            ),
        ),
        (
            "YAHOO",
            lambda: yahoo_history(
                symbol,
                period="5d",
            ),
        ),
    ])

    for provider_name, provider_func in providers:

        for attempt in range(retries):

            try:

                df = provider_func()

                if df is not None and not df.empty:

                    print(
                        f"[SUCCESS] {symbol} "
                        f"via {provider_name}"
                    )

                    return df


            except PolygonRateLimitException:

                POLYGON_AVAILABLE = False

                print(

                    "[POLYGON DISABLED] "

                    "Provider entered cooldown."

                )

                break

            except Exception as e:

                print(
                    f"[FAIL] {provider_name} "
                    f"{symbol}: {e}"
                )

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
    print("=" * 80)
    print("UPDATE_LATEST_PRICES")
    print("SYMBOL COUNT:", len(symbols))
    print("FIRST 20:", symbols[:20])
    print("=" * 80)
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

            # Throttle to avoid API bans
            time.sleep(0.50)


        except Exception as e:

            try:

                db.rollback()

            except Exception:

                pass

            print(f"[FAIL] {sym}: {e}")

            failed += 1
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