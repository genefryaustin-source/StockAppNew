"""
modules/options/options_ai.py

AI enhancements for Options Trading — all 5 components.

1. Trade Thesis Generator   — per-contract AI rationale
2. Strategy Recommender     — optimal strategy given market view
3. Risk Scanner             — portfolio-level options risk flags
4. Options Q&A Assistant    — inline chain analyst chat
5. Flow Alert Interpreter   — plain-English unusual activity alerts

Uses existing ANTHROPIC_API_KEY already in app.
Context injected from existing modules:
  - analyst_service  → EPS revisions, consensus, price target
  - sentiment_service → composite social score
  - flow_service     → dark pool, options flow data
"""
from __future__ import annotations

import json
import os
from typing import Optional

import streamlit as st


# ─────────────────────────────────────────────────────────────
# Claude API helper
# ─────────────────────────────────────────────────────────────

def _claude(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Call Claude Haiku for fast, cheap options analysis."""
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("ANTHROPIC_API_KEY")

    if not key:
        return "⚠️ ANTHROPIC_API_KEY not found in secrets."

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msgs = [{"role": "user", "content": prompt}]
        kwargs = {"model": "claude-haiku-4-5-20251001",
                  "max_tokens": max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.content[0].text.strip()
    except Exception as e:
        return f"AI unavailable: {e}"


def _safe_get(module_fn, *args, **kwargs):
    """Call an existing module function safely — never crash options page."""
    try:
        return module_fn(*args, **kwargs)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────
# 1. TRADE THESIS GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_trade_thesis(
    ticker: str,
    option_type: str,
    strike: float,
    expiry: str,
    dte: int,
    iv: Optional[float],
    delta: Optional[float],
    theta: Optional[float],
    bid: Optional[float],
    ask: Optional[float],
) -> str:
    """
    Generate a trade rationale for a specific options contract.
    Pulls analyst consensus + sentiment from existing modules.
    """
    # Gather context from existing modules
    analyst_ctx = ""
    try:
        from modules.analyst.analyst_service import get_revision_score, get_price_targets
        rev   = _safe_get(get_revision_score, ticker)
        tgts  = _safe_get(get_price_targets, ticker)
        analyst_ctx = (
            f"Analyst consensus: {rev.get('current_reco','—')} | "
            f"Bull %: {rev.get('bull_pct',0):.0f}% | "
            f"Revision direction: {rev.get('revision_direction','—')} | "
            f"Composite revision score: {rev.get('composite_revision',0):+.0f} | "
            f"Price target: ${tgts.get('consensus_target',0):,.2f}"
            if tgts.get('consensus_target') else
            f"Analyst consensus: {rev.get('current_reco','—')} | "
            f"Bull %: {rev.get('bull_pct',0):.0f}%"
        )
    except Exception:
        analyst_ctx = "Analyst data unavailable."

    sentiment_ctx = ""
    try:
        from modules.sentiment.sentiment_service import get_composite_sentiment
        sent = _safe_get(get_composite_sentiment, ticker)
        sentiment_ctx = (
            f"Social sentiment: {sent.get('label','—')} "
            f"(score {sent.get('composite_score',0):+.0f}) | "
            f"Sources: {', '.join(sent.get('sources_used',[]))}"
        )
    except Exception:
        sentiment_ctx = "Sentiment data unavailable."

    spread = round(ask - bid, 2) if bid and ask else None
    mid    = round((bid + ask) / 2, 2) if bid and ask else None

    prompt = f"""You are a professional options trader. Analyze this options contract and provide a concise trade thesis.

Ticker: {ticker}
Contract: {option_type.upper()} ${strike:.2f} expiring {expiry} ({dte} DTE)
Market data: IV={f'{iv*100:.1f}%' if iv else 'N/A'} | Delta={f'{delta:.3f}' if delta else 'N/A'} | Theta={f'{theta:.4f}' if theta else 'N/A'}
Bid/Ask: ${bid:.2f} / ${ask:.2f} | Mid: ${mid:.2f} | Spread: ${spread:.2f}
{analyst_ctx}
{sentiment_ctx}

Provide a 3-part response:
1. SETUP (1 sentence): What market condition makes this contract interesting right now?
2. RATIONALE (2 sentences): Specific reasons to enter this trade based on the data above.
3. RISKS (1 sentence): Key risk to this position.

Be direct, specific, and use the actual data provided. No generic advice."""

    return _claude(prompt, max_tokens=350)


# ─────────────────────────────────────────────────────────────
# 2. STRATEGY RECOMMENDER
# ─────────────────────────────────────────────────────────────

def recommend_strategy(
    ticker: str,
    current_price: float,
    market_view: str,       # bullish / bearish / neutral
    conviction: str,        # high / medium / low
    risk_tolerance: str,    # aggressive / moderate / conservative
    iv_percentile: Optional[float] = None,
) -> dict:
    """
    Recommend the optimal strategy and pre-populate legs.
    Returns: {strategy_name, rationale, legs_config, max_risk, ideal_conditions}
    """
    # Pull IV context from chain if available
    iv_ctx = f"IV percentile: {iv_percentile:.0f}%" if iv_percentile else "IV percentile: unknown"

    # Pull analyst + sentiment for richer context
    analyst_ctx = ""
    try:
        from modules.analyst.analyst_service import get_revision_score
        rev = _safe_get(get_revision_score, ticker)
        analyst_ctx = (
            f"Analyst: {rev.get('current_reco','—')} | "
            f"EPS revisions: {rev.get('revision_direction','—')}"
        )
    except Exception:
        pass

    prompt = f"""You are an expert options strategist. Recommend the single best options strategy.

Ticker: {ticker} at ${current_price:.2f}
Market view: {market_view}
Conviction level: {conviction}
Risk tolerance: {risk_tolerance}
{iv_ctx}
{analyst_ctx}

Available strategies: Long Call, Long Put, Covered Call, Protective Put, Bull Call Spread, 
Bear Put Spread, Long Straddle, Long Strangle, Iron Condor, Butterfly Spread

Respond in this exact JSON format (no markdown, no extra text):
{{
  "strategy": "<strategy name>",
  "rationale": "<2 sentences why this strategy fits>",
  "ideal_dte": <number of days>,
  "strike_guidance": "<where to set strikes relative to current price>",
  "max_risk": "<description of max risk>",
  "ideal_conditions": "<what needs to happen for this to work>",
  "iv_note": "<one sentence on current IV environment and how it affects this strategy>"
}}"""

    raw = _claude(prompt, max_tokens=400)

    try:
        # Strip any markdown fences
        clean = raw.strip().replace("```json","").replace("```","").strip()
        result = json.loads(clean)
        result["raw"] = raw
        return result
    except Exception:
        return {
            "strategy": "Unknown",
            "rationale": raw,
            "raw": raw,
        }


# ─────────────────────────────────────────────────────────────
# 3. RISK SCANNER
# ─────────────────────────────────────────────────────────────

def scan_portfolio_risk(positions: list) -> dict:
    """
    Analyze all open options positions and flag risks.
    positions: list of OptionsPosition objects from broker.
    Returns: {flags: list[str], summary: str, risk_level: str}
    """
    if not positions:
        return {"flags": [], "summary": "No open options positions.", "risk_level": "none"}

    # Build position summary for Claude
    pos_summary = []
    total_delta  = 0
    expiring_soon = []
    high_theta    = []

    for p in positions:
        delta = p.delta or 0
        total_delta += delta * p.qty * 100

        if p.dte <= 7:
            expiring_soon.append(p.option_symbol)
        if p.theta and abs(p.theta) > 0.05:
            high_theta.append(p.option_symbol)

        pos_summary.append(
            f"- {p.option_symbol}: {p.option_type.upper()} ${p.strike} "
            f"exp {p.expiry} ({p.dte}d) | qty={int(p.qty)} | "
            f"P&L=${p.unrealized_pnl:,.0f} | "
            f"delta={delta:.3f}"
        )

    positions_text = "\n".join(pos_summary)

    prompt = f"""You are an options risk manager. Analyze these open options positions and identify key risks.

OPEN POSITIONS:
{positions_text}

PORTFOLIO METRICS:
- Total positions: {len(positions)}
- Net portfolio delta: {total_delta:+.1f}
- Positions expiring within 7 days: {len(expiring_soon)}
- High theta decay positions: {len(high_theta)}

Identify the TOP 3-5 specific risk flags. Then provide:
1. An overall risk assessment (Low/Medium/High/Critical)
2. The single most urgent action needed

Respond in this exact JSON format:
{{
  "risk_level": "Low|Medium|High|Critical",
  "flags": [
    "Flag 1: specific risk description",
    "Flag 2: specific risk description",
    "Flag 3: specific risk description"
  ],
  "urgent_action": "<single most important thing to do right now>",
  "summary": "<2 sentence overall portfolio risk summary>"
}}"""

    raw = _claude(prompt, max_tokens=500)

    try:
        clean = raw.strip().replace("```json","").replace("```","").strip()
        result = json.loads(clean)
        return result
    except Exception:
        return {
            "risk_level": "Unknown",
            "flags": [raw],
            "urgent_action": "Review positions manually.",
            "summary": raw,
        }


# ─────────────────────────────────────────────────────────────
# 4. OPTIONS Q&A ASSISTANT
# ─────────────────────────────────────────────────────────────

def options_qa(
    question: str,
    ticker: str,
    chain_summary: str,
    conversation_history: list[dict],
) -> str:
    """
    Answer questions about the options chain using Claude.
    Maintains conversation history for multi-turn dialogue.
    chain_summary: pre-built string summary of current chain data.
    """
    system = f"""You are an expert options analyst with deep knowledge of derivatives, 
Greeks, volatility, and options strategies. You are analyzing {ticker}'s options chain.

CURRENT CHAIN CONTEXT:
{chain_summary}

Answer questions concisely and specifically using the chain data above.
Focus on actionable insights. If asked about specific strikes or expiries, 
reference the actual data. Maximum 3-4 sentences per answer."""

    # Build message history
    messages = []
    for msg in conversation_history[-6:]:  # last 6 turns to stay within context
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })
    messages.append({"role": "user", "content": question})

    key = None
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("ANTHROPIC_API_KEY")

    if not key:
        return "⚠️ ANTHROPIC_API_KEY not found in secrets."

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system,
            messages=messages,
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"AI unavailable: {e}"


def build_chain_summary(ticker: str, chain_data: dict) -> str:
    """Build a compact chain summary string for the Q&A context."""
    if not chain_data or "error" in chain_data:
        return f"No chain data available for {ticker}."

    all_rows = chain_data.get("all_rows")
    if all_rows is None or all_rows.empty:
        return f"Chain data loaded for {ticker} but no rows available."

    import pandas as pd
    expirations = chain_data.get("expirations", [])
    n_calls = len(all_rows[all_rows["type"] == "call"])
    n_puts  = len(all_rows[all_rows["type"] == "put"])

    # Put/call ratio
    call_vol = all_rows[all_rows["type"]=="call"]["volume"].fillna(0).sum()
    put_vol  = all_rows[all_rows["type"]=="put"]["volume"].fillna(0).sum()
    pcr = round(put_vol / max(1, call_vol), 2)

    # Avg IV by type
    call_iv = all_rows[all_rows["type"]=="call"]["iv"].dropna().mean()
    put_iv  = all_rows[all_rows["type"]=="put"]["iv"].dropna().mean()

    # Highest OI strikes
    top_oi = all_rows.nlargest(3, "open_interest")[
        ["strike","type","open_interest","expiry"]
    ].to_dict("records") if "open_interest" in all_rows.columns else []

    # Max pain (strike with highest total OI)
    try:
        oi_by_strike = all_rows.groupby("strike")["open_interest"].sum()
        max_pain = float(oi_by_strike.idxmax()) if not oi_by_strike.empty else None
    except Exception:
        max_pain = None

    summary = f"""Ticker: {ticker}
Expirations available: {len(expirations)} ({', '.join(expirations[:4])}{' ...' if len(expirations)>4 else ''})
Total contracts: {n_calls} calls, {n_puts} puts
Put/Call volume ratio: {pcr} ({'Bearish skew' if pcr > 1.2 else 'Bullish skew' if pcr < 0.7 else 'Neutral'})
Avg call IV: {f'{call_iv*100:.1f}%' if call_iv else 'N/A'} | Avg put IV: {f'{put_iv*100:.1f}%' if put_iv else 'N/A'}
Max pain strike: ${max_pain:,.2f} (highest total open interest) {f'— {max_pain:.2f}' if max_pain else ''}
Top OI strikes: {', '.join(f"${r['strike']} {r['type']} ({r['expiry']})" for r in top_oi[:3])}"""

    return summary


# ─────────────────────────────────────────────────────────────
# 5. FLOW ALERT INTERPRETER
# ─────────────────────────────────────────────────────────────

def interpret_flow_alerts(
    ticker: str,
    unusual_contracts: list[dict],
    dark_pool_data: dict,
    pcr: float,
) -> list[dict]:
    """
    Generate plain-English interpretations of unusual options activity.
    unusual_contracts: list of dicts with strike/type/volume/oi/iv/expiry
    Returns: list of {contract, alert, interpretation, sentiment}
    """
    if not unusual_contracts:
        return []

    # Build compact alert context
    alert_lines = []
    for c in unusual_contracts[:5]:  # top 5 unusual
        vol_oi_ratio = round(c.get("volume",0) / max(1, c.get("open_interest",1)), 1)
        alert_lines.append(
            f"- {c.get('type','').upper()} ${c.get('strike')} exp {c.get('expiry')} "
            f"| vol={c.get('volume',0):,} ({vol_oi_ratio}×OI) "
            f"| IV={str(round(c.get('iv',0)*100,0))+'%' if c.get('iv') else 'N/A'}"
        )

    dp_ctx = ""
    if dark_pool_data and dark_pool_data.get("source") == "finra":
        dp_ctx = (
            f"Dark pool: {dark_pool_data.get('dark_pct',0):.2f}% of volume "
            f"| Z-score: {dark_pool_data.get('z_score',0):+.2f} "
            f"({dark_pool_data.get('signal','')})"
        )

    prompt = f"""You are an options flow analyst. Interpret these unusual options alerts for {ticker}.

UNUSUAL ACTIVITY:
{chr(10).join(alert_lines)}

Put/Call volume ratio: {pcr:.2f}
{dp_ctx}

For each alert, provide a 1-sentence interpretation explaining:
- What the activity suggests about smart money positioning
- Whether it's likely bullish, bearish, or hedging
- Any notable characteristics (size, structure, timing)

Respond in JSON array format:
[
  {{
    "contract": "<type strike expiry>",
    "interpretation": "<1 sentence plain-English interpretation>",
    "sentiment": "bullish|bearish|neutral|hedging"
  }}
]

Be specific about whether this looks like directional speculation or hedging."""

    raw = _claude(prompt, max_tokens=500)

    try:
        clean = raw.strip().replace("```json","").replace("```","").strip()
        alerts = json.loads(clean)
        return alerts if isinstance(alerts, list) else []
    except Exception:
        return [{"contract": "All", "interpretation": raw, "sentiment": "neutral"}]


def detect_unusual_contracts(chain_data: dict, vol_oi_threshold: float = 2.0) -> list[dict]:
    """
    Find contracts with unusual volume vs open interest ratio.
    vol_oi_threshold: flag when volume > threshold × open_interest
    """
    if not chain_data or "error" in chain_data:
        return []

    all_rows = chain_data.get("all_rows")
    if all_rows is None or all_rows.empty:
        return []

    df = all_rows.copy()
    df = df.dropna(subset=["volume","open_interest"])
    df = df[df["open_interest"] > 50]  # minimum OI to filter noise
    df["vol_oi_ratio"] = df["volume"] / df["open_interest"].replace(0, 1)
    unusual = df[df["vol_oi_ratio"] >= vol_oi_threshold].nlargest(10, "vol_oi_ratio")

    return unusual[["option_symbol","type","strike","expiry","volume",
                     "open_interest","iv","vol_oi_ratio"]].to_dict("records")