"""
Data fetching helpers. Everything free: yfinance for prices, local JSON for config.
"""
import json
import os
import time
import pandas as pd
import yfinance as yf

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def load_watchlist():
    with open(os.path.join(CONFIG_DIR, "watchlist.json")) as f:
        return json.load(f)["tickers"]


def load_portfolio():
    with open(os.path.join(CONFIG_DIR, "portfolio.json")) as f:
        return json.load(f)["holdings"]


def get_history(ticker, period="1y", retries=2):
    """Fetch daily OHLCV history for one ticker. Returns None on failure
    instead of raising, so one bad ticker doesn't kill the whole daily run."""
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period=period, interval="1d",
                              progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception:
            time.sleep(1.5)
    return None


def get_info(ticker, retries=2):
    """Fetch fundamental snapshot for one ticker. Returns {} on failure."""
    for attempt in range(retries):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            return info
        except Exception:
            time.sleep(1.5)
    return {}
