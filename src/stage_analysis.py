"""
Classifies each stock into a market "stage," using Stan Weinstein's Stage
Analysis (the framework Mark Minervini — a 2x US Investing Champion — calls
his single non-negotiable entry criterion). This distinguishes a stock EARLY
in its advance (best risk/reward) from one that's ALREADY extended (chasing).

Stage 1: Basing — flat 30-week average, price chopping sideways. Not yet buyable.
Stage 2A: Early advance — 30-week average just turned up, price just broke
          above it. The "ideal time to buy" window both call out.
Stage 2B: Extended advance — been in Stage 2 a long time, price far above a
          still-rising average. Real trend, but chasing it here is higher risk.
Stage 3: Topping — average flattening after an advance. Exit zone, not entry.
Stage 4: Declining — average falling, price below it. Avoid.
"""


def classify_stage(df):
    """df must have a 'Close' column with at least ~220 trading days of
    history (30-week/150-day SMA needs runway, plus a lookback for slope)."""
    if df is None or len(df) < 220:
        return None

    close = df["Close"]
    sma30w = close.rolling(150).mean()  # ~30 trading weeks
    sma40w = close.rolling(200).mean()  # ~40 trading weeks

    price = float(close.iloc[-1])
    ma30 = float(sma30w.iloc[-1])
    ma30_20d_ago = float(sma30w.iloc[-21])
    ma40 = float(sma40w.iloc[-1])
    ma40_20d_ago = float(sma40w.iloc[-21])

    ma30_slope_up = ma30 > ma30_20d_ago
    ma40_slope_up = ma40 > ma40_20d_ago
    price_above_ma30 = price > ma30
    pct_above_ma30 = 100 * (price - ma30) / ma30 if ma30 else 0

    # How recently did price genuinely cross above the 30-week average? Using
    # a point-in-time comparison (price vs average ~40 sessions ago) rather
    # than a consecutive-day streak count, since a flat/noisy base can
    # produce spurious streaks from random blips above/below the average.
    lookback = min(41, len(close) - 1)
    price_then = float(close.iloc[-lookback - 1])
    sma_then = float(sma30w.iloc[-lookback - 1])
    was_below_before = price_then <= sma_then * 1.02
    days_above = 0 if was_below_before else lookback + 1

    if not price_above_ma30 and not ma30_slope_up:
        stage, note = "4_declining", "Below a falling 30-week average — avoid"
    elif not price_above_ma30 and ma30_slope_up:
        stage, note = "1_basing", "Below the average but it's turning up — watch, not yet buyable"
    elif price_above_ma30 and ma30_slope_up and ma40_slope_up:
        if days_above <= 40 and pct_above_ma30 <= 20:
            stage = "2A_early_advance"
            note = "Fresh breakout above a rising average — the textbook 'ideal time to buy' window"
        else:
            stage = "2B_extended_advance"
            note = f"In Stage 2 for a while now, {round(pct_above_ma30,1)}% above the average — real trend, but chasing it here is higher risk"
    elif price_above_ma30 and not ma30_slope_up:
        stage, note = "3_topping", "Average flattening after an advance — exit zone, not entry"
    else:
        stage, note = "1_basing", "Building a base"

    return {
        "stage": stage,
        "note": note,
        "pct_above_30w_avg": round(pct_above_ma30, 1),
        "days_above_30w_avg": days_above,
    }
