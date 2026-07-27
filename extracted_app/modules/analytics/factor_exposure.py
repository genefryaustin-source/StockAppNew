import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


def compute_factor_exposure(df):

    factors = [
        "Momentum",
        "Value",
        "Growth",
        "Quality",
    ]

    results = {}

    for f in factors:

        if f not in df.columns:
            continue

        vals = df[f].dropna()

        if vals.empty:
            continue

        results[f] = vals.mean()

    return results


def render_factor_exposure(rows):

    st.subheader("Factor Exposure Engine")

    if rows is None or (isinstance(rows, pd.DataFrame) and rows.empty):

        st.warning("No factor data available.")
        return

    exposures = compute_factor_exposure(rows)

    if not exposures:

        st.warning("Factor exposures unavailable.")
        return

    df = pd.DataFrame(
        [{"Factor": k, "Exposure": v} for k, v in exposures.items()]
    )

    fig, ax = plt.subplots()

    ax.bar(df["Factor"], df["Exposure"])

    ax.set_title("Factor Exposure Profile")

    st.pyplot(fig)

    st.markdown("### Factor Scores")

    st.dataframe(df, use_container_width=True, hide_index=True)

def compute_factor_timeseries(db_session, portfolio_id: str):
    import pandas as pd
    from sqlalchemy import text

    # ---------------------------------
    # LOAD SNAPSHOT FACTOR DATA
    # ---------------------------------
    rows = db_session.execute(text("""
        SELECT
            asof as Date,
            momentum,
            value,
            growth,
            quality
        FROM analytics_snapshots
        WHERE portfolio_id = :pid
        ORDER BY asof
    """), {"pid": portfolio_id}).fetchall()

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=[
        "Date", "Momentum", "Value", "Growth", "Quality"
    ])

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    # ---------------------------------
    # CLEAN
    # ---------------------------------
    df = df.dropna()

    return df