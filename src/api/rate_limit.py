"""Small in-memory sliding-window rate limiter, keyed by client IP.

Deliberately minimal: one process, one dict, no external store. Right-sized for a
public single-container demo (Hugging Face Spaces) where the goal is capping
worst-case OpenAI spend, not distributed fairness. The clock is injectable for
deterministic tests.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        """True if `key` has made fewer than `limit` calls in the window; records the call.

        A limit of 0 or less disables limiting (always allowed, nothing recorded).
        """
        if limit <= 0:
            return True
        now = self._clock()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            # Bound memory: drop idle keys opportunistically.
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}
            return True
