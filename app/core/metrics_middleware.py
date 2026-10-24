import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, metrics_service_getter, error_tracker_getter=None, profiler_getter=None):
        super().__init__(app)
        self.metrics_service_getter = metrics_service_getter
        self.error_tracker_getter = error_tracker_getter
        self.profiler_getter = profiler_getter

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

            if response.status_code >= 400 and self.error_tracker_getter is not None:
                error_tracker = self.error_tracker_getter()
                if error_tracker is not None:
                    error_tracker.track(
                        error_type=str(response.status_code),
                        message=path,
                        path=path
                    )

            if self.profiler_getter is not None:
                profiler = self.profiler_getter()
                if profiler is not None:
                    profiler.record(
                        method=request.method,
                        path=path,
                        duration_ms=duration_ms,
                        status_code=response.status_code
                    )
        except Exception:
            pass

        return response
