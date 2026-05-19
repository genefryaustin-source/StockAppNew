import selectors

import streamlit as st
import pandas as pd
from datetime import datetime, UTC

VERSION = "2.4.0"

st.set_page_config(page_title="Equity Research Terminal", layout="wide")

# ---------------------------------------------------
# Database init
# ---------------------------------------------------
from modules.db.core import init_database, SessionLocal

import modules.db.models
import modules.institutional.models
import modules.analytics.models
import modules.alerts.models
import modules.universe.models
import modules.jobs.models
import modules.market_data.models
import modules.analytics.strategy_models
from models.strategy_run import StrategyRun
import modules.market_data.service as mds
from modules.help.help_ui import render_help
from modules.portfolio.portfolio_ui import render_portfolio_ui
from modules.portfolio.nav_service import NavService
from modules.portfolio.order_service import OrderService
from modules.alerts.service import AlertService
import time
import sys
import os
from modules.auth.auth_service import logout
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


class MarketDataServiceAdapter:
    def get_quote(self, symbol: str):
        # Try common function names in your module
        if hasattr(mds, "get_quote"):
            return mds.get_quote(symbol)

        if hasattr(mds, "get_price"):
            return {"price": mds.get_price(symbol)}

        if hasattr(mds, "fetch_price"):
            return {"price": mds.fetch_price(symbol)}

        raise AttributeError("No compatible market data function found in service.py")


market_data_service = MarketDataServiceAdapter()


init_database()

# ---------------------------------------------------
# Seed reference data on first run
# ---------------------------------------------------
from scripts.seed_db import run_seed

run_seed(
    db_path=os.path.join(os.getcwd(), "stockapp.db"),   # matches core.py exactly
    seed_file=os.path.join(os.getcwd(), "seed_data.sql")
)

db = SessionLocal()

from models.trading import (
    TradeOrder,
    TradeFill,
    PortfolioPosition,
    PortfolioCashLedger,
    PortfolioSnapshot,
    ClosedTrade,
)



if "tables_initialized" not in st.session_state:
    from models.base import Base

    try:
        engine = db.get_bind()
    except Exception:
        engine = db.session.get_bind()

    Base.metadata.create_all(bind=engine)
    st.session_state["tables_initialized"] = True




# ---------------------------------------------------
# Market Data Service
# ---------------------------------------------------
from modules.market_data.service import build_shared_price_cache, get_price_history

# ---------------------------------------------------
# Session/User (AUTH GATE)
# ---------------------------------------------------

# ---------------------------------------------------
# Session/User (AUTH GATE)
# ---------------------------------------------------
DEV_MODE = False

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
        from modules.auth.login_ui import render_login
        render_login(db)
        st.stop()

from modules.auth.guards import enforce_session_timeout
enforce_session_timeout()

user = st.session_state.user
# ---------------------------------
# 🔥 RESET SESSION WHEN USER CHANGES
# ---------------------------------
current_user_id = user.get("user_id")

if st.session_state.get("_last_user_id") != current_user_id:
    print("🔥 USER SWITCH DETECTED — RESETTING SESSION")

    st.session_state.clear()

    st.session_state["_last_user_id"] = current_user_id


st.sidebar.markdown("---")
st.sidebar.write(f"Logged in as: {user.get('email', user.get('user_id'))}")
st.sidebar.write(f"Role: {user.get('role')}")

if st.sidebar.button("Logout", key="sidebar_logout"):
    logout()
    st.rerun()

nav_service = NavService(db, market_data_service)
alert_service = AlertService(db)
order_service = OrderService(db)

# ---------------------------------
# 🚀 RUN SCHEDULER (SAFE INTERVAL)
# ---------------------------------
if "last_scheduler_run" not in st.session_state:
    st.session_state["last_scheduler_run"] = 0

try:
    if time.time() - st.session_state["last_scheduler_run"] > 60:

        nav_service.run_rebalance_scheduler(
            order_service=order_service,
            alert_service=alert_service,
            user_id=user.get("user_id")  # ✅ FIXED
        )

        st.session_state["last_scheduler_run"] = time.time()

except Exception as e:
    print("⚠️ Scheduler error:", e)
# ---------------------------------------------------
# Sidebar
# ---------------------------------------------------
st.sidebar.title("Equity Research Terminal")

st.sidebar.markdown(f"**Version:** {VERSION}")
st.sidebar.markdown(datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))

