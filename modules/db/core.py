import os
from datetime import datetime, UTC
import streamlit as st
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from models.base import Base
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------
# Database URL
# ---------------------------------------------------





DB_URL = st.secrets["DATABASE_URL"]







# ---------------------------------------------------
# Engine
# ---------------------------------------------------

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_reset_on_return="rollback",
    echo=False,
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

        db.rollback()

        st.error(...)



    # PostgreSQL tenant migration
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE tenants
                ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1
            """))
        print("TENANT is_active migration complete")
    except Exception as e:
        print("TENANT is_active migration skipped:", e)

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

