from modules.db.core import SessionLocal
from modules.market_data.price_history_service import (
    get_symbols_with_short_history,
    force_backfill_symbol
)

db = SessionLocal()

symbols = get_symbols_with_short_history(db, min_rows=250)

print("Repairing", len(symbols), "symbols")

for sym in symbols:
    force_backfill_symbol(db, sym)

print("Repair complete")