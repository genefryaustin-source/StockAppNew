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
    import modules.universe.models
    import modules.jobs.models
    import modules.market_data.models
    import modules.analytics.strategy_models

    # Create all tables from models first
    Base.metadata.create_all(bind=engine)

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

from datetime import datetime, UTC

@event.listens_for(engine, "connect")
def set_sqlite_utc(dbapi_connection, connection_record):
    dbapi_connection.create_function(
        "utcnow",
        0,
        lambda: datetime.now(UTC).isoformat()
    )