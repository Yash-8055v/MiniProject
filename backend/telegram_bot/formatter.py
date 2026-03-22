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

def _escape_url(url: str) -> str:
    """Escape URLs for Telegram MarkdownV2 inline links."""
    # Inside the (url) part of [text](url), only ) and \ need escaping
    return str(url).replace("\\", "\\\\").replace(")", "\\)")


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

    # ── Sources ──
    # Assuming sources is a list of dicts with 'title' and 'url'
    sources = data.get("sources", [])
    sources_text = ""
    if sources:
        sources_text = "\n\n".join(
            f"• [{_escape(s.get('title', 'Source'))}]({_escape_url(s.get('url', ''))})"
            for s in sources[:3] # Show max 3 sources to avoid huge messages
        )
    else:
        sources_text = "_No direct sources provided_"

    icon = _verdict_icon(verdict)
    
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
        "📰 *Sources:*",
        sources_text,
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


def format_trending(claims: list[dict], website_url: str) -> tuple[str, InlineKeyboardMarkup]:
    if not claims:
        # Return an empty keyboard if no claims
        return "No trending claims found right now\\. Check back later\\!", InlineKeyboardMarkup([])

    lines = ["🔥 *Trending Misinformation*", ""]

    for i, claim in enumerate(claims[:5], start=1):
        claim_text = claim.get("claim", "Unknown claim")
        region = claim.get("region", "global").capitalize()
        source_name = claim.get("source_name", "Source")
        source_url = claim.get("source_url")
        
        # Determine fallback analysis link
        url = source_url or f"{website_url.rstrip('/')}/analyze?q={urllib.parse.quote(claim_text)}"
        
        if len(claim_text) > 80:
            claim_text = claim_text[:77] + "..."
            
        # Plain text claim
        lines.append(f"{i}\\. {_escape(claim_text)}")
        
        # Sub-bullet with region
        lines.append(f"   📍 {_escape(region)}")
        
        # Sub-bullet with link
        if source_url and source_name and source_name.lower() != "unknown":
            lines.append(f"   🔗 [{_escape(source_name)}]({_escape_url(source_url)})")
        else:
            lines.append(f"   🔗 [View Analysis]({_escape_url(url)})")
            
        lines.append("") # Blank line for spacing

    trending_url = f"{website_url.rstrip('/')}/trending"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 View all trending claims", url=trending_url)]
    ])
    
    return "\n".join(lines), keyboard


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
