import streamlit as st


def _home():
    st.markdown('''
# 📘 Stock Research Terminal Documentation Center

This help center is organized as an operating guide, not just a feature list.

Core platform workflow:

```text
Login / User Context
    ↓
Watchlists / Universes
    ↓
Market Data Refresh
    ↓
Analytics / Rankings / Signals
    ↓
Research Dashboards / AI / IPO / Crypto / Options
    ↓
Portfolio Construction / Deployment / Reports / Exports
```

Use the section selector on the left to jump to the area you need.
''')


def _getting_started():
    st.markdown('''
# 🚀 Getting Started

## First-Time Setup Checklist

### 1. Log in and verify user context

Confirm the app opens under the correct user, tenant, role, and permission level.

Typical roles:

```text
regular user
analyst
trader
portfolio manager
tenant admin
super admin
```

Your sidebar modules may vary based on role.

### 2. Confirm API keys

Common keys:

```text
POLYGON_API_KEY
MARKETDATA_API_KEY
FINNHUB_API_KEY
ALPHAVANTAGE_API_KEY
TWELVEDATA_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
ROIC_API_KEY
```

Local app location:

```text
.streamlit/secrets.toml
```

Streamlit Cloud location:

```text
App → Settings → Secrets
```

### 3. Create your first watchlist

Go to **Watchlists** and add symbols such as:

```text
AAPL
MSFT
NVDA
AMD
PLTR
AMZN
META
GOOGL
```

Watchlists feed market data refresh, analytics, rankings, alerts, portfolio construction, and reports.

### 4. Build or select a universe

Go to **Universe**. A universe is a larger research population than a watchlist.

Examples:

- all symbols
- large cap growth
- AI infrastructure
- semiconductors
- energy
- portfolio holdings
- custom symbols

### 5. Refresh market data

Go to **Market Data**.

Use:

```text
Limit symbols = 0
```

to refresh the full selected universe.

For testing:

```text
Limit symbols = 25 / 50 / 100
```

### 6. Run analytics

Go to **Analytics**. Analytics creates value, growth, momentum, quality, risk, composite, and ranking inputs.

### 7. Review rankings

Go to **Rankings** and **AI Rankings** to identify the strongest candidates.

### 8. Research candidates

Use Stock Dashboard, Earnings, Analyst Consensus, Sentiment, Smart Money, and Reports.

### 9. Build portfolio candidates

Use Portfolio Construction, Portfolio Deployment, AI Portfolio, Alerts, and Research Reports.
''')


def _daily_workflow():
    st.markdown('''
# 📅 Daily Operating Workflow

## Morning Workflow

### Step 1 — Review Market Overview

Check index direction, sector leadership, volatility, risk-on/risk-off tone, top movers, crypto tone, IPO updates, and Pre-IPO updates.

### Step 2 — Refresh market data

Go to **Market Data**.

Recommended:

```text
Limit symbols = 0
```

for complete refresh after provider health is verified.

For quick checks:

```text
Limit symbols = 25 or 50
```

Provider failover order:

```text
Polygon / Massive
    ↓
MarketData.app
    ↓
Finnhub
    ↓
Alpha Vantage
    ↓
TwelveData
    ↓
Yahoo fallback
```

### Step 3 — Run analytics

Run analytics after market data refresh to update scores, rankings, dashboards, portfolio inputs, alerts, strategy inputs, and reports.

### Step 4 — Check rankings

Review top composite names, names improving or deteriorating, high momentum names, value + quality names, low confidence names, and high risk names.

### Step 5 — Check Stock Dashboard

For top ranked names:

1. open the Stock Dashboard
2. review price trend
3. review analytics
4. review sentiment/news
5. review earnings/transcript data
6. compare ranking signal to market context

### Step 6 — Check alerts and scanner

Review breakouts, volume spikes, watchlist triggers, portfolio risk alerts, price changes, and technical conditions.

### Step 7 — Review portfolio

Check holdings, cash, PnL, exposure, sector concentration, drift, and replacement candidates.

## During Market Hours

Use Intraday Charts, Stock Dashboard, Options Flow, Alerts, Scanner, Market Overview, Sentiment, and Smart Money.

## End-of-Day Workflow

1. Refresh prices after close.
2. Run analytics again.
3. Review rankings.
4. Review portfolio drift.
5. Review alerts.
6. Generate research reports.
7. Export data if needed.
8. Prepare next-day watchlist.
''')


