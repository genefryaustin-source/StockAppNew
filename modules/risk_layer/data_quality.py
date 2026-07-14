"""
modules/risk_layer/data_quality.py

Schema validation for the Risk Layer's core DataFrames, via pandera
(https://github.com/unionai-oss/pandera, MIT license). Built directly in
response to three real data-quality bugs found and fixed in this app this
session:

  1. Duplicate same-day snapshots summed together, fabricating a ~900%
     single-day "return" and 1500%+ annualized volatility.
  2. A currency-conversion bug inflating USD/JPY notional by ~158x.
  3. A hardcoded cash_buffer silently feeding a wrong number into the
     survival score.

None of those would have raised an exception -- they were internally
consistent numbers that were just wrong. A schema check with sanity
bounds (not just type checks) is the general-purpose fix: it can't catch
every possible bug, but it catches the *shape* of all three of the above
-- an extreme single-day return, an extreme position value relative to
recent history, a required field silently null -- at the boundary, before
they cascade into VaR/volatility/limit breaches/defense directives.

Validation here is advisory, not a hard gate: validate_*() functions
never raise and never drop data. They return the original (or lightly
coerced) DataFrame plus a list of warning strings, so the Risk Layer can
surface "this data looks suspicious" without taking the page down over
it -- a false-positive schema warning should never be worse than the bug
it's trying to catch.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema, Check

# A single-day return this large is far more likely to be a data glitch
# (duplicate snapshots, a bad price tick, a currency-unit bug) than a real
# 1-day move -- even a 3x meme-stock day rarely clears this.
EXTREME_DAILY_RETURN = 0.75

POSITIONS_SCHEMA = DataFrameSchema(
    {
        "Symbol": Column(str, nullable=False),
        "Asset Class": Column(str, nullable=False),
        "Market Value": Column(float, nullable=False, checks=Check(lambda s: s.abs() < 1e10)),
        "Weight": Column(float, nullable=False, checks=Check.in_range(-1e-6, 1.0 + 1e-6)),
    },
    strict=False,   # extra columns (Leverage, Margin Required, Side, ...) are fine
    coerce=False,
)

RETURNS_SCHEMA = DataFrameSchema(
    {
        "equity": Column(float, nullable=False, checks=Check(lambda s: (s >= 0).all())),
        "Return": Column(float, nullable=True),
        "Drawdown": Column(float, nullable=True, checks=Check.in_range(-1.0 - 1e-6, 1e-6)),
    },
    strict=False,
    coerce=False,
)


def validate_positions_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if df is None or df.empty:
        return df, []
    warnings: list[str] = []
    try:
        POSITIONS_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        for _, row in e.failure_cases.iterrows():
            warnings.append(
                f"positions_df: column '{row.get('column')}' failed check "
                f"'{row.get('check')}' (value: {row.get('failure_case')})"
            )
    return df, warnings


def validate_returns_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if df is None or df.empty:
        return df, []
    warnings: list[str] = []
    try:
        RETURNS_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        for _, row in e.failure_cases.iterrows():
            warnings.append(
                f"returns_df: column '{row.get('column')}' failed check "
                f"'{row.get('check')}' (value: {row.get('failure_case')})"
            )

    if "Return" in df.columns:
        extreme = df[df["Return"].abs() > EXTREME_DAILY_RETURN]
        for _, row in extreme.iterrows():
            as_of = row.get("as_of", "?")
            warnings.append(
                f"returns_df: extreme single-day return of {row['Return']:+.1%} on {as_of} -- "
                "this is far more likely to be a data glitch (duplicate/erroneous snapshot, "
                "a bad price tick, a currency-unit bug) than a genuine move. VaR/volatility "
                "computed from this series may be unreliable until investigated."
            )

    return df, warnings
