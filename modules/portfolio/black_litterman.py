import numpy as np
import pandas as pd


def compute_covariance(price_cache, symbols):

    returns = []

    for s in symbols:

        df = price_cache.get(s)

        if df is None or df.empty:
            continue

        r = df["Close"].pct_change().dropna()

        returns.append(r)

    if not returns:
        return None

    df = pd.concat(returns, axis=1)

    df.columns = symbols[:len(df.columns)]

    return df.cov()


def black_litterman_weights(price_cache, symbols):

    cov = compute_covariance(price_cache, symbols)

    if cov is None:
        return None

    inv = np.linalg.pinv(cov.values)

    ones = np.ones(len(symbols))

    w = inv @ ones

    w = w / np.sum(w)

    weights = pd.DataFrame({
        "symbol": symbols,
        "weight": w
    })

    return weights