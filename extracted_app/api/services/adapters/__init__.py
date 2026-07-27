from .portfolio_adapter import PortfolioServiceAdapter
from .stocks_adapter import StockServiceAdapter
from .forex_adapter import ForexServiceAdapter
from .options_adapter import OptionsServiceAdapter
from .crypto_adapter import CryptoServiceAdapter
from .ai_adapter import AIServiceAdapter

__all__ = [

    "PortfolioServiceAdapter",

    "StockServiceAdapter",

    "ForexServiceAdapter",

    "OptionsServiceAdapter",

    "CryptoServiceAdapter",

    "AIServiceAdapter",

]

"""
Portfolio Service Adapter

Bridges the API layer to the existing
StockApp Portfolio module.
"""

from __future__ import annotations


class PortfolioServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            #
            # TODO
            #
            # Replace with the existing portfolio
            # service used by Streamlit.
            #

            # Example:
            #
            # from modules.portfolio.portfolio_service import PortfolioService
            #
            # self._service = PortfolioService()

            pass

        return self._service

"""
Stock Service Adapter
"""

from __future__ import annotations


class StockServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            #
            # Wire existing stock service
            #

            pass

        return self._service
"""
Forex Adapter
"""

from __future__ import annotations


class ForexServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            #
            # Existing:
            #
            # modules.forex.forex_service
            #

            pass

        return self._service

"""
Options Adapter
"""

from __future__ import annotations


class OptionsServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            pass

        return self._service

"""
Crypto Adapter
"""

from __future__ import annotations


class CryptoServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            pass

        return self._service

"""
AI Adapter
"""

from __future__ import annotations


class AIServiceAdapter:

    def __init__(self):

        self._service = None

    @property
    def service(self):

        if self._service is None:

            pass

        return self._service

