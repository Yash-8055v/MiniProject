"""
Since we now use dedicated fact-check site feeds, ALL articles are about
real misleading claims. The keyword filter is bypassed — every article passes.

We keep a light filter just to skip obviously unrelated articles
(e.g. "About Us" pages or empty-description articles).
"""

import logging

logger = logging.getLogger(__name__)

# Minimum description length to be worth sending to Groq
MIN_DESCRIPTION_LEN = 20

# Skip articles with these generic titles from feed meta-pages
SKIP_TITLES = {"about", "contact", "privacy", "subscribe", "home", "sitemap"}


def filter_suspicious(articles: list[dict]) -> list[dict]:
    """
    Light filter: skip articles with no real description or meta-page titles.
    Since we use fact-check feeds, virtually all articles pass.
    """
    valid = []
    for article in articles:
        title_lower = (article.get("title") or "").lower().strip()
        description = (article.get("description") or "").strip()

        # Skip navigation/meta pages
        if title_lower in SKIP_TITLES:
            continue

        # Skip articles with no description at all
        if len(description) < MIN_DESCRIPTION_LEN:
            # Still include if title is descriptive enough
            if len(title_lower) < 20:
                continue

        valid.append(article)

    logger.info(
        f"Pre-filter: {len(articles)} articles → {len(valid)} sent to Groq"
    )
    return valid
