import streamlit as st
import json

from modules.api.portfolio_api import PortfolioAPI


def render_api_ui(
    db_session,
    portfolio_id,
    totals,
    health,
    df_pos,
    sleeve_df,
    trades_df,
    risk_df,
):

    st.header("Live API Layer")

    api = PortfolioAPI(db_session)

    snapshot = api.get_portfolio_snapshot(
        portfolio_id=portfolio_id,
        totals=totals,
        health=health,
        df_pos=df_pos,
        sleeve_df=sleeve_df,
        trades_df=trades_df,
        risk_df=risk_df,
    )

    st.subheader("Portfolio Snapshot API Response")
    st.json(snapshot)

    st.subheader("Endpoints")

    if st.checkbox("Show Positions Endpoint"):
        st.json(api.get_positions(df_pos))

    if st.checkbox("Show Strategies Endpoint"):
        st.json(api.get_strategies(sleeve_df))

    if st.checkbox("Show Trades Endpoint"):
        st.json(api.get_trades(trades_df))

    if st.checkbox("Show Risk Endpoint"):
        st.json(api.get_risk(risk_df))

    st.subheader("Export API Snapshot")

    st.download_button(
        "Download API JSON",
        data=json.dumps(snapshot, indent=2),
        file_name=f"api_snapshot_{portfolio_id}.json",
        mime="application/json",
    )