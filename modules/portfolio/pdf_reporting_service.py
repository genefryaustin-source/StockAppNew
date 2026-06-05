from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus.tables import TableStyle  # Add this

from datetime import datetime, UTC
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tempfile
import os
from sqlalchemy import text

from modules.utils.data_utils import normalize_timeseries_df


class PDFReportingService:

    def __init__(self, db_session, nav_service, accounting_service, reporting_service):
        self.db = db_session
        self.nav_service = nav_service
        self.accounting = accounting_service
        self.reporting = reporting_service
        self.styles = getSampleStyleSheet()

    # =========================================================
    # CHART HELPERS
    # =========================================================

    def _save_chart(self, fig):
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        fig.savefig(path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        return path

    # ... keep your chart methods (_nav_chart, _benchmark_chart, etc.) as they are ...

    # =========================================================
    # MAIN REPORT
    # =========================================================

    def generate_portfolio_report(self, portfolio_id, output_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        temp_files = []

        # Cover Page
        elements.append(Paragraph("Portfolio Report", self.styles["Title"]))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
            self.styles["Normal"]
        ))
        elements.append(PageBreak())

        # NAV Data
        nav_df = normalize_timeseries_df(
            self.nav_service.get_nav_history(portfolio_id)
        )

        if nav_df.empty or "NAV" not in nav_df.columns:
            elements.append(Paragraph("No performance data available.", self.styles["Normal"]))
            total_return = ann_return = 0
        else:
            # NAV Chart (only once)
            nav_chart = self._nav_chart(nav_df)
            if nav_chart:
                temp_files.append(nav_chart)
                elements.append(Image(nav_chart, width=450, height=220))

            start = nav_df["NAV"].iloc[0]
            end = nav_df["NAV"].iloc[-1]
            total_return = (end / start - 1) if start else 0

            days = (nav_df["Date"].iloc[-1] - nav_df["Date"].iloc[0]).days
            ann_return = (1 + total_return) ** (365 / max(days, 1)) - 1 if days > 0 else 0

        # Positions


        rows = self.db.execute(
            text("""
                SELECT
                    symbol,
                    qty,
                    market_value,
                    unrealized_pnl
                FROM portfolio_positions
                WHERE portfolio_id = :pid
            """),
            {"pid": portfolio_id}
        ).fetchall()

        df_pos = pd.DataFrame(
            rows,
            columns=[
                "symbol",
                "qty",
                "market_value",
                "unrealized_pnl"
            ]
        )

        # Executive Summary
        elements.append(Paragraph("Executive Summary", self.styles["Heading2"]))
        summary_data = [
            ["Metric", "Value"],
            ["Total Return", f"{total_return*100:.2f}%"],
            ["Annualized Return", f"{ann_return*100:.2f}%"],
            ["Equity", f"${df_pos['market_value'].sum():,.2f}" if not df_pos.empty else "$0.00"],
            ["Unrealized PnL", f"${df_pos['unrealized_pnl'].sum():,.2f}" if not df_pos.empty else "$0.00"],
        ]
        elements.append(Table(summary_data, style=TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ])))
        elements.append(Spacer(1, 20))
        elements.append(PageBreak())

        # === Add more sections with proper TableStyle similarly ===

        # Final Build
        doc.build(elements)

        # Cleanup
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass

        return output_path