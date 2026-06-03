import streamlit as st


def render_help():

    st.title("📘 StockApp / Equities Research Terminal — Complete User Guide")

    st.markdown("""
Welcome to the StockApp Equities Research Terminal.

This guide explains how to get started, what to do each day, and how each major
area of the app connects to the rest of the platform.

The app is designed around one core workflow:

```text
Symbols / Universe
    ↓
Market Data
    ↓
Analytics
    ↓
Rankings / Research / Signals
    ↓
Portfolio / Trading / Reports
```

If something looks empty, the most common reason is that an earlier dependency
has not been completed yet, usually market data or analytics.
""")

    # ================================================================
    # GETTING STARTED
    # ================================================================

    with st.expander("🚀 Start Here — First-Time Setup for a Regular User", expanded=True):
        st.markdown("""
## Goal

Get the app ready so you can research stocks, review rankings, monitor portfolios,
and use the daily dashboards.

## Step-by-Step Setup

### 1. Log in and confirm your tenant/user context

After login, confirm that your account opens the correct workspace.

If the app uses roles, your available pages may differ depending on whether you are:

- regular user
- analyst
- trader
- admin
- tenant admin
- super admin

### 2. Confirm API keys and provider settings

The app relies on market data, transcript data, AI models, and optional news/sentiment providers.

Common keys include:

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

If running locally, these are usually in:

```text
.streamlit/secrets.toml
```

If running in Streamlit Cloud, they are in:

```text
App → Settings → Secrets
```

### 3. Create or select your watchlist

Go to **Watchlists** and add the symbols you care about.

Example:

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

Watchlists are one of the main sources for analysis, rankings, alerts, and portfolio ideas.

### 4. Build or select a universe

Go to **Universe Builder** if you want a broader research universe.

A universe may include:

- all symbols in the database
- sector-specific groups
- large-cap growth names
- high-volume stocks
- custom symbols
- portfolio/watchlist symbols

### 5. Run Market Data Refresh

Go to **Market Data / Market Refresh** and run the refresh.

Use:

```text
Limit symbols = 0
```

to refresh all symbols in the selected source/universe.

The market data refresh now uses provider failover:

```text
Polygon / Massive
    ↓ if unavailable or rate-limited
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

This is important because a single provider can throttle, fail, or return no data.

### 6. Run Analytics

Go to **Analytics** and run the analytics pipeline.

This creates:

- valuation metrics
- momentum scores
- quality scores
- growth scores
- risk metrics
- composite scores
- ranking inputs

Many pages depend on analytics being current.

### 7. Review Rankings

Go to **Rankings** and **AI Ranking Engine**.

Use these pages to find the strongest stocks by:

- value
- growth
- quality
- momentum
- composite score
- AI-adjusted scoring

### 8. Use Portfolio Construction

After rankings are populated, use **Portfolio Construction** to build a model portfolio.

The portfolio engine uses analytics outputs to help decide:

- which names to include
- position sizes
- sector balance
- concentration limits
- risk exposure

### 9. Monitor performance

Use:

- Portfolio Analytics
- Client Dashboard
- Market Dashboard
- Reports
- Alerts

to monitor positions and market conditions.

### 10. Export or report

Use **Reports** and **Export** to generate outputs for review, clients, internal documentation,
or investment committee workflows.
""")

    # ================================================================
    # DAILY WORKFLOW
    # ================================================================

    with st.expander("📅 Daily Workflow — What To Do After Setup", expanded=True):
        st.markdown("""
## Morning Workflow

### 1. Open Market Overview / Market Dashboard

Start with the broad market:

- major index trend
- sector movement
- macro dashboard
- top movers
- risk-on/risk-off conditions

This gives context before looking at individual names.

### 2. Refresh market data

Run **Market Data Refresh**.

For full refresh:

```text
Limit symbols = 0
```

For a faster test refresh:

```text
Limit symbols = 25 / 50 / 100
```

Use the provider health dashboard to see whether providers are healthy, rate-limited, or falling back.

### 3. Run Analytics

After data refresh, run analytics.

This updates:

- scores
- rankings
- signals
- portfolio analytics
- dashboards

### 4. Check Rankings

Review top-ranked opportunities.

Look for:

- names moving up the ranking
- high-confidence names
- names with strong momentum and fundamentals
- names that have fallen due to risk or technical weakness

### 5. Check Alerts and Scanner

Review:

- price alerts
- breakout alerts
- volume alerts
- technical scanner results
- unusual activity

### 6. Review portfolio and trading pages

For portfolios:

- check exposure
- review cash
- review PnL
- review risk
- check concentration

For trading:

- review trade candidates
- confirm execution rules
- check paper/live mode

## During Market Hours

Use:

- Intraday
- Options Flow
- Scanner
- Alerts
- Sentiment
- Market Dashboard

These pages are more tactical and useful while the market is active.

## End-of-Day Workflow

1. Refresh prices after close.
2. Run analytics again.
3. Review portfolio drift.
4. Generate reports.
5. Export data if needed.
6. Prepare next-day watchlist/trade list.
""")

    # ================================================================
    # ROLE WORKFLOWS
    # ================================================================

    with st.expander("👤 Workflow for a Regular Research User"):
        st.markdown("""
A regular user is usually focused on discovering, researching, and monitoring stocks.

## Recommended workflow

1. Maintain watchlists.
2. Refresh market data.
3. Run analytics.
4. Review rankings.
5. Open stock dashboard for individual names.
6. Read earnings and transcript insights.
7. Save candidates to watchlists.
8. Monitor alerts.

## Best pages for this role

- Watchlists
- Screener
- Market Data
- Analytics
- Rankings
- Stock Dashboard
- Earnings
- Forecasting
- Reports
""")

    with st.expander("🧠 Workflow for an Analyst"):
        st.markdown("""
An analyst uses the platform for deeper research, comparison, and report generation.

## Analyst workflow

1. Build a focused universe.
2. Run market data refresh.
3. Run analytics.
4. Review rankings and outliers.
5. Open individual stock dashboards.
6. Use Earnings Transcript AI Q&A.
7. Compare companies across transcripts.
8. Review valuation and sentiment.
9. Generate reports and export results.

## Analyst-specific modules

### Analyst Page

Used for structured analyst workflows, research notes, reviews, and deeper company evaluation.

### Earnings Transcript AI Q&A

Fetches or stores earnings call transcripts, then lets you ask questions using OpenAI or Anthropic.

Example questions:

```text
What did management say about revenue growth?
What were the main margin drivers?
What guidance did management provide?
What risks did analysts ask about?
```

### Reports

Used to produce research outputs from app data.

### Export

Used to export tables, research outputs, and data for downstream review.

## Analyst daily routine

- Morning: check market overview and watchlist changes.
- Midday: review earnings, news, sentiment, and ranking changes.
- End of day: generate reports, update notes, export top candidates.
""")

    with st.expander("📈 Workflow for a Trader"):
        st.markdown("""
A trader uses the app to identify timely opportunities, monitor intraday action, and manage execution.

## Trader workflow

1. Refresh market data.
2. Check Market Dashboard.
3. Review Intraday module.
4. Check Scanner and Alerts.
5. Review Options Flow.
6. Review Sentiment.
7. Check Rankings for confirmation.
8. Use Trading / Portfolio pages for execution and risk tracking.

## Trader-specific modules

### Intraday

Tracks short-term market behavior and intraday movements.

Useful for:

- identifying active names
- monitoring price action
- checking short-term momentum
- confirming entry/exit conditions

### Options Flow

Tracks unusual or notable options activity.

Useful for:

- directional clues
- institutional activity
- unusual volume
- possible catalyst trades

### Alerts / Scanner

Useful for:

- breakouts
- volume spikes
- oversold/overbought moves
- watchlist triggers

### Trading

Used for simulated or enabled trading workflows.

## Trader daily routine

- Pre-market: refresh data, check macro dashboard, review alerts.
- Market open: monitor intraday, scanner, and options flow.
- Midday: check risk, PnL, and trade list.
- Close: refresh data, review trades, export/report if needed.
""")

    with st.expander("🏦 Workflow for a Portfolio Manager"):
        st.markdown("""
A portfolio manager focuses on allocation, risk, exposure, performance, and reporting.

## Portfolio workflow

1. Review current holdings.
2. Refresh market data.
3. Run analytics.
4. Review portfolio analytics.
5. Check rankings for replacement candidates.
6. Use portfolio construction.
7. Review risk and sector concentration.
8. Generate reports.

## Best modules

- Portfolio Analytics
- Portfolio Construction
- AI Portfolio Center
- Rankings
- Market Dashboard
- Reports
- Export

## Key questions

- Is the portfolio concentrated?
- Are holdings still ranked well?
- Has sector exposure drifted?
- Is risk increasing?
- Are there better-ranked replacements?
- Are alerts firing on holdings?
""")

    with st.expander("🛠️ Workflow for Admin / Tenant Admin"):
        st.markdown("""
Admins maintain the operational side of the app.

## Admin responsibilities

- manage users
- manage tenants
- verify API keys
- monitor provider health
- monitor caches
- check errors
- validate data refreshes
- control feature access when implemented
- troubleshoot deployment issues

## Best admin pages

- Admin
- Tenant Admin
- Provider Health Dashboard
- Market Data Refresh
- Analytics Fabric dashboards
- Reports / Exports

## Admin daily checks

1. Confirm app loads correctly.
2. Confirm provider health.
3. Confirm market data refresh completed.
4. Confirm analytics jobs completed.
5. Check logs for API throttling.
6. Confirm users can access the right pages.
""")

    # ================================================================
    # MODULE DETAILS
    # ================================================================

    with st.expander("📊 Market Overview / Market Dashboard"):
        st.markdown("""
## Purpose

Shows broad market conditions before users drill into individual names.

## What it does

- summarizes market direction
- shows sector/asset movement
- highlights market risk
- provides top-down context

## Why it matters

Individual stock decisions should be made in context of the market regime.

## Integrations

Uses market data from:

```text
Market Data Refresh → price_history → Market Dashboard
```

May also connect to:

- macro dashboard
- sentiment
- rankings
- alerts
""")

    with st.expander("📡 Market Data / Market Refresh / Provider Health", expanded=True):
        st.markdown("""
## Purpose

This is the data foundation of the entire app.

If market data is missing or stale, analytics, rankings, portfolio analytics, charts,
and signals may be incomplete.

## What it does

- loads price history
- stores data in `price_history`
- refreshes current/latest prices
- uses multiple providers
- falls back when providers fail
- avoids relying on a single vendor

## Provider failover

The refresh system should attempt providers in this general order:

```text
Polygon / Massive
MarketData.app
Finnhub
Alpha Vantage
TwelveData
Yahoo
```

If Polygon is rate-limited, the app should move to MarketData instead of retrying Polygon repeatedly.

## Important control

```text
Limit symbols (0 = all)
```

- `0` means refresh all symbols selected by the refresh universe.
- A positive number limits the run for testing or smaller updates.

## How it integrates

Market data feeds:

- Analytics
- Rankings
- AI Ranking Engine
- Stock Dashboard
- Portfolio Analytics
- Intraday
- Alerts
- Scanner
- Reports
- Forecasting

## Common problems

### Provider throttling

If you see:

```text
maximum requests per minute
rate limit
too many requests
```

the provider is throttled. Failover should move to the next provider.

### Empty rankings

Usually means market data or analytics has not been run.

### Only one symbol refreshing

Check the symbol source and refresh universe. The updater should receive the full symbol list.
""")

    with st.expander("📋 Watchlists"):
        st.markdown("""
## Purpose

Watchlists organize symbols into groups.

## What users do here

- create watchlists
- add/remove symbols
- monitor selected names
- prepare research groups

## Why it matters

Watchlists are often the first step before analytics, alerts, rankings, and reporting.

## Integrations

Watchlists can feed:

- Market Data Refresh
- Screener
- Analytics
- Rankings
- Alerts
- Portfolio Construction
- Reports
""")

    with st.expander("🌐 Universe Builder"):
        st.markdown("""
## Purpose

Creates larger groups of symbols for screening, analytics, and portfolio construction.

## What it does

- defines the research universe
- filters by market cap, sector, liquidity, or other rules
- creates groups larger than a watchlist

## Why it matters

The universe defines what the app analyzes.

A strong universe means better rankings and better portfolio candidates.

## Integrations

Universe Builder feeds:

- Market Data Refresh
- Analytics
- Rankings
- AI Ranking Engine
- Portfolio Construction
- Scanner
""")

    with st.expander("🔍 Screener"):
        st.markdown("""
## Purpose

Filters stocks using rules.

## Common filters

- price
- market cap
- volume
- valuation
- growth
- momentum
- RSI
- sector

## Workflow

1. Choose universe/watchlist.
2. Set filters.
3. Run screen.
4. Save candidates.
5. Run analytics if needed.
6. Review rankings or dashboard.

## Integrations

Screener uses data from:

- market data
- fundamentals
- analytics
- watchlists/universes

Screener results can feed:

- watchlists
- rankings
- portfolio construction
- reports
""")

    with st.expander("⚙️ Analytics", expanded=True):
        st.markdown("""
## Purpose

Analytics converts raw data into scores, metrics, and ranking inputs.

## What it calculates

- price momentum
- volatility
- drawdown
- valuation
- growth
- quality
- technical indicators
- composite scores
- risk metrics

## Why it matters

Analytics is required before many advanced pages work properly.

## Pages that depend on analytics

- Rankings
- AI Ranking Engine
- Portfolio Construction
- Portfolio Analytics
- Strategy Lab
- Forecasting
- Reports
- Alerts
- Scanner

## Controls

### Batch size

Controls how many symbols are processed at once.

### Force refresh

Recomputes even if data already exists.

### Lookback

Controls the historical window.

### Max symbols / max API calls

Prevents overloading providers or running too long.

## Best practice

Run market data first, then analytics.
""")

    with st.expander("🏆 Rankings / AI Ranking Engine"):
        st.markdown("""
## Purpose

Ranks stocks using analytics scores.

## Standard Rankings

Ranks by:

- value
- growth
- quality
- momentum
- composite score
- risk-adjusted metrics

## AI Ranking Engine

Combines signals into smarter prioritization.

The AI ranking layer can use weighted scoring across:

- value
- growth
- quality
- momentum
- risk
- confidence

## Why it matters

Rankings help users find the best opportunities from a large universe.

## Integrations

Depends on:

- Market Data
- Analytics
- Universe/Watchlists

Feeds:

- Portfolio Construction
- Analyst research
- Reports
- Trading candidates
""")

    with st.expander("📈 Stock Dashboard"):
        st.markdown("""
## Purpose

Single-stock research view.

## What it should show

- price history
- technicals
- fundamentals
- analytics summary
- earnings/events
- sentiment
- rankings
- forecasts

## Why it matters

Use this page after a stock appears in rankings, screener, or alerts.

## Integrations

Uses:

- market data
- analytics
- earnings
- sentiment
- forecasts
- reports
""")

    with st.expander("🧾 Earnings + Transcript AI Q&A"):
        st.markdown("""
## Purpose

Analyzes earnings events and earnings call transcripts.

## What it does

- loads earnings data
- fetches transcripts from supported providers
- stores transcripts
- lets users ask AI questions
- compares multiple companies
- supports manual transcript upload

## Transcript workflow

1. Enter symbol.
2. Load latest transcript.
3. Confirm transcript is cached.
4. Ask a question.
5. Review answer and citations.

## AI providers

The app can use:

```text
OpenAI
Anthropic / Claude
```

depending on configured keys.

## Transcript providers

The app can support provider abstraction such as:

```text
ROIC.ai
Quartr
Manual Upload
Legacy/Fallback Providers
```

## Example questions

```text
What did management say about revenue growth?
What were the main drivers of margin expansion?
What guidance did they provide?
What risks were mentioned?
How did management describe demand?
```

## Integrations

Feeds:

- analyst research
- reports
- comparison tables
- stock dashboard
- portfolio review
""")

    with st.expander("🔮 Forecasting"):
        st.markdown("""
## Purpose

Provides forward-looking analysis based on historical data and model logic.

## What it can support

- price forecasting
- trend projections
- scenario analysis
- risk estimates
- signal forecasts

## How it integrates

Forecasting depends on:

- market data
- price history
- analytics
- sometimes sentiment or macro data

Forecasting can feed:

- portfolio construction
- trading candidates
- reports
""")

    with st.expander("🧪 Strategy Lab / Backtesting"):
        st.markdown("""
## Purpose

Tests strategies before using them.

## What it does

- simulates historical performance
- tests ranking-based portfolios
- evaluates rebalance frequency
- measures risk and drawdown
- compares strategy configurations

## Common controls

- lookback period
- rebalance frequency
- top N holdings
- score threshold
- drawdown rules
- transaction cost assumptions

## Integrations

Uses:

- price history
- analytics scores
- rankings
- portfolio construction rules
""")

    with st.expander("🏗️ Portfolio Construction"):
        st.markdown("""
## Purpose

Builds portfolios from ranked candidates.

## What it does

- selects holdings
- assigns weights
- enforces concentration controls
- manages sector exposure
- applies cash reserve
- can use analytics/ranking inputs

## Common controls

- portfolio size
- max weight
- min weight
- sector cap
- cash reserve
- ranking basis

## Integrations

Depends on:

- analytics
- rankings
- universe/watchlists
- market data

Feeds:

- portfolio analytics
- deployment
- trading
- reports
""")

    with st.expander("💼 Portfolio Analytics / Client Dashboard / AI Portfolio Center"):
        st.markdown("""
## Purpose

Tracks portfolios and helps evaluate performance.

## What it shows

- holdings
- cash
- equity
- PnL
- NAV
- exposure
- risk
- portfolio drift
- performance trends

## AI Portfolio Center

Adds higher-level decision support for portfolios.

May help with:

- risk review
- allocation review
- replacement candidates
- portfolio summary
- optimization suggestions

## Integrations

Uses:

- portfolio holdings
- market data
- analytics
- rankings
- reports
""")

    with st.expander("💸 Trading / Deployment"):
        st.markdown("""
## Purpose

Supports trade workflow and portfolio deployment.

## What it may include

- paper trading
- order sizing
- buy/sell workflows
- cash tracking
- position tracking
- deployment from model portfolios

## Important note

Always confirm whether the app is running in paper/simulated mode or connected to live execution.

## Integrations

Trading depends on:

- portfolios
- prices
- rankings
- alerts
- risk controls
""")

    with st.expander("⚡ Intraday"):
        st.markdown("""
## Purpose

Short-term market monitoring.

## Useful for

- traders
- active monitoring
- short-term momentum
- market-open activity
- identifying active names

## Integrations

Uses market data and can support alerts, scanner, and trading workflows.
""")

    with st.expander("📊 Options Flow"):
        st.markdown("""
## Purpose

Tracks options activity.

## Useful for

- unusual options volume
- directional clues
- sentiment confirmation
- possible institutional activity

## How to use it

Use options flow as one input, not as a standalone decision.

Combine with:

- price trend
- volume
- rankings
- sentiment
- upcoming catalysts
""")

    with st.expander("🚨 Alerts / Scanner"):
        st.markdown("""
## Purpose

Surfaces conditions that need attention.

## Alert examples

- price crosses level
- RSI threshold
- volume spike
- breakout
- ranking change
- portfolio risk condition

## Scanner examples

- momentum movers
- oversold names
- high-volume names
- technical setups

## Integrations

Uses:

- market data
- analytics
- watchlists
- portfolios
- intraday data
""")

    with st.expander("🗞️ Sentiment"):
        st.markdown("""
## Purpose

Adds qualitative market context.

## What it may include

- news sentiment
- social sentiment
- company sentiment
- market tone

## How to use it

Sentiment should confirm or challenge what the data says.

Example:

```text
High ranking + positive sentiment = stronger confirmation
High ranking + negative sentiment = review risk carefully
```

## Integrations

Can support:

- analyst research
- stock dashboard
- rankings
- reports
- alerts
""")

    with st.expander("📤 Export"):
        st.markdown("""
## Purpose

Exports app data for review or external use.

## What can be exported

- rankings
- analytics tables
- screen results
- portfolio data
- research outputs
- report data

## Why it matters

Exports let users move data into spreadsheets, presentations, internal reports, and client materials.
""")

    with st.expander("📄 Reports"):
        st.markdown("""
## Purpose

Creates readable reports from app data.

## Report uses

- research summaries
- portfolio reviews
- client reporting
- internal documentation
- investment committee support

## Integrations

Reports can pull from:

- analytics
- rankings
- portfolios
- earnings
- sentiment
- market dashboard
""")

    with st.expander("👥 Team / Collaboration"):
        st.markdown("""
## Purpose

Supports teamwork across users.

## What it can support

- shared notes
- shared research
- assignments
- collaboration records
- analyst/trader workflows

## Integrations

Can connect to:

- analyst notes
- reports
- portfolios
- watchlists
- exports
""")

    with st.expander("🤖 Agent / AI Assistant Modules"):
        st.markdown("""
## Purpose

Adds AI-assisted workflow support.

## Possible uses

- summarize research
- assist analyst workflows
- review portfolio context
- explain signals
- generate report text
- help with multi-step workflows

## Integrations

Can use outputs from:

- analytics
- rankings
- earnings transcripts
- reports
- portfolios
- sentiment
""")

    with st.expander("🏛️ Analytics Fabric / Runtime / Diagnostics / Self-Healing"):
        st.markdown("""
## Purpose

The Analytics Fabric is the operational layer behind advanced analytics execution.

It supports:

- forecasting
- optimization
- execution planning
- orchestration
- runtime control
- command processing
- diagnostics
- self-healing

## Diagnostic Engine

Evaluates component health and produces:

- health score
- risk score
- component findings
- anomalies
- predicted failures
- recommendations

## Self-Healing Engine

Consumes diagnostics and creates recovery plans.

It can:

- generate healing plans
- dry-run recovery
- require approvals
- execute allowed recovery actions
- track recovery history
- export healing reports

## Why it matters

This layer moves the platform from basic analytics into a more autonomous operating system for research workflows.

## Integrations

Connects to:

- forecasting
- optimizer
- execution planner
- orchestrator
- runtime controller
- supervisor
- command processor
- control plane
- dashboards
""")

    with st.expander("🔐 Admin / Tenant Admin"):
        st.markdown("""
## Purpose

Controls application administration.

## Admin tasks

- manage users
- manage tenant configuration
- review app health
- verify provider keys
- check refresh status
- enable/disable features when available
- troubleshoot errors

## Tenant Admin tasks

- manage tenant-level users
- configure tenant settings
- monitor tenant data
- review tenant-specific usage

## Integrations

Admin settings impact:

- user access
- provider access
- feature visibility
- operational dashboards
""")

    # ================================================================
    # TROUBLESHOOTING
    # ================================================================

    with st.expander("🛠️ Troubleshooting", expanded=True):
        st.markdown("""
## Rankings are empty

Likely causes:

- market data has not been refreshed
- analytics has not been run
- universe/watchlist is empty
- provider failed
- data is stale

Fix:

1. Refresh market data.
2. Run analytics.
3. Check rankings again.

## Market Data Refresh is slow

Causes:

- refreshing thousands of symbols
- provider throttling
- provider fallback
- API rate limits

Fix:

- test with a small limit first
- review provider health
- verify failover is working
- avoid repeated full refreshes during rate limits

## Polygon / Massive rate limit

If you see:

```text
maximum requests per minute
```

Polygon is throttled. The app should move to the next provider.

## AI Q&A says transcript is too short

The cached transcript may be incomplete.

Fix:

- force provider refresh
- load transcript again
- manually paste a full transcript
- verify character count is thousands, not dozens

## Earnings transcript provider returns nothing

Possible causes:

- missing ROIC/Quartr key
- provider endpoint issue
- provider has no transcript
- invalid symbol
- transcript requires year/quarter

Fix:

- check provider status
- verify API key
- try manual upload

## Analytics did not update

Possible causes:

- `updated_symbols` empty
- market data failed
- database write failed
- analytics dependency missing

Fix:

- check refresh result
- verify price_history updated
- rerun analytics manually

## GitHub / remote site not updating

Most common cause:

```text
files modified but not staged
```

Use:

```bash
git status
git add .
git commit -m "Update app"
git push origin main
```

Make sure the commit says more than `1 file changed` if many files were edited.
""")

    with st.expander("🎚️ Common Controls / Glossary"):
        st.markdown("""
## Top N

Number of results shown.

## Limit symbols

Number of symbols processed.

```text
0 = all
```

## Batch size

How many symbols are processed in a chunk.

Lower is safer. Higher is faster but may hit rate limits.

## Lookback

Historical time window.

## Threshold

Minimum condition required.

## Weight

Importance assigned to a factor.

## Force refresh

Bypasses cached data and requests fresh data.

## Confidence

Filters results based on data quality or model certainty.

## Sector cap

Maximum allocation to one sector.

## Max weight

Maximum portfolio allocation to one holding.

## Cash reserve

Amount of capital held uninvested.
""")

    with st.expander("✅ Recommended Operating Rules"):
        st.markdown("""
1. Always refresh market data before analytics.
2. Always run analytics before rankings.
3. Use small symbol limits when testing new provider changes.
4. Use full refresh after provider failover is verified.
5. Use rankings as a starting point, not the only decision.
6. Use transcript AI for management commentary, not guaranteed forecasts.
7. Use options flow and sentiment as confirmation signals.
8. Export reports after data and analytics are current.
9. Check provider health if refresh slows or fails.
10. Check Git status from the repository root before pushing updates.
""")

    st.success("✅ Help guide updated. Start with Market Data, then Analytics, then Rankings, then Portfolio/Trading/Reports.")
