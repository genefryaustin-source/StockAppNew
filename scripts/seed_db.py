import sqlite3
import os

TABLES_TO_SEED = [
    "universes",
    "universe_symbols", 
    "universe_equities",
    "universe_analytics_cache",
    "users",
    "tenants",
]

def is_seeded(conn: sqlite3.Connection) -> bool:
    """Check if any of the seed tables already have data."""
    cursor = conn.cursor()
    for table in TABLES_TO_SEED:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"[seeder] {table} already has {count} rows — skipping seed.")
                return True
        except Exception:
            pass
    return False

def run_seed(db_path: str, seed_file: str):
    """Run the seed SQL file if tables are empty."""
    if not os.path.exists(seed_file):
        print(f"[seeder] Seed file not found: {seed_file}")
        return

    conn = sqlite3.connect(db_path)
    try:
        if is_seeded(conn):
            return

        print("[seeder] Tables are empty — running seed...")
        with open(seed_file, "r", encoding="utf-8") as f:
            sql = f.read()

        conn.executescript(sql)
        conn.commit()
        print("[seeder] ✅ Seed complete.")

    except Exception as e:
        print(f"[seeder] ❌ Seed failed: {e}")
    finally:
        conn.close()