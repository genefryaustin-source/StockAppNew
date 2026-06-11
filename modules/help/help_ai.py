# modules/help/help_ai.py

import streamlit as st


def render_help_ai():

    st.header("🤖 AI Features")

    st.markdown("""
The platform supports multiple AI systems.

## Earnings Transcript AI

Ask questions about:

- Guidance
- Revenue
- Margins
- Risks
- Competition

## Research Copilot

Provides:

- Company Summaries
- Research Notes
- Report Drafting
- Opportunity Analysis

## Crypto AI

Supports:

- Coin Analysis
- Portfolio Advice
- Trend Detection
- Risk Scanning

## IPO Intelligence AI

Generates:

- IPO Assessments
- Probability Scoring
- Opportunity Scores
- Timeline Estimates

## AI Providers

Supported:

- OpenAI
- Anthropic Claude
""")