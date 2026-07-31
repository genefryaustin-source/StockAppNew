import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_daily_checklist_help():

    st.title("✅ Daily Checklist")

    st.caption(
        "A simple routine to run through each day, whether you're brand new "
        "or you've been doing this for years. Pick the checklist that matches "
        "what you're using the app for -- you don't need to do all of them."
    )

    _section("🔰 New / casual user — 5 minutes a day", """
If you're just building the habit of checking in on your investments, this is
all you need:

- [ ] Open your **Watchlist** and see if anything moved a lot (up or down).
- [ ] For anything that moved a lot, open its **Stock Dashboard** (or Coin
      Detail, for crypto) and read the summary to understand *why*.
- [ ] Check your **Portfolio** (even if it's paper/practice) to see your
      current value and whether anything needs attention.
- [ ] Skim any **AI Briefing** or daily summary the app offers you — it's
      written to be read in under a minute.
- [ ] If nothing needs a decision today, that's a completely normal outcome.
      You don't have to act every day.

That's the whole routine. Consistency matters more than depth when you're
starting out.
""", True)

    _section("📊 Stock & equity research routine", """
1. [ ] **Refresh market data** for your universe/watchlist if it's stale
       (there's usually a visible "last updated" time or a Refresh button).
2. [ ] **Re-run Analytics** after refreshing data — rankings and scores are
       only as good as the latest analytics pass.
3. [ ] **Check Rankings** for any new names entering your top tier, or
       existing holdings dropping out of it.
4. [ ] **Review Alerts/Scanner** for anything that crossed a threshold you
       care about.
5. [ ] **Check upcoming Earnings** for anything in your watchlist or
       portfolio this week.
6. [ ] **Review Sentiment/News** for anything with unusual activity.
7. [ ] Document anything you decide to act on before moving to Portfolio.
""")

    _section("💼 Portfolio routine", """
1. [ ] Confirm market data and analytics are current before reviewing
       (stale inputs make Portfolio Analytics misleading).
2. [ ] Check **NAV, cash, and PnL** for anything unexpected.
3. [ ] Review **sector/position concentration** — has anything grown into an
       outsized share of the portfolio?
4. [ ] Check whether any holding's **ranking has dropped** significantly
       since you bought it.
5. [ ] Review **replacement candidates** if the AI Portfolio Center offers
       them.
6. [ ] Confirm you know whether you're in **Paper or Live** mode before
       placing any trade.
7. [ ] Generate/update a **Portfolio Report** if you're reporting to someone
       else (a client, a committee, or just your own records).
""")

    _section("⚡ Options routine", """
1. [ ] Start with **Market Overview** / underlying trend context.
2. [ ] Check **upcoming earnings or catalysts** for anything in your options
       watchlist — these dramatically change options risk.
3. [ ] Review **Options Flow** for unusual activity.
4. [ ] Check **Greeks and portfolio-level exposure** (Delta, Gamma, Theta,
       Vega) — are you more exposed than you intended?
5. [ ] Review **expiration risk** — anything expiring soon that needs a
       decision (roll, close, let expire)?
6. [ ] Review **assignment risk** on any short positions.
7. [ ] If you use the Institutional workspaces (CIO Dashboard, Trade
       Selection, Risk Rebalancing), refresh them **after** market data is
       current, not before — they depend on the same underlying data.
""")

    _section("₿ Crypto routine", """
1. [ ] Refresh price/volume data for your crypto watchlist.
2. [ ] Check **Sentiment/News** for anything unusual — crypto reacts to news
       faster and harder than stocks.
3. [ ] If you use **Wallet Intelligence**, check for any newly-discovered
       flagged wallets since your last visit.
4. [ ] If you track **Exchange Intelligence**, glance at any registered
       reserve addresses for unexpected balance drops.
5. [ ] If you use **DeFi Intelligence**, check TVL trend on any protocols
       you're exposed to — sharp declines are a real warning sign.
6. [ ] Remember: crypto trades 24/7, including weekends. "Daily" here means
       "whenever you check in," not "only on weekdays."
""")

    _section("💱 Forex routine", """
1. [ ] Check the **Macro Environment** and **Currency Strength** panels for
       the current regime before looking at individual pairs.
2. [ ] Review your **Watchlist** pairs for significant moves.
3. [ ] Check the **Economic Calendar** and **Central Bank Events** for
       anything scheduled today that could move your pairs.
4. [ ] Review **open positions and exposure** (by currency and by pair) for
       concentration you didn't intend.
5. [ ] If you use **AI Trade Setup** or **AI Command Center**, review any new
       recommendations — remember these are suggestions for you to evaluate,
       not instructions to follow automatically.
""")

    _section("🛡️ Compliance / analyst routine", """
1. [ ] Review any new **Threat Actor / Scam Campaign** entries added by
       other analysts on your team.
2. [ ] Check the **Fraud Clusters** tab for newly-strengthened clusters
       (more members added since last review).
3. [ ] Confirm the **sanctions cache** refreshed recently (shown in Wallet
       Intelligence admin settings) — flag it for a manual refresh if it
       looks stale.
4. [ ] Review any **AI Investigation** reports generated since your last
       check-in, and confirm or override their risk-level assessment based
       on your own judgment.
5. [ ] Document your review, even when no action is needed — an empty daily
       review is still a record that the review happened.
""")