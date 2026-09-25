"""
The system had no memory of whether its own picks actually worked — you
were evaluating accuracy from screenshots and recollection, which isn't a
real feedback loop. This module fixes that: every confirmed pick gets
logged with its entry price/date, and every day we check open positions
against their stop/target to see what actually happened.

Storage: logs/trade_log.json — one entry per confirmed pick, ever. Kept in
the repo (committed by the workflow, same as the daily/weekly JSON logs)
so the track record survives across runs.

This existing purely to answer one question honestly: is this screen
actually working, or not? Right now nobody — including me — can answer
that without this.
"""
import json
import os
from datetime import date

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "trade_log.json")


def _load():
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(entries):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def record_new_picks(confirmed_hits, today=None):
    """Log today's confirmed picks, skipping any ticker already open so we
    don't log the same setup twice while it's still active."""
    today = today or date.today().isoformat()
    entries = _load()
    already_open = {e["ticker"] for e in entries if e["status"] == "OPEN"}
    for h in confirmed_hits:
        if h["ticker"] in already_open:
            continue
        entries.append({
            "ticker": h["ticker"],
            "entry_date": today,
            "entry_price": h["close"],
            "stop": h["suggested_stop"],
            "target": h["suggested_target"],
            "score_at_entry": h["score"],
            "status": "OPEN",
            "closed_date": None,
            "closed_price": None,
            "result_pct": None,
        })
    _save(entries)


def check_open_trades(get_current_price_fn):
    """For every OPEN logged pick, fetch the current price and close it out
    if it's hit its stop or target. get_current_price_fn(ticker) -> float
    or None, so this module doesn't need to import data.py directly and
    stays easy to unit test."""
    entries = _load()
    changed = False
    for e in entries:
        if e["status"] != "OPEN":
            continue
        price = get_current_price_fn(e["ticker"])
        if price is None:
            continue
        if price <= e["stop"]:
            e["status"] = "LOSS"
            e["closed_date"] = date.today().isoformat()
            e["closed_price"] = price
            e["result_pct"] = round(100 * (price - e["entry_price"]) / e["entry_price"], 2)
            changed = True
        elif price >= e["target"]:
            e["status"] = "WIN"
            e["closed_date"] = date.today().isoformat()
            e["closed_price"] = price
            e["result_pct"] = round(100 * (price - e["entry_price"]) / e["entry_price"], 2)
            changed = True
    if changed:
        _save(entries)
    return entries


def summary_stats():
    entries = _load()
    closed = [e for e in entries if e["status"] in ("WIN", "LOSS")]
    open_count = sum(1 for e in entries if e["status"] == "OPEN")
    wins = [e for e in closed if e["status"] == "WIN"]
    losses = [e for e in closed if e["status"] == "LOSS"]
    win_rate = round(100 * len(wins) / len(closed), 1) if closed else None
    avg_win_pct = round(sum(e["result_pct"] for e in wins) / len(wins), 1) if wins else None
    avg_loss_pct = round(sum(e["result_pct"] for e in losses) / len(losses), 1) if losses else None
    return {
        "total_logged": len(entries),
        "open": open_count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
    }
