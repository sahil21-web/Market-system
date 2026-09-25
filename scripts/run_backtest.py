"""
Manual-only (not scheduled) — run via GitHub Actions "Run workflow" whenever
you want to check: is this screener's confirmed-pick criteria actually
working, based on real history, not memory of a few recent picks?
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import data, backtest, alerts


def build_message():
    tickers = data.load_watchlist(limit=80)  # capped — slow, ~80 tickers x many samples each
    lines = [f"📊 <b>BACKTEST REPORT</b> — {date.today().isoformat()}", ""]
    lines.append("Testing: would a stock scoring 65+ (confirmed) actually have gone up over the next 10 trading days, using real historical data?")
    lines.append("")

    result = backtest.run_backtest(tickers, forward_days=10, min_score=65)

    if result["n_trades"] == 0:
        lines.append("No historical confirmed signals found to test in this sample.")
        return "\n".join(lines)

    lines.append(f"<b>{result['n_trades']} historical confirmed signals tested</b> (10-day forward window):")
    lines.append(f"   Hit rate (price up after 10 days): {result['hit_rate_pct']}%")
    lines.append(f"   Average forward return: {result['avg_forward_return_pct']}%")
    lines.append(f"   Average winner: +{result['avg_win_pct']}% | Average loser: {result['avg_loss_pct']}%")
    lines.append(f"   Hit target first: {result['target_hit_count']} | Hit stop first: {result['stop_hit_count']} | Still open at 10 days: {result['still_open_count']}")
    lines.append("")
    lines.append("<i>Honest limitation: Fundamentals uses today's numbers even for past dates (no free point-in-time history) — small look-ahead bias on ~10 of 80 raw points. Everything else is genuinely as-of-date.</i>")
    lines.append("")
    lines.append("<b>Sample trades (5 worst, 5 best):</b>")
    for t in result["sample_trades"]:
        lines.append(f"   {t['ticker']} — score {t['score']}, forward return {t['forward_return_pct']}%")

    return "\n".join(lines)


def main():
    message = build_message()
    alerts.send_telegram(message)
    print(message)


if __name__ == "__main__":
    main()
