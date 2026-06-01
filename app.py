import streamlit as st
import sys
import os
import traceback

st.set_page_config(page_title="Equity Research Terminal", layout="wide")

_diag = []

def _test(label, fn):
    try:
        fn()
        _diag.append(f"✅ {label}")
        return True
    except Exception as e:
        _diag.append(f"❌ {label}\n{traceback.format_exc()}")
        return False

_test("pandas",       lambda: __import__("pandas"))
_test("sqlalchemy",   lambda: __import__("sqlalchemy"))
_test("matplotlib",   lambda: __import__("matplotlib"))
_test("diskcache",    lambda: __import__("diskcache"))
_test("anthropic",    lambda: __import__("anthropic"))
_test("yfinance",     lambda: __import__("yfinance"))
_test("db.core",      lambda: __import__("modules.db.core", fromlist=["*"]))
_test("db.models",    lambda: __import__("modules.db.models", fromlist=["*"]))
_test("inst.models",  lambda: __import__("modules.institutional.models", fromlist=["*"]))
_test("analytics.models", lambda: __import__("modules.analytics.models", fromlist=["*"]))
_test("alerts.models",    lambda: __import__("modules.alerts.models", fromlist=["*"]))
_test("universe.models",  lambda: __import__("modules.universe.models", fromlist=["*"]))
_test("jobs.models",      lambda: __import__("modules.jobs.models", fromlist=["*"]))
_test("market_data.models", lambda: __import__("modules.market_data.models", fromlist=["*"]))
_test("strategy_models",  lambda: __import__("modules.analytics.strategy_models", fromlist=["*"]))
_test("auth.login_ui",    lambda: __import__("modules.auth.login_ui", fromlist=["*"]))
_test("nav_service",      lambda: __import__("modules.portfolio.nav_service", fromlist=["*"]))
_test("order_service",    lambda: __import__("modules.portfolio.order_service", fromlist=["*"]))
_test("alerts.service",   lambda: __import__("modules.alerts.service", fromlist=["*"]))
_test("forecasting",      lambda: __import__("modules.forecasting.forecast_ui", fromlist=["*"]))

for line in _diag:
    if line.startswith("❌"):
        st.error(line)
        st.stop()

st.success("✅ All imports OK")
st.code("\n".join(_diag))