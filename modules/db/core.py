import os
from datetime import datetime, UTC

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from models.base import Base
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------
# Database URL
# ---------------------------------------------------

DB_PATH = os.path.join(os.getcwd(), "stockapp.db")

DB_URL = f"sqlite:///{DB_PATH}"

print("=" * 80)
print("DATABASE DEBUG")
print("CWD:", os.getcwd())
print("DB PATH:", DB_PATH)
print("ABS DB PATH:", os.path.abspath(DB_PATH))
print("DB EXISTS:", os.path.exists(DB_PATH))

if os.path.exists(DB_PATH):
    try:
        print("DB SIZE:", os.path.getsize(DB_PATH))
        print(
            "DB MODIFIED:",
            datetime.fromtimestamp(
                os.path.getmtime(DB_PATH)
            )
        )
    except Exception as e:
        print("DB FILE INFO ERROR:", e)

print("DB URL:", DB_URL)
print("=" * 80)

# ---------------------------------------------------
# Engine
# ---------------------------------------------------

engine = create_engine(
    DB_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    poolclass=StaticPool,
    echo=False
)

print("=" * 80)
print("SQLALCHEMY URL:", engine.url)
print("DATABASE FILE:", DB_PATH)
print("=" * 80)

# ---------------------------------------------------
# SQLite Performance + Lock Fixes
# ---------------------------------------------------

@event.listens_for(engine, "connect")
def enable_sqlite_wal(dbapi_connection, connection_record):

    cursor = dbapi_connection.cursor()

    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA cache_size=10000")

    cursor.close()

# ---------------------------------------------------
# Session
# ---------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False  # disables this entire class of bugs
)


# ---------------------------------------------------
# Init Database
# ---------------------------------------------------

def init_database():

    import modules.db.models
    import modules.institutional.models
    import modules.analytics.models
    import modules.alerts.models
    import modules.universe.models
    import modules.jobs.models
    import modules.market_data.models
    import modules.analytics.strategy_models
    import models.trading

    # Create all tables from models first
    Base.metadata.create_all(bind=engine)
    print("=" * 80)
    print("REGISTERED TABLES")
    for t in sorted(Base.metadata.tables.keys()):
        print(t)
    print("=" * 80)

    # ---------------------------------------------------
    # Database Health Check
    # ---------------------------------------------------

    try:
        with engine.connect() as conn:

            tenant_count = conn.execute(
                text("SELECT COUNT(*) FROM tenants")
            ).scalar()

            user_count = conn.execute(
                text("SELECT COUNT(*) FROM users")
            ).scalar()

            print("=" * 80)
            print("DATABASE CONTENTS")
            print("TENANTS:", tenant_count)
            print("USERS:", user_count)
            print("=" * 80)

    except Exception as e:
        print("DATABASE CONTENT CHECK FAILED:", e)

    # Safe migrations
    migrations = [
        # users
        "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN updated_at TEXT",

        # universes
        "ALTER TABLE universes ADD COLUMN description TEXT",
        "ALTER TABLE universes ADD COLUMN created_by_user_id VARCHAR",
        "ALTER TABLE universes ADD COLUMN updated_at TEXT",

        # tenants
        "ALTER TABLE tenants ADD COLUMN updated_at TEXT",
        "ALTER TABLE tenants ADD COLUMN tenant_id VARCHAR",
        "ALTER TABLE tenants ADD COLUMN description TEXT",
        "ALTER TABLE tenants ADD COLUMN is_active INTEGER DEFAULT 1",
    ]

    with engine.connect() as conn:

        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

# ---------------------------------------------------
# UTC Helper
# ---------------------------------------------------

@event.listens_for(engine, "connect")
def set_sqlite_utc(dbapi_connection, connection_record):

    dbapi_connection.create_function(
        "utcnow",
        0,
        lambda: datetime.now(UTC).isoformat()
    )