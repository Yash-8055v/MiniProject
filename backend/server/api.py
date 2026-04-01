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
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Optional, Any
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
# Pydantic Response Models — for auto-generated API documentation
# ---------------------------------------------------------------------------

class SourceItem(BaseModel):
    """A single news source used during verification."""
    title: str = Field(..., description="Headline of the source article", example="India GDP growth slows to 6.3% — Reuters")
    url: str = Field(..., description="Full URL to the source article", example="https://reuters.com/article/india-gdp-2025")
    source: str = Field(..., description="Domain or publisher name", example="reuters.com")
    trusted: bool = Field(..., description="Whether this source is from a pre-approved trusted domain list", example=True)


class CredibilityLayer(BaseModel):
    """One layer of the multi-layer credibility scoring system."""
    score: int = Field(..., ge=0, le=100, description="Score for this layer (0-100)", example=75)
    weight: int = Field(..., description="Weight of this layer in the final score (percentage)", example=35)


class CredibilityLayers(BaseModel):
    """Breakdown of the 5-layer credibility scoring system."""
    source_tier: CredibilityLayer = Field(..., description="Layer 1: Average quality tier of source domains (Gov=100, Int'l=90, National=75, Regional=55, Unknown=20)")
    source_count: CredibilityLayer = Field(..., description="Layer 2: Number of sources found (normalized: 8 sources = 100)")
    evidence_alignment: CredibilityLayer = Field(..., description="Layer 3: Percentage of sources from known trusted domains")
    claim_verifiability: CredibilityLayer = Field(..., description="Layer 4: Heuristic score based on claim specificity (numbers, proper nouns, dates)")
    cross_agreement: CredibilityLayer = Field(..., description="Layer 5: Number of independent trusted sources agreeing (0=0, 1=40, 2=70, 3+=100)")


class VerifyResponseData(BaseModel):
    """Structured result from the CrewAI verification pipeline."""
    verdict: str = Field(..., description="Verification verdict", example="Likely False")
    confidence: int = Field(..., ge=0, le=100, description="Credibility confidence score (0-100) calculated from 5-layer system", example=72)
    english: str = Field("", description="Explanation in English")
    hindi: str = Field("", description="Explanation in Hindi (Devanagari)")
    marathi: str = Field("", description="Explanation in Marathi (Devanagari)")
    sources: list[SourceItem] = Field(default_factory=list, description="List of news sources used for verification")
    credibility_layers: CredibilityLayers | None = Field(None, description="Detailed 5-layer credibility score breakdown")


class VerifyResponse(BaseModel):
    """Response from the /verify endpoint."""
    status: str = Field("success", description="Request status", example="success")
    languages: list[str] = Field(["en", "hi", "mr"], description="Languages available in the response")
    data: VerifyResponseData


class AnalyzeClaimData(BaseModel):
    """Structured result from the /api/analyze-claim endpoint."""
    claim: str = Field(..., description="The original claim text submitted")
    verdict: str = Field(..., description="One of: Likely True, Likely False, Likely Misleading", example="Likely False")
    confidence: int = Field(..., ge=0, le=100, description="Credibility confidence score (0-100)", example=68)
    credibility_layers: CredibilityLayers | None = Field(None, description="Detailed 5-layer credibility breakdown")
    explanation: str = Field("", description="Explanation in English")
    explanation_hi: str = Field("", description="Explanation in Hindi")
    explanation_mr: str = Field("", description="Explanation in Marathi")
    sources: list[SourceItem] = Field(default_factory=list, description="Sources used for verification")
    top_regions: list[str] = Field(default_factory=list, description="Top 5 Indian states where this claim is trending")
    url: str = Field("", description="Link to full analysis on the TruthCrew website")


class AnalyzeClaimResponse(BaseModel):
    """Response from /api/analyze-claim."""
    status: str = Field("success", example="success")
    cached: bool = Field(..., description="Whether the result was served from MongoDB cache (24h TTL)", example=False)
    data: AnalyzeClaimData


