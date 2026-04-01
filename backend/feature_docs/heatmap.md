# 🗺️ Heatmap Feature — Complete Explanation

## What This Feature Does

The Heatmap feature shows **which Indian states are most interested in a particular claim**. It paints a map where high-interest states are highlighted. It combines 3 data signals and also generates an AI insight explaining the geographic pattern.

---

## Files Involved

| File | Purpose |
|------|---------|
| `server/heatmap.py` | Core logic — fetches Google Trends, maps news domains to states, combines 3 signals |
| `server/api.py` | API endpoints — `/api/heatmap`, `/api/heatmap-insight`, and heatmap building inside `/api/analyze-claim` |
| `database/db.py` | MongoDB — cache heatmap data (12h TTL), store/read regional user queries (30d TTL) |

---

## Complete Flow Diagram

```
User searches a claim
        ↓
┌─── /api/heatmap (api.py line 709) ────────────┐
│                                                 │
│  1. MD5 hash the query                          │
│  2. Check heatmap_cache in MongoDB              │
│     ├─ HIT → return cached data instantly       │
│     └─ MISS → continue ↓                       │
│                                                 │
│  3. get_combined_heatmap() (heatmap.py line 227)│
│     ├─ Signal 1: Google Trends (50%)            │
│     ├─ Signal 2: News Coverage (30%)            │
│     └─ Signal 3: User IP Queries (20%)          │
│                                                 │
│  4. Save combined result to heatmap_cache       │
│  5. Return { state: score } map                 │
└─────────────────────────────────────────────────┘
        ↓
┌─── /api/heatmap-insight (api.py line 800) ─────┐
│                                                 │
│  Takes heatmap data + claim text                │
│  → Sends to Groq LLaMA 3.3 70B                 │
│  → Returns 1-2 sentence insight                 │
│  (e.g. "Higher interest in Maharashtra likely   │
│   due to regional political context...")         │
└─────────────────────────────────────────────────┘
```

---

## The 3 Signals — Explained in Detail

### Signal 1: Google Trends (50% weight)

**File:** `heatmap.py` — `get_google_trends_heatmap()` (line 180-224)

**What it does:** Asks Google Trends "how much is each Indian state searching for this topic in the last 7 days?"

**How it works:**

```python
# line 195-202
_pytrends.build_payload(
    kw_list=[clean_query],     # e.g. "BJP elections"
    timeframe="now 7-d",       # last 7 days
    geo="IN",                  # India only
)
df = _pytrends.interest_by_region(
    resolution="REGION",       # state-level data
    inc_low_vol=True,          # include states with low search volume
)
```

**Library used:** `pytrends` — an unofficial Python library for Google Trends.

**Query trimming (line 189):**
```python
clean_query = " ".join(query.strip().split()[:5])  # only first 5 words
```
Long queries don't work well with Google Trends, so we take only the first 5 words.

**Output example:**
```python
{
    "maharashtra": 85,
    "delhi": 72,
    "karnataka": 45,
    "tamil nadu": 38,
    "uttar pradesh": 22
}
```

**Compatibility fix (lines 16-27):**
```python
# pytrends uses old urllib3 parameter name "method_whitelist"
# newer urllib3 renamed it to "allowed_methods"
# This patch fixes the incompatibility
urllib3.util.retry.Retry.__init__ = _patched_retry_init
```
Without this fix, pytrends would crash on newer Python environments.

#### Fallback: Simulated Data (line 153-177)

If Google Trends is **unavailable** (rate limited, API error, no data), the system generates **deterministic fake data** using the query's MD5 hash:

```python
def _generate_fallback_data(query: str) -> dict:
    h = hashlib.md5(query.lower().strip().encode("utf-8")).digest()
    num_states = 6 + (h[0] % 7)   # picks 6-12 states from hash bytes
    # ...generates scores between 20-98 from hash bytes
```

**Why deterministic?** Same query always produces the same fake data → cacheable and consistent. The map always shows *something* instead of being empty.

**Why fake?** Free Google Trends API is unreliable — gets rate-limited often. An empty map gives a bad user experience. Simulated data at least fills the map with a plausible-looking pattern.

---

### Signal 2: News Coverage (30% weight)

**File:** `heatmap.py` — `_get_news_coverage_signal()` (line 125-137)

