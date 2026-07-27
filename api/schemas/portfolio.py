"""
api/schemas/portfolio.py

Portfolio Request Schemas

Pydantic request bodies for the Portfolio router: a legacy query filter
(PortfolioQuery, currently unused by the router but kept for
compatibility) plus the create/update bodies for POST and PUT
/api/v1/portfolio.
"""

from pydantic import BaseModel
from pydantic import Field


class PortfolioQuery(BaseModel):
    """Tenant/account/user filter shape -- not currently referenced by
    any route in api/routers/portfolio.py."""

    tenant_id: str

    account_id: str | None = None

    user_id: str | None = None


class PortfolioCreateRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=120)

    description: str | None = None

    benchmark: str = Field(default="SPY", max_length=20)

    base_currency: str = Field(default="USD", max_length=10)

    starting_cash: float = Field(default=100000.0, ge=0)


class PortfolioUpdateRequest(BaseModel):
    """
    Partial update -- every field is optional, only fields explicitly
    provided in the request body are changed. starting_cash and
    is_active are intentionally not editable via this endpoint; see
    PortfolioService.update_portfolio for why.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)

    description: str | None = None

    benchmark: str | None = Field(default=None, max_length=20)

    base_currency: str | None = Field(default=None, max_length=10)