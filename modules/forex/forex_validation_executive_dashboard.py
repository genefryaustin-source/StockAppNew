from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _safe_import(path,name):
    m=__import__(path,fromlist=[name]); return getattr(m,name)

try:
    import streamlit as st
except Exception:
    st=None
def render_forex_validation_executive_dashboard(db=None,user=None):
    if st is None:return
    st.title("Forex Validation Executive Dashboard")
    Center=_safe_import("modules.forex.forex_validation_center","ForexValidationCenter")
    if st.button("Refresh Executive Summary",key="fx_val_exec_refresh"):
        st.json(Center().status())
