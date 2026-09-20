"""
This is the piece that actually looks at candles. It draws a real candlestick
+ volume chart image and sends it to Gemini's vision-capable model, asking it
to name any recognizable pattern — the way a human chartist would look at a
chart, not just compute numbers from it. Runs only on the shortlist to stay
inside the free API rate limit.
"""
import os
import io
import base64
import requests
import matplotlib
matplotlib.use("Agg")
import mplfinance as mpf
from . import data

GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"


def _make_chart_png_b64(ticker, days=90):
    df = data.get_history(ticker, period="6mo")
    if df is None or len(df) < 30:
        return None
    df = df.tail(days)
    buf = io.BytesIO()
    try:
        mpf.plot(
            df, type="candle", volume=True, style="charles",
            savefig=dict(fname=buf, format="png", dpi=100),
        )
    except Exception as e:
        print(f"[chart_vision] could not render chart for {ticker}: {e}")
        return None
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def read_chart(ticker):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "(chart reading skipped — no GEMINI_API_KEY secret set)"

    img_b64 = _make_chart_png_b64(ticker)
    if not img_b64:
        return "(could not build a chart image — not enough price history)"

    prompt = (
        f"This is a daily candlestick chart with a volume panel for {ticker}, "
        "the last ~90 trading sessions. Actually look at the candle shapes and "
        "the volume bars. In under 50 words: name any recognizable pattern "
        "(breakout, flag, head-and-shoulders, double top/bottom, "
        "support/resistance test, tight consolidation, or 'no clear pattern' "
        "if nothing stands out), and a confidence word (High/Medium/Low). "
        "Be honest — don't force a pattern that isn't there."
    )
    try:
        resp = requests.post(
            f"{GEMINI_VISION_URL}?key={api_key}",
            json={
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                    ]
                }]
            },
            timeout=45,
        )
        resp.raise_for_status()
        out = resp.json()
        return out["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"(chart reading unavailable right now: {e})"
