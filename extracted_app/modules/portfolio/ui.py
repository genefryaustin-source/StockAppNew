import streamlit as st
from modules.portfolio.portfolio_assignment_service import PortfolioAssignmentService
from modules.portfolio.portfolio_ui import render_portfolio_ui


def render_portfolios(db, user, market_data_service):

    #st.write("🚀 ENTERED Portfolio SECTION")

    user_id = user.get("user_id") or user.get("id")
    tenant_id = user.get("tenant_id")
    role = (user.get("role") or "").lower()

    #st.write("DEBUG USER:", user)
    st.write("DEBUG CONTEXT:", {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role
    })

    # ---------------------------------
    # 🔥 CLIENT FLOW (FIXED)
    # ---------------------------------
    if role == "client":

        # 🚨 IMPORTANT: DO NOT CALL portfolio_ui HERE
        # Route client to client_dashboard ONLY

        from modules.client.client_dashboard import render_client_dashboard

        render_client_dashboard(
            db_session=db,
            user=user,
            market_data_service=market_data_service
        )

        st.stop()  # 🔥 CRITICAL: prevent any further execution

    # ---------------------------------
    # 🔥 ADMIN / TENANT ADMIN FLOW
    # ---------------------------------
    else:
        st.write("⚙️ NON-CLIENT FLOW")

        # Admins go directly to portfolio UI
        render_portfolio_ui(
            db_session=db,
            user=user,
            market_data_service=market_data_service
        )

        st.stop()