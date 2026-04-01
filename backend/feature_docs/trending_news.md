# 🔥 Trending News Feature — Complete Explanation

## What This Feature Does

The Trending News feature **automatically finds viral misinformation claims** from fact-check websites, scores them using AI, stores them in MongoDB, and serves them to users via API. It runs on autopilot with a 6-hour refresh cycle.

---

## Files Involved

| File | Purpose |
|------|---------|
| `trending/rss_fetcher.py` | Step 1 — Fetch articles from RSS feeds |
| `trending/filter.py` | Step 2 — Remove junk/meta pages |
| `trending/groq_analyzer.py` | Step 3 — AI analyzes each article |
| `trending/pipeline.py` | Orchestrator — runs Step 1→2→3 in order |
| `database/db.py` | MongoDB operations (store, retrieve, TTL) |
| `server/api.py` | API endpoints + scheduler setup |

---

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    TRIGGER (3 ways)                       │
│                                                          │
│  1. APScheduler (every 6 hours)  →  api.py line 72-79   │
│  2. Server startup (if stale)    →  api.py line 86-107  │
│  3. Manual API call              →  api.py line 772-794 │
│                POST /api/trending/refresh                │
└────────────────────────┬─────────────────────────────────┘
                         ↓
        ┌─── run_refresh_pipeline() ───┐
        │    pipeline.py line 26       │
        │                              │
        │  Step 1: fetch_articles()    │  ← rss_fetcher.py
        │           ↓                  │
        │  Step 2: filter_suspicious() │  ← filter.py
        │           ↓                  │
        │  Step 3: analyze_article()   │  ← groq_analyzer.py (×10 max)
        │           ↓                  │
        │  Step 4: upsert_claim()      │  ← db.py (save to MongoDB)
        │           ↓                  │
        │  Save last refresh time      │
        └──────────────────────────────┘
                         ↓
        ┌─── User requests trending ───┐
        │  GET /api/trending-claims    │  ← api.py line 660
        │           ↓                  │
        │  get_trending_claims()       │  ← db.py line 102
        │  (reads from MongoDB,        │
        │   sorted by misleading_score)│
        └──────────────────────────────┘
