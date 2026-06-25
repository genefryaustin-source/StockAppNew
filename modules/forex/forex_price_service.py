
"""
modules/forex/forex_price_service.py
"""

from __future__ import annotations

from typing import Iterable, Optional

from modules.forex.providers.forex_provider_router import (
    get_forex_latest_price,
    get_forex_latest_prices,
    get_forex_quote_from_router,
    get_forex_quotes_from_router,
)


class ForexPriceService:

    def get_quote(self,pair:str,force_refresh:bool=False)->dict:
        return get_forex_quote_from_router(
            pair,
            force_refresh=force_refresh,
        )

    def get_quotes(
        self,
        pairs:Iterable[str],
        force_refresh:bool=False,
    )->dict:
        return get_forex_quotes_from_router(
            pairs,
            force_refresh=force_refresh,
        )

    def get_latest_price(
        self,
        pair:str,
        force_refresh:bool=False,
    )->Optional[float]:
        return get_forex_latest_price(
            pair,
            force_refresh=force_refresh,
        )

    def get_latest_prices(
        self,
        pairs:Iterable[str],
        force_refresh:bool=False,
    )->dict:
        return get_forex_latest_prices(
            pairs,
            force_refresh=force_refresh,
        )

    def convert(
        self,
        amount:float,
        base:str,
        quote:str,
        force_refresh:bool=False,
    )->Optional[float]:
        pair=f"{base.upper()}/{quote.upper()}"
        rate=self.get_latest_price(
            pair,
            force_refresh=force_refresh,
        )
        if rate is None:
            return None
        return float(amount)*float(rate)


_SERVICE:ForexPriceService|None=None


def get_forex_price_service()->ForexPriceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE=ForexPriceService()
    return _SERVICE
