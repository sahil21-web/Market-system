"""
Sends the final message to your phone via Telegram. Reads the bot token and
chat id from environment variables so no secrets ever live in the code —
GitHub Actions injects them from repo Secrets at run time.
"""
import os
import requests


def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — printing message instead:\n")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram caps messages at 4096 chars; split if needed
    chunks = [message[i:i + 3500] for i in range(0, len(message), 3500)] or [message]
    for chunk in chunks:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=15)
        except Exception as e:
            print(f"Telegram send failed: {e}")
