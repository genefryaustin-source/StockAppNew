# risk.pt in Analytics
import pandas as pd
import numpy as np

def compute_risk(db, symbol: str):
    from modules.market_data.service import get_price_history

    sym = symbol.upper()
    df = get_price_history(db, sym, period="1y", interval="1d")
    if df is None or df.empty or len(df) < 60:
        return {"vol_20d": None, "max_drawdown_1y": None, "risk_score": None}

    close = df["Close"].astype(float)
    rets = close.pct_change().dropna()

    vol_20d = float(rets.tail(20).std() * np.sqrt(252))  # annualized
    running_max = close.cummax()
    drawdowns = (close / running_max) - 1.0
    max_dd = float(drawdowns.min())  # negative number

    # Risk score heuristic (deterministic):
    # vol: 0.15 low -> 0, 0.80 high -> 60
    # dd: -0.15 mild -> +0, -0.60 severe -> +40
    vol_component = min(max((vol_20d - 0.15) / (0.80 - 0.15), 0.0), 1.0) * 60.0
    dd_component = min(max((abs(max_dd) - 0.15) / (0.60 - 0.15), 0.0), 1.0) * 40.0
    risk_score = float(vol_component + dd_component)

    return {"vol_20d": vol_20d, "max_drawdown_1y": max_dd, "risk_score": risk_score}