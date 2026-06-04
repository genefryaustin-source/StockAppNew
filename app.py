from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, UTC

import pandas as pd
import sqlite3
import matplotlib
import streamlit as st
from sqlalchemy import text

# MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Equity Research Terminal", layout="wide")

VERSION = "2.4.0"
DEV_MODE = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


# ============================================================
# DATABASE
# ============================================================
@st.cache_resource
def get_db():
    try:
        from modules.db.core import init_database, SessionLocal
        init_database()
        return SessionLocal()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.stop()


def _secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()





db = get_db()






# ============================================================
# IMPORT MODELS + SERVICES
# ============================================================
try:
    import modules.db.models
    import modules.institutional.models
    import modules.analytics.models
    import modules.alerts.models
    import modules.universe.models
    import modules.jobs.models
    import modules.market_data.models
    import modules.analytics.strategy_models

    from modules.auth.login_ui import render_login
    from modules.help.help_ui import render_help
    from modules.portfolio.nav_service import NavService
    from modules.portfolio.order_service import OrderService
    from modules.alerts.service import AlertService

except Exception as e:
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
                return None

        return MarketDataServiceAdapter()

    except Exception as e:
        st.warning(f"Market data service init warning: {e}")
        return None


market_data_service = get_market_data_service()


# ============================================================
# AUTH GATE
# ============================================================
user = st.session_state.get("user")

if user is None:
    render_login(db)
    st.stop()

role = (user.get("role") or "").lower()


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
    nav_service = NavService(db, market_data_service)
    alert_service = AlertService(db)
    order_service = OrderService(db)
except Exception as e:
    st.error(f"Service initialization failed: {e}")
    st.exception(e)
    st.stop()


# ============================================================
# SIDEBAR
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
# DEV DEBUG OUTPUT
# ============================================================
if DEV_MODE:
    try:
        st.sidebar.markdown("### DB Debug")

        from modules.db.core import DB_PATH, DB_URL

        print("DATABASE URL:", DB_URL.split("@")[1])
        print("CONNECTED TO POSTGRES")






    except Exception as e:
        st.sidebar.error(f"DB debug failed: {e}")


# ============================================================
# SCHEDULER
# ============================================================
if "last_scheduler_run" not in st.session_state:
    st.session_state["last_scheduler_run"] = 0

try:
    if time.time() - st.session_state["last_scheduler_run"] > 60:
        if hasattr(nav_service, "run_rebalance_scheduler"):
            nav_service.run_rebalance_scheduler(
                order_service=order_service,
                alert_service=alert_service,
                user_id=user.get("user_id"),
            )
            st.session_state["last_scheduler_run"] = time.time()
except Exception as e:
    st.sidebar.warning(f"Scheduler: {str(e)[:80]}")


# ============================================================
# PAGE LIST
# ============================================================
if role == "client":
    pages = ["Portfolio"]
