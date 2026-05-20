import streamlit as st
import pandas as pd
from datetime import datetime, UTC
import time
import sys
import os
import sqlite3
import matplotlib

VERSION = "2.4.0"

st.set_page_config(page_title="Equity Research Terminal", layout="wide")

# ============================================================
# 0. DEV MODE FLAG (controls debug output)
# ============================================================
DEV_MODE = False  # Set True to show PRAGMA debug info

# ============================================================
# 1. ENGINE + TABLE INSPECTION (NO DELETIONS IN SAFE MODE)
# ============================================================
from modules.db.core import engine
from sqlalchemy import inspect as _inspect

_inspector = _inspect(engine)
_existing_tables = set(_inspector.get_table_names())

# Required tables for a healthy DB
REQUIRED_TABLES = {
    "users",
    "universes",
    "universe_symbols",
    "universe_equities",  # Option C compatibility table
    "tenants"
}

# We DO NOT delete the DB in safe mode
missing_required = [t for t in REQUIRED_TABLES if t not in _existing_tables]
if missing_required:
    print(f"[startup] Missing tables detected: {missing_required}")
else:
    print("[startup] All required tables present")

# ============================================================
# 2. CACHED DB SESSION (runs AFTER rebuild if needed)
# ============================================================
@st.cache_resource
def get_db():
    try:
        from modules.db.core import init_database, SessionLocal
        init_database()  # Creates tables if missing
        return SessionLocal()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()

# ============================================================
# 3. IMPORT MODELS + SERVICES
# ============================================================
try:
    import modules.db.models
    import modules.institutional.models
    import modules.analytics.models
    import modules.alerts.models
    import modules.universe.models  # includes UniverseEquity (Option C)
    import modules.jobs.models
    import modules.market_data.models
    import modules.analytics.strategy_models
    from modules.help.help_ui import render_help
    from modules.portfolio.nav_service import NavService
    from modules.portfolio.order_service import OrderService
    from modules.alerts.service import AlertService
except Exception as e:
    st.error(f"Critical module import failed: {e}")
    st.stop()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ============================================================
# 4. INITIALIZE DB + CREATE TABLES
# ============================================================
try:
    db = get_db()
except Exception as e:
    st.error(f"❌ Failed to initialize database: {e}")
    st.stop()

from models.base import Base
engine = db.get_bind()

# Create ALL tables including universe_equities (Option C)
Base.metadata.create_all(bind=engine)

# ============================================================
# 5. SAFE SCHEMA MIGRATIONS
# ============================================================
def safe_migration(sql, label):
    try:
        with engine.connect() as conn:
            conn.execute(sql)
            conn.commit()
        print(f"[migration] Applied: {label}")
    except Exception:
        pass  # Already applied or SQLite limitation

safe_migration("""
    ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1
""", "ALTER TABLE users ADD COLUMN is_active")

safe_migration("""
    ALTER TABLE users ADD COLUMN updated_at TEXT
""", "ALTER TABLE users ADD COLUMN updated_at")

safe_migration("""
    ALTER TABLE universes ADD COLUMN description TEXT
""", "ALTER TABLE universes ADD COLUMN description")

safe_migration("""
    ALTER TABLE universes ADD COLUMN created_by_user_id VARCHAR
""", "ALTER TABLE universes ADD COLUMN created_by_user_id")

safe_migration("""
    ALTER TABLE tenants ADD COLUMN updated_at TEXT
""", "ALTER TABLE tenants ADD COLUMN updated_at")

safe_migration("""
    ALTER TABLE tenants ADD COLUMN tenant_id VARCHAR
""", "ALTER TABLE tenants ADD COLUMN tenant_id")

safe_migration("""
    ALTER TABLE tenants ADD COLUMN description TEXT
""", "ALTER TABLE tenants ADD COLUMN description")

safe_migration("""
    ALTER TABLE tenants ADD COLUMN is_active INTEGER DEFAULT 1
""", "ALTER TABLE tenants ADD COLUMN is_active")

