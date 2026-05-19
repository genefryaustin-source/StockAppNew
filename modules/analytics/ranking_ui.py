import streamlit as st
from modules.analytics.alpha_engine import compute_alpha_rank
from modules.analytics.rankings import build_percentile_rankings
from modules.analytics.snapshot_cache import get_latest_snapshots_df


# -------------------------------------
# Helper
# -------------------------------------

def build_weight_dict(df):

    if df is None or df.empty:
        return {}

    df = df.dropna(subset=["Ticker", "weight"])

    weights = dict(zip(df["Ticker"], df["weight"]))

    return weights








# ----------------------------------------
# Render AI Rankings
# ----------------------------------------
def render_ai_rankings(db, user, price_data):

    st.subheader("AI Stock Rankings")

    if not price_data:
        st.warning("No cached price data available.")
        return

    # -----------------------------------
    # LOAD SNAPSHOTS → SECTOR MAP
    # -----------------------------------
    tenant_id = user.get("tenant_id")

    snapshot_df = get_latest_snapshots_df(db, tenant_id)

    sector_map = {}

    if snapshot_df is not None and not snapshot_df.empty:

        snapshot_df["symbol"] = snapshot_df["symbol"].astype(str).str.upper()

        if "sector" in snapshot_df.columns:
            sector_map = dict(zip(snapshot_df["symbol"], snapshot_df["sector"]))
        else:
            st.warning("No sector column found in snapshots")

    # DEBUG
    st.write("SECTOR MAP SIZE:", len(sector_map))

    # -----------------------------------
    # COMPUTE ALPHA (NOW SECTOR-NEUTRAL)
    # -----------------------------------
    rankings = compute_alpha_rank(price_data, sector_map=sector_map)

    if rankings is None or rankings.empty:
        st.warning("No AI rankings available.")
        return

    # IMPORTANT: store for portfolio + downstream modules
    st.session_state.rank_rows = rankings

    # -----------------------------------
    # DISPLAY
    # -----------------------------------
    st.dataframe(rankings, use_container_width=True)

    st.markdown("### Top Alpha Picks")
    st.dataframe(rankings.head(10), use_container_width=True)

    # -----------------------------------
    # COMPUTE ALPHA WITH SECTOR NEUTRAL
    # -----------------------------------
    rankings = compute_alpha_rank(price_data, sector_map=sector_map)
    
    # -----------------------------------
    # STORE
    # -----------------------------------
    st.session_state.rank_rows = rankings
    
    # -----------------------------------
    # Build Weights
    # -----------------------------------

    weights = build_weight_dict(rankings)

    st.write("WEIGHT SAMPLE:", list(weights.items())[:10])



    # -----------------------------------
    # DISPLAY TABLE
    # -----------------------------------
    st.dataframe(rankings, use_container_width=True)

    # -----------------------------------
    # TOP PICKS
    # -----------------------------------
    st.markdown("### Top Alpha Picks")
    st.dataframe(rankings.head(10), use_container_width=True)