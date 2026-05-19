import requests
from datetime import datetime, timedelta
from modules.utils.config import get_secret


# --------------------------------------------------
# NEWS
# --------------------------------------------------
def get_finnhub_news(symbol: str):

    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []

    try:
        today = datetime.utcnow()
        start = today - timedelta(days=7)

        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": symbol,
                "from": start.strftime("%Y-%m-%d"),
                "to": today.strftime("%Y-%m-%d"),
                "token": key,
            },
            timeout=6,
        )

        data = r.json()

        if not isinstance(data, list):
            return []

        return data[:10]

    except Exception as e:
        print("FINNHUB NEWS ERROR:", e)
        return []


# --------------------------------------------------
# SENTIMENT
# --------------------------------------------------
def get_finnhub_sentiment(symbol: str):

    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return {}

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news-sentiment",
            params={
                "symbol": symbol,
                "token": key,
            },
            timeout=6,
        )

        data = r.json()

        # Finnhub returns nested structure
        sentiment = data.get("sentiment", {})

        if not sentiment:
            return {}

        return {
            "bullish": float(sentiment.get("bullishPercent", 0) or 0),
            "bearish": float(sentiment.get("bearishPercent", 0) or 0),
            "score": float(sentiment.get("score", 0) or 0),
        }

    except Exception as e:
        print("FINNHUB SENTIMENT ERROR:", e)
        return {}

def derive_sentiment_from_news(news_items):
        if not news_items:
            return 0.0

        bullish_words = [
            "beat", "growth", "strong", "upgrade", "outperform",
            "positive", "record", "surge", "bullish"
        ]

        bearish_words = [
            "miss", "decline", "weak", "downgrade", "underperform",
            "negative", "drop", "fall", "bearish"
        ]

        score = 0

        for n in news_items:
            text = (n.get("headline", "") + " " + n.get("summary", "")).lower()

            if any(w in text for w in bullish_words):
                score += 1
            elif any(w in text for w in bearish_words):
                score -= 1

        return score / max(len(news_items), 1)