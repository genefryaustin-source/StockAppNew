import streamlit as st

from modules.institutional.earnings import (
    ingest_massive_earnings,
    list_upcoming,
)


def _safe_eps(e):
    """
    Safely resolve EPS value from any possible column.
    """
    return (
        getattr(e, "eps_actual", None)
        or getattr(e, "eps_est", None)
        or getattr(e, "eps_estimate", None)
    )


def _safe_revenue(e):
    """
    Safely resolve revenue value from any possible column.
    """
    return (
        getattr(e, "rev_actual", None)
        or getattr(e, "revenue_actual", None)
        or getattr(e, "rev_est", None)
        or getattr(e, "revenue_estimate", None)
    )


def render_earnings(db, user):

    tenant_id = user["tenant_id"]

    st.subheader("Massive Earnings")

    symbol = st.text_input("Ticker", "AAPL").upper()

    if st.button("Fetch Earnings", type="primary"):

        try:
            inserted = ingest_massive_earnings(
                db,
                tenant_id,
                symbol,
            )

            if inserted == 0:
                st.warning("No earnings inserted (may already exist).")
            else:
                st.success(f"{inserted} earnings records inserted.")

        except Exception as e:
            st.error(f"Earnings ingestion failed: {e}")
            return

    events = list_upcoming(db, tenant_id)

    if not events:
        st.info("No earnings data ingested yet.")
        return

    st.markdown("### Stored Earnings")

    for e in events:

        eps = _safe_eps(e)
        revenue = _safe_revenue(e)

        eps_display = f"{eps:.2f}" if isinstance(eps, (int, float)) else "N/A"

        if isinstance(revenue, (int, float)):
            revenue_display = f"{revenue:,.0f}"
        else:
            revenue_display = "N/A"

        st.write(
            f"{e.symbol} | {e.event_date} | "
            f"EPS: {eps_display} | "
            f"Revenue: {revenue_display}"
        )