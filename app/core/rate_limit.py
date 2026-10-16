"""IP tabanlı sliding window rate limiter middleware."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


@dataclass
class _Bucket:
    timestamps: list[float] = field(default_factory=list)


class RateLimiter:
    def __init__(self, max_requests: int = 60, window: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = max(window * 2, 120)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, now: float) -> None:
        if (now - self._last_cleanup) < self._cleanup_interval:
            return
        self._last_cleanup = now
        cutoff = now - self.window
        expired = [ip for ip, b in self._buckets.items() if not b.timestamps or b.timestamps[-1] < cutoff]
        for ip in expired:
            del self._buckets[ip]

    def is_allowed(self, request: Request) -> bool:
        if not request.url.path.startswith("/api/"):
            return True
        now = time.monotonic()
        self._cleanup(now)
        ip = self._client_ip(request)
        bucket = self._buckets[ip]
        cutoff = now - self.window
        bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]
        if len(bucket.timestamps) >= self.max_requests:
            return False
        bucket.timestamps.append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window: int = 60) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(max_requests=max_requests, window=window)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.limiter.is_allowed(request):
            return JSONResponse(
                status_code=429,
                content={"detail": "Çok fazla istek gönderildi. Lütfen biraz bekleyin.", "code": "rate_limited"},
                headers={"Retry-After": str(self.limiter.window)},
            )
        return await call_next(request)
