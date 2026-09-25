"""
Runs automatically every trading day after market close (via GitHub Actions).

v4 — the real fix for the "picks keep falling" problem: both of the two
picks you reported as losers (JSWINFRA, IKS) were flagged while India's
regime was in Defensive territory (28.6, 35.7). Raising the confirmation
bar to 85 (v3) wasn't the right fix — it still let a breakout-style "buy
this" signal through in exactly the regime where breakout/momentum setups
have the weakest historical follow-through (this matches the research you
gathered: momentum's edge turns negative in choppy/defensive regimes, not
just weaker).

So: in Defensive regime, this now shows ZERO confirmed picks, period — not
a higher bar, an empty section with an explicit "no trade" reason. You'll
still see the early/unconfirmed list for awareness, just nothing telling
you to act.

Also added: a real track record. Every confirmed pick gets logged
(src/trade_log.py) and checked against its stop/target on every run, so
the message now shows actual win/loss numbers instead of you having to
judge "accuracy" from memory.
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import (
    regime, global_regime, sector_rotation, cash_screener,
    exit_monitor, alerts, ai_research, chart_vision, formatting, trade_log, data,
    early_stage_screener, red_flags,
)

BASE_CONFIRMED_BAR = 75
BASE_EARLY_BAR = 60
INDIA_DEFENSIVE_THRESHOLD = 45
RISK_OFF_THRESHOLD = 25


def _regime_emoji(score):
    if score >= 65:
        return "🟢"
    elif score >= 45:
        return "🟡"
    elif score >= 25:
        return "🟠"
    return "🔴"


def _current_price(ticker):
    df = data.get_history(ticker, period="5d")
    if df is None or len(df) == 0:
        return None
    return float(df["Close"].iloc[-1])


def build_message():
    today = date.today().isoformat()
    lines = [f"📊 <b>DAILY MARKET BRIEF</b> — {today}", ""]

    # Track record first — the honest accuracy check, up front, not buried
    trade_log.check_open_trades(_current_price)
    stats = trade_log.summary_stats()
    lines.append("📒 <b>TRACK RECORD</b>")
    if stats["total_logged"] == 0:
        lines.append("   No picks logged yet — starts tracking from today's confirmed picks.")
    else:
        wr = f"{stats['win_rate_pct']}%" if stats["win_rate_pct"] is not None else "n/a (no closed trades yet)"
        lines.append(
            f"   {stats['wins']}W / {stats['losses']}L closed ({wr} win rate), "
            f"{stats['open']} still open, {stats['total_logged']} logged total"
        )
        if stats["avg_win_pct"] is not None:
            lines.append(f"   Avg win {stats['avg_win_pct']}% | Avg loss {stats['avg_loss_pct']}%")
    lines.append("")

    india = regime.compute_regime()
    glob = global_regime.compute_global_regime()
    combined = round(0.8 * india["score"] + 0.2 * glob["score"], 1)
    lines.append(f"{_regime_emoji(combined)} REGIME: {combined}/100")
    lines.append(f"   India {india['score']}/100 | Global {glob['score']}/100")

    india_risk_off = india["score"] < RISK_OFF_THRESHOLD
    india_defensive = india["score"] < INDIA_DEFENSIVE_THRESHOLD
    no_new_trades = india_risk_off or india_defensive

    if india_defensive and not india_risk_off:
        lines.append(
            "   🟠 India regime is Defensive — <b>no confirmed picks today.</b> "
            "Breakout/momentum setups have weak follow-through in choppy conditions; "
            "the system sits out new buy signals until the regime firms up (score ≥ 45)."
        )
    elif india_risk_off:
        lines.append("   🔴 India regime is RISK-OFF — sitting out entirely.")
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

    all_hits = cash_screener.run_screen()

    # Hard gate: no confirmed picks at all when regime is Defensive or worse —
    # not a higher bar, none.
    confirmed = [] if no_new_trades else [h for h in all_hits if h["score"] >= BASE_CONFIRMED_BAR]
    early = [h for h in all_hits if BASE_EARLY_BAR <= h["score"] < BASE_CONFIRMED_BAR]

    lines.append(
        f"⚡ <b>CASH-FLOW WATCHLIST</b> ({len(confirmed)} confirmed, "
        f"{len(early)} early, {len(all_hits)} scanned):"
    )
    if no_new_trades:
        lines.append("   No new buy signals today by design (see regime note above).")
    elif confirmed:
        for h in confirmed[:8]:
            b = h["breakdown"]
            risk_txt = f" ⚠️ {formatting.escape(', '.join(h['risk_notes']))}" if h["risk_notes"] else ""
            flags = red_flags.check_red_flags(h["ticker"])
            flag_txt = f" 🚨 RED FLAG: {formatting.escape(flags[0]['matched'])}" if flags else ""
            lines.append(
                f"{h['stars']} <b>{formatting.escape(h['ticker'])}</b> — {h['score']}/100 ({h['label']}){risk_txt}{flag_txt}\n"
                f"   Stage: {formatting.escape(h.get('stage_note',''))}\n"
                f"   Entry ~{h['close']} | Stop {h['suggested_stop']} | Target {h['suggested_target']} | R:R {h['risk_reward']}\n"
                f"   Trend {b['trend']}, Momentum {b['momentum']}, Volume {b['volume']}, "
                f"Price Action {b['price_action']}, Fundamentals {b['fundamentals']}"
            )
        trade_log.record_new_picks(confirmed, today)
    else:
        lines.append("   No confirmed setups today — that's a normal, valid outcome, not a broken screen.")

    if early:
        lines.append("")
        lines.append(f"🟡 <b>EARLY / UNCONFIRMED</b> (score {BASE_EARLY_BAR}-{BASE_CONFIRMED_BAR - 1}, for awareness only — not a signal):")
        for h in early[:5]:
            lines.append(f"   {formatting.escape(h['ticker'])} — {h['score']}/100 (close {h['close']})")

    if not confirmed and not early and all_hits:
        lines.append("")
        lines.append("📋 <b>TOP SCORED TODAY</b> (below the actionable bar, shown for reference):")
        for h in all_hits[:5]:
            b = h["breakdown"]
            lines.append(
                f"   {formatting.escape(h['ticker'])} — {h['score']}/100 "
                f"(Trend {b['trend']}, Momentum {b['momentum']}, Volume {b['volume']}, "
                f"Price Action {b['price_action']}, Fundamentals {b['fundamentals']})"
            )

    # Early-stage / base-breakout candidates — deliberately complementary:
    # stocks just starting to move (Weinstein Stage 2A / Minervini VCP), not
    # already extended, and structurally unable to flag a still-falling stock
    # (only fires once price is confirmed back above a rising average).
    lines.append("")
    early_stage_hits = early_stage_screener.run_screen()
    lines.append(f"🌱 <b>EARLY-STAGE / BASE BREAKOUTS</b> ({len(early_stage_hits)} found — fresh moves, not extended ones):")
    if not early_stage_hits:
        lines.append("   None today. This is a stricter, rarer setup by design.")
    else:
        for h in early_stage_hits[:6]:
            flags = red_flags.check_red_flags(h["ticker"])
            flag_txt = f" 🚨 RED FLAG: {formatting.escape(flags[0]['matched'])}" if flags else ""
            lines.append(
                f"   <b>{formatting.escape(h['ticker'])}</b> — {formatting.escape(h['stage_note'])}{flag_txt}\n"
                f"   Entry ~{h['close']} | Stop {h['suggested_stop']} | Target {h['suggested_target']} | R:R {h['risk_reward']}\n"
                f"   VCP tightening: {'yes' if h['vcp_confirmed'] else 'no'} | Volume confirmed: {'yes' if h['volume_confirmed'] else 'no'} | RSI {h['rsi']}"
            )

    # AI read only runs on real confirmed picks — no point spending API calls
    # narrating a stock we're explicitly not recommending today.
    if confirmed:
        lines.append("")
        lines.append("🧠 <b>AI READ ON TOP 3</b>:")
        for h in confirmed[:3]:
            text_take = ai_research.research_cash_flow_candidate(h)
            chart_take = chart_vision.read_chart(h["ticker"])
            lines.append(f"<b>{formatting.escape(h['ticker'])}</b>")
            lines.append(f"   Text: {formatting.escape(text_take)}")
            lines.append(f"   Chart: {formatting.escape(chart_take)}")
    lines.append("")
    lines.append("<i>Screen + AI opinion, not a buy order. You decide. Stop-losses do not protect against an overnight gap on surprise news — that risk is managed with position size, never fully removed.</i>")

    raw = {
        "india_regime": india, "global_regime": glob, "combined_score": combined,
        "no_new_trades": no_new_trades, "track_record": stats,
        "sectors": sectors, "holdings": holdings_results,
        "confirmed_candidates": confirmed, "early_candidates": early, "all_scanned": all_hits,
        "early_stage_candidates": early_stage_hits,
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
