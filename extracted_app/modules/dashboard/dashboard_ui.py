import streamlit as st
from modules.portfolio.portfolio_ui import render_portfolio_ui


def render_dashboard(db_session, user, market_data_service):

    #st.write("📊 ENTERED DASHBOARD UI")

    role = (user.get("role") or "").lower()

    # ---------------------------------
    # CLIENT ROUTING (SEND TO REAL CLIENT DASHBOARD)
    # ---------------------------------
    if role == "client":
        from modules.client.client_dashboard import render_client_dashboard

        render_client_dashboard(
            db_session=db_session,
            user=user,
            market_data_service=market_data_service
        )

        st.stop()

    # ---------------------------------
    # ADMIN / TENANT ADMIN
    # ---------------------------------
    #st.write("⚙️ ADMIN DASHBOARD")

    render_portfolio_ui(
        db_session=db_session,
        user=user,
        market_data_service=market_data_service
    )

    st.stop()





