import streamlit as st
from modules.institutional.screener import run_screener

def render_screener(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Stock Screener")

    symbols = st.text_area(
        "Symbols (comma separated)",
        "AAPL,MSFT,NVDA,PLTR,TSLA"
    )

    min_price = st.number_input("Min Price", value=0.0)

    if st.button("Run Screener"):

        symbol_list = [
            s.strip().upper()
            for s in symbols.split(",")
        ]

        results = run_screener(
            db,
            tenant_id,
            symbol_list,
            min_price=min_price
        )

        st.dataframe(results)