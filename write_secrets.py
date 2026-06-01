import os

content = (
    'DATABASE_URL = "sqlite:///./app.db"\n'
    'BASE_URL = "http://localhost:8501"\n'
    'POLYGON_API_KEY = "m6lUZpzppIwEh4fASAEEkyRWPtqUYTxD"\n'
    'MASSIVE_API_KEY = "m6lUZpzppIwEh4fASAEEkyRWPtqUYTxD"\n'
    'FMP_API_KEY = "ijN4i32gvowDZUs1GJe0U2v9olOw0bGf"\n'
    'EODHD_API_KEY = "69bf4fdc40ef46.91510923"\n'
    'FINNHUB_API_KEY = "d6vo1f1r01qiiutchb5gd6vo1f1r01qiiutchb60"\n'
    'MARKETDATA_API_KEY = "Wmp4d2ZZTzBpc3l0bUpmSDlwRjhkX1lfX1FzY3BVelg5VHJOUzFiLVcxND0"\n'
    'ALPHAVANTAGE_API_KEY = "UW5KGD8KXUUFZ92S"\n'
    'ANTHROPIC_API_KEY = "PASTE_YOUR_NEW_KEY_HERE"\n'
    'TWELVEDATA_API_KEY = "1d731f471e2b4cd197e5931e0d0c4dbe"\n'
    'QUIVER_API_KEY = ""\n'
    'FINTEL_API_KEY = ""\n'
    'IEX_API_TOKEN = ""\n'
    'ALPACA_API_KEY = "PKI4C5KHDNYJOK2SNSVYKUIBUC"\n'
    'ALPACA_API_SECRET = "E7CM3U2HnZLo7MDvKm8bao5TRthocDK5NWqhsQHcbTud"\n'
    'ALPACA_BASE_URL = "https://paper-api.alpaca.markets"\n'
    'STRIPE_SECRET_KEY = ""\n'
    'OAUTH_MS_TENANT = "common"\n'
    '\n'
    '[market_data]\n'
    'PRIMARY_PROVIDER = "polygon"\n'
    'TIMEOUT_SECONDS = 15\n'
    'MAX_RETRIES = 4\n'
    'CACHE_TTL_SECONDS = 900\n'
    'ENABLE_OFFLINE_MODE = true\n'
    '\n'
    '[trading]\n'
    'DEFAULT_BROKER = "paper"\n'
    'ENABLE_LIVE_TRADING = false\n'
    'KILL_SWITCH = false\n'
    'MAX_ORDER_NOTIONAL = 50000\n'
    'MAX_POSITION_PCT = 0.25\n'
    'MAX_DAILY_ORDERS = 25\n'
    'MAX_DRAWDOWN_HALT = -0.20\n'
    'ALLOW_SHORTS = false\n'
    '\n'
    '[alpaca]\n'
    'API_KEY = "PKI4C5KHDNYJOK2SNSVYKUIBUC"\n'
    'API_SECRET = "E7CM3U2HnZLo7MDvKm8bao5TRthocDK5NWqhsQHcbTud"\n'
    'BASE_URL_PAPER = "https://paper-api.alpaca.markets"\n'
    'BASE_URL_LIVE = "https://api.alpaca.markets"\n'
    'DATA_URL = "https://data.alpaca.markets"\n'
    '\n'
    '[email]\n'
    'PROVIDER = "smtp"\n'
    'SMTP_PORT = 587\n'
    'SMTP_USE_TLS = true\n'
)

path = r'C:\StockApp\.streamlit\secrets.toml'
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f'Written OK to {path}')

# Verify it parses
import toml
with open(path, 'r', encoding='utf-8') as f:
    data = toml.load(f)
print('TOML valid. Top-level keys:', [k for k in data.keys()])