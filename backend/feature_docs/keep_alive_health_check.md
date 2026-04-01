# 💓 Keep-Alive & Health Check Feature — Complete Explanation

## The Problem This Feature Solves

### Render Free Tier = Server Spins Down

Our backend is hosted on **Render.com free tier**. Free tier has one major limitation:

> **If no HTTP request hits your server for 15 minutes, Render shuts it down (spins down).**

When the server is **spun down**:
- ❌ Server is OFF — no code is running
- ❌ APScheduler is dead — trending pipeline stops
- ❌ Telegram bot is disconnected — no responses
- ❌ Next user request takes **30-60 seconds** to respond (cold start)

### What Happens Without Keep-Alive:

```
12:00 PM — Last user visits the website
12:15 PM — No more requests → Render shuts down server 💀
12:15 PM to 8:00 PM — Server is DEAD for 8 hours
  └─ APScheduler is not running
  └─ Trending pipeline never fires
  └─ Telegram bot is offline
  └─ All caches expire (24h analysis, 12h heatmap)
8:00 PM — New user visits → Render wakes up server (30-60s cold start)
  └─ APScheduler restarts from zero
  └─ MongoDB has stale/no trending data
  └─ User sees empty trending page 😞
```

### The Real Pain Points:

| Problem | Impact |
|---------|--------|
| Server spins down after 15 min idle | Users wait 30-60s for first response |
| APScheduler resets on restart | Trending pipeline misses scheduled runs |
| Telegram bot disconnects | Users sending messages get no response |
| Caches expire while server is down | First requests after wake-up are slow |

---

## The Solution: 2 Features Working Together

### Feature 1: GitHub Actions Keep-Alive (Pinger)
**File:** `.github/workflows/keep_alive.yml`

Pings the server every 5 minutes so Render **never** considers it idle.

### Feature 2: Health Check Endpoint (Receiver)  
**File:** `server/api.py` lines 1044-1073

A lightweight endpoint that responds to the ping and reports server status.

### Feature 3: Startup Stale-Check (Safety Net)
**File:** `server/api.py` lines 82-108

If the server somehow still restarts, this ensures trending data is refreshed immediately.

---

## How It Works — Complete Flow

```
GitHub Actions (runs on GitHub's servers, FREE)
    │
    │  Every 5 minutes, 24/7
    │
    ▼
curl https://truthcrew-api-miniproject.onrender.com/health
    │
    │  HTTP GET request
    │
    ▼
Render sees incoming request → keeps server ALIVE ✅
    │
    ▼
/health endpoint responds with:
{
    "status": "ok",
    "timestamp": "2026-04-01T18:30:00Z",
    "last_trending_refresh": "2026-04-01T18:00:00Z"
}
    │
    ▼
GitHub Actions checks: HTTP 200? → ✅ Server is alive
                       Not 200?  → ❌ Logs failure (alert)
```

---

## File 1: GitHub Actions Workflow

**File:** `.github/workflows/keep_alive.yml`

```yaml
name: Keep Server Alive

on:
  schedule:
    - cron: "*/5 * * * *"    # every 5 minutes, 24/7
  workflow_dispatch:          # manual trigger from GitHub UI
```

### Cron Expression: `*/5 * * * *`

```
*/5  — every 5 minutes
*    — every hour
*    — every day
*    — every month
*    — every day of week

= Runs 288 times per day (24 × 12)
```

### `workflow_dispatch`:
Adding this means you can also trigger it **manually** from GitHub → Actions → "Keep Server Alive" → "Run workflow". Useful for testing.

### The Job (lines 11-34):

```yaml
jobs:
  ping:
    name: Ping Backend Health
    runs-on: ubuntu-latest       # runs on GitHub's free Linux servers
    timeout-minutes: 2           # kill if takes more than 2 min

    steps:
      - name: Ping /health endpoint
        run: |
          # 1. Send request, capture HTTP status code
          response=$(curl -s -o /tmp/health_response.json -w "%{http_code}" \
            --max-time 30 \
            https://truthcrew-api-miniproject.onrender.com/health)

          # 2. Print status for logs
          echo "HTTP Status: $response"
          cat /tmp/health_response.json

          # 3. Fail if not 200
          if [ "$response" != "200" ]; then
            echo "❌ Health check failed with status $response"
            exit 1
          fi

          echo "✅ Server is alive"
```

### What the curl command does:

| Flag | Purpose |
|------|---------|
| `-s` | Silent mode (no progress bar) |
| `-o /tmp/health_response.json` | Save response body to file |
| `-w "%{http_code}"` | Print HTTP status code (200, 500, etc.) |
| `--max-time 30` | Give up after 30 seconds |

### Why `exit 1` on failure?

When `exit 1` runs, GitHub marks the workflow run as **failed** ❌ in the Actions tab. You can see it in your GitHub repo → Actions → red ❌ means server was down.

### Cost: FREE

GitHub Actions gives **2,000 free minutes/month** for public repos and **500 minutes for private repos**. This workflow uses about **1 minute per run × 288 runs/day × 30 days = ~144 minutes/month** — well within free limits.

---

## File 2: Health Check Endpoint

**File:** `server/api.py` lines 1044-1073

```python
@app.get("/health")
async def health_check():
    last = get_last_refresh_time()           # from MongoDB pipeline_state collection
    last_str = last.isoformat() if last else "never"
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_trending_refresh": last_str,
    }
```

