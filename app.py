from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, UTC
from typing import Any, Callable, Optional


import streamlit as st
print("STREAMLIT VERSION =", st.__version__)


from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DBAPIError
from branding.conduro_theme import load_conduro_theme, render_conduro_header

# MUST BE FIRST STREAMLIT COMMAND
# MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Equity Research Terminal",
    layout="wide",
    initial_sidebar_state="expanded",
)

# MUST RUN IMMEDIATELY AFTER set_page_config
load_conduro_theme()

VERSION = "2.4.1"
DEV_MODE = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def init_db_once():
    from modules.db.core import init_database
    init_database()


init_db_once()

from modules.db.core import SessionLocal


def new_db_session():
    """Create a short-lived SQLAlchemy session for the current Streamlit run."""
    return SessionLocal()


def safe_rollback(session: Any) -> None:
    try:
        if session is not None:
            session.rollback()
    except Exception:
        pass


def safe_close(session: Any) -> None:
    try:
        if session is not None:
            session.close()
    except Exception:
        pass


def ensure_live_session(session: Any):
    """
    PostgreSQL/Neon can close idle SSL connections. This validates the current
    session and replaces it if the DBAPI connection is dead.
    """
    try:
        safe_rollback(session)
        session.execute(text("SELECT 1")).scalar()
        return session
    except Exception:
        safe_rollback(session)
        safe_close(session)
        replacement = new_db_session()
        replacement.execute(text("SELECT 1")).scalar()
        return replacement


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def db_scalar(sql: str, params: Optional[dict] = None):
    """Run a small debug query in an isolated session."""
    with new_db_session() as s:
        return s.execute(text(sql), params or {}).scalar()


def db_fetchall(sql: str, params: Optional[dict] = None):
    """Run a small debug query in an isolated session."""
    with new_db_session() as s:
        return s.execute(text(sql), params or {}).fetchall()


