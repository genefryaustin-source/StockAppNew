from __future__ import annotations

from pydantic import BaseModel


class PortfolioSummaryDTO(BaseModel):

    portfolio_id: str

    name: str

    account_id: str | None = None

    total_value: float = 0.0

    cash: float = 0.0

    buying_power: float = 0.0

    unrealized_pl: float = 0.0

    realized_pl: float = 0.0

    daily_pl: float = 0.0

    positions: int = 0