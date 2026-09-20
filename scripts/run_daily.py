"""
Runs automatically every trading day after market close (via GitHub Actions).
Does: India regime + global regime -> sector ranking -> cash-flow screen (with
target/R:R) -> exit monitor -> AI text read + AI chart read on the top picks
-> one Telegram message. You do nothing — this just arrives on your phone.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (
    regime, global_regime, sector_rotation, cash_screener,
    exit_monitor, alerts, ai_research, chart_vision,
)


def build_message():
    today = date.today().isoformat()
    lines = [f"📊 DAILY MARKET BRIEF — {today}", ""]

    # 1. India regime + global regime, combined
    india = regime.compute_regime()
    glob = global_regime.compute_global_regime()
    combined = round(0.7 * india["score"] + 0.3 * glob["score"], 1)
    lines.append(f"INDIA REGIME: {india['score']}/100 — {india['label']}")
    lines.append(f"GLOBAL REGIME: {glob['score']}/100 — {glob['label']}")
    lines.append(f"COMBINED: {combined}/100")
    lines.append("")

    # 2. Sector rotation — top 5
    sectors = sector_rotation.rank_sectors()
    if sectors:
        lines.append("TOP SECTORS (1M/3M momentum):")
        for s in sectors[:5]:
            lines.append(f"  {s['sector']}: score {s['score']} (1M {s['1m_return_pct']}%, 3M {s['3m_return_pct']}%)")
        lines.append("")

    # 3. Exit monitor (holdings) — always shown, it's the most important
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

    # 4. Cash-flow screener with target/R:R, then AI text + AI chart read on top 3
    hits = cash_screener.run_screen()
    lines.append(f"CASH-FLOW WATCHLIST ({len(hits)} candidates passed 2+ checks):")
    if combined < 25:
        lines.append("  Combined regime is RISK-OFF — candidates suppressed today. Sit out.")
    elif not hits:
        lines.append("  None today. No trade is a valid outcome.")
    else:
        for h in hits[:8]:
            lines.append(
                f"  {h['ticker']}: close {h['close']}, checks {h['checks_passed']}/3, "
                f"stop {h['suggested_stop']}, target {h['suggested_target']} (R:R {h['risk_reward']})"
            )
        lines.append("")
        lines.append("AI READ ON TOP 3 (text + chart):")
        for h in hits[:3]:
            text_take = ai_research.research_cash_flow_candidate(h)
            chart_take = chart_vision.read_chart(h["ticker"])
            lines.append(f"  {h['ticker']}:")
            lines.append(f"    Text read: {text_take}")
            lines.append(f"    Chart read: {chart_take}")
    lines.append("")
    lines.append("Reminder: this is a screen + AI opinion, not a buy order. You decide.")

    raw = {
        "india_regime": india, "global_regime": glob, "combined_score": combined,
        "sectors": sectors, "holdings": holdings_results, "candidates": hits,
    }
    return "\n".join(lines), raw


def main():
    message, raw = build_message()
    alerts.send_telegram(message)

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"), exist_ok=True)
    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", f"daily_{date.today().isoformat()}.json")
    with open(log_path, "w") as f:
        json.dump(raw, f, indent=2, default=str)

    print(message)


if __name__ == "__main__":
    main()
