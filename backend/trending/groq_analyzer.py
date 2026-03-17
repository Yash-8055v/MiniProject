"""
Groq LLM analyzer for misinformation detection.
Uses llama-3.3-70b-versatile via Groq's OpenAI-compatible REST API.
Analyzes only the headline + short description — no full article content.
"""

import os
import json
import logging
import re
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Store anything with misleading_score >= 50
# (Groq is conservative; lowering threshold ensures real news makes it in)
MIN_MISLEADING_SCORE = 50

PROMPT_TEMPLATE = """You are a misinformation analyst. The article below is from a FACT-CHECK website — it is debunking a viral false claim.

Your job is to:
1. Identify the FALSE or MISLEADING claim that the article is debunking
2. Extract it as a clear one-sentence claim
3. Score how misleading/false that underlying claim is (not the article — the CLAIM it debunks)

Region: {region}
Article headline: {title}
Article description: {description}

Almost every fact-check article contains a false claim — find it and score it.

Scoring guide for the claim being debunked:
- 85–100: Completely false, viral, potentially dangerous
- 65–84: Misleading, exaggerated, or unsupported claim
- 50–64: Partially false or missing important context

Return ONLY valid JSON (no markdown):
{{
  "misleading": true,
  "claim": "the specific false/misleading claim in one clear sentence",
  "explanation": "2-3 sentence explanation of why this claim is false or misleading",
  "category": "one of: Health, Politics, Science, Technology, Social Media, Environment, Finance, Other",
  "misleading_score": integer 50-100
}}"""


def analyze_article(article: dict) -> dict | None:
    """
    Send a single article headline+description to Groq for misinformation analysis.
    Returns structured result dict if misleading_score >= MIN_MISLEADING_SCORE,
    otherwise returns None.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not found in .env")

    def _safe(text: str) -> str:
        """Strip curly braces from text so .format() does not crash."""
        return (text or "").replace("{", "").replace("}", "")

    prompt = PROMPT_TEMPLATE.format(
        region=_safe(article.get("region", "global")),
        title=_safe(article.get("title", "")),
        description=_safe(article.get("description", "No description available")),
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 512,
    }

    try:
        response = requests.post(
            GROQ_API_URL, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown code blocks if present
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        result = json.loads(content)

    except requests.RequestException as e:
        logger.error(f"Groq API request failed: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse Groq response: {e}")
        return None

    score = int(result.get("misleading_score", 0))
    logger.info(
        f"  Groq scored {score}/100 — claim: {result.get('claim', '')[:60]}"
    )

    # Skip if score too low
    if score < MIN_MISLEADING_SCORE:
        logger.info(f"  → Skipped (score {score} < {MIN_MISLEADING_SCORE})")
        return None

    return {
        "claim": result.get("claim", article["title"]),
        "explanation": result.get("explanation", ""),
        "category": result.get("category", "Other"),
        "misleading_score": score,
        "source_name": article.get("source_name", "Unknown"),
        "source_url": article.get("url", ""),
        "region": article.get("region", "global"),
        "published_at": article.get("published_at"),
    }
