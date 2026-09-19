"""
Market regime gate: one score that tells the rest of the system whether it's
allowed to be aggressive today. This is deliberately simple and transparent —
you can see exactly why the score is what it is.
"""
from . import data


def _pct_above_ma(df, window):
    if df is None or len(df) < window + 1:
        return None
    ma = df["Close"].rolling(window).mean()
    return bool(df["Close"].iloc[-1] > ma.iloc[-1])


def compute_regime():
    result = {"components": {}, "score": 0, "label": "UNKNOWN"}
    score = 0
    max_score = 0

    # 1. Nifty trend vs 50 and 200 day average
    nifty = data.get_history("^NSEI", period="1y")
    if nifty is not None and len(nifty) > 200:
        above50 = _pct_above_ma(nifty, 50)
        above200 = _pct_above_ma(nifty, 200)
        result["components"]["nifty_above_50dma"] = above50
        result["components"]["nifty_above_200dma"] = above200
        score += 15 if above50 else 0
        score += 15 if above200 else 0
        max_score += 30
    else:
        result["components"]["nifty"] = "data unavailable"

    # 2. India VIX level (lower = calmer = healthier)
    vix = data.get_history("^INDIAVIX", period="3mo")
    if vix is not None and len(vix) > 5:
        latest_vix = float(vix["Close"].iloc[-1])
        result["components"]["india_vix"] = round(latest_vix, 2)
        if latest_vix < 13:
            score += 20
        elif latest_vix < 17:
            score += 12
        elif latest_vix < 22:
            score += 5
        # above 22 adds 0
        max_score += 20
    else:
        result["components"]["india_vix"] = "data unavailable"

    # 3. Breadth: % of watchlist above their own 50-day average
    tickers = data.load_watchlist()
    above_count, total_checked = 0, 0
    for t in tickers:
        df = data.get_history(t, period="6mo")
        res = _pct_above_ma(df, 50)
        if res is not None:
            total_checked += 1
            if res:
                above_count += 1
    if total_checked > 0:
        breadth_pct = round(100 * above_count / total_checked, 1)
        result["components"]["breadth_pct_above_50dma"] = breadth_pct
        if breadth_pct >= 65:
            score += 20
        elif breadth_pct >= 50:
            score += 12
        elif breadth_pct >= 35:
            score += 5
        max_score += 20
    else:
        result["components"]["breadth"] = "data unavailable"

    # Normalize to 0-100 in case some components were unavailable
    final_score = round(100 * score / max_score, 1) if max_score > 0 else 0
    result["score"] = final_score

    if final_score >= 65:
        result["label"] = "RISK-ON — normal trading allowed"
    elif final_score >= 45:
        result["label"] = "CONSTRUCTIVE — trade selectively, smaller size"
    elif final_score >= 25:
        result["label"] = "DEFENSIVE — new positions only on the strongest setups"
    else:
        result["label"] = "RISK-OFF — sit out, do not force new trades"

    return result
