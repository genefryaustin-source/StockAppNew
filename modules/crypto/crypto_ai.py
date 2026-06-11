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
import re
from typing import Any, Optional

import streamlit as st


DEFAULT_CLAUDE_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-haiku-4-5-20251001",
)


def _get_anthropic_key() -> str:
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        key = os.getenv("ANTHROPIC_API_KEY", "")

    return str(key or "").strip()


def _claude(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """
    Small Anthropic wrapper.

    Important:
    - Do not pass system=None.
    - Anthropic SDK 0.109.x accepts messages cleanly with no system field.
    - If a system prompt is provided, pass it as an array content block.
    """

    key = _get_anthropic_key()

    if not key:
        return "⚠️ ANTHROPIC_API_KEY not found."

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)

        kwargs: dict[str, Any] = {
            "model": DEFAULT_CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": str(prompt or ""),
                }
            ],
        }

        if system and str(system).strip():
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": str(system).strip(),
                }
            ]

        resp = client.messages.create(**kwargs)

        if not getattr(resp, "content", None):
            return "No AI response returned."

        block = resp.content[0]

        return str(getattr(block, "text", "") or "").strip()

    except Exception as e:
        return f"AI unavailable: {type(e).__name__}: {e}"


def _extract_json_payload(raw: str) -> Any:
    """
    Robustly extract JSON from Claude responses.

    Handles:
    - ```json
    - ``` json
    - extra text before/after JSON
    - list or object payloads
    """

    text = str(raw or "").strip()

    if not text:
        raise ValueError("Empty AI response")

    text = re.sub(r"```[\s]*json", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    array_start = text.find("[")
    array_end = text.rfind("]")

    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidate = text[array_start : array_end + 1]
        return json.loads(candidate)

    obj_start = text.find("{")
    obj_end = text.rfind("}")

    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidate = text[obj_start : obj_end + 1]
        return json.loads(candidate)

    raise ValueError("No valid JSON object or array found")


def _coerce_list(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    if isinstance(value, dict):
        return [value]

    return []


def _clean_symbol_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]

    return []


def _json_or_text_to_trends(raw: str) -> list[dict]:
    """
    Convert AI output into display-friendly trend dictionaries.
    Prevents raw JSON from leaking into the UI.
    """

    try:
        parsed = _extract_json_payload(raw)
        trends = _coerce_list(parsed)

        clean_rows: list[dict] = []

        for trend in trends:
            clean_rows.append(
                {
                    "theme": str(trend.get("theme") or "Market Narrative").strip(),
                    "coins": _clean_symbol_list(trend.get("coins")),
                    "momentum": str(trend.get("momentum") or "unknown").strip(),
                    "rationale": str(trend.get("rationale") or "").strip(),
                    "risk": str(trend.get("risk") or "").strip(),
                }
            )

        if clean_rows:
            return clean_rows

    except Exception:
        pass

    cleaned = re.sub(r"```[\s]*json", "", str(raw or ""), flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()

    return [
        {
            "theme": "AI Trend Analysis",
            "coins": [],
            "momentum": "unknown",
            "rationale": cleaned[:2000] if cleaned else "No trend analysis returned.",
            "risk": "",
        }
    ]


def _json_or_text_to_alerts(raw: str) -> list[dict]:
    try:
        parsed = _extract_json_payload(raw)
        alerts = _coerce_list(parsed)

        clean_rows: list[dict] = []

        for alert in alerts:
            clean_rows.append(
                {
                    "symbol": str(alert.get("symbol") or "MARKET").strip(),
                    "alert_type": str(alert.get("alert_type") or "market").strip(),
                    "interpretation": str(alert.get("interpretation") or "").strip(),
                    "severity": str(alert.get("severity") or "medium").strip(),
                    "action": str(alert.get("action") or "monitor").strip(),
                }
            )

        return clean_rows

    except Exception:
        return [
            {
                "symbol": "MARKET",
                "interpretation": str(raw or "")[:2000],
                "severity": "medium",
                "action": "monitor",
                "alert_type": "market",
            }
        ]


def _json_or_text_to_portfolio(raw: str) -> dict:
    try:
        parsed = _extract_json_payload(raw)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    return {
        "overall_assessment": str(raw or "").strip(),
        "concentration_risk": "",
        "rebalancing_suggestion": "",
        "market_timing": "",
        "top_concern": "",
        "opportunity": "",
    }


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
        for g in top_gainers[:5]
        if g.get("24h %")
    )

    losers_str = ", ".join(
        f"{l.get('Symbol','')} {l.get('24h %',0):.1f}%"
        for l in top_losers[:5]
        if l.get("24h %")
    )

    trending_str = ", ".join(t.get("Symbol", "") for t in trending[:5])

    prompt = f"""You are a senior crypto market analyst. Summarize today's crypto market in 3 short markdown sections.

MARKET DATA:
- Total crypto market cap: ${total_mcap/1e9:,.0f}B ({mcap_change:+.1f}% 24h)
- 24h trading volume: ${total_vol/1e9:,.0f}B
- BTC dominance: {btc_dom:.1f}%
- Fear & Greed Index: {fear_greed_value} — {fear_greed_label}
- Top gainers: {gainers_str}
- Top losers: {losers_str}
- Trending searches: {trending_str}
- DeFi TVL change 24h: {f'{defi_tvl_change:+.1f}%' if defi_tvl_change else 'N/A'}

Return markdown using exactly these headings:

### Macro Picture
2 sentences.

### Sector Rotation
1-2 sentences.

### Watch List
1 sentence.

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
    mcap_b = (market_cap or 0) / 1e9
    vol_b = (volume_24h or 0) / 1e9
    vol_mcap = round(vol_b / max(0.001, mcap_b) * 100, 1)

    desc_short = (description[:400] + "…") if len(description) > 400 else description

    prompt = f"""You are a crypto research analyst. Provide a concise investment analysis for {name} ({symbol}).

MARKET DATA:
- Price: ${price:,.4f}
- 24h change: {change_24h:+.2f}%  |  7d change: {change_7d:+.2f}%
- Market cap: ${mcap_b:.1f}B
- 24h volume: ${vol_b:.1f}B  |  Volume/Market cap ratio: {vol_mcap:.1f}%
- ATH: ${ath:,.4f}  |  Distance from ATH: {from_ath:.1f}%
- Circulating supply: {circulating_supply:,.0f} {symbol}
- Community score: {community_score or 'N/A'}  |  Developer score: {developer_score or 'N/A'}

PROJECT:
{desc_short[:200] if desc_short else 'No description available.'}

Return markdown using exactly these headings:

### What It Is
1 sentence.

### Bull Case
2 sentences.

### Bear Case
1-2 sentences.

### Verdict
1 sentence.

Be specific to this coin's actual data and characteristics."""

    return _claude(prompt, max_tokens=400)


# ── 3. Portfolio Advisor ───────────────────────────────────────────────────────

def advise_portfolio(
    holdings: list[dict],
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

Return only valid JSON with these keys:
{{
  "overall_assessment": "<2 sentences on portfolio health>",
  "concentration_risk": "<note on concentration if any position > 40%>",
  "rebalancing_suggestion": "<specific suggestion if needed>",
  "market_timing": "<should they add, hold, or reduce given Fear/Greed?>",
  "top_concern": "<single biggest risk in this portfolio right now>",
  "opportunity": "<one specific opportunity based on current market conditions>"
}}"""

    raw = _claude(prompt, max_tokens=500)

    return _json_or_text_to_portfolio(raw)


# ── 4. Trend Detector ─────────────────────────────────────────────────────────

def detect_trends(
    top_coins: list[dict],
    trending: list[dict],
    category_performers: list[dict],
) -> list[dict]:
    """Identify emerging narratives and sector rotations."""
    movers = [c for c in top_coins if (c.get("7d %") or 0) > 10][:10]

    movers_str = "\n".join(
        f"- {c.get('Symbol','')} ({c.get('Name','')}): +{c.get('7d %',0):.1f}% 7d"
        for c in movers
    )

    trending_str = ", ".join(t.get("Symbol", "") for t in trending[:8])

    categories_str = "\n".join(
        f"- {c.get('Category', c.get('Name', 'Unknown'))}: {c.get('24h %', c.get('7d %', 0)):+.1f}%"
        for c in category_performers[:8]
        if isinstance(c, dict)
    )

    prompt = f"""You are a crypto trend analyst. Identify 3-5 emerging market narratives.

TOP 7-DAY PERFORMERS:
{movers_str if movers_str else 'No significant movers'}

TRENDING SEARCHES:
{trending_str}

CATEGORY / SECTOR MOVERS:
{categories_str if categories_str else 'No category data available'}

Return only valid JSON. Do not wrap in markdown fences. Do not add commentary before or after JSON.

[
  {{
    "theme": "Narrative name",
    "coins": ["SYMBOL1", "SYMBOL2"],
    "momentum": "strong|moderate|early",
    "rationale": "1-2 sentence reason this theme is emerging",
    "risk": "1 sentence key risk"
  }}
]"""

    raw = _claude(prompt, max_tokens=650)

    return _json_or_text_to_trends(raw)


# ── 5. Risk Alert Scanner ─────────────────────────────────────────────────────

def scan_crypto_risks(
    watchlist_coins: list[dict],
    fear_greed: int,
    btc_change_24h: float,
    market_cap_change: float,
) -> list[dict]:
    """Flag anomalies and risks across a crypto watchlist."""
    flags = []

    for coin in watchlist_coins:
        symbol = coin.get("Symbol", "")
        ch24 = coin.get("24h %") or 0
        ch7d = coin.get("7d %") or 0
        vol = coin.get("Volume 24h") or 0
        mcap = coin.get("Market Cap") or 1
        vol_mcap = vol / max(1, mcap)

        reasons = []

        if abs(ch24) > 15:
            reasons.append(f"Extreme 24h move: {ch24:+.1f}%")

        if vol_mcap > 0.5:
            reasons.append(f"Unusual volume: {vol_mcap*100:.0f}% of market cap")

        if ch7d < -20:
            reasons.append(f"Sharp 7d decline: {ch7d:.1f}%")

        if reasons:
            flags.append(
                {
                    "symbol": symbol,
                    "reasons": reasons,
                    "change_24h": ch24,
                    "change_7d": ch7d,
                }
            )

    if not flags and fear_greed < 25:
        flags.append(
            {
                "symbol": "MARKET",
                "reasons": [f"Extreme Fear: Fear & Greed = {fear_greed}"],
                "change_24h": btc_change_24h,
                "change_7d": 0,
            }
        )

    if not flags:
        return []

    flags_str = "\n".join(
        f"- {f['symbol']}: {', '.join(f['reasons'])}"
        for f in flags[:8]
    )

    prompt = f"""
    You are a senior crypto risk analyst.

    MARKET CONTEXT
    --------------
    Fear & Greed: {fear_greed}
    BTC 24h Change: {btc_change_24h:+.1f}%
    Total Market Cap Change: {market_cap_change:+.1f}%

    FLAGGED CONDITIONS
    ------------------
    {flags_str}

    Write a short risk report using markdown.

    For each flagged asset provide:

    ### SYMBOL

    Severity: Low / Medium / High

    What Happened:
    <1 sentence>

    Why It Matters:
    <1-2 sentences>

    Recommended Action:
    Monitor / Review / Caution

    Keep the report concise and analyst-focused.
    """

    raw = _claude(prompt, max_tokens=700)

    return raw
