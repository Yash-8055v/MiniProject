import os
import logging
import asyncio
import urllib.parse
from functools import partial

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional

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
)
from trending.pipeline import run_refresh_pipeline
from server.heatmap import get_google_trends_heatmap
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

    # Start the 24-hour background scheduler
    scheduler.add_job(
        scheduled_refresh,
        trigger="interval",
        hours=24,
        id="trending_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("✅ APScheduler started — trending refresh every 24 hours")

    # ---------------------------------------------------------------------------
    # Start Telegram Bot (polling) — only if token is configured
    # ---------------------------------------------------------------------------
    _bot_app = None
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            from telegram_bot.bot import build_application, BOT_COMMANDS
            _bot_app = build_application()
            await _bot_app.initialize()
            # post_init only fires via run_polling() — call it manually here
            await _bot_app.bot.set_my_commands(BOT_COMMANDS)
            await _bot_app.start()
            await _bot_app.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Telegram bot started in polling mode (menu commands registered)")
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
async def analyze_claim(body: AnalyzeClaimRequest):
    """
    Bot-friendly claim analysis endpoint.
    Accepts { "query": "..." } and returns a structured result.
    Results are cached in MongoDB for 24 hours to minimise Groq API usage.
    """
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
        return {"status": "success", "cached": True, "data": cached}

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

    # ── Fetch top regions from heatmap (cached separately) ──
    try:
        loop = asyncio.get_event_loop()
        heatmap = await loop.run_in_executor(
            None, partial(get_google_trends_heatmap, claim)
        )
        sorted_regions = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)
        top_regions = [r for r, _ in sorted_regions[:5] if _ > 0]
    except Exception:
        top_regions = []

    data = {
        "claim": claim,
        "verdict": crew_result.get("verdict", "Unknown"),
        "confidence": crew_result.get("confidence", 0),
        "explanation": crew_result.get("english", ""),
        "explanation_hi": crew_result.get("hindi", ""),
        "explanation_mr": crew_result.get("marathi", ""),
        "top_regions": top_regions,
        "url": full_url,
    }

    # ── Save to cache ──
    set_cached_analysis(claim_hash, data)

    return {"status": "success", "cached": False, "data": data}


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

    # Cache miss — fetch from Google Trends
    logger.info(f"🔍 Heatmap cache MISS — fetching from Google Trends: {query}")
    data = get_google_trends_heatmap(query)

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

