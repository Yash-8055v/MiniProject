import os
import logging
import asyncio
import urllib.parse
from datetime import datetime, timezone, timedelta
from functools import partial

import base64
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
from starlette.responses import StreamingResponse

from apscheduler.schedulers.background import BackgroundScheduler

from crew.crew import run_crew
from database.db import (
    get_collection,
    get_trending_claims,
    get_cached_heatmap,
    set_cached_heatmap,
    make_claim_hash,
    get_cached_analysis,
    set_cached_analysis,
    get_last_refresh_time,
    save_regional_query,
)
from trending.pipeline import run_refresh_pipeline
from server.heatmap import get_google_trends_heatmap, get_combined_heatmap
from server.media_verification import router as media_verification_router
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# APScheduler — 24-hour refresh job
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler()


def scheduled_refresh():
    """Wrapper so APScheduler can log the pipeline run."""
    logger.info("⏰ APScheduler: triggering 24-hour trending refresh...")
    try:
        summary = run_refresh_pipeline()
        logger.info(f"⏰ Scheduled refresh done: {summary}")
    except Exception as e:
        logger.error(f"⏰ Scheduled refresh failed: {e}")


# ---------------------------------------------------------------------------
# App lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting TruthCrew API...")

    # Ensure MongoDB indexes are created on startup
    try:
        get_collection()
        logger.info("✅ MongoDB connected and indexes verified")
    except Exception as e:
        logger.error(f"⚠️  MongoDB connection failed: {e} — trending features disabled")

    # Start the 6-hour background scheduler (reduced from 24h; catches up faster after spin-down)
    scheduler.add_job(
        scheduled_refresh,
        trigger="interval",
        hours=6,
        id="trending_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("✅ APScheduler started — trending refresh every 6 hours")

    # ── Startup stale-data check ─────────────────────────────────────────────
    # On every cold-start, check if the pipeline ran recently.
    # Free servers (Render) restart often; APScheduler resets, so this ensures
    # we always have fresh data even after a long spin-down period.
    def _startup_refresh_if_stale():
        try:
            last = get_last_refresh_time()
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
                
            stale_threshold = timedelta(hours=6)
            is_stale = (last is None) or (
                datetime.now(timezone.utc) - last > stale_threshold
            )
            if is_stale:
                age_str = "never" if last is None else f"{int((datetime.now(timezone.utc) - last).total_seconds() / 3600)}h ago"
                logger.info(f"🔄 Startup: data is stale (last refresh: {age_str}), triggering immediate refresh...")
                run_refresh_pipeline()
            else:
                age_min = int((datetime.now(timezone.utc) - last).total_seconds() / 60)
                logger.info(f"✅ Startup: trending data is fresh (last refresh {age_min} minutes ago), skipping.")
        except Exception as e:
            logger.error(f"⚠️  Startup stale-check failed: {e}")

    import threading
    threading.Thread(target=_startup_refresh_if_stale, daemon=True, name="startup-refresh").start()
    logger.info("✅ Startup stale-data check launched in background thread")

    # ---------------------------------------------------------------------------
    # Start Telegram Bot (polling) — only if token is configured
    # ---------------------------------------------------------------------------
    _bot_app = None
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            from telegram_bot.bot import build_application, BOT_COMMANDS, BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION
            _bot_app = build_application()
            await _bot_app.initialize()
            # post_init only fires via run_polling() — call Telegram API manually here
            await _bot_app.bot.set_my_commands(BOT_COMMANDS)
            await _bot_app.bot.set_my_description(BOT_DESCRIPTION)
            await _bot_app.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
            await _bot_app.start()
            await _bot_app.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Telegram bot started (commands + description registered)")
        except Exception as e:
            logger.warning(f"⚠️  Telegram bot failed to start: {e}")
            _bot_app = None
    else:
        logger.info("ℹ️  TELEGRAM_BOT_TOKEN not set — bot disabled")

    yield

    # Shutdown Telegram Bot
    if _bot_app is not None:
        try:
            await _bot_app.updater.stop()
            await _bot_app.stop()
            await _bot_app.shutdown()
            logger.info("🛑 Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")

    # Shutdown APScheduler
    scheduler.shutdown(wait=False)
    logger.info("🛑 APScheduler stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Fake News Verification API", lifespan=lifespan)

# Read allowed origins from env; defaults to "*"
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",")]

