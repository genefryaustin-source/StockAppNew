import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_api_providers_help():
    st.title("🔌 API Providers Help — Market Data, AI, Transcripts")
    _section("Provider overview", """
The platform avoids reliance on a single provider by using failover, caching, and provider health checks.
""", True)
    _section("Market data provider chain", """
Typical failover order:

```text
Polygon / Massive
MarketData.app
Finnhub
Alpha Vantage
TwelveData
Yahoo fallback
```

A provider can fail because of rate limits, missing symbol coverage, timeout, invalid key, endpoint outage, or returned empty data.
""", True)
    _section("Provider setup checklist", """
For each provider:
1. Add key to Streamlit secrets.
2. Confirm code reads the correct secret name.
3. Test one symbol.
4. Test a small batch.
5. Confirm cache writes.
6. Confirm failover works.
""")
    _section("AI providers", """
AI providers can include OpenAI and Anthropic. They may power transcript Q&A, report drafting, research summaries, AI rankings, AI portfolio review, and agent workflows.

Never hardcode API keys in source files.
""")
    _section("Transcript providers", """
Transcript providers may include ROIC, Quartr, manual upload, and legacy providers.

If transcript AI returns shallow answers, check transcript length and provider output before blaming the model.
""")
    _section("Troubleshooting provider problems", """
## Rate limits
Reduce batch size, use caching, or fail over to another provider.

## Invalid key
Check Streamlit Cloud secrets and local secrets.

## Data stale
Clear provider cache or force refresh.

## Only Yahoo fallback works
Primary providers may be disabled, missing keys, rate limited, or failing health checks.
""", True)

def render_help():
    render_api_providers_help()
