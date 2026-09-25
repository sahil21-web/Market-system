"""
Weighted composite scoring, adapted from a professional swing-trading rubric
(Trend/Momentum/Volume/Price-Action/Fundamentals). Two categories from the
original rubric — News/Catalyst and Options/Derivatives — aren't computable
from free data at full-universe scale, so their weight is redistributed
proportionally across the categories we CAN measure honestly, rather than
faked with a placeholder number.

v3 changes (after a live run showed 50/297 stocks called "Exceptional",
many tied at identical scores, some with 0/10 fundamentals):
  1. Momentum, Volume, and Price Action are now continuous curves instead
     of 3-4 coarse buckets — two stocks with genuinely different setups no
     longer land on the exact same score just because they cleared the
     same boolean thresholds.
  2. Fundamentals is also continuous (scaled by how far past the bar a
     stock is, capped) rather than all-or-nothing.
  3. Hard floor: a stock cannot be labeled "Exceptional" or "Strong"
     unless Fundamentals >= 3/10 — a technically perfect setup with zero
     fundamental confirmation is now capped at "Watchlist" and flagged,
     instead of being called the top label.
"""
import pandas as pd
from . import data, stage_analysis

MAX_TREND = 25
MAX_MOMENTUM = 15
MAX_VOLUME = 15
MAX_PRICE_ACTION = 15
MAX_FUNDAMENTALS = 10
RAW_MAX = MAX_TREND + MAX_MOMENTUM + MAX_VOLUME + MAX_PRICE_ACTION + MAX_FUNDAMENTALS  # 80

MIN_SCORE_TO_SHOW = 55
FUNDAMENTALS_FLOOR_FOR_TOP_LABELS = 3  # out of 10 — below this, cap the label


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


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


