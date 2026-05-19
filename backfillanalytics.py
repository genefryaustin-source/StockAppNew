from sqlalchemy import text
from modules.db.core import SessionLocal
from modules.analytics.runner import run_full_analytics
import time

db = SessionLocal()

TENANT_ID = "default_tenant"

rows = db.execute(text("""
SELECT symbol
FROM universe_equities
WHERE symbol NOT IN (
    SELECT DISTINCT symbol
    FROM analytics_snapshots
)
""")).fetchall()

symbols = [r[0] for r in rows]

print("Symbols missing analytics:", len(symbols))

for sym in symbols:

    try:

        row = run_full_analytics(db, TENANT_ID, sym)

        if row is None:
            print("Skipped:", sym)
            continue

        print("Computed:", sym)

        time.sleep(0.02)

    except Exception as e:

        print("Failed:", sym, e)