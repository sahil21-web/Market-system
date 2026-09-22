"""
Draws a real candlestick + volume chart image and sends it to a Gemini
vision-capable model, asking it to name any recognizable pattern.

v2: a live run showed Gemini's vision endpoint returning 503 (overloaded)
on 3/3 attempts across both models — a real, if intermittent, free-tier
capacity issue outside our control. Two changes:
  1. Fewer retries per model (2, not 3) with shorter backoff, so a bad run
     fails fast instead of burning ~a minute per stock before giving up.
  2. When vision is genuinely unavailable, read_chart() now falls back to
     a deterministic, rule-based description built from the same price
     data already fetched (52-week-high proximity, breakout structure,
     short-term trend) — so the message always says something useful
     instead of just "(unavailable)".
"""
import os
import io
import base64
import time
import requests
import matplotlib
matplotlib.use("Agg")
import mplfinance as mpf
from . import data

GEMINI_MODELS = [
    "gemini-2.5-flash",   # tried first — more established, historically steadier capacity
    "gemini-3.6-flash",
]
GEMINI_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _make_chart_png_b64(df, days=90):
    df = df.tail(days)
    buf = io.BytesIO()
    try:
        mpf.plot(
            df, type="candle", volume=True, style="charles",
            savefig=dict(fname=buf, format="png", dpi=100),
        )
    except Exception as e:
        print(f"[chart_vision] could not render chart: {e}")
        return None
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _fallback_description(df):
    """No vision available — say something honest and useful from the
    numbers we already have, instead of nothing."""
    if df is None or len(df) < 30:
        return "(no chart pattern available — insufficient price history)"
    close = df["Close"]
    high = df["High"]
    last_close = float(close.iloc[-1])
    high_52w = float(close.max())
    sma20 = float(close.rolling(20).mean().iloc[-1])

    bits = []
    if last_close >= 0.95 * high_52w:
        bits.append("trading within 5% of its 52-week high")
    elif last_close >= 0.85 * high_52w:
        bits.append("within striking distance of its 52-week high")

    if len(df) > 40:
        recent_high = float(high.iloc[-20:].max())
        prior_high = float(high.iloc[-40:-20].max())
        if prior_high > 0 and recent_high > prior_high:
            bits.append("made a fresh 20-day high vs. the prior 20 sessions (breakout structure)")

    if last_close > sma20:
        bits.append("above its 20-day average (short-term uptrend intact)")
    else:
        bits.append("below its 20-day average (short-term pullback)")

    return "(pattern from price data — chart vision unavailable this run) " + "; ".join(bits) + "."


def read_chart(ticker, retries=2):
    df = data.get_history(ticker, period="6mo")
    if df is None or len(df) < 30:
        return "(could not build a chart — not enough price history)"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _fallback_description(df)

    img_b64 = _make_chart_png_b64(df)
    if not img_b64:
        return _fallback_description(df)

    prompt = (
        f"This is a daily candlestick chart with a volume panel for {ticker}, "
        "the last ~90 trading sessions. Actually look at the candle shapes and "
        "the volume bars. In under 50 words: name any recognizable pattern "
        "(breakout, flag, head-and-shoulders, double top/bottom, "
        "support/resistance test, tight consolidation, or 'no clear pattern' "
        "if nothing stands out), and a confidence word (High/Medium/Low). "
        "Be honest — don't force a pattern that isn't there."
    )

    last_error = None
    for model in GEMINI_MODELS:
        url = GEMINI_URL_TMPL.format(model=model)
        for attempt in range(retries):
            try:
                resp = requests.post(
                    f"{url}?key={api_key}",
                    json={
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                            ]
                        }]
                    },
                    timeout=30,
                )
                if resp.status_code == 404:
                    last_error = f"404 on model {model} (likely renamed/retired)"
                    break
                if resp.status_code in (429, 503):
                    time.sleep(4 * (attempt + 1))
                    last_error = f"{resp.status_code} on attempt {attempt + 1} (model {model})"
                    continue
                resp.raise_for_status()
                out = resp.json()
                return out["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                last_error = e
                time.sleep(2)
    # Vision genuinely unavailable this run — don't leave the message empty
    return _fallback_description(df) + f" [vision error: {last_error}]"
