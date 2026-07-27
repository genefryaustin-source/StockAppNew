# earnings_service.py in Data
import yfinance as yf
from modules.data.models import EarningsEvent


def ingest_earnings(db, symbol):

    ticker = yf.Ticker(symbol)
    cal = ticker.calendar

    if cal is None or cal.empty:
        return False

    event_date = cal.loc["Earnings Date"][0]

    exists = (
        db.query(EarningsEvent)
        .filter(
            EarningsEvent.symbol == symbol,
            EarningsEvent.event_date == event_date
        )
        .first()
    )

    if exists:
        return True

    db.add(
        EarningsEvent(
            symbol=symbol,
            event_date=event_date,
        )
    )

    db.commit()
    return True