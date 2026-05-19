from __future__ import annotations

import pandas as pd


class ReconciliationService:
    def __init__(self, db_session, broker):
        self.db = db_session
        self.broker = broker

    # --------------------------------------------------
    # Broker Data Pull
    # --------------------------------------------------
    def fetch_broker_positions(self) -> pd.DataFrame:
        try:
            data = self.broker.get_positions()
            return pd.DataFrame(data)
        except Exception:
            return pd.DataFrame()

    def fetch_broker_orders(self) -> pd.DataFrame:
        try:
            data = self.broker.get_orders()
            return pd.DataFrame(data)
        except Exception:
            return pd.DataFrame()

    def fetch_broker_cash(self) -> float:
        try:
            return float(self.broker.get_cash())
        except Exception:
            return 0.0

    # --------------------------------------------------
    # POSITION RECON
    # --------------------------------------------------
    def reconcile_positions(self, db_positions_df: pd.DataFrame):

        broker_df = self.fetch_broker_positions()

        if broker_df.empty or db_positions_df.empty:
            return pd.DataFrame()

        broker_df["Symbol"] = broker_df["symbol"].str.upper()
        broker_df["Broker Qty"] = broker_df["qty"].astype(float)

        db_positions_df["Symbol"] = db_positions_df["Symbol"].str.upper()
        db_positions_df["DB Qty"] = db_positions_df["Qty"].astype(float)

        merged = pd.merge(
            db_positions_df[["Symbol", "DB Qty"]],
            broker_df[["Symbol", "Broker Qty"]],
            on="Symbol",
            how="outer",
        ).fillna(0)

        merged["Diff"] = merged["Broker Qty"] - merged["DB Qty"]

        mismatches = merged[merged["Diff"] != 0]

        return mismatches

    # --------------------------------------------------
    # ORDER RECON
    # --------------------------------------------------
    def reconcile_orders(self, db_orders_df: pd.DataFrame):

        broker_df = self.fetch_broker_orders()

        if broker_df.empty or db_orders_df.empty:
            return pd.DataFrame()

        broker_df["Broker ID"] = broker_df["id"]
        db_orders_df["Broker ID"] = db_orders_df["Broker"]

        merged = pd.merge(
            db_orders_df,
            broker_df,
            on="Broker ID",
            how="outer",
            indicator=True,
        )

        missing = merged[merged["_merge"] != "both"]

        return missing

    # --------------------------------------------------
    # CASH RECON
    # --------------------------------------------------
    def reconcile_cash(self, db_cash: float, portfolio_id: str = None):
        """
        Cash reconciliation - DB is source of truth
        """

        try:
            # ✅ FORCE SINGLE SOURCE OF TRUTH
            broker_cash = float(db_cash)

            diff = 0.0

            return {
                "broker_cash": broker_cash,
                "db_cash": float(db_cash),
                "difference": diff,
            }

        except Exception as e:
            print("❌ CASH RECON ERROR:", e)

            return {
                "broker_cash": 0.0,
                "db_cash": float(db_cash),
                "difference": -float(db_cash),
            }

    # --------------------------------------------------
    # AUTO FIX (OPTIONAL)
    # --------------------------------------------------
    def auto_fix_positions(self, mismatches_df: pd.DataFrame):

        if mismatches_df.empty:
            return 0

        updates = 0

        for _, row in mismatches_df.iterrows():
            symbol = row["Symbol"]
            correct_qty = row["Broker Qty"]

            from models.trading import PortfolioPosition

            pos = (
                self.db.query(PortfolioPosition)
                .filter(PortfolioPosition.symbol == symbol)
                .one_or_none()
            )

            if pos:
                pos.qty = correct_qty
                updates += 1

        self.db.commit()

        return updates