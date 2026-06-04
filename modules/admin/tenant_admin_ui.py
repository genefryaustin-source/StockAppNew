import streamlit as st
from sqlalchemy import text as sql_text
import uuid
import hashlib
from modules.admin.tenant_service import TenantService
from modules.portfolio.portfolio_assignment_service import PortfolioAssignmentService


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def render_tenant_admin_panel(db, user):

    # FIX 1: Moved title/success inside a header area that doesn't
    # repeat awkwardly when embedded in admin_ui tabs — use st.header
    # instead of st.title to avoid duplicate H1 nesting.
    st.header("Tenant Administration")

    role = user.get("role")
    tenant_id = user.get("tenant_id")

    if not tenant_id:
        st.error("❌ No tenant context passed from Admin panel")
        st.stop()

    st.success(f"✅ Active Tenant: {tenant_id}")

    # ---------------------------------
    # TABS
    # FIX 2: Use consistent tab structure for both roles so the rest
    # of the function can always use `with tab_users:` without
    # branching. For non-super-admins, omit the Tenants tab entirely.
    # ---------------------------------
    if role == "super_admin":
        tab_users, tab_tenants = st.tabs(["👤 Users", "🏢 Tenants"])
    else:
        tab_users, = st.tabs(["👤 Users"])
        tab_tenants = None

    # ========================================
    # USERS TAB
    # ========================================
    with tab_users:

        # ---------------------------------
        # CREATE PORTFOLIO
        # ---------------------------------
        st.subheader("Create Portfolio")

        pname = st.text_input(
            "Portfolio Name",
            key="tenant_ui_new_portfolio_name",  # FIX 3: unique key
        )

        if st.button("Create Portfolio", key="tenant_ui_create_portfolio"):
            if not pname:
                st.warning("Enter a portfolio name.")
            else:
                try:
                    db.execute(sql_text("""
                        INSERT INTO portfolios (
                            id,
                            tenant_id,
                            name,
                            description,
                            benchmark,
                            base_currency,
                            starting_cash,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :id,
                            :tenant_id,
                            :name,
                            :description,
                            :benchmark,
                            :base_currency,
                            :starting_cash,
                            1,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                    """), {
                        "id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "name": pname.strip(),
                        "description": "",
                        "benchmark": "SPY",
                        "base_currency": "USD",
                        "starting_cash": 100000.0,
                    })
                    db.commit()
                    st.success(f"Portfolio '{pname}' created.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create portfolio: {e}")

        # ---------------------------------
        # CREATE USER
        # ---------------------------------
        st.divider()
        st.subheader("Create User")

        col1, col2 = st.columns(2)

        new_email = col1.text_input(
            "Email",
            key="tenant_ui_create_user_email",
        )
        new_password = col2.text_input(
            "Password",
            type="password",
            key="tenant_ui_create_user_password",
        )

        role_options = ["client"]
        if role in ("tenant_admin", "super_admin"):
            role_options.append("tenant_admin")
        if role == "super_admin":
            role_options.append("super_admin")

        new_role = st.selectbox(
            "Role",
            role_options,
            key="tenant_ui_create_user_role",
        )

        if st.button("Create User", key="tenant_ui_create_user"):
            if not new_email or not new_password:
                st.warning("Email and password are required.")
            else:
                try:
                    db.execute(sql_text("""
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
                        "email": new_email.lower().strip(),
                        "pw": _hash_password(new_password),
                        "role": new_role,
                        "tenant": tenant_id,
                    })
                    db.commit()
                    st.success("User created.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create user: {e}")

        # ---------------------------------
        # USER LIST + INLINE CRUD
        # FIX 4: Was read-only. Now includes edit role, toggle
        # active, reset password, and delete per user.
        # ---------------------------------
        st.divider()
        st.subheader("Tenant Users")

        user_rows = db.execute(sql_text("""
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

                with st.expander(
                    f"{'🟢' if active else '🔴'}  {email_u}  —  {role_u}"
                ):
                    e1, e2 = st.columns(2)

                    edited_email = e1.text_input(
                        "Email",
                        value=email_u,
                        key=f"tenant_ui_edit_email_{uid}",
                    )
                    edited_role = e2.selectbox(
                        "Role",
                        role_options,
                        index=role_options.index(role_u)
                              if role_u in role_options else 0,
                        key=f"tenant_ui_edit_role_{uid}",
                    )

                    b1, b2, b3, b4 = st.columns(4)

                    # Save
                    if b1.button("Save", key=f"tenant_ui_save_{uid}"):
                        try:
                            db.execute(sql_text("""
                                UPDATE users
                                SET email = :email,
                                    role  = :role
                                WHERE id = :id
                            """), {
                                "email": edited_email.lower().strip(),
                                "role": edited_role,
                                "id": uid,
                            })
                            db.commit()
                            st.success("User updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")

                    # Toggle active
                    toggle_label = (
                        "Deactivate" if active else "Reactivate"
                    )
                    if b2.button(
                        toggle_label,
                        key=f"tenant_ui_toggle_{uid}",
                    ):
                        try:
                            db.execute(sql_text("""
                                UPDATE users
                                SET is_active = :val
                                WHERE id = :id
                            """), {
                                "val": 0 if active else 1,
                                "id": uid,
                            })
                            db.commit()
                            st.success("Status updated.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Status change failed: {e}")

                    # Reset password
                    new_pw = st.text_input(
                        "New Password",
                        type="password",
                        key=f"tenant_ui_reset_pw_{uid}",
                    )
                    if b3.button(
                        "Reset PW",
                        key=f"tenant_ui_reset_pw_btn_{uid}",
                    ):
                        if not new_pw:
                            st.warning("Enter a new password first.")
                        else:
                            try:
                                db.execute(sql_text("""
                                    UPDATE users
                                    SET password_hash = :pw
                                    WHERE id = :id
                                """), {
                                    "pw": _hash_password(new_pw),
                                    "id": uid,
                                })
                                db.commit()
                                st.success("Password reset.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Reset failed: {e}")

                    # Delete
                    if b4.button(
                        "Delete",
                        key=f"tenant_ui_delete_{uid}",
                        type="secondary",
                    ):
                        if uid == user.get("user_id"):
                            st.error(
                                "You cannot delete your own account."
                            )
                        else:
                            try:
                                db.execute(sql_text("""
                                    DELETE FROM users
                                    WHERE id = :id
                                """), {"id": uid})
                                db.commit()
                                st.success("User deleted.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")

        # ---------------------------------
        # PORTFOLIO ASSIGNMENTS
        # FIX 5: Replaced `return` with early-exit messages that
        # don't abort the whole function (and thus the Tenants tab).
        # ---------------------------------
        st.divider()
        st.subheader("Portfolio Assignments")

        assignment_service = PortfolioAssignmentService(db)

        client_rows = db.execute(sql_text("""
            SELECT id, email
            FROM users
            WHERE tenant_id = :tenant
              AND role = 'client'
            ORDER BY email
        """), {"tenant": tenant_id}).fetchall()

        if not client_rows:
            st.info("No client users found. Create a client user above.")
        else:
            user_map = {u[0]: u[1] for u in client_rows}

            selected_user = st.selectbox(
                "Select Client",
                options=list(user_map.keys()),
                format_func=lambda x: user_map[x],
                key="tenant_ui_assignment_client",
            )

            portfolios = db.execute(("""
                SELECT id, name
                FROM portfoliossql_text
                WHERE tenant_id = :tenant
                ORDER BY name
            """), {"tenant": tenant_id}).fetchall()

            if not portfolios:
                st.warning(
                    "No portfolios yet. Create one above before assigning."
                )
            else:
                portfolio_map = {p[0]: p[1] for p in portfolios}

                assigned = assignment_service.get_user_portfolios(
                    tenant_id=tenant_id,
                    user_id=selected_user,
                )
                assigned_ids = [p["id"] for p in assigned]

                selected_portfolios = st.multiselect(
                    "Assign Portfolios",
                    options=list(portfolio_map.keys()),
                    default=assigned_ids,
                    format_func=lambda x: portfolio_map[x],
                    key="tenant_ui_assignment_portfolios",
                )

                if st.button(
                    "Save Assignments",
                    key="tenant_ui_save_assignments",
                ):
                    try:
                        for pid in assigned_ids:
                            if pid not in selected_portfolios:
                                assignment_service.remove_assignment(
                                    tenant_id=tenant_id,
                                    user_id=selected_user,
                                    portfolio_id=pid,
                                )

                        for pid in selected_portfolios:
                            if pid not in assigned_ids:
                                assignment_service.assign_portfolio_to_user(
                                    tenant_id=tenant_id,
                                    user_id=selected_user,
                                    portfolio_id=pid,
                                )

                        st.success("Assignments updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Assignment update failed: {e}")

    # ========================================
    # TENANT MANAGEMENT TAB (Super Admin Only)
    # ========================================
    if tab_tenants:
        with tab_tenants:

            st.header("🏢 Tenant Management")

            service = TenantService(db)

            # --- CREATE NEW TENANT ---
            st.subheader("➕ Create New Tenant")

            new_tenant_name = st.text_input(
                "Tenant Name",
                key="tenant_ui_new_tenant_name",  # FIX 6: unique key
                placeholder="Acme Corporation",
            )

            if st.button(
                "Create Tenant",
                type="primary",
                key="tenant_ui_create_tenant",
            ):
                if not new_tenant_name or not new_tenant_name.strip():
                    st.error("Tenant name is required.")
                else:
                    try:
                        new_id = service.create_tenant(
                            new_tenant_name.strip()
                        )
                        st.success(
                            f"✅ Tenant '{new_tenant_name}' created! "
                            f"(ID: {new_id})"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create tenant: {e}")

            st.divider()

            # --- LIST & MANAGE EXISTING TENANTS ---
            # FIX 7: Added rename (update) functionality alongside
            # activate/deactivate for full CRUD on tenants.
            st.subheader("Existing Tenants")


            debug_rows = db.execute(sql_text("""
                SELECT id, name, created_at
                FROM tenants
                ORDER BY created_at DESC
                """)
            ).fetchall()

            st.write("TENANT DEBUG:", debug_rows)
            tenants = service.list_tenants()

            if not tenants:
                st.info("No tenants found.")
            else:
                for tenant in tenants:
                    with st.expander(
                        f"{'🟢' if tenant['is_active'] else '🔴'}  "
                        f"{tenant['name']}  "
                        f"(ID: {tenant['id'][:8]}...)"
                    ):
                        t1, t2 = st.columns([3, 1])

                        edited_name = t1.text_input(
                            "Name",
                            value=tenant["name"],
                            key=f"tenant_ui_rename_{tenant['id']}",
                        )

                        if t2.button(
                            "Save Name",
                            key=f"tenant_ui_save_name_{tenant['id']}",
                        ):
                            if not edited_name.strip():
                                st.error("Name cannot be blank.")
                            else:
                                try:
                                    service.update_tenant(
                                        tenant["id"],
                                        edited_name.strip(),
                                    )
                                    st.success("Tenant renamed.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Rename failed: {e}")

                        a1, a2 = st.columns(2)

                        if tenant["is_active"]:
                            if a1.button(
                                "Deactivate",
                                key=f"tenant_ui_deact_{tenant['id']}",
                            ):
                                service.deactivate_tenant(tenant["id"])
                                st.rerun()
                        else:
                            if a1.button(
                                "Activate",
                                key=f"tenant_ui_act_{tenant['id']}",
                            ):
                                service.activate_tenant(tenant["id"])
                                st.rerun()

                        a2.caption(
                            f"Created: {tenant['created_at']}"
                        )