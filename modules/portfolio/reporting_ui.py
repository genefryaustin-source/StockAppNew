import streamlit as st
import pandas as pd
import json

from modules.portfolio.reporting_service import ReportingService
from modules.portfolio.nav_service import NavService
from modules.portfolio.accounting_service import AccountingService
from modules.portfolio.pdf_reporting_service import PDFReportingService

def render_reporting_ui(
    portfolio_id,
    totals,
    health,
    df_pos,
    sleeve_df,
    trades_df,
    risk_df,
):

    st.header("Investor Reporting Engine")

    service = ReportingService()


    nav_service = NavService(db_session, market_data_service)
    accounting_service = AccountingService(db_session)
    reporting_service = ReportingService()
    nav_service = NavService(db_session, market_data_service)
    accounting_service = AccountingService(db_session)

    pdf_service = PDFReportingService(
        db_session,
        nav_service,
        accounting_service,
        reporting_service
    )

    summary = service.build_portfolio_summary(totals, health)
    positions = service.build_positions_report(df_pos)
    strategies = service.build_strategy_report(sleeve_df)
    trades = service.build_trade_blotter(trades_df)
    risk = service.build_risk_report(risk_df)

    # ---------------------------------
    # SUMMARY
    # ---------------------------------
    st.subheader("Portfolio Summary")
    st.json(summary)

    # ---------------------------------
    # POSITIONS
    # ---------------------------------
    st.subheader("Positions")
    if not positions.empty:
        st.dataframe(positions, use_container_width=True)
    else:
        st.caption("No positions")

    # ---------------------------------
    # STRATEGY ATTRIBUTION
    # ---------------------------------
    st.subheader("Strategy Attribution")
    if not strategies.empty:
        st.dataframe(strategies, use_container_width=True)
    else:
        st.caption("No strategy data")

    # ---------------------------------
    # TRADES
    # ---------------------------------
    st.subheader("Trade Blotter")
    if not trades.empty:
        st.dataframe(trades, use_container_width=True)
    else:
        st.caption("No trades")

    # ---------------------------------
    # RISK
    # ---------------------------------
    st.subheader("Risk Report")
    if risk is not None and not risk.empty:
        st.dataframe(risk, use_container_width=True)
    else:
        st.caption("No risk data")

    # ---------------------------------
    # EXPORT
    # ---------------------------------
    st.subheader("Export")

    bundle = service.export_bundle(summary, positions, strategies, trades, risk)

    col1, col2, col3 = st.columns(3)

    # -------------------------
    # JSON EXPORT
    # -------------------------
    with col1:
        st.download_button(
            "Download JSON Report",
            data=json.dumps(bundle, indent=2),
            file_name=f"portfolio_report_{portfolio_id}.json",
            mime="application/json",
        )

    # -------------------------
    # CSV EXPORT
    # -------------------------
    with col2:
        if not positions.empty:
            st.download_button(
                "Download Positions CSV",
                data=positions.to_csv(index=False),
                file_name=f"positions_{portfolio_id}.csv",
                mime="text/csv",
            )

    # -------------------------
    # PDF EXPORT (NEW - PHASE 24)
    # -------------------------
    with col3:
        try:
            pdf_bytes = pdf_service.build_pdf(
                portfolio_id=portfolio_id,
                summary=summary,
                positions_df=positions,
                strategies_df=strategies,
                trades_df=trades,
                risk_df=risk,
                title="Investor Portfolio Tear Sheet",
            )

            st.download_button(
                "Download PDF Tear Sheet",
                data=pdf_bytes,
                file_name=f"portfolio_tearsheet_{portfolio_id}.pdf",
                mime="application/pdf",
            )

        except Exception as e:
            st.error(f"PDF generation failed: {e}")