def _stock_research():
    st.markdown('''
# 📊 Stock Research Modules

## Watchlists

Purpose: organize symbols, track research candidates, feed analytics and alerts, and build custom focus lists.

Daily use:

1. Add or remove symbols.
2. Refresh market data.
3. Run analytics.
4. Review rankings and alerts.

## Universe

Purpose: define broader research groups for screening, bulk analytics, and portfolio construction.

Examples: AI Infrastructure, Semiconductors, Large Cap Growth, Dividend Quality, Energy, Custom Portfolio Universe.

## Screener

Filters stocks by price, market cap, volume, RSI, momentum, valuation, growth, sector, and analytics score.

Workflow:

1. choose universe
2. set filters
3. run screen
4. save candidates
5. review Stock Dashboard
6. add to watchlist or portfolio workflow

## Stock Dashboard

Single-name research workspace showing price, volume, technicals, analytics, sentiment/news, earnings, rankings, and AI research notes.

Best use:

```text
Ranking candidate → Stock Dashboard → Research validation → Watchlist / Portfolio
```

## Earnings

Tracks earnings and transcripts. Supports transcript retrieval, transcript cache, AI transcript Q&A, management commentary review, and guidance analysis.

Example questions:

```text
What did management say about margins?
What guidance was provided?
What risks were discussed?
What are the demand trends?
What did analysts challenge management on?
```

## Analyst Consensus

Review price targets, rating changes, consensus direction, and confirmation/contradiction of internal analytics.

## Smart Money

Track institutional-style signals when available. Use as confirmation, not as a standalone decision.
''')


def _market_data_analytics():
    st.markdown('''
# 📡 Market Data, Analytics, Rankings

## Market Data

Market data is the foundation of the app. If stale or missing, Analytics, Rankings, Stock Dashboard, Portfolio Analytics, Forecasts, Reports, and Alerts may be incomplete.

### Provider Failover

```text
Polygon / Massive
MarketData.app
Finnhub
Alpha Vantage
TwelveData
Yahoo
```

### Best Practice

1. Test with 25 symbols.
2. Confirm provider health.
3. Run full refresh.
4. Run analytics.
5. Review rankings.

## Analytics

Analytics converts raw data into value score, quality score, growth score, momentum score, volatility, drawdown, risk score, and composite score.

Run analytics after every major market data refresh.

## Rankings

Rankings include value, growth, quality, momentum, composite, and risk-adjusted views.

## AI Rankings

AI Rankings combine scores with decision logic for shortlist generation, portfolio candidates, analyst review, and strategy research.
''')


def _ipo():
    st.markdown('''
# 🚀 IPO Intelligence Center

## Purpose

Tracks companies entering public markets through IPO calendars, filings, pricing stages, watchlists, and analytics.

## Main Workflow

1. Open IPO Intelligence.
2. Refresh IPO calendar if needed.
3. Review upcoming IPOs.
4. Check deal size and exchange.
5. Review sector and underwriter trends.
6. Add interesting IPOs to watchlist.
7. Generate research notes or reports.

## IPO Calendar

Shows company, symbol, exchange, expected IPO date, price range, shares, deal size, and underwriters.

## IPO Watchlist

Tracks IPOs of interest including pricing changes, listing date changes, watch status, notes, and alerts.

## IPO Analytics

Analyze IPO count by sector, deal size trends, exchange activity, underwriter concentration, and recent listing performance.

## IPO Research Workflow

1. Review calendar data.
2. Review company description.
3. Check sector.
4. Check underwriters.
5. Compare to similar public companies.
6. Add to watchlist if relevant.
7. Generate report.
''')


