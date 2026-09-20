"""
Pulls the full NSE 500 stock list automatically from NSE's own public data,
so the screeners scan the real market instead of a hand-picked 50 names.
Falls back to config/watchlist.json if the live fetch fails for any reason
(NSE occasionally blocks scripted requests) so the system never breaks.
"""
import io
import requests
import pandas as pd

NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,*/*",
}


def fetch_nifty500(limit=None):
    """Returns a list of tickers like ['RELIANCE.NS', ...] or None on failure."""
    try:
        resp = requests.get(NIFTY500_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        symbols = df["Symbol"].dropna().astype(str).str.strip().unique().tolist()
        tickers = [f"{s}.NS" for s in symbols]
        if limit:
            tickers = tickers[:limit]
        return tickers
    except Exception as e:
        print(f"[universe] Live NSE 500 fetch failed ({e}); will fall back to config/watchlist.json")
        return None
