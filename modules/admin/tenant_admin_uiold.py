import streamlit as st
from sqlalchemy import text
import uuid
import hashlib
import os
from modules.admin.tenant_service import TenantService
from modules.portfolio.portfolio_assignment_service import PortfolioAssignmentService

#st.write("DEBUG FILE LOADED:", __file__)

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def render_tenant_admin_panel(db, user):

    st.title("Tenant Administration")

    role = user.get("role")
    tenant_id = user.get("tenant_id")

    if not tenant_id:
        st.error("❌ No tenant context passed from Admin panel")
        st.stop()

    st.success(f"✅ ACTIVE TENANT: {tenant_id}")

    # ---------------------------------
    # TABS
    # ---------------------------------
    if role == "super_admin":
        tab_users, tab_tenants = st.tabs(["👤 Users", "🏢 Tenants"])
    else:
        tab_users = st.container()
        tab_tenants = None

    # ---------------------------------
    # USERS TAB
    # ---------------------------------
    with tab_users:

        # ---------------------------------
        # CREATE PORTFOLIO
        # ---------------------------------
        st.subheader("Create Portfolio")

        pname = st.text_input("Portfolio Name", key="new_portfolio_name")

        if st.button("Create Portfolio"):
            if not pname:
                st.warning("Enter a portfolio name")
            else:
                db.execute(text("""
                    INSERT INTO portfolios (
                        id,
                        name,
                        tenant_id,
                        created_at
                    )
                    VALUES (
                        :id,
                        :name,
                        :tenant,
                        CURRENT_TIMESTAMP
                    )
                """), {
                    "id": str(uuid.uuid4()),
                    "name": pname,
                    "tenant": tenant_id
                })
                db.commit()
                st.success(f"Portfolio '{pname}' created")
                st.rerun()

        # ---------------------------------
        # CREATE USER
        # ---------------------------------
        st.divider()
        st.subheader("Create User")

        col1, col2 = st.columns(2)

        email = col1.text_input("Email", key="create_user_email")
        password = col2.text_input("Password", type="password", key="create_user_password")

        role_options = ["client"]
        if role == "tenant_admin":
            role_options.append("tenant_admin")
        if role == "super_admin":
            role_options.extend(["tenant_admin", "super_admin"])

        new_role = st.selectbox("Role", role_options, key="create_user_role")

        if st.button("Create User"):

            if not email or not password:
                st.warning("Email and password required")
            else:
                db.execute(text("""
                    INSERT INTO users (
                        id,
                        email,
                        password_hash,
                        role,
                        tenant_id,
                        is_active
                    )
                    VALUES (
                        :id,
                        :email,
                        :pw,
                        :role,
                        :tenant,
                        1
                    )
                """), {
                    "id": str(uuid.uuid4()),
                    "email": email.lower().strip(),
                    "pw": _hash_password(password),
                    "role": new_role,
                    "tenant": tenant_id
                })
                db.commit()
                st.success("User created")
                st.rerun()

        # ---------------------------------
        # USER LIST
        # ---------------------------------
        st.divider()
        st.subheader("Tenant Users")

        user_rows = db.execute(text("""
            SELECT id, email, role, is_active
            FROM users
            WHERE tenant_id = :tenant
            ORDER BY email
        """), {"tenant": tenant_id}).fetchall()

        if not user_rows:
            st.info("No users yet.")
        else:
            for u in user_rows:
                uid, email_u, role_u, active = u

                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(email_u)
                c2.write(role_u)
                c3.write("🟢" if active else "🔴")

        # ---------------------------------
        # PORTFOLIO ASSIGNMENTS (GLOBAL)
        # ---------------------------------
        st.divider()
        st.subheader("Portfolio Assignments")

        assignment_service = PortfolioAssignmentService(db)

        client_rows = db.execute(text("""
            SELECT id, email
            FROM users
            WHERE tenant_id = :tenant
            AND role = 'client'
        """), {"tenant": tenant_id}).fetchall()

        if not client_rows:
            st.info("No client users found.")
            return

        user_map = {u[0]: u[1] for u in client_rows}

        selected_user = st.selectbox(
            "Select Client",
            options=list(user_map.keys()),
            format_func=lambda x: user_map[x]
        )

        # DEBUG
        #st.write("DEBUG TENANT:", tenant_id)
        #st.write("DEBUG SELECTED USER:", selected_user)

        portfolios = db.execute(text("""
            SELECT id, name
            FROM portfolios
            WHERE tenant_id = :tenant
        """), {"tenant": tenant_id}).fetchall()

        if not portfolios:
            st.warning("No portfolios created yet.")
            return

        portfolio_map = {p[0]: p[1] for p in portfolios}

        # ✅ FIXED ORDER
        assigned = assignment_service.get_user_portfolios(
            tenant_id=tenant_id,
            user_id=selected_user
        )

        assigned_ids = [p["id"] for p in assigned]

        # DEBUG
        #st.write("DEBUG CURRENT ASSIGNED IDS:", assigned_ids)

        selected_portfolios = st.multiselect(
            "Assign Portfolios",
            options=list(portfolio_map.keys()),
            default=assigned_ids,
            format_func=lambda x: portfolio_map[x]
        )

        if st.button("Save Assignments"):

            # REMOVE UNCHECKED
            for pid in assigned_ids:
                if pid not in selected_portfolios:
                    assignment_service.remove_assignment(
                        tenant_id=tenant_id,
                        user_id=selected_user,
                        portfolio_id=pid
                    )

            # ADD NEW
            for pid in selected_portfolios:
                if pid not in assigned_ids:
                    assignment_service.assign_portfolio_to_user(
                        tenant_id=tenant_id,
                        user_id=selected_user,
                        portfolio_id=pid
                    )

            st.success("Assignments updated")
            st.rerun()

    # ---------------------------------
    # TENANT MANAGEMENT
    # ---------------------------------
    if tab_tenants:

        with tab_tenants:

            st.header("🏢 Tenant Management")

            service = TenantService(db)

            tenants = service.list_tenants()

            selected = next((t for t in tenants if t["id"] == tenant_id), None)

            if not selected:
                st.error("Selected tenant not found.")
                return

            st.markdown(f"### 🏢 Managing Tenant: {selected['name']}")

            col1, col2, col3 = st.columns([3, 2, 1])

            col1.write(selected["name"])
            col2.write("🟢 Active" if selected["is_active"] else "🔴 Inactive")

            if selected["is_active"]:
                if col3.button("Deactivate Tenant"):
                    service.deactivate_tenant(selected["id"])
                    st.rerun()
            else:
                if col3.button("Activate Tenant"):
                    service.activate_tenant(selected["id"])
                    st.rerun()