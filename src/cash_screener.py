"""
Rule-based cash-flow (swing) screener. No AI, no guessing — just the same
three checks applied consistently to every stock in your watchlist:
  1. Price above both 20-day and 50-day EMA (uptrend)
  2. RSI(14) has crossed above 55 in the last 3 sessions (fresh momentum)
  3. Today's volume is at least 1.5x the 20-day average volume (real interest)
"""
import pandas as pd
from . import data


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def screen_stock(ticker):
    df = data.get_history(ticker, period="6mo")
    if df is None or len(df) < 60:
        return None

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["RSI14"] = _rsi(df["Close"])
    df["VolAvg20"] = df["Volume"].rolling(20).mean()

    last = df.iloc[-1]
    rsi_recent = df["RSI14"].iloc[-4:-1]

    trend_ok = bool(last["Close"] > last["EMA20"] > last["EMA50"])
    rsi_cross = bool((rsi_recent < 55).any() and last["RSI14"] >= 55)
    volume_ok = bool(last["Volume"] >= 1.5 * last["VolAvg20"]) if pd.notna(last["VolAvg20"]) else False

    checks_passed = sum([trend_ok, rsi_cross, volume_ok])

    if checks_passed >= 2:
        # ATR-based stop, and a target built to a fixed 2:1 reward:risk from
        # that same ATR distance — this is a constructed R:R, not a "found"
        # resistance level, and is labelled as such.
        high_low = df["High"] - df["Low"]
        atr14 = high_low.rolling(14).mean().iloc[-1]
        close_price = float(last["Close"])
        suggested_stop = round(close_price - 2 * atr14, 2)
        risk = close_price - suggested_stop
        suggested_target = round(close_price + 2 * risk, 2)  # 2:1 reward:risk by construction
        return {
            "ticker": ticker,
            "close": round(close_price, 2),
            "trend_ok": trend_ok,
            "rsi_cross": rsi_cross,
            "volume_ok": volume_ok,
            "checks_passed": checks_passed,
            "suggested_stop": suggested_stop,
            "suggested_target": suggested_target,
            "risk_reward": 2.0,
        }
    return None


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        r = screen_stock(t)
        if r:
            hits.append(r)
    hits.sort(key=lambda x: (x["checks_passed"], x["close"]), reverse=True)
    return hits
