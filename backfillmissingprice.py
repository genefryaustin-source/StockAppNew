from sqlalchemy import text
from modules.db.core import SessionLocal
from modules.market_data.service import massive_fetch_ohlc
from modules.market_data.price_history_service import store_price_history
import time

db = SessionLocal()

rows = db.execute(text("""
SELECT symbol
FROM universe_equities
WHERE symbol NOT IN (
    SELECT DISTINCT symbol FROM price_history
)
""")).fetchall()

symbols = [r[0] for r in rows]

print("Missing symbols:", len(symbols))

for sym in symbols:

    retry = True

    while retry:

        try:

            df = massive_fetch_ohlc(sym, period="5y")

            if df is None or df.empty:
                print("No data:", sym)
                break

            df = df.set_index("Date")

            # remove old rows to avoid UNIQUE constraint errors
            db.execute(text("DELETE FROM price_history WHERE symbol = :s"), {"s": sym})
            db.commit()

            store_price_history(db, sym, df)

            print("Inserted:", sym, len(df))

            time.sleep(0.6)   # safe rate

            retry = False

        except Exception as e:

            if "429" in str(e):
                print("Rate limited... sleeping 60 seconds")
                time.sleep(60)
            else:
                print("Failed:", sym, e)
                retry = False