import os
import time
import base64
import requests
from src.llm_text import query_text_llm

def read_chart_image(image_path: str, prompt: str = "Analyze this stock chart. Summarize trend, support/resistance levels, and key indicators.") -> str:
    """
    Performs vision analysis on a chart image via Gemini REST API with exponential backoff retries.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return "(Chart read unavailable: GEMINI_API_KEY not set)"

    if not os.path.exists(image_path):
        return "(Chart read unavailable: Image file not found)"

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        return f"(Chart read unavailable: Failed to read image file - {e})"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": encoded_image
                    }
                }
            ]
        }]
    }
    headers = {"Content-Type": "application/json"}

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        for attempt in range(1, 4):  # Exponential backoff (2s, 4s, 8s)
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text_res = "".join([p.get("text", "") for p in parts if "text" in p])
                        if text_res:
                            return text_res.strip()
                elif response.status_code in (503, 429, 500):
                    time.sleep(2 ** attempt)
                    continue
                else:
                    break  # Move to next model if non-retriable error
            except Exception:
                time.sleep(2 ** attempt)

    return "(chart reading unavailable after retries: Service temporary overload)"

def generate_stock_research(ticker: str, news_context: str = "", chart_image_path: str = None) -> dict:
    """
    Runs combined text AI research via Groq and optional chart image reading via Gemini Vision.
    """
    prompt = f"Analyze stock ticker: {ticker}.\nNews/Context:\n{news_context}\n\nProvide core bullish/bearish arguments, valuation insights, and key risk factors."
    
    text_analysis = query_text_llm(prompt)
    
    chart_analysis = "No chart provided."
    if chart_image_path and os.path.exists(chart_image_path):
        chart_analysis = read_chart_image(chart_image_path)

    return {
        "ticker": ticker,
        "text_research": text_analysis,
        "chart_research": chart_analysis
    }