class TrendingClaimItem(BaseModel):
    """A single trending misinformation claim stored in MongoDB."""
    model_config = {"populate_by_name": True}
    id: str = Field("", alias="_id", description="MongoDB document ID")
    claim_hash: str = Field(..., description="MD5 hash of normalized claim text for deduplication")
    claim: str = Field(..., description="The misleading claim text", example="5G towers cause COVID-19")
    explanation: str = Field("", description="Why this claim is misleading")
    category: str = Field("General", description="Category: Health, Politics, Science, Technology, Social Media, etc.", example="Health")
    misleading_score: int = Field(..., ge=0, le=100, description="How misleading the claim is (50-100)", example=85)
    source_name: str = Field("Unknown", description="Fact-check source that debunked this claim", example="AltNews")
    source_url: str = Field("", description="URL of the fact-check article")
    region: str = Field("global", description="Region: global, india, maharashtra, etc.", example="india")
    published_at: str = Field("", description="ISO timestamp when the fact-check was published")
    created_at: str = Field("", description="ISO timestamp when stored in MongoDB")
    trending_score: int = Field(1, description="Accumulated trending frequency score")


class TrendingClaimsResponse(BaseModel):
    """Response from /api/trending-claims."""
    status: str = Field("success", example="success")
    region_filter: str = Field("all", description="Applied region filter", example="india")
    count: int = Field(..., description="Number of claims returned", example=10)
    data: list[TrendingClaimItem]


class HeatmapResponse(BaseModel):
    """Response from /api/heatmap — regional spread scores."""
    status: str = Field("success", example="success")
    data: dict[str, int] = Field(
        ...,
        description="Map of Indian state names (lowercase) to interest scores (0-100). Example: {'maharashtra': 85, 'delhi': 72}",
        example={"maharashtra": 85, "delhi": 72, "karnataka": 45, "tamil nadu": 38},
    )


class HeatmapInsightResponse(BaseModel):
    """Response from /api/heatmap-insight — AI-generated geographic insight."""
    insight: str = Field(
        "",
        description="1-2 sentence AI-generated insight about the geographic spread pattern. Empty string if generation fails.",
        example="The claim shows highest interest in Maharashtra and Delhi, likely due to its political nature and urban media consumption patterns.",
    )


class STTResponse(BaseModel):
    """Response from /api/agents/stt — Speech-to-Text transcription."""
    transcript: str = Field(..., description="Transcribed text from the uploaded audio", example="क्या यह सच है कि 5G टावर से कोरोना फैलता है")


class TTSRequest(BaseModel):
    """Request body for /api/agents/tts — Text-to-Speech conversion."""
    text: str = Field(..., description="Text to convert to speech (max 500 characters)", example="This claim is likely false.")
    language: str = Field(
        "en-IN",
        description="Target language for speech: 'hi-IN' (Hindi), 'mr-IN' (Marathi), or 'en-IN' (English)",
        example="hi-IN",
    )


class RefreshPipelineResponse(BaseModel):
    """Response from /api/trending/refresh — manual pipeline trigger."""
    status: str = Field("success", example="success")
    pipeline_summary: dict = Field(
        ...,
        description="Pipeline execution summary with counts",
        example={
            "status": "success",
            "articles_fetched": 30,
            "articles_filtered": 25,
            "groq_calls_made": 10,
            "claims_stored": 7,
            "claims_skipped": 3,
            "errors": 0,
            "duration_seconds": 45.2,
        },
    )


