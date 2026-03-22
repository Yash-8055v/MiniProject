"""
Message formatter for the TruthCrew Telegram bot.
Supports English, Hindi, and Marathi output via inline language buttons.
"""

import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ── Verdict emoji mapping ──────────────────────────────────────────────────
VERDICT_ICON = {
    "false": "❌",
    "misleading": "⚠️",
    "true": "✅",
    "likely true": "✅",
    "partially true": "⚠️",
    "unknown": "❓",
    "unverified": "❓",
}

# Language display labels for buttons
LANG_LABELS = {"en": "🇬🇧 English", "hi": "🇮🇳 Hindi", "mr": "🇲🇭 Marathi"}


def _verdict_icon(verdict: str) -> str:
    return VERDICT_ICON.get(verdict.lower(), "❓")


def _escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def format_analysis(
    data: dict,
    lang: str = "en",
    claim_hash: str = "",
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Format a claim analysis dict into a Telegram MarkdownV2 message.

    Args:
        data: dict with keys claim, verdict, confidence, explanation /
              explanation_hi / explanation_mr, top_regions, url
        lang: 'en', 'hi', or 'mr'
        claim_hash: MD5 hash used to build language-switch callback data

    Returns:
        (message_text, InlineKeyboardMarkup)
    """
    claim = data.get("claim", "")
    verdict = data.get("verdict", "Unknown")
    confidence = data.get("confidence", 0)
    top_regions = data.get("top_regions", [])
    url = data.get("url", "")

    # Pick explanation in requested language, fall back to English
    if lang == "hi":
        explanation = data.get("explanation_hi") or data.get("explanation", "")
        if not explanation:
            explanation = data.get("explanation", "No explanation available.")
    elif lang == "mr":
        explanation = data.get("explanation_mr") or data.get("explanation", "")
        if not explanation:
            explanation = data.get("explanation", "No explanation available.")
    else:
        explanation = data.get("explanation", "No explanation available.")

    # Truncate for readability
    if len(explanation) > 350:
        explanation = explanation[:347] + "..."

    icon = _verdict_icon(verdict)
    regions_text = (
        ", ".join(top_regions) if top_regions else "No regional data available"
    )

    lines = [
        "🚨 *Claim Analysis*",
        "",
        f"*Claim:* {_escape(claim)}",
        "",
        f"*Status:* {icon} {_escape(verdict.title())}",
        f"*Confidence:* {_escape(str(confidence))}%",
        "",
        "*Explanation:*",
        _escape(explanation),
        "",
        "🌍 *Geographic Spread:*",
        f"Top regions: {_escape(regions_text)}",
    ]

    text = "\n".join(lines)

    # ── Language toggle buttons ──
    lang_buttons = []
    for code, label in LANG_LABELS.items():
        display = f"{label} ✓" if code == lang else label
        callback = f"lang|{claim_hash}|{code}"
        lang_buttons.append(InlineKeyboardButton(display, callback_data=callback))

    keyboard = InlineKeyboardMarkup(
        [
            lang_buttons,
            [InlineKeyboardButton("🔗 View Full Analysis", url=url)],
        ]
    )

    return text, keyboard


def format_trending(claims: list[dict], website_url: str) -> str:
    if not claims:
        return "No trending claims found right now\\. Check back later\\!"

    lines = ["🔥 *Trending Misinformation*", ""]

    for i, claim in enumerate(claims[:5], start=1):
        claim_text = claim.get("claim", "Unknown claim")
        region = claim.get("region", "global").capitalize()
        if len(claim_text) > 80:
            claim_text = claim_text[:77] + "..."
        lines.append(f"{i}\\. {_escape(claim_text)} \\({_escape(region)}\\)")

    trending_url = f"{website_url.rstrip('/')}/trending"
    lines += ["", f"🔗 [View all trending claims]({trending_url})"]
    return "\n".join(lines)


def format_welcome() -> str:
    return (
        "👋 *Welcome to TruthCrew Bot\\!*\n\n"
        "I help you verify claims and spot misinformation\\.\n\n"
        "Here's what I can do:\n"
        "• /check \\<claim\\> — Analyse any claim\n"
        "• /trending — See top trending misinformation\n"
        "• /language — Change response language \\(EN / HI / MR\\)\n"
        "• /help — Show all commands\n\n"
        "Just send me a claim and I'll fact\\-check it for you\\! 🔍"
    )


def format_help() -> str:
    return (
        "📖 *Available Commands*\n\n"
        "/start — Welcome message\n"
        "/help — Show this help message\n"
        "/check \\<claim\\> — Analyse a specific claim\n"
        "/trending — Show top trending misinformation\n"
        "/language — Change response language \\(English / Hindi / Marathi\\)\n\n"
        "💡 *Tip:* You can also just send me any sentence and I'll fact\\-check it\\!\n"
        "🌐 *Languages:* Responses available in English, Hindi, and Marathi\\."
    )


def format_language_picker(current_lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Show a language selection menu."""
    text = (
        "🌐 *Choose your preferred language*\n\n"
        "Your selected language will be used for all future analyses\\."
    )
    buttons = []
    for code, label in LANG_LABELS.items():
        display = f"{label} ✓" if code == current_lang else label
        buttons.append(
            InlineKeyboardButton(display, callback_data=f"setlang|{code}")
        )
    keyboard = InlineKeyboardMarkup([buttons])
    return text, keyboard
