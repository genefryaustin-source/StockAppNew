from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.universe.universe_cleanup_service import (
    UniverseCleanupService,
)


# -------------------------------------------------
# UI
# -------------------------------------------------

def render_universe_cleanup_ui(db):

    st.subheader("🧹 Universe Cleanup & Governance")

    service = UniverseCleanupService(db)

    universes_df = service.get_universes()

    if universes_df.empty:
        st.warning("No universes found.")
        return

    universe_map = {
        row["name"]: row["id"]
        for _, row in universes_df.iterrows()
    }

    selected_name = st.selectbox(
        "Select Universe",
        list(universe_map.keys())
    )

    universe_id = universe_map[selected_name]

    # -------------------------------------------------
    # SYMBOLS
    # -------------------------------------------------
    st.markdown("### Universe Symbols")

    symbols_df = service.get_universe_symbols(universe_id)

    st.write(f"Total symbols: {len(symbols_df)}")

    st.dataframe(
        symbols_df,
        use_container_width=True,
        height=300,
    )

    # -------------------------------------------------
    # PREVIEW SUSPICIOUS
    # -------------------------------------------------
    st.markdown("### Suspicious Symbols")

    suspicious_df = service.preview_suspicious_symbols(universe_id)

    if suspicious_df.empty:
        st.success("No suspicious symbols found.")
    else:

        st.warning(
            f"Found {len(suspicious_df)} suspicious symbols"
        )

        st.dataframe(
            suspicious_df,
            use_container_width=True,
            height=250,
        )

    # -------------------------------------------------
    # MANUAL DELETE
    # -------------------------------------------------
    st.markdown("### Manual Symbol Removal")

    symbol_to_delete = st.text_input(
        "Symbol to delete"
    ).upper().strip()

    purge_snapshots = st.checkbox(
        "Purge analytics snapshots",
        value=True,
    )

    blacklist = st.checkbox(
        "Blacklist symbol",
        value=True,
    )

    if st.button("🗑 Delete Symbol"):

        if not symbol_to_delete:
            st.error("Enter a symbol")

        else:

            result = service.delete_symbol(
                universe_id=universe_id,
                symbol=symbol_to_delete,
                purge_snapshots=purge_snapshots,
                blacklist=blacklist,
            )

            st.success(
                f"Deleted {result['symbol']}"
            )

            st.info(
                f"Purged snapshots: {result['deleted_snapshots']}"
            )

            st.rerun()

    # -------------------------------------------------
    # AUTO CLEANUP
    # -------------------------------------------------
    st.markdown("### Auto Cleanup")

    if st.button("🧹 Auto Remove Suspicious Symbols"):

        result = service.auto_cleanup_universe(
            universe_id=universe_id,
            purge_snapshots=True,
            blacklist=True,
        )

        st.success(
            f"Removed {result['removed']} symbols"
        )

        if result["symbols"]:

            st.dataframe(pd.DataFrame({
                "Removed": result["symbols"]
            }))

        st.rerun()

    # -------------------------------------------------
    # BLACKLIST
    # -------------------------------------------------
    st.markdown("### Symbol Blacklist")

    blacklist_df = service.get_blacklist()

    if blacklist_df.empty:
        st.info("Blacklist empty")
    else:

        st.dataframe(
            blacklist_df,
            use_container_width=True,
            height=250,
        )