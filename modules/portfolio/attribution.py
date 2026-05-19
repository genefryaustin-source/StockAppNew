import pandas as pd


def sector_attribution(rows, snapshots):

    data = []

    for r in rows:

        sym = r["symbol"]

        if sym not in snapshots:
            continue

        data.append(
            {
                "symbol": sym,
                "sector": snapshots[sym]["sector"],
                "value": r["value"],
            }
        )

    df = pd.DataFrame(data)

    if df.empty:
        return df

    return df.groupby("sector")["value"].sum().reset_index()