**What it does:** Looks at the search result sources from the claim verification. If a source is a **regional news website**, it maps that domain to an Indian state.

**Domain → State mapping (lines 39-104):**

The code has a hardcoded dictionary mapping **50+ news domains** to their home states:

| Domain | State |
|--------|-------|
| `lokmat.com`, `maharashtratimes.com`, `mid-day.com` | Maharashtra |
| `divyabhaskar.co.in`, `gujaratsamachar.com` | Gujarat |
| `dinakaran.com`, `dinamalar.com`, `dailythanthi.com` | Tamil Nadu |
| `deccanherald.com`, `vijaykarnataka.com` | Karnataka |
| `mathrubhumi.com`, `manoramaonline.com` | Kerala |
| `amarujala.com`, `jagran.com` | Uttar Pradesh |
| `ndtv.com`, `hindustantimes.com` | Delhi (HQ) |
| `telegraphindia.com`, `anandabazar.com` | West Bengal |
| ... and more for each state |

**How it works:**
```python
def _get_news_coverage_signal(sources: list) -> dict:
    counts = {}
    for src in sources:
        domain = _get_bare_domain(src["url"])       # e.g. "lokmat.com"
        state = _DOMAIN_TO_STATE.get(domain)         # e.g. "maharashtra"
        if state:
            counts[state] = counts.get(state, 0) + 1  # count per state
    return _normalize(counts)                        # scale to 0-100
```

**Logic:** If 3 Maharashtra newspapers covered a claim → Maharashtra gets a high score. If only 1 Delhi paper covered it → Delhi gets a lower score.

**Normalization (`_normalize` function, line 115-122):**
```python
def _normalize(d: dict) -> dict:
    max_val = max(d.values())
    return {k: round(v / max_val * 100) for k, v in d.items()}
```
The state with highest count gets 100, others are scaled proportionally.

**Example:**
```
Sources found: lokmat.com, mid-day.com, ndtv.com, deccanherald.com
  → maharashtra: 2 hits, delhi: 1 hit, karnataka: 1 hit
  → Normalized: maharashtra: 100, delhi: 50, karnataka: 50
```

**Important:** This signal is **only available** when called from `/api/analyze-claim` (which has search results). When `/api/heatmap` is called standalone, `sources` list is empty and this signal is skipped.

---

### Signal 3: User IP Queries (20% weight)

**What it does:** Tracks **which Indian state** each user is searching from, and uses that as a signal.

**How IP tracking works (2 paths):**

#### Path A: Cache MISS — Async tracking (`api.py` line 640-654)

When a user submits a claim and it's a cache miss:
```python
async def _geolocate_and_save(request, claim_hash):
    ip = _get_client_ip(request)                    # get user's IP
    resp = await client.get(f"https://ipinfo.io/{ip}/json")  # lookup IP
    state = resp.json().get("region", "")            # e.g. "Maharashtra"
    save_regional_query(claim_hash, state)           # save to MongoDB
```

#### Path B: Cache HIT — Background thread tracking (`api.py` line 617-624)

Even on cache hits, we still track the user's location (in a background thread so it doesn't slow down the response):
```python
def _track_query_location(request, claim_hash):
    threading.Thread(
        target=_sync_geolocate_and_save,
        args=(ip, claim_hash),
        daemon=True
    ).start()
```

#### Getting the real IP behind proxies (`api.py` line 607-614):

```python
def _get_client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()  # first IP in chain = real user
    return request.client.host
```
On Render/Vercel, the user's real IP is in the `X-Forwarded-For` header because there's a reverse proxy in front.

#### MongoDB Storage (`db.py` line 241-258):

```python
def save_regional_query(claim_hash, state):
    col.update_one(
        {"claim_hash": claim_hash, "state": state.lower()},
        {
            "$inc": {"count": 1},              # increment count
            "$setOnInsert": {"created_at": now} # set date only on first insert
        },
        upsert=True,
    )
```

**Document in MongoDB:**
```json
{
    "claim_hash": "a3f8b2c1...",
    "state": "maharashtra",
    "count": 15,
    "created_at": "2026-03-30T10:00:00Z"
}
```

This means 15 users from Maharashtra searched for this specific claim.

#### Reading the data (`db.py` line 262-268):

