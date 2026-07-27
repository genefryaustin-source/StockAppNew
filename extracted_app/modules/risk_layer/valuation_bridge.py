"""
modules/risk_layer/valuation_bridge.py

Flags equity positions trading at rich valuation multiples, using the same
modules.valuation.compute_valuation() the Valuation feature itself calls.
This is intentionally a thin, honest wrapper -- compute_valuation currently
returns P/E and P/S multiples (whatever fundamentals snapshot is on hand),
not a fair-value target, so "risk flag" here means "expensive by a simple
multiple threshold," not "this stock will fall." Thresholds are
deliberately conservative and configurable via the args below.
"""

from __future__ import annotations

from modules.valuation import compute_valuation

DEFAULT_PE_RICH_THRESHOLD = 40.0
DEFAULT_PS_RICH_THRESHOLD = 15.0


def valuation_flags(
    db,
    tenant_id: str,
    symbols: list[str],
    pe_threshold: float = DEFAULT_PE_RICH_THRESHOLD,
    ps_threshold: float = DEFAULT_PS_RICH_THRESHOLD,
) -> dict:
    """Returns {symbol: {"pe_ttm":..., "ps_ttm":..., "flag": str|None}} for
    every equity symbol with a fundamentals snapshot on hand. Symbols with
    no snapshot are omitted rather than guessed at."""
    out = {}
    for symbol in dict.fromkeys(symbols):
        try:
            val = compute_valuation(db, tenant_id, symbol)
        except Exception:
            continue
        if val is None:
            continue
        pe, ps = val.get("pe_ttm"), val.get("ps_ttm")
        if pe is None and ps is None:
            continue

        flag = None
        try:
            if pe is not None and float(pe) > pe_threshold:
                flag = f"P/E {float(pe):.1f}x exceeds {pe_threshold:.0f}x threshold"
            elif ps is not None and float(ps) > ps_threshold:
                flag = f"P/S {float(ps):.1f}x exceeds {ps_threshold:.0f}x threshold"
        except (TypeError, ValueError):
            pass

        out[symbol] = {"pe_ttm": pe, "ps_ttm": ps, "flag": flag}
    return out