# ============================================================
# 6. SAFE SEEDING (only after tables exist)
# ============================================================
_db_path = os.path.join(os.getcwd(), "stockapp.db")
_seed_path = os.path.join(os.getcwd(), "seed_data.sql")

conn = sqlite3.connect(_db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
existing_tables = {row[0] for row in cur.fetchall()}

missing = [t for t in REQUIRED_TABLES if t not in existing_tables]

if missing:
    print(f"[seeder] Skipping seeding — missing tables: {missing}")
    conn.close()
else:
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    conn.close()

    if user_count == 0:
        print("[seeder] Seeding reference data...")
        try:
            conn = sqlite3.connect(_db_path, timeout=30)
            with open(_seed_path, "r", encoding="utf-8") as f:
                sql = f.read()

            inserts = "\n".join(
                line for line in sql.splitlines()
                if line.strip().upper().startswith("INSERT")
            )

            conn.executescript(inserts)
            conn.commit()
            conn.close()
            print("[seeder] Done.")
        except Exception as e:
            print(f"[seeder] FAILED: {e}")
            st.sidebar.error(f"Seeder failed: {e}")

# ============================================================
# 7. MARKET DATA SERVICE
# ============================================================
@st.cache_resource
def get_market_data_service():
    try:
        import modules.market_data.service as mds

        class MarketDataServiceAdapter:
            def get_quote(self, symbol: str):
                if hasattr(mds, "get_quote"):
                    return mds.get_quote(symbol)
                if hasattr(mds, "get_price"):
                    return {"price": mds.get_price(symbol)}
                if hasattr(mds, "fetch_price"):
                    return {"price": mds.fetch_price(symbol)}
                return None

        return MarketDataServiceAdapter()
    except Exception as e:
        st.warning(f"Market data service init warning: {e}")
        return None

market_data_service = get_market_data_service()

# ============================================================
# 8. AUTH GATE
# ============================================================
if DEV_MODE:
    if "user" not in st.session_state:
        st.session_state.user = {
            "user_id": "local_user",
            "tenant_id": "default_tenant",
            "role": "super_admin",
            "email": "dev@local",
            "is_active": 1,
        }
else:
    if "user" not in st.session_state:
        try:
            from modules.auth.login_ui import render_login
            render_login(db)
            st.stop()
        except Exception as e:
            st.error(f"Login screen failed to load: {e}")
            st.stop()

user = st.session_state.user

# ============================================================
# 9. SESSION TIMEOUT
# ============================================================
try:
    from modules.auth.guards import enforce_session_timeout
    enforce_session_timeout()
except Exception:
    pass

# ============================================================
# 10. USER SWITCH RESET
# ============================================================
current_user_id = user.get("user_id")
if st.session_state.get("_last_user_id") != current_user_id:
    st.session_state.clear()
    st.session_state["_last_user_id"] = current_user_id
    st.rerun()

# ============================================================
# 11. SERVICES
# ============================================================
try:
    nav_service = NavService(db, market_data_service)
    alert_service = AlertService(db)
    order_service = OrderService(db)
except Exception as e:
    st.error(f"Service initialization failed: {e}")
    st.stop()

# ============================================================
# 12. SIDEBAR
# ============================================================
st.sidebar.title("Stocks Research Terminal")
st.sidebar.markdown(f"**Version:** {VERSION}")
st.sidebar.markdown(datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
st.sidebar.divider()

st.sidebar.write(f"Logged in as: {user.get('email', user.get('user_id'))}")
st.sidebar.write(f"Role: {user.get('role')}")

if st.sidebar.button("Logout", key="sidebar_logout"):
    from modules.auth.auth_service import logout
    logout()
    st.rerun()

# ============================================================
# 13. DEV_MODE DEBUG PRAGMA OUTPUT
# ============================================================
if DEV_MODE:
    conn = sqlite3.connect(_db_path)
    cur = conn.cursor()

    for table in ["universes", "users", "tenants", "universe_symbols", "universe_equities"]:
        cur.execute(f"PRAGMA table_info({table})")
        st.sidebar.write(f"{table} columns:", [row[1] for row in cur.fetchall()])

    conn.close()

# ============================================================
# 14. SCHEDULER
# ============================================================
if "last_scheduler_run" not in st.session_state:
    st.session_state["last_scheduler_run"] = 0

try:
    if time.time() - st.session_state["last_scheduler_run"] > 60:
        if hasattr(nav_service, "run_rebalance_scheduler"):
            nav_service.run_rebalance_scheduler(
                order_service=order_service,
                alert_service=alert_service,
                user_id=user.get("user_id")
            )
            st.session_state["last_scheduler_run"] = time.time()
except Exception as e:
    st.sidebar.warning(f"Scheduler: {str(e)[:80]}")

# ============================================================
# 15. PAGE ROUTING
# ============================================================
role = (user.get("role") or "").lower()

if role == "client":
    pages = ["Portfolio"]
else:
    pages = [
        "Dashboard", "Watchlists", "Screener", "Earnings", "Market Data",
        "Analytics", "Rankings", "Universe", "Stock Dashboard", "Portfolio",
        "Portfolio Construction", "Portfolio Deployment", "Market Overview",
        "AI Rankings", "Strategy Lab", "Regime Engine", "Strategy Discovery",
        "Strategy Library", "Alerts", "Admin", "Help"
    ]

page = st.sidebar.selectbox("Go to", pages)

def safe_import(module_path: str):
    try:
        return __import__(module_path, fromlist=["*"])
    except Exception as e:
        return e

watchlists_mod = safe_import("modules.institutional.ui.watchlists_ui")
screener_mod = safe_import("modules.institutional.ui.screener_ui")
earnings_mod = safe_import("modules.institutional.ui.earnings_ui")
market_data_mod = safe_import("modules.institutional.ui.market_data_ui")
analytics_mod = safe_import("modules.institutional.ui.analytics_ui")
rankings_mod = safe_import("modules.institutional.ui.rankings_ui")
ranking_ui_mod = safe_import("modules.analytics.ranking_ui")
alerts_mod = safe_import("modules.institutional.ui.alerts_ui")
universe_mod = safe_import("modules.institutional.ui.universe_ui")
stock_dashboard_mod = safe_import("modules.institutional.ui.stock_dashboard_ui")
portfolio_mod = safe_import("modules.portfolio.ui")
construction_mod = safe_import("modules.portfolio.construction_engine")
deployment_mod = safe_import("modules.portfolio.deployment_engine")
market_dashboard_mod = safe_import("modules.market.dashboard")
sector_heatmap_mod = safe_import("modules.market.sector_heatmap")
heatmap_mod = safe_import("modules.market.heatmap")
regime_mod = safe_import("modules.market.regime_dashboard")
factor_mod = safe_import("modules.analytics.factor_exposure")
backtest_mod = safe_import("modules.analytics.backtesting")
regime_engine_mod = safe_import("modules.market.regime_engine")
strategy_discovery_mod = safe_import("modules.analytics.strategy_discovery")
strategy_library_mod = safe_import("modules.analytics.strategy_library")
admin_mod = safe_import("modules.admin.admin_ui")

# ====================== PAGE ROUTING ======================
if page == "Dashboard":
    st.header("Institutional Research Dashboard")
    st.info("Select a module from the sidebar.")

elif page == "Watchlists":
    if isinstance(watchlists_mod, Exception):
        st.error("Watchlists module failed to load.")
        st.exception(watchlists_mod)
    elif hasattr(watchlists_mod, "render_watchlists"):
        watchlists_mod.render_watchlists(db, user)

elif page == "Screener":
    if isinstance(screener_mod, Exception):
        st.error("Screener module failed to load.")
        st.exception(screener_mod)
    elif hasattr(screener_mod, "render_screener"):
        screener_mod.render_screener(db, user)

elif page == "Earnings":
    if isinstance(earnings_mod, Exception):
        st.error("Earnings module failed to load.")
        st.exception(earnings_mod)
    elif hasattr(earnings_mod, "render_earnings"):
        earnings_mod.render_earnings(db, user)

elif page == "Market Data":
    if isinstance(market_data_mod, Exception):
        st.error("Market Data module failed to load.")
        st.exception(market_data_mod)
    else:
        if hasattr(market_data_mod, "render_market_data"):
            market_data_mod.render_market_data(db, user)
        if hasattr(market_data_mod, "render_market_refresh"):
            market_data_mod.render_market_refresh(db, user)

elif page == "Analytics":
    if isinstance(analytics_mod, Exception):
        st.error("Analytics module failed to load.")
        st.exception(analytics_mod)
    elif hasattr(analytics_mod, "render_analytics"):
        analytics_mod.render_analytics(db, user)

elif page == "Rankings":
    if isinstance(rankings_mod, Exception):
        st.error("Rankings module failed to load.")
        st.exception(rankings_mod)
    elif hasattr(rankings_mod, "render_rankings"):
        rankings_mod.render_rankings(db, user)

elif page == "Universe":
    if isinstance(universe_mod, Exception):
        st.error("Universe module failed to load.")
        st.exception(universe_mod)
    elif hasattr(universe_mod, "render_universe"):
        universe_mod.render_universe(db, user)

elif page == "Stock Dashboard":
    if isinstance(stock_dashboard_mod, Exception):
        st.error("Stock dashboard failed to load.")
        st.exception(stock_dashboard_mod)
    elif hasattr(stock_dashboard_mod, "render_stock_dashboard"):
        stock_dashboard_mod.render_stock_dashboard(db, user)

elif page == "Portfolio":
    if isinstance(portfolio_mod, Exception):
        st.error("Portfolio module failed to load.")
        st.exception(portfolio_mod)
        st.stop()

    if role == "client":
        from modules.client.client_dashboard import render_client_dashboard
        render_client_dashboard(db_session=db, user=user, market_data_service=market_data_service)
        st.stop()
    elif role in ["tenant_admin", "super_admin"]:
        from modules.dashboard.dashboard_ui import render_dashboard
        render_dashboard(db_session=db, user=user, market_data_service=market_data_service)
        st.stop()
    else:
        st.error(f"Unauthorized role: {role}")
        st.stop()

elif page == "Portfolio Construction":
    if isinstance(construction_mod, Exception):
        st.error("Portfolio construction module failed to load.")
        st.exception(construction_mod)
    else:
        rows = st.session_state.get("rank_rows")
        construction_mod.render_portfolio_construction(rows)

elif page == "Portfolio Deployment":
    if isinstance(deployment_mod, Exception):
        st.error("Deployment module failed to load.")
        st.exception(deployment_mod)
    else:
        deployment_mod.render_portfolio_deployment(db, user)

elif page == "Market Overview":
    st.header("Market Overview")
    if hasattr(market_dashboard_mod, "render_market_dashboard"):
        market_dashboard_mod.render_market_dashboard(db)

elif page == "AI Rankings":
    st.header("AI Stock Rankings")
    if isinstance(ranking_ui_mod, Exception):
        st.error("AI Rankings module failed to load.")
        st.exception(ranking_ui_mod)
    else:
        st.info("AI Rankings module ready")

elif page == "Admin":

    st.header("Admin Console")

    if isinstance(admin_mod, Exception):

        st.error("Admin module failed to load.")

        st.exception(admin_mod)

    elif hasattr(admin_mod, "render_admin_panel"):

        try:

            admin_mod.render_admin_panel(db, user)

        except Exception as e:

            st.error("Admin panel failed.")

            st.exception(e)

    else:

        st.error(
            "render_admin_panel() not found in admin_ui.py"
        )

elif page == "Help":
    try:
        render_help()
    except Exception as e:
        st.error("Help module failed.")
        st.exception(e)

# ============================================================
# 16. CLEANUP
# ============================================================
try:
    if db is not None:
        db.close()
except:
    pass
