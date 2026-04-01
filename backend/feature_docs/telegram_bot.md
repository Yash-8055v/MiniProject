# 🤖 Telegram Bot Feature — Explanation

## What It Does

A Telegram bot where users can **send a claim (text or voice)** and get a fact-check verdict back — without visiting the website.

---

## Files

| File | Purpose |
|------|---------|
| `telegram_bot/bot.py` | Builds the bot app, registers all command handlers |
| `telegram_bot/handlers.py` | Logic for each command (/check, /trending, voice, etc.) |
| `telegram_bot/formatter.py` | Formats messages with emojis, buttons, MarkdownV2 |
| `telegram_bot/rate_limiter.py` | Max 5 requests per user per 60 seconds |
| `telegram_bot/user_prefs.py` | Stores each user's preferred language (EN/HI/MR) |

---

## Bot Commands

| Command | What it does |
|---------|-------------|
| `/start` | Welcome message with usage guide |
| `/help` | Lists all available commands |
| `/check <claim>` | Fact-check a specific claim |
| `/trending` | Shows top 5 trending misinformation claims |
| `/language` | Pick response language (English / Hindi / Marathi) |
| *Send voice message* | Transcribes → fact-checks → replies with text + voice |
| *Send plain text* | Only works as reply to bot's prompt (prevents spam) |

---

## How Each Feature Works

### `/check <claim>` Flow (handlers.py lines 119-159)

```
User: /check Modi visited France
  ↓
1. Rate limit check (max 5/min per user)
  ↓
2. Show "🔍 Analysing claim... please wait"
  ↓
3. _analyze_claim(claim):
   ├─ Hash claim → check MongoDB cache
   ├─ HIT → return cached result
   └─ MISS → run_crew() pipeline → get verdict → cache result
  ↓
4. Format result with verdict, confidence, explanation, sources
  ↓
5. Add inline buttons: [🇬🇧 English] [🇮🇳 Hindi] [🇲🇭 Marathi] [🔗 View Full Analysis]
  ↓
6. Edit the "please wait" message with the result
```

### Voice Message Flow (handlers.py lines 353-450)

```
User: sends voice message (Hindi/Marathi/English)
  ↓
1. Rate limit check
  ↓
2. Download OGG audio from Telegram servers
  ↓
3. Send audio to Sarvam AI STT → get text transcript
  ↓
4. Show "🎙️ Heard: <transcript>... 🔍 Fact-checking..."
  ↓
5. _analyze_claim(transcript) → same as /check
  ↓
6. Reply with text verdict + inline buttons
  ↓
7. Send voice reply back using Sarvam AI TTS (in user's language)
```

### `/trending` Flow (handlers.py lines 164-183)

```
User: /trending
  ↓
1. Read top 5 claims from MongoDB (get_trending_claims)
  ↓
2. Format as numbered list with region + source link
  ↓
3. Add button: [🔗 View all trending claims] → links to website
```

### Language Switching (handlers.py lines 241-301)

Two types of language buttons:

**1. `/language` command** → sets default language for future responses
```
callback: setlang|hi → saves preference in memory
```

**2. Inline buttons on analysis** → switch language on THAT specific message
```
callback: lang|<claim_hash>|hi → fetches cached analysis → re-renders in Hindi
```

Both work via `handle_callback_query()` which reads the callback data format.

---

## How Bot Starts (api.py lines 113-131)

The bot runs **inside the FastAPI server** (not as a separate process):

```python
# api.py line 114
if os.getenv("TELEGRAM_BOT_TOKEN"):
    _bot_app = build_application()
    await _bot_app.initialize()
    await _bot_app.bot.set_my_commands(BOT_COMMANDS)    # register menu
    await _bot_app.start()
    await _bot_app.updater.start_polling()              # start listening
```

- Uses **polling mode** (bot asks Telegram "any new messages?" repeatedly)
- Only starts if `TELEGRAM_BOT_TOKEN` is set in `.env`
- Shuts down cleanly when server stops (api.py lines 134-142)

---

## Rate Limiting (rate_limiter.py)

```python
rate_limiter = RateLimiter(max_calls=5, period=60)
# 5 requests per user per 60 seconds
```

How it works:
- Stores timestamps of each user's requests in a list
- On new request → remove timestamps older than 60s → count remaining
- If count < 5 → allowed ✅
- If count >= 5 → blocked ⏳ (tells user how many seconds to wait)

---

## User Preferences (user_prefs.py)

```python
_prefs: dict[int, str] = {}    # {telegram_user_id: "hi"}

# In-memory only — resets on server restart
# Default language: English
```

Supports: `en` (English), `hi` (Hindi), `mr` (Marathi)

---

## Message Formatting (formatter.py)

Telegram uses **MarkdownV2** which requires escaping special characters. The `_escape()` function handles this:

```python
special = r"\_*[]()~`>#+-=|{}.!"
# Every special char gets a \ prefix
```

### Analysis Message Format:
```
🚨 Claim Analysis

Claim: Modi visited France

Status: ❌ Likely False
Confidence: 72%

Explanation: No official records show...

📰 Sources:
• Reuters Article (link)
• NDTV Report (link)

[🇬🇧 English] [🇮🇳 Hindi] [🇲🇭 Marathi]
[🔗 View Full Analysis]
```

---

## Summary

| What | Detail |
|------|--------|
| **Library** | `python-telegram-bot` |
| **Mode** | Polling (inside FastAPI server) |
| **Commands** | /start, /help, /check, /trending, /language |
| **Voice** | Sarvam STT (speech→text) + Sarvam TTS (text→speech) |
| **Languages** | English, Hindi, Marathi (switchable per message) |
| **Rate Limit** | 5 requests/user/minute |
| **Caching** | Shares same MongoDB analysis_cache as website (24h TTL) |
| **Backend Reuse** | Calls same `run_crew()` and `get_trending_claims()` as website API |