class HealthResponse(BaseModel):
    """Response from /health — server liveness probe."""
    status: str = Field("ok", example="ok")
    timestamp: str = Field(..., description="Current UTC timestamp", example="2026-04-01T00:00:00+00:00")
    last_trending_refresh: str = Field(..., description="ISO timestamp of last trending pipeline run, or 'never'", example="2026-03-31T23:00:00+00:00")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AnalyzeClaimRequest(BaseModel):
    """Request body for /api/analyze-claim."""
    query: str = Field(
        ...,
        description="The news claim or headline to fact-check. Supports English, Hindi, Marathi, and Hinglish.",
        min_length=1,
        example="India's GDP grew 15% in 2025",
    )


class HeatmapInsightRequest(BaseModel):
    """Request body for /api/heatmap-insight."""
    query: str = Field(..., description="The claim/query text", example="5G towers cause cancer")
    heatmap_data: dict = Field(
        ...,
        description="Region-to-score mapping from /api/heatmap",
        example={"maharashtra": 85, "delhi": 72, "karnataka": 45},
    )


# ---------------------------------------------------------------------------
# API Tag metadata for Swagger grouping
# ---------------------------------------------------------------------------

tags_metadata = [
    {
        "name": "🔍 Claim Verification",
        "description": "Core fact-checking endpoints. Submit a claim (text/image) and receive a multi-language verdict with confidence scores, credibility layers, and source attributions.",
    },
    {
        "name": "🔥 Trending Misinformation",
        "description": "Endpoints for discovering and managing trending misinformation claims. Data is automatically refreshed every 6 hours from fact-check RSS feeds (AltNews, BoomLive, Snopes, etc.) and analyzed by Groq LLM.",
    },
    {
        "name": "🗺️ Geographic Heatmap",
        "description": "Regional spread analysis combining Google Trends data, news source coverage mapping, and IP-geolocated user queries to show which Indian states are most affected by a claim.",
    },
    {
        "name": "🎙️ Voice & Speech (Sarvam AI)",
        "description": "Speech-to-Text and Text-to-Speech endpoints powered by Sarvam AI. Supports Hindi, Marathi, and English for inclusive accessibility.",
    },
    {
        "name": "🖼️ Media Verification",
        "description": "AI-powered image, video, and audio deepfake detection using Groq Vision (LLaMA multimodal). Analyzes visual artifacts, metadata, and filename signals.",
    },
    {
        "name": "⚙️ System",
        "description": "Health checks, monitoring, and administrative endpoints.",
    },
]


