import numpy as np
import pandas as pd


def risk_parity_weights(price_cache, symbols):
    # NOTE: this used to ignore price_cache entirely and fetch fresh via
    # get_price_history(db, ...) -- but it imported `db` as `from modules
    # import db` (the package itself, not a session), which crashed with
    # AttributeError on every call. black_litterman_weights() already reads
    # price_cache correctly; do the same here for consistency, and so both
    # models share one (page-level) price-loading path.
    vols = []
    used_symbols = []

    for s in symbols:
        df = price_cache.get(s)

        if df is None or df.empty:
            continue

        r = df["Close"].pct_change().dropna()

        if r.empty:
            continue

        vol = r.std()

        if vol is None or vol == 0 or pd.isna(vol):
            continue

        vols.append(vol)
        used_symbols.append(s)

    if not vols:
        return None

    inv_vol = 1 / np.array(vols)

    weights = inv_vol / inv_vol.sum()

    return pd.DataFrame({
        "symbol": used_symbols,
        "weight": weights
    })