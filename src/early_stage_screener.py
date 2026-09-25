"""
Finds stocks EARLY in a new advance — just breaking out of a base, not
already run up, and NOT still falling (that distinction matters: this only
fires on confirmed Stage 2A, price already back ABOVE a rising average — it
will never flag a stock still in decline, so it can't catch a falling knife).
Uses Minervini's VCP (Volatility Contraction Pattern) idea: volatility
tightens as sellers dry up, then expands on real breakout volume.
Deliberately complementary to cash_screener.py's momentum picks, not a
replacement for them.
"""
from . import data, stage_analysis


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def screen_stock(ticker):
    df = data.get_history(ticker, period="1y")
    if df is None or len(df) < 220:
        return None

    stage_info = stage_analysis.classify_stage(df)
    if stage_info is None or stage_info["stage"] != "2A_early_advance":
        return None  # ONLY fresh, confirmed-above-average breakouts — never a still-falling stock

    close = df["Close"]
    volume = df["Volume"]
    last_close = float(close.iloc[-1])

    recent_range_pct = float((df["High"].iloc[-15:] - df["Low"].iloc[-15:]).mean() / last_close * 100)
    prior_range_pct = float((df["High"].iloc[-45:-15] - df["Low"].iloc[-45:-15]).mean() / last_close * 100)
    vcp_confirmed = recent_range_pct < prior_range_pct

    vol_avg20 = float(volume.iloc[-20:].mean())
    vol_today = float(volume.iloc[-1])
    volume_confirmed = vol_today >= 1.5 * vol_avg20 if vol_avg20 else False

    rsi_val = float(_rsi(close).iloc[-1])
    rsi_healthy = 45 <= rsi_val <= 68  # early-stage strength, not already overbought

    checks_passed = sum([vcp_confirmed, volume_confirmed, rsi_healthy])
    if checks_passed < 2:
        return None

    high_low = df["High"] - df["Low"]
    atr14 = float(high_low.rolling(14).mean().iloc[-1])
    suggested_stop = round(last_close - 1.5 * atr14, 2)
    risk = last_close - suggested_stop
    suggested_target = round(last_close + 2.5 * risk, 2)

    return {
        "ticker": ticker,
        "close": round(last_close, 2),
        "stage_note": stage_info["note"],
        "pct_above_30w_avg": stage_info["pct_above_30w_avg"],
        "vcp_confirmed": vcp_confirmed,
        "volume_confirmed": volume_confirmed,
        "rsi": round(rsi_val, 1),
        "checks_passed": checks_passed,
        "suggested_stop": suggested_stop,
        "suggested_target": suggested_target,
        "risk_reward": round((suggested_target - last_close) / risk, 1) if risk else None,
    }


def run_screen():
    tickers = data.load_watchlist()
    hits = []
    for t in tickers:
        r = screen_stock(t)
        if r:
            hits.append(r)
    hits.sort(key=lambda x: x["checks_passed"], reverse=True)
    return hits
