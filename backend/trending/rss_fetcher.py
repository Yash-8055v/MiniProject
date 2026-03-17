"""
RSS feed fetcher — uses DEDICATED FACT-CHECK site feeds.

Why fact-check sites?
  - Google News / BBC articles are about topics, Groq scores them as non-misleading
  - Fact-check sites (AltNews, BoomLive, Snopes) report on actual VIRAL FALSE CLAIMS
  - Every article contains a real misleading claim that Groq can extract and score high
"""

import feedparser
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Fact-check RSS feeds — every article is about a real false/misleading claim
RSS_FEEDS = [
    # India — top fact-checkers
    ("https://www.altnews.in/feed/", "india"),
    ("https://www.boomlive.in/feed", "india"),
    ("https://factchecker.in/feed/", "india"),

    # India regional / Hindi
    ("https://www.vishvasnews.com/feed/", "india"),

    # Global fact-checkers
    ("https://www.snopes.com/feed/", "global"),
    ("https://apnews.com/hub/ap-fact-check?format=rss", "global"),

    # India-Google News search specifically for fact-check results
    (
        "https://news.google.com/rss/search?q=fact+check+india+fake+viral&hl=en-IN&gl=IN&ceid=IN:en",
        "india",
    ),
    (
        "https://news.google.com/rss/search?q=fact+check+fake+claim+viral+whatsapp",
        "global",
    ),
]

MAX_ARTICLES_TOTAL = 30
MAX_PER_FEED = 6


def _parse_date(entry) -> datetime:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_articles() -> list[dict]:
    """
    Fetch articles from fact-check RSS feeds.
    Returns up to MAX_ARTICLES_TOTAL articles, capped at MAX_PER_FEED per source.
    """
    articles = []
    seen_urls: set[str] = set()

    for feed_url, region in RSS_FEEDS:
        if len(articles) >= MAX_ARTICLES_TOTAL:
            break

        try:
            feed = feedparser.parse(feed_url)
            count = 0

            for entry in feed.entries:
                if count >= MAX_PER_FEED or len(articles) >= MAX_ARTICLES_TOTAL:
                    break

                url = getattr(entry, "link", "")
                if not url or url in seen_urls:
                    continue

                title = _clean_text(getattr(entry, "title", ""))
                description = _clean_text(getattr(entry, "summary", ""))
                source_name = getattr(feed.feed, "title", region.title())
                published_at = _parse_date(entry)

                if not title:
                    continue

                seen_urls.add(url)
                articles.append({
                    "title": title,
                    "description": description[:600],
                    "url": url,
                    "source_name": source_name,
                    "published_at": published_at,
                    "region": region,
                })
                count += 1

            logger.info(f"  Fetched {count} articles from [{region}] {feed_url}")

        except Exception as e:
            logger.error(f"  Failed to fetch feed {feed_url}: {e}")
            continue

    logger.info(f"Total articles fetched: {len(articles)}")
    return articles
