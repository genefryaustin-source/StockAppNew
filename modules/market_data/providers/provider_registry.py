from modules.market_data.providers.polygon import PolygonProvider
from modules.market_data.providers.finnhub_provider import FinnhubProvider
from modules.market_data.providers.marketdata_provider import MarketDataProvider
from modules.market_data.providers.alpha_vantage_provider import AlphaVantageProvider
from modules.market_data.providers.yahoo import YahooProvider


HISTORY_PROVIDER_ORDER = [

    PolygonProvider(),

    MarketDataProvider(),

    FinnhubProvider(),

    AlphaVantageProvider(),

    YahooProvider(),
]


QUOTE_PROVIDER_ORDER = [

    PolygonProvider(),

    FinnhubProvider(),

    MarketDataProvider(),

    YahooProvider(),
]