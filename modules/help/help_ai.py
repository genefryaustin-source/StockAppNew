import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_ai_help():
    st.title("🤖 AI Help — Rankings, Scanner, Forecasting, Agent, Research")
    _section("AI module overview", """
The AI layer supports ranking interpretation, research summaries, portfolio review, transcript Q&A, forecasting context, scanner explanation, and report generation.

AI outputs should be treated as decision support and reviewed against source data.
""", True)
    _section("AI Rankings", """
AI Rankings combine quantitative signals into a more interpretable priority list. Inputs may include value, growth, quality, momentum, risk, sentiment, and confidence.

Use AI Rankings after Market Data and Analytics are current.
""")
    _section("AI Scanner", """
AI Scanner can help explain why names appear interesting: momentum changes, alerts, unusual behavior, sentiment shifts, or ranking changes.
""")
    _section("AI Forecast", """
Forecasting tools can project trends, scenarios, or directional risk. Forecast outputs are not guarantees; they should be used with market data, valuation, and risk controls.
""")
    _section("AI Agent", """
The AI Agent can assist with multi-step workflows such as summarizing a stock, reviewing portfolio risk, drafting report language, or explaining analytics output.
""")
    _section("Transcript AI Q&A", """
Use transcript AI to ask questions about earnings calls:

```text
What did management say about margins?
What risks were discussed?
What guidance was provided?
How did analysts challenge management?
```

If answers look shallow, verify transcript length and provider status.
""", True)
    _section("Best practices", """
- Use AI after data is current.
- Ask specific questions.
- Verify outputs against source data.
- Do not use AI as the sole reason for trades.
- Use AI summaries for workflow speed, not final authority.
""")

def render_help():
    render_ai_help()
