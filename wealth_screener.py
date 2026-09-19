"""
Fundamental screener for the wealth engine. Runs weekly since fundamentals
don't change daily. Uses yfinance's info fields — these are best-effort and
sometimes missing for NSE stocks, so the code skips instead of crashing when
a field isn't available.
"""
from . import data

MIN_ROE = 0.15          # 15%
MAX_DEBT_TO_EQUITY = 0.5 * 100  # yfinance reports debtToEquity as a plain ratio*100 sometimes; treated leniently below
MIN_REVENUE_GROWTH = 0.15  # 15% YoY


def screen_stock(ticker):
    info = data.get_info(ticker)
    if not info:
        return None

    roe = info.get("returnOnEquity")
    debt_to_equity = info.get("debtToEquity")
    revenue_growth = info.get("revenueGrowth")

    if roe is None or revenue_growth is None:
        return None  # not enough data to judge, skip rather than guess

    roe_ok = roe >= MIN_ROE
    growth_ok = revenue_growth >= MIN_REVENUE_GROWTH
    debt_ok = (debt_to_equity is None) or (debt_to_equity <= 100)  # D/E <= 1.0 as a loose filter

    passed = sum([roe_ok, growth_ok, debt_ok])
    if passed >= 2:
        return {
            "ticker": ticker,
            "roe_pct": round(roe * 100, 1),
            "revenue_growth_pct": round(revenue_growth * 100, 1),
            "debt_to_equity": debt_to_equity,
            "checks_passed": passed,
        }
    return None


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        r = screen_stock(t)
        if r:
            hits.append(r)
    hits.sort(key=lambda x: x["checks_passed"], reverse=True)
    return hits
