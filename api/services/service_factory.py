"""
Service Factory

Responsible for constructing service instances.
"""

from __future__ import annotations


from api.services.adapters import (

    PortfolioServiceAdapter,

    StockServiceAdapter,

    ForexServiceAdapter,

    OptionsServiceAdapter,

    CryptoServiceAdapter,

    AIServiceAdapter,

)


class ServiceFactory:

    def create_portfolio_service(self):

        return PortfolioServiceAdapter()

    def create_stock_service(self):

        return StockServiceAdapter()

    def create_forex_service(self):

        return ForexServiceAdapter()

    def create_options_service(self):

        return OptionsServiceAdapter()

    def create_crypto_service(self):

        return CryptoServiceAdapter()

    def create_ai_service(self):

        return AIServiceAdapter()