```

---

## Step-by-Step Detailed Explanation

### Step 1: Fetch Articles from RSS Feeds

**File:** `trending/rss_fetcher.py`

The system fetches articles from **8 fact-check RSS feeds** using the `feedparser` library.

#### RSS Feed Sources (line 20-42):

| Feed | Region | Why this source? |
|------|--------|------------------|
| `altnews.in/feed/` | India | India's top fact-checker |
| `boomlive.in/feed` | India | Popular Indian fact-check site |
| `factchecker.in/feed/` | India | Indian fact-check site |
| `vishvasnews.com/feed/` | India | Hindi fact-checker |
| `snopes.com/feed/` | Global | World-famous fact-checker |
| `apnews.com/hub/ap-fact-check` | Global | AP News fact-check section |
| Google News (fact check india) | India | Google aggregated results |
| Google News (fact check global) | Global | Google aggregated results |

> **Why fact-check sites?** Because normal news sites (BBC, NDTV) report on topics — Groq would score them as "not misleading". Fact-check sites specifically **debunk false claims** — every article contains a real misleading claim that Groq can extract.

#### How fetching works (line 65-115):

```python
# Limits to prevent overload
MAX_ARTICLES_TOTAL = 30   # max articles across all feeds
MAX_PER_FEED = 6          # max articles per single feed
```

For each feed:
1. Parse RSS XML using `feedparser.parse(feed_url)` (line 78)
2. Extract from each entry: **title, description, URL, published date, source name** (lines 89-104)
3. **Clean HTML tags** from text using regex: `re.sub(r"<[^>]+>", "", text)` (line 62)
4. **Skip duplicates** using `seen_urls` set (line 86-87)
5. **Truncate description** to 600 characters max (line 100)
6. Stop when we hit 30 total articles

#### Output: A list of article dicts like:
```json
{
    "title": "Fact Check: Did PM Modi say India will ban WhatsApp?",
    "description": "A viral message claims PM Modi announced...",
    "url": "https://www.altnews.in/fact-check-pm-modi-whatsapp-ban",
    "source_name": "Alt News",
    "published_at": "2026-03-30T10:00:00+00:00",
    "region": "india"
}
```

---

### Step 2: Filter Articles

**File:** `trending/filter.py`

A **light filter** that removes junk articles. Since we use fact-check feeds, almost everything passes.

#### What gets removed (lines 17-41):

1. **Meta pages** — titles like "About", "Contact", "Privacy", "Subscribe" (line 31)
2. **Empty descriptions** — description shorter than 20 characters AND title shorter than 20 characters (lines 35-38)

```python
SKIP_TITLES = {"about", "contact", "privacy", "subscribe", "home", "sitemap"}
MIN_DESCRIPTION_LEN = 20
```

#### Why so light?
Because we specifically use **fact-check feeds** — every article IS about a misleading claim. No need for heavy keyword filtering. The real filtering happens in Step 3 (Groq scoring).

---

### Step 3: Groq AI Analysis

**File:** `trending/groq_analyzer.py`

Each filtered article is sent to **Groq LLaMA 3.3 70B** to extract the false claim and score it.

#### The Prompt (line 25-50):

The AI is told:
- "This article is from a FACT-CHECK website — it is debunking a viral false claim"
- "Identify the FALSE claim being debunked"
- "Extract it as a one-sentence claim"
- "Score how misleading that claim is (50-100)"

#### Scoring Guide given to AI:

| Score Range | Meaning |
|-------------|---------|
| 85–100 | Completely false, viral, potentially dangerous |
| 65–84 | Misleading, exaggerated, or unsupported |
| 50–64 | Partially false or missing important context |

#### API Call Details (lines 73-88):

```python
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

payload = {
    "model": GROQ_MODEL,
    "temperature": 0.3,    # low = more focused, less creative
    "max_tokens": 512,     # short response expected
}
```

#### AI Returns JSON like:
```json
{
    "misleading": true,
    "claim": "PM Modi announced India will ban WhatsApp by 2026",
    "explanation": "This claim is completely false. No such announcement was made...",
    "category": "Politics",
    "misleading_score": 88
}
```

#### Threshold Check (line 112-114):
```python
MIN_MISLEADING_SCORE = 50

if score < MIN_MISLEADING_SCORE:
    return None  # skip — not misleading enough
```

If score is **below 50**, the article is **skipped** and not stored.

#### Final Output (lines 116-125):
```python
return {
    "claim": result.get("claim", article["title"]),
    "explanation": result.get("explanation", ""),
    "category": result.get("category", "Other"),
    "misleading_score": score,
    "source_name": article.get("source_name", "Unknown"),
    "source_url": article.get("url", ""),
    "region": article.get("region", "global"),
    "published_at": article.get("published_at"),
}
```

---

### Step 4: Pipeline Orchestrator

**File:** `trending/pipeline.py`

This file calls Step 1 → 2 → 3 in order and handles rate limiting.

#### Key Constants (lines 20-23):
```python
MAX_GROQ_CALLS = 10        # max articles to send to AI per refresh
GROQ_DELAY_SECONDS = 3     # wait 3 seconds between each AI call
```

#### Why limit to 10?
Groq **free tier** has API rate limits. If we send 30 articles at once, we'll get blocked. So we only analyze the **first 10** filtered articles per refresh.

#### Why 3-second delay?
```python
# pipeline.py line 78-79
if i < len(to_analyze) - 1:
    time.sleep(GROQ_DELAY_SECONDS)   # avoid Groq rate limit
