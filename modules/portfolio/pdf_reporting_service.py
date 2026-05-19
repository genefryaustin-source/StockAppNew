from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tempfile
import os

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
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    def _nav_chart(self, nav_df):
        if nav_df.empty or "NAV" not in nav_df.columns:
            return None

        fig, ax = plt.subplots()
        ax.plot(nav_df["Date"], nav_df["NAV"])
        ax.set_title("Portfolio NAV")
        return self._save_chart(fig)

    def _benchmark_chart(self, comp_df):
        if comp_df.empty:
            return None

        fig, ax = plt.subplots()

        if "cum_p" in comp_df.columns:
            ax.plot(comp_df["Date"], comp_df["cum_p"], label="Portfolio")
        if "cum_b" in comp_df.columns:
            ax.plot(comp_df["Date"], comp_df["cum_b"], label="Benchmark")

        ax.legend()
        ax.set_title("Portfolio vs Benchmark")
        return self._save_chart(fig)

    def _drawdown_chart(self, nav_df):
        if nav_df.empty or "NAV" not in nav_df.columns:
            return None

        df = nav_df.copy()
        df["cum_max"] = df["NAV"].cummax()
        dd = (df["NAV"] - df["cum_max"]) / df["cum_max"]

        fig, ax = plt.subplots()
        ax.plot(df["Date"], dd)
        ax.set_title("Drawdown")
        return self._save_chart(fig)

    def _allocation_chart(self, df):
        if df.empty:
            return None

        top = df.sort_values("market_value", ascending=False).head(10)

        fig, ax = plt.subplots()
        ax.pie(top["market_value"], labels=top["symbol"], autopct="%1.1f%%")
        ax.set_title("Top Holdings Allocation")
        return self._save_chart(fig)

    def _factor_chart(self, attr):
        fig, ax = plt.subplots()
        ax.bar(
            ["Value", "Growth", "Momentum", "Quality"],
            [
                attr.get("value_pct", 0),
                attr.get("growth_pct", 0),
                attr.get("momentum_pct", 0),
                attr.get("quality_pct", 0),
            ],
        )
        ax.set_title("Factor Attribution")
        return self._save_chart(fig)

    # =========================================================
    # MAIN REPORT
    # =========================================================

    def generate_portfolio_report(self, portfolio_id, output_path):

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        temp_files = []

        # -----------------------------------------------------
        # COVER PAGE
        # -----------------------------------------------------
        elements.append(Paragraph("Portfolio Report", self.styles["Title"]))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d')}",
            self.styles["Normal"]
        ))
        elements.append(PageBreak())

        # -----------------------------------------------------
        # NAV DATA
        # -----------------------------------------------------
        nav_df = normalize_timeseries_df(
            self.nav_service.get_nav_history(portfolio_id)
        )

        if nav_df.empty or "NAV" not in nav_df.columns:
            elements.append(Paragraph(
                "No performance data available for this portfolio.",
                self.styles["Normal"]
            ))
            total_return = 0
            ann_return = 0
        else:
            nav_chart = self._nav_chart(nav_df)
            if nav_chart:
                temp_files.append(nav_chart)
                elements.append(Image(nav_chart, width=400, height=200))

            start = nav_df["NAV"].iloc[0]
            end = nav_df["NAV"].iloc[-1]

            total_return = (end / start - 1) if start else 0

            days = (nav_df["Date"].iloc[-1] - nav_df["Date"].iloc[0]).days
            ann_return = (1 + total_return) ** (365 / max(days, 1)) - 1

        # -----------------------------------------------------
        # POSITIONS
        # -----------------------------------------------------
        df_pos = pd.read_sql("""
            SELECT symbol, qty, market_value, unrealized_pnl
            FROM portfolio_positions
            WHERE portfolio_id = :pid
        """, self.db.bind, params={"pid": portfolio_id})

        # -----------------------------------------------------
        # EXECUTIVE SUMMARY
        # -----------------------------------------------------
        elements.append(Paragraph("Executive Summary", self.styles["Heading2"]))
        elements.append(Table([
            ["Metric", "Value"],
            ["Total Return", f"{total_return*100:.2f}%"],
            ["Annualized Return", f"{ann_return*100:.2f}%"],
            ["Equity", f"${df_pos['market_value'].sum():,.2f}" if not df_pos.empty else "$0.00"],
            ["PnL", f"${df_pos['unrealized_pnl'].sum():,.2f}" if not df_pos.empty else "$0.00"],
        ]))
        elements.append(PageBreak())

        # -----------------------------------------------------
        # PERFORMANCE OVERVIEW
        # -----------------------------------------------------
        elements.append(Paragraph("Performance Overview", self.styles["Heading2"]))
        nav_chart = self._nav_chart(nav_df)
        if nav_chart:
            temp_files.append(nav_chart)
            elements.append(Image(nav_chart, width=400, height=200))
        elements.append(Spacer(1, 20))

        # -----------------------------------------------------
        # BENCHMARK
        # -----------------------------------------------------
        try:
            bench = self.nav_service.compute_nav_vs_benchmark(portfolio_id, "SPY")

            comp_df = normalize_timeseries_df(bench.get("comparison_df", []))

            if comp_df.empty:
                elements.append(Paragraph("No benchmark data available.", self.styles["Normal"]))
            else:
                bench_chart = self._benchmark_chart(comp_df)
                if bench_chart:
                    temp_files.append(bench_chart)
                    elements.append(Paragraph("Benchmark Comparison", self.styles["Heading2"]))
                    elements.append(Image(bench_chart, width=400, height=200))

        except Exception as e:
            print("⚠️ BENCHMARK ERROR:", str(e))

        # -----------------------------------------------------
        # DRAWDOWN
        # -----------------------------------------------------
        elements.append(Paragraph("Drawdown Analysis", self.styles["Heading2"]))
        dd_chart = self._drawdown_chart(nav_df)
        if dd_chart:
            temp_files.append(dd_chart)
            elements.append(Image(dd_chart, width=400, height=200))
        elements.append(PageBreak())

        # -----------------------------------------------------
        # ALLOCATION
        # -----------------------------------------------------
        elements.append(Paragraph("Allocation / Holdings", self.styles["Heading2"]))

        if not df_pos.empty:
            alloc_chart = self._allocation_chart(df_pos.copy())
            if alloc_chart:
                temp_files.append(alloc_chart)
                elements.append(Image(alloc_chart, width=400, height=200))

            elements.append(Table(
                [df_pos.columns.tolist()] + df_pos.values.tolist()
            ))

        elements.append(PageBreak())

        # -----------------------------------------------------
        # FACTOR ATTRIBUTION
        # -----------------------------------------------------
        try:
            attr_data = self.nav_service.compute_factor_pnl_attribution(portfolio_id)
            attr = attr_data.get("attribution", {})

            elements.append(Paragraph("Factor Attribution", self.styles["Heading2"]))
            elements.append(Table([
                ["Factor", "Contribution"],
                ["Value", f"{attr.get('value_pct', 0)*100:.2f}%"],
                ["Growth", f"{attr.get('growth_pct', 0)*100:.2f}%"],
                ["Momentum", f"{attr.get('momentum_pct', 0)*100:.2f}%"],
                ["Quality", f"{attr.get('quality_pct', 0)*100:.2f}%"],
            ]))

            factor_chart = self._factor_chart(attr)
            if factor_chart:
                temp_files.append(factor_chart)
                elements.append(Image(factor_chart, width=400, height=200))

        except Exception as e:
            print("⚠️ FACTOR ERROR:", str(e))

        elements.append(PageBreak())

        # -----------------------------------------------------
        # RISK METRICS
        # -----------------------------------------------------
        if not nav_df.empty and "NAV" in nav_df.columns:
            returns = nav_df["NAV"].pct_change().dropna()

            vol = returns.std() * np.sqrt(252) if not returns.empty else 0
            sharpe = (
                (returns.mean() / returns.std() * np.sqrt(252))
                if returns.std() != 0 else 0
            )
        else:
            vol = 0
            sharpe = 0

        elements.append(Paragraph("Risk Metrics", self.styles["Heading2"]))
        elements.append(Table([
            ["Metric", "Value"],
            ["Volatility", f"{vol*100:.2f}%"],
            ["Sharpe Ratio", f"{sharpe:.2f}"],
        ]))
        elements.append(PageBreak())

        # -----------------------------------------------------
        # TRADES
        # -----------------------------------------------------
        df_trades = pd.read_sql("""
            SELECT symbol, side, filled_qty, avg_fill_price
            FROM trade_orders
            WHERE portfolio_id = :pid
        """, self.db.bind, params={"pid": portfolio_id})

        elements.append(Paragraph("Trade Analysis", self.styles["Heading2"]))

        if not df_trades.empty:
            elements.append(Table(
                [df_trades.columns.tolist()] + df_trades.values.tolist()
            ))

        elements.append(PageBreak())

        # -----------------------------------------------------
        # BUILD
        # -----------------------------------------------------
        doc.build(elements)

        # CLEANUP
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass

        return output_path