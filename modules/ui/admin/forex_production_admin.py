"""
ui/admin/forex_production_admin.py

Admin entrypoints for final Forex production validation.
"""

from __future__ import annotations

import streamlit as st

try:
    import pandas as pd
except Exception:
    pd = None


def render_forex_production_admin(db=None):
    st.title("Forex Production Admin")
    st.caption("Final validation, broker health, production health, and safety tests.")

    tabs = st.tabs(["Validation Center", "Production Health", "Broker Health", "Broker Safety"])

    with tabs[0]:
        from ui.admin.forex_terminal_validation_center import render_forex_terminal_validation_center
        render_forex_terminal_validation_center(db=db)

    with tabs[1]:
        try:
            from modules.forex.forex_phase12_production_services import get_forex_phase12_production_services
            prod = get_forex_phase12_production_services(db=db)
            st.json(prod.operations_health())
        except Exception as exc:
            st.error(f"Production health failed: {exc}")

    with tabs[2]:
        try:
            from modules.forex.forex_phase12_production_services import get_forex_phase12_production_services
            prod = get_forex_phase12_production_services(db=db)
            health = prod.broker_health()
            rows = health.get("brokers", [])
            if pd is not None:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.json(rows)
        except Exception as exc:
            st.error(f"Broker health failed: {exc}")

    with tabs[3]:
        st.warning("This test should reject live broker routes and only confirm safety lockout.")
        if st.button("Run Broker Safety Test", type="primary"):
            try:
                from modules.forex.forex_broker_router import get_forex_broker_router
                router = get_forex_broker_router(db=db, default_broker="paper")
                rows = []
                for broker in ["oanda", "mt5", "ibkr", "dxtrade"]:
                    result = router.route_order(
                        broker=broker,
                        pair="EUR/USD",
                        side="BUY",
                        lots=0.01,
                        order_type="MARKET",
                    )
                    rows.append({
                        "Broker": broker,
                        "Expected": "REJECTED",
                        "Actual": result.get("status"),
                        "Passed": str(result.get("status", "")).upper() == "REJECTED",
                        "Message": result.get("message"),
                    })
                if pd is not None:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.json(rows)
            except Exception as exc:
                st.error(f"Broker safety test failed: {exc}")


def render(db=None):
    return render_forex_production_admin(db=db)