st.sidebar.divider()

symbol_global = st.sidebar.text_input("Global Symbol", value="AAPL").upper()

st.sidebar.divider()

st.sidebar.markdown("---")
st.sidebar.write(f"Logged in as: {user.get('user_id')}")

role = (user.get("role") or "").lower()

st.sidebar.title("Navigation")

# ---------------------------------
# ROLE-BASED NAVIGATION
# ---------------------------------
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
        "Universe",
        "Stock Dashboard",
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
        "Help",
    ]

page = st.sidebar.selectbox("Go to", pages)






# ---------------------------------------------------
# Safe import helper
# ---------------------------------------------------
def safe_import(module_path: str):
    try:
        return __import__(module_path, fromlist=["*"])
    except Exception as e:
        return e


# ---------------------------------------------------
# Module imports
# ---------------------------------------------------
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


# ---------------------------------------------------
# Dashboard
# ---------------------------------------------------
if page == "Dashboard":

    st.header("Institutional Research Dashboard")

    st.markdown(
        """
- Watchlists  
- Screener  
- Earnings ingestion  
- Market data  
- Analytics  
- Rankings  
- Universe Builder  
- Portfolio analytics  
- Market Overview  
- AI Ranking Engine  
- Strategy Backtesting  
- Portfolio Construction  
- Alerts  
"""
    )

    st.info("Select a module from the sidebar.")


# ---------------------------------------------------
# Watchlists
# ---------------------------------------------------
elif page == "Watchlists":

    if isinstance(watchlists_mod, Exception):
        st.error("Watchlists module failed to load.")
        st.exception(watchlists_mod)

    elif hasattr(watchlists_mod, "render_watchlists"):
        watchlists_mod.render_watchlists(db, user)


# ---------------------------------------------------
# Screener
# ---------------------------------------------------
elif page == "Screener":

    if isinstance(screener_mod, Exception):
        st.error("Screener module failed to load.")
        st.exception(screener_mod)

    elif hasattr(screener_mod, "render_screener"):
        screener_mod.render_screener(db, user)


# ---------------------------------------------------
# Earnings
# ---------------------------------------------------
elif page == "Earnings":

    if isinstance(earnings_mod, Exception):
        st.error("Earnings module failed to load.")
        st.exception(earnings_mod)

    elif hasattr(earnings_mod, "render_earnings"):
        earnings_mod.render_earnings(db, user)


# ---------------------------------------------------
# Market Data
# ---------------------------------------------------
elif page == "Market Data":

    if isinstance(market_data_mod, Exception):
        st.error("Market Data module failed to load.")
        st.exception(market_data_mod)

    else:

        if hasattr(market_data_mod, "render_market_data"):
            market_data_mod.render_market_data(db, user)

        st.divider()

        if hasattr(market_data_mod, "render_market_refresh"):
            market_data_mod.render_market_refresh(db, user)


# ---------------------------------------------------
# Analytics
# ---------------------------------------------------
elif page == "Analytics":

    if isinstance(analytics_mod, Exception):
        st.error("Analytics module failed to load.")
        st.exception(analytics_mod)

    elif hasattr(analytics_mod, "render_analytics"):
        analytics_mod.render_analytics(db, user)


# ---------------------------------------------------
# Rankings
# ---------------------------------------------------
elif page == "Rankings":

    if isinstance(rankings_mod, Exception):
        st.error("Rankings module failed to load.")
        st.exception(rankings_mod)

    elif hasattr(rankings_mod, "render_rankings"):
        rankings_mod.render_rankings(db, user)


# ---------------------------------------------------
# Universe
# ---------------------------------------------------
elif page == "Universe":

    if isinstance(universe_mod, Exception):
        st.error("Universe module failed to load.")
        st.exception(universe_mod)

    elif hasattr(universe_mod, "render_universe"):
        universe_mod.render_universe(db, user)


# ---------------------------------------------------
# Stock Dashboard
# ---------------------------------------------------
elif page == "Stock Dashboard":

    if isinstance(stock_dashboard_mod, Exception):
        st.error("Stock dashboard failed to load.")
        st.exception(stock_dashboard_mod)

    elif hasattr(stock_dashboard_mod, "render_stock_dashboard"):
        stock_dashboard_mod.render_stock_dashboard(db, user)

# ---------------------------------------------------
# Portfolio
# ---------------------------------------------------

