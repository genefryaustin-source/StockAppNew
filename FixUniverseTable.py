import sqlite3
import uuid

DB_PATH = "app.db"


def gen_uuid():
    return str(uuid.uuid4())


def main():

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("\n--- Universe Migration Starting ---\n")

    # --------------------------------------------------
    # Ensure tables exist
    # --------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS universes (
        id TEXT PRIMARY KEY,
        tenant_id TEXT,
        name TEXT,
        description TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS universe_symbols (
        id TEXT PRIMARY KEY,
        tenant_id TEXT,
        universe_id TEXT,
        symbol TEXT
    )
    """)

    conn.commit()

    # --------------------------------------------------
    # Detect legacy tables
    # --------------------------------------------------

    cur.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table'
    """)

    tables = [r[0] for r in cur.fetchall()]

    print("Tables found:")
    for t in tables:
        print(" -", t)

    # --------------------------------------------------
    # Find universes
    # --------------------------------------------------

    cur.execute("SELECT id,name FROM universes")
    universes = cur.fetchall()

    if not universes:
        print("\nNo universes exist. Creating default universe.")

        uid = gen_uuid()

        cur.execute(
            "INSERT INTO universes VALUES (?,?,?,?)",
            (uid, "default_tenant", "Default Universe", "")
        )

        conn.commit()

        universes = [(uid, "Default Universe")]

    print("\nUniverses:")
    for u in universes:
        print(u)

    # --------------------------------------------------
    # Detect orphan symbols
    # --------------------------------------------------

    print("\nChecking universe_symbols integrity...")

    cur.execute("""
    SELECT symbol FROM universe_symbols
    WHERE universe_id NOT IN (SELECT id FROM universes)
    """)

    orphan_symbols = cur.fetchall()

    if orphan_symbols:

        default_universe = universes[0][0]

        print(f"Fixing {len(orphan_symbols)} orphan symbols")

        for sym in orphan_symbols:

            cur.execute("""
            UPDATE universe_symbols
            SET universe_id = ?
            WHERE symbol = ?
            """, (default_universe, sym[0]))

    # --------------------------------------------------
    # Deduplicate symbols
    # --------------------------------------------------

    print("\nRemoving duplicate symbols...")

    cur.execute("""
    SELECT universe_id, symbol, COUNT(*)
    FROM universe_symbols
    GROUP BY universe_id, symbol
    HAVING COUNT(*) > 1
    """)

    duplicates = cur.fetchall()

    for universe_id, symbol, count in duplicates:

        print("Duplicate:", symbol, count)

        cur.execute("""
        DELETE FROM universe_symbols
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM universe_symbols
            WHERE universe_id=? AND symbol=?
        )
        """, (universe_id, symbol))

    conn.commit()

    # --------------------------------------------------
    # Normalize symbols to uppercase
    # --------------------------------------------------

    print("\nNormalizing symbol case...")

    cur.execute("""
    UPDATE universe_symbols
    SET symbol = UPPER(symbol)
    """)

    conn.commit()

    # --------------------------------------------------
    # Final counts
    # --------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM universe_symbols")
    total_symbols = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM universes")
    total_universes = cur.fetchone()[0]

    print("\n--- Migration Complete ---")
    print("Universes:", total_universes)
    print("Symbols:", total_symbols)

    conn.close()


if __name__ == "__main__":
    main()