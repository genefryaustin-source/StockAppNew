import streamlit as st

def render_help_troubleshooting():

    st.header("❓ Troubleshooting")

    st.markdown("""
### News Not Loading

Check:

- Finnhub API Key
- Polygon API Key
- Provider Health

### AI Errors

Check:

- OPENAI_API_KEY
- ANTHROPIC_API_KEY

### SEC Discovery Issues

Verify:

- SEC User Agent
- Internet Connectivity

### Missing Data

Run:

- Refresh Market Data
- Refresh IPO Calendar
- Refresh SEC Discovery

### Provider Failures

Review:

- Provider Health Dashboard
- Runtime Logs
- Diagnostics Center
""")