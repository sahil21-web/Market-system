"""
Extends the regime check beyond India — both research chats stressed that
Indian stocks don't move in isolation. Checks S&P 500 / Nasdaq trend, US VIX,
crude oil, and the dollar index (DXY), since a strong dollar + rising crude
is historically a headwind for Indian equities (import bill, inflation, INR).
"""
from . import data

TICKERS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "us_vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "crude_wti": "CL=F",
}


def _trend_ok(df, window=50):
    if df is None or len(df) < window + 1:
        return None
    ma = df["Close"].rolling(window).mean()
    return bool(df["Close"].iloc[-1] > ma.iloc[-1])


def _pct_change(df, lookback_days):
    if df is None or len(df) < lookback_days + 1:
        return None
    start = float(df["Close"].iloc[-lookback_days - 1])
    end = float(df["Close"].iloc[-1])
    if start == 0:
        return None
    return round(100 * (end - start) / start, 2)


def compute_global_regime():
    result = {"components": {}}
    score, max_score = 0, 0

    sp500 = data.get_history(TICKERS["sp500"], period="1y")
    trend = _trend_ok(sp500)
    result["components"]["sp500_above_50dma"] = trend
    if trend is not None:
        score += 20 if trend else 0
        max_score += 20

    nasdaq = data.get_history(TICKERS["nasdaq"], period="1y")
    trend = _trend_ok(nasdaq)
    result["components"]["nasdaq_above_50dma"] = trend
    if trend is not None:
        score += 15 if trend else 0
        max_score += 15

    vix = data.get_history(TICKERS["us_vix"], period="3mo")
    if vix is not None and len(vix) > 5:
        latest_vix = float(vix["Close"].iloc[-1])
        result["components"]["us_vix"] = round(latest_vix, 2)
        if latest_vix < 15:
            score += 20
        elif latest_vix < 20:
            score += 12
        elif latest_vix < 25:
            score += 5
        max_score += 20

    crude = data.get_history(TICKERS["crude_wti"], period="3mo")
    crude_chg = _pct_change(crude, 21)
    if crude_chg is not None:
        result["components"]["crude_1m_change_pct"] = crude_chg
        if crude_chg < 5:
            score += 15
        elif crude_chg < 10:
            score += 8
        max_score += 15

    dxy = data.get_history(TICKERS["dxy"], period="3mo")
    dxy_chg = _pct_change(dxy, 21)
    if dxy_chg is not None:
        result["components"]["dxy_1m_change_pct"] = dxy_chg
        if dxy_chg < 1:
            score += 15
        elif dxy_chg < 2.5:
            score += 8
        max_score += 15

    final_score = round(100 * score / max_score, 1) if max_score > 0 else 50.0
    result["score"] = final_score
    if final_score >= 65:
        result["label"] = "GLOBAL TAILWIND"
    elif final_score >= 40:
        result["label"] = "GLOBAL NEUTRAL"
    else:
        result["label"] = "GLOBAL HEADWIND — crude/dollar/US markets working against Indian equities"
    return result
