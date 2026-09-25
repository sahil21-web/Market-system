"""
Sends the built message to Telegram. Upgraded to send HTML (bold, so the
message is actually scannable) instead of plain text, and to split
messages over Telegram's 4096-character limit instead of silently failing
or truncating on a long watchlist day.

Reconstructed to match how scripts/run_daily.py and run_weekly.py call it
(alerts.send_telegram(message)) since the original wasn't in any uploaded
zip. If you already have a working alerts.py, keep yours — just add
parse_mode="HTML" and the chunking loop below, since that's what the new
message formatting in scripts/run_daily.py now relies on.
"""
import os
import time
import requests

TELEGRAM_MAX_LEN = 4096


def _chunk_message(message, max_len=TELEGRAM_MAX_LEN):
    """Split on line boundaries so we never cut an HTML tag in half."""
    if len(message) <= max_len:
        return [message]
    chunks = []
    current = ""
    for line in message.split("\n"):
        candidate = current + ("\n" if current else "") + line
        if len(candidate) > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def send_telegram(message, parse_mode="HTML", retries=3):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[alerts] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — printing instead:")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for chunk in _chunk_message(message):
        sent = False
        last_error = None
        for attempt in range(retries):
            try:
                resp = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode,
                          "disable_web_page_preview": True},
                    timeout=20,
                )
                if resp.status_code == 429:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                    time.sleep(retry_after)
                    continue
                if resp.status_code == 400 and parse_mode:
                    # malformed HTML in one chunk shouldn't lose the whole brief —
                    # fall back to plain text for this chunk only
                    resp = requests.post(
                        url,
                        json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                        timeout=20,
                    )
                resp.raise_for_status()
                sent = True
                break
            except Exception as e:
                last_error = e
                time.sleep(2)
        if not sent:
            print(f"[alerts] failed to send a message chunk after {retries} retries: {last_error}")
            ok = False
    return ok
