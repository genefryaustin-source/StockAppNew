# ratings.py in analytics
def compute_rating(fin: dict, val: dict, tech: dict, risk: dict):
    """
    Deterministic rating model.
    Output: rating + rationale string.
    """

    score = 0
    reasons = []

    # Trend
    if tech.get("trend") == "Uptrend":
        score += 2; reasons.append("Uptrend (price > SMA50 > SMA200)")
    elif tech.get("trend") == "Downtrend":
        score -= 2; reasons.append("Downtrend (price < SMA50 < SMA200)")

    # Momentum (RSI)
    rsi = tech.get("rsi_14")
    if rsi is not None:
        if rsi >= 60:
            score += 1; reasons.append("Momentum strong (RSI>=60)")
        elif rsi <= 40:
            score -= 1; reasons.append("Momentum weak (RSI<=40)")

    # Growth
    cagr = fin.get("revenue_cagr_3y")
    if cagr is not None:
        if cagr >= 0.20:
            score += 2; reasons.append("High growth (3Y rev CAGR>=20%)")
        elif cagr <= 0.05:
            score -= 1; reasons.append("Low growth (3Y rev CAGR<=5%)")

    # Profitability
    fcfm = fin.get("fcf_margin")
    if fcfm is not None:
        if fcfm >= 0.15:
            score += 2; reasons.append("Strong FCF margin (>=15%)")
        elif fcfm <= 0.05:
            score -= 1; reasons.append("Weak FCF margin (<=5%)")

    # Valuation (only if available)
    pe = val.get("pe_ttm")
    if pe is not None:
        if pe <= 25:
            score += 1; reasons.append("Reasonable P/E (<=25)")
        elif pe >= 60:
            score -= 2; reasons.append("High P/E (>=60)")

    # Risk penalty
    risk_score = risk.get("risk_score")
    if risk_score is not None:
        if risk_score >= 70:
            score -= 2; reasons.append("High risk (risk_score>=70)")
        elif risk_score <= 30:
            score += 1; reasons.append("Lower risk (risk_score<=30)")

    # Map score → rating
    if score >= 5:
        rating = "Strong Buy"
    elif score >= 2:
        rating = "Buy"
    elif score >= -1:
        rating = "Hold"
    else:
        rating = "Sell"

    rationale = "; ".join(reasons) if reasons else "Insufficient data for a scored rating."

    return rating, rationale