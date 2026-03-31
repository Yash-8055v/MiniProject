import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERP_API_KEY = os.getenv("SEARCH_API_KEY")

# ---------------------------------------------------------------------------
# Trusted source domains (searched with priority)
# ---------------------------------------------------------------------------

GOVERNMENT_SOURCES = [
    "pib.gov.in",
    "mygov.in",
    "india.gov.in",
    "bbc.com",          # BBC News (global trusted)
]

NATIONAL_NEWS = [
    "thehindu.com",
    "indianexpress.com",
    "ndtv.com",
    "timesofindia.indiatimes.com",
    "hindustantimes.com",
]

REGIONAL_NEWS = [
    "lokmat.com",
    "maharashtratimes.com",
    "mid-day.com",
    "punemirror.com",
]

# Full flat list for fast lookup
TRUSTED_DOMAINS = set(GOVERNMENT_SOURCES + NATIONAL_NEWS + REGIONAL_NEWS)

# SerpAPI site: query string built from trusted domains
_SITE_QUERY = " OR ".join(f"site:{d}" for d in (GOVERNMENT_SOURCES + NATIONAL_NEWS))


def _call_serpapi(params: dict) -> list[dict]:
    """Low-level SerpAPI call. Returns parsed organic results."""
    if not SERP_API_KEY:
        raise ValueError("SEARCH_API_KEY not found in .env")

    response = requests.get(
        "https://serpapi.com/search", params=params, timeout=25
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("organic_results", []):
        link = item.get("link", "")
        domain = _extract_domain(link)
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "source": item.get("source") or domain or link,
            "url": link,
            "trusted": domain in TRUSTED_DOMAINS,
        })
    return results


def _extract_domain(url: str) -> str:
    """Return bare domain from a URL, e.g. 'https://ndtv.com/foo' → 'ndtv.com'."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        # Strip leading www.
        return host.lstrip("www.")
    except Exception:
        return ""


def search_with_priority(query: str, num_results: int = 6) -> list[dict]:
    """
    Search strategy:
    1. Try a site:-restricted query on trusted government + national news domains.
    2. If fewer than 2 results, fall back to an open web search.
    3. Merge: trusted results first, then open-web results (deduplicated by URL).
    Returns up to `num_results` items, each with keys:
        title, snippet, source, url, trusted (bool)
    """
    base_params = {
        "api_key": SERP_API_KEY,
        "engine": "google",
        "num": num_results,
    }

    # --- Step 1: trusted-domain restricted search ---
    trusted_results = _call_serpapi({
        **base_params,
        "q": f"{query} ({_SITE_QUERY})",
    })

    # --- Step 2: fallback open search ---
    open_results = _call_serpapi({
        **base_params,
        "q": query,
    })

    # --- Step 3: merge, trusted first, deduplicate by URL ---
    seen_urls: set[str] = set()
    merged: list[dict] = []

    for item in trusted_results + open_results:
        url = item.get("url", "")
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(item)
        if len(merged) >= num_results:
            break

    return merged


# Keep old simple function for any direct callers
def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Thin wrapper — delegates to search_with_priority."""
    return search_with_priority(query, num_results)
