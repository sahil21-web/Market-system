"""
Runs automatically every trading day after market close (via GitHub Actions).
Does: India regime + global regime -> sector ranking -> cash-flow screen
(weighted 0-100 score, not simple pass/fail) -> exit monitor -> AI text read +
AI pattern-library chart read on the top picks -> one clean Telegram message.

Formatting note: this was rewritten to use HTML tags (<b>, <i>) instead of
Markdown (*bold*, _italic_) — alerts.py sends every message with
parse_mode="HTML", so Markdown syntax was rendering as literal asterisks
and underscores on your phone instead of actual bold/italic text.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (
    regime, global_regime, sector_rotation, cash_screener,
    exit_monitor, alerts, ai_research, chart_vision, formatting,
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
    lines = [f"📊 <b>DAILY MARKET BRIEF</b> — {today}", ""]

    india = regime.compute_regime()
    glob = global_regime.compute_global_regime()
    combined = round(0.7 * india["score"] + 0.3 * glob["score"], 1)
    lines.append(f"{_regime_emoji(combined)} REGIME: {combined}/100")
    lines.append(f"   India {india['score']}/100 | Global {glob['score']}/100")
    lines.append("")

    sectors = sector_rotation.rank_sectors()
    if sectors:
        lines.append("📈 <b>TOP SECTORS</b>:")
        for s in sectors[:5]:
            arrow = "▲" if s["1m_return_pct"] > 0 else "▼"
            lines.append(f"   {arrow} {formatting.escape(s['sector'])} — 1M {s['1m_return_pct']}%, 3M {s['3m_return_pct']}%")
        lines.append("")

    holdings_results = exit_monitor.run_monitor()
    lines.append("💼 <b>YOUR HOLDINGS</b>:")
    if holdings_results:
        for h in holdings_results:
            if h.get("status") == "NO DATA":
                lines.append(f"   ⚪ {formatting.escape(h['ticker'])}: no data")
            else:
                lines.append(f"   {h['status']} {formatting.escape(h['ticker'])} — close {h['close']}, stop {h.get('trailing_stop_level')}")
    else:
        lines.append("   none configured in config/portfolio.json")
    lines.append("")

    # Weighted-score cash-flow candidates — shows every scanned stock's
    # score, not just ones clearing a bar, so "the system did nothing" never
    # looks the same as "the system ran and found nothing good."
    all_hits = cash_screener.run_screen()
    confirmed = [h for h in all_hits if h["score"] >= 65]
    early = [h for h in all_hits if 55 <= h["score"] < 65]

    lines.append(f"⚡ <b>CASH-FLOW WATCHLIST</b> ({len(confirmed)} confirmed, {len(early)} early, {len(all_hits)} scanned):")
    if combined < 25:
        lines.append("   🔴 Regime is RISK-OFF — sit out today, even if candidates appear below.")
    if confirmed:
        for h in confirmed[:8]:
            b = h["breakdown"]
            risk_txt = f" ⚠️ {formatting.escape(', '.join(h['risk_notes']))}" if h["risk_notes"] else ""
            lines.append(
                f"{h['stars']} <b>{formatting.escape(h['ticker'])}</b> — {h['score']}/100 ({h['label']}){risk_txt}\n"
                f"   Entry ~{h['close']} | Stop {h['suggested_stop']} | Target {h['suggested_target']} | R:R {h['risk_reward']}\n"
                f"   Trend {b['trend']}, Momentum {b['momentum']}, Volume {b['volume']}, "
                f"Price Action {b['price_action']}, Fundamentals {b['fundamentals']}"
            )
    else:
        lines.append("   No confirmed setups today — that's a normal, valid outcome, not a broken screen.")

    if early:
        lines.append("")
        lines.append("🟡 <b>EARLY / UNCONFIRMED</b> (score 55-64, worth watching, not yet actionable):")
        for h in early[:5]:
            lines.append(f"   {formatting.escape(h['ticker'])} — {h['score']}/100 (close {h['close']})")

    if not confirmed and not early and all_hits:
        # Nothing even hit the early-signal bar — show the actual top scorers
        # anyway so "nothing qualified" is visibly different from "nothing ran."
        lines.append("")
        lines.append("📋 <b>TOP SCORED TODAY</b> (below the actionable bar, shown for reference):")
        for h in all_hits[:5]:
            b = h["breakdown"]
            lines.append(
                f"   {formatting.escape(h['ticker'])} — {h['score']}/100 "
                f"(Trend {b['trend']}, Momentum {b['momentum']}, Volume {b['volume']}, "
                f"Price Action {b['price_action']}, Fundamentals {b['fundamentals']})"
            )

    hits = confirmed if confirmed else (early if early else all_hits[:3])
    if hits:
        lines.append("")
        lines.append("🧠 <b>AI READ ON TOP 3</b>:")
        for h in hits[:3]:
            text_take = ai_research.research_cash_flow_candidate(h)
            chart_take = chart_vision.read_chart(h["ticker"])
            lines.append(f"<b>{formatting.escape(h['ticker'])}</b>")
            lines.append(f"   Text: {formatting.escape(text_take)}")
            lines.append(f"   Chart: {formatting.escape(chart_take)}")
    lines.append("")
    lines.append("<i>Screen + AI opinion, not a buy order. You decide.</i>")

    raw = {
        "india_regime": india, "global_regime": glob, "combined_score": combined,
        "sectors": sectors, "holdings": holdings_results,
        "confirmed_candidates": confirmed, "early_candidates": early, "all_scanned": all_hits,
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