```
Groq free tier allows ~30 requests/minute. 3-second gaps = 20 requests/minute = safe.

#### What happens with each article (lines 52-79):
```
For each article (max 10):
  ├─ analyze_article(article)  → sends to Groq
  │    ├─ Returns result dict  → upsert_claim(result) → saved to MongoDB ✅
  │    ├─ Returns None         → skipped (score too low) ⏭️
  │    └─ Throws Exception     → logged as error ❌
  └─ Wait 3 seconds before next article
```

#### Pipeline Summary (lines 84-99):
After all articles are processed, the pipeline returns a summary:
```json
{
    "status": "success",
    "articles_fetched": 30,
    "articles_filtered": 25,
    "groq_calls_made": 10,
    "claims_stored": 7,
    "claims_skipped": 3,
    "errors": 0,
    "duration_seconds": 45.2
}
```

#### Save Last Refresh Time (line 107):
```python
set_last_refresh_time()  # saves current UTC time to MongoDB
```
This is used by the **startup stale-check** to know when the pipeline last ran.

---

### Step 5: Store in MongoDB

**File:** `database/db.py` — `upsert_claim()` function (line 73-99)

#### Collection: `misinformation_claims`

#### Upsert Logic:
```python
col.update_one(
    {"claim_hash": claim_hash},        # find by hash
    {
        "$setOnInsert": { ... },       # only set these fields on FIRST insert
        "$inc": {"trending_score": 1}, # increment score every time
    },
    upsert=True,                       # insert if not found
)
```

**What this means:**
- If claim **doesn't exist** → insert new document + set `trending_score = 1`
- If claim **already exists** (same hash) → only increment `trending_score` by 1, don't update other fields

#### Document Structure in MongoDB:
```json
{
    "claim_hash": "a3f8b2c1d4e5...",
    "claim": "PM Modi announced India will ban WhatsApp by 2026",
    "explanation": "This claim is completely false...",
    "category": "Politics",
    "misleading_score": 88,
    "source_name": "Alt News",
    "source_url": "https://www.altnews.in/...",
    "region": "india",
    "published_at": "2026-03-30T10:00:00Z",
    "created_at": "2026-03-30T12:00:00Z",
    "trending_score": 3
}
```

#### TTL (Auto-Delete) — line 43:
```python
_collection.create_index("created_at", expireAfterSeconds=7 * 24 * 3600)
```
MongoDB **automatically deletes** documents 7 days after `created_at`. No cleanup code needed.

#### Deduplication — line 40:
```python
_collection.create_index("claim_hash", unique=True)
```
The `claim_hash` field has a **unique index** — MongoDB won't allow two documents with the same hash.

---

## How The Pipeline Gets Triggered (3 Ways)

### Way 1: APScheduler — Automatic Every 6 Hours

**File:** `server/api.py` lines 72-80

```python
scheduler.add_job(
    scheduled_refresh,
    trigger="interval",
    hours=6,
    id="trending_refresh",
    replace_existing=True,
)
scheduler.start()
```

APScheduler is a Python library that runs a function on a timer. Every 6 hours, it calls `scheduled_refresh()` → which calls `run_refresh_pipeline()`.

#### Problem: Server Restarts Reset the Timer
On free hosting (like Render), the server **spins down** after inactivity. When it restarts, APScheduler also restarts — it doesn't remember the last run. This means after a long spin-down (say 20 hours), the data could be stale.

### Way 2: Startup Stale-Check — Runs on Every Server Boot

**File:** `server/api.py` lines 82-108

```python
def _startup_refresh_if_stale():
    last = get_last_refresh_time()               # check MongoDB for last run time
    is_stale = (last is None) or (
        datetime.now(timezone.utc) - last > timedelta(hours=6)
    )
    if is_stale:
        run_refresh_pipeline()                    # data is old, refresh now!
