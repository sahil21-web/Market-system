"""
Scans a stock's actual recent headlines for events that precede sudden
drops — fraud, regulatory action, auditor resignation, guidance cuts,
promoter selling/pledging. Keyword-based, not deep NLP: a real but limited
safety net. It catches stories already public. It CANNOT predict a surprise
announcement that hasn't been reported yet — no free-data system can, and a
stop-loss doesn't protect against an overnight gap past it either. That's a
real, irreducible risk of holding any single stock.
"""
from . import news

RED_FLAG_KEYWORDS = [
    "fraud", "sebi probe", "sebi investigation", "raid", "cbi", "ed probe",
    "enforcement directorate", "auditor resign", "resignation of auditor",
    "promoter pledge", "pledge increase", "promoter selling", "stake sale by promoter",
    "guidance cut", "profit warning", "downgrade", "default", "insolvency",
    "bankruptcy", "delisting", "show cause notice", "penalty imposed",
    "credit rating downgrade", "going concern", "restatement", "accounting irregular",
    "resignation of ceo", "resignation of cfo", "whistleblower",
]


def check_red_flags(ticker):
    headlines = news.get_recent_headlines(ticker, limit=8)
    hits = []
    for h in headlines:
        h_lower = h.lower()
        for kw in RED_FLAG_KEYWORDS:
            if kw in h_lower:
                hits.append({"headline": h, "matched": kw})
                break
    return hits
