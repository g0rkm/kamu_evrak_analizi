import asyncio
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("timeout")


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Istek zaman asimi middleware'i - uzun suren istekleri keser."""

    def __init__(self, app, timeout_seconds: int = 300):
        super().__init__(app)
        self.timeout = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
            duration = time.time() - start
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            return response
        except asyncio.TimeoutError:
            duration = time.time() - start
            logger.warning(
                f"Request timeout: {request.method} {request.url.path} "
                f"({duration:.1f}s > {self.timeout}s)"
            )
            return JSONResponse(
                status_code=504,
                content={
                    "detail": "Istek zaman asimina ugradi",
                    "code": "timeout",
                    "timeout_seconds": self.timeout,
                }
            )


class ActiveJobsMiddleware(BaseHTTPMiddleware):
    """Aktif is sayacini yoneten middleware."""

    async def dispatch(self, request: Request, call_next):
        app = request.app
        if hasattr(app.state, "active_jobs"):
            app.state.active_jobs += 1
        try:
            response = await call_next(request)
            return response
        finally:
            if hasattr(app.state, "active_jobs"):
                app.state.active_jobs -= 1