```

**Every time the server starts:**
1. Read `last_refreshed_at` from MongoDB `pipeline_state` collection
2. If it was more than 6 hours ago (or never ran) → run pipeline immediately
3. If it was recent → skip ("data is fresh")

This runs in a **background thread** (line 107) so it doesn't block server startup:
```python
threading.Thread(target=_startup_refresh_if_stale, daemon=True).start()
```

### Way 3: Manual API Trigger

**File:** `server/api.py` lines 765-794

```
POST /api/trending/refresh
```

Calling this endpoint manually runs the pipeline. Used for:
- First-time setup (when MongoDB is empty)
- Testing the pipeline
- Forcing a refresh without waiting 6 hours

---

## How Users Get Trending Claims (API)

### Endpoint: `GET /api/trending-claims`

**File:** `server/api.py` lines 660-703

```python
async def trending_claims(region: Optional[str] = None):
    claims = get_trending_claims(region=region, limit=10)
    return {
        "status": "success",
        "region_filter": region or "all",
        "count": len(claims),
        "data": claims,
    }
```

### Database Query (db.py line 102-123):

```python
def get_trending_claims(region=None, limit=10):
    query = {}
    if region and region.lower() != "all":
        query["region"] = region.lower()     # optional region filter

    cursor = col.find(query)
        .sort("misleading_score", DESCENDING)  # highest score first
        .limit(limit)                          # max 10 results
```

### Region Filters:
| Parameter | Returns |
|-----------|---------|
| `?region=india` | Only India claims |
| `?region=global` | Only global claims |
| `?region=maharashtra` | Only Maharashtra claims |
| No parameter | All regions |

### Response Example:
```json
{
    "status": "success",
    "region_filter": "india",
    "count": 5,
    "data": [
        {
            "claim": "PM Modi announced WhatsApp ban",
            "explanation": "This is completely false...",
            "category": "Politics",
            "misleading_score": 92,
            "source_name": "Alt News",
            "region": "india",
            "trending_score": 5
        }
    ]
}
```

---

## Rate Limiting & Free Tier Protection

| Protection | Where | Value |
|-----------|-------|-------|
| Max articles fetched | `rss_fetcher.py` line 44 | 30 total |
| Max per feed | `rss_fetcher.py` line 45 | 6 per feed |
| Max Groq calls per refresh | `pipeline.py` line 20 | 10 calls |
| Delay between Groq calls | `pipeline.py` line 23 | 3 seconds |
| Min score to store | `groq_analyzer.py` line 23 | 50 (out of 100) |
| Auto-delete old claims | `db.py` line 43 | 7 days TTL |

---

## Timeline Example

```
Day 1, 00:00  — Server starts → stale-check → runs pipeline
                  └─ Fetches 30 articles → filters to 25 → analyzes 10
                  └─ Stores 7 claims (score ≥ 50), skips 3

Day 1, 06:00  — APScheduler triggers → runs pipeline
                  └─ Fetches 28 articles → filters to 22 → analyzes 10
                  └─ Stores 5 new + bumps trending_score of 2 existing

Day 1, 12:00  — APScheduler triggers → runs pipeline again
                  └─ Same claim "WhatsApp ban" found again → trending_score: 3

Day 2 - Day 6 — Pipeline keeps running every 6 hours
                  └─ New claims added, popular ones get higher trending_score

Day 8, 00:00  — MongoDB TTL auto-deletes Day 1 claims (7 days old)
                  └─ Trending page now shows only Day 2+ claims

... cycle continues forever ...
```

---

## Summary

| What | Answer |
|------|--------|
| **Data Source** | 8 fact-check RSS feeds (AltNews, BoomLive, Snopes, etc.) |
| **AI Model** | Groq LLaMA 3.3 70B |
| **Refresh Cycle** | Every 6 hours (+ on startup if stale) |
| **Max AI calls per refresh** | 10 (with 3s delay each) |
| **Storage** | MongoDB Atlas, `misinformation_claims` collection |
| **Auto-cleanup** | TTL index deletes claims after 7 days |
| **Deduplication** | MD5 hash of claim text (unique index) |
| **API Endpoint** | `GET /api/trending-claims?region=india` |
| **Sorting** | By `misleading_score` descending (most dangerous first) |
