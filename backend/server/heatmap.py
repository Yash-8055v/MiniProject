"""
Google Trends heatmap fetcher.
Returns region-wise search interest for a given query within India.
Falls back to deterministic simulated data when Trends is unavailable.
"""

import hashlib
import logging
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

logger = logging.getLogger(__name__)

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