elif page == "Portfolio":

    #st.write("🚀 ENTERED Portfolio SECTION")

    #st.write("DEBUG USER OBJECT:", user)

    print("SESSION STATE:", {
        "portfolio_id": st.session_state.get("selected_portfolio_id"),
        "portfolio_name": st.session_state.get("selected_portfolio_name"),
    })

    if isinstance(portfolio_mod, Exception):
        st.error("Portfolio module failed to load.")
        st.exception(portfolio_mod)
        st.stop()

    role = (user.get("role") or "").lower()

    st.sidebar.write("Role:", role)
    #st.write("DEBUG ROLE RESOLVED:", role)

    # ---------------------------------
    # CLIENT FLOW (ONLY CLIENT DASHBOARD)
    # ---------------------------------
    if role == "client":
        from modules.client.client_dashboard import render_client_dashboard

        st.sidebar.warning("Client View")

        render_client_dashboard(
            db_session=db,
            user=user,
            market_data_service=market_data_service,
        )

        st.stop()

    # ---------------------------------
    # ADMIN / TENANT ADMIN FLOW
    # ---------------------------------
    elif role in ["tenant_admin", "super_admin"]:
        from modules.dashboard.dashboard_ui import render_dashboard

        st.sidebar.success("Admin View")
        render_dashboard(
            db_session=db,
            user=user,
            market_data_service=market_data_service,
        )

        st.stop()

    # ---------------------------------
    # FALLBACK
    # ---------------------------------
    else:
        st.error(f"Unauthorized role: {role}")
        st.stop()

# ---------------------------------------------------
# Portfolio Construction
# ---------------------------------------------------
elif page == "Portfolio Construction":

    if isinstance(construction_mod, Exception):
        st.error("Portfolio construction module failed to load.")
        st.exception(construction_mod)

    else:
        rows = st.session_state.get("rank_rows")
        construction_mod.render_portfolio_construction(rows)


# ---------------------------------------------------
# Portfolio Deployment
# ---------------------------------------------------
elif page == "Portfolio Deployment":

    if isinstance(deployment_mod, Exception):
        st.error("Deployment module failed to load.")
        st.exception(deployment_mod)

    else:
        deployment_mod.render_portfolio_deployment(db, user)


# ---------------------------------------------------
# Market Overview
# ---------------------------------------------------
elif page == "Market Overview":

    st.header("Market Overview")

    if hasattr(market_dashboard_mod, "render_market_dashboard"):
        market_dashboard_mod.render_market_dashboard(db)

    price_cache = st.session_state.get("price_cache", {})

    if price_cache:

        if hasattr(sector_heatmap_mod, "render_sector_heatmap"):
            sector_heatmap_mod.render_sector_heatmap(price_cache)

        if hasattr(heatmap_mod, "render_market_heatmap"):
            heatmap_mod.render_market_heatmap(price_cache)

        if hasattr(regime_mod, "render_market_regime"):
            regime_mod.render_market_regime(price_cache)


