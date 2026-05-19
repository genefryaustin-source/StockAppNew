from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from typing import List
import time

from modules.db.core import SessionLocal
from modules.market_data.price_history_service import get_price_history


# ---------------------------------------------------
# Worker
# ---------------------------------------------------

def _backfill_symbol(symbol: str):

    db = SessionLocal()

    try:

        df = get_price_history(db, symbol)

        if df is None or df.empty:
            return symbol, False

        return symbol, True

    except Exception as e:

        print("Backfill error:", symbol, e)

        return symbol, False

    finally:

        db.close()


# ---------------------------------------------------
# Batch Backfill
# ---------------------------------------------------

def backfill_price_history(symbols: List[str], max_workers: int = 12):

    if not symbols:
        return

    symbols = [s.strip().upper() for s in symbols if s]

    total = len(symbols)
    completed = 0
    success = 0

    print(f"Starting price history backfill for {total} symbols")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {
            executor.submit(_backfill_symbol, sym): sym
            for sym in symbols
        }

        for future in as_completed(futures):

            sym = futures[future]

            try:

                symbol, ok = future.result()

                completed += 1

                if ok:
                    success += 1

            except Exception:

                completed += 1

            if completed % 50 == 0:

                print(
                    f"Backfill progress: {completed}/{total} "
                    f"({round(completed/total*100,1)}%)"
                )

            # small pause to avoid API throttling
            time.sleep(0.01)

    print(
        f"Backfill finished: {success}/{total} successful"
    )

    return {
        "symbols": total,
        "success": success,
    }