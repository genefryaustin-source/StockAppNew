import streamlit as st

def render_dashboard(db, user):

    st.subheader("Dashboard")

    st.write("Institutional Terminal Active")

    st.write("User:", user["email"])