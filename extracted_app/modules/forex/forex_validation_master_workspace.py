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
def render_forex_validation_master_workspace(db=None,user=None):
    if st is None:return
    st.title("Forex Validation Master Workspace")
    page=st.radio("Workspace",["Validation Center","Executive Dashboard","Release Dashboard"],horizontal=True,key="fx_val_master")
    if page=="Validation Center":
        mod=_safe_import("modules.forex.forex_validation_dashboard","render_forex_validation_dashboard"); mod(db=db,user=user)
    elif page=="Executive Dashboard":
        mod=_safe_import("modules.forex.forex_validation_executive_dashboard","render_forex_validation_executive_dashboard"); mod(db=db,user=user)
    else:
        mod=_safe_import("modules.forex.forex_release_dashboard","render_forex_release_dashboard"); mod(db=db,user=user)
