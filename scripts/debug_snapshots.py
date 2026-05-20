import sqlite3
import pandas as pd

con = sqlite3.connect("stockapp.db")

df = pd.read_sql("""
SELECT
    symbol,
    composite_score,
    signal,
    asof
FROM analytics_snapshots
ORDER BY asof DESC
LIMIT 500
""", con)

print(df)