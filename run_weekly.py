"""
Runs automatically once a week (Saturday morning) via GitHub Actions.
Does: fundamental wealth screen -> one Telegram message.
Fundamentals don't change day to day, so this doesn't need to run daily.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import wealth_screener, alerts


def build_message():
    today = date.today().isoformat()
    lines = [f"📈 WEEKLY WEALTH SCREEN — {today}", ""]

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
    lines.append("This is a fundamental filter only — do your own read of the business before adding anything here.")

    return "\n".join(lines), {"candidates": hits}


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
