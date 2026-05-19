import sqlite3

DB_FILE = "stockapp.db"


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols


def add_column(cursor, table, column, definition):
    if not column_exists(cursor, table, column):
        print(f"Adding {table}.{column}")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        print(f"OK {table}.{column}")


def repair_earnings_events(cursor):

    # core event fields
    add_column(cursor, "earnings_events", "event_date", "DATETIME")
    add_column(cursor, "earnings_events", "earnings_date", "DATETIME")
    add_column(cursor, "earnings_events", "time_of_day", "TEXT")

    # EPS
    add_column(cursor, "earnings_events", "eps_actual", "REAL")
    add_column(cursor, "earnings_events", "eps_estimate", "REAL")
    add_column(cursor, "earnings_events", "eps_est", "REAL")

    # Revenue
    add_column(cursor, "earnings_events", "rev_actual", "REAL")
    add_column(cursor, "earnings_events", "rev_est", "REAL")

    add_column(cursor, "earnings_events", "revenue_actual", "REAL")
    add_column(cursor, "earnings_events", "revenue_estimate", "REAL")
    add_column(cursor, "earnings_events", "rev_estimate", "REAL")

    # metadata
    add_column(cursor, "earnings_events", "source", "TEXT")


def repair_financial_periods(cursor):

    add_column(cursor, "financial_periods", "source", "TEXT")
    add_column(cursor, "financial_periods", "ebitda", "REAL")

    add_column(cursor, "financial_periods", "operating_cash_flow", "REAL")
    add_column(cursor, "financial_periods", "capex", "REAL")
    add_column(cursor, "financial_periods", "free_cash_flow", "REAL")

    add_column(cursor, "financial_periods", "cash", "REAL")
    add_column(cursor, "financial_periods", "total_debt", "REAL")


def repair_jobs(cursor):

    add_column(cursor, "jobs", "done", "INTEGER")
    add_column(cursor, "jobs", "total", "INTEGER")

    add_column(cursor, "jobs", "payload", "TEXT")
    add_column(cursor, "jobs", "logs", "TEXT")

    add_column(cursor, "jobs", "error", "TEXT")


def main():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("\nRepairing database schema...\n")

    repair_earnings_events(cursor)
    repair_financial_periods(cursor)
    repair_jobs(cursor)

    conn.commit()
    conn.close()

    print("\nSchema repair complete.\n")


if __name__ == "__main__":
    main()