```python
def get_regional_query_counts(claim_hash):
    return {doc["state"]: doc["count"] for doc in col.find({"claim_hash": claim_hash})}
# Returns: {"maharashtra": 15, "delhi": 8, "karnataka": 3}
```

#### TTL: 30 days (`db.py` line 234-236):
```python
create_index("created_at", expireAfterSeconds=30 * 24 * 3600)
```

Old query data auto-deletes after 30 days.

#### IP geolocation service:
Uses **ipinfo.io** — a free API that takes an IP address and returns the city, state, country:
```
GET https://ipinfo.io/103.21.58.193/json
→ {"region": "Maharashtra", "city": "Mumbai", "country": "IN"}
```

---

## How The 3 Signals Are Combined

**File:** `heatmap.py` — `get_combined_heatmap()` (line 227-280)

### Weights:
| Signal | Weight | Always available? |
|--------|--------|-------------------|
| Google Trends | 50% | Yes (with fallback) |
| News Coverage | 30% | Only when sources list is provided |
| User IP Queries | 20% | Only when claim_hash exists in MongoDB |

### Dynamic Weight Re-normalization (lines 263-267):

If a signal has no data, its weight is **redistributed**:

```python
w_gt = 0.5                                    # always 0.5
w_news = 0.3 if has_news else 0.0             # 0.3 or 0
w_user = 0.2 if has_user else 0.0             # 0.2 or 0
total_w = w_gt + w_news + w_user              # sum of active weights
```

**Scenarios:**

| Available Signals | Effective Weights |
|-------------------|-------------------|
| All 3 | GT=50%, News=30%, User=20% |
| GT + News only | GT=62.5%, News=37.5% (re-normalized from 0.5+0.3) |
| GT + User only | GT=71.4%, User=28.6% (re-normalized from 0.5+0.2) |
| GT only | Returns GT data directly (line 260-261) |

### Combining Formula (lines 271-278):

```python
all_states = set(gt_data) | set(news_data) | set(user_data)  # union of all states

for state in all_states:
    score = (
        gt_data.get(state, 0) * (w_gt / total_w)
        + news_data.get(state, 0) * (w_news / total_w)
        + user_data.get(state, 0) * (w_user / total_w)
    )
    if score > 0:
        combined[state] = round(score)
```

### Example Calculation:

Claim: "5G towers cause cancer"

| State | Google Trends (50%) | News Coverage (30%) | User Queries (20%) | **Combined** |
|-------|:---:|:---:|:---:|:---:|
| Maharashtra | 80 | 100 | 60 | 80×0.5 + 100×0.3 + 60×0.2 = **82** |
| Delhi | 60 | 50 | 40 | 60×0.5 + 50×0.3 + 40×0.2 = **53** |
| Karnataka | 40 | 0 | 30 | 40×0.5 + 0×0.3 + 30×0.2 = **26** |
| Kerala | 0 | 0 | 80 | 0×0.5 + 0×0.3 + 80×0.2 = **16** |

---

## Heatmap Caching

**File:** `db.py` lines 48-64, 281-303

### Collection: `heatmap_cache`

### TTL: 12 hours (line 62)
```python
create_index("created_at", expireAfterSeconds=12 * 3600)
```

### Cache Key: MD5 hash of lowercase query
```python
# api.py line 746
query_hash = hashlib.md5(query.lower().encode("utf-8")).hexdigest()
```

### Cache Check (`api.py` lines 746-750):
```python
cached = get_cached_heatmap(query_hash)
if cached is not None:
    return {"status": "success", "data": cached}   # instant return
```

### Cache Save (`api.py` line 757):
```python
set_cached_heatmap(query_hash, data)
```

### Document in MongoDB:
```json
{
    "query_hash": "e7d6c5b4a3f2...",
    "data": {"maharashtra": 82, "delhi": 53, "karnataka": 26},
    "created_at": "2026-04-01T12:00:00Z"
}
```

After 12 hours, MongoDB auto-deletes this → next request builds fresh heatmap.

---

## Heatmap Insight (AI Explanation)

**File:** `api.py` lines 800-876

### Endpoint: `POST /api/heatmap-insight`

This is a **separate endpoint** called by the frontend AFTER it gets the heatmap data. It asks AI to explain *why* certain states show higher interest.

