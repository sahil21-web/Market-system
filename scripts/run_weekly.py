"""
Runs automatically once a week (Saturday morning) via GitHub Actions.
Does: fundamental wealth screen -> AI text read (with real news headlines) +
AI chart read on top candidates -> one Telegram message.
"""
import sys
import os
import json
import time
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import wealth_screener, alerts, ai_research, chart_vision, sector_rotation


def build_message():
    today = date.today().isoformat()
    lines = [f"📈 WEEKLY WEALTH SCREEN — {today}", ""]

    sectors = sector_rotation.rank_sectors()
    if sectors:
        lines.append("SECTOR CONTEXT (top 5 by 1M/3M momentum):")
        for s in sectors[:5]:
            lines.append(f"  {s['sector']}: score {s['score']}")
        lines.append("")

    hits = wealth_screener.run_screen()
    lines.append(f"{len(hits)} companies passed 2+ of 3 checks (ROE >=15%, revenue growth >=15%, D/E <=1.0):")
    if not hits:
        lines.append("  None this week — that's fine, quality bars stay high on purpose.")
    else:
        for h in hits[:15]:
            lines.append(
                f"  {h['ticker']}: ROE {h['roe_pct']}%, revenue growth {h['revenue_growth_pct']}%, "
                f"D/E {h['debt_to_equity']}, checks {h['checks_passed']}/3"
            )
        lines.append("")
        lines.append("AI RESEARCH READ (text + chart, top candidates):")
        for h in hits[:8]:
            text_take = ai_research.research_wealth_candidate(h)
            time.sleep(3)
            chart_take = chart_vision.read_chart(h["ticker"])
            time.sleep(3)
            lines.append(f"  {h['ticker']}:")
            lines.append(f"    Text read: {text_take}")
            lines.append(f"    Chart read: {chart_take}")
    lines.append("")
    lines.append("This is a fundamental filter + AI opinion, not investment advice — do your own read of the business.")

    return "\n".join(lines), {"sectors": sectors, "candidates": hits}


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
