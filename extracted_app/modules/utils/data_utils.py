import pandas as pd


import pandas as pd

def normalize_timeseries_df(df):
    if isinstance(df, pd.DataFrame):
        out = df.copy()
    else:
        out = pd.DataFrame(df)

    # ---------------------------------
    # HANDLE EMPTY DATAFRAME SAFELY
    # ---------------------------------
    if out.empty:
        # Create empty Date column to prevent downstream errors
        out["Date"] = pd.Series(dtype="datetime64[ns]")
        return out

    # ---------------------------------
    # NORMALIZE DATE COLUMN
    # ---------------------------------
    if "Date" not in out.columns:
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.reset_index()
        else:
            raise KeyError("Missing Date column")

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")

    return out.dropna(subset=["Date"])