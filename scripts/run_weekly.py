"""
Runs automatically once a week (Saturday morning) via GitHub Actions.
Does: fundamental wealth screen + recovery ("fallen but fundamentally
strong") screen -> AI text read (with real news headlines) + AI chart read on
top candidates -> one clean Telegram message.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import wealth_screener, recovery_screener, alerts, ai_research, chart_vision, sector_rotation, formatting


def build_message():
    today = date.today().isoformat()
    lines = [f"📈 <b>WEEKLY WEALTH SCREEN</b> — {today}", ""]

    sectors = sector_rotation.rank_sectors()
    if sectors:
        lines.append("📊 <b>SECTOR CONTEXT</b> (top 5):")
        for s in sectors[:5]:
            lines.append(f"   {formatting.escape(s['sector'])} — score {s['score']}")
        lines.append("")

    hits = wealth_screener.run_screen()
    lines.append(f"💎 <b>WEALTH CANDIDATES</b>: {len(hits)} companies passed 2+ of 3 checks (ROE ≥15%, revenue growth ≥15%, D/E ≤1.0):")
    if not hits:
        lines.append("   None this week — that's fine, quality bars stay high on purpose.")
    else:
        for h in hits[:15]:
            lines.append(
                f"   {formatting.escape(h['ticker'])}: ROE {h['roe_pct']}%, growth {h['revenue_growth_pct']}%, "
                f"D/E {h['debt_to_equity']}, checks {h['checks_passed']}/3"
            )
        lines.append("")
        lines.append("🧠 <b>AI RESEARCH READ</b> (top candidates):")
        for h in hits[:8]:
            text_take = ai_research.research_wealth_candidate(h)
            chart_take = chart_vision.read_chart(h["ticker"])
            lines.append(f"<b>{formatting.escape(h['ticker'])}</b>")
            lines.append(f"   Text: {formatting.escape(text_take)}")
            lines.append(f"   Chart: {formatting.escape(chart_take)}")
    lines.append("")

    # Recovery candidates — "fell more than the business deteriorated"
    recovery_hits = recovery_screener.run_screen()
    lines.append(f"📉➡️📈 <b>RECOVERY CANDIDATES</b>: {len(recovery_hits)} fallen-but-fundamentally-intact stocks:")
    if not recovery_hits:
        lines.append("   None this week.")
    else:
        for h in recovery_hits[:10]:
            stabilize_note = "stabilizing" if h["selling_stabilizing"] else "still volatile"
            lines.append(
                f"   {formatting.escape(h['ticker'])}: down {h['fall_from_high_pct']}% from 52w high ({h['close']} vs {h['high_52w']}), "
                f"ROE {h['roe_pct']}%, growth {h['revenue_growth_pct']}%, checks {h['checks_passed']}/3, range {stabilize_note}"
            )
    lines.append("")
    lines.append("<i>Fundamental filters + AI opinion, not investment advice — do your own read.</i>")

    return "\n".join(lines), {"sectors": sectors, "wealth_candidates": hits, "recovery_candidates": recovery_hits}


def main():
    message, raw = build_message()
    alerts.send_telegram(message)

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"), exist_ok=True)
    log_path = os.path.join(os.path.dirname(__file__), "..", "logs", f"weekly_{date.today().isoformat()}.json")
    with open(log_path, "w") as f:
        json.dump(raw, f, indent=2, default=str)

    print(message)


if __name__ == "__main__":
    main()
