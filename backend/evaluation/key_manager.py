"""
API Key Manager with automatic rotation on rate limits.
Cycles through multiple Groq and SerpAPI keys.
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

# ── Groq API Keys (rotate on 429/rate limit) ──────────────────────────────
GROQ_KEYS = [
    "YOUR_GROQ_KEY_1",
    "YOUR_GROQ_KEY_2",
    "YOUR_GROQ_KEY_3",
]

# ── SerpAPI Keys (rotate on limit exhaustion) ──────────────────────────────
SERP_KEYS = [
    "YOUR_SERPAPI_KEY_1",
    "YOUR_SERPAPI_KEY_2",
]

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqKeyManager:
    """Manages multiple Groq API keys with automatic rotation."""

    def __init__(self):
        self.keys = list(GROQ_KEYS)
        self.current_index = 0
        self.call_count = 0

    @property
    def current_key(self):
        return self.keys[self.current_index]

    def rotate(self):
        """Switch to next key."""
        old_idx = self.current_index
        self.current_index = (self.current_index + 1) % len(self.keys)
        logger.info(f"🔄 Groq key rotated: key_{old_idx} → key_{self.current_index}")

    def call(self, model: str, messages: list, temperature: float = 0.1,
             max_tokens: int = 50, max_retries: int = 5) -> str:
        """
        Make a Groq API call with automatic key rotation and retry.
        Returns the response text content.
        """
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.current_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=30,
                )

                if resp.status_code == 429:
                    # Rate limited — rotate key
                    logger.warning(f"⚠️ Groq 429 rate limit on key_{self.current_index}, rotating...")
                    self.rotate()
                    wait = min(2 ** attempt, 30)
                    logger.info(f"  Waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                self.call_count += 1
                content = resp.json()["choices"][0]["message"]["content"].strip()
                return content

            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Groq timeout on attempt {attempt+1}, retrying...")
                time.sleep(3)
                continue
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Groq error: {e}, rotating key and retrying...")
                    self.rotate()
                    time.sleep(2)
                    continue
                raise

        raise RuntimeError(f"Groq API failed after {max_retries} retries across all keys")


class SerpKeyManager:
    """Manages multiple SerpAPI keys with automatic rotation."""

    def __init__(self):
        self.keys = list(SERP_KEYS)
        self.current_index = 0
        self.call_counts = {i: 0 for i in range(len(self.keys))}

    @property
    def current_key(self):
        return self.keys[self.current_index]

    def rotate(self):
        """Switch to next key."""
        old_idx = self.current_index
        self.current_index = (self.current_index + 1) % len(self.keys)
        logger.info(f"🔄 SerpAPI key rotated: key_{old_idx} → key_{self.current_index}")

    def search(self, query: str, num_results: int = 6) -> list:
        """Search with automatic key rotation on failure."""
        for attempt in range(len(self.keys) * 2):
            try:
                resp = requests.get(
                    "https://serpapi.com/search",
                    params={
                        "api_key": self.current_key,
                        "engine": "google",
                        "q": query,
                        "num": num_results,
                    },
                    timeout=25,
                )

                if resp.status_code == 429 or "rate" in resp.text.lower():
                    logger.warning(f"⚠️ SerpAPI rate limit on key_{self.current_index}, rotating...")
                    self.rotate()
                    time.sleep(5)
                    continue

                resp.raise_for_status()
                self.call_counts[self.current_index] += 1
                data = resp.json()
                return data.get("organic_results", [])

            except Exception as e:
                logger.warning(f"⚠️ SerpAPI error: {e}, rotating...")
                self.rotate()
                time.sleep(3)
                continue

        raise RuntimeError("SerpAPI failed across all keys")


# ── Singleton instances ────────────────────────────────────────────────────
groq_manager = GroqKeyManager()
serp_manager = SerpKeyManager()