def _preipo():
    st.markdown('''
# 🏢 Pre-IPO Intelligence Center

## Purpose

Identifies companies showing signs of preparing for a public offering before listing.

## Daily Workflow

1. Open Pre-IPO Intelligence.
2. Run **SEC Discovery**.
3. Review **IPO Intelligence Dashboard**.
4. Review most likely IPO candidates.
5. Review recent high-probability candidates.
6. Check IPO Pipeline Funnel.
7. Check sector breakdown.
8. Add companies to watchlist.
9. Use Company SEC Lookup for targeted searches.

## SEC Discovery

Monitors:

```text
S-1
S-1/A
F-1
F-1/A
424B3
424B4
S-4
S-4/A
SPAC filings
```

Use:

```text
Lookback Days = 30 / 60 / 90
Max Results = 300 / 500 / 1000
```

## IPO Probability Engine

Calculates IPO Probability, IPO Opportunity Score, IPO Maturity Stage, Timeline Estimate, Sector, SPAC Classification, and Underwriter Strength.

## IPO Maturity Stages

```text
Initial Registration
Amendment / Roadshow Prep
Pricing / Prospectus Stage
SPAC / Merger Registration
Early Signal
```

## Timeline Estimates

```text
0-30 days / pricing stage
30-90 days
1-2 quarters
2-4 quarters
Deal-dependent / merger timeline
Watchlist only
```

## Watchlist Workflow

1. Find a candidate.
2. Review filing type.
3. Check probability and stage.
4. Add to watchlist.
5. Review periodically for new amendments.
''')


def _crypto():
    st.markdown('''
# ₿ Crypto Intelligence Center

## Purpose

Combines market data, sentiment, AI reports, portfolio tracking, and risk scanning.

## Daily Crypto Workflow

1. Open Crypto.
2. Review Market Overview.
3. Check Fear & Greed.
4. Review top movers.
5. Review trending coins.
6. Review DeFi / on-chain data.
7. Generate AI Market Narrative.
8. Run Trend Detector.
9. Run Risk Scanner.
10. Review portfolio tracker if holdings are entered.

## Market Overview

Shows total market cap, 24h volume, BTC dominance, ETH dominance, active coins, top coins table, and trending tokens.

## Coin Detail

Shows price, 24h/7d/30d change, market cap, volume, ATH distance, supply, chart, and AI coin analysis.

AI Coin Analysis includes What It Is, Bull Case, Bear Case, and Verdict.

## DeFi & NFT

Tracks DeFi TVL, protocols, chains, categories, and TVL changes.

## Sentiment & News

Includes crypto news, Reddit buzz, Polymarket odds, BTC on-chain metrics, futures/funding, and coin-specific sentiment.

## AI Market Narrative

Generates Macro Picture, Sector Rotation, and Watch List.

## Trend Detector

Identifies narratives such as AI tokens, Layer 1/2, DeFi, Gaming, Meme coins, Privacy coins, and RWAs.

## Risk Scanner

Flags extreme 24h moves, unusual volume, sharp 7d declines, and extreme fear conditions.

Outputs readable risk reports with What Happened, Why It Matters, Severity, and Recommended Action.

## Portfolio Tracker

Lets users enter holdings and receive portfolio value, weights, 7d movement, AI advice, concentration risk, and rebalancing suggestions.
''')


def _options():
    st.markdown('''
# 🧩 Options Trading

## Purpose

Supports strategy research, premium income, hedging, and risk analysis.

## Daily Options Workflow

1. Review underlying stock trend.
2. Check options flow.
3. Review volatility.
4. Choose strategy type.
5. Check Greeks.
6. Review max profit/loss.
7. Review breakeven.
8. Confirm portfolio exposure.

## Options Flow

Use for unusual volume, possible institutional interest, bullish/bearish confirmation, and catalyst detection.

## Strategy Center

Strategies may include covered calls, cash-secured puts, vertical spreads, iron condors, butterflies, and the wheel strategy.

## Covered Call Manager

Use when you own shares, want income, and are neutral to moderately bullish.

## Cash Secured Put Manager

Use when you are willing to buy shares lower, want premium income, and have cash reserved.

## Wheel Strategy

```text
cash secured put → assigned shares → covered call → repeat
```

## Greeks Dashboard

Monitor Delta, Gamma, Theta, Vega, and Rho.

## Risk Rules

Always review max loss, assignment risk, liquidity, bid/ask spread, expiration, and earnings dates.
''')


