# screener.py in Institutional
import pandas as pd
from sqlalchemy.orm import Session

from modules.market_data.service import get_price_history


def run_screener(
    db: Session,
    tenant_id: str,
    symbols: list[str],
    period: str = "6mo",
    interval: str = "1d",
    min_price: float = None,
):

    results = []

    for symbol in symbols:

        try:

            df = get_price_history(
                db,
                symbol,
                period=period,
                interval=interval,
            )

            if df is None or df.empty:
                continue

            last = df.iloc[-1]

            price = float(last["Close"])

            if min_price is not None and price < min_price:
                continue

            results.append(
                {
                    "Symbol": symbol,
                    "Price": price,
                    "Volume": float(last.get("Volume", 0)),
                }
            )

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("Price", ascending=False)