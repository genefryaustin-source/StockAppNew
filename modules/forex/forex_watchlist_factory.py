from modules.forex.forex_watchlist_service import (
    ForexWatchlistService,
)


def get_forex_watchlist_service(
    *,
    db,
    tenant_id,
    user_id,
    portfolio_id=None,
):

    return ForexWatchlistService(

        db=db,

        tenant_id=tenant_id,

        user_id=user_id,

        portfolio_id=portfolio_id,

    )