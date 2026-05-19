import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------
# Database URL
# ---------------------------------------------------

DB_PATH = os.path.join(os.getcwd(), "stockapp.db")

DB_URL = f"sqlite:///{DB_PATH}"

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
# Base
# ---------------------------------------------------

Base = declarative_base()

# ---------------------------------------------------
# Init Database
# ---------------------------------------------------

def init_database():
    import modules.db.models
    import modules.institutional.models
    import modules.analytics.models
    import modules.alerts.models
    Base.metadata.create_all(bind=engine)

    # ---------------------------------------------------
    # Safe Migrations - add missing columns if needed
    # ---------------------------------------------------
    migrations = [
        "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN updated_at TEXT",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"[migration] Applied: {sql}")
            except Exception:
                pass  # Column already exists, skip

from datetime import datetime, UTC

@event.listens_for(engine, "connect")
def set_sqlite_utc(dbapi_connection, connection_record):
    dbapi_connection.create_function(
        "utcnow",
        0,
        lambda: datetime.now(UTC).isoformat()
    )