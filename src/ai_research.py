"""
This is the piece that was missing: an actual AI model reading data about a
shortlisted stock and giving a judgment call, the way the ChatGPT/Gemini
research chats described (moat, risk, confidence) — instead of only mechanical
math. Uses Gemini's free API. Runs only on the short list the rule-based
screeners already narrowed down to (never the full market) to stay inside the
free tier's rate limits.
"""
import os
import json
import requests
from . import data, news

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "(AI research skipped — no GEMINI_API_KEY secret set yet)"
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        out = resp.json()
        return out["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"(AI research unavailable right now: {e})"


def research_cash_flow_candidate(hit):
    """hit = one dict from cash_screener.run_screen()"""
    headlines = news.get_recent_headlines(hit["ticker"], limit=5)
    headline_text = "\n".join(f"- {h}" for h in headlines) if headlines else "(no recent headlines found)"
    prompt = f"""You are a cautious markets research assistant, not a salesperson.
Stock: {hit['ticker']}
Technical facts (already calculated, trust these, don't invent new numbers):
- Last close: {hit['close']}
- Passed {hit['checks_passed']}/3 momentum checks (trend, RSI cross, volume)
- Suggested stop: {hit['suggested_stop']}, target: {hit.get('suggested_target')}, R:R {hit.get('risk_reward')}
Recent headlines:
{headline_text}

In under 70 words: is this a reasonable short-term swing candidate or not, whether the headlines support or contradict the technical setup, the single biggest risk to watch this week, and a confidence word (High/Medium/Low). Do not tell the user to buy — just give your read."""
    return _call_gemini(prompt)


def research_wealth_candidate(hit):
    """hit = one dict from wealth_screener.run_screen()"""
    info = data.get_info(hit["ticker"])
    business = info.get("longBusinessSummary", "")[:600]
    headlines = news.get_recent_headlines(hit["ticker"], limit=5)
    headline_text = "\n".join(f"- {h}" for h in headlines) if headlines else "(no recent headlines found)"
    prompt = f"""You are a cautious long-term equity research assistant, not a salesperson.
Stock: {hit['ticker']}
Fundamental facts (already calculated, trust these):
- ROE: {hit['roe_pct']}%
- Revenue growth: {hit['revenue_growth_pct']}%
- Debt/Equity: {hit['debt_to_equity']}
Business description: {business}
Recent headlines:
{headline_text}

In under 100 words: does this look like a business with a real durable advantage (moat) worth researching further for a multi-year hold, whether recent news raises any concern, the biggest red flag or open question, and a confidence word (High/Medium/Low). Do not tell the user to buy — just give your honest read, including reasons to be skeptical."""
    return _call_gemini(prompt)
