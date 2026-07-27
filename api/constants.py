"""
Global API Constants
"""

from __future__ import annotations

DEFAULT_PAGE_SIZE = 50

MAX_PAGE_SIZE = 500

MAX_SYMBOLS_PER_REQUEST = 250

DEFAULT_TIMEOUT_SECONDS = 30

DEFAULT_CACHE_SECONDS = 300

DEFAULT_RATE_LIMIT = 100

DEFAULT_API_PREFIX = "/api"

API_VERSION_PREFIX = "/v1"

SUPPORTED_MARKETS = [

    "stocks",

    "options",

    "forex",

    "crypto",

]

SUPPORTED_ORDER_TYPES = [

    "market",

    "limit",

    "stop",

    "stop_limit",

]

SUPPORTED_SIDES = [

    "buy",

    "sell",

]

SUPPORTED_TIME_IN_FORCE = [

    "day",

    "gtc",

    "ioc",

    "fok",

]

SUPPORTED_BROKERS = [

    "paper",

    "alpaca",

    "interactive_brokers",

]

SUPPORTED_PROVIDERS = [

    "polygon",

    "marketdata",

    "finnhub",

    "alphavantage",

    "twelvedata",

    "yahoo",

]