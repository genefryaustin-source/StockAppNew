"""
modules/forex/forex_central_bank_engine.py

Central-bank policy-rate analysis.

Rates are pulled live from FRED (St. Louis Fed) via
providers/fred_provider.py. Two of the eight are the bank's exact published
policy rate (Fed effective funds rate, ECB deposit facility rate); the rest
use the closest live FRED series available for that country (OECD overnight
interbank / central-bank-rate series), since FRED does not mirror every
central bank's headline rate directly. Each row is tagged "proxy": True/False
so callers/UI can be honest about which numbers are exact vs. a close proxy.

If FRED_API_KEY isn't configured, or a specific series lookup fails, that
bank's row carries an explicit "error" field instead of a fabricated rate --
callers should render that honestly rather than substituting a static
number.
"""

from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.providers import fred_provider

# currency / FRED series mapping.
#   proxy=False -> this series IS the bank's actual published policy rate.
#   proxy=True  -> FRED has no direct feed for this bank's policy rate, so we
#                  use the closest live short-term interbank rate as a proxy,
#                  which tracks the policy rate very closely in practice.
BANKS = {
    "FED":  {"currency": "USD", "series_id": "FEDFUNDS",        "proxy": False, "series_desc": "Effective Federal Funds Rate"},
    "ECB":  {"currency": "EUR", "series_id": "ECBDFR",          "proxy": False, "series_desc": "ECB Deposit Facility Rate"},
    "BOJ":  {"currency": "JPY", "series_id": "IRSTCB01JPM156N", "proxy": False, "series_desc": "Japan Central Bank Rate (OECD)"},
    "BOC":  {"currency": "CAD", "series_id": "IRSTCB01CAM156N", "proxy": False, "series_desc": "Canada Central Bank Rate (OECD)"},
    "BOE":  {"currency": "GBP", "series_id": "IRSTCI01GBM156N", "proxy": True,  "series_desc": "UK Overnight Interbank Rate (OECD proxy)"},
    "SNB":  {"currency": "CHF", "series_id": "IRSTCI01CHM156N", "proxy": True,  "series_desc": "Switzerland Overnight Interbank Rate (OECD proxy)"},
    "RBA":  {"currency": "AUD", "series_id": "IRSTCI01AUM156N", "proxy": True,  "series_desc": "Australia Overnight Interbank Rate (OECD proxy)"},
    "RBNZ": {"currency": "NZD", "series_id": "IRSTCI01NZM156N", "proxy": True,  "series_desc": "New Zealand Overnight Interbank Rate (OECD proxy)"},
}

# Kept for backward compatibility -- dashboards that import CENTRAL_BANKS
# still get the currency/series mapping (no static rates baked in anymore).
CENTRAL_BANKS = BANKS


def _stance(rate: float) -> tuple[str, int]:
    """Simple, transparent bucketing of a live rate into a stance label.
    This is a classification of a real number, not an invented value."""
    if rate >= 5:
        return "HAWKISH", 90
    if rate >= 4:
        return "MODERATELY_HAWKISH", 75
    if rate >= 2:
        return "NEUTRAL", 55
    return "DOVISH", 35


class ForexCentralBankEngine:

    def analyze(self, force_refresh: bool = False):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        bank_names = list(BANKS.keys())
        observations: dict[str, dict] = {}

        with ThreadPoolExecutor(max_workers=len(bank_names)) as executor:
            futures = {
                executor.submit(fred_provider.latest_observation, BANKS[bank]["series_id"]): bank
                for bank in bank_names
            }
            for future in as_completed(futures):
                bank = futures[future]
                try:
                    observations[bank] = future.result()
                except Exception as exc:
                    observations[bank] = {"error": str(exc)}

        rows = []

        for bank in bank_names:
            meta = BANKS[bank]
            obs = observations.get(bank) or {"error": "No observation returned."}

            if obs.get("error"):
                rows.append({
                    "central_bank": bank,
                    "currency": meta["currency"],
                    "policy_rate": None,
                    "policy_bias": "UNKNOWN",
                    "hawkish_score": None,
                    "currency_bias": "UNKNOWN",
                    "proxy": meta["proxy"],
                    "series_id": meta["series_id"],
                    "series_desc": meta["series_desc"],
                    "error": obs["error"],
                })
                continue

            rate = obs["value"]
            stance, score = _stance(rate)

            rows.append({
                "central_bank": bank,
                "currency": meta["currency"],
                "policy_rate": rate,
                "policy_rate_asof": obs.get("date"),
                "policy_bias": stance,
                "hawkish_score": score,
                "currency_bias": "BULLISH" if score >= 70 else "BEARISH" if score < 45 else "NEUTRAL",
                "proxy": meta["proxy"],
                "series_id": meta["series_id"],
                "series_desc": meta["series_desc"],
            })

        scored = [r for r in rows if r.get("hawkish_score") is not None]
        scored.sort(key=lambda r: r["hawkish_score"], reverse=True)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "fred",
            "fred_configured": fred_provider.is_configured(),
            "central_banks": rows,
            "most_hawkish": scored[0] if scored else None,
            "most_dovish": scored[-1] if scored else None,
        }


_ENGINE = None


def get_forex_central_bank_engine(db=None, tenant_id=None, user_id=None, portfolio_id=None):
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ForexCentralBankEngine()
    return _ENGINE