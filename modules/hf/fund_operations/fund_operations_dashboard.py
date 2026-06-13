from __future__ import annotations
from typing import Any
import pandas as pd
import streamlit as st

from modules.hf.fund_operations.nav_engine import calculate_nav, sample_positions
from modules.hf.fund_operations.nav_history_engine import build_nav_history
from modules.hf.fund_operations.fund_performance_engine import calculate_fund_performance
from modules.hf.fund_operations.performance_attribution_engine import attribute_performance
from modules.hf.fund_operations.risk_reporting_engine import build_risk_report
from modules.hf.fund_operations.exposure_monitor_engine import monitor_exposure
from modules.hf.fund_operations.investor_reporting_engine import build_investor_report
from modules.hf.fund_operations.lp_reporting_engine import build_lp_statement
from modules.hf.fund_operations.compliance_reporting_engine import build_compliance_report
from modules.hf.fund_operations.audit_trail_engine import audit_event
from modules.hf.fund_operations.fund_health_engine import score_fund_health
from modules.hf.fund_operations.capital_flow_engine import summarize_capital_flows
from modules.hf.fund_operations.benchmark_comparison_engine import compare_to_benchmark
from modules.hf.fund_operations.fund_operations_ai import explain_fund_operations


def build_fund_operations_packet(db: Any = None, user: dict | None = None) -> dict[str, Any]:
    positions = sample_positions()
    cash = 250_000.0
    liabilities = 25_000.0
    shares = 1_000_000.0
    nav = calculate_nav(positions, cash=cash, liabilities=liabilities, shares_outstanding=shares)
    nav_history = build_nav_history(nav['net_assets'], days=60)
    performance = calculate_fund_performance(nav_history)
    attribution = attribute_performance(positions)
    risk = build_risk_report(positions, nav['net_assets'])
    exposure = monitor_exposure(positions, nav['net_assets'])
    compliance = build_compliance_report(risk, exposure)
    health = score_fund_health(performance, risk, compliance)
    flows = summarize_capital_flows(subscriptions=100_000, redemptions=25_000)
    benchmark = compare_to_benchmark(performance, benchmark_return=0.07)
    audit = [audit_event('HF5_PACKET_BUILT', actor=(user or {}).get('email', 'system'), details={'nav': nav.get('net_assets')})]
    return {
        'positions': positions,
        'nav': nav,
        'nav_history': nav_history,
        'performance': performance,
        'attribution': attribution,
        'risk': risk,
        'exposure': exposure,
        'compliance': compliance,
        'health': health,
        'capital_flows': flows,
        'benchmark': benchmark,
        'audit': audit,
    }


def render_fund_operations_dashboard(db: Any = None, user: dict | None = None) -> None:
    st.header('🏦 Fund Operations')
    st.caption('HF-5 · NAV, performance, risk, investor reporting, compliance, and fund health.')

    refresh = st.button('Refresh Fund Operations Packet', key='hf5_refresh_packet', use_container_width=True)
    if refresh or 'hf5_packet' not in st.session_state:
        st.session_state['hf5_packet'] = build_fund_operations_packet(db=db, user=user)

    packet = st.session_state['hf5_packet']
    nav = packet['nav']; performance = packet['performance']; risk = packet['risk']; health = packet['health']; compliance = packet['compliance']

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric('Net Assets', f"${nav.get('net_assets', 0):,.0f}")
    c2.metric('NAV / Share', f"{nav.get('nav_per_share', 0):,.4f}")
    c3.metric('YTD Return', f"{performance.get('ytd_return', 0):.2%}")
    c4.metric('Sharpe', performance.get('sharpe', 0))
    c5.metric('Fund Health', f"{health.get('fund_health_score')}/100", health.get('status'))

    tabs = st.tabs(['📊 Fund Dashboard','💰 NAV','📈 Attribution','⚠ Risk','🏦 Investors','📄 LP Reports','📉 Exposure','🛡 Compliance','📋 Audit','🤖 Copilot'])

    with tabs[0]:
        st.subheader('Fund Dashboard')
        a, b, c, d = st.columns(4)
        a.metric('MTD', f"{performance.get('mtd_return', 0):.2%}")
        b.metric('QTD', f"{performance.get('qtd_return', 0):.2%}")
        c.metric('Alpha', f"{packet['benchmark'].get('alpha', 0):.2%}")
        d.metric('Compliance', compliance.get('status'))
        st.dataframe(pd.DataFrame(packet['positions']), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader('NAV Management')
        st.json(nav)
        st.line_chart(pd.DataFrame(packet['nav_history']).set_index('date')['nav'])

    with tabs[2]:
        st.subheader('Performance Attribution')
        st.metric('Total P&L', f"${packet['attribution'].get('total_pnl', 0):,.0f}")
        st.dataframe(pd.DataFrame(packet['attribution']['position_attribution']), use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame(packet['attribution']['sector_attribution']), use_container_width=True, hide_index=True)

    with tabs[3]:
        st.subheader('Risk Reporting')
        st.json(risk)

    with tabs[4]:
        st.subheader('Investor Reporting')
        report = build_investor_report('Conduro Equity Fund', nav, performance, risk)
        st.markdown(report)
        st.download_button('Download Investor Report', report, file_name='investor_report.md', mime='text/markdown', key='hf5_investor_report_download')

    with tabs[5]:
        st.subheader('LP Reporting')
        lp = build_lp_statement('Sample LP', 500_000, performance.get('ytd_return', 0), fees=2_500)
        st.json(lp)

    with tabs[6]:
        st.subheader('Exposure Monitor')
        st.metric('Gross Exposure', f"{packet['exposure'].get('gross_exposure', 0):.1%}")
        st.dataframe(pd.DataFrame(packet['exposure']['positions']), use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame(packet['exposure']['sector_exposure']), use_container_width=True, hide_index=True)

    with tabs[7]:
        st.subheader('Compliance Reporting')
        if compliance.get('status') == 'Compliant': st.success('Fund is compliant with configured exposure limits.')
        else: st.warning('Compliance exceptions require review.')
        st.json(compliance)

    with tabs[8]:
        st.subheader('Audit Trail')
        st.dataframe(pd.DataFrame(packet['audit']), use_container_width=True, hide_index=True)

    with tabs[9]:
        st.subheader('Fund Operations Copilot')
        st.markdown(explain_fund_operations(packet))
