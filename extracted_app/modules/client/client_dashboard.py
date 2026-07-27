import streamlit as st

#print("🔥 ENTERED CLIENT DASHBOARD FILE")


def render_client_dashboard(db_session, user, market_data_service):
    import os
    #st.write("🚨 ACTIVE FILE:", os.path.abspath(__file__))
    from modules.portfolio.portfolio_assignment_service import PortfolioAssignmentService
    from modules.portfolio.portfolio_ui import render_portfolio_ui

    st.markdown("# 📊 Portfolio Dashboard")

    #st.write("🚨 CLIENT DASHBOARD STARTED")

    try:
        user_id = user.get("user_id")
        tenant_id = user.get("tenant_id")

        #st.write("DEBUG USER ID:", user_id)
        #st.write("DEBUG TENANT ID:", tenant_id)

        assignment_service = PortfolioAssignmentService(db_session)

        #st.write("🚨 ABOUT TO LOAD PORTFOLIOS")

        portfolios = assignment_service.get_user_portfolios(
            tenant_id=tenant_id,
            user_id=user_id
        )

        #st.write("🔥 DEBUG CLIENT PORTFOLIOS:", portfolios)

    except Exception as e:
        st.error("❌ ERROR LOADING PORTFOLIOS")
        st.write(str(e))
        st.stop()

    if not portfolios:
        st.error("No portfolios returned")
        st.stop()

    # ---------------------------------
    # FORCE STATE
    # ---------------------------------
    if "selected_portfolio_id" not in st.session_state:
        st.session_state["selected_portfolio_id"] = portfolios[0]["id"]

    portfolio_map = {p["id"]: p["name"] for p in portfolios}
    portfolio_ids = list(portfolio_map.keys())

    #st.write("🚨 BEFORE SELECTOR")

    selected_pid = st.selectbox(
        "Select Portfolio",
        options=portfolio_ids,
        format_func=lambda x: portfolio_map[x],
        index=portfolio_ids.index(st.session_state["selected_portfolio_id"]),
        key="client_selector_debug"
    )

    # ---------------------------------
    # 🔥 FORCE RERUN ON CHANGE
    # ---------------------------------
    if selected_pid != st.session_state.get("portfolio_id"):
        st.session_state["selected_portfolio_id"] = selected_pid
        st.session_state["portfolio_id"] = selected_pid
        st.session_state["portfolio_name"] = portfolio_map[selected_pid]

        st.rerun()

    st.divider()

    #st.write("🚨 BEFORE PORTFOLIO UI")

    render_portfolio_ui(
        db_session=db_session,
        user=user,
        market_data_service=market_data_service
    )

    st.stop()