import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_help_getting_started():

    st.header("🚀 Getting Started")

    st.info(
        "New here? Start with **\"🔰 I've never done this before\"** below. "
        "Already know your way around investing? Jump to **\"For Analysts & Experienced Users\"** near the bottom."
    )

    # ==================================================================
    # BEGINNER TRACK
    # ==================================================================

    _section("🔰 I've never done this before — start here", """
### What this app actually does

This app helps you look into a company, a cryptocurrency, or an investment idea
**before** you decide whether to buy it, sell it, or leave it alone. Think of it
like a research assistant: it pulls together price history, news, and analysis
so you don't have to hunt for it yourself.

Nothing in this app requires you to already know how investing works. You'll
pick things up as you go.

### A few words you'll see everywhere

- **Ticker symbol** — the short code for a company on the stock market, like
  `AAPL` for Apple or `TSLA` for Tesla. You'll type these into search boxes
  throughout the app.
- **Watchlist** — a simple list of tickers you want to keep an eye on, like a
  favorites list.
- **Portfolio** — the list of things you actually own (or are pretending to
  own — see below).
- **Paper trading** — practicing with **fake money**. This is the safe way to
  learn. Nothing you do in paper trading affects real money, ever.
- **Live trading** — using **real money**. This app will always make it clear
  when you're about to do this, and most areas default to paper trading unless
  you deliberately turn it off.

### ⚠️ Before you touch anything: paper vs. live

Every trading screen in this app has a toggle or a clear label showing whether
you're in **📄 Paper** mode (practice, fake money) or **⚡ Live** mode (real
money). **If you are new to investing, stay in Paper mode until you are
completely comfortable with how a section works.** There is no rush, and
practicing costs nothing.

### Your first 15 minutes in this app

1. **Pick one thing you're curious about.** It can be a company you've heard
   of (like Apple, or your favorite grocery store's stock, if it's public) or
   a cryptocurrency you've heard mentioned in the news (like Bitcoin).
2. **Go to the Stock Research section** in the left sidebar (or Crypto, if you
   picked a cryptocurrency).
3. **Type the ticker symbol** into the search box. If you don't know it, typing
   the company's name usually helps you find it.
4. **Look at the Stock Dashboard.** You'll see a price chart, some basic
   numbers, and a summary. Don't worry about understanding every number yet —
   just get a feel for what's there.
5. **Read any AI summary or analysis text you find.** These are written in
   plain language and are meant to explain what the numbers mean, not just show
   them to you.
6. **Add it to a Watchlist.** Look for an "Add to Watchlist" button. This just
   saves it so you can find it again easily — it doesn't buy anything.

That's it. You've now researched your first investment idea. Nothing was
bought, nothing was risked, and you can repeat this for anything else you're
curious about.

### What to do next, in order

1. **Build a small watchlist** (3-5 things you're genuinely curious about) —
   see the Stock Research help section below.
2. **Explore the Stock Dashboard for each one** — get comfortable reading a
   price chart and a summary before anything else.
3. **Try Paper Trading** — practice buying and selling with fake money so the
   mechanics feel familiar. See the Portfolio help section.
4. **Only once you're comfortable, look at Options or Crypto Wallet
   Intelligence** — these are more advanced tools built for people who already
   understand the basics. There's no need to rush into them.

### If you get stuck

- A blank page or missing chart almost always means the data hasn't loaded yet
  — look for a "Refresh" button on that page.
- If something looks broken, check the **Troubleshooting** section in this
  Help Center before assuming you did something wrong.
- You cannot break anything by clicking around in Paper mode. Explore freely.
""", True)

    # ==================================================================
    # EXISTING (PRESERVED) HIGH-LEVEL WORKFLOW
    # ==================================================================

    _section("📊 For Analysts & Experienced Users", """
### Workflow

1. Login
2. Select module
3. Research securities
4. Build watchlists
5. Analyze opportunities
6. Generate reports

### Navigation

Use the left sidebar to access:

- Stock Dashboard
- Analytics
- IPO Intelligence
- Pre-IPO Intelligence
- Crypto
- Forex
- Options
- Portfolio
- Administration

### First Tasks

- Build a watchlist
- Review analytics
- Explore IPO opportunities
- Configure AI providers
""")