import requests
import streamlit as st
import pandas as pd


# =====================================================
# EXISTING FUNCTION (UNCHANGED)
# =====================================================

def get_alpha_signals(symbol):

    signals = {
        "earnings_surprise": None,
        "analyst_score": None,
        "insider_score": None,
        "short_interest": None,
        "options_flow": None,
    }

    try:

        api_key = st.secrets["market_data"].get("FMP_API_KEY")

        # earnings surprise
        url = f"https://financialmodelingprep.com/api/v3/earnings-surprises/{symbol}?apikey={api_key}"

        r = requests.get(url, timeout=10)

        if r.status_code == 200:

            data = r.json()

            if data:

                surprise = data[0].get("surprisePercentage")

                if surprise:
                    signals["earnings_surprise"] = float(surprise)

        # analyst rating
        url = f"https://financialmodelingprep.com/api/v3/analyst-estimates/{symbol}?apikey={api_key}"

        r = requests.get(url, timeout=10)

        if r.status_code == 200:

            data = r.json()

            if data:

                rating = data[0].get("estimatedEpsAvg")

                if rating:
                    signals["analyst_score"] = float(rating)

    except Exception:
        pass

    return signals


# =====================================================
# 🔥 NEW: SIGNAL LAYER ON TOP OF ALPHA
# =====================================================

def build_alpha_signals(alpha_df):

    if alpha_df is None or alpha_df.empty:
        return pd.DataFrame()

    df = alpha_df.copy()

    # -------------------------------------------------
    # SIGNAL CLASSIFICATION (UPGRADED)
    # -------------------------------------------------
    def classify(row):

        pct = row.get("alpha_percentile")
        spread = row.get("alpha_minus_percentile")
        conf = row.get("confidence_score")

        if pct is None:
            return "Neutral"

        # 🔥 Strong edge: high alpha + undervalued
        if pct >= 90 and spread is not None and spread > 10:
            return "Strong Buy (Undervalued Alpha)"

        # Strong buy
        if pct >= 90:
            return "Strong Buy"

        # Buy
        if pct >= 75:
            return "Buy"

        # Neutral / hold
        if pct >= 40:
            return "Hold"

        # Weak / reduce
        if pct >= 20:
            return "Reduce"

        # Overhyped / weak alpha
        return "Sell"

    df["alpha_signal"] = df.apply(classify, axis=1)

    # -------------------------------------------------
    # RATIONALE (UPGRADED)
    # -------------------------------------------------
    def rationale(row):

        parts = []

        # Factor strength
        if row.get("quality_z", 0) > 1.0:
            parts.append("strong quality")

        if row.get("growth_z", 0) > 1.0:
            parts.append("strong growth")

        if row.get("value_z", 0) > 1.0:
            parts.append("deep value")

        if row.get("momentum_z", 0) > 1.0:
            parts.append("strong momentum")

        if row.get("risk_z", 0) > 0.5:
            parts.append("low risk")

        # 🔥 Edge detection
        spread = row.get("alpha_minus_percentile")

        if spread is not None:
            if spread > 10:
                parts.append("undervalued vs market")
            elif spread < -10:
                parts.append("overhyped vs market")

        # Confidence
        conf = row.get("confidence_score")
        if conf is not None:
            if conf >= 80:
                parts.append("high confidence")
            elif conf < 50:
                parts.append("low confidence")

        return ", ".join(parts) if parts else "mixed profile"

    df["alpha_rationale"] = df.apply(rationale, axis=1)

    # -------------------------------------------------
    # OPTIONAL FLAGS (VERY USEFUL)
    # -------------------------------------------------
    df["undervalued_flag"] = df["alpha_minus_percentile"].apply(
        lambda x: True if pd.notna(x) and x > 10 else False
    )

    df["overhyped_flag"] = df["alpha_minus_percentile"].apply(
        lambda x: True if pd.notna(x) and x < -10 else False
    )

    return df