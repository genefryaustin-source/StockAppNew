import time
import streamlit as st
from modules.auth.auth_service import SESSION_TIMEOUT_MINUTES, logout


def enforce_session_timeout():
    now = time.time()
    last_activity = st.session_state.get("last_activity_ts")

    if last_activity is None:
        st.session_state["last_activity_ts"] = now
        return

    timeout_seconds = SESSION_TIMEOUT_MINUTES * 60

    if now - last_activity > timeout_seconds:
        logout()
        st.warning("Session expired. Please log in again.")
        st.stop()

    st.session_state["last_activity_ts"] = now


def require_login():
    if "user" not in st.session_state:
        st.error("Please log in.")
        st.stop()


def require_role(allowed_roles):
    user = st.session_state.get("user")
    if not user:
        st.error("Please log in.")
        st.stop()

    role = user.get("role")
    if role not in allowed_roles:
        st.error("Unauthorized")
        st.stop()