from __future__ import annotations

import time
import random
from typing import List

from sqlalchemy.orm import Session

from modules.market_data.service import massive_fetch_ohlc
from modules.market_data.price_history_service import store_price_history


# ---------------------------------------
# Safe fetch with retry + backoff
# ---------------------------------------

def fetch_with_retry(symbol: str, retries: int = 5):

    delay = 1.5

    for attempt in range(retries):
        try:
            df = massive_fetch_ohlc(symbol, period="5d")

            if df is not None and not df.empty:
                return df

        except Exception as e:

            msg = str(e)

            # Handle rate limits
            if "429" in msg or "Too Many Requests" in msg:
                sleep_time = delay + random.uniform(0.5, 2.0)
                print(f"[RATE LIMIT] {symbol} retrying in {sleep_time:.1f}s")
                time.sleep(sleep_time)
                delay *= 2
                continue

            print(f"[ERROR] {symbol} {e}")
            return None

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

            # Progress callback for UI
            if progress_callback:
                progress_callback(i + 1, total, sym)

            # Throttle to avoid API bans
            time.sleep(0.12)

        except Exception as e:
            print(f"[FAIL] {sym}: {e}")
            failed += 1

    return {
        "total": total,
        "updated": updated,
        "failed": failed,
        "skipped": skipped,
        "updated_symbols": updated_symbols,
    }