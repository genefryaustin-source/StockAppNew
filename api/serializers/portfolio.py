from models.trading import Portfolio


def serialize_portfolio(portfolio: Portfolio):

    return {
        "id": portfolio.id,
        "tenant_id": portfolio.tenant_id,
        "name": portfolio.name,
        "description": portfolio.description,
        "benchmark": portfolio.benchmark,
        "base_currency": portfolio.base_currency,
        "starting_cash": portfolio.starting_cash,
        "is_active": portfolio.is_active,
        "created_at": portfolio.created_at,
        "updated_at": portfolio.updated_at,
    }


def serialize_portfolios(portfolios):

    return [
        serialize_portfolio(p)
        for p in portfolios
    ]