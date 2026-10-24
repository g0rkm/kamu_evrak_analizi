import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, metrics_service_getter):
        super().__init__(app)
        self.metrics_service_getter = metrics_service_getter

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        try:
            metrics_service = self.metrics_service_getter()
            if metrics_service is not None:
                metrics_service.record_request(
                    method=request.method,
                    path=path,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )
        except Exception:
            pass

        return response