# ---------------------------------------------------
# AI Rankings
# ---------------------------------------------------
elif page == "AI Rankings":

    st.header("AI Stock Rankings")

    if isinstance(ranking_ui_mod, Exception):
        st.error("AI Rankings module failed to load.")
        st.exception(ranking_ui_mod)

    else:

        if "ai_symbols" not in st.session_state:
            st.session_state.ai_symbols = ""

        if "ai_run" not in st.session_state:
            st.session_state.ai_run = False

        if "rank_rows" not in st.session_state:
            st.session_state.rank_rows = []

        symbols_input = st.text_area(
            "Universe Symbols",
            value=st.session_state.ai_symbols,
            height=120,
            key="ai_symbols_input_main"
        )

        if st.button("Load / Refresh AI Ranking Data", key="ai_rankings_btn_main"):
            st.session_state.ai_symbols = symbols_input
            st.session_state.ai_run = True

        if st.session_state.ai_run:

            raw_input = st.session_state.ai_symbols or ""

            symbols = [
                s.strip().upper()
                for s in raw_input.replace("\n", ",").split(",")
                if s.strip()
            ]

            symbols = [
                s for s in symbols
                if s.isalpha() and 1 <= len(s) <= 5
            ][:500]

            if not symbols:
                st.error("No valid symbols after filtering.")
                st.stop()

            st.write("FILTERED SYMBOL COUNT:", len(symbols))
            st.write("VALID SYMBOL SAMPLE:", symbols[:10])

            working_price_cache = {}

            with st.spinner("Loading price history..."):
                progress_bar = st.progress(0)

                for i, sym in enumerate(symbols, start=1):
                    try:
                        hist_df = get_price_history(
                            db,
                            sym,
                            period="1y",
                            interval="1d",
                            force_refresh=False,
                        )

                        if hist_df is None or hist_df.empty:
                            print("NO HISTORY:", sym)
                        else:
                            close_col = None
                            for c in ["Close", "close"]:
                                if c in hist_df.columns:
                                    close_col = c
                                    break

                            if close_col:
                                series = pd.to_numeric(
                                    hist_df[close_col], errors="coerce"
                                ).dropna()

                                if len(series) >= 20:
                                    working_price_cache[sym] = series.reset_index(drop=True)
                                else:
                                    print("NOT ENOUGH ROWS:", sym, len(series))
                            else:
                                print("NO CLOSE COLUMN:", sym, hist_df.columns.tolist())

                    except Exception as e:
                        print("AI RANKINGS HISTORY ERROR:", sym, e)

                    progress_bar.progress(int((i / len(symbols)) * 100))

            st.write("PRICE CACHE SIZE:", len(working_price_cache))
            st.write("CACHE SAMPLE:", list(working_price_cache.keys())[:10])

            st.session_state["price_cache"] = working_price_cache

            if working_price_cache:
                ranking_ui_mod.render_ai_rankings(db, user, working_price_cache)
            else:
                st.warning("No cached price data available.")

            rows = st.session_state.get("rank_rows")

            if isinstance(rows, pd.DataFrame) and not rows.empty and not isinstance(factor_mod, Exception):
                st.divider()
                factor_mod.render_factor_exposure(rows)


# ---------------------------------------------------
# Strategy Lab
# ---------------------------------------------------
elif page == "Strategy Lab":

    st.header("Strategy Lab")

    rows = st.session_state.get("rank_rows")

    if isinstance(backtest_mod, Exception):
        st.error("Backtesting module failed to load.")
        st.exception(backtest_mod)

    else:
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            backtest_mod.render_backtest(rows)
        else:
            st.info("Run AI Rankings first to generate strategies.")


# ---------------------------------------------------
# Regime Engine
# ---------------------------------------------------
elif page == "Regime Engine":

    if isinstance(regime_engine_mod, Exception):
        st.error("Regime Engine failed to load.")
        st.exception(regime_engine_mod)

    elif hasattr(regime_engine_mod, "render_regime_engine"):
        regime_engine_mod.render_regime_engine(db, user)


# ---------------------------------------------------
# Strategy Discovery
# ---------------------------------------------------
elif page == "Strategy Discovery":

    if isinstance(strategy_discovery_mod, Exception):
        st.error("Strategy Discovery module failed to load.")
        st.exception(strategy_discovery_mod)

    elif hasattr(strategy_discovery_mod, "render_strategy_discovery"):
        strategy_discovery_mod.render_strategy_discovery(db, user)


# ---------------------------------------------------
# Strategy Library
# ---------------------------------------------------
elif page == "Strategy Library":

    if isinstance(strategy_library_mod, Exception):
        st.error("Strategy Library module failed to load.")
        st.exception(strategy_library_mod)

    elif hasattr(strategy_library_mod, "render_strategy_library"):
        strategy_library_mod.render_strategy_library(db, user)


# ---------------------------------------------------
# Alerts
# ---------------------------------------------------
elif page == "Alerts":

    if isinstance(alerts_mod, Exception):
        st.error("Alerts module failed to load.")
        st.exception(alerts_mod)

    elif hasattr(alerts_mod, "render_alerts"):
        alerts_mod.render_alerts(db, user)

# ---------------------------------------------------
# Admin
# ---------------------------------------------------
elif page == "Admin":
    from modules.auth.guards import require_role
    require_role(["super_admin", "tenant_admin"])

    from modules.admin.admin_ui import render_admin_panel
    render_admin_panel(db, user)

# ---------------------------------------------------
# Help 
# ---------------------------------------------------
elif page == "Help":

    st.header("Help")

    try:
        render_help()
    except Exception as e:
        st.error("Help module failed to load.")
        st.exception(e)



# ---------------------------------------------------
# Cleanup
# ---------------------------------------------------
try:
    db.close()
except Exception:
    pass