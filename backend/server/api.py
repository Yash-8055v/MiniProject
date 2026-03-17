import os
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from crew.crew import run_crew
from database.db import get_collection, get_trending_claims
from trending.pipeline import run_refresh_pipeline

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

    yield

    # Shutdown
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
