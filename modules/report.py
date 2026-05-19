import json
import pandas as pd

def _fmt_money(x):
    if x is None:
        return "n/a"
    try:
        x = float(x)
        if abs(x) >= 1e12:
            return f"${x/1e12:.2f}T"
        if abs(x) >= 1e9:
            return f"${x/1e9:.2f}B"
        if abs(x) >= 1e6:
            return f"${x/1e6:.2f}M"
        return f"${x:,.0f}"
    except Exception:
        return "n/a"

def _fmt_pct(x):
    if x is None:
        return "n/a"
    try:
        return f"{float(x)*100:.1f}%"
    except Exception:
        return "n/a"

def build_investment_summary_text(
    symbol: str,
    profile: dict,
    fin_health: dict,
    valuation: dict,
    peers_table: pd.DataFrame,
    technicals: dict,
    risks: list[dict],
) -> str:
    name = profile.get("longName") or profile.get("shortName") or symbol
    sector = profile.get("sector", "n/a")
    industry = profile.get("industry", "n/a")

    rev = _fmt_money(fin_health.get("revenue_latest"))
    rev_yoy = _fmt_pct(fin_health.get("revenue_yoy"))
    gm = _fmt_pct(fin_health.get("gross_margin"))
    om = _fmt_pct(fin_health.get("operating_margin"))
    nm = _fmt_pct(fin_health.get("net_margin"))

    cash = _fmt_money(fin_health.get("cash"))
    debt = _fmt_money(fin_health.get("total_debt"))
    net_cash = _fmt_money(fin_health.get("net_cash"))
    cfo = _fmt_money(fin_health.get("operating_cash_flow"))
    fcf = _fmt_money(fin_health.get("fcf_proxy"))

    ps = valuation.get("price_to_sales_ttm")
    pe = valuation.get("trailing_pe")
    mcap = _fmt_money(valuation.get("market_cap"))

    cur = technicals.get("current_price", "n/a")
    trend = technicals.get("trend", "n/a")
    rsi = technicals.get("momentum", {}).get("rsi14")
    breakout = technicals.get("possible_breakout_above")
    breakdown = technicals.get("possible_breakdown_below")

    supports = technicals.get("support_resistance", {}).get("support", [])
    resist = technicals.get("support_resistance", {}).get("resistance", [])

    # peer medians
    peer_ps_median = None
    peer_pe_median = None
    try:
        peer_ps_median = peers_table["P/S (TTM)"].dropna().median()
        peer_pe_median = peers_table["TrailingPE"].dropna().median()
    except Exception:
        pass

    lines = []
    lines.append(f"## {name} ({symbol}) — Structured Investment Summary\n")
    lines.append(f"**Sector / Industry:** {sector} / {industry}")
    lines.append(f"**Market cap:** {mcap}\n")

    lines.append("### Business & Competitive Position (facts-first)")
    lines.append("- Data/AI analytics and decision-support software for government and enterprise customers (per company profile / industry classification).")
    lines.append("- Differentiation typically comes from integration depth, security/compliance posture, and workflow embedding (high switching costs once deployed).\n")

    lines.append("### Financial Health")
    lines.append(f"- **Revenue (latest annual):** {rev} | **YoY:** {rev_yoy}")
    lines.append(f"- **Margins:** Gross {gm} | Operating {om} | Net {nm}")
    lines.append(f"- **Liquidity / Leverage:** Cash {cash} | Debt {debt} | Net cash {net_cash}")
    lines.append(f"- **Cash generation:** Operating cash flow {cfo} | FCF proxy (CFO - capex) {fcf}")
    flags = fin_health.get("red_flags", [])
    if flags:
        lines.append(f"- **Automated flags:** {', '.join(flags)}")
    else:
        lines.append("- **Automated flags:** None detected from available statement signals.")
    lines.append("")

    lines.append("### Valuation (multiples)")
    lines.append(f"- **Trailing P/E:** {pe if pe is not None else 'n/a'}")
    lines.append(f"- **Price/Sales (TTM):** {ps if ps is not None else 'n/a'}")
    if peer_ps_median is not None:
        lines.append(f"- **Peer median P/S (selected set):** {peer_ps_median:.2f}")
    if peer_pe_median is not None:
        lines.append(f"- **Peer median P/E (selected set):** {peer_pe_median:.2f}")
    lines.append("- Interpretation: higher-than-peer multiples indicate the market is pricing in superior growth/durability; lower-than-peer suggests skepticism or under-recognition.\n")

    lines.append("### Industry Context")
    lines.append("- Key competitor categories typically include: hyperscalers (platform bundles), data platforms/warehouses, and analytics/ML tooling vendors.")
    lines.append("- Tailwinds: enterprise AI adoption, data governance needs, security/compliance requirements, and migration from legacy analytics stacks.")
    lines.append("- Headwinds: bundling pressure, commoditization of baseline AI tooling, and pricing competition.\n")

    lines.append("### Risks (Downside scenarios)")
    for r in risks[:8]:
        lines.append(f"- **{r.get('category')} — {r.get('scenario')}**")
        mech = r.get("mechanism")
        if mech:
            lines.append(f"  - Mechanism: {mech}")
        impact = r.get("impact_band")
        if isinstance(impact, dict):
            lines.append(f"  - Impact band: {impact}")
        if r.get("flags"):
            lines.append(f"  - Flags: {r.get('flags')}")
    lines.append("")

    lines.append("### Technical Structure (price-based)")
    lines.append(f"- **Trend:** {trend} | **Current price:** {cur} | **RSI(14):** {round(rsi,1) if isinstance(rsi,(int,float)) else 'n/a'}")
    if supports:
        lines.append(f"- **Support zones:** {supports}")
    if resist:
        lines.append(f"- **Resistance zones:** {resist}")
    lines.append(f"- **Breakout area:** above {breakout if breakout is not None else 'n/a'}")
    lines.append(f"- **Breakdown area:** below {breakdown if breakdown is not None else 'n/a'}\n")

    lines.append("### Bottom Line")
    lines.append("- This summary is generated from available market data feeds and simple quantitative rules.")
    lines.append("- Use it to structure diligence: validate drivers, confirm statement quality, and sanity-check valuation vs peers.\n")

    return "\n".join(lines)

def export_markdown(text: str) -> bytes:
    return text.encode("utf-8")