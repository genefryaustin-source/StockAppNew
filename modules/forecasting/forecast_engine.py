"""
modules/forecasting/forecast_engine.py

AI price forecast engine for Market Terminal.
Uses the Anthropic tool-use API (structured outputs) to guarantee valid JSON —
no more parse errors from stray apostrophes, newlines, or markdown in the
model's response.

Usage:
    from modules.forecasting.forecast_engine import generate_ai_forecast
    result = generate_ai_forecast(symbol, price_df)
"""

from __future__ import annotations

import json
import os
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
import pandas as pd


# ─────────────────────────────────────────────────────────────
# Anthropic client
# ─────────────────────────────────────────────────────────────

def _anthropic_client():
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Add it to your environment or Streamlit secrets."
        )
    return anthropic.Anthropic(api_key=api_key)


def anthropic_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────────────────────
# Tool schema — forces the model to return valid structured JSON
# ─────────────────────────────────────────────────────────────

def _forecast_tool(horizon_days: int) -> dict:
    """
    Anthropic tool definition. By asking the model to "call" this tool,
    the API guarantees the response matches the schema exactly — no free-text
    that can break JSON parsing.
    """
    return {
        "name": "submit_price_forecast",
        "description": (
            "Submit a structured price forecast for the given stock. "
            "All price arrays must have exactly the requested number of elements."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mid_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": (
                        f"Central projected price path — exactly {horizon_days} floats, "
                        "one per trading day."
                    ),
                },
                "bull_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": (
                        f"Optimistic scenario upper band — exactly {horizon_days} floats."
                    ),
                },
                "bear_prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": (
                        f"Pessimistic scenario lower band — exactly {horizon_days} floats."
                    ),
                },
                "target_7d": {
                    "type": "number",
                    "description": "Projected price in 7 trading days.",
                },
                "target_30d": {
                    "type": "number",
                    "description": f"Projected price in {horizon_days} trading days.",
                },
                "confidence_pct": {
                    "type": "integer",
                    "description": "Analyst confidence in directional call, 40–85.",
                },
                "signal": {
                    "type": "string",
                    "enum": ["Bullish", "Bearish", "Neutral"],
                    "description": "Directional signal.",
                },
                "signal_strength": {
                    "type": "string",
                    "enum": ["Strong", "Moderate", "Weak"],
                    "description": "Strength of the signal.",
                },
                "rationale": {
                    "type": "string",
                    "description": (
                        "2-3 sentence analyst rationale referencing specific stats "
                        "from the provided data."
                    ),
                },
            },
            "required": [
                "mid_prices", "bull_prices", "bear_prices",
                "target_7d", "target_30d",
                "confidence_pct", "signal", "signal_strength", "rationale",
            ],
        },
    }


# ─────────────────────────────────────────────────────────────
# Core forecast function
# ─────────────────────────────────────────────────────────────

def generate_ai_forecast(
    symbol: str,
    price_df: pd.DataFrame,
    horizon_days: int = 30,
    extra_context: Optional[dict] = None,
) -> dict:
    """
    Generate an AI price forecast for `symbol`.

    Returns dict with keys:
        forecast_dates, mid_prices, bull_prices, bear_prices,
        target_7d, target_30d, confidence_pct, signal,
        signal_strength, rationale, last_price, error
    """

    if price_df is None or price_df.empty:
        return _error_result("No price history available for forecast.")

    # ── Normalise DataFrame columns ───────────────────────────
    df = price_df.copy()
    col_map = {}
    for col in df.columns:
        if col.lower() == "close":
            col_map[col] = "Close"
        elif col.lower() == "date":
            col_map[col] = "Date"
    if col_map:
        df = df.rename(columns=col_map)

    df["Close"] = pd.to_numeric(df.get("Close", pd.Series(dtype=float)), errors="coerce")
    df = df.dropna(subset=["Close"])

    if df.empty:
        return _error_result("Price data has no valid Close values.")

    prices = df["Close"].tolist()
    last_price = prices[-1]

    # ── Build stats dict for the prompt ───────────────────────
    stats = _build_stats(symbol, prices, horizon_days, extra_context)

    # ── Try Anthropic API (tool-use mode) ─────────────────────
    try:
        client = _anthropic_client()
    except EnvironmentError as e:
        return _statistical_fallback(symbol, prices, horizon_days, str(e))

    try:
        parsed = _call_anthropic_tool(client, stats, horizon_days)
    except Exception as e:
        # Last resort: try plain text + aggressive extraction
        try:
            parsed = _call_anthropic_text(client, stats, horizon_days)
        except Exception as e2:
            return _statistical_fallback(
                symbol, prices, horizon_days,
                f"API error: {e}; fallback also failed: {e2}"
            )

    # ── Validate + pad arrays ─────────────────────────────────
    for key in ("mid_prices", "bull_prices", "bear_prices"):
        arr = parsed.get(key) or []
        if not arr:
            arr = [last_price] * horizon_days
        elif len(arr) < horizon_days:
            arr += [arr[-1]] * (horizon_days - len(arr))
        parsed[key] = [float(v) for v in arr[:horizon_days]]

    mid = parsed["mid_prices"]
    t7  = parsed.get("target_7d") or (mid[6] if len(mid) > 6 else mid[-1])
    t30 = parsed.get("target_30d") or mid[-1]

    return {
        "forecast_dates":  _future_trading_dates(horizon_days),
        "mid_prices":      [round(p, 2) for p in mid],
        "bull_prices":     [round(p, 2) for p in parsed["bull_prices"]],
        "bear_prices":     [round(p, 2) for p in parsed["bear_prices"]],
        "target_7d":       round(float(t7), 2),
        "target_30d":      round(float(t30), 2),
        "confidence_pct":  int(parsed.get("confidence_pct") or 60),
        "signal":          str(parsed.get("signal") or "Neutral"),
        "signal_strength": str(parsed.get("signal_strength") or "Moderate"),
        "rationale":       str(parsed.get("rationale") or ""),
        "last_price":      last_price,
        "error":           None,
    }


