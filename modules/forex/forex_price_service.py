
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

    def get_quote(
        self,
        pair: str,
        *,
        runtime=None,
        force_refresh: bool = False,
    ) -> dict:
        return get_forex_quote_from_router(
            pair,
            runtime=runtime,
            force_refresh=force_refresh,
        )

    def get_quotes(
        self,
        pairs: Iterable[str],
        *,
        runtime=None,
        force_refresh: bool = False,
    ) -> dict:
        return get_forex_quotes_from_router(
            pairs,
            runtime=runtime,
            force_refresh=force_refresh,
        )

    #
    # Sprint 28/29
    # Semantic entry point used by the Runtime Builder.
    #
    def load_runtime_quotes(
        self,
        pairs: Iterable[str],
        *,
        runtime=None,
        force_refresh: bool = False,
    ) -> dict:
        return self.get_quotes(
            pairs,
            runtime=runtime,
            force_refresh=force_refresh,
        )

    def get_latest_price(
        self,
        pair: str,
        *,
        runtime=None,
        force_refresh: bool = False,
    ) -> Optional[float]:
        quote = self.get_quote(
            pair,
            runtime=runtime,
            force_refresh=force_refresh,
        )
        return quote.get("mid") or quote.get("last")

    def get_latest_prices(
        self,
        pairs: Iterable[str],
        *,
        runtime=None,
        force_refresh: bool = False,
    ) -> dict:
        quotes = self.get_quotes(
            pairs,
            runtime=runtime,
            force_refresh=force_refresh,
        )

        return {
            pair: (
                quote.get("mid")
                or quote.get("last")
            )
            for pair, quote in quotes.items()
        }

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

    def load_runtime_quotes(
            self,
            pairs,
            runtime=None,
            force_refresh: bool = False,
    ) -> dict:
        """
        Runtime entry point for bulk quote retrieval.

        This simply delegates to get_quotes() so there is exactly one
        implementation of quote acquisition.
        """
        return self.get_quotes(
            pairs=pairs,
            runtime=runtime,
            force_refresh=force_refresh,
        )


_SERVICE:ForexPriceService|None=None


def get_forex_price_service()->ForexPriceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE=ForexPriceService()
    return _SERVICE
