"""
Groq's free tier is far more generous than Gemini's for text (30 requests/min,
up to 14,400/day vs Gemini's ~20/day) — so all text reasoning goes here now,
and Gemini is reserved only for chart images (src/chart_vision.py), where its
vision capability is actually needed. This keeps both providers comfortably
inside their free limits.
"""
import os
import time
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def call_groq(prompt, retries=3):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "(AI research skipped — no GROQ_API_KEY secret set yet)"
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                timeout=30,
            )
            if resp.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                last_error = f"{resp.status_code} on attempt {attempt + 1}"
                continue
            resp.raise_for_status()
            out = resp.json()
            return out["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_error = e
            time.sleep(3)
    return f"(AI research unavailable after retries: {last_error})"
