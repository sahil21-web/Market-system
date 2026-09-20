import os
import requests
import time

# Active Groq model priority list with fallbacks to avoid 404 deprecation outages
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "qwen/qwen3.8-27b"
]

def query_text_llm(prompt: str, max_tokens: int = 1000) -> str:
    """
    Queries the Groq API for text-based market research.
    Loops through fallback models automatically if a model is deprecated (404) or rate-limited (429).
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "(AI research unavailable: GROQ_API_KEY environment variable is not set.)"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    last_error = ""

    for model in GROQ_MODELS:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a senior equity research analyst providing direct, quantitative, and concise stock market analysis."
                },
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }

        # gpt-oss models utilize reasoning tokens
        if "gpt-oss" in model:
            payload["reasoning_effort"] = "low"
            payload["max_tokens"] = max(max_tokens, 1500)

        for attempt in range(2):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return content.strip()
                elif response.status_code in (404, 429, 400):
                    last_error = f"HTTP {response.status_code} ({model}): {response.text}"
                    break  # Move to fallback model
                else:
                    response.raise_for_status()
            except Exception as e:
                last_error = f"Error with model {model}: {str(e)}"
                time.sleep(1)

    return f"(AI research unavailable after retries: {last_error})"
