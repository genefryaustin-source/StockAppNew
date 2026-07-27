import pandas as pd
def build_target_weights(snapshots):
    rows = []

    for s in snapshots:
        signal = s.signal or "Hold"
        confidence = s.confidence_score or 0

        # base weight logic
        weight = 0.0

        if signal in ["Strong Buy"]:
            weight = 0.08
        elif signal in ["Buy"]:
            weight = 0.05
        elif signal in ["Hold"]:
            weight = 0.02
        elif signal in ["Sell"]:
            weight = 0.0
        elif signal in ["Strong Sell"]:
            weight = 0.0

        # confidence scaling
        weight *= (confidence / 100)

        if weight > 0:
            rows.append({
                "Symbol": s.symbol,
                "Target Weight": weight
            })

    if not rows:
        return None

    df = pd.DataFrame(rows)

    # normalize weights
    total = df["Target Weight"].sum()
    if total > 0:
        df["Target Weight"] /= total

    return df