def _portfolio():
    st.markdown('''
# 💼 Portfolio Management

## Purpose

Helps construct, track, analyze, and deploy investment portfolios.

## Daily Portfolio Workflow

1. Review current holdings.
2. Refresh prices.
3. Run analytics.
4. Review PnL.
5. Review exposure.
6. Check rankings for replacement candidates.
7. Review alerts.
8. Generate portfolio report.

## Portfolio Dashboard

Tracks holdings, cash, positions, PnL, NAV, exposure, and risk.

## Portfolio Construction

Builds model portfolios from ranked candidates using number of holdings, max weight, sector cap, cash reserve, and ranking basis.

## Portfolio Deployment

Moves model portfolios into simulated or enabled deployment workflows. Check cash, target weights, order sizing, current holdings, and risk limits.

## AI Portfolio

Generates risk review, allocation review, concentration review, replacement ideas, and portfolio summaries.
''')


def _ai():
    st.markdown('''
# 🤖 AI Features

## Providers

```text
OpenAI
Anthropic Claude
```

## Uses

- earnings transcript Q&A
- stock analysis
- portfolio review
- crypto analysis
- trend detection
- IPO / Pre-IPO scoring
- report drafting
- research summaries

## Anthropic / Claude

Used in Crypto AI, research workflows, narrative analysis, and risk reports.

Verify:

```text
ANTHROPIC_API_KEY
```

Start Streamlit from the correct Python 3.12 venv.

## OpenAI

Used in transcript Q&A, research summaries, and AI workflows.

Verify:

```text
OPENAI_API_KEY
```

## Best Practices

1. Use AI as analysis support, not a trade signal by itself.
2. Confirm AI outputs against data.
3. Use AI reports to summarize, compare, and explain.
4. Keep provider keys current.
5. Restart app after changing secrets.
''')


def _analytics_fabric():
    st.markdown('''
# ⚙ Analytics Fabric / Operations

## Purpose

Manages large-scale analytics execution and operational health.

## Core Components

- Analytics Operations Center
- Analytics Scheduler
- Analytics Governor
- Analytics Optimizer
- Universe Analytics Orchestrator
- Universe Job Registry
- Universe Execution Queue
- Workload Balancer
- Runtime Controller
- Resource Governor
- Self Diagnostic Engine
- Self Healing Engine
- Validation Engine

## Diagnostics

Diagnostic modules check service dependencies, schema integrity, runtime health, missing tables, broken providers, and execution failures.

## Self-Healing

Self-healing can detect failed jobs, build recovery plans, dry-run fixes, recommend recovery actions, and track healing history.

## Admin Daily Checks

1. Check provider health.
2. Check job queue.
3. Check analytics status.
4. Check failed symbols.
5. Check diagnostics.
6. Review logs.
''')


def _admin():
    st.markdown('''
# 🛠 Administration

## Purpose

Controls platform operations.

## Admin Workflow

1. Confirm app starts correctly.
2. Confirm database is connected.
3. Confirm users can log in.
4. Confirm API keys.
5. Confirm provider health.
6. Confirm market data refresh.
7. Confirm analytics execution.
8. Check errors.
9. Check reports/exports.

## User Management

Manage users, roles, active/inactive status, and tenant assignments.

## Tenant Management

Manage tenant users, tenant configuration, and tenant data visibility.

## Provider Health

Monitor Polygon, MarketData.app, Finnhub, Alpha Vantage, TwelveData, Yahoo, ROIC, OpenAI, Anthropic, SEC EDGAR, and CoinGecko.

## Common Admin Fixes

### Wrong Python Environment

```cmd
python -m streamlit run app.py
```

from the activated app venv.

### Missing Package

```cmd
python -m pip install package-name
```

### Module Cache Issue

Stop Streamlit fully and restart.
''')


