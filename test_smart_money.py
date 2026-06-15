# test_smart_money.py

from modules.db.core import SessionLocal
from modules.smart_money.smart_money_service import (
    fetch_finnhub_insider_transactions,
    upsert_insider_transactions,
)

db = SessionLocal()

try:
    insiders = fetch_finnhub_insider_transactions("NVDA")

    print("FETCHED:", len(insiders))

    inserted = upsert_insider_transactions(
        db,
        insiders[:10]
    )

    print("INSERTED:", inserted)

finally:
    db.close()