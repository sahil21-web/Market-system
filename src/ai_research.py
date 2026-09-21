"""
AI reads the shortlist (never the full market, to stay inside free-tier
limits) and gives a judgment call — moat, risk, confidence — the way the
research chats described, instead of only mechanical math.

Text reasoning runs on Groq (src/llm_text.py) since its free tier is far
more generous than Gemini's. Chart images run separately on Gemini
(src/chart_vision.py) since that needs vision, which Groq's free models
don't reliably offer.

Updated to match the newer cash_screener.py's weighted-category schema
(score/label/stars/breakdown/risk_notes) instead of the older binary
checks_passed/checks_total — that mismatch (this file reading a field the
new screener no longer returns) was the cause of the daily run's KeyError
and exit code 1.
"""
from . import data, news
from .llm_text import call_groq


def research_cash_flow_candidate(hit):
    """hit = one dict from cash_screener.run_screen()"""
    headlines = news.get_recent_headlines(hit["ticker"], limit=5)
    headline_text = "\n".join(f"- {h}" for h in headlines) if headlines else "(no recent headlines found)"
    b = hit.get("breakdown", {})
    breakdown_text = ", ".join(f"{k.replace('_', ' ').title()} {v}" for k, v in b.items()) or "n/a"
    risk_notes = ", ".join(hit.get("risk_notes") or []) or "none flagged"
    prompt = f"""You are a cautious markets research assistant, not a salesperson.
Stock: {hit['ticker']}
Technical facts (already calculated, trust these, don't invent new numbers):
- Last close: {hit['close']}
- Composite score: {hit['score']}/100 ({hit.get('label', 'n/a')})
- Category breakdown: {breakdown_text}
- Risk flags already detected: {risk_notes}
- Suggested stop: {hit['suggested_stop']}, target: {hit.get('suggested_target')}, R:R {hit.get('risk_reward')}
Recent headlines:
{headline_text}

In under 70 words: is this a reasonable short-term swing candidate or not, whether the headlines support or contradict the technical setup, the single biggest risk to watch this week, and a confidence word (High/Medium/Low). Do not tell the user to buy — just give your read."""
    return call_groq(prompt)


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
    return call_groq(prompt)
