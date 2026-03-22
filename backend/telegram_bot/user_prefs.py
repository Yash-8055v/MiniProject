"""
In-memory user language preferences for TruthCrew Telegram bot.
Stores each user's preferred language (persists until server restart).
"""

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English 🇬🇧",
    "hi": "Hindi 🇮🇳",
    "mr": "Marathi 🇲🇭",
}

# Maps telegram user_id → language code ('en', 'hi', 'mr')
_prefs: dict[int, str] = {}


def get_language(user_id: int) -> str:
    """Return the user's preferred language, defaulting to English."""
    return _prefs.get(user_id, "en")


def set_language(user_id: int, lang: str) -> None:
    """Persist a language preference for a user."""
    if lang in SUPPORTED_LANGUAGES:
        _prefs[user_id] = lang


def get_lang_name(lang: str) -> str:
    """Return the display name for a language code."""
    return SUPPORTED_LANGUAGES.get(lang, "English 🇬🇧")
