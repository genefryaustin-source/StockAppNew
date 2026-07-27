from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import render_section_header,panel
from modules.forex.ui.forex_ui_cards import render_metric_ribbon
import streamlit as st

def render_forex_risk_budget_workspace(payload=None,db=None):
    inject_forex_ui_theme(st)
    render_section_header("Risk Budget Workstation",kicker="Institutional Risk")
    render_metric_ribbon([
        {"label":"Portfolio VaR","value":"2.3%","progress":72,"status":"READY","icon":"🛡️"},
        {"label":"Risk Budget","value":"100%","progress":100,"status":"READY","icon":"⚖️"},
        {"label":"Capital Used","value":"69%","progress":69,"status":"ACTIVE","icon":"💼"},
        {"label":"Stress","value":"PASS","progress":92,"status":"READY","icon":"📉"},
        {"label":"Drawdown","value":"3.1%","progress":82,"status":"READY","icon":"📊"},
        {"label":"Leverage","value":"1.0x","progress":40,"status":"READY","icon":"🏦"},
        {"label":"Exposure","value":"Balanced","progress":88,"status":"READY","icon":"🌐"},
        {"label":"Status","value":"READY","progress":100,"status":"READY","icon":"🟢"},
    ])
    with panel("Risk Budget Allocation"):
        st.dataframe([
            {"Pair":"EUR/USD","Risk %":18,"VaR":"0.42%","Status":"READY"},
            {"Pair":"USD/CHF","Risk %":16,"VaR":"0.38%","Status":"READY"},
            {"Pair":"AUD/USD","Risk %":12,"VaR":"0.31%","Status":"READY"},
            {"Pair":"GBP/USD","Risk %":9,"VaR":"0.27%","Status":"WATCH"},
        ],use_container_width=True,hide_index=True)
    c1,c2=st.columns(2)
    with c1:
        with panel("Risk Controls"):
            st.success("Position sizing within limits")
            st.info("No concentration breaches detected")
            st.info("Paper trading mode")
    with c2:
        with panel("Stress Testing"):
            st.metric("99% VaR","2.3%")
            st.metric("Expected Shortfall","3.0%")
            st.metric("Max Drawdown","5.8%")
    with panel("Execution Guardrails"):
        st.dataframe([
            {"Control":"Max Position","Limit":"25%","Current":"24%","Status":"PASS"},
            {"Control":"Sector Exposure","Limit":"35%","Current":"31%","Status":"PASS"},
            {"Control":"Currency Concentration","Limit":"40%","Current":"33%","Status":"PASS"},
            {"Control":"Liquidity","Limit":"Institutional","Current":"PASS","Status":"PASS"},
        ],use_container_width=True,hide_index=True)
    return {"status":"READY"}