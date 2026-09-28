import time
from threading import Lock

from src.config import settings


class RateLimiter:
    """Small in-process failure limiter with a lockout window.

    Suitable for a single-process deployment. With multiple workers, pair this
    with a reverse-proxy limit (or swap in a shared store such as Redis).
    """

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = Lock()

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key, 0.0)
            if until > now:
                return max(1, int(until - now) + 1)
            self._locked_until.pop(key, None)
            return 0

    def record_failure(self, key: str) -> int:
        if not settings.RATE_LIMIT_ENABLED:
            return 0
        now = time.monotonic()
        with self._lock:
            recent = [stamp for stamp in self._failures.get(key, []) if stamp >= now - settings.RATE_LIMIT_WINDOW_SECONDS]
            recent.append(now)
            if len(recent) >= settings.RATE_LIMIT_MAX_FAILURES:
                self._failures.pop(key, None)
                self._locked_until[key] = now + settings.RATE_LIMIT_LOCKOUT_SECONDS
                return settings.RATE_LIMIT_LOCKOUT_SECONDS
            self._failures[key] = recent
            return 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()


rate_limiter = RateLimiter()