### Why not just return `"ok"`?

The extra fields help with **monitoring**:

| Field | Why useful |
|-------|-----------|
| `status: "ok"` | Confirms server is running |
| `timestamp` | Confirms server clock is correct |
| `last_trending_refresh` | Confirms trending pipeline is running. If this shows "12 hours ago", something is wrong |

### Response Example:

```json
{
    "status": "ok",
    "timestamp": "2026-04-01T18:30:00+00:00",
    "last_trending_refresh": "2026-04-01T18:00:00+00:00"
}
```

### Why is this a GET request?

- Lightweight — no request body needed
- Safe to call repeatedly — doesn't change anything
- Works with simple `curl` from GitHub Actions
- Standard convention for health checks

---

## File 3: Startup Stale-Check (Safety Net)

**File:** `server/api.py` lines 82-108

Even with keep-alive pinging, the server **might still restart** because:
- Render redeploys on new code push
- Render does maintenance restarts
- Server crashes due to memory/error

When server restarts, **APScheduler resets** — it forgets when it last ran the trending pipeline. This safety net catches that:

```python
def _startup_refresh_if_stale():
    last = get_last_refresh_time()       # read from MongoDB (survives restarts!)

    is_stale = (last is None) or (
        datetime.now(timezone.utc) - last > timedelta(hours=6)
    )

    if is_stale:
        run_refresh_pipeline()           # run immediately!
    else:
        # data is fresh, skip
```

### Key Insight: MongoDB Remembers, APScheduler Doesn't

```
APScheduler timer → lives in server memory → dies on restart
MongoDB timestamp → lives in cloud database → survives restart ✅
```

That's why `set_last_refresh_time()` saves to MongoDB after each pipeline run (`pipeline.py` line 107). On restart, the server reads this timestamp to know if data is stale.

### Why background thread? (line 106-107)

```python
threading.Thread(target=_startup_refresh_if_stale, daemon=True).start()
```

The pipeline takes ~45 seconds. If it ran on the main thread, the server wouldn't accept requests during startup. Background thread = server starts instantly, pipeline runs quietly behind.

### `daemon=True` — Why?

If the main server shuts down, daemon threads are **killed automatically**. Without this, a stuck pipeline thread could prevent clean shutdown.

---

## Before vs After — Complete Comparison

### ❌ BEFORE (without keep-alive):

```
Timeline of a typical day:

00:00  Server is alive, APScheduler running
02:00  Last user leaves → no requests
02:15  Render spins down server 💀
       └─ APScheduler dead
       └─ Telegram bot dead
       └─ 06:00 trending refresh: MISSED ❌
       └─ 12:00 trending refresh: MISSED ❌
18:00  User visits website
       └─ Render wakes server (45 second wait...)
       └─ Startup stale-check: "last refresh was 18h ago!"
       └─ Runs pipeline immediately (45 more seconds)
       └─ User finally sees content (~90 seconds total wait)
       └─ APScheduler restarts, next run at 00:00

Problems:
- User waited 90 seconds 😡
- 2 scheduled refreshes missed
- Telegram bot was dead for 16 hours
- Trending data was 18 hours stale
```

### ✅ AFTER (with keep-alive):

```
Timeline of a typical day:

00:00  Server is alive, APScheduler running
02:00  Last user leaves → no requests
02:05  GitHub Actions pings /health → server stays alive ✅
02:10  GitHub Actions pings /health → still alive ✅
  ... (every 5 minutes, forever)
06:00  APScheduler fires trending refresh → works perfectly ✅
12:00  APScheduler fires trending refresh → works perfectly ✅
18:00  User visits website → instant response (server was always running) ✅
       └─ Trending data is only 0-6 hours old
       └─ Telegram bot was running all day
       └─ All caches are warm

Problems: NONE 🎉
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│                GitHub Actions                │
│         (GitHub's servers, FREE)             │
│                                             │
│   Cron: every 5 minutes                     │
│   curl → /health                            │
└──────────────────┬──────────────────────────┘
                   │ HTTP GET every 5 min
                   ▼
┌─────────────────────────────────────────────┐
│              Render.com Server               │
│         (Free tier, spins down if idle)      │
│                                             │
│   /health endpoint ← receives ping          │
│   APScheduler ← stays alive because         │
│                  server never goes idle      │
│   Telegram Bot ← stays connected            │
│                                             │
│   Startup stale-check ← safety net          │
│   (if server restarts despite pings)         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│            MongoDB Atlas (Cloud)             │
│                                             │
│   pipeline_state.last_refreshed_at           │
│   (remembers last run, survives restarts)    │
└─────────────────────────────────────────────┘
```

---

## Summary

| What | Detail |
|------|--------|
| **Problem** | Render free tier spins down server after 15 min idle |
| **Solution** | GitHub Actions pings `/health` every 5 minutes |
| **Workflow File** | `.github/workflows/keep_alive.yml` |
| **Cron Schedule** | `*/5 * * * *` (every 5 min, 24/7) |
| **Endpoint** | `GET /health` — returns status + last refresh time |
| **Safety Net** | Startup stale-check reads MongoDB, refreshes if needed |
| **Cost** | FREE (GitHub Actions free minutes + Render free tier) |
| **What stays alive** | APScheduler (trending pipeline) + Telegram bot + warm caches |
| **Before** | Server dead for hours, users wait 90s, stale data |
| **After** | Server always alive, instant responses, fresh data |
