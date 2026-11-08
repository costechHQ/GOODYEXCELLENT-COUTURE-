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


# Password reset (FR-56): 10 attempts per IP per 15 minutes, requests and confirmations together.
# That is plenty for a real person and stops inbox flooding or link guessing.
reset_limiter = RateLimiter(10, 900)


# Admin sign-in: 20 attempts per IP per 10 minutes. The per-account lockout stops guessing one account;
# this stops one machine spraying many accounts, and stops unauthenticated requests being used to burn
# CPU, because every attempt (even for an unknown email) costs a deliberately slow password check.
login_limiter = RateLimiter(20, 600)


def _enforce(limiter: RateLimiter, request: Request, message: str) -> None:
    # The connection address, never a client-sent header such as X-Forwarded-For, which anyone can forge.
    key = request.client.host if request.client else "unknown"
    retry_after = limiter.hit(key)
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            headers={"Retry-After": str(retry_after)},
        )


async def limit_enquiries(request: Request) -> None:
    """Dependency for the public forms."""
    _enforce(enquiry_limiter, request, "Too many submissions. Please wait a few minutes and try again.")


async def limit_password_resets(request: Request) -> None:
    """Dependency for the password-reset routes."""
    _enforce(reset_limiter, request, "Too many attempts. Please wait a few minutes and try again.")


async def limit_logins(request: Request) -> None:
    """Dependency for the admin sign-in route."""
    _enforce(login_limiter, request, "Too many sign-in attempts. Please wait a few minutes and try again.")
