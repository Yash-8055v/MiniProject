"""
Layered Credibility Scoring Module
===================================
Calculates a transparent, multi-layer credibility score (0-100) from
web search results and the original claim text.

Weights (sum = 1.00):
  Layer 1 — Source Tier Quality    35%
  Layer 2 — Source Count           20%
  Layer 3 — Evidence Alignment     25%
  Layer 4 — Claim Verifiability    10%
  Layer 5 — Cross Agreement        10%
"""

import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Domain → Tier mapping
# Must stay in sync with GOVERNMENT_SOURCES / NATIONAL_NEWS / REGIONAL_NEWS
# defined in backend/tools/web_search.py
# ---------------------------------------------------------------------------
DOMAIN_TIERS: dict[str, str] = {
    # Government / Official (100)
    "pib.gov.in": "government",
    "mygov.in": "government",
    "india.gov.in": "government",
    # International trusted (90)
    "bbc.com": "international",
    "reuters.com": "international",
    "apnews.com": "international",
    "aljazeera.com": "international",
    # National Indian news (75)
    "thehindu.com": "national",
    "indianexpress.com": "national",
    "ndtv.com": "national",
    "timesofindia.indiatimes.com": "national",
    "hindustantimes.com": "national",
    "theprint.in": "national",
    "thewire.in": "national",
    # Regional news (55)
    "lokmat.com": "regional",
    "maharashtratimes.com": "regional",
    "mid-day.com": "regional",
    "punemirror.com": "regional",
}

TIER_SCORES: dict[str, float] = {
    "government": 100.0,
    "international": 90.0,
    "national": 75.0,
    "regional": 55.0,
    "unknown": 20.0,
}

# Date/time keywords for claim verifiability check
_DATE_KEYWORDS = [
    "2023", "2024", "2025", "2026",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "today", "yesterday", "this year", "last year",
]


def _get_tier(url: str) -> str:
    """Return tier name for a URL's bare domain."""
    try:
        host = urlparse(url).netloc.lower()
        # Strip www. prefix
        if host.startswith("www."):
            host = host[4:]
        return DOMAIN_TIERS.get(host, "unknown")
    except Exception:
        return "unknown"


def layer1_source_tier(search_results: list) -> float:
    """
    Average tier score across all sources.
    Empty list → 0.0 (no sources = no confidence).
    """
    if not search_results:
        return 0.0
    scores = [TIER_SCORES[_get_tier(r.get("url", ""))] for r in search_results]
    return sum(scores) / len(scores)


def layer2_source_count(search_results: list) -> float:
    """
    Linear normalization: 0 sources → 0, 8 sources → 100.
    8 matches num_results passed to search_with_priority in crew.py.
    """
    MAX_SOURCES = 8
    return min(100.0, len(search_results) / MAX_SOURCES * 100.0)


def layer3_evidence_alignment(search_results: list) -> float:
    """
    Percentage of sources from known trusted domains (not "unknown").
    If all results are from unknown sources, score is 0.
    """
    if not search_results:
        return 0.0
    trusted_count = sum(
        1 for r in search_results if _get_tier(r.get("url", "")) != "unknown"
    )
    return trusted_count / len(search_results) * 100.0


def layer4_claim_verifiability(claim: str) -> float:
    """
    Heuristic: specific, fact-checkable claims score higher.
    Base score = 30. Each specificity element adds points (cap 100).

    Elements checked:
      +20  contains any number/digit
      +20  has ≥2 capitalised words (proper nouns / names)
      +15  contains a date keyword
      +15  contains a percentage (e.g. 8.2%)
    """
    score = 30.0

    if re.search(r"\d+", claim):
        score += 20.0

    words = claim.split()
    proper_nouns = [w for w in words if w and w[0].isupper() and len(w) > 2]
    if len(proper_nouns) >= 2:
        score += 20.0

    if any(kw in claim.lower() for kw in _DATE_KEYWORDS):
        score += 15.0

    if re.search(r"\d+\.?\d*\s*%", claim):
        score += 15.0

    return min(100.0, score)


def layer5_cross_agreement(search_results: list) -> float:
    """
    Count-based proxy for cross-validation.
    The presence of multiple independent trusted sources is a strong
    agreement signal without requiring NLP content analysis.

      0 trusted → 0
      1 trusted → 40  (single source, no cross-validation)
      2 trusted → 70
      3+        → 100
    """
    trusted_count = sum(
        1 for r in search_results if _get_tier(r.get("url", "")) != "unknown"
    )
    if trusted_count == 0:
        return 0.0
    if trusted_count == 1:
        return 40.0
    if trusted_count == 2:
        return 70.0
    return 100.0


def calculate_credibility_score(search_results: list, claim: str) -> dict:
    """
    Compute the final weighted credibility score and per-layer breakdown.

    Args:
        search_results: Raw list from search_with_priority() — includes 'url', 'title',
                        'snippet', 'trusted' keys. Must NOT be the filtered 'sources'
                        list (which drops snippets).
        claim:          The English version of the claim used for search.

    Returns:
        {
            "final_score": int (0-100),
            "layers": {
                "source_tier":         {"score": int, "weight": 35},
                "source_count":        {"score": int, "weight": 20},
                "evidence_alignment":  {"score": int, "weight": 25},
                "claim_verifiability": {"score": int, "weight": 10},
                "cross_agreement":     {"score": int, "weight": 10},
            }
        }
    """
    l1 = layer1_source_tier(search_results)
    l2 = layer2_source_count(search_results)
    l3 = layer3_evidence_alignment(search_results)
    l4 = layer4_claim_verifiability(claim)
    l5 = layer5_cross_agreement(search_results)

    # Weights: 0.35 + 0.20 + 0.25 + 0.10 + 0.10 = 1.00
    final = l1 * 0.35 + l2 * 0.20 + l3 * 0.25 + l4 * 0.10 + l5 * 0.10

    return {
        "final_score": round(final),
        "layers": {
            "source_tier":         {"score": round(l1), "weight": 35},
            "source_count":        {"score": round(l2), "weight": 20},
            "evidence_alignment":  {"score": round(l3), "weight": 25},
            "claim_verifiability": {"score": round(l4), "weight": 10},
            "cross_agreement":     {"score": round(l5), "weight": 10},
        },
    }
