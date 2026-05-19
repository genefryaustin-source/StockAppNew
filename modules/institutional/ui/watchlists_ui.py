import streamlit as st

from modules.institutional.watchlists import (
    create_watchlist,
    list_watchlists,
    add_symbol,
    remove_symbol,
    list_symbols,
)


def render_watchlists(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Watchlists")

    # ---------------------------------------------------
    # CREATE WATCHLIST
    # ---------------------------------------------------

    with st.expander("Create Watchlist", expanded=False):

        name = st.text_input("Watchlist Name")

        if st.button("Create Watchlist"):

            if not name.strip():
                st.warning("Enter a watchlist name")
            else:
                create_watchlist(db, tenant_id, name)
                st.success("Watchlist created")
                st.rerun()

    # ---------------------------------------------------
    # LIST WATCHLISTS
    # ---------------------------------------------------

    watchlists = list_watchlists(db, tenant_id)

    if not watchlists:
        st.info("No watchlists created yet.")
        return

    watchlist_map = {w.name: w.id for w in watchlists}

    selected_name = st.selectbox(
        "Select Watchlist",
        list(watchlist_map.keys())
    )

    watchlist_id = watchlist_map[selected_name]   # ✅ FIX

    # ---------------------------------------------------
    # ADD SYMBOL
    # ---------------------------------------------------

    col1, col2 = st.columns([3,1])

    with col1:
        new_symbol = st.text_input("Add Symbol")

    with col2:
        if st.button("Add"):

            if new_symbol.strip():
                add_symbol(
                    db,
                    tenant_id,
                    watchlist_id,
                    new_symbol.strip()
                )
                st.rerun()

    # ---------------------------------------------------
    # SHOW SYMBOLS
    # ---------------------------------------------------

    symbols = list_symbols(db, watchlist_id)

    if not symbols:
        st.info("No symbols in this watchlist.")
        return

    st.markdown("### Symbols")

    for sym in symbols:

        col1, col2 = st.columns([4,1])

        with col1:
            st.write(sym)

        with col2:
            if st.button("Remove", key=f"rm_{sym}"):

                remove_symbol(
                    db,
                    watchlist_id,
                    sym
                )

                st.rerun()