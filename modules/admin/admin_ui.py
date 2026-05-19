import pandas as pd
import streamlit as st
from modules.auth.auth_service import (
    create_user,
    list_users_for_scope,
    update_user,
    set_user_active,
    reset_user_password,
    delete_user,
)
from modules.admin.tenant_admin_ui import render_tenant_admin_panel
def get_active_tenant(user):
    if user.get("role") == "super_admin":
        return st.session_state.get("admin_selected_tenant")
    return user.get("tenant_id")
def render_admin_panel(db, user):
    #st.write("DEBUG SELECTED TENANT:", st.session_state.get("admin_selected_tenant"))
    from sqlalchemy import text

    # 🔥 FIX TENANT ID IF NAME WAS STORED
    if user.get("tenant_id") and not str(user.get("tenant_id")).startswith(
            ("a", "b", "c", "d", "e", "f", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):

        tenant_lookup = db.execute(text("""
            SELECT id
            FROM tenants
            WHERE name = :name
        """), {"name": user.get("tenant_id")}).fetchone()

        if tenant_lookup:
            user["tenant_id"] = tenant_lookup[0]
            st.session_state["user"]["tenant_id"] = tenant_lookup[0]

            #st.warning("⚠️ Fixed tenant_id from name → UUID")
            #st.write("NEW TENANT ID:", tenant_lookup[0])
    role = user.get("role")
    tenant_id = user.get("tenant_id")

    st.title("Admin")
    from sqlalchemy import text
    #st.write("DEBUG SESSION STATE:", dict(st.session_state))
    # ---------------------------------
    # TENANT SELECTOR (SUPER ADMIN ONLY)
    # ---------------------------------
    if role == "super_admin":

        tenants = db.execute(text("""
            SELECT id, name
            FROM tenants
            ORDER BY name
        """)).fetchall()

        if tenants:
            tenant_map = {t[0]: t[1] for t in tenants}
            tenant_ids = list(tenant_map.keys())

            # ✅ FORCE DEFAULT
            if "admin_selected_tenant" not in st.session_state or not st.session_state["admin_selected_tenant"]:
                st.session_state["admin_selected_tenant"] = tenant_ids[0]

            selected_tenant = st.selectbox(
                "Select Tenant",
                options=tenant_ids,
                format_func=lambda x: tenant_map[x],
                key="admin_selected_tenant"
            )

            tenant_id = selected_tenant

            st.success(f"Managing Tenant: {tenant_map[tenant_id]}")

        else:
            st.warning("No tenants found.")
            return

    # ---------------------------------
    # CREATE USER
    # ---------------------------------
    st.subheader("Create User")

    c1, c2 = st.columns(2)
    new_email = c1.text_input("Email", key="admin_new_email")
    new_password = c2.text_input("Password", type="password", key="admin_new_password")

    allowed_roles = ["client", "tenant_admin"] if role == "tenant_admin" else ["client", "tenant_admin", "super_admin"]
    new_role = st.selectbox("Role", allowed_roles, key="admin_new_role")

    if role == "super_admin":
        new_tenant_id = st.text_input("Tenant ID", value=tenant_id or "", key="admin_new_tenant")
    else:
        new_tenant_id = tenant_id

    if st.button("Create User", key="admin_create_user"):
        if not new_email or not new_password:
            st.warning("Email and password are required.")
        else:
            try:
                create_user(
                    db=db,
                    email=new_email,
                    password=new_password,
                    role=new_role,
                    tenant_id=new_tenant_id,
                    is_active=1,
                )
                st.success("User created.")
                st.rerun()
            except Exception as e:
                st.error(f"Create failed: {e}")

    # ---------------------------------
    # USER LIST
    # ---------------------------------
    st.divider()
    st.subheader("Users")

    rows = db.execute(text("""
        SELECT *
        FROM users
        WHERE tenant_id = :tenant
    """), {"tenant": tenant_id}).fetchall()

    if not rows:
        st.info("No users found.")
        return

    df = pd.DataFrame([dict(r._mapping) for r in rows])
    display_df = df.copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ---------------------------------
    # EDIT / ACTIONS
    # ---------------------------------
    st.divider()
    st.subheader("Manage User")

    user_options = {
        f"{r.email} | {r.role} | {r.id}": r.id
        for r in rows
    }

    selected_label = st.selectbox("Select User", list(user_options.keys()), key="admin_selected_user")
    selected_user_id = user_options[selected_label]

    selected_row = df[df["id"] == selected_user_id].iloc[0]

    e1, e2 = st.columns(2)
    edit_email = e1.text_input("Edit Email", value=selected_row["email"], key="admin_edit_email")
    edit_role = e2.selectbox(
        "Edit Role",
        allowed_roles,
        index=max(0, allowed_roles.index(selected_row["role"])) if selected_row["role"] in allowed_roles else 0,
        key="admin_edit_role"
    )

    if role == "super_admin":
        edit_tenant_id = st.text_input(
            "Edit Tenant ID",
            value="" if pd.isna(selected_row.get("tenant_id")) else str(selected_row.get("tenant_id")),
            key="admin_edit_tenant"
        )
    else:
        edit_tenant_id = tenant_id

    a1, a2, a3, a4 = st.columns(4)

    if a1.button("Save Changes", key="admin_save_user"):
        try:
            update_user(
                db=db,
                target_user_id=selected_user_id,
                email=edit_email,
                role=edit_role,
                tenant_id=edit_tenant_id,
            )
            st.success("User updated.")
            st.rerun()
        except Exception as e:
            st.error(f"Update failed: {e}")

    is_active = bool(selected_row["is_active"])
    toggle_label = "Deactivate User" if is_active else "Reactivate User"

    if a2.button(toggle_label, key="admin_toggle_user"):
        try:
            set_user_active(db, selected_user_id, not is_active)
            st.success("User status updated.")
            st.rerun()
        except Exception as e:
            st.error(f"Status change failed: {e}")

    new_reset_password = st.text_input("Reset Password", type="password", key="admin_reset_password")

    if a3.button("Reset Password", key="admin_reset_user_pw"):
        if not new_reset_password:
            st.warning("Enter a new password first.")
        else:
            try:
                reset_user_password(db, selected_user_id, new_reset_password)
                st.success("Password reset.")
                st.rerun()
            except Exception as e:
                st.error(f"Password reset failed: {e}")

    if a4.button("Delete User", key="admin_delete_user"):
        try:
            if selected_user_id == user.get("user_id"):
                st.error("You cannot delete your own logged-in account.")
            else:
                delete_user(db, selected_user_id)
                st.success("User deleted.")
                st.rerun()
        except Exception as e:
            st.error(f"Delete failed: {e}")

    tab_users, tab_tenants = st.tabs(["Users", "Tenants"])

    with tab_tenants:

        if role == "super_admin":
            tenant_id = st.session_state.get("admin_selected_tenant")
        else:
            tenant_id = user.get("tenant_id")

        #st.write("DEBUG FINAL TENANT:", tenant_id)

        if not tenant_id:
            st.error("❌ No tenant context available")
            st.stop()

        render_tenant_admin_panel(
            db,
            {
                **user,
                "tenant_id": tenant_id
            }
        )


