import streamlit as st
import os
import sys
import traceback

st.set_page_config(page_title="Diagnostic", layout="wide")
st.title("🛠️ Streamlit Cloud Diagnostic")
st.write("**Python version:**", sys.version)
st.write("**Working directory:**", os.getcwd())

def test_import(label, fn):
    try:
        fn()
        st.success(f"✅ {label}")
        return True
    except Exception as e:
        st.error(f"❌ {label}")
        st.code(traceback.format_exc())
        return False

st.subheader("1️⃣ Core Libraries")
test_import("pandas", lambda: __import__("pandas"))
test_import("plotly", lambda: __import__("plotly"))
test_import("yfinance", lambda: __import__("yfinance"))
test_import("sqlalchemy", lambda: __import__("sqlalchemy"))
test_import("openai", lambda: __import__("openai"))

st.subheader("2️⃣ App Modules")
test_import("modules.db.core", lambda: __import__("modules.db.core", fromlist=["init_database", "SessionLocal"]))
test_import("modules.db.models", lambda: __import__("modules.db.models"))
test_import("modules.institutional.models", lambda: __import__("modules.institutional.models"))
test_import("modules.analytics.models", lambda: __import__("modules.analytics.models"))
test_import("modules.alerts.models", lambda: __import__("modules.alerts.models"))
test_import("modules.universe.models", lambda: __import__("modules.universe.models"))
test_import("modules.jobs.models", lambda: __import__("modules.jobs.models"))
test_import("modules.market_data.models", lambda: __import__("modules.market_data.models"))
test_import("modules.analytics.strategy_models", lambda: __import__("modules.analytics.strategy_models"))

st.subheader("3️⃣ Models")
test_import("models.strategy_run", lambda: __import__("models.strategy_run", fromlist=["StrategyRun"]))
test_import("models.trading", lambda: __import__("models.trading", fromlist=["TradeOrder"]))
test_import("models.base", lambda: __import__("models.base", fromlist=["Base"]))

st.subheader("4️⃣ Services")
test_import("modules.market_data.service", lambda: __import__("modules.market_data.service"))
test_import("modules.auth.auth_service", lambda: __import__("modules.auth.auth_service", fromlist=["logout"]))
test_import("modules.auth.login_ui", lambda: __import__("modules.auth.login_ui", fromlist=["render_login"]))
test_import("modules.auth.guards", lambda: __import__("modules.auth.guards", fromlist=["enforce_session_timeout"]))
test_import("modules.portfolio.portfolio_ui", lambda: __import__("modules.portfolio.portfolio_ui", fromlist=["render_portfolio_ui"]))
test_import("modules.portfolio.nav_service", lambda: __import__("modules.portfolio.nav_service", fromlist=["NavService"]))
test_import("modules.portfolio.order_service", lambda: __import__("modules.portfolio.order_service", fromlist=["OrderService"]))
test_import("modules.alerts.service", lambda: __import__("modules.alerts.service", fromlist=["AlertService"]))
test_import("modules.help.help_ui", lambda: __import__("modules.help.help_ui", fromlist=["render_help"]))

st.subheader("5️⃣ Seeder")
test_import("scripts.seed_db", lambda: __import__("scripts.seed_db", fromlist=["run_seed"]))

st.subheader("6️⃣ Database Init")
def test_db():
    from modules.db.core import init_database, SessionLocal
    init_database()
    db = SessionLocal()
    db.close()
test_import("init_database()", test_db)

st.info("✅ Fix every ❌ above before restoring the real app.py")