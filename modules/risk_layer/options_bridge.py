"""
modules/risk_layer/options_bridge.py

Options-specific risk overlay. Concentration and near-term expiry risk
are computed directly from broker position data (qty/strike/expiry/market
value); real Greeks (delta/gamma/theta/vega/rho) are computed via
modules.options.quantlib_greeks_engine (QuantLib, BSD license) rather
than reported as unavailable -- broker feeds like Alpaca's raw
/v2/positions don't include live Greeks, but each position's own
mark_price is enough to back out an implied volatility (Black-Scholes
inversion), which is then fed back through Black-Scholes to get real
Greeks. This only works for positions with a usable mark_price, strike,
expiry, and a resolvable underlying spot price -- positions missing any
of those are counted but excluded from the Greeks aggregate, and the
result says so rather than silently treating them as zero.
"""

from __future__ import annotations

from datetime import datetime

NEAR_TERM_DTE_DAYS = 7


def _parse_expiry(expiry_str: str):
    if not expiry_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(expiry_str, fmt).date()
        except ValueError:
            continue
    return None


def _compute_position_greeks(position, spot_price: float) -> dict | None:
    from modules.options.quantlib_greeks_engine import compute_greeks, implied_volatility

    expiry_date = _parse_expiry(position.expiry)
    if not expiry_date or position.strike <= 0 or position.mark_price <= 0 or spot_price <= 0:
        return None

    iv = implied_volatility(
        market_price=position.mark_price, spot=spot_price, strike=position.strike,
        expiry=expiry_date, option_type=position.option_type or "call",
    )
    if iv is None or iv <= 0:
        return None

    greeks = compute_greeks(
        spot=spot_price, strike=position.strike, expiry=expiry_date,
        option_type=position.option_type or "call", implied_vol=iv, is_american=True,
    )
    if not greeks.available:
        return None

    contracts = position.qty
    multiplier = 100  # standard equity option contract multiplier
    return {
        "implied_vol": iv,
        "delta": greeks.delta,
        "gamma": greeks.gamma,
        "theta": greeks.theta,
        "vega": greeks.vega,
        "position_delta": (greeks.delta * contracts * multiplier) if greeks.delta is not None else None,
        "position_gamma": (greeks.gamma * contracts * multiplier) if greeks.gamma is not None else None,
        "position_theta": (greeks.theta * contracts * multiplier) if greeks.theta is not None else None,
        "position_vega": (greeks.vega * contracts * multiplier) if greeks.vega is not None else None,
    }


def options_risk_summary(paper: bool = True) -> dict:
    """
    Returns options-position risk context using whatever Alpaca options
    positions are live. Returns {"available": False, "reason": ...} if
    Alpaca options aren't configured/reachable -- never raises.
    """
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        broker = AlpacaOptionsBroker(paper=paper)
        positions = broker.list_options_positions()
    except Exception as e:
        return {"available": False, "reason": f"Could not reach options broker: {e}"}

    if not positions:
        return {"available": True, "position_count": 0, "greeks_available": False,
                "by_underlying": {}, "near_term_expiry": [], "total_notional": 0.0}

    total_notional = sum(abs(p.market_value) for p in positions)
    by_underlying: dict[str, float] = {}
    for p in positions:
        by_underlying[p.underlying] = by_underlying.get(p.underlying, 0.0) + abs(p.market_value)

    near_term = [
        {"symbol": p.option_symbol, "underlying": p.underlying, "dte": p.dte,
         "market_value": p.market_value, "option_type": p.option_type}
        for p in positions if p.dte is not None and p.dte <= NEAR_TERM_DTE_DAYS
    ]

    concentration = {
        u: round(v / total_notional, 4) if total_notional else 0.0
        for u, v in sorted(by_underlying.items(), key=lambda kv: -kv[1])
    }

    # ── Real Greeks via QuantLib, using each position's own mark_price to
    # back out implied vol rather than requiring a separate IV feed ──
    greeks_by_position = {}
    net_delta = net_gamma = net_theta = net_vega = 0.0
    n_delta = n_gamma = n_theta = n_vega = 0
    positions_with_greeks = 0
    try:
        from modules.market_data.service import get_latest_price_map
        underlyings = list({p.underlying for p in positions})
        spot_prices = get_latest_price_map(underlyings) or {}
    except Exception:
        spot_prices = {}

    for p in positions:
        spot = spot_prices.get(p.underlying)
        if not spot:
            continue
        g = _compute_position_greeks(p, float(spot))
        if g is None:
            continue
        greeks_by_position[p.option_symbol] = g
        positions_with_greeks += 1
        if g["position_delta"] is not None:
            net_delta += g["position_delta"]; n_delta += 1
        if g["position_gamma"] is not None:
            net_gamma += g["position_gamma"]; n_gamma += 1
        if g["position_theta"] is not None:
            net_theta += g["position_theta"]; n_theta += 1
        if g["position_vega"] is not None:
            net_vega += g["position_vega"]; n_vega += 1

    greeks_available = positions_with_greeks > 0
    result = {
        "available": True,
        "greeks_available": greeks_available,
        "position_count": len(positions),
        "total_notional": total_notional,
        "by_underlying_weight": concentration,
        "near_term_expiry": near_term,
        "near_term_dte_threshold": NEAR_TERM_DTE_DAYS,
    }

    if greeks_available:
        result["greeks"] = {
            # None (not 0) when zero positions contributed a real value for
            # that Greek -- e.g. American-exercise positions only get
            # delta/gamma reliably (see quantlib_greeks_engine's American
            # theta/vega caveat), so net_theta/net_vega are frequently
            # partial or absent even when delta/gamma are solid.
            "net_delta": net_delta if n_delta else None,
            "net_gamma": net_gamma if n_gamma else None,
            "net_theta_per_day": net_theta if n_theta else None,
            "net_vega": net_vega if n_vega else None,
            "positions_contributing": {"delta": n_delta, "gamma": n_gamma, "theta": n_theta, "vega": n_vega},
            "positions_with_greeks": positions_with_greeks,
            "positions_missing_greeks": len(positions) - positions_with_greeks,
            "by_position": greeks_by_position,
            "method": "QuantLib Black-Scholes (IV backed out from each position's own mark price)",
        }
        if positions_with_greeks < len(positions):
            result["greeks_note"] = (
                f"{len(positions) - positions_with_greeks} of {len(positions)} position(s) "
                "excluded from Greeks (missing strike/expiry/mark price, or underlying spot "
                "price unavailable)."
            )
    else:
        result["greeks_note"] = (
            "Could not compute Greeks for any position -- need a resolvable underlying spot "
            "price and a usable per-contract mark price to back out implied volatility."
        )

    return result
