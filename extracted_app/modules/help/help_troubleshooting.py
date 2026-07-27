import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_troubleshooting_help():
    st.title("🛠️ Troubleshooting Runbook")
    _section("Login and auth issues", """
## Login successful but page does not advance
The login function likely saved `st.session_state['user']` but did not trigger a rerun, or app.py stopped after rendering login.

## DuplicateElementId on Email Address
The login form rendered twice in the same Streamlit run. Ensure auth gate calls `render_login(db)` once and then `st.stop()`.

## AttributeError: user.get
The app continued past auth gate with `user = None`. Guard user before any `user.get(...)` calls.

## Invalid credentials
Check password hash, user is_active, tenant/user seed records, and the correct database URL.
""", True)
    _section("Database and Neon issues", """
## Confirm correct database
```sql
SELECT current_database();
SELECT current_user;
SELECT COUNT(*) FROM tenants;
SELECT COUNT(*) FROM users;
```

## Inspect tables
```sql
SELECT id, name, is_active, created_at FROM tenants;
SELECT id, tenant_id, email, role, is_active, created_at FROM users;
```

## Bootstrap failure: is_active null
Tenants and users require `is_active = TRUE` because the schema has no default.
""", True)
    _section("Market data issues", """
## Market Data Refresh is slow
Likely causes: full universe size, provider throttling, failover delay, API limits.

## Fix
Test with 25/50/100 symbols, review provider health, verify failover, then full refresh.
""")
    _section("Rankings and analytics empty", """
Likely causes:
- Market data has not been refreshed.
- Analytics has not been run.
- Universe/watchlist is empty.
- Provider failed.
- Analytics cache is stale.

Fix: refresh market data, run analytics, then check rankings.
""", True)
    _section("Earnings transcript issues", """
## Transcript too short
Provider returned incomplete text. Force refresh or manual upload.

## Provider returns nothing
Check provider key, symbol, year/quarter, endpoint status, and availability.
""")
    _section("GitHub / deployment issues", """
## Remote missing files
Run:
```bash
git status
git add -A
git commit -m "Add remaining files"
git push origin main
```

## Secrets accidentally at risk
Confirm `.streamlit/secrets.toml`, `.env`, local databases, cache folders, and `.venv` are ignored.

## Streamlit Cloud not updating
Confirm branch, commit hash, app logs, and dependency install status.
""", True)
    _section("Cache corruption", """
If diskcache reports `database disk image is malformed`, delete local market data cache and let it rebuild.

On Windows:
```cmd
rmdir /S /Q "%LOCALAPPDATA%\\EquityResearchTerminal\\market_data_cache"
```
""")
    _section("Common controls glossary", """
- Top N: Number of results shown.
- Limit symbols: Number of symbols processed. `0 = all`.
- Batch size: How many symbols are processed per chunk.
- Lookback: Historical window.
- Force refresh: Ignore cache and request fresh data.
- Confidence: Data/model certainty filter.
- Sector cap: Maximum allocation to one sector.
- Cash reserve: Capital held uninvested.
""")

def render_help():
    render_troubleshooting_help()