# ---------------------------------------------------------------------------
# FastAPI app with comprehensive OpenAPI documentation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TruthCrew — AI-Powered Misinformation Detection API",
    description="""
## 🛡️ TruthCrew Backend API

**TruthCrew** is an AI-powered misinformation detection platform that verifies news claims 
using a multi-agent CrewAI pipeline, web search evidence from trusted sources, and a 
5-layer credibility scoring system.

### 🏗️ Architecture Overview
- **CrewAI Pipeline**: 3 specialized AI agents (Interpreter → Analyzer → Response Generator) powered by Groq LLaMA 3.3 70B
- **Web Search**: Priority-based search via SerpAPI (Government → International → National → Regional → Open Web)
- **Credibility Scoring**: Transparent 5-layer system (Source Tier 35% + Source Count 20% + Evidence Alignment 25% + Claim Verifiability 10% + Cross Agreement 10%)
- **Database**: MongoDB Atlas with TTL-indexed collections for auto-expiring caches
- **Media Detection**: Groq Vision (LLaMA 4 Scout) for AI-generated image/video detection
- **Trending Pipeline**: RSS feeds from fact-check sites → Groq analysis → MongoDB storage (auto-refreshes every 6 hours)
- **Multilingual**: All results in English, Hindi (Devanagari), and Marathi (Devanagari)
- **Telegram Bot**: Full-featured bot with voice support via Sarvam AI STT/TTS

### 🔑 Required API Keys
| Key | Service | Purpose |
|-----|---------|---------|
| `GROQ_API_KEY` | Groq Cloud | LLM inference (LLaMA 3.3 70B + LLaMA 4 Scout Vision) |
| `SEARCH_API_KEY` | SerpAPI | Google Search for evidence gathering |
| `MONGO_URI` | MongoDB Atlas | Database for caching, trending claims, heatmaps |
| `SARVAM_API_KEY` | Sarvam AI | Hindi/Marathi/English Speech-to-Text and Text-to-Speech |
| `TELEGRAM_BOT_TOKEN` | Telegram | Bot integration (optional) |

### 📊 Caching Strategy
| Cache | TTL | Collection |
|-------|-----|------------|
| Claim Analysis | 24 hours | `analysis_cache` |
| Heatmap Data | 12 hours | `heatmap_cache` |
| Trending Claims | 7 days | `misinformation_claims` |
| Regional Queries | 30 days | `regional_queries` |
""",
    version="1.0.0",
    contact={
        "name": "TruthCrew Team",
        "url": "https://truthcrew.vercel.app",
    },
    license_info={
        "name": "MIT License",
    },
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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
# Claim Verification — /verify
# ---------------------------------------------------------------------------
@app.post(
    "/verify",
    response_model=VerifyResponse,
    tags=["🔍 Claim Verification"],
    summary="Verify a news claim (form-data with optional image)",
    response_description="Verification result with verdict, confidence score, multilingual explanations, and sources",
)
async def verify_news(
    text: Optional[str] = Form(
        None,
        description="The news claim or headline to verify. Supports English, Hindi, Marathi, and Hinglish.",
    ),
    image: Optional[UploadFile] = File(
        None,
        description="Optional image file to accompany the claim (JPEG, PNG, WebP)",
    ),
):
    """
    ## Verify a News Claim
    
    Runs the full **CrewAI multi-agent pipeline** to fact-check a claim:
    
    1. **Translation**: Auto-translates Hindi/Marathi/Hinglish claims to English
    2. **Web Search**: Searches trusted sources via SerpAPI (government → national → open web)
    3. **Agent 1 — Interpreter**: Restates the claim clearly and summarizes evidence
    4. **Agent 2 — Analyzer**: Evaluates evidence and assigns a verdict + confidence
    5. **Agent 3 — Response Generator**: Creates multilingual explanations (EN/HI/MR)
    6. **Credibility Scoring**: Calculates 5-layer transparency score (0-100)
    
    ### Input
    - At least one of `text` or `image` must be provided
    - Text can be in English, Hindi, Marathi, or Hinglish
    
    ### Response Fields
    - **verdict**: `Likely True` | `Likely False` | `Likely Misleading`
    - **confidence**: 0-100 score from the 5-layer credibility system
    - **english/hindi/marathi**: Explanations in three languages
    - **sources**: List of news sources with trust indicators
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
# Claim Analysis — /api/analyze-claim (with caching + heatmap)
# ---------------------------------------------------------------------------
@app.post(
    "/api/analyze-claim",
    response_model=AnalyzeClaimResponse,
    tags=["🔍 Claim Verification"],
    summary="Analyze a claim with caching, heatmap, and geolocation",
    response_description="Full analysis result with verdict, credibility layers, sources, top regions, and website URL",
)
async def analyze_claim(request: Request, body: AnalyzeClaimRequest):
    """
    ## Analyze a Claim (Bot-Friendly, Cached)
    
    Primary endpoint used by the frontend and Telegram bot. Includes:
    
    - **MongoDB Caching**: Results cached for 24 hours (saves Groq API calls)
    - **IP Geolocation**: Tracks which Indian state the user is querying from (via ipinfo.io)
    - **Combined Heatmap**: Builds a 3-signal regional spread map after analysis
    - **Website URL**: Returns a direct link to the full analysis on truthcrew.vercel.app
    
    ### Pipeline Flow
    ```
    Request → Cache Check → [HIT] Return cached result
                          → [MISS] IP Geolocation → CrewAI Pipeline → Build Heatmap → Cache & Return
    ```
    
    ### Heatmap Signals
    1. **Google Trends** (50% weight): Real-time search interest by Indian state
    2. **News Coverage** (30% weight): Regional news source domain mapping
    3. **User Queries** (20% weight): IP-geolocated user query origins
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
# Trending Claims — /api/trending-claims
# ---------------------------------------------------------------------------
@app.get(
    "/api/trending-claims",
    response_model=TrendingClaimsResponse,
    tags=["🔥 Trending Misinformation"],
    summary="Get top trending misinformation claims",
    response_description="List of top 10 trending claims sorted by misleading score",
)
async def trending_claims(
    region: Optional[str] = Query(
        default=None,
        description="Filter by region: global, india, maharashtra, delhi, kerala. Leave empty for all regions.",
    )
):
    """
    ## Get Trending Misinformation Claims
    
    Returns the top 10 trending misinformation claims from fact-check RSS feeds,
    sorted by `misleading_score` (highest first).
    
    ### Data Source Pipeline
    ```
    RSS Feeds (AltNews, BoomLive, Snopes, etc.)
      → Keyword Filter (skip meta pages)
      → Groq LLM Analysis (extract false claim + score 50-100)
      → MongoDB Storage (7-day TTL)
    ```
    
    ### Region Filters
    - `global` — International claims
    - `india` — India-specific claims
    - `maharashtra`, `delhi`, `kerala` — State-specific claims
    - Omit parameter — All regions
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
# Heatmap — /api/heatmap
# ---------------------------------------------------------------------------
@app.get(
    "/api/heatmap",
    response_model=HeatmapResponse,
    tags=["🗺️ Geographic Heatmap"],
    summary="Get regional spread heatmap for a claim",
    response_description="Dictionary mapping Indian state names to interest scores (0-100)",
)
async def heatmap_data(
    query: str = Query(
        ...,
        description="The claim or search query to analyze geographic spread for",
    ),
):
    """
    ## Get Regional Spread Heatmap
    
    Returns a state-wise interest score (0-100) for India, combining up to 3 signals:
    
    | Signal | Weight | Source |
    |--------|--------|--------|
    | Google Trends | 50% | Real-time search interest by region (past 7 days) |
    | News Coverage | 30% | Regional news domains found in search results |
    | User Queries | 20% | IP-geolocated user query origins from MongoDB |
    
    Results are **cached in MongoDB for 12 hours**. Falls back to deterministic 
    simulated data (based on query hash) if Google Trends API is unavailable.
    
    ### Response Format
    ```json
    { "status": "success", "data": { "maharashtra": 85, "delhi": 72, "karnataka": 45 } }
    ```
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


