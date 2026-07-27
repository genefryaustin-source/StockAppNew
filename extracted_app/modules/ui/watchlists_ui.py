import streamlit as st
from modules.institutional.watchlists import (
    list_watchlists,
    create_watchlist,
    add_symbol,
    list_symbols,
)

def render_watchlists(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Watchlists")

    name = st.text_input("New Watchlist Name")

    if st.button("Create Watchlist"):

        create_watchlist(db, tenant_id, name)

        st.success("Created")

        st.rerun()

    watchlists = list_watchlists(db, tenant_id)

    if not watchlists:

        st.info("No watchlists")

        return

    selected = st.selectbox(
        "Select Watchlist",
        watchlists,
        format_func=lambda x: x.name,
    )

    symbol = st.text_input("Add Symbol")

    if st.button("Add Symbol"):

        add_symbol(db, selected.id, symbol)

        st.rerun()

    symbols = list_symbols(db, selected.id)

    st.write("Symbols:")

    for s in symbols:

        st.write(s)