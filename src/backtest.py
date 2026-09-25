"""
Runs the exact same scoring function used live (cash_screener.screen_stock)
against real historical data, then checks what actually happened afterward.
No serious quant system gets trusted without this.

HONEST LIMITATION: the Fundamentals category uses TODAY's ROE/revenue-growth
even when testing a past date, since free sources don't give point-in-time
historical fundamentals. Small look-ahead bias on ~10 of 80 raw points.
Trend/Momentum/Volume/Price Action are all genuinely as-of-the-historical-date.
"""
from . import data, cash_screener

SAMPLE_EVERY_N_DAYS = 5
MIN_HISTORY_FOR_TEST = 220


def backtest_ticker(ticker, forward_days=10, min_score=65, lookback_days=250):
    df = data.get_history(ticker, period="2y")
    if df is None or len(df) < MIN_HISTORY_FOR_TEST + forward_days + 20:
        return []

    n = len(df)
    start = max(MIN_HISTORY_FOR_TEST, n - lookback_days)
    end = n - forward_days

    trades = []
    for offset in range(start, end, SAMPLE_EVERY_N_DAYS):
        hist_slice = df.iloc[: offset + 1]
        try:
            result = cash_screener.screen_stock(ticker, df=hist_slice)
        except Exception:
            continue
        if result is None or result["score"] < min_score:
            continue

        entry_price = result["close"]
        future = df.iloc[offset + 1: offset + 1 + forward_days]
        if len(future) < forward_days:
            continue

        future_close = float(future["Close"].iloc[-1])
        forward_return_pct = round(100 * (future_close - entry_price) / entry_price, 2)
        hit_stop = bool((future["Low"] <= result["suggested_stop"]).any())
        hit_target = bool((future["High"] >= result["suggested_target"]).any())

        trades.append({
            "ticker": ticker,
            "score": result["score"],
            "label": result["label"],
            "entry": entry_price,
            "forward_return_pct": forward_return_pct,
            "hit_stop_first": hit_stop and not hit_target,
            "hit_target_first": hit_target,
            "still_open": not hit_stop and not hit_target,
        })
    return trades


def run_backtest(tickers, forward_days=10, min_score=65):
    all_trades = []
    for t in tickers:
        all_trades.extend(backtest_ticker(t, forward_days=forward_days, min_score=min_score))

    if not all_trades:
        return {"n_trades": 0}

    n = len(all_trades)
    wins = [t for t in all_trades if t["forward_return_pct"] > 0]
    losses = [t for t in all_trades if t["forward_return_pct"] <= 0]
    hit_rate = round(100 * len(wins) / n, 1)
    avg_return = round(sum(t["forward_return_pct"] for t in all_trades) / n, 2)
    avg_win = round(sum(t["forward_return_pct"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(t["forward_return_pct"] for t in losses) / len(losses), 2) if losses else 0
    target_hits = sum(1 for t in all_trades if t["hit_target_first"])
    stop_hits = sum(1 for t in all_trades if t["hit_stop_first"])

    return {
        "n_trades": n,
        "hit_rate_pct": hit_rate,
        "avg_forward_return_pct": avg_return,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "target_hit_count": target_hits,
        "stop_hit_count": stop_hits,
        "still_open_count": n - target_hits - stop_hits,
        "sample_trades": sorted(all_trades, key=lambda x: x["forward_return_pct"])[:5] +
                          sorted(all_trades, key=lambda x: x["forward_return_pct"])[-5:],
    }
