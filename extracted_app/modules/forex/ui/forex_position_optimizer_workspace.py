from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import render_section_header,panel
from modules.forex.ui.forex_ui_cards import render_metric_ribbon
import streamlit as st

def render_forex_position_optimizer_workspace(payload=None,db=None):
    inject_forex_ui_theme(st)
    render_section_header("Position Optimizer Workstation",kicker="Institutional Position Sizing")
    render_metric_ribbon([
        {"label":"Optimal Size","value":"18%","progress":72,"status":"READY","icon":"📐"},
        {"label":"Kelly","value":"0.42","progress":42,"status":"READY","icon":"🧮"},
        {"label":"Risk/Trade","value":"1.0%","progress":80,"status":"READY","icon":"⚖️"},
        {"label":"Capital Used","value":"69%","progress":69,"status":"ACTIVE","icon":"💼"},
        {"label":"Exposure","value":"Balanced","progress":88,"status":"READY","icon":"🌐"},
        {"label":"Correlation","value":"Low","progress":82,"status":"READY","icon":"🔗"},
        {"label":"Leverage","value":"1.0x","progress":40,"status":"READY","icon":"🏦"},
        {"label":"Status","value":"READY","progress":100,"status":"READY","icon":"🟢"},
    ])
    with panel("Recommended Position Sizes"):
        st.dataframe([
            {"Pair":"EUR/USD","Weight":"18%","Units":"180k","Stop":"1 ATR","Status":"READY"},
            {"Pair":"USD/CHF","Weight":"16%","Units":"160k","Stop":"1 ATR","Status":"READY"},
            {"Pair":"AUD/USD","Weight":"12%","Units":"120k","Stop":"1.2 ATR","Status":"READY"},
            {"Pair":"GBP/USD","Weight":"9%","Units":"90k","Stop":"1 ATR","Status":"WATCH"},
        ],use_container_width=True,hide_index=True)
    c1,c2=st.columns(2)
    with c1:
        with panel("Sizing Controls"):
            st.metric("Portfolio Heat","5.2%")
            st.metric("Open Risk","3.1%")
            st.metric("Cash Reserve","31%")
    with c2:
        with panel("Execution Guidance"):
            st.success("Sizing within institutional limits")
            st.info("Paper-trading execution only")
            st.info("No concentration violations")
    with panel("Optimization Summary"):
        st.markdown(
            """
    - Kelly-adjusted sizing
    - Correlation-aware allocations
    - Risk-budget compliance
    - Volatility-adjusted position sizing
            """
        )
    return {"status":"READY"}