# 🎙️ Voice Feature (STT + TTS) — Explanation

## What It Does

- **STT (Speech-to-Text):** User sends audio → gets text back
- **TTS (Text-to-Speech):** Send text → get audio back

Both powered by **Sarvam AI** — an Indian AI company that supports Hindi, Marathi & English.

---

## Files

| File | Purpose |
|------|---------|
| `server/api.py` lines 883-1038 | API endpoints `/api/agents/stt` and `/api/agents/tts` |
| `telegram_bot/handlers.py` lines 306-348 | Bot uses STT/TTS directly via Sarvam API (not through our endpoints) |

---

## STT — Speech-to-Text

**Endpoint:** `POST /api/agents/stt`

```
User uploads audio file (.webm, .wav, .mp3, .ogg)
  ↓
Send to Sarvam AI: https://api.sarvam.ai/speech-to-text
  ↓
Sarvam auto-detects language (Hindi/Marathi/English)
  ↓
Returns: { "transcript": "क्या 5G से कोरोना फैलता है" }
```

**Code (api.py lines 926-935):**
```python
response = await client.post(
    "https://api.sarvam.ai/speech-to-text",
    headers={"api-subscription-key": api_key},
    files={"file": (filename, content, content_type)},
    data={"language_code": "unknown"},    # auto-detect language
)
transcript = response.json().get("transcript", "")
```

**Key points:**
- `language_code: "unknown"` → Sarvam figures out the language automatically
- Timeout: 30 seconds
- Requires `SARVAM_API_KEY` in `.env`

---

## TTS — Text-to-Speech

**Endpoint:** `POST /api/agents/tts`

```
User sends: { "text": "This claim is false", "language": "hi-IN" }
  ↓
Send to Sarvam AI: https://api.sarvam.ai/text-to-speech
  ↓
Sarvam generates audio using Bulbul v3 model
  ↓
Returns: WAV audio stream (user hears the text spoken)
```

**3 Voices (api.py lines 952-956):**

| Language | Code | Voice Name |
|----------|------|------------|
| Hindi | `hi-IN` | Priya |
| Marathi | `mr-IN` | Kavitha |
| English | `en-IN` | Rahul |

**Code (api.py lines 1017-1032):**
```python
response = await client.post(
    "https://api.sarvam.ai/text-to-speech",
    json={
        "inputs": [text],
        "target_language_code": lang,     # "hi-IN", "mr-IN", or "en-IN"
        "speaker": voice,                 # "priya", "kavitha", or "rahul"
        "model": "bulbul:v3",
    },
)
# Sarvam returns base64-encoded WAV audio
audio_bytes = base64.b64decode(response.json()["audios"][0])
return StreamingResponse(BytesIO(audio_bytes), media_type="audio/wav")
```

**Key points:**
- Text max: **500 characters** (truncated at line 1005)
- Model: **Bulbul v3** (Sarvam's TTS model)
- Response: base64 → decoded to WAV bytes → streamed back

---

## Where These Are Used

| Used By | STT | TTS |
|---------|-----|-----|
| **Website** | User records voice → transcribed → used as claim text | User clicks "listen" → explanation read aloud |
| **Telegram Bot** | User sends voice message → transcribed → fact-checked | Bot sends back voice reply in user's language |

### Telegram Bot Voice Flow (complete):

```
User sends voice 🎙️
  ↓
Download OGG from Telegram → Sarvam STT → "5G causes cancer"
  ↓
run_crew("5G causes cancer") → verdict + explanation
  ↓
Send text reply with verdict
  ↓
Sarvam TTS (explanation in user's language) → send voice reply 🔊
```

---

## Summary

| What | STT | TTS |
|------|-----|-----|
| **Direction** | Audio → Text | Text → Audio |
| **API** | Sarvam `/speech-to-text` | Sarvam `/text-to-speech` |
| **Languages** | Auto-detect (HI/MR/EN) | Choose: hi-IN, mr-IN, en-IN |
| **Our Endpoint** | `POST /api/agents/stt` | `POST /api/agents/tts` |
| **Limit** | File size (30s timeout) | 500 characters max |
| **Key Required** | `SARVAM_API_KEY` | `SARVAM_API_KEY` |
