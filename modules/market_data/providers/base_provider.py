from abc import ABC, abstractmethod
import pandas as pd


class BaseMarketDataProvider(ABC):

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_latest_price(
        self,
        symbol: str,
    ):
        pass

    @abstractmethod
    def get_latest_prices(
        self,
        symbols,
    ):
        pass

    @abstractmethod
    def provider_name(self) -> str:
        pass