def ensure_default_bootstrap(session) -> None:
    """
    Creates the initial tenant and admin users if the database is empty.
    Safe to run every startup.
    """
    try:
        safe_rollback(session)

        user_count = session.execute(
            text("SELECT COUNT(*) FROM users")
        ).scalar()

        if int(user_count or 0) > 0:
            return

        tenant_id = "default_tenant"

        # Default tenant
        session.execute(
            text("""
                INSERT INTO tenants (
                    id,
                    name,
                    is_active,
                    created_at
                )
                VALUES (
                    :id,
                    :name,
                    :is_active,
                    CURRENT_TIMESTAMP
                )
            """),
            {
                "id": tenant_id,
                "name": "Default Tenant",
                "is_active": True,
            },
        )

        # Super Admin
        session.execute(
            text("""
                INSERT INTO users (
                    id,
                    tenant_id,
                    email,
                    role,
                    created_at,
                    password_hash,
                    is_active
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :email,
                    :role,
                    CURRENT_TIMESTAMP,
                    :password_hash,
                    :is_active
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "email": "admin@test.com",
                "role": "super_admin",
                "password_hash": _hash_password("password"),
                "is_active": True,
            },
        )

        # Tenant Admin
        session.execute(
            text("""
                INSERT INTO users (
                    id,
                    tenant_id,
                    email,
                    role,
                    created_at,
                    password_hash,
                    is_active
                )
                VALUES (
                    :id,
                    :tenant_id,
                    :email,
                    :role,
                    CURRENT_TIMESTAMP,
                    :password_hash,
                    :is_active
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "email": "tenant@test.com",
                "role": "tenant_admin",
                "password_hash": _hash_password("password"),
                "is_active": True,
            },
        )

        session.commit()

        print("=" * 80)
        print("DEFAULT TENANT CREATED")
        print("SUPER ADMIN: admin@test.com")
        print("TENANT ADMIN: tenant@test.com")
        print("PASSWORD: password")
        print("=" * 80)

    except Exception:
        safe_rollback(session)
        raise


# Main DB session for this Streamlit run only. Do not cache this object.
db = new_db_session()
try:
    db = ensure_live_session(db)
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.exception(e)
    st.stop()

st.write("SECRETS DATABASE URL")
st.code(st.secrets.get("DATABASE_URL", "NOT FOUND"))

try:
    ensure_default_bootstrap(db)
except Exception as e:
    st.error(f"Bootstrap failed: {e}")
    st.exception(e)
# ============================================================
# PRE-LOGIN DB DEBUG
# ============================================================
if DEV_MODE:
    st.sidebar.markdown("## PRE-LOGIN DB DEBUG")

    try:
        user_count = db_scalar("SELECT COUNT(*) FROM users")
        tenant_count = db_scalar("SELECT COUNT(*) FROM tenants")

        st.sidebar.write("USER COUNT", user_count)
        st.sidebar.write("TENANT COUNT", tenant_count)

        users = db_fetchall("""
            SELECT email, role, tenant_id
            FROM users
            ORDER BY email
        """)

        st.sidebar.write("USERS")
        st.sidebar.json([str(x) for x in users])

    except Exception as e:
        st.sidebar.error(f"DEBUG FAILED: {e}")

    #try:
        # st.sidebar.write("DATABASE", db_scalar("SELECT current_database()"))
    except Exception as e:
        st.sidebar.error(f"DB NAME FAILED: {e}")

    try:
        users = db_fetchall("""
            SELECT email, role
            FROM users
            ORDER BY email
        """)
        print("=" * 80)
        print("POSTGRES USERS")
        for u in users:
            print(u)
        print("=" * 80)
    except Exception as e:
        print("USER DEBUG FAILED:", e)


# ============================================================
# IMPORT MODELS + SERVICES
# ============================================================
try:
    from modules.auth.login_ui import render_login
    from modules.help.help_ui import render_help
    from modules.portfolio.nav_service import NavService
    from modules.portfolio.order_service import OrderService
    from modules.alerts.service import AlertService
except Exception as e:
    safe_rollback(db)
    st.error(f"Critical module import failed: {e}")
    st.exception(e)
    st.stop()


# ============================================================
# MARKET DATA SERVICE
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
                if hasattr(mds, "get_latest_price"):
                    return {"price": mds.get_latest_price(symbol)}
                return None

        return MarketDataServiceAdapter()

    except Exception as e:
        st.warning(f"Market data service init warning: {e}")
        return None

# import block executes


market_data_service = get_market_data_service()


# ============================================================
# AUTH GATE
# ============================================================
user = st.session_state.get("user")

if user is None:
    try:
        db = ensure_live_session(db)
        render_login(db)
    except Exception as e:
        safe_rollback(db)
        st.error(f"Login failed: {e}")
        st.exception(e)

st.write("SESSION STATE")
st.write(dict(st.session_state))
user = st.session_state.get("user")

if user is None:
    st.session_state.pop("user", None)
    render_login(db)
    st.stop()

render_conduro_header(
    title="Stock Research Terminal",
    subtitle="AI-powered equity research, portfolio analytics, options intelligence, and advisor workflows.",
    kicker="Conduro Ventures LLC",
    status=user.get("role", "User").replace("_", " ").title() if user else "User"
)
# ============================================================
# SESSION TIMEOUT
# ============================================================
try:
    from modules.auth.guards import enforce_session_timeout
    enforce_session_timeout()
except Exception:
    pass


# ============================================================
# SERVICES
# ============================================================
try:
    db = ensure_live_session(db)
    nav_service = NavService(db, market_data_service)
    alert_service = AlertService(db)
    order_service = OrderService(db)
except Exception as e:
    safe_rollback(db)
    st.error(f"Service initialization failed: {e}")
    st.exception(e)
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.markdown("## Conduro Ventures\n\n**Stock Research Terminal**")
st.sidebar.markdown(f"**Version:** {VERSION}")
#st.sidebar.info("Conduro Ventures Research Platform")
st.sidebar.markdown(datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
st.sidebar.divider()

st.sidebar.write(f"Logged in as: {user.get('email', user.get('user_id'))}")
st.sidebar.write(f"Role: {user.get('role')}")

if st.sidebar.button("Sign Out", key="sidebar_logout", use_container_width=True):
    from modules.auth.auth_service import logout
    logout()
    st.rerun()


# ============================================================
# DEV DEBUG OUTPUT - isolated sessions only
# ============================================================
if DEV_MODE:
    try:
        st.sidebar.markdown("### DB Debug")
        st.subheader("POSTGRES DEBUG")

        try:
            st.write("USER COUNT", db_scalar("SELECT COUNT(*) FROM users"))
            st.write("TENANT COUNT", db_scalar("SELECT COUNT(*) FROM tenants"))

            users = db_fetchall("""
                SELECT
                    email,
                    role,
                    tenant_id,
                    is_active
                FROM users
                ORDER BY email
            """)

            st.write("USERS")
            st.json([str(u) for u in users])

        except Exception as e:
            st.error(f"USER DEBUG FAILED: {e}")

        try:
            tenants = db_fetchall("""
                SELECT
                    id,
                    name,
                    created_at
                FROM tenants
                ORDER BY name
            """)

            st.write("TENANTS")
            st.json([str(t) for t in tenants])

        except Exception as e:
            st.error(f"TENANT DEBUG FAILED: {e}")

        #try:
            # st.write("POSTGRES DATABASE", db_scalar("SELECT current_database()"))
        except Exception as e:
            st.error(f"DB NAME FAILED: {e}")

        try:
            version = db_scalar("SELECT version()")
            st.write("POSTGRES VERSION")
            st.code(version)
        except Exception as e:
            st.error(f"VERSION FAILED: {e}")

        try:
            cols = db_fetchall("""
                SELECT
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE table_name = 'portfolios'
                ORDER BY ordinal_position
            """)
            st.write(cols)
        except Exception as e:
            st.error(f"PORTFOLIO SCHEMA DEBUG FAILED: {e}")

    except Exception as e:
        st.sidebar.error(f"DB debug failed: {e}")


# ============================================================
# SCHEDULER
# ============================================================
if "last_scheduler_run" not in st.session_state:
    st.session_state["last_scheduler_run"] = 0

try:
    if time.time() - st.session_state["last_scheduler_run"] > 60:
        db = ensure_live_session(db)
        if hasattr(nav_service, "run_rebalance_scheduler"):
            nav_service.run_rebalance_scheduler(
                order_service=order_service,
                alert_service=alert_service,
                user_id=user.get("user_id"),
            )
            st.session_state["last_scheduler_run"] = time.time()
except Exception as e:
    safe_rollback(db)
    st.sidebar.warning(f"Scheduler: {str(e)[:120]}")


# ============================================================
# PAGE LIST
# ============================================================
role = (user.get("role") or "").lower()
if role == "client":
    pages = ["Portfolio"]
else:
    pages = [
        "Executive Dashboard",
        "Watchlists",
        "Screener",
        "Formula Builder",
        "Earnings",
        "Market Data",
        "Analytics",
        "Rankings",
        "Indicator Builder",
        "Universe",
        "Stock Dashboard",
        "Intraday Charts",
        "Portfolio",
        "Portfolio Construction",
        "Portfolio Deployment",
        "Market Overview",
        "Strategy Lab",
        "Regime Engine",
        "Strategy Discovery",
        "Strategy Library",
        "IPO Intelligence",
        "Alerts",
        "Admin",
        "AI Rankings",
        "AI Portfolio",
        "AI Forecast",
        "AI Scanner",
        "AI Agent",
        "Options Flow",
        "Options Trading",
        "Analyst Consensus",
        "Smart Money",
        "Export / Sheets",
        "Research Reports",
        "Social Sentiment",
        "Team Collaboration",
        "Crypto",
        "Help",
    ]

page = st.sidebar.selectbox("Go to", pages)


# ============================================================
# SAFE IMPORT / SAFE RENDER
# ============================================================
def safe_import(module_path: str):
    try:
        return __import__(module_path, fromlist=["*"])
    except Exception as e:
        return e


def render_module_error(label: str, exc: Exception) -> None:
    st.error(f"{label} module failed to load.")
    st.exception(exc)


def run_page(label: str, fn: Callable, *args, stop_after: bool = False, **kwargs):
    """
    Standard PostgreSQL-safe page wrapper.
    Clears stale transactions before render and rolls back on any page exception.
    """
    global db
    try:
        db = ensure_live_session(db)
        result = fn(*args, **kwargs)
        if stop_after:
            st.stop()
        return result

    except (OperationalError, DBAPIError) as e:
        safe_rollback(db)
        st.error(f"{label} database error.")
        st.exception(e)
        if stop_after:
            st.stop()

    except Exception as e:
        safe_rollback(db)
        st.error(f"{label} failed.")
        st.exception(e)
        if stop_after:
            st.stop()

executive_dashboard_mod = safe_import("modules.dashboard.executive_dashboard")
watchlists_mod = safe_import("modules.institutional.ui.watchlists_ui")
screener_mod = safe_import("modules.institutional.ui.screener_ui")
earnings_mod = safe_import("modules.institutional.ui.earnings_ui")
market_data_mod = safe_import("modules.institutional.ui.market_data_ui")
analytics_mod = safe_import("modules.institutional.ui.analytics_ui")
rankings_mod = safe_import("modules.institutional.ui.rankings_ui")
alerts_mod = safe_import("modules.institutional.ui.alerts_ui")
universe_mod = safe_import("modules.institutional.ui.universe_ui")
stock_dashboard_mod = safe_import("modules.institutional.ui.stock_dashboard_ui")
portfolio_mod = safe_import("modules.portfolio.ui")
construction_mod = safe_import("modules.portfolio.construction_engine")
deployment_mod = safe_import("modules.portfolio.deployment_engine")
market_dashboard_mod = safe_import("modules.market.dashboard")
admin_mod = safe_import("modules.admin.admin_ui")


# ============================================================
# ROUTING
# ============================================================
if page == "Executive Dashboard":
    if isinstance(executive_dashboard_mod, Exception):
        st.error("Executive Dashboard module failed to load.")
        st.exception(executive_dashboard_mod)
    elif hasattr(executive_dashboard_mod, "render_executive_dashboard"):
        executive_dashboard_mod.render_executive_dashboard(db, user)
    st.header("Institutional Research Dashboard")
    st.info("Select a module from the sidebar.")

elif page == "Watchlists":
    if isinstance(watchlists_mod, Exception):
        render_module_error("Watchlists", watchlists_mod)
    elif hasattr(watchlists_mod, "render_watchlists"):
        run_page("Watchlists", watchlists_mod.render_watchlists, db, user)

elif page == "Screener":
    if isinstance(screener_mod, Exception):
        render_module_error("Screener", screener_mod)
    elif hasattr(screener_mod, "render_screener"):
        run_page("Screener", screener_mod.render_screener, db, user)

elif page == "Formula Builder":
    try:
        from modules.screener.formula_ui import render_formula_page
        run_page("Formula Builder", render_formula_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error(f"Formula Builder failed: {e}")
        st.exception(e)

elif page == "Earnings":
    if isinstance(earnings_mod, Exception):
        render_module_error("Earnings", earnings_mod)
    elif hasattr(earnings_mod, "render_earnings"):
        run_page("Earnings", earnings_mod.render_earnings, db, user)

elif page == "Market Data":
    if isinstance(market_data_mod, Exception):
        render_module_error("Market Data", market_data_mod)
    else:
        if hasattr(market_data_mod, "render_market_data"):
            run_page("Market Data", market_data_mod.render_market_data, db, user)
        if hasattr(market_data_mod, "render_market_refresh"):
            run_page("Market Refresh", market_data_mod.render_market_refresh, db, user)

elif page == "Analytics":
    if isinstance(analytics_mod, Exception):
        render_module_error("Analytics", analytics_mod)
    elif hasattr(analytics_mod, "render_analytics"):
        run_page("Analytics", analytics_mod.render_analytics, db, user)

elif page == "Rankings":
    if isinstance(rankings_mod, Exception):
        render_module_error("Rankings", rankings_mod)
    elif hasattr(rankings_mod, "render_rankings"):
        run_page("Rankings", rankings_mod.render_rankings, db, user)

elif page == "Indicator Builder":
    try:
        from modules.indicators.indicator_ui import render_indicator_builder
        run_page("Indicator Builder", render_indicator_builder, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Indicator Builder failed to load.")
        st.exception(e)

elif page == "Universe":
    if isinstance(universe_mod, Exception):
        render_module_error("Universe", universe_mod)
    elif hasattr(universe_mod, "render_universe"):
        run_page("Universe", universe_mod.render_universe, db, user)

elif page == "Stock Dashboard":
    if isinstance(stock_dashboard_mod, Exception):
        render_module_error("Stock Dashboard", stock_dashboard_mod)
    elif hasattr(stock_dashboard_mod, "render_stock_dashboard"):
        run_page("Stock Dashboard", stock_dashboard_mod.render_stock_dashboard, db, user)

elif page == "Intraday Charts":
    try:
        from modules.intraday.intraday_ui import render_intraday_page
        run_page("Intraday Charts", render_intraday_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Intraday Charts failed to load.")
        st.exception(e)

elif page == "Portfolio":
    if isinstance(portfolio_mod, Exception):
        render_module_error("Portfolio", portfolio_mod)
        st.stop()

    if role == "client":
        from modules.client.client_dashboard import render_client_dashboard
        run_page(
            "Client Portfolio",
            render_client_dashboard,
            db_session=db,
            user=user,
            market_data_service=market_data_service,
            stop_after=True,
        )

    elif role in ["tenant_admin", "super_admin"]:
        from modules.dashboard.dashboard_ui import render_dashboard
        run_page(
            "Portfolio Dashboard",
            render_dashboard,
            db_session=db,
            user=user,
            market_data_service=market_data_service,
            stop_after=True,
        )

    else:
        st.error(f"Unauthorized role: {role}")
        st.stop()

elif page == "Portfolio Construction":
    if isinstance(construction_mod, Exception):
        render_module_error("Portfolio Construction", construction_mod)
    else:
        rows = st.session_state.get("rank_rows")
        run_page("Portfolio Construction", construction_mod.render_portfolio_construction, rows)

elif page == "Portfolio Deployment":
    if isinstance(deployment_mod, Exception):
        render_module_error("Portfolio Deployment", deployment_mod)
    elif hasattr(deployment_mod, "render_portfolio_deployment"):
        run_page("Portfolio Deployment", deployment_mod.render_portfolio_deployment, db, user)

elif page == "Market Overview":
    st.header("Market Overview")
    if isinstance(market_dashboard_mod, Exception):
        render_module_error("Market Overview", market_dashboard_mod)
    elif hasattr(market_dashboard_mod, "render_market_dashboard"):
        run_page("Market Overview", market_dashboard_mod.render_market_dashboard, db)
    else:
        st.error("render_market_dashboard() not found in modules.market.dashboard")

elif page == "AI Rankings":
    rankings_ui_mod = safe_import("modules.analytics.ranking_ui")
    if isinstance(rankings_ui_mod, Exception):
        render_module_error("AI Rankings UI", rankings_ui_mod)
    elif hasattr(rankings_ui_mod, "render_ai_rankings"):
        run_page("AI Rankings", rankings_ui_mod.render_ai_rankings, db=db, user=user, price_data={})
    else:
        st.error("AI Rankings UI failed to load. Expected modules.analytics.ranking_ui.render_ai_rankings")

elif page == "Regime Engine":
    try:
        from modules.market.regime_engine import render_regime_engine
        run_page("Regime Engine", render_regime_engine, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Regime Engine failed to load.")
        st.exception(e)

elif page in ("Strategy Lab", "Strategy Discovery", "Strategy Library"):
    try:
        from modules.analytics.strategy_lab_ui import render_strategy_lab
        run_page("Strategy Lab", render_strategy_lab, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Strategy Lab failed to load.")
        st.exception(e)

elif page == "IPO Intelligence":
    from modules.ipo.ipo_ui import render_ipo_center
    render_ipo_center(db, user)

elif page == "Pre-IPO Intelligence":
    from modules.preipo.preipo_ui import render_preipo_center
    render_preipo_center(db, user)

elif page == "Alerts":
    st.header("Alerts")
    if isinstance(alerts_mod, Exception):
        render_module_error("Alerts", alerts_mod)
    elif hasattr(alerts_mod, "render_alerts_page"):
        run_page("Alerts", alerts_mod.render_alerts_page, db, user)
    elif hasattr(alerts_mod, "render_alerts"):
        run_page("Alerts", alerts_mod.render_alerts, db, user)
    else:
        st.error("No alerts render function found.")

elif page == "Admin":
    st.header("Admin Console")
    if isinstance(admin_mod, Exception):
        render_module_error("Admin", admin_mod)
    elif hasattr(admin_mod, "render_admin_panel"):
        run_page("Admin Panel", admin_mod.render_admin_panel, db, user)
    else:
        st.error("render_admin_panel() not found in admin_ui.py")

elif page == "AI Portfolio":
    try:
        from modules.portfolio.ai_portfolio_ui import render_ai_portfolio_center
        run_page("AI Portfolio", render_ai_portfolio_center, db=db, user=user)
    except Exception as e:
        safe_rollback(db)
        st.error("AI Portfolio failed to load.")
        st.exception(e)

elif page == "AI Forecast":
    try:
        from modules.forecasting.forecast_ui import render_forecast_page
        run_page("AI Forecast", render_forecast_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("AI Forecast module failed to load.")
        st.exception(e)

elif page == "AI Scanner":
    try:
        from modules.alerts.scanner_ui import render_scanner_page
        run_page("AI Scanner", render_scanner_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("AI Scanner failed.")
        st.exception(e)

elif page == "AI Agent":
    try:
        from modules.agent.agent_ui import render_agent_page
        run_page("AI Agent", render_agent_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("AI Agent failed.")
        st.exception(e)

elif page == "Options Trading":
    try:
        from modules.options.options_ui import render_options_trading_page
        run_page("Options Trading", render_options_trading_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error(f"Options Trading failed: {e}")
        st.exception(e)

elif page == "Options Flow":
    try:
        from modules.options_flow.flow_ui import render_options_flow_page
        run_page("Options Flow", render_options_flow_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Options Flow failed.")
        st.exception(e)

elif page == "Analyst Consensus":
    try:
        from modules.analyst.analyst_ui import render_analyst_page
        run_page("Analyst Consensus", render_analyst_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Analyst Consensus failed.")
        st.exception(e)

elif page == "Smart Money":
    try:
        from modules.smc.smc_ui import render_smc_page
        run_page("Smart Money", render_smc_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Smart Money failed.")
        st.exception(e)

elif page == "Export / Sheets":
    try:
        from modules.export.export_ui import render_export_page
        run_page("Export / Sheets", render_export_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Export page failed to load.")
        st.exception(e)

elif page == "Research Reports":
    try:
        from modules.reports.report_ui import render_reports_page
        run_page("Research Reports", render_reports_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Research Reports failed.")
        st.exception(e)

elif page == "Social Sentiment":
    try:
        from modules.sentiment.sentiment_ui import render_sentiment_page
        run_page("Social Sentiment", render_sentiment_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Social Sentiment failed.")
        st.exception(e)

elif page == "Team Collaboration":
    try:
        from modules.collab.collab_ui import render_team_page
        run_page("Team Collaboration", render_team_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error("Team Collaboration failed.")
        st.exception(e)

elif page == "Crypto":
    try:
        from modules.crypto.service import render_crypto_page
        run_page("Crypto", render_crypto_page, db, user)
    except Exception as e:
        safe_rollback(db)
        st.error(f"Crypto module failed: {e}")
        st.exception(e)

elif page == "Help":
    from modules.help.help_home import render_help_center
    render_help_center()



# Best-effort cleanup at end of Streamlit run.
safe_rollback(db)