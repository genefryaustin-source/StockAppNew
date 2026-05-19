from modules.db.core import SessionLocal
from modules.market_data.service import massive_fetch_ohlc
from modules.market_data.price_history_service import store_price_history

import time

db = SessionLocal()

symbols = [r[0] for r in db.execute("""
SELECT symbol FROM universe_equities
""").fetchall()]

print("Updating latest prices for", len(symbols), "symbols")

for i, sym in enumerate(symbols):

    try:
        df = massive_fetch_ohlc(sym, period="5d")

        if df is None or df.empty:
            continue

        df = df.reset_index()

        store_price_history(db, sym, df)

        if i % 100 == 0:
            print(f"{i}/{len(symbols)} updated")

        time.sleep(0.15)  # prevents rate limiting

    except Exception as e:
        print("Failed:", sym, e)

print("DONE")