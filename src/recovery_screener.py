"""
A different question from the wealth screener: not "is this a great business"
but "has the PRICE fallen more than the BUSINESS has" — i.e. good fundamentals,
temporarily beaten down, not merely cheap or oversold. Runs weekly alongside
the wealth screen. Reuses the same quality bar (ROE, revenue growth, debt) as
wealth_screener.py, then adds a distance-from-52-week-high filter.
"""
from . import data

MIN_ROE = 0.15
MIN_REVENUE_GROWTH = 0.10  # slightly looser than the wealth screen — a real
                            # dip can temporarily depress growth optics too
MIN_FALL_PCT = 15   # at least 15% below 52-week high to be interesting
MAX_FALL_PCT = 50   # beyond this, more likely a genuine problem than a dip


def screen_stock(ticker):
    df = data.get_history(ticker, period="1y")
    if df is None or len(df) < 100:
        return None

    close = float(df["Close"].iloc[-1])
    high_52w = float(df["Close"].max())
    if high_52w == 0:
        return None
    fall_pct = round(100 * (high_52w - close) / high_52w, 1)

    if not (MIN_FALL_PCT <= fall_pct <= MAX_FALL_PCT):
        return None

    info = data.get_info(ticker)
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    debt_to_equity = info.get("debtToEquity")

    if roe is None or rev_growth is None:
        return None  # not enough data to judge fundamentals — skip, don't guess

    roe_ok = roe >= MIN_ROE
    growth_ok = rev_growth >= MIN_REVENUE_GROWTH
    debt_ok = (debt_to_equity is None) or (debt_to_equity <= 100)

    checks_passed = sum([roe_ok, growth_ok, debt_ok])
    if checks_passed < 2:
        return None  # fell AND fundamentals are also shaky — likely not a dip, a real problem

    # Is selling pressure stabilizing? Rough proxy: last 10 days' range narrower
    # than the prior 10 days' range (a real signal, not a guess)
    recent_range = float(df["High"].iloc[-10:].max() - df["Low"].iloc[-10:].min())
    prior_range = float(df["High"].iloc[-20:-10].max() - df["Low"].iloc[-20:-10].min())
    stabilizing = recent_range < prior_range

    return {
        "ticker": ticker,
        "close": round(close, 2),
        "high_52w": round(high_52w, 2),
        "fall_from_high_pct": fall_pct,
        "roe_pct": round(roe * 100, 1),
        "revenue_growth_pct": round(rev_growth * 100, 1),
        "debt_to_equity": debt_to_equity,
        "checks_passed": checks_passed,
        "selling_stabilizing": stabilizing,
    }


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        r = screen_stock(t)
        if r:
            hits.append(r)
    # prefer stronger fundamentals first, then bigger (but not extreme) discount
    hits.sort(key=lambda x: (x["checks_passed"], x["fall_from_high_pct"]), reverse=True)
    return hits
