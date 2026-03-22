"""
In-memory per-user rate limiter for the Telegram bot.
Allows max `max_calls` requests per user within a `period` (seconds) window.
"""

from collections import defaultdict
from time import time


class RateLimiter:
    def __init__(self, max_calls: int = 5, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self._calls: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Return True if the user may proceed, False if throttled."""
        now = time()
        calls = self._calls[user_id]
        # Evict timestamps outside the rolling window
        calls[:] = [t for t in calls if now - t < self.period]
        if len(calls) < self.max_calls:
            calls.append(now)
            return True
        return False

    def remaining_seconds(self, user_id: int) -> int:
        """Return how many seconds until the oldest request expires."""
        now = time()
        calls = self._calls[user_id]
        calls[:] = [t for t in calls if now - t < self.period]
        if not calls:
            return 0
        oldest = min(calls)
        return max(0, int(self.period - (now - oldest)))


# Module-level singleton: 5 analyses per minute per user
rate_limiter = RateLimiter(max_calls=5, period=60)