### Input:
```json
{
    "query": "5G towers cause cancer",
    "heatmap_data": {"maharashtra": 82, "delhi": 53, "karnataka": 26}
}
```

### How it works:

1. Sort regions by score, take **top 5** (line 834-840):
```python
sorted_regions = sorted(heatmap_data.items(), key=lambda x: x[1], reverse=True)
top_regions = sorted_regions[:5]
data_summary = ", ".join([f"{region}: {score}" for region, score in top_regions])
```

2. Build prompt (lines 842-849):
```
"Given this heatmap data showing regional search interest (0-100 scale)
for the claim '5G towers cause cancer' across Indian states:
maharashtra: 82, delhi: 53, karnataka: 26

Provide a brief 1-2 sentence insight about the geographic spread pattern.
Focus on why certain regions may show higher interest.
Be specific and analytical. Do not use bullet points."
```

3. Send to Groq (lines 851-871):
```python
payload = {
    "model": "llama-3.3-70b-versatile",
    "temperature": 0.5,     # moderate creativity
    "max_tokens": 150,      # short response — just 1-2 sentences
}
```

4. Return insight:
```json
{
    "insight": "The claim shows highest interest in Maharashtra and Delhi, likely due to high urban population density and greater 5G tower deployment in these metro regions, leading to increased anxiety about health effects."
}
```

### Failure Handling:
- If `GROQ_API_KEY` not set → returns `{"insight": ""}` (line 831)
- If empty query or data → returns `{"insight": ""}` (line 823-824)
- If any error → returns `{"insight": ""}` (line 874-876)
- **Never crashes** — always returns something

---

## Where Heatmap is Built (2 Places)

### Place 1: Inside `/api/analyze-claim` (`api.py` lines 570-582)

When a user analyzes a claim, heatmap is built **automatically** as part of the response:

```python
heatmap = await loop.run_in_executor(
    None, partial(get_combined_heatmap, claim, claim_hash, sources)
)
# uses ALL 3 signals because sources list is available from web search
set_cached_heatmap(query_hash, heatmap)  # save for /api/heatmap to use later
top_regions = [r for r, _ in sorted_regions[:5] if _ > 0]
```

This heatmap is cached, so when the frontend later calls `/api/heatmap`, it gets a cache HIT.

### Place 2: Standalone `/api/heatmap` (`api.py` lines 709-759)

The frontend can also call this endpoint directly (e.g., user wants to see spread for a different query):

```python
data = get_combined_heatmap(query, claim_hash=query_hash)
# sources=None → News Coverage signal is EMPTY (only GT + user queries used)
```

Key difference: When called standalone, the **news coverage signal (30%) is missing** because there are no search results. Only Google Trends + user queries are used.

---

## Complete Feature Flow — User's Perspective

```
1. User types claim on website → hits "Analyze"
        ↓
2. Frontend calls POST /api/analyze-claim
        ↓
3. Backend runs CrewAI pipeline + builds heatmap (all 3 signals)
        ↓
4. Response includes top_regions: ["maharashtra", "delhi", "karnataka", ...]
        ↓
5. Frontend calls GET /api/heatmap?query=... → gets full state scores (cache HIT)
        ↓
6. Frontend renders the Leaflet.js map with colored regions
        ↓
7. Frontend calls POST /api/heatmap-insight with map data
        ↓
8. AI returns insight → displayed below the map
   "Higher interest in Maharashtra and Delhi likely due to..."
```

---

## Summary Table

| What | Detail |
|------|--------|
| **3 Signals** | Google Trends (50%) + News Coverage (30%) + User IP (20%) |
| **Google Trends Library** | `pytrends` — unofficial Python API for Google Trends |
| **News Domain Mapping** | 50+ Indian news domains → mapped to states |
| **IP Geolocation** | `ipinfo.io` free API → IP to Indian state |
| **AI Insight** | Groq LLaMA 3.3 70B explains geographic patterns |
| **Heatmap Cache** | MongoDB, 12-hour TTL |
| **User Query Cache** | MongoDB, 30-day TTL |
| **Fallback** | Deterministic simulated data from query hash (if Google Trends fails) |
| **Endpoints** | `GET /api/heatmap` + `POST /api/heatmap-insight` |
| **Map Frontend** | Leaflet.js + OpenStreetMap (free, no API key needed) |
