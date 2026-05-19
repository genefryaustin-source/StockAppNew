import sqlite3
import os
import streamlit as st

TABLES_TO_SEED = [
    "universes",
    "universe_symbols",
    "universe_equities",
    "universe_analytics_cache",
    "users",
    "tenants",
]


def is_seeded(conn: sqlite3.Connection) -> bool:
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
    print(f"[seeder] Starting... db={db_path} seed={seed_file}")

    if not os.path.exists(seed_file):
        print(f"[seeder] ERROR: Seed file not found: {seed_file}")
        print(f"[seeder] Files in cwd: {os.listdir(os.getcwd())}")
        return

    print(f"[seeder] Seed file found, size={os.path.getsize(seed_file)}")

    conn = sqlite3.connect(db_path)
    try:
        if is_seeded(conn):
            return
        print("[seeder] Tables empty — running seed...")
        with open(seed_file, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        print("[seeder] Seed complete.")
    except Exception as e:
        print(f"[seeder] FAILED: {e}")
    finally:
        conn.close()