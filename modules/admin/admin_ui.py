import pandas as pd
import streamlit as st

from sqlalchemy import text

from modules.auth.auth_service import (
    create_user,
    update_user,
    set_user_active,
    reset_user_password,
    delete_user,
)

from modules.admin.tenant_admin_ui import (
    render_tenant_admin_panel,
)

from modules.universe.universe_cleanup_ui import (
    render_universe_cleanup_ui,
)

st.warning("ADMIN_UI IMPORTED")
# ---------------------------------------------------------
# ACTIVE TENANT
# ---------------------------------------------------------
def get_active_tenant(user):

    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")

    return user.get("tenant_id")


# ---------------------------------------------------------
# ADMIN PANEL
# ---------------------------------------------------------
def render_admin_panel(db, user):

    st.title("ADMIN DEBUG")

    st.write("FUNCTION STARTED")

    try:

        st.write("IMPORTS OK")

        role = user.get("role")
        tenant_id = user.get("tenant_id")

        st.write("ROLE:", role)
        st.write("TENANT:", tenant_id)

        st.write("BEFORE TABS")

        tab1, tab2 = st.tabs([
            "Tab1",
            "Tab2",
        ])

        st.write("AFTER TABS")

        with tab1:

            st.write("TAB1 LOADED")

        with tab2:

            st.write("TAB2 LOADED")

    except Exception as e:

        st.exception(e)