else:
    pages = [
        "Dashboard",
        "Watchlists",
        "Screener",
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
        "AI Rankings",
        "Strategy Lab",
        "Regime Engine",
        "Strategy Discovery",
        "Strategy Library",
        "Alerts",
        "Admin",
        "AI Portfolio",
        "AI Forecast",
        "AI Scanner",
        "AI Agent",
        "Options Flow",
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
# SAFE IMPORT
# ============================================================
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

elif page == "Indicator Builder":
    from modules.indicators.indicator_ui import render_indicator_builder
    render_indicator_builder(db, user)

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

elif page == "Intraday Charts":
    from modules.intraday.intraday_ui import render_intraday_page
    render_intraday_page(db, user)

elif page == "Portfolio":
    if isinstance(portfolio_mod, Exception):
        st.error("Portfolio module failed to load.")
        st.exception(portfolio_mod)
        st.stop()

    if role == "client":
        from modules.client.client_dashboard import render_client_dashboard
        render_client_dashboard(
            db_session=db,
            user=user,
            market_data_service=market_data_service,
        )
        st.stop()

    if role in ["tenant_admin", "super_admin"]:
        from modules.dashboard.dashboard_ui import render_dashboard
        render_dashboard(
            db_session=db,
            user=user,
            market_data_service=market_data_service,
        )
        st.stop()

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
    rankings_ui_mod = safe_import("modules.analytics.ranking_ui")

    if isinstance(rankings_ui_mod, Exception):
        st.error("AI Rankings UI failed to load.")
        st.exception(rankings_ui_mod)
    elif hasattr(rankings_ui_mod, "render_ai_rankings"):
        rankings_ui_mod.render_ai_rankings(
            db=db,
            user=user,
            price_data={},
        )
    else:
        st.error(
            "AI Rankings UI failed to load. "
            "Expected modules.analytics.ranking_ui.render_ai_rankings"
        )

elif page == "Regime Engine":
    from modules.market.regime_engine import render_regime_engine
    render_regime_engine(db, user)

elif page in ("Strategy Lab", "Strategy Discovery", "Strategy Library"):
    try:
        from modules.analytics.strategy_lab_ui import render_strategy_lab
        render_strategy_lab(db, user)
    except Exception as e:
        st.error("Strategy Lab failed to load.")
        st.exception(e)

elif page == "Alerts":
    st.header("Alerts")

    if isinstance(alerts_mod, Exception):
        st.error("Alerts module failed to load.")
        st.exception(alerts_mod)
    elif hasattr(alerts_mod, "render_alerts_page"):
        try:
            alerts_mod.render_alerts_page(db, user)
        except Exception as e:
            st.error("Alerts page failed.")
            st.exception(e)
    elif hasattr(alerts_mod, "render_alerts"):
        try:
            alerts_mod.render_alerts(db, user)
        except Exception as e:
            st.error("Alerts page failed.")
            st.exception(e)
    else:
        st.error("No alerts render function found.")

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
        st.error("render_admin_panel() not found in admin_ui.py")

elif page == "AI Portfolio":
    try:
        from modules.portfolio.ai_portfolio_ui import render_ai_portfolio_center
        render_ai_portfolio_center(db=db, user=user)
    except Exception as e:
        st.error("AI Portfolio failed to load.")
        st.exception(e)

elif page == "AI Forecast":
    try:
        from modules.forecasting.forecast_ui import render_forecast_page
        render_forecast_page(db, user)
    except Exception as e:
        st.error("AI Forecast module failed to load.")
        st.exception(e)

elif page == "AI Scanner":
    from modules.alerts.scanner_ui import render_scanner_page
    render_scanner_page(db, user)

elif page == "AI Agent":
    from modules.agent.agent_ui import render_agent_page
    render_agent_page(db, user)

elif page == "Options Flow":
    from modules.options_flow.flow_ui import render_options_flow_page
    render_options_flow_page(db, user)

elif page == "Analyst Consensus":
    from modules.analyst.analyst_ui import render_analyst_page
    render_analyst_page(db, user)

elif page == "Smart Money":
    from modules.smc.smc_ui import render_smc_page
    render_smc_page(db, user)

elif page == "Export / Sheets":
    try:
        from modules.export.export_ui import render_export_page
        render_export_page(db, user)
    except Exception as e:
        st.error("Export page failed to load.")
        st.exception(e)

elif page == "Research Reports":
    from modules.reports.report_ui import render_reports_page
    render_reports_page(db, user)

elif page == "Social Sentiment":
    from modules.sentiment.sentiment_ui import render_sentiment_page
    render_sentiment_page(db, user)

elif page == "Team Collaboration":
    from modules.collab.collab_ui import render_team_page
    render_team_page(db, user)

elif page == "Crypto":
    try:
        from modules.crypto.service import render_crypto_page
        render_crypto_page(db, user)
    except Exception as e:
        st.error(f"Crypto module failed: {e}")
        st.exception(e)

elif page == "Help":
    try:
        render_help()
    except Exception as e:
        st.error("Help module failed.")
        st.exception(e)