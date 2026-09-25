# Market System — fully automated, free, cash/stocks only

No F&O anywhere in this system. Two scheduled jobs run in GitHub's free cloud
(not your laptop) and text you on Telegram. You set it up once; after that
you don't touch data or code again — you only edit `config/portfolio.json`
when you actually buy or sell something.

## What runs automatically

| Job | Schedule | Does |
|---|---|---|
| **Daily** | Mon–Fri, 4:00 PM IST | Market regime check, cash-flow screener, exit check on your holdings |
| **Weekly** | Saturday, 8:30 AM IST | Fundamental (wealth) screener |

Both send one Telegram message each. That's it — nothing else to check.

---

## One-time setup (about 20 minutes, never repeat this)

### 1. Create the Telegram bot (5 min)
1. Open Telegram, search **@BotFather**, send `/newbot`, follow the prompts.
2. Copy the **bot token** it gives you.
3. Send your new bot any message (e.g. "hi"), then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and
   copy the `"chat":{"id": ...}` number — that's your **chat id**.

### 2. Create a GitHub repo (5 min)
1. Go to github.com → New repository → name it e.g. `market-system` → Create.
2. Upload every file in this project keeping the folder structure exactly as
   given (drag-and-drop on the repo's "Add file → Upload files" page works
   fine, or `git push` if you're comfortable with git).

### 3. Add your secrets (2 min)
In the repo: **Settings → Secrets and variables → Actions → New repository secret**
- `TELEGRAM_BOT_TOKEN` = the token from step 1
- `TELEGRAM_CHAT_ID` = the chat id from step 1

### 4. Edit your two config files once (5 min)
- `config/watchlist.json` — the stocks the daily/weekly screeners scan. A
  starter list of ~50 liquid names is already in there; edit freely.
- `config/portfolio.json` — your actual holdings. Replace the `EXAMPLE.NS`
  entry with your real positions (ticker, entry price, quantity, and
  `"engine": "cash_flow"` or `"engine": "wealth"` so the exit monitor knows
  which rule to apply). Come back and edit this **only** when you buy or sell.

### 5. Turn it on
Nothing else to do — GitHub Actions runs on the schedule in
`.github/workflows/daily.yml` and `weekly.yml` automatically. To confirm it
works right now instead of waiting for the schedule: go to the repo's
**Actions** tab → pick "Daily Market Brief" or "Weekly Wealth Screen" → **Run
workflow** button. Check Telegram a minute later.

---

## How the rules work (so you trust what it tells you)

**Regime score (0–100):** Nifty vs its 50/200-day average + India VIX level +
% of your watchlist above their own 50-day average. Below 25 → the system
tells you to sit out for the day.

**Cash-flow screener:** flags a stock only when at least 2 of these 3 are
true — price above its 20 & 50-day average, RSI(14) freshly crossed above 55,
volume at least 1.5x its 20-day average.

**Exit monitor:** for `cash_flow` holdings, exits on an ATR-based trailing
stop or a break below the 50-day average — mechanical, no feelings involved.
For `wealth` holdings, a price drop only triggers a "review" flag, never an
automatic exit — the idea is to protect a compounder from being sold just
because the price dipped.

**Wealth screener:** flags a company when 2 of 3 are true — ROE ≥ 15%,
revenue growth ≥ 15%, debt/equity ≤ 1.0. This is a rough fundamental filter,
not a verdict — read the actual business before acting on anything it surfaces.

---

## What this system will never do
- Never places a trade for you — every message ends with "you decide"
- Never touches F&O / derivatives
- Never gives a wealth holding a tight price-based stop-loss
- Never claims certainty — "no trade today" is a normal, expected output

## Extending it later (optional, not required)
- Add a `GEMINI_API_KEY` secret and a small script to have Gemini summarize
  recent news/headlines for your top weekly candidates — keep it to a
  shortlist of ~20 stocks since the free tier is rate-limited.
- Swap the hand-picked `watchlist.json` for a script that pulls NSE's full
  liquid-stock list automatically.
- Once you've watched this run untouched for 2–3 months, compare its calls
  against what actually happened before trusting it with real size.
