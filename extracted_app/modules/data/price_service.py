# price_service.py in Data
import yfinance as yf
from modules.data.models import PriceHistory
from datetime import datetime


def ingest_price_history(db, symbol, period="5y"):

    data = yf.download(symbol, period=period)

    if data.empty:
        return False

    for index, row in data.iterrows():
        exists = (
            db.query(PriceHistory)
            .filter(
                PriceHistory.symbol == symbol,
                PriceHistory.date == index.date()
            )
            .first()
        )

        if exists:
            continue

        db.add(
            PriceHistory(
                symbol=symbol,
                date=index.date(),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"],
            )
        )

    db.commit()
    return True