_PRODUCTION_ORIGIN = "https://truthcrew.vercel.app"
if "*" not in _cors_origins and _PRODUCTION_ORIGIN not in _cors_origins:
    _cors_origins.append(_PRODUCTION_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register media verification routes (/api/detect-image, etc.)
app.include_router(media_verification_router)


# ---------------------------------------------------------------------------
# Existing endpoint — claim verification
# ---------------------------------------------------------------------------
@app.post("/verify")
async def verify_news(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    """
    Accepts:
    - text (optional)
    - image (optional)

    Returns:
    - Verification result in English, Hindi, and Marathi
    """
    if text:
        text = text.strip()

    if not text and not image:
        raise HTTPException(
            status_code=400,
            detail="Either non-empty text or image must be provided",
        )

    image_bytes = None
    if image:
        image_bytes = await image.read()

    crew_input = {
        "text": text,
        "image_provided": bool(image_bytes),
    }

    try:
        result = run_crew(crew_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "languages": ["en", "hi", "mr"],
        "data": result,
    }


# ---------------------------------------------------------------------------
# New: Bot-friendly claim analysis endpoint with caching
# ---------------------------------------------------------------------------
class AnalyzeClaimRequest(BaseModel):
    query: str


@app.post("/api/analyze-claim")
async def analyze_claim(request: Request, body: AnalyzeClaimRequest):
    """
    Bot-friendly claim analysis endpoint.
    Accepts { "query": "..." } and returns a structured result.
    Results are cached in MongoDB for 24 hours to minimise Groq API usage.
    """
    import httpx

    claim = body.query.strip()
    if not claim:
        raise HTTPException(status_code=400, detail="query must not be empty")

    website_url = os.getenv("WEBSITE_URL", "https://truthcrew.vercel.app").rstrip("/")
    encoded_claim = urllib.parse.quote(claim)
    full_url = f"{website_url}/analyze?q={encoded_claim}"

    # ── Cache check ──
    claim_hash = make_claim_hash(claim)
    cached = get_cached_analysis(claim_hash)
    if cached is not None:
        logger.info(f"🔥 Analysis cache HIT for: {claim[:60]}")
        cached["url"] = full_url  # always refresh URL in case WEBSITE_URL changed
        # Still record the querying user's location even on cache hit
        _track_query_location(request, claim_hash)
        return {"status": "success", "cached": True, "data": cached}

    # ── IP geolocation — track which state the user is querying from ──
    # Run before crew pipeline so the regional signal is ready when we build the heatmap
    await _geolocate_and_save(request, claim_hash)

    # ── Run crew pipeline (blocking → executor) ──
    logger.info(f"🔍 Analysis cache MISS — running crew for: {claim[:60]}")
    try:
        loop = asyncio.get_event_loop()
        crew_result = await loop.run_in_executor(
            None,
            partial(run_crew, {"text": claim, "image_provided": False}),
        )
    except Exception as e:
        logger.error(f"Crew pipeline failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis pipeline failed")

    # ── Build combined heatmap (GT + news coverage + user geo) ──
    sources = crew_result.get("sources", [])
    try:
        loop = asyncio.get_event_loop()
        heatmap = await loop.run_in_executor(
            None, partial(get_combined_heatmap, claim, claim_hash, sources)
        )
        # Cache combined heatmap so /api/heatmap returns enriched data
        query_hash = hashlib.md5(claim.lower().encode("utf-8")).hexdigest()
        set_cached_heatmap(query_hash, heatmap)
        sorted_regions = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)
        top_regions = [r for r, _ in sorted_regions[:5] if _ > 0]
    except Exception:
        top_regions = []

    data = {
        "claim": claim,
        "verdict": crew_result.get("verdict", "Unknown"),
        "confidence": crew_result.get("confidence", 0),
        "credibility_layers": crew_result.get("credibility_layers", {}),
        "explanation": crew_result.get("english", ""),
        "explanation_hi": crew_result.get("hindi", ""),
        "explanation_mr": crew_result.get("marathi", ""),
        "sources": sources,
        "top_regions": top_regions,
        "url": full_url,
    }

    # ── Save to cache ──
    set_cached_analysis(claim_hash, data)

    return {"status": "success", "cached": False, "data": data}


# ---------------------------------------------------------------------------
# Helpers — IP geolocation (non-fatal)
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, honouring X-Forwarded-For (Render/Vercel proxy)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def _track_query_location(request: Request, claim_hash: str) -> None:
    """Fire-and-forget synchronous IP tracking (used for cache-hit path)."""
    import threading
    ip = _get_client_ip(request)
    if ip and ip not in ("127.0.0.1", "::1", ""):
        threading.Thread(
            target=_sync_geolocate_and_save, args=(ip, claim_hash), daemon=True
        ).start()


def _sync_geolocate_and_save(ip: str, claim_hash: str) -> None:
    """Synchronous version of IP → state → MongoDB (runs in background thread)."""
    import httpx as _httpx
    try:
        resp = _httpx.get(f"https://ipinfo.io/{ip}/json", timeout=5)
        state = resp.json().get("region", "").strip().lower()
        if state:
            save_regional_query(claim_hash, state)
            logger.info(f"📍 Recorded query from state: {state}")
    except Exception:
        pass


async def _geolocate_and_save(request: Request, claim_hash: str) -> None:
    """Async IP → state lookup, saves to regional_queries collection."""
    import httpx
    ip = _get_client_ip(request)
    if not ip or ip in ("127.0.0.1", "::1", ""):
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://ipinfo.io/{ip}/json")
            state = resp.json().get("region", "").strip().lower()
            if state:
                save_regional_query(claim_hash, state)
                logger.info(f"📍 Recorded query from state: {state}")
    except Exception:
        pass  # Non-fatal — never block the analysis pipeline


# ---------------------------------------------------------------------------
# Trending claims endpoints
# ---------------------------------------------------------------------------
@app.get("/api/trending-claims")
async def trending_claims(
    region: Optional[str] = Query(
        default=None,
        description="Filter by region: global, india, maharashtra, delhi, kerala",
    )
):
    """
    Return top 10 trending misinformation claims sorted by misleading_score.
    Optionally filter by ?region=india etc.
    """
    try:
        claims = get_trending_claims(region=region, limit=10)
        return {
            "status": "success",
            "region_filter": region or "all",
            "count": len(claims),
            "data": claims,
        }
    except Exception as e:
        logger.error(f"Error fetching trending claims: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Heatmap endpoint — Google Trends
# ---------------------------------------------------------------------------
@app.get("/api/heatmap")
async def heatmap_data(
    query: str = Query(..., description="The claim/query to fetch spread data for"),
):
    """
    Returns region-wise Google Trends interest scores (0-100) for India.
    Results are cached in MongoDB for 12 hours.
    """
    query = query.strip()
    if not query:
        return {"status": "success", "data": {}}

    # Check MongoDB cache first
    query_hash = hashlib.md5(query.lower().encode("utf-8")).hexdigest()
    cached = get_cached_heatmap(query_hash)
    if cached is not None:
        logger.info(f"🔥 Heatmap cache HIT for: {query}")
        return {"status": "success", "data": cached}

    # Cache miss — build combined heatmap (GT + any stored user-query signal)
    logger.info(f"🔍 Heatmap cache MISS — building combined heatmap: {query}")
    data = get_combined_heatmap(query, claim_hash=query_hash)

    # Store in cache
    set_cached_heatmap(query_hash, data)

    return {"status": "success", "data": data}


@app.post("/api/trending/refresh")
async def manual_refresh():
    """
    Manually trigger the trending misinformation refresh pipeline.
    Useful for testing and first-time setup.
    """
    try:
        logger.info("🔄 Manual refresh triggered via API")
        summary = run_refresh_pipeline()
        return {"status": "success", "pipeline_summary": summary}
    except Exception as e:
        logger.error(f"Manual refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Heatmap Insight endpoint — AI-generated insight via Groq
# ---------------------------------------------------------------------------
class HeatmapInsightRequest(BaseModel):
    query: str
    heatmap_data: dict


@app.post("/api/heatmap-insight")
async def heatmap_insight(body: HeatmapInsightRequest):
    """
    Generate a brief AI insight about the geographic spread pattern
    of a claim using Groq LLM.
    """
    if not body.query.strip() or not body.heatmap_data:
        return {"insight": ""}

    try:
        import requests as req

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {"insight": ""}

        # Build a concise summary of the heatmap data
        sorted_regions = sorted(
            body.heatmap_data.items(), key=lambda x: x[1], reverse=True
        )
        top_regions = sorted_regions[:5]
        data_summary = ", ".join(
            [f"{region}: {score}" for region, score in top_regions]
        )

        prompt = (
            f"Given this heatmap data showing regional search interest (0-100 scale) "
            f"for the claim '{body.query.strip()[:100]}' across Indian states:\n"
            f"{data_summary}\n\n"
            f"Provide a brief 1-2 sentence insight about the geographic spread pattern. "
            f"Focus on why certain regions may show higher interest. "
            f"Be specific and analytical. Do not use bullet points."
        )

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 150,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()
        return {"insight": content}

    except Exception as e:
        logger.error(f"Heatmap insight generation failed: {e}")
        return {"insight": ""}



# ---------------------------------------------------------------------------
# Sarvam AI — Speech-to-Text (STT)
# ---------------------------------------------------------------------------
@app.post("/api/agents/stt")
async def sarvam_stt(audio: UploadFile = File(...)):
    """
    Accepts audio upload (.webm/.wav/.mp3/.ogg) and returns transcript via Sarvam AI.
    Sarvam auto-detects Hindi, Marathi, and English.
    """
    import httpx

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    # Determine file extension for Sarvam
    filename = audio.filename or "audio.webm"
    content_type = audio.content_type or "audio/webm"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": api_key},
                files={"file": (filename, content, content_type)},
                data={"language_code": "unknown"},  # auto-detect
            )
        response.raise_for_status()
        data = response.json()
        transcript = data.get("transcript", "")
        if not transcript:
            raise HTTPException(status_code=422, detail="No transcript returned")
        return {"transcript": transcript}
    except httpx.HTTPStatusError as e:
        logger.error(f"Sarvam STT error: {e.response.text}")
        raise HTTPException(status_code=502, detail="Speech recognition failed")
    except Exception as e:
        logger.error(f"Sarvam STT exception: {e}")
        raise HTTPException(status_code=502, detail="Speech recognition failed")


# ---------------------------------------------------------------------------
# Sarvam AI — Text-to-Speech (TTS)
# ---------------------------------------------------------------------------
class TTSRequest(BaseModel):
    text: str
    language: str = "en-IN"  # "hi-IN" | "mr-IN" | "en-IN"


_SARVAM_VOICES = {
    "hi-IN": "priya",
    "mr-IN": "kavitha",
    "en-IN": "rahul",
}


@app.post("/api/agents/tts")
async def sarvam_tts(body: TTSRequest):
    """
    Converts text to speech via Sarvam AI and returns audio/wav.
    Sarvam TTS returns base64-encoded WAV inside JSON — decoded here.
    """
    import httpx

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    # Truncate to Sarvam's limit (500 chars per request)
    text = text[:500]
    lang = body.language if body.language in _SARVAM_VOICES else "en-IN"
    voice = _SARVAM_VOICES[lang]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": [text],
                    "target_language_code": lang,
                    "speaker": voice,
                    "model": "bulbul:v3",
                    "enable_preprocessing": True,
                },
            )
        response.raise_for_status()
        data = response.json()
        # Sarvam returns { "audios": ["<base64_wav>"] }
        audios = data.get("audios", [])
        if not audios:
            raise HTTPException(status_code=502, detail="No audio returned from TTS")
        audio_bytes = base64.b64decode(audios[0])
        return StreamingResponse(BytesIO(audio_bytes), media_type="audio/wav")
    except httpx.HTTPStatusError as e:
        logger.error(f"Sarvam TTS error: {e.response.text}")
        raise HTTPException(status_code=502, detail="Text-to-speech failed")
    except Exception as e:
        logger.error(f"Sarvam TTS exception: {e}")
        raise HTTPException(status_code=502, detail="Text-to-speech failed")


# ---------------------------------------------------------------------------
# Health check endpoint - pinged by GitHub Actions cron job every 5 minutes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Lightweight liveness probe. Pinged by the GitHub Actions cron job
    (.github/workflows/keep_alive.yml) every 5 minutes to prevent the free
    Render server from spinning down.
    Returns the timestamp of the last successful trending refresh as a bonus.
    """
    last = get_last_refresh_time()
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    last_str = last.isoformat() if last else "never"
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_trending_refresh": last_str,
    }
