import streamlit as st

def render_help():

    st.title("📘 Equities Research Terminal — User Guide")

    st.markdown("""
Welcome to the Equities Research Terminal.

This guide walks you through **how to use the platform step-by-step**, including:
- correct workflow order
- dependencies between sections
- explanation of sliders and controls
- troubleshooting common issues

---

## 🚀 QUICK START (READ THIS FIRST)

1. Create or select a **Watchlist or Universe**
2. Ensure **market data is loading**
3. Run **Analytics**
4. Go to **Rankings / AI Ranking Engine**
5. Use **Portfolio Construction**
6. Monitor via **Portfolio Analytics**
7. Execute via **Trading (if enabled)**

⚠️ Many sections will NOT work until Analytics has been run.
""")

    # --------------------------------------------------
    # ORDER OF OPERATIONS
    # --------------------------------------------------

    with st.expander("🧭 Recommended Order of Operations", expanded=True):
        st.markdown("""
### FIRST-TIME SETUP FLOW

1. Open app and confirm configuration (API keys, DB, data)
2. Create/select Watchlist or Universe
3. Load market data (prices + history)
4. Run Analytics (**critical step**)
5. Review Rankings / AI Ranking
6. Build portfolio
7. Track performance
8. Use trading / alerts

---

### WHY ANALYTICS COMES FIRST

Analytics computes:
- valuation metrics
- growth/quality scores
- momentum indicators
- risk metrics
- composite scores

Without this:
- Rankings will be empty
- Portfolio Construction will not work
- AI Ranking will fail
""")

    # --------------------------------------------------
    # MARKET OVERVIEW
    # --------------------------------------------------

    with st.expander("📊 Market Overview"):
        st.markdown("""
**Purpose:** Understand overall market conditions.

Use this page to:
- assess market direction
- view sector performance
- identify top movers

### Controls

**Timeframe**
- Short = recent moves
- Long = trend context

**Top N**
- Number of stocks/sectors displayed

**Volume Filter**
- Higher values remove illiquid names
""")

    # --------------------------------------------------
    # WATCHLISTS
    # --------------------------------------------------

    with st.expander("📋 Watchlists"):
        st.markdown("""
**Purpose:** Store and track selected stocks.

Use to:
- organize tickers
- build research groups
- prepare for analytics

### Workflow
1. Create watchlist
2. Add symbols
3. Run analytics
4. Review rankings

### Controls

**Symbol Input**
- Add individual or multiple tickers

**Top N**
- Limits display size
""")

    # --------------------------------------------------
    # SCREENER
    # --------------------------------------------------

    with st.expander("🔍 Screener"):
        st.markdown("""
**Purpose:** Filter stocks by criteria.

### Common Filters

**Market Cap**
- Larger = safer, more liquid
- Smaller = higher risk, higher potential

**Price**
- Filters penny stocks or expensive names

**Volume**
- Ensures tradability

**P/E**
- Lower = cheaper
- Higher = growth premium

**P/S**
- Useful when earnings are inconsistent

**EV/EBITDA**
- Operating valuation

**RSI**
- <30 = oversold
- >70 = overbought

**Revenue Growth**
- Higher = faster-growing companies

### Workflow
1. Set filters
2. Run screener
3. Save results
4. Run analytics
""")

    # --------------------------------------------------
    # ANALYTICS
    # --------------------------------------------------

    with st.expander("⚙️ Analytics (MOST IMPORTANT)", expanded=True):
        st.markdown("""
This is the **core engine** of the platform.

### What it computes:
- valuation (P/E, P/S, EV/EBITDA)
- growth (Revenue CAGR)
- margins (gross, operating, FCF)
- technicals (RSI, SMA50/200)
- risk (volatility, drawdown)
- scores (quality, growth, value, momentum)
- composite ranking

---

### REQUIRED BEFORE:
- Rankings
- AI Ranking
- Portfolio Construction
- Strategy Engine

---

### Controls

**Batch Size**
- Lower = safer
- Higher = faster but risk of API limits

**Max API Calls**
- Limits external requests

**Min History Rows**
- Minimum price data required

**Lookback**
- Longer = more stable metrics

**Force Refresh**
- Bypasses cache
""")

    # --------------------------------------------------
    # RANKINGS
    # --------------------------------------------------

    with st.expander("🏆 Rankings"):
        st.markdown("""
Ranks stocks based on analytics.

### Requires:
Analytics must be run first.

### Controls

**Ranking Basis**
- Choose factor (value, momentum, etc.)

**Top N**
- Number of stocks shown

**Confidence Threshold**
- Filters unreliable data

**Sector Filter**
- Narrow results
""")

    # --------------------------------------------------
    # AI RANKING
    # --------------------------------------------------

    with st.expander("🤖 AI Ranking Engine"):
        st.markdown("""
Combines factors into smarter ranking.

### Controls

**Factor Weights**
- Adjust importance of:
  - quality
  - growth
  - value
  - momentum

**Confidence Threshold**
- Filters incomplete data

**Top N**
- Final results count
""")

    # --------------------------------------------------
    # UNIVERSE BUILDER
    # --------------------------------------------------

    with st.expander("🌐 Universe Builder"):
        st.markdown("""
Creates stock universes.

### Controls

**Market Cap**
- Filters size

**Sector**
- Focus area

**Liquidity**
- Removes thin stocks

**Max Symbols**
- Limits universe size
""")

    # --------------------------------------------------
    # PORTFOLIO CONSTRUCTION
    # --------------------------------------------------

    with st.expander("🏗️ Portfolio Construction"):
        st.markdown("""
Build portfolios from ranked stocks.

### Requires:
Analytics must be run.

### Controls

**Portfolio Size**
- Number of holdings

**Max Weight**
- Prevents concentration

**Min Weight**
- Removes tiny allocations

**Sector Cap**
- Limits exposure

**Cash Reserve**
- Keeps capital uninvested
""")

    # --------------------------------------------------
    # PORTFOLIO ANALYTICS
    # --------------------------------------------------

    with st.expander("📈 Portfolio Analytics"):
        st.markdown("""
Monitor performance.

### Shows:
- cash
- equity
- PnL
- holdings
- risk

### Controls

**Date Range**
- Historical view

**Holdings Limit**
- Number of positions shown
""")

    # --------------------------------------------------
    # TRADING
    # --------------------------------------------------

    with st.expander("💼 Trading"):
        st.markdown("""
Execute trades (paper or live).

### Controls

**Order Size**
- Position size

**Limit Price**
- Entry control

**Transaction Cost**
- Simulated slippage

**Stop / Target**
- Risk management
""")

    # --------------------------------------------------
    # BACKTESTING
    # --------------------------------------------------

    with st.expander("🧪 Strategy Backtesting"):
        st.markdown("""
Test strategies on historical data.

### Controls

**Lookback**
- Data window

**Rebalance Frequency**
- How often to update

**Top N**
- Holdings count

**Score Threshold**
- Minimum ranking

**Drawdown Limit**
- Risk control
""")

    # --------------------------------------------------
    # ALERTS
    # --------------------------------------------------

    with st.expander("🚨 Alerts"):
        st.markdown("""
Track conditions.

### Examples:
- price breakout
- RSI levels
- volume spikes

### Controls

**Threshold**
- Trigger level

**Sensitivity**
- Signal frequency
""")

    # --------------------------------------------------
    # TROUBLESHOOTING
    # --------------------------------------------------

    with st.expander("🛠️ Troubleshooting", expanded=True):
        st.markdown("""
### Analytics returned no result
- Missing price data
- Not enough history
- API failure

### No API key found
- Check secrets/config

### Rankings empty
- Run Analytics first

### Portfolio page blank
- Missing analytics or symbols

### DB errors
- Check schema + restart session
""")

    # --------------------------------------------------
    # SLIDER GLOSSARY
    # --------------------------------------------------

    with st.expander("🎚️ Slider Glossary"):
        st.markdown("""
**Top N**
- Number of results

**Threshold**
- Minimum condition required

**Lookback**
- Historical window

**Batch Size**
- Processing chunk size

**Weight**
- Factor importance

**Cap**
- Maximum limit

**Confidence**
- Data reliability filter
""")

    st.success("✅ You are ready to use the Equities Research Terminal!")