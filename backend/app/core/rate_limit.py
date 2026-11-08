import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

_SWEEP_ABOVE = 10_000  # tracked clients; above this, idle ones are dropped so memory stays bounded


class RateLimiter:
    """Sliding-window limiter held in memory (FR-37).

    Counts reset when the server restarts and are not shared between server processes.
    That is fine for one small server; use a shared store if the API is ever scaled out.
    """

    def __init__(self, max_requests: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.max_requests = max_requests
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> int | None:
        """Record an attempt. Returns None if allowed, or the seconds to wait if over the limit."""
        now = self._clock()
        if len(self._hits) > _SWEEP_ABOVE:
            self._sweep(now)
        times = self._hits.setdefault(key, deque())
        while times and now - times[0] >= self.window:
            times.popleft()
        if len(times) >= self.max_requests:
            return max(1, math.ceil(self.window - (now - times[0])))
        times.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()

    def _sweep(self, now: float) -> None:
        for key in [k for k, t in self._hits.items() if not t or now - t[-1] >= self.window]:
            del self._hits[key]


enquiry_limiter = RateLimiter(settings.rate_limit_max_requests, settings.rate_limit_window_seconds)


async def limit_enquiries(request: Request) -> None:
    """Dependency for the public forms. Uses the connection address, never a client-sent header."""
    key = request.client.host if request.client else "unknown"
    retry_after = enquiry_limiter.hit(key)
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please wait a few minutes and try again.",
            headers={"Retry-After": str(retry_after)},
        )
