from __future__ import annotations

from datetime import datetime, timedelta
from typing import List
import time

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from modules.market_data.models import PriceHistory


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

    if df is None or df.empty:
        return

    symbol = symbol.upper()

    for _, row in df.iterrows():

        stmt = insert(PriceHistory).values(
            symbol=symbol,
            date=row["Date"],
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]) if row["Volume"] else None,
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

    db.commit()


# ---------------------------------------------------
# Batch Yahoo downloader
# ---------------------------------------------------

def download_price_batch(symbols, batch_size=5, pause=3):

    """
    Download price history in controlled batches
    to avoid Yahoo rate limits.
    """

    results = {}

    if not symbols:
        return results

    end = datetime.utcnow()
    start = end - timedelta(days=365 * 5)

    for i in range(0, len(symbols), batch_size):

        batch = symbols[i:i + batch_size]

        try:

            data = yf.download(
                tickers=" ".join(batch),
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            if data is None or data.empty:

                print("Yahoo returned empty data")

                time.sleep(10)

                continue

            # single ticker case
            if len(batch) == 1:

                df = data.dropna()

                if not df.empty:
                    results[batch[0]] = df

            else:

                for sym in batch:

                    try:

                        df = data[sym].dropna()

                        if not df.empty:
                            results[sym] = df

                    except Exception:
                        continue

        except Exception as e:

            if "RateLimit" in str(e) or "Too Many Requests" in str(e):

                print("Yahoo rate limit hit, sleeping 30s")

                time.sleep(30)

                continue

            print("YAHOO DOWNLOAD ERROR", e)

        time.sleep(pause)

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