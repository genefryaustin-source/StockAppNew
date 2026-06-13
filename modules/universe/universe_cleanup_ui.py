from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.universe.universe_cleanup_service import UniverseCleanupService
from modules.universe.universe_exchange_sync_service import UniverseExchangeSyncService


def _get_current_user() -> dict:
    try:
        return st.session_state.get("user") or {}
    except Exception:
        return {}


def _get_current_tenant_id() -> str:
    user = _get_current_user()
    return user.get("tenant_id") or "default_tenant"


def _render_symbol_preview(title: str, symbols: list[str], height: int = 220) -> None:
    st.markdown(title)

    if not symbols:
        st.info("None found.")
        return

    st.dataframe(
        pd.DataFrame({"Symbol": symbols}),
        use_container_width=True,
        height=height,
        hide_index=True,
    )


def render_universe_cleanup_ui(db):
    st.subheader("🧹 Universe Cleanup & Governance")

    tenant_id = _get_current_tenant_id()

    service = UniverseCleanupService(db)
    sync_service = UniverseExchangeSyncService(db)

    universes_df = service.get_universes(tenant_id=tenant_id)

    if universes_df.empty:
        st.warning("No universes found for this tenant.")
        return

    universe_map = {
        f"{row['name']}": row["id"]
        for _, row in universes_df.iterrows()
    }

    selected_name = st.selectbox(
        "Select Universe",
        list(universe_map.keys()),
        key="cleanup_universe_select",
    )

    universe_id = universe_map[selected_name]

    st.caption(f"Tenant: `{tenant_id}`")

    st.markdown("### Universe Symbols")

    symbols_df = service.get_universe_symbols(
        universe_id=universe_id,
        tenant_id=tenant_id,
    )

    st.write(f"Total symbols: {len(symbols_df)}")

    st.dataframe(
        symbols_df,
        use_container_width=True,
        height=300,
    )

    st.markdown("### Exchange Membership Sync")

    st.caption(
        "Checks the selected tenant universe against available exchange/reference data "
        "and can add newly listed symbols that are missing from this universe."
    )

    reference_choice = st.selectbox(
        "Reference universe / exchange",
        options=[
            "Auto-detect from selected universe name",
            "AMEX",
            "NASDAQ",
            "NYSE",
            "S&P 500",
        ],
        key="exchange_sync_reference_choice",
    )

    reference_key = None if reference_choice == "Auto-detect from selected universe name" else reference_choice

    col_preview, col_sync = st.columns(2)

    with col_preview:
        preview_clicked = st.button(
            "🔍 Check for New Symbols",
            key="preview_exchange_sync",
            use_container_width=True,
        )

    with col_sync:
        sync_clicked = st.button(
            "➕ Add Missing Symbols",
            key="apply_exchange_sync",
            use_container_width=True,
        )

    remove_stale = st.checkbox(
        "Also remove symbols no longer found in reference source",
        value=False,
        help="Leave off unless you are sure the reference source is complete.",
        key="exchange_sync_remove_stale",
    )

    if preview_clicked or sync_clicked:
        try:
            if preview_clicked:
                result = sync_service.preview_exchange_sync(
                    tenant_id=tenant_id,
                    universe_id=universe_id,
                    reference_key=reference_key,
                )
            else:
                result = sync_service.sync_exchange_membership(
                    tenant_id=tenant_id,
                    universe_id=universe_id,
                    reference_key=reference_key,
                    add_missing=True,
                    remove_stale=remove_stale,
                )

            if not result.get("ok"):
                st.error(result.get("message", "Exchange sync failed."))
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current", result.get("current_count", 0))
                c2.metric("Reference", result.get("reference_count", 0))
                c3.metric("Missing", result.get("missing_count", 0))
                c4.metric("Stale", result.get("stale_count", 0))

                st.caption(f"Reference source: {result.get('source', 'Unknown')}")

                if sync_clicked:
                    st.success(
                        f"Sync complete. Added {result.get('added_count', 0)} symbols. "
                        f"Removed {result.get('removed_count', 0)} symbols."
                    )

                left, right = st.columns(2)
                with left:
                    _render_symbol_preview("#### Missing Symbols", result.get("missing", []))
                with right:
                    _render_symbol_preview("#### Stale Symbols", result.get("stale", []))

                if sync_clicked:
                    st.rerun()

        except Exception as e:
            st.error(f"Exchange sync failed: {e}")

    history_df = sync_service.get_sync_history(
        tenant_id=tenant_id,
        universe_id=universe_id,
        limit=5,
    )

    if not history_df.empty:
        with st.expander("Recent Exchange Sync History", expanded=False):
            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Suspicious Symbols")

    suspicious_df = service.preview_suspicious_symbols(
        universe_id=universe_id,
        tenant_id=tenant_id,
    )

    if suspicious_df.empty:
        st.success("No suspicious symbols found.")
    else:
        st.warning(f"Found {len(suspicious_df)} suspicious symbols")
        st.dataframe(
            suspicious_df,
            use_container_width=True,
            height=250,
        )

    st.markdown("### Manual Symbol Removal")

    symbol_to_delete = st.text_input("Symbol to delete").upper().strip()

    purge_snapshots = st.checkbox("Purge analytics snapshots", value=True)
    blacklist = st.checkbox("Blacklist symbol", value=True)

    if st.button("🗑 Delete Symbol"):
        if not symbol_to_delete:
            st.error("Enter a symbol")
        else:
            result = service.delete_symbol(
                universe_id=universe_id,
                tenant_id=tenant_id,
                symbol=symbol_to_delete,
                purge_snapshots=purge_snapshots,
                blacklist=blacklist,
            )

            st.success(f"Deleted {result['symbol']}")
            st.info(f"Purged snapshots: {result['deleted_snapshots']}")
            st.rerun()

    st.markdown("### Auto Cleanup")

    if st.button("🧹 Auto Remove Suspicious Symbols"):
        result = service.auto_cleanup_universe(
            universe_id=universe_id,
            tenant_id=tenant_id,
            purge_snapshots=True,
            blacklist=True,
        )

        st.success(f"Removed {result['removed']} symbols")

        if result["symbols"]:
            st.dataframe(pd.DataFrame({"Removed": result["symbols"]}))

        return

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
