import streamlit as st
from modules.institutional.earnings import list_upcoming

def render_earnings(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Earnings Calendar")

    events = list_upcoming(db, tenant_id)

    if not events:

        st.info("No earnings data")

        return

    for e in events:

        st.write(
            e.symbol,
            e.event_date,
            e.eps_est
        )