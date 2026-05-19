# technicals_service.py in Data
import pandas as pd
from modules.data.models import TechnicalIndicator, PriceHistory


def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ingest_technicals(db, symbol):

    prices = (
        db.query(PriceHistory)
        .filter(PriceHistory.symbol == symbol)
        .order_by(PriceHistory.date)
        .all()
    )

    if not prices:
        return False

    df = pd.DataFrame(
        [(p.date, p.close) for p in prices],
        columns=["date", "close"]
    ).set_index("date")

    df["rsi"] = compute_rsi(df["close"])
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()

    for date, row in df.iterrows():
        exists = (
            db.query(TechnicalIndicator)
            .filter(
                TechnicalIndicator.symbol == symbol,
                TechnicalIndicator.date == date
            )
            .first()
        )

        if exists:
            continue

        db.add(
            TechnicalIndicator(
                symbol=symbol,
                date=date,
                rsi=row["rsi"],
                sma_50=row["sma_50"],
                sma_200=row["sma_200"],
            )
        )

    db.commit()
    return True