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
import time
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


def read_chart(ticker, retries=3):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "(chart reading skipped — no GEMINI_API_KEY secret set)"

    img_b64 = _make_chart_png_b64(ticker)
    if not img_b64:
        return "(could not build a chart image — not enough price history)"

    prompt = (
        f"This is a daily candlestick chart with a volume panel for {ticker}, "
        "the last ~90 trading sessions. Actually look at the candle shapes and "
        "volume bars, and classify what you see into ONE of these 12 named "
        "setup families (pick the closest match, or say 'no clear pattern' if "
        "genuinely nothing fits):\n"
        "1. Support Reversal — bounce off a support level with a bullish candle + volume\n"
        "2. Resistance Breakout — closes above a prior swing high/range top on volume\n"
        "3. Breakout + Retest — broke resistance, pulled back to retest it, held\n"
        "4. Trend Pullback — uptrend pulls back into a rising MA and reverses\n"
        "5. Momentum Continuation — flag/pennant/triangle/cup-handle after a strong move\n"
        "6. Oversold Reversal — real decline into support, momentum turning up\n"
        "7. Divergence Reversal — price and momentum disagree, then price confirms\n"
        "8. Volatility Compression → Expansion — tight range breaking out on volume\n"
        "9. Volume/Accumulation — selling dries up, buying builds, range contracts\n"
        "10. Liquidity/Structure Reversal — sweeps a low then reclaims it fast\n"
        "11. Multi-Timeframe Confluence — daily setup aligning with a bigger trend\n"
        "12. Event-Driven — a gap or breakout on a news catalyst, holding on volume\n\n"
        "In under 55 words: name the family, describe what you actually see (location, "
        "candle shape, volume behavior), and a confidence word (High/Medium/Low). "
        "Don't force a fit — 'no clear pattern' is a valid and often more honest answer."
    )
    last_error = None
    for attempt in range(retries):
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
            if resp.status_code in (429, 503):
                time.sleep(8 * (attempt + 1))
                last_error = f"{resp.status_code} on attempt {attempt + 1}"
                continue
            resp.raise_for_status()
            out = resp.json()
            return out["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            last_error = e
            time.sleep(4)
    return f"(chart reading unavailable after retries: {last_error})"
