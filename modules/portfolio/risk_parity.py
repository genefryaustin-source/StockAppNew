import numpy as np
import pandas as pd


def risk_parity_weights(price_cache, symbols):

    vols = []

    for s in symbols:

        from modules.market_data.service import get_price_history

        df = get_price_history(db, symbol, period="1y")

        if df is None or df.empty:
            continue

        r = df["Close"].pct_change().dropna()

        vol = r.std()

        vols.append(vol)

    if not vols:
        return None

    inv_vol = 1 / np.array(vols)

    weights = inv_vol / inv_vol.sum()

    return pd.DataFrame({
        "symbol": symbols[:len(weights)],
        "weight": weights
    })