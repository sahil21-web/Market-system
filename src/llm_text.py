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

# llama-3.3-70b-versatile was retired by Groq (shut down 08/16/2026), which is
# why every call was 404ing. Groq's own recommended replacement is
# openai/gpt-oss-120b, with qwen/qwen3.6-27b as the second-choice fallback.
# Model IDs on free platforms get deprecated periodically, so we try a short
# list in order rather than hardcoding one — if the primary one ever gets
# retired again, the fallback list absorbs it instead of the whole pipeline
# silently 404ing again.
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
]


def call_groq(prompt, retries=3):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "(AI research skipped — no GROQ_API_KEY secret set yet)"
    last_error = None
    for model in GROQ_MODELS:
        for attempt in range(retries):
            try:
                resp = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=30,
                )
                if resp.status_code == 404:
                    # This model ID no longer exists on Groq (deprecated/retired) —
                    # no point retrying the same model, move to the next one.
                    last_error = f"404 on model {model} (likely deprecated)"
                    break
                if resp.status_code in (429, 503):
                    time.sleep(5 * (attempt + 1))
                    last_error = f"{resp.status_code} on attempt {attempt + 1} (model {model})"
                    continue
                resp.raise_for_status()
                out = resp.json()
                return out["choices"][0]["message"]["content"].strip()
            except Exception as e:
                last_error = e
                time.sleep(3)
    return f"(AI research unavailable after retries: {last_error})"
