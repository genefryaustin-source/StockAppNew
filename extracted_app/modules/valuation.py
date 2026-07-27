from typing import Any


def _latest_fundamental_snapshot(db: Any, tenant_id: str, symbol: str, max_age_hours: int):
    from modules.institutional.fundamentals import latest_snapshot

    return latest_snapshot(db, tenant_id, symbol, max_age_hours=max_age_hours)


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def compute_valuation(db: Any, tenant_id: str, symbol: str):
    """
    Phase A valuation:
      - P/S = market_cap / revenue_ttm (if both exist)
    Phase B valuation fields (P/E, EV/EBITDA) remain None until we ingest EV/EPS/EBITDA inputs.
    """
    sym = symbol.upper()
    snap = _latest_fundamental_snapshot(db, tenant_id, sym, max_age_hours=72)

    if not snap:
        return {"pe_ttm": None, "ps_ttm": None, "ev_ebitda": None}

    market_cap = getattr(snap, "market_cap", None)
    revenue_ttm = getattr(snap, "revenue_ttm", None)

    ps_ttm = None
    if market_cap is not None and revenue_ttm is not None:
        try:
            if float(revenue_ttm) > 0:
                ps_ttm = float(market_cap) / float(revenue_ttm)
        except Exception:
            ps_ttm = None

    return {
        "pe_ttm": getattr(snap, "pe_ttm", None),
        "ps_ttm": ps_ttm,
        "ev_ebitda": None,
    }


def build_dcf_base_inputs(db: Any, tenant_id: str, symbol: str):
    """
    Pull the best available starting point for the interactive DCF builder.
    Values are raw dollars/share counts, not display-scaled.
    """
    sym = symbol.upper()
    snap = _latest_fundamental_snapshot(db, tenant_id, sym, max_age_hours=9999)

    latest_period = None
    try:
        from modules.institutional.models import FinancialPeriod

        latest_period = (
            db.query(FinancialPeriod)
            .filter(
                FinancialPeriod.tenant_id == tenant_id,
                FinancialPeriod.symbol == sym,
                FinancialPeriod.period_type == "annual",
            )
            .order_by(FinancialPeriod.period_end.desc())
            .first()
        )
    except Exception:
        latest_period = None

    base_fcf = _safe_float(getattr(latest_period, "free_cash_flow", None))
    revenue_ttm = _safe_float(getattr(snap, "revenue_ttm", None)) if snap else None
    fcf_margin = _safe_float(getattr(snap, "fcf_margin", None)) if snap else None
    if base_fcf is None and revenue_ttm is not None and fcf_margin is not None:
        base_fcf = revenue_ttm * fcf_margin

    cash = _safe_float(getattr(snap, "cash", None)) if snap else None
    debt = _safe_float(getattr(snap, "total_debt", None)) if snap else None
    market_cap = _safe_float(getattr(snap, "market_cap", None)) if snap else None
    shares = _safe_float(getattr(snap, "shares_outstanding", None)) if snap else None

    current_price = None
    if market_cap is not None and shares not in (None, 0):
        current_price = market_cap / shares

    return {
        "base_fcf": base_fcf,
        "shares_outstanding": shares,
        "net_debt": (debt or 0.0) - (cash or 0.0),
        "current_price": current_price,
        "source_period_end": getattr(latest_period, "period_end", None),
    }


def compute_dcf_valuation(
    base_fcf: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
    growth_rate: float = 0.05,
    discount_rate: float = 0.10,
    terminal_multiple: float = 12.0,
    projection_years: int = 5,
):
    """
    Simple FCFF DCF:
      projected FCF grows at growth_rate for N years
      terminal value = final-year FCF * terminal_multiple
      equity value = enterprise value - net debt
    """
    base_fcf = float(base_fcf)
    shares_outstanding = float(shares_outstanding)
    net_debt = float(net_debt or 0.0)
    growth_rate = float(growth_rate)
    discount_rate = float(discount_rate)
    terminal_multiple = float(terminal_multiple)
    projection_years = int(projection_years)

    if base_fcf <= 0:
        raise ValueError("Base free cash flow must be greater than zero.")
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    if projection_years <= 0:
        raise ValueError("Projection years must be greater than zero.")
    if discount_rate <= -1.0:
        raise ValueError("Discount rate must be greater than -100%.")
    if terminal_multiple < 0:
        raise ValueError("Terminal multiple cannot be negative.")

    projections = []
    projected_fcf = base_fcf
    present_value_fcf = 0.0

    for year in range(1, projection_years + 1):
        projected_fcf *= 1.0 + growth_rate
        discount_factor = (1.0 + discount_rate) ** year
        pv_fcf = projected_fcf / discount_factor
        present_value_fcf += pv_fcf
        projections.append(
            {
                "year": year,
                "fcf": projected_fcf,
                "discount_factor": discount_factor,
                "present_value": pv_fcf,
            }
        )

    terminal_value = projected_fcf * terminal_multiple
    present_value_terminal = terminal_value / ((1.0 + discount_rate) ** projection_years)
    enterprise_value = present_value_fcf + present_value_terminal
    equity_value = enterprise_value - net_debt
    fair_value_per_share = equity_value / shares_outstanding

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": fair_value_per_share,
        "present_value_fcf": present_value_fcf,
        "terminal_value": terminal_value,
        "present_value_terminal": present_value_terminal,
        "terminal_value_weight": (
            present_value_terminal / enterprise_value if enterprise_value else None
        ),
        "projections": projections,
    }
