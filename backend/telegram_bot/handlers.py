"""
Telegram bot command and message handlers for TruthCrew.
Supports EN / HI / MR explanations with inline language switcher.
"""

import os
import asyncio
import logging
from functools import partial

from telegram import Update, ForceReply
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

from telegram_bot.rate_limiter import rate_limiter
from telegram_bot import formatter as fmt
from telegram_bot.user_prefs import get_language, set_language, get_lang_name

logger = logging.getLogger(__name__)


# ── Shared async helper: run blocking analysis in executor ───────────────────

async def _analyze_claim(claim: str) -> dict:
    """
    Analyze a claim using existing backend logic.
    Checks MongoDB cache first; falls back to Groq pipeline.
    Returns dict with all 3 language fields: explanation, explanation_hi, explanation_mr.
    """
    from database.db import make_claim_hash, get_cached_analysis, set_cached_analysis
    from crew.crew import run_crew
    from server.heatmap import get_google_trends_heatmap

    website_url = os.getenv("WEBSITE_URL", "https://truthcrew.vercel.app").rstrip("/")
    import urllib.parse
    encoded = urllib.parse.quote(claim)
    full_url = f"{website_url}/analyze?q={encoded}"

    # ── Cache check ──
    claim_hash = make_claim_hash(claim)
    cached = get_cached_analysis(claim_hash)
    if cached is not None:
        logger.info(f"🔥 Bot analysis cache HIT for: {claim[:60]}")
        cached["url"] = full_url
        cached["_hash"] = claim_hash
        return cached

    logger.info(f"🔍 Bot running crew for: {claim[:60]}")
    loop = asyncio.get_event_loop()

    # Run crew (blocking) in thread executor
    crew_result = await loop.run_in_executor(
        None,
        partial(run_crew, {"text": claim, "image_provided": False}),
    )

    # Fetch heatmap for top regions
    try:
        heatmap = await loop.run_in_executor(
            None, partial(get_google_trends_heatmap, claim)
        )
        sorted_regions = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)
        top_regions = [r for r, score in sorted_regions[:5] if score > 0]
    except Exception:
        top_regions = []

    data = {
        "claim": claim,
        "verdict": crew_result.get("verdict", "Unknown"),
        "confidence": crew_result.get("confidence", 0),
        # All three languages from crew output
        "explanation": crew_result.get("english", ""),
        "explanation_hi": crew_result.get("hindi", ""),
        "explanation_mr": crew_result.get("marathi", ""),
        "sources": crew_result.get("sources", []),
        "top_regions": top_regions,
        "url": full_url,
    }

    set_cached_analysis(claim_hash, data)
    data["_hash"] = claim_hash
    return data


# ── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        fmt.format_welcome(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /help ────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        fmt.format_help(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /language ────────────────────────────────────────────────────────────────