# ---------------------------------------------------------------------------
# Manual Trending Refresh — /api/trending/refresh
# ---------------------------------------------------------------------------
@app.post(
    "/api/trending/refresh",
    response_model=RefreshPipelineResponse,
    tags=["🔥 Trending Misinformation"],
    summary="Manually trigger the trending misinformation refresh pipeline",
    response_description="Pipeline execution summary with article counts and timing",
)
async def manual_refresh():
    """
    ## Manually Trigger Trending Refresh
    
    Runs the full trending misinformation pipeline on demand:
    
    1. **Fetch**: Pull articles from 8 fact-check RSS feeds (AltNews, BoomLive, Snopes, etc.)
    2. **Filter**: Skip meta-pages and empty descriptions
    3. **Analyze**: Send up to 10 articles to Groq LLM for misinformation scoring
    4. **Store**: Upsert claims with score ≥ 50 into MongoDB
    
    This pipeline normally runs automatically every 6 hours via APScheduler.
    Use this endpoint for testing or first-time setup.
    
    ⚠️ **Rate Limit**: Groq free tier has API limits. Pipeline includes 3-second delays between calls.
    """
    try:
        logger.info("🔄 Manual refresh triggered via API")
        summary = run_refresh_pipeline()
        return {"status": "success", "pipeline_summary": summary}
    except Exception as e:
        logger.error(f"Manual refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Heatmap Insight — /api/heatmap-insight
# ---------------------------------------------------------------------------
@app.post(
    "/api/heatmap-insight",
    response_model=HeatmapInsightResponse,
    tags=["🗺️ Geographic Heatmap"],
    summary="Generate an AI insight about geographic spread patterns",
    response_description="1-2 sentence AI-generated insight about the claim's geographic spread",
)
async def heatmap_insight(body: HeatmapInsightRequest):
    """
    ## Generate Heatmap Insight
    
    Uses **Groq LLaMA 3.3 70B** to generate a brief analytical insight about why 
    certain Indian states show higher interest in a claim.
    
    ### Input
    - `query`: The claim text
    - `heatmap_data`: The region→score dict from `/api/heatmap`
    
    ### Behaviour
    - Returns an empty string if `GROQ_API_KEY` is not set or generation fails
    - Uses top 5 regions for the prompt to keep it concise
    - Temperature: 0.5, Max tokens: 150
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
@app.post(
    "/api/agents/stt",
    response_model=STTResponse,
    tags=["🎙️ Voice & Speech (Sarvam AI)"],
    summary="Convert speech audio to text (Hindi/Marathi/English)",
    response_description="Transcribed text from the uploaded audio file",
)
async def sarvam_stt(
    audio: UploadFile = File(
        ...,
        description="Audio file to transcribe (.webm, .wav, .mp3, .ogg). Sarvam auto-detects Hindi, Marathi, and English.",
    ),
):
    """
    ## Speech-to-Text (Sarvam AI)
    
    Transcribes audio into text using **Sarvam AI's** speech recognition API.
    Sarvam auto-detects the language (Hindi, Marathi, English).
    
    ### Supported Formats
    - `.webm` (browser recording)
    - `.wav`, `.mp3`, `.ogg`
    
    ### Use Case
    Used by the Telegram bot to transcribe voice messages before fact-checking.
    
    ### Requires
    - `SARVAM_API_KEY` environment variable
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

_SARVAM_VOICES = {
    "hi-IN": "priya",
    "mr-IN": "kavitha",
    "en-IN": "rahul",
}


@app.post(
    "/api/agents/tts",
    tags=["🎙️ Voice & Speech (Sarvam AI)"],
    summary="Convert text to speech audio (Hindi/Marathi/English)",
    response_description="WAV audio stream of the synthesized speech",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "WAV audio file of the synthesized speech",
        },
        400: {"description": "Text is empty"},
        502: {"description": "Sarvam AI TTS service error"},
        503: {"description": "SARVAM_API_KEY not configured"},
    },
)
async def sarvam_tts(body: TTSRequest):
    """
    ## Text-to-Speech (Sarvam AI)
    
    Converts text to speech using **Sarvam AI's Bulbul v3** TTS model.
    Returns a WAV audio stream.
    
    ### Voices
    | Language | Code | Voice |
    |----------|------|-------|
    | Hindi | `hi-IN` | Priya |
    | Marathi | `mr-IN` | Kavitha |
    | English | `en-IN` | Rahul |
    
    ### Limits
    - Text is truncated to 500 characters (Sarvam API limit)
    
    ### Use Case
    Used by the Telegram bot to send voice responses back to users.
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
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["⚙️ System"],
    summary="Server health check (keep-alive probe)",
    response_description="Server status with last trending refresh timestamp",
)
async def health_check():
    """
    ## Health Check / Liveness Probe
    
    Lightweight endpoint pinged by the **GitHub Actions cron job** 
    (`.github/workflows/keep_alive.yml`) every 5 minutes to prevent the 
    free Render server from spinning down.
    
    ### Response
    - `status`: Always `"ok"` if server is running
    - `timestamp`: Current UTC time
    - `last_trending_refresh`: ISO timestamp of last successful trending pipeline run
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
