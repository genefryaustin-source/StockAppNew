"""
modules/options/options_ai_advisors.py

Seven AI/rule-based advisors for the expanded options workstation:
- AI Options Advisor
- AI Strategy Generator
- AI Trade Critic
- AI Risk Analyzer
- AI Wheel Assistant
- AI Covered Call Assistant
- AI Earnings Options Assistant

Uses existing modules.options.options_ai._claude when available.
Falls back to deterministic rule-based guidance when an AI key is unavailable.
"""

from __future__ import annotations

from typing import Any
import json
import math


def _call_ai(prompt: str, max_tokens: int = 700) -> str:
    try:
        from modules.options.options_ai import _claude
        ans = _claude(prompt, max_tokens=max_tokens)
        if ans and "API_KEY not found" not in ans and not ans.startswith("AI unavailable"):
            return ans
    except Exception:
        pass
    return ""


def _fallback(title: str, bullets: list[str]) -> str:
    return "### " + title + "\n\n" + "\n".join(f"- {b}" for b in bullets)


def ai_options_advisor(ticker: str, context: dict[str, Any]) -> str:
    prompt = f"""
You are an institutional options advisor. Review this symbol and options context.

Ticker: {ticker}
Context JSON:
{json.dumps(context, default=str)[:6000]}

Return:
1. Market posture
2. Best strategy family
3. Risk level
4. What to avoid
5. Next action checklist
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Options Advisor", [
        f"Review {ticker} only after confirming market data, IV, DTE, liquidity, and spread quality.",
        "Prefer defined-risk spreads when conviction is moderate or liquidity is uncertain.",
        "Avoid short premium into binary events unless assignment and gap risk are acceptable.",
    ])


def ai_strategy_generator(ticker: str, market_view: str, conviction: str, risk_tolerance: str, context: dict[str, Any]) -> str:
    prompt = f"""
Generate a specific options strategy recommendation.

Ticker: {ticker}
Market view: {market_view}
Conviction: {conviction}
Risk tolerance: {risk_tolerance}
Context:
{json.dumps(context, default=str)[:6000]}

Return a specific strategy, leg template, ideal DTE, entry conditions, exit rules, and risk notes.
"""
    ans = _call_ai(prompt)
    if ans:
        return ans
    if market_view.lower() == "bullish":
        strat = "Bull call spread for defined-risk upside; covered call if already holding shares."
    elif market_view.lower() == "bearish":
        strat = "Bear put spread for defined-risk downside; protective put if hedging stock."
    elif market_view.lower() == "neutral":
        strat = "Iron condor or covered call depending on whether the account owns shares."
    else:
        strat = "Long straddle/strangle only if expected move appears underpriced."
    return _fallback("AI Strategy Generator", [strat, "Use liquid strikes near high open interest.", "Size by max loss, not by contract count."])


def ai_trade_critic(ticker: str, strategy: str, legs: list[dict], summary: dict[str, Any]) -> str:
    prompt = f"""
Critique this options trade as a skeptical risk manager.

Ticker: {ticker}
Strategy: {strategy}
Legs: {json.dumps(legs, default=str)[:4000]}
Summary: {json.dumps(summary, default=str)[:4000]}

Return: approval level, 5 concerns, improvements, invalidation conditions.
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Trade Critic", [
        "Confirm bid/ask spreads are reasonable before entry.",
        "Check whether max loss is acceptable at portfolio level.",
        "Validate that the chosen DTE matches the thesis timeframe.",
        "Do not enter if liquidity or open interest is thin.",
    ])


def ai_risk_analyzer(ticker: str, positions: list[dict], greek_totals: dict[str, Any]) -> str:
    prompt = f"""
Analyze options portfolio risk.

Ticker: {ticker}
Positions: {json.dumps(positions, default=str)[:5000]}
Greek totals: {json.dumps(greek_totals, default=str)}

Return key exposures, risk flags, hedging ideas, and monitoring rules.
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Risk Analyzer", [
        f"Portfolio delta: {greek_totals.get('delta', 'unknown')}.",
        f"Theta exposure: {greek_totals.get('theta', 'unknown')}.",
        "Watch expiration clustering, short gamma, short vega, and assignment risk.",
    ])


def ai_wheel_assistant(ticker: str, put_candidates: list[dict], call_candidates: list[dict], account_context: dict[str, Any]) -> str:
    prompt = f"""
Act as a Wheel Strategy assistant.

Ticker: {ticker}
Cash-secured put candidates: {json.dumps(put_candidates, default=str)[:4500]}
Covered-call candidates: {json.dumps(call_candidates, default=str)[:4500]}
Account context: {json.dumps(account_context, default=str)[:2000]}

Return wheel plan, preferred strikes/DTE, assignment handling, and stop rules.
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Wheel Assistant", [
        "Sell cash-secured puts only at prices where assignment is acceptable.",
        "After assignment, sell covered calls above cost basis when possible.",
        "Avoid earnings weeks unless premium justifies gap risk.",
    ])


def ai_covered_call_assistant(ticker: str, shares: int, cost_basis: float, candidates: list[dict]) -> str:
    prompt = f"""
Analyze covered-call choices.

Ticker: {ticker}
Shares: {shares}
Cost basis: {cost_basis}
Candidates: {json.dumps(candidates, default=str)[:5000]}

Return preferred strike/DTE, income objective, assignment tradeoff, and roll guidance.
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Covered Call Assistant", [
        "Prefer OTM calls above cost basis unless intentionally exiting the stock.",
        "Balance income yield against assignment probability.",
        "Consider rolling when the option moves deep ITM and the stock thesis remains bullish.",
    ])


def ai_earnings_options_assistant(ticker: str, expected_move: dict[str, Any], iv_context: dict[str, Any], strategy_context: dict[str, Any]) -> str:
    prompt = f"""
Advise on earnings options setup.

Ticker: {ticker}
Expected move: {json.dumps(expected_move, default=str)}
IV context: {json.dumps(iv_context, default=str)}
Strategy context: {json.dumps(strategy_context, default=str)}

Return: avoid/trade decision, strategy candidates, IV crush risk, post-earnings plan.
"""
    ans = _call_ai(prompt)
    return ans or _fallback("AI Earnings Options Assistant", [
        "Earnings trades should be sized for gap risk and IV crush.",
        "Compare market-implied move with historical earnings move before buying premium.",
        "Defined-risk spreads are usually safer than naked options into binary events.",
    ])
