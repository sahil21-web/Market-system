"""
Checks your actual holdings (config/portfolio.json) against exit rules.
Cash-flow positions get a hard price-based rule (ATR trailing stop / EMA break).
Wealth positions never get an automatic price-based exit — only a flag to
review, because a falling price alone is not a reason to sell a compounder.
"""
from . import data


def check_holding(holding):
    ticker = holding["ticker"]
    engine = holding.get("engine", "cash_flow")
    df = data.get_history(ticker, period="6mo")
    if df is None or len(df) < 60:
        return {"ticker": ticker, "status": "NO DATA", "note": "could not fetch price history"}

    df["EMA50"] = df["Close"].ewm(span=50).mean()
    high_low = df["High"] - df["Low"]
    atr14 = float(high_low.rolling(14).mean().iloc[-1])
    close = float(df["Close"].iloc[-1])
    ema50 = float(df["EMA50"].iloc[-1])

    # ATR trailing stop off the highest close since we started tracking (approx: last 6mo high)
    highest_close = float(df["Close"].max())
    trailing_stop = highest_close - 2 * atr14

    result = {
        "ticker": ticker,
        "engine": engine,
        "close": round(close, 2),
        "ema50": round(ema50, 2),
        "trailing_stop_level": round(trailing_stop, 2),
    }

    if engine == "cash_flow":
        if close < trailing_stop or close < ema50:
            result["status"] = "🔴 EXIT SIGNAL"
            result["note"] = "Price broke trailing stop or 50-EMA. Rule says close the position."
        else:
            result["status"] = "🟢 HOLD"
            result["note"] = "Still above trailing stop and 50-EMA."
    else:  # wealth
        if close < ema50:
            result["status"] = "🟡 REVIEW"
            result["note"] = "Price weak vs 50-EMA — check if this is business deterioration or just noise. No auto-exit for wealth positions."
        else:
            result["status"] = "🟢 HOLD"
            result["note"] = "Price trend fine. No action needed."

    return result


def run_monitor():
    holdings = data.load_portfolio()
    return [check_holding(h) for h in holdings if h.get("ticker") != "EXAMPLE.NS"]
