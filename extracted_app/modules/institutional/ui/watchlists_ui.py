import streamlit as st

from modules.institutional.watchlists import (
    create_watchlist,
    list_watchlists,
    add_symbol,
    remove_symbol,
    list_symbols,
    delete_watchlist,
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

    col_select, col_delete = st.columns([4, 1])

    with col_select:
        selected_name = st.selectbox(
            "Select Watchlist",
            list(watchlist_map.keys())
        )

    watchlist_id = watchlist_map[selected_name]   # ✅ FIX

    with col_delete:
        st.write("")  # align with the selectbox
        if st.button("🗑️ Delete", key="delete_current_watchlist", use_container_width=True):
            st.session_state["confirm_delete_watchlist"] = watchlist_id

    if st.session_state.get("confirm_delete_watchlist") == watchlist_id:
        st.warning(f"Delete watchlist **{selected_name}** and all its symbols? This can't be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, delete it", key="confirm_delete_yes", use_container_width=True):
                delete_watchlist(db, tenant_id, watchlist_id)
                st.session_state["confirm_delete_watchlist"] = None
                st.success(f"Deleted '{selected_name}'.")
                st.rerun()
        with c2:
            if st.button("Cancel", key="confirm_delete_cancel", use_container_width=True):
                st.session_state["confirm_delete_watchlist"] = None
                st.rerun()

    # ---------------------------------------------------
    # BULK CLEANUP (delete several at once)
    # ---------------------------------------------------

    with st.expander("Manage / clean up watchlists", expanded=False):
        st.caption("Select one or more watchlists to delete in bulk.")

        to_delete = st.multiselect(
            "Watchlists to delete",
            list(watchlist_map.keys()),
            key="bulk_delete_select",
        )

        if to_delete and st.button(
            f"🗑️ Delete {len(to_delete)} selected", key="bulk_delete_confirm"
        ):
            for name in to_delete:
                delete_watchlist(db, tenant_id, watchlist_map[name])
            st.success(f"Deleted {len(to_delete)} watchlist(s).")
            st.rerun()

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