async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a language picker so the user can set their preference."""
    user_id = update.effective_user.id
    current = get_language(user_id)
    text, keyboard = fmt.format_language_picker(current)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /check <claim> ───────────────────────────────────────────────────────────

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    if not rate_limiter.is_allowed(user_id):
        secs = rate_limiter.remaining_seconds(user_id)
        await update.message.reply_text(
            f"⏳ You're sending too many requests\\. Please wait *{secs}s*\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    claim = " ".join(context.args).strip() if context.args else ""
    if not claim:
        await update.message.reply_text(
            "⚠️ Please reply to this message with the claim you want to check\\.\n\n"
            "Or just type any claim directly in the chat\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ForceReply(selective=True)
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    processing_msg = await update.message.reply_text(
        "🔍 *Analysing claim\\.\\.\\. please wait\\.*",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _analyze_claim(claim)
        lang = get_language(user_id)
        text, keyboard = fmt.format_analysis(data, lang=lang, claim_hash=data["_hash"])
        await processing_msg.edit_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logger.error(f"Claim analysis failed for '{claim}': {e}")
        await processing_msg.edit_text(
            "❌ Unable to analyse the claim right now\\. Please try again in a moment\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


# ── /trending ────────────────────────────────────────────────────────────────

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        from database.db import get_trending_claims
        claims = get_trending_claims(limit=5)
    except Exception as e:
        logger.error(f"Failed to fetch trending claims: {e}")
        await update.message.reply_text(
            "❌ Unable to fetch trending claims right now\\. Please try again later\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    website_url = os.getenv("WEBSITE_URL", "https://truthcrew.vercel.app")
    text, keyboard = fmt.format_trending(claims, website_url)
    await update.message.reply_text(
        text, 
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard
    )


# ── Natural language / plain text ────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    # Restrict random texts: only process if it's a direct reply to the bot's ForceReply prompt
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id
    )
    
    if not is_reply_to_bot:
        await update.message.reply_text(
            "👋 Hi\\! To verify a news claim, please use the `/check` command from the menu\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if not rate_limiter.is_allowed(user_id):
        secs = rate_limiter.remaining_seconds(user_id)
        await update.message.reply_text(
            f"⏳ You're sending too many requests\\. Please wait *{secs}s*\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    claim = _extract_claim(text)
    await update.message.chat.send_action(ChatAction.TYPING)
    processing_msg = await update.message.reply_text(
        f"🔍 *Fact\\-checking:* _{fmt._escape(claim[:80])}_\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        data = await _analyze_claim(claim)
        lang = get_language(user_id)
        reply_text, keyboard = fmt.format_analysis(
            data, lang=lang, claim_hash=data["_hash"]
        )
        await processing_msg.edit_text(
            reply_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logger.error(f"Natural language analysis failed: {e}")
        await processing_msg.edit_text(
            "❌ Unable to analyse the claim right now\\. Please try again later\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


# ── Callback query handler (language buttons) ─────────────────────────────────

async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handles two callback types:
      • lang|<claim_hash>|<lang_code>   → switch language on an analysis message
      • setlang|<lang_code>             → set persistent language preference
    """
    query = update.callback_query
    await query.answer()  # acknowledge immediately (removes loading spinner)

    data = query.data or ""

    # ── Language preference setter (/language command picker) ──
    if data.startswith("setlang|"):
        lang_code = data.split("|", 1)[1]
        set_language(query.from_user.id, lang_code)
        lang_name = get_lang_name(lang_code)
        text, keyboard = fmt.format_language_picker(lang_code)
        try:
            await query.edit_message_text(
                text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception:
            pass
        await query.answer(f"✅ Language set to {lang_name}", show_alert=False)
        return

    # ── Inline language switcher on an analysis card ──
    if data.startswith("lang|"):
        parts = data.split("|")
        if len(parts) != 3:
            return
        _, claim_hash, lang_code = parts

        # Retrieve cached analysis
        try:
            from database.db import get_cached_analysis
            cached = get_cached_analysis(claim_hash)
        except Exception:
            cached = None

        if not cached:
            await query.answer(
                "⏳ Analysis expired. Please run /check again.", show_alert=True
            )
            return

        cached["_hash"] = claim_hash
        reply_text, keyboard = fmt.format_analysis(
            cached, lang=lang_code, claim_hash=claim_hash
        )
        try:
            await query.edit_message_text(
                reply_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            # Message not modified (same language clicked) — that's fine
            logger.debug(f"Callback edit suppressed: {e}")


# ── Natural language claim extractor ────────────────────────────────────────

def _extract_claim(text: str) -> str:
    import re
    prefixes = [
        r"^is it true that\s+",
        r"^is it a fact that\s+",
        r"^i heard that\s+",
        r"^did you know that\s+",
        r"^fact check[:\s]+",
        r"^check[:\s]+",
        r"^verify[:\s]+",
        r"^is\s+it\s+true\s+",
    ]
    cleaned = text.strip()
    for pattern in prefixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.rstrip("?").strip() or text
