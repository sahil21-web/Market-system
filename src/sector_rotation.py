"""
Ranks NSE sector indices so the system can tell you which industries actually
have momentum, instead of scanning individual stocks blind to sector context —
the "which sectors are going to rise" part of the original question.
"""
from . import data

SECTOR_INDICES = {
    "Auto": "^CNXAUTO",
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY",
    "PSU Bank": "^CNXPSUBANK",
    "Bank": "^NSEBANK",
    "Financial Services": "^CNXFIN",
    "Media": "^CNXMEDIA",
    "Infra": "^CNXINFRA",
}


def _return_pct(df, days):
    if df is None or len(df) < days + 1:
        return None
    start = float(df["Close"].iloc[-days - 1])
    end = float(df["Close"].iloc[-1])
    if start == 0:
        return None
    return round(100 * (end - start) / start, 2)


def rank_sectors():
    nifty = data.get_history("^NSEI", period="6mo")  # benchmark for relative strength
    bench_1m = _return_pct(nifty, 21)

    results = []
    for name, ticker in SECTOR_INDICES.items():
        df = data.get_history(ticker, period="6mo")
        ret_1m = _return_pct(df, 21)
        ret_3m = _return_pct(df, 63)
        if ret_1m is None or ret_3m is None:
            continue
        rel_strength = round(ret_1m - bench_1m, 2) if bench_1m is not None else None
        score = round(0.4 * ret_1m + 0.6 * ret_3m, 2)  # weight the longer trend more
        results.append({
            "sector": name,
            "1m_return_pct": ret_1m,
            "3m_return_pct": ret_3m,
            "relative_strength_vs_nifty_1m": rel_strength,
            "score": score,
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
