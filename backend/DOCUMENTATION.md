# TruthCrew — Complete Backend Documentation

> **AI-Powered Misinformation Detection Platform**  
> Built with FastAPI • CrewAI • Groq LLaMA • MongoDB • Sarvam AI • Telegram Bot  
> Last Updated: April 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack & Libraries](#3-technology-stack--libraries)
4. [Environment Configuration](#4-environment-configuration)
5. [Feature 1 — Claim Verification Pipeline](#5-feature-1--claim-verification-pipeline)
6. [Feature 2 — Credibility Scoring System](#6-feature-2--credibility-scoring-system)
7. [Feature 3 — Trending Misinformation Pipeline](#7-feature-3--trending-misinformation-pipeline)
8. [Feature 4 — Geographic Heatmap & Spread Analysis](#8-feature-4--geographic-heatmap--spread-analysis)
9. [Feature 5 — Media Verification (AI Deepfake Detection)](#9-feature-5--media-verification-ai-deepfake-detection)
10. [Feature 6 — Voice Interface (Speech-to-Text & Text-to-Speech)](#10-feature-6--voice-interface-speech-to-text--text-to-speech)
11. [Feature 7 — Telegram Bot Integration](#11-feature-7--telegram-bot-integration)
12. [Feature 8 — Caching & Database Layer](#12-feature-8--caching--database-layer)
13. [Feature 9 — Server Health & Keep-Alive System](#13-feature-9--server-health--keep-alive-system)
14. [API Reference](#14-api-reference)
15. [Directory Structure](#15-directory-structure)

---

## 1. Project Overview

**TruthCrew** is a misinformation detection platform that fact-checks news claims using artificial intelligence. Users can submit any news headline or claim in English, Hindi, or Marathi, and the system will:

- Search trusted news sources (government, national, international)
- Analyze the evidence using a 3-agent AI pipeline
- Generate a verdict (Likely True / Likely False / Likely Misleading)
- Calculate a transparent 5-layer credibility score (0-100)
- Provide explanations in 3 languages (English, Hindi, Marathi)
- Show a geographic heatmap of where the claim is trending
- Detect AI-generated images and videos

### Key Capabilities

| Capability | Technology |
|-----------|-----------|
| Fact-checking AI Pipeline | CrewAI + Groq LLaMA 3.3 70B |
| Web Search | SerpAPI (Google Search) |
| AI Image/Video Detection | Groq Vision (LLaMA 4 Scout 17B) |
| Multilingual Support | Sarvam AI (STT/TTS) + LLM Translation |
| Database & Caching | MongoDB Atlas |
| Trending Detection | RSS Feeds + Groq Analysis |
| Geographic Analysis | Google Trends (pytrends) + IP Geolocation |
| Telegram Bot | python-telegram-bot |
| Server Keep-Alive | GitHub Actions Cron |

---

## 2. Architecture Overview

### High-Level System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        FE["🌐 Frontend<br/>(React + Vite)"]
        TG["🤖 Telegram Bot"]
    end

    subgraph "API Layer (FastAPI)"
        API["FastAPI Server<br/>Uvicorn on port 8000"]
        CORS["CORS Middleware"]
    end

    subgraph "Core Pipeline"
        CREW["CrewAI Pipeline<br/>3 AI Agents"]
        SEARCH["Web Search<br/>SerpAPI"]
        CRED["Credibility Scorer<br/>5-Layer System"]
        TRANS["LLM Translation<br/>Hindi/Marathi/English"]
    end

    subgraph "Feature Modules"
        MEDIA["Media Verification<br/>Groq Vision"]
        HEAT["Heatmap Engine<br/>Google Trends + IP Geo"]
        TREND["Trending Pipeline<br/>RSS + Groq Analysis"]
        VOICE["Voice Interface<br/>Sarvam AI STT/TTS"]
    end

    subgraph "Data Layer"
        MONGO["MongoDB Atlas<br/>truthcrew database"]
        CACHE_A["analysis_cache<br/>(24h TTL)"]
        CACHE_H["heatmap_cache<br/>(12h TTL)"]
        CLAIMS["misinformation_claims<br/>(7-day TTL)"]
        REGION["regional_queries<br/>(30-day TTL)"]
        STATE["pipeline_state"]
    end

    subgraph "External APIs"
        GROQ["Groq Cloud<br/>LLaMA 3.3 70B"]
        GROQV["Groq Vision<br/>LLaMA 4 Scout"]
        SERP["SerpAPI<br/>Google Search"]
        SARVAM["Sarvam AI<br/>STT + TTS"]
        IPINFO["ipinfo.io<br/>IP Geolocation"]
        GTRENDS["Google Trends<br/>pytrends"]
        RSS_EXT["RSS Feeds<br/>AltNews, BoomLive, Snopes"]
    end

    FE --> CORS --> API
    TG --> API
    
    API --> CREW
    API --> MEDIA
    API --> HEAT
    API --> VOICE
    
    CREW --> SEARCH --> SERP
    CREW --> TRANS --> GROQ
    CREW --> CRED
    
    MEDIA --> GROQV
    HEAT --> GTRENDS
    HEAT --> IPINFO
    VOICE --> SARVAM
    TREND --> RSS_EXT
    TREND --> GROQ
    
    API --> MONGO
    MONGO --- CACHE_A
    MONGO --- CACHE_H
    MONGO --- CLAIMS
    MONGO --- REGION
    MONGO --- STATE
```

### Application Startup Flow

```mermaid
sequenceDiagram
    participant Main as main.py
    participant App as FastAPI App
    participant DB as MongoDB
    participant Sched as APScheduler
    participant Bot as Telegram Bot
    participant Refresh as Trending Pipeline

    Main->>App: uvicorn.run(app)
    App->>App: lifespan() — startup
    App->>DB: get_collection() — connect & create indexes
    App->>Sched: Add job: trending_refresh every 6 hours
    App->>Sched: Start scheduler
    
    App->>App: Check if data is stale (>6 hours old)
    alt Data is stale
        App->>Refresh: run_refresh_pipeline() in background thread
    end
    
    alt TELEGRAM_BOT_TOKEN is set
        App->>Bot: build_application()
        App->>Bot: Set commands, description
        App->>Bot: Start polling
    end
    
    App-->>Main: Server ready on port 8000
```

---

## 3. Technology Stack & Libraries

### Core Framework

| Library | Version | Purpose |
|---------|---------|---------|
| **FastAPI** | 0.129.0 | Async web framework with automatic OpenAPI docs |
| **Uvicorn** | 0.41.0 | ASGI server to run FastAPI |
| **Pydantic** | 2.11.10 | Data validation and serialization for request/response models |
| **python-dotenv** | 1.1.1 | Load environment variables from `.env` file |
| **python-multipart** | 0.0.22 | Parse multipart form data (file uploads) |

### AI & Machine Learning

| Library | Version | Purpose |
|---------|---------|---------|
| **CrewAI** | 1.9.3 | Multi-agent AI orchestration framework |
| **LiteLLM** | 1.74.15 | Unified LLM API wrapper (used by CrewAI) |
| **Groq Cloud API** | (REST) | Free LLM inference — LLaMA 3.3 70B + LLaMA 4 Scout Vision |
| **OpenAI SDK** | 1.83.0 | Client library used by LiteLLM for Groq-compatible API calls |

### Search & Data Collection

| Library | Version | Purpose |
|---------|---------|---------|
| **requests** | 2.32.5 | HTTP client for SerpAPI and Groq REST calls |
| **httpx** | 0.28.1 | Async HTTP client for Sarvam AI and ipinfo.io |
| **feedparser** | 6.0.12 | Parse RSS/Atom feeds from fact-check websites |
| **pytrends** | 4.9.2 | Unofficial Google Trends API for regional interest data |

### Database

| Library | Version | Purpose |
|---------|---------|---------|
| **PyMongo** | 4.16.0 | MongoDB driver for Python |
| **MongoDB Atlas** | (Cloud) | Cloud-hosted NoSQL database |

### Media Processing

| Library | Version | Purpose |
|---------|---------|---------|
| **Pillow** | 12.1.1 | Image compression, format conversion, resizing |
| **OpenCV** (headless) | 4.11.0 | Video frame extraction |

### Scheduling & Background Tasks

| Library | Version | Purpose |
|---------|---------|---------|
| **APScheduler** | 3.11.2 | Background job scheduler (6-hour trending refresh) |

### Telegram Bot

| Library | Version | Purpose |
|---------|---------|---------|
| **python-telegram-bot** | 22.7 | Telegram Bot API SDK (polling mode) |

### Voice & Speech

| Library | Version | Purpose |
|---------|---------|---------|
| **Sarvam AI** | (REST) | Indian-language Speech-to-Text and Text-to-Speech |

---

## 4. Environment Configuration

All configuration is via environment variables loaded from a `.env` file:

| Variable | Required | Service | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | Groq Cloud | API key for LLaMA 3.3 70B and LLaMA 4 Scout Vision |
| `SEARCH_API_KEY` | ✅ | SerpAPI | API key for Google Search queries |
| `MONGO_URI` | ✅ | MongoDB Atlas | Connection string: `mongodb+srv://user:pass@cluster.mongodb.net/truthcrew` |
| `SARVAM_API_KEY` | ⚠️ | Sarvam AI | Required for voice features (STT/TTS) |
| `TELEGRAM_BOT_TOKEN` | ⚠️ | Telegram | Required to enable the Telegram bot |
| `WEBSITE_URL` | ❌ | — | Frontend URL (default: `https://truthcrew.vercel.app`) |
| `CORS_ORIGINS` | ❌ | — | Comma-separated allowed origins (default: `*`) |
| `BACKEND_URL` | ❌ | — | Backend URL for Telegram bot callbacks |

> ⚠️ = Required only for that specific feature. The app starts without them but disables the feature.

---

## 5. Feature 1 — Claim Verification Pipeline

### Overview
The core feature of TruthCrew. Users submit a news claim (text), and it goes through a 3-agent AI pipeline that searches for evidence, analyzes it, and generates a multilingual verdict.

### Files Involved

| File | Purpose |
|------|---------|
| `server/api.py` | `/verify` and `/api/analyze-claim` endpoints |
| `crew/crew.py` | CrewAI pipeline orchestration |
| `crew/llm.py` | Groq LLM initialization |
| `config/agents.yaml` | AI agent role/goal/backstory definitions |
| `config/tasks.yaml` | Task descriptions and expected outputs |
| `tools/web_search.py` | SerpAPI web search with trusted-source priority |
| `server/credibility_scorer.py` | 5-layer credibility calculation |

### Complete Flow Diagram

```mermaid
sequenceDiagram
    participant User as User/Frontend
    participant API as FastAPI /api/analyze-claim
    participant Cache as MongoDB Cache
    participant Geo as ipinfo.io
    participant Trans as LLM Translation
    participant Search as SerpAPI
    participant Agent1 as Agent 1: Interpreter
    participant Agent2 as Agent 2: Analyzer
    participant Agent3 as Agent 3: Response Gen
    participant Cred as Credibility Scorer
    participant Heat as Heatmap Engine

    User->>API: POST { "query": "India GDP grew 15%" }
    API->>Cache: Check analysis_cache (MD5 hash)
    
    alt Cache HIT (within 24h)
        Cache-->>API: Return cached result
        API->>Geo: Fire-and-forget IP tracking
        API-->>User: { cached: true, data: {...} }
    end
    
    Note over API: Cache MISS — run full pipeline
    
    API->>Geo: Async IP → state geolocation
    Geo-->>API: "maharashtra"
    API->>API: save_regional_query(hash, state)
    
    API->>Trans: translate_claim_to_english(claim)
    Trans-->>API: "India's GDP grew 15% in 2025"
    
    API->>Search: search_with_priority(english_claim, 8)
    Note over Search: Step 1: Search trusted domains<br/>(PIB, BBC, NDTV, TheHindu...)
    Note over Search: Step 2: Search open web
    Note over Search: Step 3: Merge, trusted first, dedup
    Search-->>API: [8 search results with snippets]
    
    API->>Cred: calculate_credibility_score(results, claim)
    Cred-->>API: { final_score: 72, layers: {...} }
    
    Note over API: Build evidence text from search results
    
    API->>Agent1: Task: Restate claim + summarize evidence
    Agent1-->>Agent2: Clear claim + evidence summary
    
    API->>Agent2: Task: Analyze + assign verdict + confidence
    Agent2-->>Agent3: Verdict + analysis
    
    API->>Agent3: Task: Generate EN/HI/MR explanations as JSON
    Agent3-->>API: { verdict, confidence, english, hindi, marathi }
    
    Note over API: Override LLM confidence with calculated credibility score
    
    API->>Heat: get_combined_heatmap(claim, hash, sources)
    Heat-->>API: { "maharashtra": 85, "delhi": 72, ... }
    
    API->>Cache: Save analysis + heatmap to MongoDB
    API-->>User: { cached: false, data: { verdict, confidence, sources, top_regions, ... } }
```

### The 3 AI Agents

| Agent | Role | What It Does |
|-------|------|-------------|
| **Interpreter Agent** | Input Interpreter & Evidence Reviewer | Understands mixed-language inputs (Hinglish, Roman Marathi), restates the claim in clear English, and summarizes web search evidence |
| **Analyzer Agent** | Claim Analyzer & Verification Specialist | Evaluates the claim against evidence, identifies contradictions, assigns verdict (`Likely True` / `Likely False` / `Likely Misleading`) and confidence score |
| **Response Agent** | Multilingual Explanation Generator | Creates user-friendly explanations in English, Hindi (Devanagari), and Marathi (Devanagari) as a JSON object |

### Web Search Strategy

The search uses a **two-phase priority strategy**:

```mermaid
graph LR
    subgraph "Phase 1: Trusted Search"
        A["SerpAPI Query:<br/>claim + site:pib.gov.in OR<br/>site:bbc.com OR site:ndtv.com..."]
    end
    
    subgraph "Phase 2: Open Web"
        B["SerpAPI Query:<br/>claim (no restrictions)"]
    end
    
    subgraph "Phase 3: Merge"
        C["Trusted results FIRST<br/>Then open web<br/>Deduplicate by URL<br/>Return top 8"]
    end
    
    A --> C
    B --> C
```

**Trusted Domain Tiers:**

| Tier | Score | Examples |
|------|-------|---------|
| Government (Tier 1) | 100 | pib.gov.in, mygov.in, india.gov.in |
| International (Tier 2) | 90 | bbc.com, reuters.com, apnews.com |
| National News (Tier 3) | 75 | thehindu.com, ndtv.com, indianexpress.com |
| Regional News (Tier 4) | 55 | lokmat.com, mid-day.com |
| Unknown | 20 | All other domains |

### API Endpoints

#### `POST /verify` — Basic Verification (Form Data)
```
Content-Type: multipart/form-data

Fields:
  - text (string, optional): The claim to verify
  - image (file, optional): Optional image attachment

Response:
{
  "status": "success",
  "languages": ["en", "hi", "mr"],
  "data": {
    "verdict": "Likely False",
    "confidence": 72,
    "english": "This claim is not supported by...",
    "hindi": "यह दावा...",
    "marathi": "हा दावा...",
    "sources": [{ "title": "...", "url": "...", "trusted": true }],
    "credibility_layers": { ... }
  }
}
```

#### `POST /api/analyze-claim` — Full Analysis with Caching
```json
// Request
{ "query": "India's GDP grew 15% in 2025" }

// Response
{
  "status": "success",
  "cached": false,
  "data": {
    "claim": "India's GDP grew 15% in 2025",
    "verdict": "Likely False",
    "confidence": 72,
    "credibility_layers": {
      "source_tier": { "score": 75, "weight": 35 },
      "source_count": { "score": 100, "weight": 20 },
      "evidence_alignment": { "score": 60, "weight": 25 },
      "claim_verifiability": { "score": 65, "weight": 10 },
      "cross_agreement": { "score": 70, "weight": 10 }
    },
    "explanation": "Based on official data from PIB...",
    "explanation_hi": "पीआईबी के आधिकारिक आंकड़ों के अनुसार...",
    "explanation_mr": "PIB च्या अधिकृत आकडेवारीनुसार...",
    "sources": [
      { "title": "India GDP Growth...", "url": "https://...", "source": "reuters.com", "trusted": true }
    ],
    "top_regions": ["maharashtra", "delhi", "karnataka"],
    "url": "https://truthcrew.vercel.app/analyze?q=..."
  }
}
```

---

## 6. Feature 2 — Credibility Scoring System

### Overview
A transparent, **5-layer weighted scoring system** that calculates a credibility score (0-100) from web search results and the claim text. This replaces the LLM's guessed confidence with a deterministic, explainable score.

### File: `server/credibility_scorer.py`

### Scoring Layers

```mermaid
graph TB
    subgraph "5-Layer Credibility Score"
        L1["Layer 1: Source Tier Quality<br/>Weight: 35%<br/>Average tier score of all sources"]
        L2["Layer 2: Source Count<br/>Weight: 20%<br/>How many sources found (0-8 → 0-100)"]
        L3["Layer 3: Evidence Alignment<br/>Weight: 25%<br/>% of sources from trusted domains"]
        L4["Layer 4: Claim Verifiability<br/>Weight: 10%<br/>Does claim contain numbers, dates, names?"]
        L5["Layer 5: Cross Agreement<br/>Weight: 10%<br/>Multiple independent trusted sources?"]
    end
    
    L1 --> FINAL["Final Score = Σ(layer × weight)<br/>Range: 0-100"]
    L2 --> FINAL
    L3 --> FINAL
    L4 --> FINAL
    L5 --> FINAL
```

### Layer Details

| Layer | Weight | Input | Calculation |
|-------|--------|-------|-------------|
| **Source Tier** | 35% | Search result URLs | Average of domain tier scores (Gov=100, Int'l=90, National=75, Regional=55, Unknown=20) |
| **Source Count** | 20% | Number of results | `min(100, count / 8 × 100)` — 8 results = full score |
| **Evidence Alignment** | 25% | Search result URLs | `trusted_count / total_count × 100` |
| **Claim Verifiability** | 10% | Claim text | Base 30 + numbers(+20) + proper nouns(+20) + date keywords(+15) + percentages(+15) |
| **Cross Agreement** | 10% | Search result URLs | 0 trusted=0, 1=40, 2=70, 3+=100 |

### Formula
```
Final Score = L1 × 0.35 + L2 × 0.20 + L3 × 0.25 + L4 × 0.10 + L5 × 0.10
```

---

## 7. Feature 3 — Trending Misinformation Pipeline

### Overview
Automatically detects and catalogs trending misinformation by fetching articles from **fact-check RSS feeds**, analyzing them with Groq LLaMA, and storing the extracted false claims in MongoDB.

### Files Involved

| File | Purpose |
|------|---------|
| `trending/pipeline.py` | Pipeline orchestrator (fetch → filter → analyze → store) |
| `trending/rss_fetcher.py` | RSS feed parser using `feedparser` |
| `trending/filter.py` | Light filter to skip meta-pages |
| `trending/groq_analyzer.py` | Groq LLM analysis of individual articles |
| `database/db.py` | MongoDB upsert and query functions |

### Pipeline Flow

```mermaid
graph TB
    subgraph "Step 1: Fetch RSS Feeds"
        RSS1["AltNews (India)"]
        RSS2["BoomLive (India)"]
        RSS3["FactChecker.in (India)"]
        RSS4["VishvasNews (Hindi)"]
        RSS5["Snopes (Global)"]
        RSS6["AP Fact Check (Global)"]
        RSS7["Google News: fact check india"]
        RSS8["Google News: fact check global"]
    end
    
    subgraph "Step 2: Filter"
        FILTER["filter_suspicious()<br/>Skip: about/contact/privacy pages<br/>Skip: description < 20 chars<br/>Max 30 articles total, 6 per feed"]
    end
    
    subgraph "Step 3: Groq Analysis"
        GROQ["analyze_article() × 10 max<br/>3-second delay between calls<br/>LLaMA 3.3 70B via Groq API"]
        PROMPT["Prompt: 'Extract the FALSE claim<br/>this article is debunking.<br/>Score it 50-100.'"]
    end
    
    subgraph "Step 4: Store"
        STORE["upsert_claim()<br/>MongoDB: misinformation_claims<br/>Deduplicate by MD5 hash<br/>Auto-delete after 7 days"]
    end
    
    RSS1 & RSS2 & RSS3 & RSS4 & RSS5 & RSS6 & RSS7 & RSS8 --> FILTER
    FILTER --> GROQ
    GROQ --> PROMPT
    PROMPT --> STORE
```

### Scheduling

| Trigger | Frequency | Purpose |
|---------|-----------|---------|
| APScheduler | Every 6 hours | Regular refresh of trending claims |
| Startup stale-check | On cold boot | If data is >6 hours old, trigger immediate refresh |
| Manual API | `POST /api/trending/refresh` | On-demand refresh for testing |

### Groq Analysis Prompt (Simplified)

The LLM receives an article headline + description from a fact-check website and is asked to:
1. Identify the **false claim** being debunked
2. Extract it as a clear one-sentence claim
3. Score how misleading it is (50-100)
4. Categorize it (Health, Politics, Science, Technology, etc.)

Only claims with `misleading_score >= 50` are stored.

### API Endpoint

#### `GET /api/trending-claims`
```
Query Parameters:
  - region (optional): "global", "india", "maharashtra", "delhi", "kerala"

Response:
{
  "status": "success",
  "region_filter": "india",
  "count": 10,
  "data": [
    {
      "claim": "5G towers cause COVID-19",
      "explanation": "This claim has been debunked by...",
      "category": "Health",
      "misleading_score": 92,
      "source_name": "AltNews",
      "source_url": "https://altnews.in/...",
      "region": "india",
      "published_at": "2026-03-31T10:00:00+00:00",
      "created_at": "2026-03-31T10:05:00+00:00"
    }
  ]
}
```

---

## 8. Feature 4 — Geographic Heatmap & Spread Analysis

### Overview
Shows how a misinformation claim is spreading across Indian states by combining three data signals into a unified 0-100 heatmap.

### Files Involved

| File | Purpose |
|------|---------|
| `server/heatmap.py` | Google Trends fetching, fallback generation, 3-signal combination |
| `server/api.py` | `/api/heatmap` and `/api/heatmap-insight` endpoints |
| `database/db.py` | Heatmap caching and regional query storage |

### Three Signals Combined

```mermaid
graph LR
    subgraph "Signal 1 (50%)"
        GT["Google Trends<br/>pytrends library<br/>Past 7 days, geo=IN<br/>interest_by_region()"]
    end
    
    subgraph "Signal 2 (30%)"
        NEWS["News Coverage<br/>Map source URLs to states<br/>e.g. lokmat.com → maharashtra<br/>ndtv.com → delhi"]
    end
    
    subgraph "Signal 3 (20%)"
        USER["User Queries<br/>IP geolocation via ipinfo.io<br/>Stored in regional_queries<br/>MongoDB collection"]
    end
    
    GT --> COMBINE["Weighted Average<br/>per state"]
    NEWS --> COMBINE
    USER --> COMBINE
    
    COMBINE --> OUTPUT["{ 'maharashtra': 85,<br/>'delhi': 72,<br/>'karnataka': 45 }"]
```

### Regional News Domain Mapping

The system maps 50+ Indian news website domains to their headquarter states:

| State | Domains |
|-------|---------|
| Maharashtra | lokmat.com, maharashtratimes.com, mid-day.com, loksatta.com, esakal.com |
| Gujarat | divyabhaskar.co.in, gujaratsamachar.com, sandesh.com |
| Tamil Nadu | dinakaran.com, dinamalar.com, dailythanthi.com, thehindu.com |
| Karnataka | deccanherald.com, vijaykarnataka.com, prajavani.net |
| Kerala | mathrubhumi.com, manoramaonline.com, keralakaumudi.com |
| Delhi | hindustantimes.com, ndtv.com, indianexpress.com, timesofindia.indiatimes.com |
| ... | (and more for UP, MP, Punjab, WB, Bihar, Odisha, Assam) |

### Fallback Mechanism

If Google Trends returns no data (429 rate limit or empty results), the system generates **deterministic simulated data** using an MD5 hash of the query:

```python
# Same query always produces same spread pattern (cacheable)
hash = md5(query.lower().encode())
num_states = 6 + (hash[0] % 7)  # 6 to 12 states
# Scores between 20-98, derived from hash bytes
```

### API Endpoints

#### `GET /api/heatmap?query=5G+towers+cause+cancer`
```json
{
  "status": "success",
  "data": {
    "maharashtra": 85,
    "delhi": 72,
    "karnataka": 45,
    "tamil nadu": 38,
    "uttar pradesh": 30
  }
}
```

#### `POST /api/heatmap-insight`
```json
// Request
{
  "query": "5G towers cause cancer",
  "heatmap_data": { "maharashtra": 85, "delhi": 72, "karnataka": 45 }
}

// Response
{
  "insight": "The claim shows highest interest in Maharashtra and Delhi, likely due to urban media consumption and tech awareness in major metros."
}
```

---

## 9. Feature 5 — Media Verification (AI Deepfake Detection)

### Overview
Detects AI-generated images and videos using **Groq Vision** (LLaMA 4 Scout 17B multimodal model). Uses both visual analysis and filename metadata signals.

### Files Involved

| File | Purpose |
|------|---------|
| `server/media_verification.py` | All media detection logic + API routes |

### Image Detection Flow

```mermaid
sequenceDiagram
    participant User as User
    participant API as POST /api/detect-image
    participant Comp as Image Compressor
    participant Fname as Filename Analyzer
    participant Groq as Groq Vision API
    
    User->>API: Upload image (max 20 MB)
    API->>API: Validate content type (image/*)
    API->>API: Check file size limit
    
    alt Image > 1 MB
        API->>Comp: Compress (reduce quality 90→40, then resize)
    end
    
    API->>Fname: Check filename for AI keywords
    Note over Fname: "midjourney", "dalle", "sora",<br/>"generated", "deepfake", etc.
    Fname-->>API: filename_score (0 or 90)
    
    API->>Groq: Send base64 image + forensic prompt
    Note over Groq: Analyze lighting, textures, hands,<br/>symmetry, backgrounds, watermarks
    Groq-->>API: { ai_probability: 75, english/hindi/marathi }
    
    API->>API: final_score = max(visual_score, filename_score)
    
    alt Score ≥ 70
        API-->>User: "likely AI-generated"
    else Score ≥ 35
        API-->>User: "uncertain"
    else Score < 35
        API-->>User: "likely real"
    end
```

### Video Detection Flow

```mermaid
graph TB
    UPLOAD["Upload video (max 15 MB)"] --> EXTRACT["Extract 3 frames<br/>(start, middle, end)<br/>using OpenCV"]
    EXTRACT --> ANALYZE["Analyze 2 frames<br/>(first + middle)<br/>with Groq Vision"]
    ANALYZE --> AVERAGE["Average AI probability<br/>from both frames"]
    AVERAGE --> VERDICT["Apply verdict thresholds<br/>≥70: AI-generated<br/>35-69: Uncertain<br/><35: Real"]
```

### AI Filename Keywords

The system checks filenames for these keywords (returns score 90 if found):

```
generated, midjourney, dalle, stablediffusion, sora, runway, kling,
pika, haiper, luma, hailuo, chatgpt, gemini, firefly, flux, ideogram,
deepfake, fake, synthetic, artificial, ai_image, ai_video, ai_art
```

### API Endpoints

#### `POST /api/detect-image`
```json
// Response
{
  "status": "success",
  "ai_probability": 75,
  "verdict": "likely AI-generated",
  "filename": "midjourney_landscape.png",
  "raw": [{ "label": "AI-Generated", "score": 0.75 }],
  "explanation": {
    "english": "The image shows several AI-generation artifacts...",
    "hindi": "छवि में कई AI-जनित कलाकृतियां दिखाई दे रही हैं...",
    "marathi": "प्रतिमेत अनेक AI-निर्मित कलाकृती दिसत आहेत..."
  }
}
```

#### `POST /api/detect-video`
```json
// Response (same structure + frames_analyzed count)
{
  "status": "success",
  "ai_probability": 62,
  "verdict": "uncertain",
  "filename": "clip.mp4",
  "frames_analyzed": 2,
  "explanation": { "english": "...", "hindi": "...", "marathi": "..." }
}
```

#### `POST /api/detect-audio` (Coming Soon)
Returns `{ "status": "unavailable" }` — requires GPU infrastructure.

---

## 10. Feature 6 — Voice Interface (Speech-to-Text & Text-to-Speech)

### Overview
Enables multilingual voice interaction using **Sarvam AI**'s Indian-language models. Users can speak claims in Hindi, Marathi, or English and receive spoken verdicts back.

### Flow Diagram

```mermaid
sequenceDiagram
    participant User as User (Telegram)
    participant Bot as Telegram Bot
    participant STT as Sarvam STT API
    participant Pipeline as Fact-Check Pipeline
    participant TTS as Sarvam TTS API
    
    User->>Bot: 🎙️ Voice message (Hindi)
    Bot->>Bot: Download OGG audio from Telegram
    Bot->>STT: POST /speech-to-text (audio bytes)
    STT-->>Bot: "क्या 5G टावर से कोरोना फैलता है"
    
    Bot->>Bot: Show transcript to user
    Bot->>Pipeline: _analyze_claim(transcript)
    Pipeline-->>Bot: { verdict, explanation_hi, ... }
    
    Bot->>Bot: Send text verdict card
    Bot->>TTS: POST /text-to-speech (explanation_hi, hi-IN)
    TTS-->>Bot: WAV audio bytes (base64)
    Bot->>User: 🔊 Voice response + text card
```

### Sarvam AI Configuration

| Feature | Endpoint | Model |
|---------|----------|-------|
| Speech-to-Text | `https://api.sarvam.ai/speech-to-text` | Auto-detect language |
| Text-to-Speech | `https://api.sarvam.ai/text-to-speech` | Bulbul v3 |

### TTS Voice Mapping

| Language | Code | Voice Name |
|----------|------|------------|
| Hindi | `hi-IN` | Priya |
| Marathi | `mr-IN` | Kavitha |
| English | `en-IN` | Rahul |

### API Endpoints

#### `POST /api/agents/stt`
Upload audio → returns transcript text.

#### `POST /api/agents/tts`
```json
// Request
{ "text": "This claim is likely false.", "language": "hi-IN" }

// Response: audio/wav stream (binary)
```

---

## 11. Feature 7 — Telegram Bot Integration

### Overview
A full-featured Telegram bot that provides fact-checking directly in Telegram. Supports text claims, voice messages, trending claims, and multilingual responses.

### Files Involved

| File | Purpose |
|------|---------|
| `telegram_bot/bot.py` | Application builder, handler registration |
| `telegram_bot/handlers.py` | All command and message handlers |
| `telegram_bot/formatter.py` | MarkdownV2 message formatting |
| `telegram_bot/rate_limiter.py` | Per-user rate limiting (5 requests/minute) |
| `telegram_bot/user_prefs.py` | In-memory language preferences |

### Bot Commands

| Command | Function | Description |
|---------|----------|-------------|
| `/start` | `start()` | Welcome message with usage guide |
| `/check <claim>` | `check()` | Analyze a specific claim |
| `/trending` | `trending()` | Show top 5 trending misinformation |
| `/language` | `language_cmd()` | Change preferred language (EN/HI/MR) |
| `/help` | `help_cmd()` | Show all available commands |

### Bot Architecture

```mermaid
graph TB
    subgraph "Input Handlers"
        CMD_START["/start"]
        CMD_CHECK["/check claim"]
        CMD_TREND["/trending"]
        CMD_LANG["/language"]
        CMD_HELP["/help"]
        MSG["Plain text<br/>(reply to bot only)"]
        VOICE["🎙️ Voice message"]
        CALLBACK["Inline button<br/>callbacks"]
    end
    
    subgraph "Processing"
        RATE["Rate Limiter<br/>5 requests / 60 seconds"]
        ANALYZE["_analyze_claim()<br/>Cache → CrewAI → Heatmap"]
        STT_H["Sarvam STT<br/>Voice → Text"]
        TTS_H["Sarvam TTS<br/>Text → Voice"]
        FORMAT["Formatter<br/>MarkdownV2 + Inline Buttons"]
    end
    
    subgraph "Features"
        LANG_SWITCH["Language Switcher<br/>EN / HI / MR buttons"]
        PREFS["User Preferences<br/>In-memory store"]
    end
    
    CMD_CHECK --> RATE --> ANALYZE --> FORMAT
    MSG --> RATE
    VOICE --> RATE --> STT_H --> ANALYZE
    ANALYZE --> TTS_H
    CMD_LANG --> PREFS
    CALLBACK --> LANG_SWITCH
    CALLBACK --> PREFS
```

### Callback Data Patterns

| Pattern | Purpose | Example |
|---------|---------|---------|
| `lang\|<hash>\|<code>` | Switch analysis language | `lang\|abc123\|hi` |
| `setlang\|<code>` | Set persistent preference | `setlang\|mr` |

### Rate Limiting

- **5 requests per 60-second rolling window** per user
- Uses in-memory timestamp tracking
- Shows remaining wait time when throttled

---

## 12. Feature 8 — Caching & Database Layer

### Overview
MongoDB Atlas stores all cached data with TTL (Time-To-Live) indexes for automatic expiration.

### File: `database/db.py`

### Database: `truthcrew`

### Collections

```mermaid
graph LR
    subgraph "MongoDB Atlas — truthcrew database"
        C1["misinformation_claims<br/>TTL: 7 days<br/>Index: claim_hash (unique)"]
        C2["analysis_cache<br/>TTL: 24 hours<br/>Index: claim_hash"]
        C3["heatmap_cache<br/>TTL: 12 hours<br/>Index: query_hash"]
        C4["regional_queries<br/>TTL: 30 days<br/>Index: (claim_hash, state) unique"]
        C5["pipeline_state<br/>No TTL<br/>Tracks last refresh time"]
    end
```

### Collection Details

| Collection | TTL | Purpose | Key Fields |
|-----------|-----|---------|------------|
| `misinformation_claims` | 7 days | Trending claims from RSS pipeline | `claim_hash`, `claim`, `misleading_score`, `category`, `region` |
| `analysis_cache` | 24 hours | Cached fact-check results | `claim_hash`, `data` (full analysis object) |
| `heatmap_cache` | 12 hours | Cached heatmap state→score maps | `query_hash`, `data` |
| `regional_queries` | 30 days | IP-geolocated user query origins | `claim_hash`, `state`, `count` |
| `pipeline_state` | None | Tracks last trending refresh timestamp | `_id: "trending_refresh"`, `last_refreshed_at` |

### Deduplication Strategy

Claims are deduplicated using an **MD5 hash** of the normalized (lowercase, trimmed) claim text:

```python
def make_claim_hash(claim_text: str) -> str:
    normalized = claim_text.strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()
```

### Upsert Logic

When a duplicate claim is detected, `upsert_claim()` uses `$inc` to increment the `trending_score` instead of inserting a new document. This tracks how often the same claim appears across different sources.

---

## 13. Feature 9 — Server Health & Keep-Alive System

### Overview
The backend is deployed on **Render's free tier**, which spins down after 15 minutes of inactivity. A **GitHub Actions cron job** pings the `/health` endpoint every 5 minutes to keep it alive.

### Files Involved

| File | Purpose |
|------|---------|
| `server/api.py` | `/health` endpoint |
| `.github/workflows/keep_alive.yml` | GitHub Actions cron workflow |

### Keep-Alive Flow

```mermaid
graph LR
    GHA["GitHub Actions<br/>Cron: */5 * * * *"] -->|"curl /health"| RENDER["Render Server<br/>(Free Tier)"]
    RENDER -->|"{ status: ok }"| GHA
    
    RENDER -->|"Every 6 hours"| SCHED["APScheduler<br/>Trending Refresh"]
    
    RENDER -->|"On cold start"| STALE["Stale-Data Check<br/>>6 hours old?"]
    STALE -->|"Yes"| REFRESH["Immediate Refresh<br/>in background thread"]
```

### Health Response
```json
{
  "status": "ok",
  "timestamp": "2026-04-01T00:00:00+00:00",
  "last_trending_refresh": "2026-03-31T23:00:00+00:00"
}
```

### Startup Stale-Data Recovery

On every cold boot, the server checks if the last trending refresh was more than 6 hours ago. If so, it triggers an immediate refresh in a background thread to ensure users always see fresh data.

---

## 14. API Reference

### Complete Endpoint Summary

| Method | Path | Tag | Description |
|--------|------|-----|-------------|
| `POST` | `/verify` | 🔍 Claim Verification | Verify a claim (form-data with optional image) |
| `POST` | `/api/analyze-claim` | 🔍 Claim Verification | Analyze a claim with caching, heatmap, and geolocation |
| `GET` | `/api/trending-claims` | 🔥 Trending | Get top 10 trending misinformation claims |
| `POST` | `/api/trending/refresh` | 🔥 Trending | Manually trigger the trending refresh pipeline |
| `GET` | `/api/heatmap` | 🗺️ Heatmap | Get regional spread scores for a claim |
| `POST` | `/api/heatmap-insight` | 🗺️ Heatmap | Generate AI insight about geographic spread |
| `POST` | `/api/agents/stt` | 🎙️ Voice | Speech-to-Text (Sarvam AI) |
| `POST` | `/api/agents/tts` | 🎙️ Voice | Text-to-Speech (Sarvam AI) |
| `POST` | `/api/detect-image` | 🖼️ Media | AI image detection (Groq Vision) |
| `POST` | `/api/detect-video` | 🖼️ Media | AI video detection (frame analysis) |
| `POST` | `/api/detect-audio` | 🖼️ Media | Audio deepfake detection (coming soon) |
| `GET` | `/health` | ⚙️ System | Health check / keep-alive probe |

### Interactive API Docs

FastAPI provides two built-in documentation interfaces:

- **Swagger UI**: `http://localhost:8000/docs` — Interactive testing
- **ReDoc**: `http://localhost:8000/redoc` — Clean documentation view

---

## 15. Directory Structure

```
backend/
├── main.py                          # Entry point — starts Uvicorn server
├── pyproject.toml                   # Project metadata and dependencies
├── requirements.txt                 # Pinned dependency versions
├── .envExample                      # Environment variable template
│
├── server/                          # API layer
│   ├── api.py                       # All FastAPI endpoints + lifespan
│   ├── credibility_scorer.py        # 5-layer credibility scoring
│   ├── heatmap.py                   # Google Trends + 3-signal heatmap
│   └── media_verification.py        # AI image/video/audio detection
│
├── crew/                            # CrewAI multi-agent pipeline
│   ├── crew.py                      # Pipeline orchestration (run_crew)
│   └── llm.py                       # Groq LLM initialization
│
├── config/                          # YAML configs for AI agents
│   ├── agents.yaml                  # Agent roles, goals, backstories
│   └── tasks.yaml                   # Task descriptions and outputs
│
├── tools/                           # External tool integrations
│   └── web_search.py                # SerpAPI with trusted-source priority
│
├── database/                        # Data persistence
│   └── db.py                        # MongoDB Atlas connection + all CRUD
│
├── trending/                        # Trending misinformation engine
│   ├── pipeline.py                  # Orchestrator (fetch → filter → analyze → store)
│   ├── rss_fetcher.py               # RSS feed parser (8 fact-check feeds)
│   ├── filter.py                    # Light filter for meta-pages
│   └── groq_analyzer.py            # Groq LLM misinformation scorer
│
├── telegram_bot/                    # Telegram bot integration
│   ├── bot.py                       # Application builder + handler registration
│   ├── handlers.py                  # Command + message + voice handlers
│   ├── formatter.py                 # MarkdownV2 message templates
│   ├── rate_limiter.py              # Per-user rate limiting
│   └── user_prefs.py                # In-memory language preferences
│
└── .github/
    └── workflows/
        └── keep_alive.yml           # GitHub Actions cron (ping /health every 5 min)
```

---

> 📝 **Note**: This documentation covers the complete backend as of April 2026. For interactive API testing, visit `/docs` (Swagger UI) or `/redoc` on your running server.
