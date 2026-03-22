"""
Pipeline orchestrator for the trending misinformation refresh job.
Runs: fetch RSS → filter → Groq analysis → MongoDB upsert.
Called by APScheduler every 24 hours and by the manual /api/trending/refresh endpoint.
"""

import logging
import time
import traceback
from datetime import datetime, timezone

from trending.rss_fetcher import fetch_articles
from trending.filter import filter_suspicious
from trending.groq_analyzer import analyze_article
from database.db import upsert_claim, set_last_refresh_time

logger = logging.getLogger(__name__)

# Limit how many articles we actually send to Groq per refresh
MAX_GROQ_CALLS = 10

# Seconds to wait between Groq API calls (avoid rate limiting on free tier)
GROQ_DELAY_SECONDS = 3


def run_refresh_pipeline() -> dict:
    """
    Execute the full misinformation detection pipeline.
    Returns a summary dict with counts for monitoring.
    """
    started_at = datetime.now(timezone.utc)
    logger.info(f"Starting trending refresh pipeline at {started_at.isoformat()}")

    # Step 1: Fetch RSS articles
    articles = fetch_articles()
    logger.info(f"Step 1: Fetched {len(articles)} articles from RSS feeds")

    # Step 2: Filter
    suspicious = filter_suspicious(articles)
    logger.info(f"Step 2: Filtered to {len(suspicious)} articles")

    # Limit to MAX_GROQ_CALLS to stay within free tier
    to_analyze = suspicious[:MAX_GROQ_CALLS]
    logger.info(f"Step 3: Will analyze {len(to_analyze)} articles (max {MAX_GROQ_CALLS})")

    # Step 3: Groq analysis
    stored_count = 0
    skipped_count = 0
    error_count = 0
    error_messages = []

    for i, article in enumerate(to_analyze):
        title_short = article.get("title", "")[:60]
        logger.info(f"  [{i+1}/{len(to_analyze)}] Analyzing: {title_short}...")

        try:
            result = analyze_article(article)

            if result is None:
                logger.info(f"    -> Skipped (scored below threshold)")
                skipped_count += 1
            else:
                upsert_claim(result)
                stored_count += 1
                logger.info(
                    f"    -> Stored! score={result['misleading_score']}, "
                    f"category={result['category']}"
                )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"    -> ERROR: {error_msg}")
            logger.error(traceback.format_exc())
            error_messages.append(error_msg)
            error_count += 1

        # Rate-limit delay between Groq calls
        if i < len(to_analyze) - 1:
            time.sleep(GROQ_DELAY_SECONDS)

    finished_at = datetime.now(timezone.utc)
    duration_s = (finished_at - started_at).total_seconds()

    summary = {
        "status": "success",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration_s, 1),
        "articles_fetched": len(articles),
        "articles_filtered": len(suspicious),
        "groq_calls_made": len(to_analyze) - error_count,
        "claims_stored": stored_count,
        "claims_skipped": skipped_count,
        "errors": error_count,
    }

    # Include first 3 error messages for debugging
    if error_messages:
        summary["error_details"] = error_messages[:3]

    logger.info(
        f"Pipeline complete in {duration_s:.1f}s - "
        f"{stored_count} stored, {skipped_count} skipped, {error_count} errors"
    )

    # Persist refresh timestamp in MongoDB so startup check survives restarts
    set_last_refresh_time()
    logger.info("✅ Last refresh time saved to MongoDB")

    return summary
