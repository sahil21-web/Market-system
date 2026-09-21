"""
Weighted composite scoring, adapted from a professional swing-trading rubric
(Trend/Momentum/Volume/Price-Action/Fundamentals). Two categories from the
original rubric — News/Catalyst and Options/Derivatives — aren't computable
from free data at full-universe scale, so their weight is redistributed
proportionally across the categories we CAN measure honestly, rather than
faked with a placeholder number. This produces a tighter, higher-quality
shortlist instead of a long "3/3 passed" list.
"""
import pandas as pd
from . import data

# Raw max points per category before rescaling to 0-100
MAX_TREND = 25
MAX_MOMENTUM = 15
MAX_VOLUME = 15
MAX_PRICE_ACTION = 15
MAX_FUNDAMENTALS = 10
RAW_MAX = MAX_TREND + MAX_MOMENTUM + MAX_VOLUME + MAX_PRICE_ACTION + MAX_FUNDAMENTALS  # 80

MIN_SCORE_TO_SHOW = 65  # matches the professional rubric's "below 70 = ignore" spirit


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def _weekly_trend_ok(df):
    if df is None or len(df) < 80:
        return None
    weekly = df["Close"].resample("W").last().dropna()
    if len(weekly) < 11:
        return None
    weekly_ma10 = weekly.rolling(10).mean()
    return bool(weekly.iloc[-1] > weekly_ma10.iloc[-1])


def screen_stock(ticker):
    df = data.get_history(ticker, period="1y")
    if df is None or len(df) < 210:
        return None  # need enough history for a real 200-day trend read

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA100"] = df["Close"].ewm(span=100).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["RSI14"] = _rsi(df["Close"])
    df["VolAvg20"] = df["Volume"].rolling(20).mean()
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACDSignal"] = df["MACD"].ewm(span=9).mean()

    last = df.iloc[-1]
    close = float(last["Close"])
    breakdown = {}

    # --- TREND (25) ---
    trend_pts = 0
    if close > last["EMA20"]:
        trend_pts += 5
    if last["EMA20"] > last["EMA50"]:
        trend_pts += 5
    if close > last["EMA100"]:
        trend_pts += 5
    if close > last["EMA200"]:
        trend_pts += 5
    high_52w = float(df["Close"].max())
    near_high = close >= 0.85 * high_52w
    if near_high:
        trend_pts += 5
    breakdown["trend"] = f"{trend_pts}/{MAX_TREND}"

    # --- MOMENTUM (15) ---
    momentum_pts = 0
    rsi_val = float(last["RSI14"])
    if 50 <= rsi_val <= 70:
        momentum_pts += 5
    elif rsi_val > 70:
        momentum_pts += 2  # overbought — some credit, flagged as risk later
    macd_bullish = bool(last["MACD"] > last["MACDSignal"])
    if macd_bullish:
        momentum_pts += 5
    if len(df) > 22:
        roc21 = 100 * (close - float(df["Close"].iloc[-22])) / float(df["Close"].iloc[-22])
        if roc21 > 0:
            momentum_pts += 5
    breakdown["momentum"] = f"{momentum_pts}/{MAX_MOMENTUM}"

    # --- VOLUME (15) ---
    volume_pts = 0
    vol_avg20 = float(last["VolAvg20"]) if pd.notna(last["VolAvg20"]) else None
    vol_ratio = float(last["Volume"]) / vol_avg20 if vol_avg20 else 0
    if vol_ratio >= 2:
        volume_pts = 15
    elif vol_ratio >= 1.5:
        volume_pts = 10
    elif vol_ratio >= 1.2:
        volume_pts = 5
    breakdown["volume"] = f"{volume_pts}/{MAX_VOLUME}"

    # --- PRICE ACTION (15): weekly trend + higher-high structure proxy ---
    price_action_pts = 0
    weekly_ok = _weekly_trend_ok(df)
    if weekly_ok:
        price_action_pts += 7
    if len(df) > 40:
        recent_high = float(df["High"].iloc[-20:].max())
        prior_high = float(df["High"].iloc[-40:-20].max())
        if recent_high > prior_high:
            price_action_pts += 8
    breakdown["price_action"] = f"{price_action_pts}/{MAX_PRICE_ACTION}"

    # --- FUNDAMENTALS (10): quick sanity check, not a full screen ---
    fundamentals_pts = 0
    info = data.get_info(ticker)
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    if roe is not None and roe >= 0.15:
        fundamentals_pts += 5
    if rev_growth is not None and rev_growth >= 0.15:
        fundamentals_pts += 5
    breakdown["fundamentals"] = f"{fundamentals_pts}/{MAX_FUNDAMENTALS}"

    raw_score = trend_pts + momentum_pts + volume_pts + price_action_pts + fundamentals_pts
    scaled_score = round(100 * raw_score / RAW_MAX, 1)

    # Risk penalty — deliberately conservative, only the things we can actually check
    risk_penalty = 0
    risk_notes = []
    if rsi_val > 78:
        risk_penalty += 5
        risk_notes.append("RSI overbought (>78)")
    if weekly_ok is False:
        risk_penalty += 5
        risk_notes.append("weekly trend not confirming")

    final_score = round(max(0, scaled_score - risk_penalty), 1)

    if final_score < MIN_SCORE_TO_SHOW:
        return None

    if final_score >= 85:
        label, stars = "Exceptional", "★★★★★"
    elif final_score >= 75:
        label, stars = "Strong", "★★★★"
    else:
        label, stars = "Watchlist", "★★★"

    atr14 = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
    suggested_stop = round(close - 2 * atr14, 2)
    risk = close - suggested_stop
    suggested_target = round(close + 2 * risk, 2)

    return {
        "ticker": ticker,
        "close": round(close, 2),
        "score": final_score,
        "label": label,
        "stars": stars,
        "breakdown": breakdown,
        "risk_notes": risk_notes,
        "suggested_stop": suggested_stop,
        "suggested_target": suggested_target,
        "risk_reward": 2.0,
    }


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        r = screen_stock(t)
        if r:
            hits.append(r)
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits
