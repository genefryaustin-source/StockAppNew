# alerts_ui.py in Institutional/ui
import streamlit as st
import pandas as pd

from modules.alerts.service import run_alert_checks, list_alerts, acknowledge_alert


def render_alerts(db, user: dict):
    tenant_id = user["tenant_id"]

    st.subheader("Alerts & Breakout Detection")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.text_input("Symbol (optional)", value="").strip().upper()
    with col2:
        only_unack = st.checkbox("Unacknowledged only", value=True)
    with col3:
        include_touch = st.checkbox("Include level-touch alerts", value=False)

    run_col1, run_col2 = st.columns([1, 3])
    with run_col1:
        if st.button("Run Checks", type="primary"):
            if not symbol:
                st.warning("Enter a symbol to run checks (Phase 2.2 adds watchlist-wide checks).")
            else:
                created = run_alert_checks(db, tenant_id, symbol, include_level_touch=include_touch)
                st.success(f"Created {created} new alert(s).")

    alerts = list_alerts(db, tenant_id, symbol=symbol or None, only_unack=only_unack, limit=200)

    if not alerts:
        st.info("No alerts found.")
        return

    # Table view
    df = pd.DataFrame([{
        "time": a.created_at,
        "symbol": a.symbol,
        "type": a.alert_type,
        "title": a.title,
        "last_price": a.last_price,
        "support": a.support,
        "resistance": a.resistance,
        "prev_rating": a.previous_rating,
        "new_rating": a.new_rating,
        "ack": a.acknowledged,
        "id": a.id,
    } for a in alerts])

    st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)

    st.markdown("### Acknowledge an Alert")
    alert_ids = [a.id for a in alerts if not a.acknowledged]
    if not alert_ids:
        st.caption("No unacknowledged alerts to acknowledge.")
        return

    pick = st.selectbox("Select alert", alert_ids)
    if st.button("Acknowledge Selected"):
        ok = acknowledge_alert(db, tenant_id, pick)
        if ok:
            st.success("Acknowledged.")
            st.rerun()
        else:
            st.error("Could not acknowledge.")