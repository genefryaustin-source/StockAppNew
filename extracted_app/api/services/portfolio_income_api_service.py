"""
api/services/portfolio_income_api_service.py

Portfolio Income API Service

Backs GET /api/v1/portfolio/{portfolio_id}/income.

Reads modules.portfolio's own portfolio_cash_ledger table for non-trade
cash movements (dividends, interest, and similar). Honest limitation:
nothing in this codebase currently writes a dividend or interest entry
into that ledger, so this returns real, empty results today rather than
fabricated numbers -- see the class docstring below.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

# Cash-ledger entry types written by the trading pipeline itself -- not
# income. Anything else in the ledger (dividend, interest, fee reversal,
# manual adjustment, etc.) is a genuine non-trade cash movement.
_TRADE_ENTRY_TYPES = ("buy", "sell", "unknown", "seed")


class PortfolioIncomeAPIService:
    """
    API service for non-trade cash income (dividends, interest, and
    similar). Reads modules.portfolio's own portfolio_cash_ledger table.

    Honest limitation: nothing in this codebase currently writes a
    dividend or interest entry into that ledger -- there's no dividend
    capture or interest accrual mechanism yet. This will correctly
    report real income the moment something starts recording it; until
    then it returns real, empty results rather than fabricated numbers.
    """

    def __init__(self, db):
        self.db = db

    def get_income(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        limit: int = 250,
    ) -> dict[str, Any] | None:
        """
        Non-trade cash ledger entries for one portfolio (i.e. anything
        that isn't a buy/sell/seed entry), totaled and grouped by
        entry_type.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404.
        """

        # See portfolio_correlation_api_service.py for why this matters:
        # this service's session is cached and reused for the life of
        # the process, so a prior request's unrolled-back failure would
        # otherwise break every query below, including this first one.
        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

        if portfolio is None:
            return None

        placeholders = ",".join(f":t{i}" for i in range(len(_TRADE_ENTRY_TYPES)))
        params: dict[str, Any] = {
            f"t{i}": t for i, t in enumerate(_TRADE_ENTRY_TYPES)
        }
        params["pid"] = portfolio_id
        params["limit"] = limit

        rows = self.db.execute(
            text(
                f"""
                SELECT entry_type, amount, currency, notes, created_at
                FROM portfolio_cash_ledger
                WHERE portfolio_id = :pid
                  AND entry_type NOT IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()

        entries = [dict(row) for row in rows]
        for row in entries:
            if row.get("created_at") is not None:
                row["created_at"] = str(row["created_at"])

        total_income = sum(float(e["amount"] or 0.0) for e in entries)

        by_type: dict[str, float] = {}
        for e in entries:
            by_type[e["entry_type"]] = by_type.get(e["entry_type"], 0.0) + float(
                e["amount"] or 0.0
            )

        return {
            "portfolio_id": str(portfolio_id),
            "total_income": round(total_income, 2),
            "income_by_type": {k: round(v, 2) for k, v in by_type.items()},
            "entries": entries,
            "note": (
                "No dividend or interest capture mechanism exists in this "
                "platform yet -- this reflects real ledger entries only, "
                "and will remain empty until trades or a dividend feed "
                "start writing non-trade cash entries."
                if not entries
                else None
            ),
        }