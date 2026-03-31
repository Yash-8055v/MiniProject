"""
Heatmap data for regional spread of a claim across Indian states.

Combines three signals:
  1. Google Trends interest-by-region  (weight 50%)
  2. Regional news source coverage     (weight 30%)
  3. IP-geolocated user queries        (weight 20%)

Falls back gracefully when individual signals are unavailable.
"""

import hashlib
import logging
import urllib3

# ── Compatibility shim ─────────────────────────────────────────────────────
# pytrends passes `method_whitelist` to urllib3.Retry, which was renamed to
# `allowed_methods` in urllib3 ≥ 1.26. Patch it in before TrendReq is used.
_original_retry_init = urllib3.util.retry.Retry.__init__

def _patched_retry_init(self, *args, **kwargs):
    if "method_whitelist" in kwargs and "allowed_methods" not in kwargs:
        kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
    _original_retry_init(self, *args, **kwargs)

urllib3.util.retry.Retry.__init__ = _patched_retry_init
# ───────────────────────────────────────────────────────────────────────────

from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal 2 — regional news source → state mapping
# ---------------------------------------------------------------------------
_DOMAIN_TO_STATE: dict[str, str] = {
    # Maharashtra
    "lokmat.com": "maharashtra",
    "maharashtratimes.com": "maharashtra",
    "mid-day.com": "maharashtra",
    "punemirror.com": "maharashtra",
    "loksatta.com": "maharashtra",
    "esakal.com": "maharashtra",
    # Gujarat
    "divyabhaskar.co.in": "gujarat",
    "gujaratsamachar.com": "gujarat",
    "sandesh.com": "gujarat",
    "gujaratmirror.in": "gujarat",
    # Tamil Nadu
    "dinakaran.com": "tamil nadu",
    "dinamalar.com": "tamil nadu",
    "dailythanthi.com": "tamil nadu",
    "vikatan.com": "tamil nadu",
    # Karnataka
    "deccanherald.com": "karnataka",
    "vijaykarnataka.com": "karnataka",
    "prajavani.net": "karnataka",
    "kannadadprabha.com": "karnataka",
    # Telangana / Andhra Pradesh
    "thehansindia.com": "telangana",
    "telanganatoday.com": "telangana",
    "eenadu.net": "andhra pradesh",
    "andhrajyothy.com": "andhra pradesh",
    # Kerala
    "mathrubhumi.com": "kerala",
    "manoramaonline.com": "kerala",
    "keralakaumudi.com": "kerala",
    "asianetnews.com": "kerala",
    # Uttar Pradesh
    "amarujala.com": "uttar pradesh",
    "jagran.com": "uttar pradesh",
    "livehindustan.com": "uttar pradesh",
    # Madhya Pradesh
    "bhaskar.com": "madhya pradesh",
    "naidunia.com": "madhya pradesh",
    # Punjab / Haryana
    "punjabkesari.in": "punjab",
    "tribuneindia.com": "punjab",
    "ajitjalandhar.com": "punjab",
    # Rajasthan
    "patrika.com": "rajasthan",
    "rajasthanpatrika.com": "rajasthan",
    # West Bengal
    "telegraphindia.com": "west bengal",
    "anandabazar.com": "west bengal",
    "sangbadpratidin.in": "west bengal",
    # Bihar / Jharkhand
    "prabhatkhabar.com": "jharkhand",
    # Odisha
    "sambad.com": "odisha",
    "dharitri.com": "odisha",
    # Assam / Northeast
    "sentinelassam.com": "assam",
    "assamtribune.com": "assam",
    # Delhi-headquartered national papers (counted as delhi)
    "hindustantimes.com": "delhi",
    "ndtv.com": "delhi",
    "indianexpress.com": "delhi",
    "timesofindia.indiatimes.com": "delhi",
    "thehindu.com": "tamil nadu",   # HQ Chennai
}


def _get_bare_domain(url: str) -> str:
    """Extract bare domain (no www.) from a URL string."""
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _normalize(d: dict) -> dict:
    """Scale all values in d to 0-100. Empty dict → empty dict."""
    if not d:
        return {}
    max_val = max(d.values())
    if max_val == 0:
        return {k: 0 for k in d}
    return {k: round(v / max_val * 100) for k, v in d.items()}


def _get_news_coverage_signal(sources: list) -> dict:
    """
    Map source URLs to Indian states and count coverage per state.
    Returns a normalized 0-100 dict. Unknown domains are ignored.
    """
    counts: dict[str, int] = {}
    for src in sources:
        url = src.get("url", "")
        domain = _get_bare_domain(url)
        state = _DOMAIN_TO_STATE.get(domain)
        if state:
            counts[state] = counts.get(state, 0) + 1
    return _normalize(counts)


