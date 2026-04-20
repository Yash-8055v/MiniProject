"""
Phase 1: Scrape 60 labelled claims from AltNews, BoomLive, FactChecker.in
===========================================================================
Extracts claim_text, ground_truth_verdict, language, topic from fact-check articles.
Resumable: reads existing CSV and skips already-scraped claim_ids.

Usage:
    python -m evaluation.scraper              # full run (after checkpoint approval)
    python -m evaluation.scraper --test 10    # scrape only 10 for checkpoint review
"""

import os
import sys
import re
import csv
import json
import time
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from langdetect import detect as detect_lang
except ImportError:
    def detect_lang(text):
        return "en"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
DATASET_DIR.mkdir(exist_ok=True)
CSV_PATH = DATASET_DIR / "claims_60.csv"
JSON_PATH = DATASET_DIR / "claims_60.json"

# ── CSV columns ────────────────────────────────────────────────────────────
COLUMNS = [
    "claim_id", "claim_text", "source_url", "source_fact_checker",
    "published_date", "ground_truth_verdict", "verdict_reasoning",
    "language", "topic_category",
]

# ── Verdict mapping heuristics ─────────────────────────────────────────────
FALSE_KEYWORDS = [
    "false", "fake", "debunked", "no evidence", "fabricated", "hoax",
    "not true", "baseless", "unfounded", "incorrect", "untrue",
    "photoshopped", "morphed", "doctored", "old image", "old video",
    "unrelated", "out of context", "doesn't show", "does not show",
]
MISLEADING_KEYWORDS = [
    "misleading", "partly false", "missing context", "manipulated",
    "half true", "half-true", "partially true", "exaggerated",
    "distorted", "twisted", "selective", "cherry-picked",
]
TRUE_KEYWORDS = [
    "true", "correct", "verified", "confirmed", "accurate", "factual",
]
UNVERIFIABLE_KEYWORDS = [
    "unverified", "could not be confirmed", "unverifiable",
    "insufficient evidence", "inconclusive", "cannot be verified",
]

# ── Topic classification keywords ─────────────────────────────────────────
TOPIC_KEYWORDS = {
    "Politics": ["modi", "bjp", "congress", "election", "parliament", "government", "political", "minister", "party", "vote", "opposition", "rahul", "gandhi", "politician", "law", "bill"],
    "Health": ["covid", "vaccine", "health", "disease", "cure", "medical", "hospital", "doctor", "virus", "pandemic", "drug", "treatment", "cancer", "diabetes", "ayurvedic", "who", "medicine"],
    "Science": ["nasa", "isro", "space", "moon", "earth", "climate", "scientific", "research", "study", "discovery", "planet"],
    "Technology": ["5g", "whatsapp", "facebook", "twitter", "internet", "app", "phone", "upi", "digital", "ai", "artificial intelligence", "tech", "software"],
    "Religion": ["hindu", "muslim", "christian", "temple", "mosque", "church", "religious", "god", "prayer", "ram", "allah", "communal"],
    "Social": ["viral", "social media", "rumor", "rumour", "forwarded", "whatsapp forward", "caste", "crime", "police", "violence", "protest", "scam", "fraud"],
}


def classify_verdict(text: str) -> str:
    """Map fact-checker language to standard verdict."""
    text_lower = text.lower()
    # Check unverifiable first (most specific)
    if any(kw in text_lower for kw in UNVERIFIABLE_KEYWORDS):
        return "Unverifiable"
    if any(kw in text_lower for kw in MISLEADING_KEYWORDS):
        return "Misleading"
    if any(kw in text_lower for kw in FALSE_KEYWORDS):
        return "False"
    if any(kw in text_lower for kw in TRUE_KEYWORDS):
        return "True"
    # Default for fact-check sites: most articles debunk false claims
    return "False"


def classify_topic(text: str) -> str:
    """Simple keyword-based topic classification."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        scores[topic] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"


def detect_language(text: str) -> str:
    """Detect language using langdetect; return en/hi/mr."""
    try:
        lang = detect_lang(text)
        if lang == "hi":
            return "hi"
        if lang == "mr":
            return "mr"
        return "en"
    except Exception:
        return "en"


def fetch_page(url: str, retries: int = 3) -> Optional[str]:
    """Fetch a web page with retries."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                logger.warning(f"Failed to fetch {url}: {e}")
                return None


