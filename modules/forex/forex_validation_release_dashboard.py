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
def render_forex_validation_release_dashboard(db=None,user=None):
    if st is None:return
    st.title("Forex Validation Release Readiness")
    R=_safe_import("modules.forex.forex_release_validator","ForexReleaseValidator")
    if st.button("Validate Release",key="fx_val_release"):
        st.json(R().validate())
