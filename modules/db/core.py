import os
from datetime import datetime, UTC
import streamlit as st
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from models.base import Base
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------
# Database URL
# ---------------------------------------------------








try:
    DB_URL = st.secrets.get("DATABASE_URL")
except Exception:
    DB_URL = None

if not DB_URL:

    local_db = os.path.join(
        os.getcwd(),
        "stockapp.db"
    )

    DB_URL = f"sqlite:///{local_db}"

    print(
        f"[database] DATABASE_URL missing. "
        f"Using SQLite fallback: {local_db}"
    )







# ---------------------------------------------------
# Engine
# ---------------------------------------------------

if DB_URL.startswith("sqlite"):

    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
        future=True,
    )

else:

    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
        pool_recycle=180,
        pool_size=3,
        max_overflow=2,
        pool_timeout=30,
        pool_reset_on_return="rollback",
        echo=False,
        future=True,
    )




# ---------------------------------------------------
# Session
# ---------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
# ---------------------------------------------------
# Session Helper
# ---------------------------------------------------

def new_db_session():
    """
    Create a fresh SQLAlchemy session.

    Used by background services, provider health,
    analytics jobs, schedulers and autonomous workers.
    """
    return SessionLocal()
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

    # IPO / Pre-IPO models — imported so their tables are registered
    # with Base.metadata before create_all() runs.
    import modules.ipo.models          # IPOEvent, IPOWatchlistItem, IPOResearchNote
    import modules.preipo.models       # PreIPOCompany, PreIPOFiling, PreIPOWatchlistItem
    from modules.ipo.news_service import IPONewsArticle  # noqa: F401 — ipo_news_articles table

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

        print("Database health check failed:", e)



    # Tenant table migrations -- portable across Postgres and SQLite.
    # "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" is Postgres-only syntax;
    # SQLite doesn't support the IF NOT EXISTS modifier on ADD COLUMN at
    # all, so that version silently failed (and was silently swallowed)
    # on SQLite. Checking column existence via inspect() first and using
    # plain ADD COLUMN works identically on both.
    try:
        inspector = inspect(engine)
        existing_cols_info = {c["name"]: c for c in inspector.get_columns("tenants")}
        existing_cols = set(existing_cols_info.keys())

        # IMPORTANT: each DDL type here must match the ORM's declared
        # Python type in modules/db/models.py exactly. SQLite's type
        # system is loose enough to silently tolerate a mismatch (e.g.
        # storing a Python bool into a column added as "INTEGER") --
        # Postgres is strict and raises DatatypeMismatch the moment the
        # ORM tries to UPDATE/INSERT through a session, since psycopg2
        # binds the value according to the ORM's type (Boolean), not
        # whatever the raw column actually is. This is exactly what
        # happened with api_grace_unlimited: it was added as INTEGER
        # here while the model declares it Boolean, and that mismatch
        # was invisible in SQLite testing the whole time. BOOLEAN/TRUE/
        # FALSE are valid, portable keywords on both engines (SQLite
        # just stores them as 0/1 under the hood).
        tenant_column_migrations = [
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("api_grace_unlimited", "BOOLEAN DEFAULT FALSE"),
            ("api_grace_days_override", "INTEGER"),
        ]

        for col_name, col_ddl in tenant_column_migrations:
            if col_name not in existing_cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col_name} {col_ddl}"))
                print(f"TENANT migration: added column '{col_name}'")

        # One-time corrective pass: on any database where the migration
        # above already ran with the old (wrong) INTEGER DDL, the
        # column exists now but with the wrong type -- adding it
        # correctly above won't fix an already-existing column, since
        # the ADD COLUMN only fires when the column is missing entirely.
        # Postgres has no implicit integer->boolean cast (it was removed
        # in 9.0), so this can't just be `::boolean` -- comparing against
        # 0 produces a real boolean safely, including for NULLs.
        # SQLite never had this surface as an error in the first place
        # (loose typing tolerates it), so this only needs to run, and
        # only CAN run, against Postgres.
        if engine.dialect.name == "postgresql":
            boolean_columns_to_fix = {
                "is_active": "TRUE",
                "api_grace_unlimited": "FALSE",
            }
            for col_name, default_literal in boolean_columns_to_fix.items():
                col_info = existing_cols_info.get(col_name)
                if col_info is None:
                    continue
                current_type = str(col_info.get("type", "")).upper()
                if "BOOL" in current_type:
                    continue  # already correct, nothing to do
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            f"ALTER TABLE tenants ALTER COLUMN {col_name} DROP DEFAULT"
                        ))
                        conn.execute(text(f"""
                            ALTER TABLE tenants
                            ALTER COLUMN {col_name} TYPE BOOLEAN
                            USING ({col_name} <> 0)
                        """))
                        conn.execute(text(
                            f"ALTER TABLE tenants ALTER COLUMN {col_name} "
                            f"SET DEFAULT {default_literal}"
                        ))
                    print(f"TENANT migration: corrected '{col_name}' column type to BOOLEAN")
                except Exception as e:
                    print(f"TENANT migration: could not correct '{col_name}' type:", e)

        print("TENANT column migrations complete")
    except Exception as e:
        print("TENANT column migrations skipped:", e)

    # Safe migrations
    #migrations = [
        # users
        #"ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        #"ALTER TABLE users ADD COLUMN created_at TEXT",
        #"ALTER TABLE users ADD COLUMN updated_at TEXT",

        # universes
        #"ALTER TABLE universes ADD COLUMN description TEXT",
        #"ALTER TABLE universes ADD COLUMN created_by_user_id VARCHAR",
        #"ALTER TABLE universes ADD COLUMN updated_at TEXT",

        # tenants
        #"ALTER TABLE tenants ADD COLUMN updated_at TEXT",
        #"ALTER TABLE tenants ADD COLUMN tenant_id VARCHAR",
        #"ALTER TABLE tenants ADD COLUMN description TEXT",
        #"ALTER TABLE tenants ADD COLUMN is_active INTEGER DEFAULT 1",
    #]

    #with engine.connect() as conn:

        #for sql in migrations:
            #try:
                #conn.execute(text(sql))
                #conn.commit()
            #except Exception:
                #pass