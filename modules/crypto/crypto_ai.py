"""
modules/crypto/crypto_ai.py

AI enhancements for Crypto — 5 features:
1. Market Narrative     — what's driving the market right now
2. Coin Analysis        — AI tearsheet for any coin
3. Portfolio Advisor    — given holdings, what to do
4. Trend Detector       — spot emerging narratives/sectors
5. Risk Alert           — flag anomalies in your watchlist
"""
from __future__ import annotations
import json
import os
from typing import Optional
import streamlit as st


def _claude(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    key = None
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return "⚠️ ANTHROPIC_API_KEY not found."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        kwargs = {"model": "claude-haiku-4-5-20251001",
                  "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.content[0].text.strip()
    except Exception as e:
        return f"AI unavailable: {e}"


# ── 1. Market Narrative ────────────────────────────────────────────────────────

def generate_market_narrative(
    global_stats: dict,
    fear_greed_value: Optional[int],
    fear_greed_label: Optional[str],
    top_gainers: list[dict],
    top_losers: list[dict],
    trending: list[dict],
    defi_tvl_change: Optional[float],
) -> str:
    """Generate a concise market narrative from global data."""
    btc_dom = global_stats.get("bitcoin_dominance_percentage", 0)
    total_mcap = global_stats.get("total_market_cap", {}).get("usd", 0)
    mcap_change = global_stats.get("market_cap_change_percentage_24h_usd", 0)
    total_vol = global_stats.get("total_volume", {}).get("usd", 0)

    gainers_str = ", ".join(
        f"{g.get('Symbol','')} +{g.get('24h %',0):.1f}%"
        for g in top_gainers[:5] if g.get("24h %")
    )
    losers_str = ", ".join(
        f"{l.get('Symbol','')} {l.get('24h %',0):.1f}%"
        for l in top_losers[:5] if l.get("24h %")
    )
    trending_str = ", ".join(t.get("Symbol","") for t in trending[:5])

    prompt = f"""You are a senior crypto market analyst. Summarize today's crypto market in 3 short paragraphs.

MARKET DATA:
- Total crypto market cap: ${total_mcap/1e9:,.0f}B ({mcap_change:+.1f}% 24h)
- 24h trading volume: ${total_vol/1e9:,.0f}B
- BTC dominance: {btc_dom:.1f}%
- Fear & Greed Index: {fear_greed_value} — {fear_greed_label}
- Top gainers: {gainers_str}
- Top losers: {losers_str}
- Trending searches: {trending_str}
- DeFi TVL change 24h: {f'{defi_tvl_change:+.1f}%' if defi_tvl_change else 'N/A'}

Write:
1. MACRO PICTURE (2 sentences): Overall market condition and dominant narrative
2. SECTOR ROTATION (1-2 sentences): Which sectors/narratives are gaining/losing momentum
3. WATCH LIST (1 sentence): One specific catalyst or trend worth watching in next 24-48h

Be specific and data-driven. No generic advice."""

    return _claude(prompt, max_tokens=350)


# ── 2. Coin Analysis (AI Tearsheet) ───────────────────────────────────────────

def analyze_coin(
    coin_id: str,
    symbol: str,
    name: str,
    price: float,
    change_24h: float,
    change_7d: float,
    market_cap: float,
    volume_24h: float,
    ath: float,
    ath_pct: float,
    circulating_supply: float,
    community_score: Optional[float],
    developer_score: Optional[float],
    description: str = "",
) -> str:
    """Generate an AI investment analysis for a specific coin."""
    from_ath = ath_pct or 0
    mcap_b  = (market_cap or 0) / 1e9
    vol_b   = (volume_24h or 0) / 1e9
    vol_mcap= round(vol_b / max(0.001, mcap_b) * 100, 1)  # volume/mcap ratio

    # Truncate description
    desc_short = (description[:400] + "…") if len(description) > 400 else description

    prompt = f"""You are a crypto research analyst. Provide a concise investment analysis for {name} ({symbol}).

MARKET DATA:
- Price: ${price:,.4f}
- 24h change: {change_24h:+.2f}%  |  7d change: {change_7d:+.2f}%
- Market cap: ${mcap_b:.1f}B  |  Rank by market cap
- 24h volume: ${vol_b:.1f}B  |  Volume/Market cap ratio: {vol_mcap:.1f}%
- ATH: ${ath:,.4f}  |  Distance from ATH: {from_ath:.1f}%
- Circulating supply: {circulating_supply:,.0f} {symbol}
- Community score: {community_score or 'N/A'}  |  Developer score: {developer_score or 'N/A'}

PROJECT: {desc_short[:200] if desc_short else 'No description available.'}

Provide a structured 4-part analysis:
1. WHAT IT IS (1 sentence): Core value proposition
2. BULL CASE (2 sentences): Why this could outperform
3. BEAR CASE (1-2 sentences): Key risks and concerns  
4. VERDICT (1 sentence): Overall assessment at current price/levels

Be specific to this coin's actual data and characteristics."""

    return _claude(prompt, max_tokens=400)


# ── 3. Portfolio Advisor ───────────────────────────────────────────────────────

def advise_portfolio(
    holdings: list[dict],  # [{symbol, name, value_usd, pct_portfolio, change_7d}]
    total_value: float,
    fear_greed: int,
    btc_dominance: float,
    market_change_7d: float,
) -> dict:
    """Portfolio-level AI advice based on current holdings and market conditions."""
    holdings_str = "\n".join(
        f"- {h['symbol']}: ${h['value_usd']:,.0f} ({h['pct_portfolio']:.1f}% of portfolio)"
        f" | 7d: {h.get('change_7d',0):+.1f}%"
        for h in holdings
    )

    prompt = f"""You are a crypto portfolio advisor. Analyze this crypto portfolio.

PORTFOLIO (Total: ${total_value:,.0f}):
{holdings_str}

MARKET CONDITIONS:
- Fear & Greed Index: {fear_greed} ({'Fear' if fear_greed < 40 else 'Greed' if fear_greed > 60 else 'Neutral'})
- BTC dominance: {btc_dominance:.1f}%
- Market 7d change: {market_change_7d:+.1f}%

Provide portfolio advice in this JSON format:
{{
  "overall_assessment": "<2 sentences on portfolio health>",
  "concentration_risk": "<note on concentration if any position > 40%>",
  "rebalancing_suggestion": "<specific suggestion if needed>",
  "market_timing": "<should they add, hold, or reduce given Fear/Greed?>",
  "top_concern": "<single biggest risk in this portfolio right now>",
  "opportunity": "<one specific opportunity based on current market conditions>"
}}"""

    raw = _claude(prompt, max_tokens=500)
    try:
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return json.loads(clean)
    except Exception:
        return {"overall_assessment": raw}


# ── 4. Trend Detector ─────────────────────────────────────────────────────────

def detect_trends(
    top_coins: list[dict],
    trending: list[dict],
    category_performers: list[dict],
) -> list[dict]:
    """Identify emerging narratives and sector rotations."""
    # Group top performers by potential narrative
    movers = [c for c in top_coins if (c.get("7d %") or 0) > 10][:10]
    movers_str = "\n".join(
        f"- {c.get('Symbol','')} ({c.get('Name','')}): +{c.get('7d %',0):.1f}% 7d"
        for c in movers
    )
    trending_str = ", ".join(t.get("Symbol","") for t in trending[:8])

    prompt = f"""You are a crypto trend analyst. Identify 3-5 emerging market narratives.

TOP 7-DAY PERFORMERS:
{movers_str if movers_str else 'No significant movers'}

TRENDING SEARCHES (last 24h): {trending_str}

Identify 3-5 distinct market narratives/themes gaining momentum.
Respond in JSON array:
[
  {{
    "theme": "<narrative name e.g. 'AI Tokens', 'DeFi Revival', 'L2 Season'>",
    "coins": ["SYMBOL1", "SYMBOL2"],
    "momentum": "strong|moderate|early",
    "rationale": "<1 sentence why this theme is emerging>",
    "risk": "<1 sentence key risk to this theme>"
  }}
]"""

    raw = _claude(prompt, max_tokens=500)
    try:
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return json.loads(clean)
    except Exception:
        return [{"theme": "Analysis", "rationale": raw, "momentum": "unknown", "coins": [], "risk": ""}]


# ── 5. Risk Alert Scanner ─────────────────────────────────────────────────────

def scan_crypto_risks(
    watchlist_coins: list[dict],  # from top coins data
    fear_greed: int,
    btc_change_24h: float,
    market_cap_change: float,
) -> list[dict]:
    """Flag anomalies and risks across a crypto watchlist."""
    # Find anomalies
    flags = []

    for coin in watchlist_coins:
        symbol = coin.get("Symbol","")
        ch24   = coin.get("24h %") or 0
        ch7d   = coin.get("7d %") or 0
        vol    = coin.get("Volume 24h") or 0
        mcap   = coin.get("Market Cap") or 1
        vol_mcap = vol / max(1, mcap)

        # Flag unusual conditions
        reasons = []
        if abs(ch24) > 15:
            reasons.append(f"Extreme 24h move: {ch24:+.1f}%")
        if vol_mcap > 0.5:
            reasons.append(f"Unusual volume: {vol_mcap*100:.0f}% of market cap")
        if ch7d < -20:
            reasons.append(f"Sharp 7d decline: {ch7d:.1f}%")
        if reasons:
            flags.append({"symbol": symbol, "reasons": reasons,
                          "change_24h": ch24, "change_7d": ch7d})

    if not flags and fear_greed < 25:
        flags.append({
            "symbol": "MARKET",
            "reasons": [f"Extreme Fear: Fear & Greed = {fear_greed}"],
            "change_24h": btc_change_24h,
            "change_7d": 0,
        })

    if not flags:
        return []

    flags_str = "\n".join(
        f"- {f['symbol']}: {', '.join(f['reasons'])}"
        for f in flags[:8]
    )

    prompt = f"""You are a crypto risk analyst. Interpret these market anomalies.

MARKET CONTEXT:
- Fear & Greed Index: {fear_greed}
- BTC 24h change: {btc_change_24h:+.1f}%
- Total market cap 24h change: {market_cap_change:+.1f}%

FLAGGED ANOMALIES:
{flags_str}

For each flagged coin, provide a 1-sentence risk interpretation.
Respond as JSON array:
[
  {{
    "symbol": "SYMBOL",
    "alert_type": "volatility|volume|trend|market",
    "interpretation": "<1 sentence>",
    "severity": "low|medium|high",
    "action": "monitor|review|caution"
  }}
]"""

    raw = _claude(prompt, max_tokens=600)
    try:
        clean = raw.strip().replace("```json","").replace("```","").strip()
        alerts = json.loads(clean)
        return alerts if isinstance(alerts, list) else []
    except Exception:
        return [{"symbol": "MARKET", "interpretation": raw,
                 "severity": "medium", "action": "monitor", "alert_type": "market"}]