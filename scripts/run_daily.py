"""
Runs automatically every trading day after market close (via GitHub Actions).
Does: India regime + global regime -> sector ranking -> cash-flow screen
(weighted 0-100 score, not simple pass/fail) -> exit monitor -> AI text read +
AI pattern-library chart read on the top picks -> one clean Telegram message.
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


def _regime_emoji(score):
    if score >= 65:
        return "🟢"
    elif score >= 45:
        return "🟡"
    elif score >= 25:
        return "🟠"
    return "🔴"


def build_message():
    today = date.today().isoformat()
    lines = [f"📊 *DAILY MARKET BRIEF* — {today}", ""]

    india = regime.compute_regime()
    glob = global_regime.compute_global_regime()
    combined = round(0.7 * india["score"] + 0.3 * glob["score"], 1)
    lines.append(f"{_regime_emoji(combined)} REGIME: {combined}/100")
    lines.append(f"   India {india['score']}/100 | Global {glob['score']}/100")
    lines.append("")

    sectors = sector_rotation.rank_sectors()
    if sectors:
        lines.append("📈 TOP SECTORS:")
        for s in sectors[:5]:
            arrow = "▲" if s["1m_return_pct"] > 0 else "▼"
            lines.append(f"   {arrow} {s['sector']} — 1M {s['1m_return_pct']}%, 3M {s['3m_return_pct']}%")
        lines.append("")

    holdings_results = exit_monitor.run_monitor()
    lines.append("💼 YOUR HOLDINGS:")
    if holdings_results:
        for h in holdings_results:
            if h.get("status") == "NO DATA":
                lines.append(f"   ⚪ {h['ticker']}: no data")
            else:
                lines.append(f"   {h['status']} {h['ticker']} — close {h['close']}, stop {h.get('trailing_stop_level')}")
    else:
        lines.append("   none configured in config/portfolio.json")
    lines.append("")

    # Weighted-score cash-flow candidates
    hits = cash_screener.run_screen()
    lines.append(f"⚡ CASH-FLOW WATCHLIST ({len(hits)} scored ≥65/100):")
    if combined < 25:
        lines.append("   🔴 Regime is RISK-OFF — sit out today.")
    elif not hits:
        lines.append("   No candidates cleared the bar today. No trade is a valid outcome.")
    else:
        for h in hits[:8]:
            b = h["breakdown"]
            risk_txt = f" ⚠️ {', '.join(h['risk_notes'])}" if h["risk_notes"] else ""
            lines.append(
                f"{h['stars']} *{h['ticker']}* — {h['score']}/100 ({h['label']}){risk_txt}\n"
                f"   Entry ~{h['close']} | Stop {h['suggested_stop']} | Target {h['suggested_target']} | R:R {h['risk_reward']}\n"
                f"   Trend {b['trend']}, Momentum {b['momentum']}, Volume {b['volume']}, "
                f"Price Action {b['price_action']}, Fundamentals {b['fundamentals']}"
            )
        lines.append("")
        lines.append("🧠 AI READ ON TOP 3:")
        for h in hits[:3]:
            text_take = ai_research.research_cash_flow_candidate(h)
            chart_take = chart_vision.read_chart(h["ticker"])
            lines.append(f"*{h['ticker']}*")
            lines.append(f"   Text: {text_take}")
            lines.append(f"   Chart: {chart_take}")
    lines.append("")
    lines.append("_Screen + AI opinion, not a buy order. You decide._")

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
