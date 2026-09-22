"""
Shared helpers for turning scores into the same red/yellow/green language
across the daily and weekly messages, and escaping text for Telegram's HTML
parse mode so a stray "<" or "&" in a headline can't break formatting.
"""
import html


def escape(text):
    return html.escape(str(text), quote=False)


def score_dot(score, strong=75, moderate=60):
    if score >= strong:
        return "🟢"
    if score >= moderate:
        return "🟡"
    return "🟠"


def regime_dot(score):
    if score >= 65:
        return "🟢"
    if score >= 45:
        return "🟡"
    if score >= 25:
        return "🟠"
    return "🔴"


def strength_word(score, strong=75, moderate=60):
    if score >= strong:
        return "Strong"
    if score >= moderate:
        return "Moderate"
    return "Weak"