def _providers():
    st.markdown('''
# 🔌 API Providers

## Market Data

```text
Polygon / Massive
MarketData.app
Finnhub
Alpha Vantage
TwelveData
Yahoo
```

## News / Sentiment

```text
Finnhub News
Polygon News
Alpha Vantage News Sentiment
Cached News
```

## Earnings / Transcripts

```text
ROIC
manual upload
cached transcripts
```

## SEC / IPO / Pre-IPO

```text
SEC EDGAR
company ticker index
filing discovery
S-1 / F-1 / 424B / S-4
```

## Crypto

```text
CoinGecko
DeFi Llama
Alternative.me Fear & Greed
ApeWisdom Reddit
Polymarket
Finnhub Crypto News
```

## AI

```text
OpenAI
Anthropic
```

## Provider Troubleshooting

1. check API key
2. check provider limits
3. check internet connection
4. check provider status
5. check app logs
6. check fallback provider
''')


def _troubleshooting():
    st.markdown('''
# ❓ Troubleshooting

## Rankings are empty

Likely causes: market data has not been refreshed, analytics has not been run, universe is empty, provider failed, or data is stale.

Fix:

1. Refresh market data.
2. Run analytics.
3. Reopen rankings.

## Market Data Refresh is slow

Causes: full universe refresh, provider throttling, rate limits, fallback chain delay.

Fix:

1. test with 25 symbols
2. check provider health
3. confirm failover
4. rerun full refresh later

## Stock Dashboard news/sentiment empty

Check Finnhub key, Polygon key, Alpha Vantage key, cached news fallback, and timeout settings.

## Crypto AI error

Check:

```text
ANTHROPIC_API_KEY
```

Verify Python:

```cmd
where python
python -c "import anthropic; print(anthropic.__version__)"
python -m streamlit run app.py
```

## SEC Discovery returns zero

Check SEC User-Agent, internet connection, EDGAR endpoint, provider logs, and date lookback.

## Pre-IPO tabs not showing

Usually caused by Streamlit module cache.

Fix:

1. Stop app completely.
2. Restart Streamlit.
3. Confirm `render_preipo_center()` is loaded.

## ImportError after replacing files

1. confirm full file copied
2. run `python -m py_compile path/to/file.py`
3. restart Streamlit
4. check function names expected by imports

## GitHub push not updating

```bash
git status
git add .
git commit -m "Update StockApp"
git push origin main
```
''')


def render_help_center():
    st.title('📘 Stock Research Terminal Help Center')

    nav_col, content_col = st.columns([1, 4])

    sections = [
        'Home',
        'Getting Started',
        'Daily Workflow',
        'Stock Research',
        'Market Data / Analytics',
        'IPO Intelligence',
        'Pre-IPO Intelligence',
        'Crypto Intelligence',
        'Options Trading',
        'Portfolio Management',
        'AI Features',
        'Analytics Fabric',
        'Administration',
        'API Providers',
        'Troubleshooting',
    ]

    with nav_col:
        st.markdown('### Sections')
        section = st.radio('Select help topic', sections, label_visibility='collapsed')

    with content_col:
        if section == 'Home':
            _home()
        elif section == 'Getting Started':
            _getting_started()
        elif section == 'Daily Workflow':
            _daily_workflow()
        elif section == 'Stock Research':
            _stock_research()
        elif section == 'Market Data / Analytics':
            _market_data_analytics()
        elif section == 'IPO Intelligence':
            _ipo()
        elif section == 'Pre-IPO Intelligence':
            _preipo()
        elif section == 'Crypto Intelligence':
            _crypto()
        elif section == 'Options Trading':
            _options()
        elif section == 'Portfolio Management':
            _portfolio()
        elif section == 'AI Features':
            _ai()
        elif section == 'Analytics Fabric':
            _analytics_fabric()
        elif section == 'Administration':
            _admin()
        elif section == 'API Providers':
            _providers()
        elif section == 'Troubleshooting':
            _troubleshooting()


def render_help():
    render_help_center()
