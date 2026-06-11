import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_options_help():
    st.title("📈 Options Help — Flow, Strategies, Risk, Greeks")
    _section("Options workflow overview", """
Options tools should be used as confirmation and risk-management tools:

```text
Market Context
    ↓
Underlying Stock Research
    ↓
Options Flow / Chain / Strategy Builder
    ↓
Risk / Greeks / Portfolio Impact
```
""", True)
    _section("📊 Options Flow", """
## Purpose
Tracks notable options activity and unusual flow.

## Useful signals
- Unusual volume.
- Large trades.
- Sweeps or blocks.
- Directional call/put activity.
- Activity around earnings or catalysts.

Use options flow as one input, not as a standalone trade signal.
""")
    _section("🧱 Strategy Builder", """
## Common strategy families
- Long calls/puts.
- Covered calls.
- Cash secured puts.
- Vertical spreads.
- Iron condors.
- Butterflies.
- Wheel strategy.

## Review before deployment
- Max loss.
- Max gain.
- Breakeven.
- Probability assumptions.
- Expiration risk.
- Assignment risk.
""", True)
    _section("🔬 Greeks and Risk", """
## Greeks to monitor
- Delta: directional exposure.
- Gamma: rate of delta change.
- Theta: time decay.
- Vega: volatility sensitivity.
- Rho: interest rate sensitivity.

## Portfolio-level risks
Options should be reviewed for concentration, expiration clustering, assignment risk, and underlying exposure.
""")
    _section("Daily options routine", """
1. Start with Market Overview.
2. Review underlying ranking and trend.
3. Check upcoming earnings or catalysts.
4. Review Options Flow.
5. Build strategy candidates.
6. Review Greeks and max risk.
7. Document trade thesis.
8. Monitor alerts and portfolio exposure.
""")
    _section("Troubleshooting options pages", """
## Options data empty
Check provider configuration, symbol validity, expiration availability, and API limits.

## Flow missing
Confirm options flow provider is configured and the selected symbol has enough activity.

## Greeks unavailable
Confirm chain data includes IV and contract metadata.
""")

def render_help():
    render_options_help()