def screen_stock(ticker, df=None):
    """df can be passed directly (used by backtest.py on historical
    slices) — when omitted, fetches live data as normal."""
    if df is None:
        df = data.get_history(ticker, period="1y")
    if df is None or len(df) < 210:
        return None

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

    # --- TREND (25) — boolean structure checks; 6 distinct levels is fine,
    # trend is genuinely a step function (either aligned or not) ---
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
    # Stage Analysis (Weinstein/Minervini) replaces the flat "near 52w high"
    # bonus: being near the high isn't itself the reward signal — being
    # EARLY in a rising trend is. A stock near highs with strong conviction
    # (good volume, fundamentals, trend) still scores well here — this only
    # penalizes being FAR above a rising average with nothing else backing
    # it up (see risk_notes below), not "near highs" as a blanket rule.
    near_high = close >= 0.85 * high_52w
    if near_high:
        trend_pts += 5
    breakdown["trend"] = f"{trend_pts}/{MAX_TREND}"

    stage_info = stage_analysis.classify_stage(df)

    # --- MOMENTUM (15) — continuous ---
    rsi_val = float(last["RSI14"])
    if 50 <= rsi_val <= 65:
        rsi_pts = 6.0
    elif 65 < rsi_val <= 78:
        rsi_pts = 6.0 - 4.0 * (rsi_val - 65) / 13.0   # tapers 6 -> 2 as it gets overbought
    elif rsi_val > 78:
        rsi_pts = 1.0                                  # still some credit, risk flagged separately
    elif 35 <= rsi_val < 50:
        rsi_pts = 6.0 * (rsi_val - 35) / 15.0           # building momentum, not confirmed yet
    else:
        rsi_pts = 0.0

    macd_bullish = bool(last["MACD"] > last["MACDSignal"])
    macd_pts = 5.0 if macd_bullish else 0.0

    roc_pts = 0.0
    if len(df) > 22:
        prior_close = float(df["Close"].iloc[-22])
        roc21 = 100 * (close - prior_close) / prior_close if prior_close else 0
        roc_pts = _clip(roc21 / 20.0 * 4.0, 0.0, 4.0)   # +20% or more over 21 sessions = full marks

    momentum_pts = round(rsi_pts + macd_pts + roc_pts, 1)
    breakdown["momentum"] = f"{momentum_pts}/{MAX_MOMENTUM}"

    # --- VOLUME (15) — continuous ratio to 20-day average ---
    vol_avg20 = float(last["VolAvg20"]) if pd.notna(last["VolAvg20"]) else None
    vol_ratio = float(last["Volume"]) / vol_avg20 if vol_avg20 else 0
    volume_pts = round(_clip(15.0 * (vol_ratio - 1.0) / 1.5, 0.0, 15.0), 1)
    breakdown["volume"] = f"{volume_pts}/{MAX_VOLUME}"

    # --- PRICE ACTION (15): weekly trend (boolean, 7) + breakout magnitude
    # (continuous, 8 — a bigger new high above the prior 20-day high scores
    # higher than a marginal one, instead of both getting the same flat 8) ---
    weekly_ok = _weekly_trend_ok(df)
    weekly_pts = 7.0 if weekly_ok else 0.0

    breakout_pts = 0.0
    if len(df) > 40:
        recent_high = float(df["High"].iloc[-20:].max())
        prior_high = float(df["High"].iloc[-40:-20].max())
        if prior_high > 0 and recent_high > prior_high:
            pct_new_high = (recent_high / prior_high - 1.0)
            breakout_pts = _clip(pct_new_high * 20.0 * 8.0, 0.0, 8.0)  # 5%+ new high = full marks

    price_action_pts = round(weekly_pts + breakout_pts, 1)
    breakdown["price_action"] = f"{price_action_pts}/{MAX_PRICE_ACTION}"

    # --- FUNDAMENTALS (10) — continuous, scaled by how far past the bar,
    # each sub-check capped at 5 so a huge ROE doesn't dominate ---
    info = data.get_info(ticker)
    roe = info.get("returnOnEquity")
    rev_growth = info.get("revenueGrowth")
    roe_pts = _clip(5.0 * (roe / 0.15), 0.0, 5.0) if roe is not None else 0.0
    rev_pts = _clip(5.0 * (rev_growth / 0.15), 0.0, 5.0) if rev_growth is not None else 0.0
    fundamentals_pts = round(roe_pts + rev_pts, 1)
    breakdown["fundamentals"] = f"{fundamentals_pts}/{MAX_FUNDAMENTALS}"

    raw_score = trend_pts + momentum_pts + volume_pts + price_action_pts + fundamentals_pts
    scaled_score = round(100 * raw_score / RAW_MAX, 1)

    risk_penalty = 0
    risk_notes = []
    if rsi_val > 78:
        risk_penalty += 5
        risk_notes.append("RSI overbought (>78)")
    if weekly_ok is False:
        risk_penalty += 5
        risk_notes.append("weekly trend not confirming")

    fundamentals_weak = fundamentals_pts < FUNDAMENTALS_FLOOR_FOR_TOP_LABELS
    if fundamentals_weak:
        risk_notes.append("fundamentals unconfirmed/weak — technical-only setup")

    # This is the real fix for "recommends stocks that are already at the
    # top": a stock isn't penalized just for being near a high (that's the
    # "conviction" case — strong volume/fundamentals/trend near a high is
    # fine). It's penalized only when it's been extended a LONG WAY above
    # its own rising 30-week average with nothing else backing it up —
    # that's chasing, not conviction.
    extended_and_risky = False
    if stage_info and stage_info["stage"] == "2B_extended_advance" and stage_info["pct_above_30w_avg"] > 30:
        risk_penalty += 8
        extended_and_risky = True
        risk_notes.append(f"extended {stage_info['pct_above_30w_avg']}% above 30-week avg — chasing risk, not conviction")

    final_score = round(max(0, scaled_score - risk_penalty), 1)

    if final_score >= 85 and not fundamentals_weak and not extended_and_risky:
        label, stars = "Exceptional", "★★★★★"
    elif final_score >= 75 and not fundamentals_weak and not extended_and_risky:
        label, stars = "Strong", "★★★★"
    elif final_score >= 65:
        label, stars = "Watchlist", "★★★"
    else:
        label, stars = "Early / unconfirmed", "★★"

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
        "stage": stage_info["stage"] if stage_info else "unknown",
        "stage_note": stage_info["note"] if stage_info else "",
        "suggested_stop": suggested_stop,
        "suggested_target": suggested_target,
        "risk_reward": 2.0,
    }


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        try:
            r = screen_stock(t)
        except Exception as e:
            print(f"[cash_screener] skipped {t}: {e}")
            r = None
        if r:
            hits.append(r)
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits
