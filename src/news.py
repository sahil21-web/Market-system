"""
Pulls recent real headlines for a stock so the AI research step reads actual
current news, not just a static company description. yfinance's news field
format has changed across versions, so this handles both shapes defensively.
"""
import yfinance as yf


def get_recent_headlines(ticker, limit=5):
    try:
        t = yf.Ticker(ticker)
        raw = t.news or []
    except Exception:
        return []

    headlines = []
    for item in raw[:limit]:
        title = item.get("title")
        if not title:
            # newer yfinance nests it under "content"
            title = (item.get("content") or {}).get("title")
        if title:
            headlines.append(title)
    return headlines
