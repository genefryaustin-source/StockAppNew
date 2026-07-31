import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_forex_help():
    st.title("💱 Forex Help — Currency Trading, AI Analysis, Risk")

    _section("🔰 New to forex? Start here", """
### What is "forex," in plain terms?

Forex (short for "foreign exchange") is the buying and selling of one
currency against another — for example, trading US Dollars for Euros. When
people say "trading EUR/USD," they mean betting on whether the Euro will get
stronger or weaker compared to the US Dollar.

Forex is a genuinely advanced area. **If you're brand new to investing, we'd
recommend getting comfortable with the Stock Research and Portfolio sections
first**, since currency trading uses borrowed money (leverage) by default in
most real-world settings, which means both gains and losses happen faster
than with stocks.

### The absolute basics

- **Currency pair** — always written as two currencies together, like
  `EUR/USD` or `GBP/JPY`. The first currency is what you're buying or
  selling; the second is what you're pricing it in.
- **Pip** — the smallest standard price move for a currency pair. You don't
  need to calculate this yourself; the app does it for you.
- **Long / Short** — "going long" means betting a currency will get
  stronger; "going short" means betting it will get weaker.
- **Paper vs. Live** — exactly the same distinction as everywhere else in
  this app. Stay in Paper mode until every workspace below makes sense to
  you.

### Your first steps in the Forex terminal

1. Open the **Overview** tab first — it gives you the big picture (account
   value, open positions, recent performance) without overwhelming detail.
2. Read the **AI Briefing** tab — it's written in plain language and
   summarizes what's happening in the market right now.
3. Look at **Live Market** to see real prices for major currency pairs.
4. Before placing any trade, check **Risk** to understand what a trade could
   cost you if it goes against you.
5. Only place practice trades (Paper mode) until you're confident you
   understand a workspace before moving to the next one.
""", True)

    _section("🗺️ The 13 workspace tabs, one at a time", """
The Forex terminal is organized into tabs across the top. Here's what each
one is for and when to use it:

**Overview** — Your starting point. Account value, open positions summary,
and recent performance at a glance. Check this first, every session.

**Positions** — Every currency pair you currently hold, with live profit/loss.
This is where you close a position (click "Close Position" next to any row).

**Orders** — Pending and past orders. If you placed a trade that hasn't
filled yet, it shows here. You can cancel pending orders from this tab.

**Risk** — Stress testing and a risk heat map. Shows how your account would
be affected by specific market shocks (e.g., "what if the Dollar jumps 1%
tomorrow?"). Check this before adding new positions, not just after.

**Performance** — Your historical results: win rate, average gain/loss, and
trends over time. Useful for understanding your own patterns, good or bad.

**Journal** — A place to record your reasoning for trades. Professional
traders use journals to learn from both wins and losses — writing down *why*
you made a trade is often more valuable than the trade's outcome.

**AI Briefing** — A plain-language daily summary of market conditions,
written to be read quickly.

**AI Trade Setup** — AI-generated trade ideas with reasoning, plus any active
alerts. These are suggestions to evaluate, not instructions to follow blindly
— always apply your own judgment.

**AI Command Center** — More advanced AI tools, including an autonomous
trading cycle option. This picks and can execute a trade automatically if you
enable it — **new users should leave this off** and rely on AI Trade Setup's
suggestions instead, which you approve manually.

**Live Market** — Real-time prices, currency strength across major
currencies, the macro environment, a live price chart, a trade ticket to
place orders, an economic calendar, and central bank event tracking. This is
the most detail-dense tab — it's fine to focus on just the price chart and
trade ticket at first.

**Exposure** — How much of your account is riding on each currency, not just
each pair. Useful for spotting hidden concentration (e.g., being long the
Euro across three different pairs without realizing it).

**Execution Quality** — How well your orders are actually filling (speed,
slippage). More relevant once you're placing real trades regularly.

**Quotes** — Raw, real-time price quotes for currency pairs, without extra
analysis layered on top.

### Daily forex routine

1. Check **Overview** and **AI Briefing** for the current state of things.
2. Check the **Economic Calendar** and **Central Bank Events** (inside Live
   Market) for anything scheduled today that could move your pairs.
3. Review **Risk** before making any changes to your positions.
4. Review **Exposure** to confirm you're not more concentrated in one
   currency than you intended.
5. Log any trades you make in the **Journal**, including your reasoning.
""", True)

    _section("⚠️ Risk warning", """
Forex trading commonly involves leverage, meaning a small market move can
produce a disproportionately large gain or loss relative to what you put in.
This is different from buying a stock outright, where your loss is capped at
what you paid. Always confirm whether you're in Paper or Live mode, and never
risk money in Live mode that you aren't prepared to lose.
""")

    _section("🔧 Troubleshooting", """
## Prices look stale or a tab is blank
Look for a refresh control on that tab, or check the API Providers help
section to confirm a forex data provider is configured.

## AI Command Center rejects a trade
This usually means the portfolio/account context couldn't be loaded — try
reopening the tab, or check that you have an active paper or live account
configured.

## A position I closed still shows as open
Revisit the Orders tab — reconciliation with the broker can take a moment
after a trade fills.
""")