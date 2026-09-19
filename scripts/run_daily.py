"""
Runs automatically every trading day after market close (via GitHub Actions).
Does: regime check -> cash-flow screen -> exit monitor -> one Telegram message.
You do nothing — this just arrives on your phone.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import regime, cash_screener, exit_monitor, alerts


def build_message():
    today = date.today().isoformat()
    lines = [f"📊 DAILY MARKET BRIEF — {today}", ""]

    # 1. Regime
    r = regime.compute_regime()
    lines.append(f"MARKET REGIME: {r['score']}/100 — {r['label']}")
    lines.append("")

    # 2. Exit monitor (holdings) — always shown first, it's the most important
    holdings_results = exit_monitor.run_monitor()
    if holdings_results:
        lines.append("YOUR HOLDINGS:")
        for h in holdings_results:
            if h.get("status") == "NO DATA":
                lines.append(f"  {h['ticker']}: {h['status']} — {h['note']}")
            else:
                lines.append(f"  {h['ticker']}: {h['status']} (close {h['close']}, stop {h.get('trailing_stop_level')})  {h['note']}")
        lines.append("")
    else:
        lines.append("YOUR HOLDINGS: none configured in config/portfolio.json")
        lines.append("")

    # 3. Cash-flow screener — only show top few, and only if regime isn't risk-off
    hits = cash_screener.run_screen()
    lines.append(f"CASH-FLOW WATCHLIST ({len(hits)} candidates passed 2+ checks):")
    if r["score"] < 25:
        lines.append("  Regime is RISK-OFF — candidates suppressed today. Sit out.")
    elif not hits:
        lines.append("  None today. No trade is a valid outcome.")
    else:
        for h in hits[:8]:
            lines.append(f"  {h['ticker']}: close {h['close']}, checks {h['checks_passed']}/3, suggested stop {h['suggested_stop']}")
    lines.append("")
    lines.append("Reminder: this is a screen, not a buy order. You decide.")

    return "\n".join(lines), {"regime": r, "holdings": holdings_results, "candidates": hits}


def main():
    message, raw = build_message()
    alerts.send_telegram(message)

    # log the run so it's visible in the repo history
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"), exist_ok=True)
    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", f"daily_{date.today().isoformat()}.json")
    with open(log_path, "w") as f:
        json.dump(raw, f, indent=2, default=str)

    print(message)


if __name__ == "__main__":
    main()