# Reusable pytrends session
_pytrends = TrendReq(hl="en-IN", tz=330, timeout=(10, 25), retries=2, backoff_factor=1)


# Major Indian states for fallback generation
_STATES = [
    "delhi", "maharashtra", "west bengal", "karnataka", "kerala",
    "tamil nadu", "telangana", "andhra pradesh", "gujarat", "rajasthan",
    "uttar pradesh", "madhya pradesh", "bihar", "punjab", "haryana",
    "odisha", "assam", "jharkhand", "chhattisgarh", "uttarakhand",
]


def _generate_fallback_data(query: str) -> dict:
    """
    Generate deterministic simulated heatmap data based on query hash.
    Each query always produces the same spread pattern (cacheable).
    Picks 6-12 states with scores derived from the hash digest.
    """
    h = hashlib.md5(query.lower().strip().encode("utf-8")).digest()

    # Use hash bytes to pick how many states and which ones
    num_states = 6 + (h[0] % 7)   # 6 to 12 states
    result = {}

    for i in range(num_states):
        idx = h[i % len(h)] % len(_STATES)
        state = _STATES[idx]
        if state not in result:
            # Score between 20 and 98, derived from hash bytes
            score = 20 + (h[(i + 1) % len(h)] * h[(i + 2) % len(h)]) % 79
            result[state] = min(score, 98)

    # Ensure at least one high-scoring entry
    top_idx = h[3] % len(_STATES)
    result[_STATES[top_idx]] = 75 + (h[4] % 24)

    return result


def get_google_trends_heatmap(query: str) -> dict:
    """
    Fetch Google Trends interest-by-region for India.

    Returns a dict mapping lowercase state names to 0-100 scores.
    Only states with score > 0 are included.
    Falls back to simulated data if Trends is unavailable.
    """
    # Trim query to first 5 meaningful words for better Trends matching
    clean_query = " ".join(query.strip().split()[:5])
    if not clean_query:
        return {}

    logger.info(f"Fetching Google Trends for: '{clean_query}'")
    try:
        _pytrends.build_payload(
            kw_list=[clean_query],
            timeframe="now 7-d",
            geo="IN",
        )
        df = _pytrends.interest_by_region(
            resolution="REGION", inc_low_vol=True, inc_geo_code=False
        )

        if df is not None and not df.empty:
            df = df.reset_index()  # columns: ['geoName', clean_query]
            result = {}
            for _, row in df.iterrows():
                state: str = row["geoName"]
                score = row[clean_query]
                if score > 0:
                    result[state.lower()] = int(score)

            if result:
                return result

        logger.warning(f"No Google Trends data for '{clean_query}' — using simulated data")

    except TooManyRequestsError:
        logger.error("Google Trends rate-limit exceeded (429) — using simulated data")
    except Exception as e:
        logger.error(f"Google Trends fetch error: {e} — using simulated data")

    # Fallback: deterministic simulated data so the map always shows something
    return _generate_fallback_data(clean_query)


def get_combined_heatmap(
    query: str,
    claim_hash: str | None = None,
    sources: list | None = None,
) -> dict:
    """
    Combine three signals into a single 0-100 regional spread map.

    Weights (re-normalized if a signal has no data):
      - Google Trends      50 %
      - News coverage      30 %  (requires sources list)
      - User query geo     20 %  (requires claim_hash in MongoDB)
    """
    # Signal 1: Google Trends (always present — falls back to simulated data)
    gt_data = get_google_trends_heatmap(query)

    # Signal 2: regional news coverage
    news_data = _get_news_coverage_signal(sources or [])

    # Signal 3: IP-geolocated user queries
    user_data: dict = {}
    if claim_hash:
        try:
            from database.db import get_regional_query_counts
            counts = get_regional_query_counts(claim_hash)
            user_data = _normalize(counts)
        except Exception:
            pass

    has_news = bool(news_data)
    has_user = bool(user_data)

    # If no enrichment signals are available, return raw GT data unchanged
    if not has_news and not has_user:
        return gt_data

    # Compute effective weights (re-normalize so they always sum to 1.0)
    w_gt = 0.5
    w_news = 0.3 if has_news else 0.0
    w_user = 0.2 if has_user else 0.0
    total_w = w_gt + w_news + w_user

    all_states = set(gt_data) | set(news_data) | set(user_data)
    combined: dict[str, int] = {}
    for state in all_states:
        score = (
            gt_data.get(state, 0) * (w_gt / total_w)
            + news_data.get(state, 0) * (w_news / total_w)
            + user_data.get(state, 0) * (w_user / total_w)
        )
        if score > 0:
            combined[state] = round(score)

    return combined