def load_existing_claims() -> set:
    """Load already-scraped claim_ids from CSV."""
    existing = set()
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["claim_id"])
    return existing


def save_claim_to_csv(claim: dict, write_header: bool = False):
    """Append a single claim to CSV."""
    mode = "w" if write_header else "a"
    with open(CSV_PATH, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(claim)


def save_all_to_json(claims: list):
    """Save all claims to JSON."""
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER: AltNews
# ═══════════════════════════════════════════════════════════════════════════

def scrape_altnews_article(url: str) -> Optional[dict]:
    """Extract claim and verdict from a single AltNews article page."""
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Get title
    title_tag = soup.find("h1", class_="post-title") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Get article body
    content_div = soup.find("div", class_="post-content") or soup.find("article")
    if not content_div:
        return None
    body_text = content_div.get_text(separator="\n", strip=True)

    # Extract claim — look for patterns like "Claim:", "Viral claim:", etc.
    claim_text = _extract_claim_from_body(body_text, title)
    if not claim_text:
        return None

    # Extract verdict reasoning from the article
    verdict_reasoning = _extract_verdict_reasoning(body_text)
    verdict = classify_verdict(title + " " + body_text[:2000])

    return {
        "claim_text": claim_text,
        "verdict": verdict,
        "verdict_reasoning": verdict_reasoning,
        "full_title": title,
        "body_snippet": body_text[:500],
    }


def scrape_altnews_feed(max_articles: int = 80) -> list:
    """Scrape claims from AltNews RSS + archive pages."""
    claims = []
    seen_urls = set()

    # Method 1: RSS feed
    logger.info("📰 Fetching AltNews RSS feed...")
    feed = feedparser.parse("https://www.altnews.in/feed/")
    rss_urls = []
    for entry in feed.entries[:30]:
        url = getattr(entry, "link", "")
        if url and url not in seen_urls:
            rss_urls.append(url)
            seen_urls.add(url)

    # Method 2: Archive pages (to get more historical articles)
    logger.info("📰 Fetching AltNews archive pages...")
    for page_num in range(1, 12):  # pages 1-11
        if len(rss_urls) + len(claims) >= max_articles:
            break
        archive_url = f"https://www.altnews.in/page/{page_num}/"
        html = fetch_page(archive_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "altnews.in/" in href and href not in seen_urls and "/page/" not in href:
                # Filter: only fact-check article URLs (skip category pages, etc.)
                if re.search(r"/\d{4}/\d{2}/", href):  # date pattern like /2024/03/
                    rss_urls.append(href)
                    seen_urls.add(href)
        time.sleep(1)

    logger.info(f"  Found {len(rss_urls)} AltNews article URLs")

    for i, url in enumerate(rss_urls[:max_articles]):
        logger.info(f"  [{i+1}/{min(len(rss_urls), max_articles)}] Scraping: {url[:80]}...")
        result = scrape_altnews_article(url)
        if result:
            claims.append({
                "source_url": url,
                "source_fact_checker": "AltNews",
                **result,
            })
            logger.info(f"    ✅ Claim: {result['claim_text'][:80]}...")
        else:
            logger.info(f"    ⏭️ Skipped (no extractable claim)")
        time.sleep(1.5)  # polite delay

    return claims


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER: BoomLive
# ═══════════════════════════════════════════════════════════════════════════

def scrape_boomlive_article(url: str) -> Optional[dict]:
    """Extract claim and verdict from a single BoomLive article page."""
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # BoomLive article content
    content_div = (
        soup.find("div", class_="story-element") or
        soup.find("div", class_="article-content") or
        soup.find("article") or
        soup.find("div", class_="post-content")
    )
    if not content_div:
        # Try getting all paragraphs
        paragraphs = soup.find_all("p")
        body_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
    else:
        body_text = content_div.get_text(separator="\n", strip=True)

    if not body_text or len(body_text) < 100:
        return None

    claim_text = _extract_claim_from_body(body_text, title)
    if not claim_text:
        return None

    verdict_reasoning = _extract_verdict_reasoning(body_text)
    verdict = classify_verdict(title + " " + body_text[:2000])

    return {
        "claim_text": claim_text,
        "verdict": verdict,
        "verdict_reasoning": verdict_reasoning,
        "full_title": title,
        "body_snippet": body_text[:500],
    }


def scrape_boomlive_feed(max_articles: int = 80) -> list:
    """Scrape claims from BoomLive."""
    claims = []
    seen_urls = set()

    # RSS feed
    logger.info("📰 Fetching BoomLive RSS feed...")
    feed = feedparser.parse("https://www.boomlive.in/feed")
    rss_urls = []
    for entry in feed.entries[:30]:
        url = getattr(entry, "link", "")
        if url and url not in seen_urls:
            rss_urls.append(url)
            seen_urls.add(url)

    # Archive pages
    logger.info("📰 Fetching BoomLive archive pages...")
    for section in ["fact-check", "fast-check"]:
        for page_num in range(1, 8):
            if len(rss_urls) >= max_articles:
                break
            archive_url = f"https://www.boomlive.in/{section}?page={page_num}"
            html = fetch_page(archive_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if not href.startswith("http"):
                    href = "https://www.boomlive.in" + href
                if "boomlive.in/" in href and href not in seen_urls:
                    if re.search(r"/fact-check/|/fast-check/", href):
                        rss_urls.append(href)
                        seen_urls.add(href)
            time.sleep(1)

    logger.info(f"  Found {len(rss_urls)} BoomLive article URLs")

    for i, url in enumerate(rss_urls[:max_articles]):
        logger.info(f"  [{i+1}/{min(len(rss_urls), max_articles)}] Scraping: {url[:80]}...")
        result = scrape_boomlive_article(url)
        if result:
            claims.append({
                "source_url": url,
                "source_fact_checker": "BoomLive",
                **result,
            })
            logger.info(f"    ✅ Claim: {result['claim_text'][:80]}...")
        else:
            logger.info(f"    ⏭️ Skipped")
        time.sleep(1.5)

    return claims


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER: FactChecker.in
# ═══════════════════════════════════════════════════════════════════════════

def scrape_factchecker_article(url: str) -> Optional[dict]:
    """Extract claim from FactChecker.in article."""
    html = fetch_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    content_div = soup.find("article") or soup.find("div", class_="entry-content")
    if not content_div:
        paragraphs = soup.find_all("p")
        body_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
    else:
        body_text = content_div.get_text(separator="\n", strip=True)

    if not body_text or len(body_text) < 100:
        return None

    claim_text = _extract_claim_from_body(body_text, title)
    if not claim_text:
        return None

    verdict_reasoning = _extract_verdict_reasoning(body_text)
    verdict = classify_verdict(title + " " + body_text[:2000])

    return {
        "claim_text": claim_text,
        "verdict": verdict,
        "verdict_reasoning": verdict_reasoning,
        "full_title": title,
        "body_snippet": body_text[:500],
    }


def scrape_factchecker_feed(max_articles: int = 50) -> list:
    """Scrape claims from FactChecker.in."""
    claims = []
    seen_urls = set()

    logger.info("📰 Fetching FactChecker.in RSS + archive...")
    feed = feedparser.parse("https://factchecker.in/feed/")
    rss_urls = []
    for entry in feed.entries[:20]:
        url = getattr(entry, "link", "")
        if url and url not in seen_urls:
            rss_urls.append(url)
            seen_urls.add(url)

    # Archive pages
    for page_num in range(1, 8):
        if len(rss_urls) >= max_articles:
            break
        archive_url = f"https://factchecker.in/page/{page_num}/"
        html = fetch_page(archive_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "factchecker.in/" in href and href not in seen_urls and "/page/" not in href:
                if re.search(r"fact-check|fake|claim|viral", href, re.IGNORECASE):
                    rss_urls.append(href)
                    seen_urls.add(href)
        time.sleep(1)

    logger.info(f"  Found {len(rss_urls)} FactChecker.in article URLs")

    for i, url in enumerate(rss_urls[:max_articles]):
        logger.info(f"  [{i+1}/{min(len(rss_urls), max_articles)}] Scraping: {url[:80]}...")
        result = scrape_factchecker_article(url)
        if result:
            claims.append({
                "source_url": url,
                "source_fact_checker": "FactChecker.in",
                **result,
            })
            logger.info(f"    ✅ Claim: {result['claim_text'][:80]}...")
        else:
            logger.info(f"    ⏭️ Skipped")
        time.sleep(1.5)

    return claims


# ═══════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _extract_claim_from_body(body: str, title: str) -> Optional[str]:
    """
    Extract the specific claim being fact-checked from article body.
    Tries multiple patterns common across Indian fact-check sites.
    """
    # Pattern 1: Explicit "Claim:" or "Viral Claim:" labels
    patterns = [
        r"(?:Viral\s+)?Claim\s*[:–—-]\s*(.+?)(?:\n|Fact|Verdict|Truth|Reality|Our\s+finding)",
        r"(?:The\s+)?Viral\s+(?:Message|Post|Claim)\s*[:–—-]\s*(.+?)(?:\n|Fact|Verdict)",
        r"What(?:'s|\s+is)\s+(?:the\s+)?claim\s*\??\s*[:–—-]?\s*(.+?)(?:\n|Fact|Verdict)",
        r"A\s+(?:viral\s+)?(?:message|claim|post)\s+(?:claims?|states?|says?)\s+(?:that\s+)?(.+?)(?:\.|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match:
            claim = match.group(1).strip()
            claim = re.sub(r"\s+", " ", claim)
            # Clean up: remove quotes, trim
            claim = claim.strip('"\'""''')
            if 20 < len(claim) < 500:
                return claim

    # Pattern 2: Look for quoted text in first few paragraphs (common in fact-checks)
    lines = body.split("\n")
    for line in lines[:15]:
        # Find text in quotes
        quote_match = re.search(r'["""](.{20,300})["""]', line)
        if quote_match:
            quoted = quote_match.group(1).strip()
            # Verify it looks like a claim, not a citation
            if not any(kw in quoted.lower() for kw in ["said", "told", "according", "source"]):
                return quoted

    # Pattern 3: Use the title as the claim (many fact-checks have the claim in the title)
    # Clean fact-check meta from title
    title_claim = re.sub(
        r"(?:Fact[- ]?Check|Viral|Debunked|False|Fake|Misleading|Claim)\s*[:–—-]?\s*",
        "", title, flags=re.IGNORECASE
    ).strip()
    if 15 < len(title_claim) < 400:
        return title_claim

    return None


def _extract_verdict_reasoning(body: str) -> str:
    """Extract 1-2 sentence reasoning from article body."""
    patterns = [
        r"(?:Fact|Verdict|Finding|Conclusion|Our\s+(?:research|finding))\s*[:–—-]\s*(.+?)(?:\n\n|\n[A-Z])",
        r"(?:This\s+claim\s+is|The\s+claim\s+is|We\s+found\s+that)\s+(.+?)(?:\.|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            reasoning = re.sub(r"\s+", " ", reasoning)
            # Limit to ~2 sentences
            sentences = re.split(r"(?<=[.!?])\s+", reasoning)
            return " ".join(sentences[:2])

    # Fallback: first 2 sentences of the article
    sentences = re.split(r"(?<=[.!?])\s+", body[:500])
    return " ".join(sentences[:2]) if sentences else ""


# ═══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def run_scraper(test_limit: Optional[int] = None):
    """
    Master scraper. Fetches from all three sources, assigns IDs, detects language.
    If test_limit is set, stops after that many total claims.
    """
    existing_ids = load_existing_claims()
    if existing_ids:
        logger.info(f"📋 Found {len(existing_ids)} already-scraped claims, will skip duplicates")

    all_claims = []
    counter = {"altnews": 0, "boomlive": 0, "factchecker": 0}

    # ── AltNews ────────────────────────────────────────────────────────────
    target_altnews = 10 if test_limit else 30
    logger.info(f"\n{'='*60}\n  SCRAPING ALTNEWS (target: {target_altnews})\n{'='*60}")
    altnews_raw = scrape_altnews_feed(max_articles=target_altnews)
    for item in altnews_raw:
        counter["altnews"] += 1
        cid = f"altnews_{counter['altnews']:03d}"
        if cid in existing_ids:
            continue
        claim = _build_claim_record(cid, item)
        all_claims.append(claim)
        if test_limit and len(all_claims) >= test_limit:
            break

    if test_limit and len(all_claims) >= test_limit:
        _finalize(all_claims, existing_ids)
        return all_claims

    # ── BoomLive ───────────────────────────────────────────────────────────
    target_boom = 5 if test_limit else 30
    logger.info(f"\n{'='*60}\n  SCRAPING BOOMLIVE (target: {target_boom})\n{'='*60}")
    boom_raw = scrape_boomlive_feed(max_articles=target_boom)
    for item in boom_raw:
        counter["boomlive"] += 1
        cid = f"boomlive_{counter['boomlive']:03d}"
        if cid in existing_ids:
            continue
        claim = _build_claim_record(cid, item)
        all_claims.append(claim)
        if test_limit and len(all_claims) >= test_limit:
            break

    if test_limit and len(all_claims) >= test_limit:
        _finalize(all_claims, existing_ids)
        return all_claims

    # ── FactChecker.in ─────────────────────────────────────────────────────
    target_fc = 3 if test_limit else 15
    logger.info(f"\n{'='*60}\n  SCRAPING FACTCHECKER.IN (target: {target_fc})\n{'='*60}")
    fc_raw = scrape_factchecker_feed(max_articles=target_fc)
    for item in fc_raw:
        counter["factchecker"] += 1
        cid = f"factchecker_{counter['factchecker']:03d}"
        if cid in existing_ids:
            continue
        claim = _build_claim_record(cid, item)
        all_claims.append(claim)

    _finalize(all_claims, existing_ids)
    return all_claims


def _build_claim_record(claim_id: str, raw: dict) -> dict:
    """Build a standardized claim record."""
    claim_text = raw["claim_text"]
    language = detect_language(claim_text)
    topic = classify_topic(claim_text + " " + raw.get("full_title", ""))

    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "source_url": raw["source_url"],
        "source_fact_checker": raw["source_fact_checker"],
        "published_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ground_truth_verdict": raw["verdict"],
        "verdict_reasoning": raw.get("verdict_reasoning", "")[:300],
        "language": language,
        "topic_category": topic,
    }


def _finalize(new_claims: list, existing_ids: set):
    """Write claims to CSV and JSON."""
    if not new_claims:
        logger.warning("⚠️ No new claims scraped!")
        return

    # Write CSV (header only if file doesn't exist)
    write_header = not CSV_PATH.exists() or len(existing_ids) == 0
    for i, claim in enumerate(new_claims):
        save_claim_to_csv(claim, write_header=(write_header and i == 0))

    # Read full CSV back for JSON export
    all_claims = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_claims.append(row)
    save_all_to_json(all_claims)

    logger.info(f"\n{'='*60}")
    logger.info(f"  SCRAPING COMPLETE")
    logger.info(f"  New claims: {len(new_claims)}")
    logger.info(f"  Total in CSV: {len(all_claims)}")
    logger.info(f"  Saved to: {CSV_PATH}")
    logger.info(f"  Saved to: {JSON_PATH}")
    logger.info(f"{'='*60}")

    # Print distribution
    verdicts = {}
    langs = {}
    sources = {}
    for c in all_claims:
        v = c["ground_truth_verdict"]
        l = c["language"]
        s = c["source_fact_checker"]
        verdicts[v] = verdicts.get(v, 0) + 1
        langs[l] = langs.get(l, 0) + 1
        sources[s] = sources.get(s, 0) + 1

    logger.info(f"\n  Verdict distribution: {verdicts}")
    logger.info(f"  Language distribution: {langs}")
    logger.info(f"  Source distribution: {sources}")


def print_sample(claims: list, n: int = 10):
    """Print first N claims for user review."""
    print(f"\n{'='*80}")
    print(f"  SAMPLE CLAIMS (showing {min(n, len(claims))} of {len(claims)})")
    print(f"{'='*80}")
    for i, c in enumerate(claims[:n]):
        print(f"\n  [{i+1}] {c['claim_id']}")
        print(f"      Claim:    {c['claim_text'][:100]}...")
        print(f"      Verdict:  {c['ground_truth_verdict']}")
        print(f"      Language: {c['language']}")
        print(f"      Topic:    {c['topic_category']}")
        print(f"      Source:   {c['source_fact_checker']}")
        print(f"      URL:      {c['source_url'][:80]}")
    print(f"\n{'='*80}")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_limit = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        test_limit = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 10

    claims = run_scraper(test_limit=test_limit)
    if claims:
        print_sample(claims, n=test_limit or 10)
