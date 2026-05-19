from sqlalchemy import text
import uuid

class TaxLotService:

    def __init__(self, db):
        self.db = db

    def save_selection(self, portfolio_id, sell_trade_id, selections):
        """
        selections = [
            {"buy_trade_id": "...", "qty": 10},
            ...
        ]
        """

        # delete existing selections
        self.db.execute(text("""
            DELETE FROM tax_lot_selections
            WHERE portfolio_id = :pid
              AND sell_trade_id = :sid
        """), {"pid": portfolio_id, "sid": sell_trade_id})

        for sel in selections:
            self.db.execute(text("""
                INSERT INTO tax_lot_selections (
                    id, portfolio_id, sell_trade_id, buy_trade_id, qty
                )
                VALUES (
                    :id, :pid, :sid, :bid, :qty
                )
            """), {
                "id": str(uuid.uuid4()),
                "pid": portfolio_id,
                "sid": sell_trade_id,
                "bid": sel["buy_trade_id"],
                "qty": sel["qty"]
            })

        self.db.commit()

    def load_selection_map(self, portfolio_id):
        rows = self.db.execute(text("""
            SELECT sell_trade_id, buy_trade_id, qty
            FROM tax_lot_selections
            WHERE portfolio_id = :pid
        """), {"pid": portfolio_id}).fetchall()

        mapping = {}

        for r in rows:
            sid, bid, qty = r

            if sid not in mapping:
                mapping[sid] = []

            mapping[sid].append({
                "buy_trade_id": bid,
                "qty": qty
            })

        return mapping