# ─────────────────────────────────────────────────────────────
# Method 1: Tool use (structured output) — most reliable
# ─────────────────────────────────────────────────────────────

def _call_anthropic_tool(client, stats: dict, horizon_days: int) -> dict:
    """
    Uses Anthropic's tool_use feature to force structured JSON output.
    The API validates the response against the schema before returning it,
    so json.loads() is never needed.
    """
    tool = _forecast_tool(horizon_days)

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=(
            "You are a senior quantitative equity analyst. "
            "Generate realistic price forecasts based on technical and statistical analysis. "
            "You must call the submit_price_forecast tool with your forecast."
        ),
        tools=[tool],
        tool_choice={"type": "tool", "name": "submit_price_forecast"},
        messages=[{
            "role": "user",
            "content": (
                f"Generate a {horizon_days}-trading-day price forecast for this stock:\n\n"
                f"{json.dumps(stats, indent=2)}\n\n"
                f"Base the forecast on momentum ({stats.get('momentum_30d_pct', 0):.1f}% 30d), "
                f"annualised volatility ({stats.get('annualised_vol_20d_pct', 0):.1f}%), "
                f"and position vs 52-week range. "
                f"The bull/bear bands should reflect ±1 standard deviation over the horizon."
            )
        }],
    )

    # Extract the tool_use block — the API guarantees this exists
    # when tool_choice forces it
    for block in message.content:
        if block.type == "tool_use" and block.name == "submit_price_forecast":
            return block.input  # Already a dict — no JSON parsing needed

    raise ValueError("No tool_use block found in API response.")


# ─────────────────────────────────────────────────────────────
# Method 2: Plain text + aggressive JSON extraction (fallback)
# ─────────────────────────────────────────────────────────────

def _call_anthropic_text(client, stats: dict, horizon_days: int) -> dict:
    """
    Falls back to a plain text request with aggressive JSON extraction.
    Used only if tool_use somehow fails.
    """
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=(
            "You are a quantitative analyst. Respond with a single JSON object only. "
            "No prose before or after. No markdown fences. Raw JSON only."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Stock data: {json.dumps(stats)}\n\n"
                f"Return JSON with these exact keys: "
                f"mid_prices (array of {horizon_days} numbers), "
                f"bull_prices (array of {horizon_days} numbers), "
                f"bear_prices (array of {horizon_days} numbers), "
                f"target_7d (number), target_30d (number), "
                f"confidence_pct (integer), signal (string), "
                f"signal_strength (string), rationale (string)."
            )
        }],
    )

    raw = message.content[0].text.strip()
    return _extract_json_robustly(raw, stats.get("last_price", 100), horizon_days)


def _extract_json_robustly(raw: str, last_price: float, horizon_days: int) -> dict:
    """
    Multi-strategy JSON extraction that handles all common model output problems:
    - Markdown fences (```json ... ```)
    - Prose before/after the JSON object
    - Trailing commas
    - Unescaped newlines inside string values
    - Single quotes instead of double quotes
    """
    text = raw

    # 1. Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

    # 2. Find the outermost { ... } block
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]

    # 3. Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # 4. Replace literal newlines inside string values with \n
    #    (handles the most common cause of "Expecting ',' delimiter" errors)
    def _fix_string_newlines(m):
        return m.group(0).replace("\n", "\\n").replace("\r", "")
    text = re.sub(r'"(?:[^"\\]|\\.)*"', _fix_string_newlines, text, flags=re.DOTALL)

    # 5. Try parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 6. Try single-quote → double-quote replacement as last resort
    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    # 7. Give up — extract whatever arrays we can find via regex
    return _regex_extract_arrays(raw, last_price, horizon_days)


