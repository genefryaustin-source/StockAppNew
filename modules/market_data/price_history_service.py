from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import List
import time

import pandas as pd

from sqlalchemy.orm import Session

from modules.market_data.models import PriceHistory
from modules.market_data.providers.finnhub_provider import (
    get_history as finnhub_history,
)

from modules.market_data.providers.twelvedata_provider import (
    get_history as twelvedata_history,
)
from modules.utils.symbol_classifier import (
    filter_supported_equities,
)
# ---------------------------------------------------
# Load price history from DB
# ---------------------------------------------------

def load_price_history(db: Session, symbol: str) -> pd.DataFrame | None:

    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.symbol == symbol)
        .order_by(PriceHistory.date.asc())
        .all()
    )

    if not rows:
        return None

    data = {
        "Date": [],
        "Open": [],
        "High": [],
        "Low": [],
        "Close": [],
        "Volume": [],
    }

    for r in rows:

        data["Date"].append(r.date)
        data["Open"].append(r.open)
        data["High"].append(r.high)
        data["Low"].append(r.low)
        data["Close"].append(r.close)
        data["Volume"].append(r.volume)

    df = pd.DataFrame(data)

    df.set_index("Date", inplace=True)

    return df


# ---------------------------------------------------
# Store price history to DB
# ---------------------------------------------------

from sqlalchemy.dialects.sqlite import insert

def store_price_history(db, symbol, df):
    df = df.copy()

    if df is None or df.empty:
        return

    # -----------------------------------
    # Flatten MultiIndex columns
    # -----------------------------------

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            str(c[0]).strip()
            for c in df.columns
        ]

    # -----------------------------------
    # Normalize column names
    # -----------------------------------

    df.columns = [
        str(c).strip().title()
        for c in df.columns
    ]

    # -----------------------------------
    # Normalize index -> Date column
    # -----------------------------------

    if "Date" not in df.columns:

        if isinstance(df.index, pd.MultiIndex):

            try:
                df = df.reset_index()

            except Exception:
                pass

        elif df.index.name is not None:

            df = df.reset_index()

        else:

            df = df.reset_index().rename(
                columns={"index": "Date"}
            )

    # -----------------------------------
    # Normalize columns AGAIN after reset
    # -----------------------------------

    df.columns = [
        str(c).strip().title()
        for c in df.columns
    ]

    # -----------------------------------
    # Ensure required columns exist
    # -----------------------------------

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        print(
            "PRICE HISTORY MISSING COLUMNS",
            symbol,
            missing,
            df.columns.tolist(),
        )

        return

    symbol = symbol.upper()

    for _, row in df.iterrows():

        stmt = insert(PriceHistory).values(
            symbol=symbol,
            date=pd.to_datetime(row["Date"]),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=(
                int(row["Volume"])
                if (
                        "Volume" in row
                        and pd.notna(row["Volume"])
                )
                else None
            ),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )

        db.execute(stmt)




# ---------------------------------------------------
# Batch downloader
# ---------------------------------------------------

def download_price_batch(
    symbols,
    batch_size=5,
    pause=1,
):

    """
    Multi-provider institutional price loader.

    Provider priority:
    1. Finnhub
    2. TwelveData

    Returns:
        {
            "AAPL": DataFrame,
            ...
        }
    """



    PROVIDERS = [

        finnhub_history,

        twelvedata_history,
    ]

    results = {}

    if not symbols:
        return results

    symbols = filter_supported_equities(
        symbols
    )

    total = len(symbols)

    print(
        f"🚀 DOWNLOAD PRICE BATCH START "
        f"({total} symbols)"
    )

    for i, symbol in enumerate(symbols):

        print(
            f"📈 [{i+1}/{total}] "
            f"{symbol}"
        )
        # -----------------------------------
        # Skip unsupported OTC/warrant/etc
        # -----------------------------------

        bad_suffixes = (
            "W",
            "WS",
            "U",
            "R",
        )

        if (
                len(symbol) > 5
                and symbol.endswith(bad_suffixes)
        ):
            continue
        success = False

        for provider in PROVIDERS:

            try:

                print(
                    "🔎 TRY PROVIDER:",
                    provider.__name__,
                    symbol,
                )

                df = provider(
                    symbol=symbol,
                    period="1y",
                    interval="1d",
                )

                if (
                    isinstance(df, pd.DataFrame)
                    and not df.empty
                ):

                    results[symbol] = df

                    print(
                        "✅ PROVIDER SUCCESS:",
                        provider.__name__,
                        symbol,
                        len(df),
                    )

                    success = True

                    break

                else:

                    print(
                        "⚠️ EMPTY DATA:",
                        provider.__name__,
                        symbol,
                    )

            except Exception as e:

                print(
                    "❌ PROVIDER FAILED:",
                    provider.__name__,
                    symbol,
                    e,
                )

        if not success:

            print(
                "❌ ALL PROVIDERS FAILED:",
                symbol,
            )

        time.sleep(pause)

    print(
        f"✅ DOWNLOAD COMPLETE: "
        f"{len(results)} / {total}"
    )

    return results


# ---------------------------------------------------
# Close matrix loader
# ---------------------------------------------------

def load_close_matrix(db: Session, symbols: list[str]) -> pd.DataFrame:

    if not symbols:
        return pd.DataFrame()

    rows = (
        db.query(
            PriceHistory.symbol,
            PriceHistory.date,
            PriceHistory.close,
        )
        .filter(PriceHistory.symbol.in_(symbols))
        .order_by(PriceHistory.date.asc())
        .all()
    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [(r.symbol, r.date, r.close) for r in rows],
        columns=["symbol", "date", "close"],
    )

    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot(index="date", columns="symbol", values="close")

    pivot.index = pd.to_datetime(pivot.index)

    pivot = pivot.sort_index()

    return pivot