def _regex_extract_arrays(raw: str, last_price: float, horizon_days: int) -> dict:
    """Last-resort: pull numeric arrays out of the raw text with regex."""
    def _find_array(label: str) -> list[float]:
        pattern = rf'"{label}"\s*:\s*\[([^\]]+)\]'
        m = re.search(pattern, raw)
        if not m:
            return []
        try:
            return [float(x.strip()) for x in m.group(1).split(",") if x.strip()]
        except Exception:
            return []

    def _find_scalar(label: str) -> Optional[float]:
        pattern = rf'"{label}"\s*:\s*([0-9.]+)'
        m = re.search(pattern, raw)
        try:
            return float(m.group(1)) if m else None
        except Exception:
            return None

    def _find_string(label: str) -> Optional[str]:
        pattern = rf'"{label}"\s*:\s*"([^"]+)"'
        m = re.search(pattern, raw)
        return m.group(1) if m else None

    mid   = _find_array("mid_prices")
    bull  = _find_array("bull_prices")
    bear  = _find_array("bear_prices")

    if not mid:
        mid = [last_price] * horizon_days

    return {
        "mid_prices":      mid,
        "bull_prices":     bull or mid,
        "bear_prices":     bear or mid,
        "target_7d":       _find_scalar("target_7d"),
        "target_30d":      _find_scalar("target_30d"),
        "confidence_pct":  int(_find_scalar("confidence_pct") or 60),
        "signal":          _find_string("signal") or "Neutral",
        "signal_strength": _find_string("signal_strength") or "Moderate",
        "rationale":       _find_string("rationale") or "Forecast generated via fallback extraction.",
    }


# ─────────────────────────────────────────────────────────────
# Build stats dict
# ─────────────────────────────────────────────────────────────

def _build_stats(
    symbol: str,
    prices: list,
    horizon_days: int,
    extra_context: Optional[dict],
) -> dict:
    last_price  = prices[-1]
    first_price = prices[0]
    high_52w    = max(prices[-252:]) if len(prices) >= 252 else max(prices)
    low_52w     = min(prices[-252:]) if len(prices) >= 252 else min(prices)

    pct_from_high = ((last_price - high_52w) / high_52w) * 100
    ytd_return    = ((last_price - first_price) / first_price) * 100

    recent_30    = prices[-30:] if len(prices) >= 30 else prices
    momentum_30d = ((recent_30[-1] - recent_30[0]) / recent_30[0]) * 100

    daily_returns = [
        (prices[i] - prices[i-1]) / prices[i-1]
        for i in range(1, min(21, len(prices)))
    ]
    vol_20d = (
        pd.Series(daily_returns).std() * math.sqrt(252) * 100
        if daily_returns else 0.0
    )

    # Keep the sample small to stay well within token limits
    recent_sample = prices[-60:][::5]

    stats = {
        "symbol":                    symbol,
        "last_price":                round(last_price, 2),
        "52w_high":                  round(high_52w, 2),
        "52w_low":                   round(low_52w, 2),
        "pct_from_52w_high":         round(pct_from_high, 1),
        "ytd_return_pct":            round(ytd_return, 1),
        "momentum_30d_pct":          round(momentum_30d, 1),
        "annualised_vol_20d_pct":    round(vol_20d, 1),
        "recent_price_sample_60d":   [round(p, 2) for p in recent_sample],
        "horizon_trading_days":      horizon_days,
    }

    if extra_context:
        stats["analytics_snapshot"] = extra_context

    return stats


# ─────────────────────────────────────────────────────────────
# Statistical fallback
# ─────────────────────────────────────────────────────────────

def _statistical_fallback(
    symbol: str,
    prices: list,
    horizon_days: int,
    reason: str,
) -> dict:
    last    = prices[-1]
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, min(60, len(prices)))]
    mu      = sum(returns) / len(returns) if returns else 0.0
    sig     = float(pd.Series(returns).std()) if len(returns) > 1 else 0.015

    mid, bull, bear = [], [], []
    pm, pb, pp_ = last, last, last
    for _ in range(horizon_days):
        pm  = round(pm  * (1 + mu),             2)
        pb  = round(pb  * (1 + mu + sig * 0.8), 2)
        pp_ = round(pp_ * (1 + mu - sig * 0.8), 2)
        mid.append(pm); bull.append(pb); bear.append(pp_)

    t7  = mid[6] if len(mid) > 6 else mid[-1]
    sig_dir = "Bullish" if mu > 0 else "Bearish" if mu < 0 else "Neutral"

    return {
        "forecast_dates":  _future_trading_dates(horizon_days),
        "mid_prices":      mid,
        "bull_prices":     bull,
        "bear_prices":     bear,
        "target_7d":       t7,
        "target_30d":      mid[-1],
        "confidence_pct":  52,
        "signal":          sig_dir,
        "signal_strength": "Weak",
        "rationale": (
            "Statistical projection based on 60-day historical drift and volatility. "
            f"AI forecast unavailable: {reason}"
        ),
        "last_price":      last,
        "error":           reason,
    }


def _error_result(msg: str) -> dict:
    return {
        "forecast_dates": [], "mid_prices": [], "bull_prices": [], "bear_prices": [],
        "target_7d": None, "target_30d": None, "confidence_pct": 0,
        "signal": "N/A", "signal_strength": "N/A",
        "rationale": msg, "last_price": None, "error": msg,
    }


def _future_trading_dates(n: int) -> list[str]:
    dates = []
    d = datetime.now(timezone.utc) + timedelta(days=1)
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return dates
